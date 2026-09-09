"""Withholding row grouping and record-design completion rules."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from . import _withholding_193_fields as _withholding_193
from .errors import RegistryValidationError
from .withholding_bindings import (
    WithholdingGrouping,
    WithholdingObservation,
)

_finalise_193_instrument_fields = _withholding_193.finalise_193_instrument_fields
_finalise_193_primary_fields = _withholding_193.finalise_193_primary_fields

_DATOS_ADICIONALES_CLAVES: frozenset[str] = frozenset({"A", "C"})
_DATOS_ADICIONALES_B_SUBCLAVES: frozenset[str] = frozenset({"01", "03", "04", "99"})
_REDUCCIONES_F_G_SUBCLAVES: frozenset[str] = frozenset({"01", "02", "03", "04", "05", "06"})
_REDUCCIONES_G_SUBCLAVES: frozenset[str] = frozenset({"01", "02", "03", "04", "05", "06", "08"})
_GASTOS_E_SUBCLAVES: frozenset[str] = frozenset({"01", "02"})
_GASTOS_L_SUBCLAVES: frozenset[str] = frozenset({"05", "10", "27"})


def _declares_datos_adicionales(clave: str, subclave: str) -> bool:
    """True for the claves the Modelo 190 design's 153-254 block applies to.

    The design names ``A``, ``B -subclaves 01, 03, 04 y 99-``, and ``C`` for the
    birth-year and family-situation positions specifically.
    """
    if str(clave) in _DATOS_ADICIONALES_CLAVES:
        return True
    return str(clave) == "B" and subclave in _DATOS_ADICIONALES_B_SUBCLAVES


def _declares_reducciones(clave: object, subclave: object) -> bool:
    """True for the claves the design's REDUCCIONES APLICABLES campo (171-183) applies to.

    Design: ``A``, ``B (subclaves 01, 03, 04 y 99)``, ``C``, ``E``, ``F
    (subclaves 01 a 06)``, ``G (subclaves 01 a 06 y 08)``, ``H`` e ``I``.
    """
    clave_code = str(clave)
    if clave_code in {"A", "C", "E", "H", "I"}:
        return True
    if clave_code == "B":
        return str(subclave) in _DATOS_ADICIONALES_B_SUBCLAVES
    if clave_code == "F":
        return str(subclave) in _REDUCCIONES_F_G_SUBCLAVES
    if clave_code == "G":
        return str(subclave) in _REDUCCIONES_G_SUBCLAVES
    return False


def _declares_gastos(clave: object, subclave: object) -> bool:
    """True for the claves the design's GASTOS DEDUCIBLES campo (184-196) applies to.

    Design: ``A``, ``B (subclaves 01, 03, 04 y 99)``, ``C``, ``E (subclaves 01
    y 02)``, and exceptionally ``L.05``, ``L.10`` and ``L.27``.
    """
    clave_code = str(clave)
    if clave_code in {"A", "C"}:
        return True
    if clave_code == "B":
        return str(subclave) in _DATOS_ADICIONALES_B_SUBCLAVES
    if clave_code == "E":
        return str(subclave) in _GASTOS_E_SUBCLAVES
    if clave_code == "L":
        return str(subclave) in _GASTOS_L_SUBCLAVES
    return False


def _require_consistent_identity_facts(
    bucket: dict[str, Decimal | str],
    observation: WithholdingObservation,
    *,
    fields: tuple[str, ...],
) -> None:
    """Merge one cohort observation's identity facts and refuse contradictions.

    Amounts accumulate, but a perceptor has ONE province, one birth year and one
    family situation: the first observation that carries a fact sets it, a later
    observation that disagrees is a finding the resolver must surface rather than
    silently keep the first value, and a later observation that carries nothing
    leaves the established fact alone.
    """
    for field in fields:
        stored = bucket.get(field)
        incoming = getattr(observation, field)
        if incoming is None:
            continue
        if stored is None:
            bucket[field] = incoming
        elif stored != incoming:
            raise RegistryValidationError(
                f"withholding rows for perceptor {observation.perceptor_tax_id!r} disagree on "
                f"{field!r}: {stored!r} vs {incoming!r}",
            )


_CLAVE_L29_SUBCLAVE = "29"

#: The 2025 edition's five per-type prestacion flags (positions 390-394), each
#: always recorded for clave B.01.
_PENSION_PRESACION_TYPE_FIELDS: tuple[str, ...] = (
    "pension_prestacion_jubilacion",
    "pension_prestacion_viudedad",
    "pension_prestacion_incapacidad",
    "pension_prestacion_no_contributiva",
    "pension_prestacion_resto",
)

#: The design's family-composition count positions (223-253), all declared only
#: for claves A, B (subclaves 01, 03, 04, 99) and C, all zeros when no content.
_DATOS_ADICIONALES_COUNT_FIELDS: tuple[str, ...] = (
    "descendants_under_3_total",
    "descendants_under_3_whole",
    "descendants_rest_total",
    "descendants_rest_whole",
    "descendants_disabled_33_65_total",
    "descendants_disabled_33_65_whole",
    "descendants_disabled_mobility_total",
    "descendants_disabled_mobility_whole",
    "descendants_disabled_65_plus_total",
    "descendants_disabled_65_plus_whole",
    "ascendants_under_75_total",
    "ascendants_under_75_whole",
    "ascendants_75_plus_total",
    "ascendants_75_plus_whole",
    "ascendants_disabled_33_65_total",
    "ascendants_disabled_33_65_whole",
    "ascendants_disabled_mobility_total",
    "ascendants_disabled_mobility_whole",
    "ascendants_disabled_65_plus_total",
    "ascendants_disabled_65_plus_whole",
    "first_child_compute",
    "second_child_compute",
    "third_child_compute",
)


def _declares_incapacidad_dineraria(clave: object, subclave: object) -> bool:
    """True for the claves the dineraria incapacidad-laboral block applies to.

    Design: campos 255-281, claves ``A`` and ``B.01``.
    """
    clave_code = str(clave)
    return clave_code == "A" or (clave_code == "B" and str(subclave) == "01")


def _is_clave_l29(clave: object, subclave: object) -> bool:
    """True for the clave L.29 the design's unidad-de-convivencia block applies to."""
    return str(clave) == "L" and str(subclave) == _CLAVE_L29_SUBCLAVE


def _validate_required_scoped_field(
    *,
    field: str,
    value: Decimal | str | None,
    required_fields: frozenset[str],
    in_scope: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
    requirement_description: str,
) -> None:
    """Validate a design field that is required throughout one row scope.

    The Modelo 190 design distinguishes a contradictory supplied value from a
    missing value that the payer was required to record. Keeping those two
    outcomes in one helper prevents each field's branch pair from drifting.
    """
    if field not in required_fields:
        return
    if value is not None and not in_scope:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry {field}, {scope_description}",
        )
    if in_scope and value is None:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} require "
            f"{field} {requirement_description}: no observation carries it",
        )


def _reject_nonzero_outside_scope(
    *,
    field: str,
    value: Decimal | str | None,
    required_fields: frozenset[str],
    in_scope: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
) -> None:
    """Refuse a non-zero numeric fact outside the design's declared scope."""
    if field not in required_fields or value in (None, Decimal("0")) or in_scope:
        return
    raise RegistryValidationError(
        f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry {field}, {scope_description}",
    )


def _finalise_required_scoped_field(
    finalised: dict[str, Decimal | str],
    *,
    field: str,
    value: Decimal | str | None,
    required_fields: frozenset[str],
    in_scope: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
    requirement_description: str,
    default: str,
) -> None:
    """Validate and serialise a field required whenever its design scope applies."""
    _validate_required_scoped_field(
        field=field,
        value=value,
        required_fields=required_fields,
        in_scope=in_scope,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description=scope_description,
        requirement_description=requirement_description,
    )
    if field in required_fields:
        finalised[field] = str(value) if value is not None else default


def _finalise_optional_scoped_field(
    finalised: dict[str, Decimal | str],
    *,
    field: str,
    value: Decimal | str | None,
    required_fields: frozenset[str],
    in_scope: bool,
    perceptor_tax_id: str,
    clave: str,
    scope_description: str,
    default: str,
) -> None:
    """Serialise a field when supplied, rejecting values outside its scope."""
    if field not in required_fields:
        return
    if value is not None and not in_scope:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry {field}, {scope_description}",
        )
    finalised[field] = str(value) if value is not None else default


def _validate_190_spouse_field(
    *,
    spouse: Decimal | str | None,
    situacion_declared: bool,
    titular_declared: bool,
    spouse_context: bool,
    required_fields: frozenset[str],
    perceptor_tax_id: str,
    clave: str,
) -> None:
    """Validate the conditional Modelo 190 spouse or titular identity."""
    if "spouse_or_unit_titular_tax_id" not in required_fields:
        return
    if spouse is not None and not spouse_context and (situacion_declared or titular_declared):
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "spouse_or_unit_titular_tax_id, which design campo 17 declares only when "
            "situacion familiar is 2 or clave L.29 has titular clave 2",
        )
    if spouse_context and spouse is None:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} require "
            "spouse_or_unit_titular_tax_id (design campo 17): no observation carries it",
        )
    if spouse is not None and spouse == perceptor_tax_id:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r}: spouse_or_unit_titular_tax_id "
            "equals the perceptor's own NIF, which the design campo 17 excludes",
        )


def _finalise_190_identity_fields(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    subclave: str,
    perceptor_tax_id: str,
) -> None:
    datos_adicionales = _declares_datos_adicionales(clave, subclave)
    is_clave_a = clave == "A"
    is_clave_l29 = _is_clave_l29(clave, subclave)
    identity_fields = (
        (
            "perceptor_birth_year",
            row.get("perceptor_birth_year"),
            datos_adicionales,
            "which design campo 15 declares only for claves A, B (subclaves 01, 03, 04, 99) and C",
            "(design campo 15)",
        ),
        (
            "perceptor_situacion_familiar",
            row.get("perceptor_situacion_familiar"),
            datos_adicionales,
            "which design campo 16 declares only for claves A, B (subclaves 01, 03, 04, 99) and C",
            "(design campo 16)",
        ),
        (
            "disability_clave",
            row.get("disability_clave"),
            datos_adicionales,
            "which design campo 18 declares only for claves A, B (subclaves 01, 03, 04, 99) and C",
            "(design campo 18, clave 0 for no disability)",
        ),
        (
            "contract_relation_clave",
            row.get("contract_relation_clave"),
            is_clave_a,
            "which design campo 19 declares only for clave A",
            "(design campo 19)",
        ),
        (
            "unit_convivencia_titular_clave",
            row.get("unit_convivencia_titular_clave"),
            is_clave_l29,
            "which design campo 20 declares only for clave L.29",
            "(design campo 20)",
        ),
        (
            "geographic_mobility_clave",
            row.get("geographic_mobility_clave"),
            is_clave_a,
            "which design campo 21 declares only for clave A",
            "(design campo 21)",
        ),
    )
    for field, value, in_scope, scope_description, requirement_description in identity_fields:
        _validate_required_scoped_field(
            field=field,
            value=value,
            required_fields=required_fields,
            in_scope=in_scope,
            perceptor_tax_id=perceptor_tax_id,
            clave=clave,
            scope_description=scope_description,
            requirement_description=requirement_description,
        )

    situacion_declared = "perceptor_situacion_familiar" in required_fields
    titular_declared = "unit_convivencia_titular_clave" in required_fields
    situacion = row.get("perceptor_situacion_familiar")
    titular = row.get("unit_convivencia_titular_clave")
    _validate_190_spouse_field(
        spouse=row.get("spouse_or_unit_titular_tax_id"),
        situacion_declared=situacion_declared,
        titular_declared=titular_declared,
        spouse_context=(datos_adicionales and situacion_declared and situacion is not None and str(situacion) == "2")
        or (is_clave_l29 and titular_declared and titular is not None and str(titular) == "2"),
        required_fields=required_fields,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
    )


def _finalise_190_declaration_fields(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    subclave: str,
    perceptor_tax_id: str,
    finalised: dict[str, Decimal | str],
) -> None:
    datos_adicionales = _declares_datos_adicionales(clave, subclave)

    amount_fields = (
        (
            "reducciones_aplicables",
            row.get("reducciones_aplicables"),
            _declares_reducciones(clave, subclave),
            "which design campo 22 declares only for claves A, B (01, 03, 04, 99), C, E, F "
            "(01-06), G (01-06, 08), H and I",
        ),
        (
            "gastos_deducibles",
            row.get("gastos_deducibles"),
            _declares_gastos(clave, subclave),
            "which design campo 23 declares only for claves A, B (01, 03, 04, 99), C, E "
            "(01, 02) and exceptionally L.05, L.10, L.27",
        ),
        (
            "pension_compensatoria",
            row.get("pension_compensatoria"),
            datos_adicionales,
            "which design campo 24 declares only for claves A, B (01, 03, 04, 99) and C",
        ),
        (
            "anualidades_alimentos",
            row.get("anualidades_alimentos"),
            datos_adicionales,
            "which design campo 25 declares only for claves A, B (01, 03, 04, 99) and C",
        ),
    )
    for field, value, in_scope, scope_description in amount_fields:
        _reject_nonzero_outside_scope(
            field=field,
            value=value,
            required_fields=required_fields,
            in_scope=in_scope,
            perceptor_tax_id=perceptor_tax_id,
            clave=clave,
            scope_description=scope_description,
        )
    for count_field in _DATOS_ADICIONALES_COUNT_FIELDS:
        _reject_nonzero_outside_scope(
            field=count_field,
            value=row.get(count_field),
            required_fields=required_fields,
            in_scope=datos_adicionales,
            perceptor_tax_id=perceptor_tax_id,
            clave=clave,
            scope_description=(
                "which the design's family-composition campos declare only for claves A, B (01, 03, 04, 99) and C"
            ),
        )
    _finalise_required_scoped_field(
        finalised,
        field="housing_loan_communication_clave",
        value=row.get("housing_loan_communication_clave"),
        required_fields=required_fields,
        in_scope=datos_adicionales,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description=("which design campo 27 declares only for claves A, B (01, 03, 04, 99) and C"),
        requirement_description=("(design campo 27, clave 0 for never applied)"),
        default=" ",
    )
    for count_field in _DATOS_ADICIONALES_COUNT_FIELDS:
        value = row.get(count_field)
        finalised[count_field] = str(value) if value is not None else "0"


def _validate_190_foral_scope(
    *,
    foral_parts: tuple[Decimal, ...],
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Reject foral amounts on rows outside Modelo 190 clave E."""
    if any(part != 0 for part in foral_parts) and clave != "E":
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "foral retentions, which design campo 35 declares exclusively for clave E",
        )


def _validate_190_foral_total(
    *,
    foral_total: Decimal,
    clave_e_total: Decimal,
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Require the clave-E foral split to reconcile with row totals."""
    if clave != "E":
        return
    if foral_total == 0 and clave_e_total != 0:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave E require "
            "foral retentions (design campo 35): the payer must record where the "
            "retenciones and ingresos a cuenta were ingresados",
        )
    if foral_total != clave_e_total:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave E carry foral "
            f"retentions summing to {foral_total}, which design campo 35 requires to equal "
            f"the row's retenciones practicadas plus ingresos a cuenta ({clave_e_total})",
        )


def _validate_190_foral_fields(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Validate the Modelo 190 clave-E split across the five foral slots."""
    if "foral_retention_estatal" not in required_fields:
        return
    foral_parts = tuple(
        _numeric_slot(row, field)
        for field in (
            "foral_retention_estatal",
            "foral_retention_navarra",
            "foral_retention_araba",
            "foral_retention_gipuzkoa",
            "foral_retention_bizkaia",
        )
    )
    foral_total = sum(foral_parts, Decimal("0"))
    retencion_practicada = _numeric_slot(row, "retencion_practicada")
    ingreso_a_cuenta = _numeric_slot(row, "ingreso_a_cuenta")
    clave_e_total = retencion_practicada + ingreso_a_cuenta
    _validate_190_foral_scope(
        foral_parts=foral_parts,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    _validate_190_foral_total(
        foral_total=foral_total,
        clave_e_total=clave_e_total,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )


def _validate_190_emerging_stock_clave(
    *,
    stock: Decimal | str | None,
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Reject a stock flag on a non-A Modelo 190 row."""
    if stock is not None and clave != "A":
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "emerging_stock_excess_clave, which design campo 36 declares only for clave A",
        )


def _validate_190_emerging_stock_content(
    *,
    stock: Decimal | str | None,
    especie_content: bool,
    clave: str,
    perceptor_tax_id: str,
) -> None:
    """Reject a stock flag that contradicts the row's in-kind content."""
    if stock is not None and not especie_content:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "emerging_stock_excess_clave without any in-kind percepcion, which design "
            "campo 36 declares only when the especie block has content",
        )
    if stock is None and clave == "A" and especie_content:
        raise RegistryValidationError(
            f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
            "in-kind percepciones but no emerging_stock_excess_clave, which design "
            "campo 36 requires then (clave 0 for the rest of the in-kind retributions)",
        )


def _finalise_190_emerging_stock(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    perceptor_tax_id: str,
    finalised: dict[str, Decimal | str],
) -> None:
    """Validate and serialise the clave-A in-kind stock flag."""
    if "emerging_stock_excess_clave" not in required_fields:
        return
    stock = row.get("emerging_stock_excess_clave")
    especie_content = (
        row["percibido_especie"] != 0 or row["ingreso_a_cuenta"] != 0 or row["ingreso_a_cuenta_repercutido"] != 0
    )
    _validate_190_emerging_stock_clave(
        stock=stock,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    _validate_190_emerging_stock_content(
        stock=stock,
        especie_content=especie_content,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    finalised["emerging_stock_excess_clave"] = str(stock) if stock is not None else " "


def _finalise_190_special_fields(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    subclave: str,
    perceptor_tax_id: str,
    finalised: dict[str, Decimal | str],
) -> None:
    # The design's incapacidad-laboral blocks hold the incap PART of each
    # magnitude, and the base campos explicitly exclude it ("No se incluiran en
    # este campo..."). The observation therefore carries the SPLIT: the base
    # amount facts are the non-incapacidad part (the design field's own
    # meaning), and the incap facts carry the part the design files at 255-321.
    # The totals helpers (percibido_total / retencion_total) add the two parts
    # back together, so the resumen-anual magnitudes stay the row's full total.
    incapacity_fields = (
        (
            "incapacity_cash_perception",
            _numeric_slot(row, "incapacity_cash_perception"),
            _declares_incapacidad_dineraria(clave, subclave),
            "which design campo 32 declares only for claves A and B.01",
        ),
        (
            "incapacity_kind_value",
            row["incapacity_kind_value"],
            clave == "A",
            "which design campo 33 declares only for clave A",
        ),
        (
            "incapacity_kind_ingreso_a_cuenta",
            row["incapacity_kind_ingreso_a_cuenta"],
            clave == "A",
            "which design campo 33 declares only for clave A",
        ),
    )
    for field, value, in_scope, scope_description in incapacity_fields:
        _reject_nonzero_outside_scope(
            field=field,
            value=value,
            required_fields=required_fields,
            in_scope=in_scope,
            perceptor_tax_id=perceptor_tax_id,
            clave=clave,
            scope_description=scope_description,
        )

    _finalise_required_scoped_field(
        finalised,
        field="complemento_infancia_clave",
        value=row.get("complemento_infancia_clave"),
        required_fields=required_fields,
        in_scope=_is_clave_l29(clave, subclave),
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design campo 34 declares only for clave L.29",
        requirement_description="(design campo 34)",
        default=" ",
    )
    _validate_190_foral_fields(
        row,
        required_fields=required_fields,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
    )
    _finalise_190_emerging_stock(
        row,
        required_fields=required_fields,
        clave=clave,
        perceptor_tax_id=perceptor_tax_id,
        finalised=finalised,
    )
    _finalise_optional_scoped_field(
        finalised,
        field="startup_fund_rendimientos_clave",
        value=row.get("startup_fund_rendimientos_clave"),
        required_fields=required_fields,
        in_scope=clave == "A",
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
        scope_description="which design campo 37 declares only for clave A",
        default=" ",
    )


def _finalise_pension_prestacion_fields(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    is_clave_b01: bool,
    perceptor_tax_id: str,
    clave: str,
) -> None:
    """Validate and serialise the Modelo 190 B.01 pension flags."""
    for pension_field in _PENSION_PRESACION_TYPE_FIELDS:
        if pension_field not in required_fields:
            continue
        value = row.get(pension_field)
        if value is not None and not is_clave_b01:
            raise RegistryValidationError(
                f"withholding rows for perceptor {perceptor_tax_id!r} clave {clave} carry "
                f"{pension_field}, which design campo 38 declares only for clave B.01",
            )
        if value is None and is_clave_b01:
            raise RegistryValidationError(
                f"withholding rows for perceptor {perceptor_tax_id!r} clave B.01 require "
                f"{pension_field} (design campo 38): each prestacion type's 0/1 flag is always "
                "recorded, and the 0 for a type not paid is a recorded fact",
            )
        finalised[pension_field] = str(value) if value is not None else " "


def _finalise_190_identity_defaults(
    finalised: dict[str, Decimal | str],
    *,
    birth_year: Decimal | str | None,
    situacion: Decimal | str | None,
    disability: Decimal | str | None,
    contract: Decimal | str | None,
    titular: Decimal | str | None,
    mobility: Decimal | str | None,
    spouse: Decimal | str | None,
    is_clave_a: bool,
    is_clave_l29: bool,
) -> None:
    """Write Modelo 190 identity defaults and clave-scoped one-digit fields."""
    finalised["perceptor_birth_year"] = str(birth_year) if birth_year is not None else "0000"
    finalised["perceptor_situacion_familiar"] = str(situacion) if situacion is not None else "0"
    finalised["disability_clave"] = str(disability) if disability is not None else " "
    finalised["contract_relation_clave"] = str(contract) if is_clave_a else " "
    finalised["unit_convivencia_titular_clave"] = str(titular) if is_clave_l29 else " "
    finalised["geographic_mobility_clave"] = str(mobility) if is_clave_a else " "
    finalised["spouse_or_unit_titular_tax_id"] = spouse if spouse is not None else " " * 9


def _finalise_representative_and_accrual_defaults(
    row: Mapping[str, Decimal | str],
    finalised: dict[str, Decimal | str],
) -> None:
    """Write the representative NIF and accrual-year no-content defaults."""
    representative = row.get("representative_tax_id")
    finalised["representative_tax_id"] = representative if representative is not None else " " * 9
    accrual_year = row.get("accrual_year")
    finalised["accrual_year"] = str(accrual_year) if accrual_year is not None else "0000"


def _finalise_row_defaults(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    clave: str,
    subclave: str,
    perceptor_tax_id: str,
    finalised: dict[str, Decimal | str],
) -> None:
    is_clave_a = clave == "A"
    is_clave_l29 = _is_clave_l29(clave, subclave)
    birth_year = row.get("perceptor_birth_year")
    situacion = row.get("perceptor_situacion_familiar")
    disability = row.get("disability_clave")
    spouse = row.get("spouse_or_unit_titular_tax_id")
    contract = row.get("contract_relation_clave")
    titular = row.get("unit_convivencia_titular_clave")
    mobility = row.get("geographic_mobility_clave")

    is_clave_b01 = clave == "B" and subclave == "01"
    _finalise_pension_prestacion_fields(
        row,
        finalised,
        required_fields=required_fields,
        is_clave_b01=is_clave_b01,
        perceptor_tax_id=perceptor_tax_id,
        clave=clave,
    )
    _finalise_190_identity_defaults(
        finalised,
        birth_year=birth_year,
        situacion=situacion,
        disability=disability,
        contract=contract,
        titular=titular,
        mobility=mobility,
        spouse=spouse,
        is_clave_a=is_clave_a,
        is_clave_l29=is_clave_l29,
    )
    _finalise_representative_and_accrual_defaults(row, finalised)


def _numeric_slot(row: Mapping[str, Decimal | str], field: str) -> Decimal:
    """Return the accumulated amount at ``field``, refusing a non-numeric slot.

    A withholding accumulator holds both monetary totals and the clave/code
    strings that key them, so every arithmetic read has to establish which it
    got. Refusing here keeps that check in the built artefact: an ``assert``
    would vanish under ``python -O`` and let a code string reach a sum.
    """
    value = row[field]
    if not isinstance(value, Decimal):
        raise RegistryValidationError(
            f"withholding accumulator field {field!r} holds a non-numeric value",
        )
    return value


def _finalise_withholding_row(
    row: Mapping[str, Decimal | str],
    *,
    required_fields: frozenset[str],
    row_number: int,
) -> Mapping[str, Decimal | str]:
    """Apply the design's per-clave completion rules to one accumulated row.

    The accumulation pass merges observations and their optional facts; this pass
    turns that into the record content the design defines. Every rule that can
    refuse is gated on ``required_fields`` -- the row fields the RESOLVING
    revision's bindings declare -- because modelo 193 rows share this observation
    class and its store, and a refusal for a field 193 never asks for would be
    cross-modelo noise.

    For each declared field:

    * a fact the design restricts to certain claves REFUSES when it arrives on a
      row outside those claves, and REFUSES again when the design marks it as
      always recorded for the row's clave and no observation carries it -- a
      payer that must have recorded the datum and did not is a filing defect,
      never a silent blank;
    * the spouse/titular NIF is declared only when its triggering fact is present
      (situacion familiar 2, or L.29 with titular clave 2) and refuses then, and
      never equals the perceptor's own NIF;
    * every other row carries the design's own no-content: spaces for the
      NIF/one-digit claves the design does not declare, zeros for the numeric
      fields whose design says "en cualquier otro caso se rellenará a ceros".
    """
    finalised = dict(row)
    clave = str(row["clave"])
    subclave = str(row["subclave"])
    perceptor_tax_id = str(row["perceptor_tax_id"])
    _finalise_190_identity_fields(
        row, required_fields=required_fields, clave=clave, subclave=subclave, perceptor_tax_id=perceptor_tax_id
    )
    _finalise_190_declaration_fields(
        row,
        finalised=finalised,
        required_fields=required_fields,
        clave=clave,
        subclave=subclave,
        perceptor_tax_id=perceptor_tax_id,
    )
    _finalise_190_special_fields(
        row,
        finalised=finalised,
        required_fields=required_fields,
        clave=clave,
        subclave=subclave,
        perceptor_tax_id=perceptor_tax_id,
    )
    _finalise_193_primary_fields(
        row,
        finalised=finalised,
        required_fields=required_fields,
        clave=clave,
        subclave=subclave,
        perceptor_tax_id=perceptor_tax_id,
    )
    _finalise_193_instrument_fields(
        row,
        finalised=finalised,
        required_fields=required_fields,
        clave=clave,
        subclave=subclave,
        perceptor_tax_id=perceptor_tax_id,
        row_number=row_number,
    )
    _finalise_row_defaults(
        row,
        finalised=finalised,
        required_fields=required_fields,
        clave=clave,
        subclave=subclave,
        perceptor_tax_id=perceptor_tax_id,
    )
    return finalised


def build_withholding_rows(
    grouping: WithholdingGrouping,
    observations: tuple[WithholdingObservation, ...],
    *,
    required_fields: frozenset[str] = frozenset(),
) -> tuple[Mapping[str, Decimal | str], ...]:
    """Group withholding observations into rows keyed by perceptor and optionally clave."""
    accum: dict[tuple[str | None, str, str, str], dict[str, Decimal | str]] = {}
    for observation in observations:
        if grouping == "per_perceptor":
            key = (observation.country_code, observation.perceptor_tax_id, "", "")
            row_clave = ""
            row_subclave = ""
        else:
            key = (
                observation.country_code,
                observation.perceptor_tax_id,
                observation.clave,
                observation.subclave,
            )
            row_clave = observation.clave
            row_subclave = observation.subclave
        # An unknown country is an ABSENT KEY rather than a value. The payload
        # carries decimals and strings, and a binding reading a field this row
        # did not produce already refuses with an error naming itself -- so the
        # absence surfaces as that refusal instead of as a silent "ES".
        identity: dict[str, Decimal | str] = {
            "perceptor_tax_id": observation.perceptor_tax_id,
            "perceptor_legal_name": observation.perceptor_legal_name,
            "clave": row_clave,
            "subclave": row_subclave,
            "percibido_dinerario": Decimal("0"),
            "percibido_especie": Decimal("0"),
            "retencion_practicada": Decimal("0"),
            "ingreso_a_cuenta": Decimal("0"),
            "ingreso_a_cuenta_repercutido": Decimal("0"),
            "reducciones_aplicables": Decimal("0"),
            "gastos_deducibles": Decimal("0"),
            "pension_compensatoria": Decimal("0"),
            "anualidades_alimentos": Decimal("0"),
            "incapacity_cash_perception": Decimal("0"),
            "incapacity_cash_withholding": Decimal("0"),
            "incapacity_kind_value": Decimal("0"),
            "incapacity_kind_ingreso_a_cuenta": Decimal("0"),
            "incapacity_kind_repercutido": Decimal("0"),
            "foral_retention_estatal": Decimal("0"),
            "foral_retention_navarra": Decimal("0"),
            "foral_retention_araba": Decimal("0"),
            "foral_retention_gipuzkoa": Decimal("0"),
            "foral_retention_bizkaia": Decimal("0"),
            "reducciones": Decimal("0"),
            "base_retenciones": Decimal("0"),
            "porcentaje_retencion": Decimal("0"),
            "penalizaciones": Decimal("0"),
            "compensaciones": Decimal("0"),
            "garantias": Decimal("0"),
        }
        if observation.country_code is not None:
            identity["country_code"] = observation.country_code
        if observation.province_code is not None:
            identity["province_code"] = observation.province_code
        if observation.territorial_deduction_clave is not None:
            identity["territorial_deduction_clave"] = str(observation.territorial_deduction_clave)
        bucket = accum.setdefault(key, identity)
        _require_consistent_identity_facts(
            bucket,
            observation,
            fields=(
                "province_code",
                "territorial_deduction_clave",
                "perceptor_birth_year",
                "perceptor_situacion_familiar",
                "representative_tax_id",
                "spouse_or_unit_titular_tax_id",
                "disability_clave",
                "contract_relation_clave",
                "unit_convivencia_titular_clave",
                "geographic_mobility_clave",
                "accrual_year",
                "housing_loan_communication_clave",
                "complemento_infancia_clave",
                "emerging_stock_excess_clave",
                "startup_fund_rendimientos_clave",
                "perceptor_mediador_flag",
                "clave_codigo",
                "codigo_emisor",
                "naturaleza",
                "pago",
                "tipo_codigo",
                "codigo_cuenta",
                "pendiente_flag",
                "tipo_percepcion",
                "isin_code",
                "naturaleza_declarante",
                "fecha_inicio_prestamo",
                "fecha_vencimiento_prestamo",
                "nif_pagador_anterior",
                "fecha_devengo",
                "clave_mercado",
                "numero_orden",
                *_PENSION_PRESACION_TYPE_FIELDS,
                *_DATOS_ADICIONALES_COUNT_FIELDS,
            ),
        )
        prev_dinerario = _numeric_slot(bucket, "percibido_dinerario")
        prev_especie = _numeric_slot(bucket, "percibido_especie")
        prev_retencion = _numeric_slot(bucket, "retencion_practicada")
        prev_ingreso = _numeric_slot(bucket, "ingreso_a_cuenta")
        prev_repercutido = _numeric_slot(bucket, "ingreso_a_cuenta_repercutido")
        prev_reducciones = _numeric_slot(bucket, "reducciones_aplicables")
        prev_gastos = _numeric_slot(bucket, "gastos_deducibles")
        prev_pension = _numeric_slot(bucket, "pension_compensatoria")
        prev_anualidades = _numeric_slot(bucket, "anualidades_alimentos")
        bucket["percibido_dinerario"] = prev_dinerario + observation.percibido_dinerario
        bucket["percibido_especie"] = prev_especie + observation.percibido_especie
        bucket["retencion_practicada"] = prev_retencion + observation.retencion_practicada
        bucket["ingreso_a_cuenta"] = prev_ingreso + observation.ingreso_a_cuenta
        bucket["ingreso_a_cuenta_repercutido"] = prev_repercutido + observation.ingreso_a_cuenta_repercutido
        bucket["reducciones_aplicables"] = prev_reducciones + observation.reducciones_aplicables
        bucket["gastos_deducibles"] = prev_gastos + observation.gastos_deducibles
        bucket["pension_compensatoria"] = prev_pension + observation.pension_compensatoria
        bucket["anualidades_alimentos"] = prev_anualidades + observation.anualidades_alimentos
        for amount_field in (
            "incapacity_cash_perception",
            "incapacity_cash_withholding",
            "incapacity_kind_value",
            "incapacity_kind_ingreso_a_cuenta",
            "incapacity_kind_repercutido",
            "foral_retention_estatal",
            "foral_retention_navarra",
            "foral_retention_araba",
            "foral_retention_gipuzkoa",
            "foral_retention_bizkaia",
            "reducciones",
            "base_retenciones",
            "porcentaje_retencion",
            "penalizaciones",
            "compensaciones",
            "garantias",
        ):
            previous = _numeric_slot(bucket, amount_field)
            bucket[amount_field] = previous + getattr(observation, amount_field)
    return tuple(
        _finalise_withholding_row(accum[key], required_fields=required_fields, row_number=index)
        for index, key in enumerate(sorted(accum.keys()), start=1)
    )
