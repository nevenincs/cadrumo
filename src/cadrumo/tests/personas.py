"""Read the canonical persona catalogue under ``dev/fixtures/personas`` into typed, frozen values.

The catalogue is data only; its contract is the catalogue's own README. This
reader parses and validates it and nothing more: it resolves identity roles,
refuses an unknown format, field, role or year, and checks each ledger row's
amount against its invoice figures. Year tokens stay tokens. The supported
filing-year envelope is declared by the registry, which this core-only package
cannot read, so the caller hands it in as a :class:`YearEnvelope` and every
token is checked against it here; a materialiser that reaches the registry
builds the envelope from it and resolves the tokens it submits.
"""

from __future__ import annotations

import calendar
import dataclasses
from collections.abc import Callable
from datetime import date
from typing import Final, cast

from ..core.period import StandardPeriodCode
from .inventory import REPO_ROOT
from .persona_expectations import _expectations
from .persona_identities import _Roles, identity_catalogue
from .persona_ledger import _documents, _parse_ledger
from .persona_sections import (
    _aeat_filing,
    _attested_prior_value,
    _calculated_returns,
    _check_designations,
    _filed_returns,
    _household,
    _inventory_book,
    _leased_premises,
    _local_observation,
    _officer,
    _own_account,
    _prior_carries,
    _profile_row,
    _profile_value,
    _rental,
    _withholding,
    _work_income_none,
    _work_input,
    filed_period_order,
)
from .persona_toml import _date, _keys, _optional_string, _read_toml, _string, _strings, _Table, _table, _tables
from .persona_types import (
    CATALOGUE_FORMAT,
    PERSONAS_ROOT,
    ActivityRow,
    AeatFiling,
    AttestedPriorValue,
    BelowFloorBlock,
    BelowFloorRecord,
    CalculatedReturns,
    Election,
    Expectations,
    ExpectedDeadline,
    ExpectedObligation,
    ExpectedValue,
    FieldValue,
    FiledReturns,
    IdentityCatalogue,
    LocalObservation,
    Persona,
    PersonaCatalogueError,
    PersonaDate,
    PriorCarries,
    ProfileAnswer,
    WithholdingCertificate,
    WorkIncomeNoneStatement,
    WorkInput,
    YearEnvelope,
    YearToken,
    _fail,
)
from .run_artifact import file_inputs_digest

_PERSONA_TABLES = frozenset(
    {
        "format",
        "persona",
        "clock",
        "profile",
        "fields",
        "activities",
        "profile_rows",
        "elections",
        "household",
        "own_accounts",
        "prior_carries",
        "withholding_certificates",
        "work_income_none_statements",
        "rental_properties",
        "officers",
        "filed_returns",
        "calculated_returns",
        "local_observations",
        "aeat_filings",
        "attested_prior_values",
        "work_inputs",
        "leased_premises",
        "inventory",
    }
)


_DESCENDANT_LEAVES = frozenset(
    {
        "birth_date",
        "relacion",
        "inscripcion_registro_civil",
        "acogimiento_resolucion",
        "fallecimiento",
        "discapacidad",
        "convivencia",
        "dependencia_economica",
        "custodia_compartida",
        "rentas_anuales",
        "declaracion_propia",
        "prorrata_minimo",
        "meses_madre_trabajo",
        "alta_posterior_nacimiento_mes",
        "segundo_ciclo_infantil_inicio_mes",
        "gastos_guarderia",
        "gastos_guarderia_mensuales",
        "cotizaciones_ss_madre",
    }
)


_ASCENDANT_LEAVES = frozenset(
    {
        "birth_date",
        "fallecimiento",
        "convivientes",
        "convivencia_mitad_periodo",
        "rentas_anuales",
        "declaracion_propia",
        "discapacidad",
        "discapacidad_asistencia",
        "incapacidad_judicial",
    }
)


def governed_provisions() -> frozenset[str]:
    """Every provision a stated value of the catalogue is limited to, read before any persona is validated.

    The caller reads these provisions' governed periods from the registry into the
    :class:`YearEnvelope` that validation and :func:`values_in_force` take.
    """
    provisions: set[str] = set()
    for persona_id in persona_ids():
        path = PERSONAS_ROOT / persona_id / "expectations.toml"
        if not path.is_file():
            continue
        for index, table in enumerate(_tables(_read_toml(path).get("values"), str(path))):
            governed_by = _optional_string(table, "governed_by", f"{path} values[{index}]")
            if governed_by is not None:
                provisions.add(governed_by)
    return frozenset(provisions)


def persona_ids() -> tuple[str, ...]:
    """Return every persona of the catalogue, sorted."""
    return tuple(sorted(entry.name for entry in PERSONAS_ROOT.iterdir() if (entry / "persona.toml").is_file()))


type _Header = tuple[_Table, _Table, _Table, _Table, _Table]


def _header(persona_document: _Table, persona_id: str, where: str) -> _Header:
    """Check the persona file's own shape and return its head, clock, profile, fields and household tables."""
    if persona_document.get("format") != CATALOGUE_FORMAT:
        raise _fail(where, f"format must be {CATALOGUE_FORMAT}, found {persona_document.get('format')!r}")
    _keys(
        persona_document, where, required=frozenset({"format", "persona", "clock", "profile"}), optional=_PERSONA_TABLES
    )
    head = _table(persona_document["persona"], f"{where} [persona]")
    _keys(
        head, f"{where} [persona]", required=frozenset({"id", "title", "summary", "taxpayer", "fiscal_year", "modelos"})
    )
    if head["id"] != persona_id:
        raise _fail(where, "persona id differs from its directory")
    clock = _table(persona_document["clock"], f"{where} [clock]")
    _keys(clock, f"{where} [clock]", required=frozenset({"as_of"}))
    profile = _table(persona_document["profile"], f"{where} [profile]")
    fields = _table(persona_document.get("fields", {}), f"{where} [fields]")
    if not all(isinstance(value, str) for value in fields.values()):
        raise _fail(where, "[fields] values must be strings")
    household = _table(persona_document.get("household", {}), f"{where} [household]")
    _keys(household, f"{where} [household]", required=frozenset(), optional=frozenset({"descendants", "ascendants"}))
    return head, clock, profile, fields, household


def _activities(persona_document: _Table, where: str) -> tuple[ActivityRow, ...]:
    activities: list[ActivityRow] = []
    for index, table in enumerate(_tables(persona_document.get("activities"), f"{where} activities")):
        if not all(isinstance(value, str) for value in table.values()):
            raise _fail(f"{where} activities[{index}]", "activity values must be strings")
        activities.append(ActivityRow(values=tuple((key, cast(str, value)) for key, value in table.items())))
    return tuple(activities)


def _elections(persona_document: _Table, where: str) -> tuple[Election, ...]:
    elections: list[Election] = []
    for index, table in enumerate(_tables(persona_document.get("elections"), f"{where} elections")):
        here = f"{where} elections[{index}]"
        _keys(table, here, required=frozenset({"question", "value", "year"}))
        elections.append(
            Election(
                question=_string(table, "question", here),
                value=_string(table, "value", here),
                year=YearToken.parse(table["year"], where=f"{here}.year"),
            )
        )
    return tuple(elections)


def _records[Record](
    persona_document: _Table,
    key: str,
    where: str,
    parse: Callable[..., Record],
    *context: object,
) -> tuple[Record, ...]:
    """Parse every table of the repeatable block ``key``, each with its indexed location and ``context``."""
    return tuple(
        parse(table, f"{where} {key}[{index}]", *context)
        for index, table in enumerate(_tables(persona_document.get(key), where))
    )


def _check_documents(persona: Persona, persona_id: str) -> None:
    """Refuse a ledger row and a document that disagree on which document the row carries."""
    known_documents = {document.id for document in persona.documents}
    if any(row.document is not None and row.document not in known_documents for row in persona.ledger):
        raise _fail(f"{persona_id}/ledger.csv", "a row names a document documents.toml does not hold")
    named = {row.ref: row.document for row in persona.ledger}
    for document in persona.documents:
        if document.generator is not None and any(named[ref] != document.id for ref in document.attach_to):
            raise _fail(f"{persona_id}/documents.toml", f"{document.id}: its row does not name it in ledger.csv")


def parse_persona(
    persona_id: str,
    *,
    persona_document: _Table,
    ledger_text: str,
    documents_document: _Table,
    expectations_document: _Table,
    catalogue: IdentityCatalogue,
    envelope: YearEnvelope,
    omit_below_floor: bool = False,
) -> Persona:
    """Validate one persona's parsed files against the catalogue contract and the year envelope.

    A year outside the envelope is refused. With ``omit_below_floor``, for a
    read under a horizon lowered below the registry's own, a return-history
    record or an expectation whose year falls below the floor is left out and
    listed in :attr:`Persona.below_floor` instead; every other token stays
    refused there.
    """
    where = f"{persona_id}/persona.toml"
    head, clock, profile, fields, household = _header(persona_document, persona_id, where)
    roles = _Roles(catalogue, persona_id)
    activities = _activities(persona_document, where)
    elections = _elections(persona_document, where)
    modelos = _strings(head, "modelos", where)
    own_accounts = _records(persona_document, "own_accounts", where, _own_account, modelos)
    _check_designations(own_accounts, f"{where} own_accounts")
    ledger = _parse_ledger(ledger_text, where=f"{persona_id}/ledger.csv", roles=roles)
    persona = Persona(
        id=persona_id,
        title=_string(head, "title", where),
        summary=_string(head, "summary", where),
        taxpayer=roles(head["taxpayer"], where),
        fiscal_year=YearToken.parse(head["fiscal_year"], where=f"{where}.fiscal_year"),
        modelos=modelos,
        as_of=_date(clock["as_of"], f"{where} [clock].as_of", biographical=False),
        profile=tuple(
            ProfileAnswer(question_id=key, value=_profile_value(key, value, f"{where} [profile].{key}", roles))
            for key, value in profile.items()
        ),
        fields=tuple(FieldValue(path=key, value=cast(str, value)) for key, value in fields.items()),
        activities=activities,
        profile_rows=_records(persona_document, "profile_rows", where, _profile_row, roles),
        elections=elections,
        descendants=_household(household.get("descendants"), f"{where} descendants", _DESCENDANT_LEAVES, roles),
        ascendants=_household(household.get("ascendants"), f"{where} ascendants", _ASCENDANT_LEAVES, roles),
        household_families=tuple(family for family in ("descendants", "ascendants") if family in household),
        own_accounts=own_accounts,
        prior_carries=_records(persona_document, "prior_carries", where, _prior_carries, modelos),
        withholding_certificates=_records(persona_document, "withholding_certificates", where, _withholding, roles),
        work_income_none_statements=_records(persona_document, "work_income_none_statements", where, _work_income_none),
        rental_properties=_records(persona_document, "rental_properties", where, _rental, roles),
        officers=_records(persona_document, "officers", where, _officer, roles),
        filed_returns=_records(persona_document, "filed_returns", where, _filed_returns),
        calculated_returns=_records(persona_document, "calculated_returns", where, _calculated_returns),
        local_observations=_records(persona_document, "local_observations", where, _local_observation),
        aeat_filings=_records(persona_document, "aeat_filings", where, _aeat_filing),
        attested_prior_values=_records(persona_document, "attested_prior_values", where, _attested_prior_value),
        work_inputs=_records(persona_document, "work_inputs", where, _work_input),
        leased_premises=_records(persona_document, "leased_premises", where, _leased_premises, roles),
        inventory=_records(persona_document, "inventory", where, _inventory_book),
        ledger=ledger,
        documents=_documents(
            documents_document, f"{persona_id}/documents.toml", persona_id, frozenset(row.ref for row in ledger)
        ),
        expectations=_expectations(expectations_document, f"{persona_id}/expectations.toml", persona_id, roles),
        identities=catalogue,
    )
    _check_documents(persona, persona_id)
    _check_returns(persona)
    _check_inventory(persona)
    _check_work_income_none_statements(persona)
    if omit_below_floor:
        persona = _without_records_below_floor(persona, envelope)
    _check_years(persona, envelope)
    _check_aeat_filings(persona, envelope)
    _check_attested_prior_values(persona, envelope)
    _check_work_inputs(persona, envelope)
    _check_prior_carries(persona, envelope)
    return persona


type _DatedRecord = (
    FiledReturns
    | CalculatedReturns
    | LocalObservation
    | AeatFiling
    | AttestedPriorValue
    | WorkInput
    | ExpectedObligation
    | ExpectedDeadline
    | ExpectedValue
)


def _record_periods(record: _DatedRecord) -> tuple[str, ...]:
    if isinstance(record, FiledReturns | CalculatedReturns | ExpectedObligation):
        return record.periods
    return (record.period,)


_WORK_INCOME_CLASS: Final = "trabajo"
"""The suffered-withholding class whose certificate carries work income."""


_CERTIFICATE_RETURN_MODELO: Final = "100"
"""The return a suffered-withholding certificate feeds, named when the certificate is left out."""


_CERTIFICATE_RETURN_PERIOD: Final = "0A"


def _without_records_below_floor(persona: Persona, envelope: YearEnvelope) -> Persona:
    """``persona`` without its dated records, statements, certificates and expectations below the floor, listed."""
    dropped: list[BelowFloorRecord] = []

    def kept[Record: _DatedRecord](block: BelowFloorBlock, records: tuple[Record, ...]) -> tuple[Record, ...]:
        inside: list[Record] = []
        for record in records:
            if record.year.precedes_floor(envelope):
                dropped.append(
                    BelowFloorRecord(
                        block=block, modelo=record.modelo, year=record.year, periods=_record_periods(record)
                    )
                )
            else:
                inside.append(record)
        return tuple(inside)

    carries: list[PriorCarries] = []
    for statement in persona.prior_carries:
        if statement.year.precedes_floor(envelope):
            dropped.append(BelowFloorRecord(block="prior_carries", modelo="100", year=statement.year, periods=("0A",)))
        else:
            carries.append(statement)
    expectations = persona.expectations
    certificates: list[WithholdingCertificate] = []
    for certificate in persona.withholding_certificates:
        if certificate.ejercicio.precedes_floor(envelope):
            dropped.append(
                BelowFloorRecord(
                    block="withholding_certificates",
                    modelo=_CERTIFICATE_RETURN_MODELO,
                    year=certificate.ejercicio,
                    periods=(_CERTIFICATE_RETURN_PERIOD,),
                )
            )
        else:
            certificates.append(certificate)
    statements: list[WorkIncomeNoneStatement] = []
    for statement in persona.work_income_none_statements:
        if statement.ejercicio.precedes_floor(envelope):
            dropped.append(
                BelowFloorRecord(
                    block="work_income_none_statements",
                    modelo=_CERTIFICATE_RETURN_MODELO,
                    year=statement.ejercicio,
                    periods=(_CERTIFICATE_RETURN_PERIOD,),
                )
            )
        else:
            statements.append(statement)
    return dataclasses.replace(
        persona,
        prior_carries=tuple(carries),
        withholding_certificates=tuple(certificates),
        work_income_none_statements=tuple(statements),
        filed_returns=kept("filed_returns", persona.filed_returns),
        calculated_returns=kept("calculated_returns", persona.calculated_returns),
        local_observations=kept("local_observations", persona.local_observations),
        aeat_filings=kept("aeat_filings", persona.aeat_filings),
        attested_prior_values=kept("attested_prior_values", persona.attested_prior_values),
        work_inputs=kept("work_inputs", persona.work_inputs),
        expectations=Expectations(
            obligations=kept("expectations.obligations", expectations.obligations),
            deadlines=kept("expectations.deadlines", expectations.deadlines),
            values=kept("expectations.values", expectations.values),
        ),
        below_floor=tuple(dropped),
    )


def _check_work_income_none_statements(persona: Persona) -> None:
    """Refuse a statement of no other work income for an ejercicio with no work-income certificate.

    The statement answers the boxes a work-income return leaves to the filer; for an
    ejercicio whose return rests on no work-income record the form never offers it, so
    stating it there is a mistake the replay would otherwise pass over in silence.
    """
    certified = {
        str(certificate.ejercicio)
        for certificate in persona.withholding_certificates
        if certificate.income_class == _WORK_INCOME_CLASS
    }
    for statement in persona.work_income_none_statements:
        if str(statement.ejercicio) not in certified:
            raise _fail(
                persona.id,
                f"work_income_none_statements {statement.ejercicio}: no work-income certificate for that ejercicio",
            )


def _check_returns(persona: Persona) -> None:
    """Refuse a modelo period listed twice across the filed, calculated, observed and AEAT-filed blocks."""
    seen: set[tuple[str, str, str]] = set()
    keys = [
        *((block.modelo, str(block.year), period) for block in persona.filed_returns for period in block.periods),
        *((block.modelo, str(block.year), period) for block in persona.calculated_returns for period in block.periods),
        *((item.modelo, str(item.year), item.period) for item in persona.local_observations),
        *((item.modelo, str(item.year), item.period) for item in persona.aeat_filings),
    ]
    for key in keys:
        if key in seen:
            modelo, year, period = key
            raise _fail(persona.id, f"Modelo {modelo} {year} {period} is listed twice")
        seen.add(key)


def _period_closes(year: int, period: str) -> date:
    """The last day of a filed period of ``year``."""
    if period == "0A":
        return date(year, 12, 31)
    month = 3 * filed_period_order(period) + 3
    return date(year, month, calendar.monthrange(year, month)[1])


def _check_aeat_filings(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse a return presented before its period closed."""
    for filing in persona.aeat_filings:
        closes = _period_closes(filing.year.resolve(envelope), filing.period)
        if filing.presented.resolve(envelope) <= closes:
            raise _fail(
                persona.id,
                f"Modelo {filing.modelo} {filing.year} {filing.period} is presented before its period closes",
            )


def _check_attested_prior_values(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse an attested figure listed twice, or with a source that does not precede the return it feeds.

    A source of an earlier year precedes. A source of the same year precedes only an
    annual return of another modelo, as an instalment or periodic return of the year
    feeds its annual return.
    """
    seen: set[tuple[str, str, str, str]] = set()
    for item in persona.attested_prior_values:
        key = (item.modelo, str(item.year), item.period, item.binding)
        if key in seen:
            raise _fail(persona.id, f"Modelo {item.modelo} {item.year} {item.period} attests {item.binding} twice")
        seen.add(key)
        try:
            year = item.year.resolve(envelope)
            source_years = [source.year.resolve(envelope, biographical=True) for source in item.sources]
        except ValueError as error:
            raise _fail(persona.id, str(error)) from None
        if not all(
            source_year < year
            or (source_year == year and item.period == StandardPeriodCode.ANNUAL and source.modelo != item.modelo)
            for source, source_year in zip(item.sources, source_years, strict=True)
        ):
            raise _fail(
                persona.id,
                f"Modelo {item.modelo} {item.year} {item.period} attests a source that does not precede it",
            )


def _check_work_inputs(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse two blocks for one return, and a given role an expectation of that return asserts back by name.

    A role an expectation names under ``roles`` is checked here; whether a given
    role and an expected casilla id are the same casilla resolves only through
    the registry, so the materialiser checks that against the return's edition.
    """
    seen: set[tuple[str, int, str]] = set()
    for item in persona.work_inputs:
        year = item.year.resolve(envelope)
        key = (item.modelo, year, item.period)
        if key in seen:
            raise _fail(persona.id, f"Modelo {item.modelo} {item.year} {item.period} has two work_inputs blocks")
        seen.add(key)
        given = {role for role, _ in item.roles}
        for value in persona.expectations.values:
            if (value.modelo, value.year.resolve(envelope), value.period) != key:
                continue
            asserted = given & {role for role, _ in value.roles}
            if asserted:
                raise _fail(
                    persona.id,
                    f"Modelo {item.modelo} {item.year} {item.period} gives {sorted(asserted)} as a work input "
                    "and asserts it back as an expected value",
                )


def _check_prior_carries(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse two statements of one carry family for one Modelo 100 year."""
    keys = [(statement.year.resolve(envelope), statement.family) for statement in persona.prior_carries]
    if len(set(keys)) != len(keys):
        raise _fail(persona.id, "the pending carries of one family and Modelo 100 year are stated twice")


def _check_inventory(persona: Persona) -> None:
    """Refuse two books for one activity and year."""
    books = [(book.activity, str(book.year)) for book in persona.inventory]
    if len(set(books)) != len(books):
        raise _fail(persona.id, "an inventory activity and year is listed twice")


def _dates(persona: Persona) -> list[PersonaDate]:
    found = [persona.as_of]
    found.extend(answer.value for answer in persona.profile if isinstance(answer.value, PersonaDate))
    for member in (*persona.descendants, *persona.ascendants):
        found.extend(value for _key, value in member.leaves if isinstance(value, PersonaDate))
    for row in persona.profile_rows:
        found.extend(value for _key, value in row.values if isinstance(value, PersonaDate))
    found.extend(rental.contract_start for rental in persona.rental_properties)
    found.extend(rental.fecha_adquisicion for rental in persona.rental_properties)
    found.extend(rental.arrendado_desde for rental in persona.rental_properties if rental.arrendado_desde is not None)
    found.extend(identity.birth_date for identity in persona.identities.identities if identity.birth_date is not None)
    found.extend(filing.presented for filing in persona.aeat_filings)
    found.extend(deadline.statutory_end for deadline in persona.expectations.deadlines)
    return found


def _check_years(persona: Persona, envelope: YearEnvelope) -> None:
    """Refuse every year that resolves outside the envelope; a biographical date may precede the floor."""
    tokens = [
        persona.fiscal_year,
        *(election.year for election in persona.elections),
        *(certificate.ejercicio for certificate in persona.withholding_certificates),
        *(statement.ejercicio for statement in persona.work_income_none_statements),
        *(statement.year for statement in persona.prior_carries),
        *(filed.year for filed in persona.filed_returns),
        *(calculated.year for calculated in persona.calculated_returns),
        *(observation.year for observation in persona.local_observations),
        *(filing.year for filing in persona.aeat_filings),
        *(item.year for item in persona.attested_prior_values),
        *(item.year for item in persona.work_inputs),
        *(book.year for book in persona.inventory),
        *(row.year for row in persona.ledger),
        *(item.year for item in persona.expectations.obligations),
        *(item.year for item in persona.expectations.deadlines),
        *(item.year for item in persona.expectations.values),
        *(value.year for rental in persona.rental_properties for value in rental.valores_catastrales),
    ]
    try:
        for token in tokens:
            token.resolve(envelope)
        for persona_date in _dates(persona):
            persona_date.resolve(envelope)
        for row in persona.ledger:
            row.operation_date(envelope)
    except ValueError as error:
        raise _fail(persona.id, str(error)) from None


def read_persona(persona_id: str, *, envelope: YearEnvelope, omit_below_floor: bool = False) -> Persona:
    """Read and validate one persona of the catalogue under the registry's year ``envelope``.

    ``omit_below_floor`` is as :func:`parse_persona` takes it.
    """
    directory = PERSONAS_ROOT / persona_id
    if not (directory / "persona.toml").is_file():
        raise PersonaCatalogueError(f"unknown persona {persona_id!r}")
    return parse_persona(
        persona_id,
        persona_document=_read_toml(directory / "persona.toml"),
        ledger_text=(directory / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_read_toml(directory / "documents.toml"),
        expectations_document=_read_toml(directory / "expectations.toml"),
        catalogue=identity_catalogue(),
        envelope=envelope,
        omit_below_floor=omit_below_floor,
    )


def persona_inputs_digest(persona: Persona) -> str:
    """Digest every file a persona's values come from: its directory, the identity catalogue and its documents."""
    paths = {path for path in (PERSONAS_ROOT / persona.id).rglob("*") if path.is_file()}
    paths.add(PERSONAS_ROOT / "identities.toml")
    paths.update(document.path for document in persona.documents if document.path is not None)
    return file_inputs_digest("persona-inputs", REPO_ROOT, sorted(paths))


__all__ = [
    "governed_provisions",
    "parse_persona",
    "persona_ids",
    "persona_inputs_digest",
    "read_persona",
]
