"""Parse the repeatable record sections of a persona's ``persona.toml``."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Final, cast

from ..core.iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ..core.period import is_filing_period_token
from .persona_identities import _Roles
from .persona_toml import (
    _amount,
    _bool,
    _choice,
    _date,
    _keys,
    _optional_string,
    _string,
    _strings,
    _Table,
    _table,
    _tables,
)
from .persona_types import (
    BIOGRAPHICAL_DATE_KEYS,
    GENERAL_BASES_CARRY_FAMILY,
    PRIOR_CARRY_BOXES,
    AeatFiling,
    AttestedPriorValue,
    CadastralValue,
    CalculatedReturns,
    FiledReturns,
    HouseholdMember,
    IdentityRef,
    InventoryBook,
    LeasedPremises,
    LocalObservation,
    Officer,
    OwnAccount,
    OwnAccountDesignation,
    PersonaDate,
    PriorCarries,
    PriorValueSource,
    ProfileRow,
    ProfileValue,
    RentalLedgerLink,
    RentalProperty,
    WithholdingCertificate,
    WorkIncomeNoneStatement,
    WorkInput,
    YearToken,
    _fail,
)

_IDENTITY_FIELDS = (
    "value",
    "full_name",
    "primer_apellido",
    "segundo_apellido",
    "nombre",
    "razon_social",
    "name",
    "surnames",
    "legal_name",
)


def _profile_value(question_id: str, value: object, where: str, roles: _Roles) -> ProfileValue:
    if isinstance(value, str | bool):
        return value
    if isinstance(value, list):
        return _strings({question_id: value}, question_id, where)
    table = _table(value, where)
    if "identity" in table:
        _keys(table, where, required=frozenset({"identity"}), optional=frozenset({"field"}))
        field = _choice(_string(table, "field", where), _IDENTITY_FIELDS, where) if "field" in table else "value"
        return IdentityRef(role=roles(table["identity"], where), field=field)
    return _date(table, where, biographical=question_id in BIOGRAPHICAL_DATE_KEYS)


_DEDICATED_ROW_SECTIONS: Final = frozenset({"activities"})
"""Repeatable sections a dedicated persona block records, so ``[[profile_rows]]`` refuses them."""


def _profile_row(table: _Table, where: str, roles: _Roles) -> ProfileRow:
    _keys(table, where, required=frozenset({"section", "values"}))
    section = _string(table, "section", where)
    if section in _DEDICATED_ROW_SECTIONS:
        raise _fail(where, f"section {section!r} has its own block")
    values = _table(table["values"], f"{where}.values")
    if not values:
        raise _fail(where, "values must name at least one field")
    return ProfileRow(
        section=section,
        values=tuple(
            (key, _row_value(key, value, f"{where}.values.{key}", roles)) for key, value in sorted(values.items())
        ),
    )


def _row_value(key: str, value: object, where: str, roles: _Roles) -> ProfileValue:
    """A ``[[profile_rows]]`` value; its date records a past event (a deed, an appointment), so it may precede the floor."""
    if isinstance(value, Mapping) and "identity" not in value:
        return _date(value, where, biographical=True)
    return _profile_value(key, value, where, roles)


def _household(rows: object, where: str, leaves: frozenset[str], roles: _Roles) -> tuple[HouseholdMember, ...]:
    members: list[HouseholdMember] = []
    for index, table in enumerate(_tables(rows, where)):
        here = f"{where}[{index}]"
        _keys(table, here, required=frozenset(), optional=leaves | {"identity"})
        values: list[tuple[str, str | PersonaDate]] = []
        for key, value in table.items():
            if key == "identity":
                continue
            if key == "birth_date":
                values.append((key, _date(value, f"{here}.{key}", biographical=True)))
            elif isinstance(value, str):
                values.append((key, value))
            else:
                raise _fail(here, f"{key} must be the leaf's canonical string")
        identity = roles(table["identity"], here) if "identity" in table else None
        members.append(HouseholdMember(identity=identity, leaves=tuple(values)))
    return tuple(members)


def _own_account_designation(table: _Table, where: str, modelos: tuple[str, ...]) -> OwnAccountDesignation:
    _keys(table, where, required=frozenset({"role"}), optional=frozenset({"modelo"}))
    modelo = _optional_string(table, "modelo", where)
    if modelo is not None and modelo not in modelos:
        raise _fail(where, f"modelo {modelo!r} is not one of the persona's modelos {list(modelos)}")
    return OwnAccountDesignation(
        role=_choice(_string(table, "role", where), ("charge", "refund"), where), modelo=modelo
    )


def _own_account(table: _Table, where: str, modelos: tuple[str, ...]) -> OwnAccount:
    _keys(table, where, required=frozenset({"label", "holding", "iban"}), optional=frozenset({"designations"}))
    iban = normalise_iban(_string(table, "iban", where))
    if not IBAN_SHAPE_RE.match(iban) or iban_mod_97(iban) != 1:
        raise _fail(where, "iban is not a checksum-valid ISO 13616 account number")
    return OwnAccount(
        label=_string(table, "label", where),
        holding=_choice(_string(table, "holding", where), ("titular", "cotitular"), where),
        iban=iban,
        designations=tuple(
            _own_account_designation(item, f"{where} designations[{index}]", modelos)
            for index, item in enumerate(_tables(table.get("designations"), where))
        ),
    )


def _check_designations(accounts: tuple[OwnAccount, ...], where: str) -> None:
    """Refuse two designations of one role and scope, which the register holds once."""
    keys = [(item.role, item.modelo) for account in accounts for item in account.designations]
    if len(keys) != len(set(keys)):
        raise _fail(where, "two designations state one role and scope")


def _attestation_family(value: object, where: str) -> str:
    """The carry family token a statement names; the registry's family members are checked by the user of the statement."""
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise _fail(where, f"{value!r} is not a carry family token (lower snake case)")
    return value


def _prior_carries(table: _Table, where: str, modelos: tuple[str, ...]) -> PriorCarries:
    _keys(table, where, required=frozenset({"year", "family"}), optional=frozenset({"nothing_pending", "pending"}))
    if "100" not in modelos:
        raise _fail(where, "the pending carries are a Modelo 100 statement, and the persona files no Modelo 100")
    year = YearToken.parse(table["year"], where=f"{where}.year")
    family = _attestation_family(table["family"], f"{where}.family")
    if ("nothing_pending" in table) == ("pending" in table):
        raise _fail(where, "state either nothing_pending = true or the pending amounts")
    if "nothing_pending" in table:
        if not _bool(table, "nothing_pending", where):
            raise _fail(where, "nothing_pending can only be stated true; state the pending amounts instead")
        return PriorCarries(year=year, family=family, pending=())
    boxes = _table(table["pending"], f"{where}.pending")
    if not boxes:
        raise _fail(where, "pending must name at least one box; state nothing_pending = true when none is pending")
    pending: list[tuple[str, Decimal]] = []
    for box, text in sorted(boxes.items()):
        if family == GENERAL_BASES_CARRY_FAMILY:
            if box not in PRIOR_CARRY_BOXES:
                raise _fail(where, f"box {box!r} is not one of {list(PRIOR_CARRY_BOXES)}")
        elif not re.fullmatch(r"\d{4}", box):
            raise _fail(where, f"box {box!r} is not a four-digit casilla")
        amount = _amount(text, f"{where}.pending.{box}")
        if amount <= 0:
            raise _fail(where, f"box {box} must hold a positive amount; a box left out is stated to hold nothing")
        pending.append((box, amount))
    return PriorCarries(year=year, family=family, pending=tuple(pending))


def _withholding(table: _Table, where: str, roles: _Roles) -> WithholdingCertificate:
    _keys(
        table,
        where,
        required=frozenset({"payer", "ejercicio", "income_class", "origin", "importe_integro", "retencion"}),
        optional=frozenset({"cotizaciones_seguridad_social", "reducciones_aplicables", "gastos_deducibles"}),
    )
    cotizaciones = table.get("cotizaciones_seguridad_social")
    reducciones = table.get("reducciones_aplicables")
    gastos = table.get("gastos_deducibles")
    return WithholdingCertificate(
        payer=roles(table["payer"], where),
        ejercicio=YearToken.parse(table["ejercicio"], where=f"{where}.ejercicio"),
        income_class=_string(table, "income_class", where),
        origin=_choice(_string(table, "origin", where), ("payer_certificate", "operator_declaration"), where),
        importe_integro=_amount(table["importe_integro"], f"{where}.importe_integro"),
        retencion=_amount(table["retencion"], f"{where}.retencion"),
        cotizaciones_seguridad_social=None if cotizaciones is None else _amount(cotizaciones, where),
        reducciones_aplicables=None if reducciones is None else _amount(reducciones, f"{where}.reducciones_aplicables"),
        gastos_deducibles=None if gastos is None else _amount(gastos, f"{where}.gastos_deducibles"),
    )


def _work_income_none(table: _Table, where: str) -> WorkIncomeNoneStatement:
    _keys(table, where, required=frozenset({"ejercicio"}), optional=frozenset())
    return WorkIncomeNoneStatement(ejercicio=YearToken.parse(table["ejercicio"], where=f"{where}.ejercicio"))


def _cadastral_values(value: object, where: str) -> tuple[CadastralValue, ...]:
    values: list[CadastralValue] = []
    for index, table in enumerate(_tables(value, where)):
        here = f"{where}[{index}]"
        _keys(table, here, required=frozenset({"year", "total", "construccion"}))
        values.append(
            CadastralValue(
                year=YearToken.parse(table["year"], where=f"{here}.year"),
                total=_amount(table["total"], f"{here}.total"),
                construccion=_amount(table["construccion"], f"{here}.construccion"),
            )
        )
    return tuple(values)


def _ledger_links(value: object, where: str) -> tuple[RentalLedgerLink, ...]:
    links: list[RentalLedgerLink] = []
    for index, table in enumerate(_tables(value, where)):
        here = f"{where}[{index}]"
        _keys(table, here, required=frozenset({"ref_prefix", "target"}), optional=frozenset({"gasto"}))
        target = _choice(_string(table, "target", here), ("arrendamiento", "inmueble"), here)
        gasto = _optional_string(table, "gasto", here)
        if (gasto is not None) != (target == "inmueble"):
            raise _fail(here, "a link to the property states its expense concept and a link to the lease none")
        links.append(
            RentalLedgerLink(
                ref_prefix=_string(table, "ref_prefix", here),
                target=target,
                gasto=gasto,
            )
        )
    return tuple(links)


def _rental(table: _Table, where: str, roles: _Roles) -> RentalProperty:
    _keys(
        table,
        where,
        required=frozenset(
            {
                "id",
                "use",
                "tenant",
                "contract_start",
                "monthly_rent",
                "days_let",
                "amortization_base",
                "amortization_rate",
                "situacion",
                "referencia_catastral",
                "naturaleza",
                "titularidad_regimen",
                "titular",
                "porcentaje_propiedad",
                "importe_adquisicion",
                "valor_suelo",
                "adquisicion_titulo",
                "fecha_adquisicion",
                "gastos_tributos_adquisicion",
                "valores_catastrales",
                "fecha_contrato",
                "fecha_inicio",
                "uso_vivienda",
                "zona_tensionada",
                "primer_arrendamiento_vivienda",
                "arrendatario_pariente_art24",
                "incumple_lau_17_6",
                "ledger_links",
            }
        ),
        optional=frozenset({"amortization_base_note", "arrendado_desde", "pendiente_intereses_reparacion"}),
    )
    contract_start = _date(table["contract_start"], f"{where}.contract_start", biographical=True)
    fecha_contrato = _date(table["fecha_contrato"], f"{where}.fecha_contrato", biographical=True)
    fecha_inicio = _date(table["fecha_inicio"], f"{where}.fecha_inicio", biographical=True)
    if fecha_contrato != contract_start or fecha_inicio != contract_start:
        raise _fail(where, "the lease is signed and starts on contract_start")
    reference = _cadastral_reference(table["referencia_catastral"], f"{where}.referencia_catastral")
    return RentalProperty(
        id=_string(table, "id", where),
        use=_string(table, "use", where),
        tenant=roles(table["tenant"], where),
        contract_start=contract_start,
        monthly_rent=_amount(table["monthly_rent"], where),
        days_let=_string(table, "days_let", where),
        amortization_base=_amount(table["amortization_base"], where),
        amortization_rate=_amount(table["amortization_rate"], where),
        amortization_base_note=_optional_string(table, "amortization_base_note", where),
        situacion=_string(table, "situacion", where),
        referencia_catastral=reference,
        naturaleza=_string(table, "naturaleza", where),
        titularidad_regimen=_string(table, "titularidad_regimen", where),
        titular=_string(table, "titular", where),
        porcentaje_propiedad=_amount(table["porcentaje_propiedad"], where),
        importe_adquisicion=_amount(table["importe_adquisicion"], where),
        valor_suelo=_amount(table["valor_suelo"], where),
        adquisicion_titulo=_string(table, "adquisicion_titulo", where),
        fecha_adquisicion=_date(table["fecha_adquisicion"], f"{where}.fecha_adquisicion", biographical=True),
        gastos_tributos_adquisicion=_amount(table["gastos_tributos_adquisicion"], where),
        valores_catastrales=_cadastral_values(table["valores_catastrales"], f"{where}.valores_catastrales"),
        fecha_contrato=fecha_contrato,
        fecha_inicio=fecha_inicio,
        uso_vivienda=_bool(table, "uso_vivienda", where),
        zona_tensionada=_bool(table, "zona_tensionada", where),
        primer_arrendamiento_vivienda=_bool(table, "primer_arrendamiento_vivienda", where),
        arrendatario_pariente_art24=_bool(table, "arrendatario_pariente_art24", where),
        incumple_lau_17_6=_bool(table, "incumple_lau_17_6", where),
        ledger_links=_ledger_links(table["ledger_links"], f"{where}.ledger_links"),
        arrendado_desde=(
            _date(table["arrendado_desde"], f"{where}.arrendado_desde", biographical=True)
            if "arrendado_desde" in table
            else None
        ),
        pendiente_intereses_reparacion=(
            _amount(table["pendiente_intereses_reparacion"], f"{where}.pendiente_intereses_reparacion")
            if "pendiente_intereses_reparacion" in table
            else None
        ),
    )


def _officer(table: _Table, where: str, roles: _Roles) -> Officer:
    _keys(table, where, required=frozenset({"identity", "role", "remunerated"}))
    return Officer(
        identity=roles(table["identity"], where),
        role=_string(table, "role", where),
        remunerated=_bool(table, "remunerated", where),
    )


_FILED_PERIODS: Final[tuple[str, ...]] = ("1T", "2T", "3T", "4T", "0A")
"""The period codes a filed return may name, in the order their windows close within a year."""


_IVA_COMPENSATION_MODELO: Final[str] = "303"


def _filed_returns(table: _Table, where: str) -> FiledReturns:
    _keys(
        table,
        where,
        required=frozenset({"modelo", "year", "periods"}),
        optional=frozenset({"iva_compensation_carried_in"}),
    )
    modelo = _string(table, "modelo", where)
    periods = _return_periods(table, where)
    carried = table.get("iva_compensation_carried_in")
    if carried is not None and modelo != _IVA_COMPENSATION_MODELO:
        raise _fail(where, f"only a Modelo {_IVA_COMPENSATION_MODELO} block states iva_compensation_carried_in")
    return FiledReturns(
        modelo=modelo,
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        periods=periods,
        iva_compensation_carried_in=None
        if carried is None
        else _amount(carried, f"{where}.iva_compensation_carried_in"),
    )


def _return_periods(table: _Table, where: str) -> tuple[str, ...]:
    periods = _strings(table, "periods", where)
    for period in periods:
        _choice(period, _FILED_PERIODS, where)
    if list(periods) != sorted(set(periods), key=_FILED_PERIODS.index):
        raise _fail(where, "periods must be distinct and in calendar order")
    return periods


def _calculated_returns(table: _Table, where: str) -> CalculatedReturns:
    _keys(table, where, required=frozenset({"modelo", "year", "periods"}))
    return CalculatedReturns(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        periods=_return_periods(table, where),
    )


def _local_observation(table: _Table, where: str) -> LocalObservation:
    _keys(table, where, required=frozenset({"modelo", "year", "period", "casillas", "reason"}))
    casillas = _table(table["casillas"], f"{where}.casillas")
    if not casillas:
        raise _fail(where, "casillas must name at least one casilla")
    values: list[tuple[str, str]] = []
    for casilla, value in sorted(casillas.items()):
        _amount(value, f"{where}.casillas.{casilla}")
        values.append((casilla, cast(str, value)))
    return LocalObservation(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        period=_choice(_string(table, "period", where), _FILED_PERIODS, where),
        casillas=tuple(values),
        reason=_string(table, "reason", where),
    )


_ADDRESS_REQUIRED: Final = frozenset(
    {
        "province_code",
        "municipality_code",
        "municipality",
        "locality",
        "postal_code",
        "street_type",
        "street_name",
        "number_type",
        "house_number",
    }
)


_ADDRESS_OPTIONAL: Final = frozenset(
    {"number_qualifier", "block", "portal", "staircase", "floor", "door", "complement"}
)


_CADASTRAL_WEIGHTS: Final = (13, 15, 12, 5, 4, 17, 9, 21, 3, 7, 1)


_CADASTRAL_CONTROL_LETTERS: Final = "MQWERTYUIOPASDFGHJKLBZX"


_CADASTRAL_REFERENCE: Final = re.compile(r"[0-9A-Z]{14}[0-9]{4}[A-Z]{2}")


_AEAT_CSV: Final = re.compile(r"[A-Z0-9]{16}")


_JUSTIFICANTE_NUMBER: Final = re.compile(r"[0-9]{13}")


def _aeat_filing(table: _Table, where: str) -> AeatFiling:
    _keys(
        table,
        where,
        required=frozenset({"modelo", "year", "period", "presented", "csv", "justificante", "casillas", "reason"}),
    )
    casillas = _table(table["casillas"], f"{where}.casillas")
    if not casillas:
        raise _fail(where, "casillas must name at least one casilla")
    values: list[tuple[str, str]] = []
    for casilla, value in sorted(casillas.items()):
        _amount(value, f"{where}.casillas.{casilla}")
        values.append((casilla, cast(str, value)))
    csv_code = _string(table, "csv", where)
    if _AEAT_CSV.fullmatch(csv_code) is None:
        raise _fail(where, "csv is the 16-character Código Seguro de Verificación, uppercase letters and digits")
    number = _string(table, "justificante", where)
    if _JUSTIFICANTE_NUMBER.fullmatch(number) is None:
        raise _fail(where, "justificante is the 13-digit número de justificante")
    return AeatFiling(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        period=_choice(_string(table, "period", where), _FILED_PERIODS, where),
        presented=_date(table["presented"], f"{where}.presented", biographical=False),
        csv=csv_code,
        justificante=number,
        casillas=tuple(values),
        reason=_string(table, "reason", where),
    )


def _attested_prior_value(table: _Table, where: str) -> AttestedPriorValue:
    _keys(
        table,
        where,
        required=frozenset({"modelo", "period", "year", "binding", "value", "sources", "derivation", "legal_ref"}),
        optional=frozenset({"where_declared"}),
    )
    sources = tuple(
        _prior_value_source(source, f"{where}.sources[{index}]")
        for index, source in enumerate(_tables(table["sources"], where))
    )
    if not sources:
        raise _fail(where, "sources must name at least one earlier return")
    if len(set(sources)) != len(sources):
        raise _fail(where, "sources must name each earlier return once")
    legal_ref = _strings(table, "legal_ref", where)
    if not legal_ref:
        raise _fail(where, "legal_ref must name at least one provision")
    period = _string(table, "period", where)
    if not is_filing_period_token(period):
        raise _fail(where, f"{period!r} is not a filing period")
    return AttestedPriorValue(
        modelo=_string(table, "modelo", where),
        period=period,
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        binding=_string(table, "binding", where),
        value=_amount(table["value"], f"{where}.value"),
        sources=sources,
        derivation=_string(table, "derivation", where),
        legal_ref=legal_ref,
        where_declared=_bool(table, "where_declared", where) if "where_declared" in table else False,
    )


def _work_input(table: _Table, where: str) -> WorkInput:
    _keys(table, where, required=frozenset({"modelo", "year", "period", "roles", "sources", "reason"}))
    roles = _table(table["roles"], f"{where}.roles")
    if not roles:
        raise _fail(where, "roles must name at least one role")
    values: list[tuple[str, str]] = []
    for role, value in sorted(roles.items()):
        _amount(value, f"{where}.roles.{role}")
        values.append((role, cast(str, value)))
    sources = _table(table["sources"], f"{where}.sources")
    missing = sorted(set(roles) - set(sources))
    if missing:
        raise _fail(where, f"sources must state where each role's value comes from; none for {missing}")
    extra = sorted(set(sources) - set(roles))
    if extra:
        raise _fail(where, f"sources name roles the block does not give: {extra}")
    for role, text in sources.items():
        if not isinstance(text, str) or not text.strip():
            raise _fail(where, f"sources.{role} must be a non-empty string")
    return WorkInput(
        modelo=_string(table, "modelo", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        period=_choice(_string(table, "period", where), _FILED_PERIODS, where),
        roles=tuple(values),
        sources=tuple((role, cast(str, sources[role])) for role, _ in values),
        reason=_string(table, "reason", where),
    )


def _prior_value_source(source: _Table, where: str) -> PriorValueSource:
    """One earlier return an attested figure stands in for; its period is any period a taxpayer files."""
    _keys(source, where, required=frozenset({"modelo", "year", "period"}))
    period = _string(source, "period", where)
    if not is_filing_period_token(period):
        raise _fail(where, f"{period!r} is not a filing period")
    return PriorValueSource(
        modelo=_string(source, "modelo", where),
        year=YearToken.parse(source["year"], where=f"{where}.year"),
        period=period,
    )


def _cadastral_character_value(character: str) -> int:
    if character.isdigit():
        return int(character)
    # Catastro numbers the alphabet with Ñ after N, so every letter after N moves up by one.
    return ord(character) - ord("A") + (1 if character <= "N" else 2)


def cadastral_control_characters(reference: str) -> str:
    """Return the two Catastro control letters of an 18-character urban cadastral reference.

    The first letter checks the parcel (characters 1-7), the second the map
    sheet (characters 8-14), each followed by the four-digit property number:
    the weighted sum of those eleven characters, modulo 23, indexes the
    control alphabet.
    """
    controls = ""
    for part in (reference[0:7], reference[7:14]):
        characters = part + reference[14:18]
        total = sum(
            weight * _cadastral_character_value(character)
            for weight, character in zip(_CADASTRAL_WEIGHTS, characters, strict=True)
        )
        controls += _CADASTRAL_CONTROL_LETTERS[total % len(_CADASTRAL_CONTROL_LETTERS)]
    return controls


def _cadastral_reference(value: object, where: str) -> str:
    if not isinstance(value, str) or _CADASTRAL_REFERENCE.fullmatch(value) is None:
        raise _fail(where, "cadastral_reference must be a 20-character urban cadastral reference")
    if cadastral_control_characters(value[:18]) != value[18:]:
        raise _fail(where, "cadastral_reference control characters do not match the Catastro algorithm")
    return value


def _leased_premises(table: _Table, where: str, roles: _Roles) -> LeasedPremises:
    _keys(
        table,
        where,
        required=frozenset(
            {
                "key",
                "landlord",
                "landlord_tax_status",
                "landlord_tax_regime",
                "landlord_province",
                "situation",
                "modality",
                "address",
            }
        ),
        optional=frozenset({"cadastral_reference"}),
    )
    address = _table(table["address"], f"{where}.address")
    _keys(address, f"{where}.address", required=_ADDRESS_REQUIRED, optional=_ADDRESS_OPTIONAL)
    if not all(isinstance(value, str) for value in address.values()):
        raise _fail(f"{where}.address", "address values must be strings")
    reference = table.get("cadastral_reference")
    return LeasedPremises(
        key=_string(table, "key", where),
        landlord=roles(table["landlord"], f"{where}.landlord"),
        landlord_tax_status=_string(table, "landlord_tax_status", where),
        landlord_tax_regime=_string(table, "landlord_tax_regime", where),
        landlord_province=_string(table, "landlord_province", where),
        situation=_string(table, "situation", where),
        cadastral_reference=None
        if reference is None
        else _cadastral_reference(reference, f"{where}.cadastral_reference"),
        modality=_string(table, "modality", where),
        address=tuple((key, cast(str, value)) for key, value in address.items()),
    )


def _inventory_book(table: _Table, where: str) -> InventoryBook:
    _keys(
        table,
        where,
        required=frozenset({"activity", "year", "valuation_method", "opening_stock", "closing_stock", "statement"}),
        optional=frozenset({"purchases"}),
    )
    opening = _amount(table["opening_stock"], f"{where}.opening_stock")
    closing = _amount(table["closing_stock"], f"{where}.closing_stock")
    purchases = _strings(table, "purchases", where) if "purchases" in table else ()
    if opening < 0 or closing < 0:
        raise _fail(where, "existencias are valued at a nonnegative amount")
    if closing != opening and not purchases:
        raise _fail(where, "a book with no movement closes at its opening stock")
    return InventoryBook(
        activity=_string(table, "activity", where),
        year=YearToken.parse(table["year"], where=f"{where}.year"),
        valuation_method=_string(table, "valuation_method", where),
        opening_stock=opening,
        closing_stock=closing,
        statement=_string(table, "statement", where),
        purchases=purchases,
    )


def filed_period_order(period: str) -> int:
    """The calendar position of a filed period code within its year."""
    return _FILED_PERIODS.index(period)


__all__ = [
    "cadastral_control_characters",
    "filed_period_order",
]
