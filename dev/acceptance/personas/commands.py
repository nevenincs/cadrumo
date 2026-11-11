"""The ``aeat`` arguments that perform each persona materialisation step, read off the live command graph.

Every builder renders the facts the in-process materialiser
(``cadrumo.entrypoints.tests.persona_materialisation``) submits as one CLI
command. A fact no command can take is returned as a :class:`MissingRoute`,
never rendered another way: the journey records it as a ``cli_gap``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import cache

from cadrumo.core.capabilities import ServiceCapability
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.tests.persona_materialisation import (
    WithholdingCapture,
    classify_patch,
    household_leaves,
    party_name,
    preceding_quarter,
)
from cadrumo.tests.personas import (
    FieldValue,
    FiledReturns,
    HouseholdMember,
    InventoryBook,
    LedgerRow,
    LocalObservation,
    Persona,
    WithholdingCertificate,
    YearEnvelope,
)
from cadrumo_client.commands.parameters import OptionSpec

PROFILE_EDIT: tuple[str, ...] = ("config", "profile", "edit")
DESCENDANT_ADD: tuple[str, ...] = ("config", "profile", "descendiente", "add")

#: The ``ledger classify`` option each classification patch field is given by.
CLASSIFY_OPTIONS: Mapping[str, str] = {
    "business_classification": "--classification",
    "category_id": "--category-id",
    "irpf_category": "--irpf-category",
    "iva_category": "--iva-category",
    "taxable_base": "--taxable-base",
    "iva_rate": "--iva-rate",
    "iva_amount": "--iva-amount",
    "deduction_fact_kind": "--deduction-kind",
    "counterparty_country": "--counterparty-country",
}

#: The ``--descendiente`` flag key each canonical descendant leaf is given by.
DESCENDANT_FLAG_KEYS: Mapping[str, str] = {
    "birth_date": "NACIMIENTO",
    "relacion": "RELACION",
    "inscripcion_registro_civil": "INSCRIPCION",
    "acogimiento_resolucion": "ACOGIMIENTO",
    "fallecimiento": "FALLECIMIENTO",
    "discapacidad": "DISCAPACIDAD",
    "convivencia": "CONVIVENCIA",
    "dependencia_economica": "DEPENDENCIA",
    "custodia_compartida": "CUSTODIA",
    "rentas_anuales": "RENTAS",
    "declaracion_propia": "DECLARACION_PROPIA",
    "prorrata_minimo": "PRORRATA",
    "meses_madre_trabajo": "MESES_TRABAJO",
    "alta_posterior_nacimiento_mes": "ALTA_POSTERIOR_MES",
    "segundo_ciclo_infantil_inicio_mes": "SEGUNDO_CICLO_INFANTIL_INICIO_MES",
    "gastos_guarderia": "GASTOS_GUARDERIA",
    "gastos_guarderia_mensuales": "GASTOS_GUARDERIA_MENSUAL",
    "nif": "NIF",
}

#: Profile schema paths the profile edit takes as a dedicated on/off option rather than as a wizard answer.
_FIELD_EDIT_FLAGS: Mapping[str, str] = {"withholding.colegio_concertado": "colegio-concertado"}


@dataclass(frozen=True, slots=True)
class MissingRoute:
    """A persona fact no CLI command takes, named for the ``cli_gap`` it becomes."""

    step: str
    missing: str


@cache
def declared_options(path: tuple[str, ...]) -> Mapping[str, OptionSpec]:
    """Every option spelling the command at ``path`` declares in the live command graph; empty when it is absent."""
    options: dict[str, OptionSpec] = {}
    try:
        spec = COMMAND_GRAPH.resolve_path((COMMAND_GRAPH.root().token, *path))
    except LookupError:
        return options
    for parameter in spec.parameters:
        if isinstance(parameter, OptionSpec):
            options.update(dict.fromkeys(parameter.declarations, parameter))
    return options


def command_exists(path: tuple[str, ...]) -> bool:
    """Whether the live command graph holds an executable command at ``path``."""
    try:
        spec = COMMAND_GRAPH.resolve_path((COMMAND_GRAPH.root().token, *path))
    except LookupError:
        return False
    return spec.kind == "leaf"


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _percentage(fraction: Decimal) -> str:
    """A ledger fraction as an invoice rate takes it: a percentage without trailing zeros."""
    return _decimal((fraction * 100).normalize())


# -- profile -----------------------------------------------------------------------------------------------------------


def _answer_options(question_id: str, value: str, declared: Mapping[str, OptionSpec]) -> tuple[str, ...] | None:
    """One wizard answer as profile-edit options: an on/off flag, a repeated list option, or the option and value."""
    option = f"--{question_id}"
    spec = declared.get(option)
    if spec is None:
        return None
    if spec.is_flag:
        return (option,) if value == "true" else (f"--no-{question_id}",)
    if spec.multiple:
        return tuple(item for member in value.split(",") for item in (option, member))
    return option, value


def profile_edit_arguments(
    answers: Sequence[tuple[str, str]], fields: Sequence[FieldValue]
) -> tuple[tuple[str, ...], tuple[MissingRoute, ...]]:
    """The ``config profile edit`` arguments for the wizard answers and the fields it takes, and what it cannot take."""
    declared = declared_options(PROFILE_EDIT)
    arguments: list[str] = [*PROFILE_EDIT, "--quiet"]
    missing: list[MissingRoute] = []
    for question_id, value in answers:
        options = _answer_options(question_id, value, declared)
        if options is None:
            missing.append(MissingRoute(f"profile.{question_id}", f"`config profile edit` declares no --{question_id}"))
        else:
            arguments.extend(options)
    for item in fields:
        flag = _FIELD_EDIT_FLAGS.get(item.path)
        if flag is not None and f"--{flag}" in declared:
            arguments.append(f"--{flag}" if item.value == "true" else f"--no-{flag}")
    return tuple(arguments), tuple(missing)


def _capability(path: str) -> ServiceCapability | None:
    return next((item for item in ServiceCapability if item.schema_path == path), None)


def field_arguments(item: FieldValue) -> tuple[str, ...] | MissingRoute | None:
    """The command that sets one ``[fields]`` path; ``None`` when the profile edit already carries it."""
    if item.path in _FIELD_EDIT_FLAGS:
        return None
    capability = _capability(item.path)
    if capability is not None:
        return ("config", "profile", "capabilities", "set", capability.value, "on" if item.value == "true" else "off")
    return MissingRoute(
        f"fields.{item.path}",
        "no command submits the profile field mutation for an arbitrary schema path; only capabilities and the "
        "censo pull reach it",
    )


def activity_arguments(values: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """One ``activities`` row as ``config profile add-row``."""
    pairs = (item for key, value in values for item in ("--value", f"{key}={value}"))
    return ("config", "profile", "add-row", "activities", *pairs)


def descendant_flag(persona: Persona, member: HouseholdMember, envelope: YearEnvelope) -> str | MissingRoute:
    """One descendant row as the ``--descendiente KEY=VALUE,...`` flag."""
    parts: list[str] = []
    for leaf, value in household_leaves(persona, member, envelope):
        key = DESCENDANT_FLAG_KEYS.get(leaf)
        if key is None:
            return MissingRoute(f"household.descendants.{leaf}", f"the --descendiente flag has no key for {leaf}")
        parts.append(f"{key}={value}")
    return ",".join(parts)


_NO_DESCENDANTS = MissingRoute(
    "household.descendants",
    "`config profile descendiente add` takes at least one row; no command states that the taxpayer has no "
    "descendants, which the descendant replacement records as a member count of zero",
)
_NO_ASCENDANTS = MissingRoute(
    "household.ascendants",
    "no command submits the user-profile.ascendants operation (it is listed among the operations no command submits)",
)


def _descendant_arguments(
    persona: Persona, envelope: YearEnvelope
) -> tuple[tuple[tuple[str, ...], ...], tuple[MissingRoute, ...]]:
    if not persona.descendants:
        return (), (_NO_DESCENDANTS,)
    flags = [descendant_flag(persona, member, envelope) for member in persona.descendants]
    missing = tuple(flag for flag in flags if isinstance(flag, MissingRoute))
    rendered = [item for flag in flags if isinstance(flag, str) for item in ("--descendiente", flag)]
    return ((*DESCENDANT_ADD, *rendered),) if rendered else (), missing


def household_arguments(
    persona: Persona, envelope: YearEnvelope
) -> tuple[tuple[tuple[str, ...], ...], tuple[MissingRoute, ...]]:
    """The household commands for the families the persona states, and the facts no command takes."""
    commands: tuple[tuple[str, ...], ...] = ()
    missing: tuple[MissingRoute, ...] = ()
    if "descendants" in persona.household_families:
        commands, missing = _descendant_arguments(persona, envelope)
    if "ascendants" in persona.household_families:
        missing = (*missing, _NO_ASCENDANTS)
    return commands, missing


# -- ledger ------------------------------------------------------------------------------------------------------------


def classify_arguments(persona: Persona, row: LedgerRow, transaction_id: str, actor: str) -> tuple[str, ...]:
    """The single ``ledger classify`` of one row, from the materialiser's own classification patch."""
    patch, fields = classify_patch(persona, row)
    values = patch.model_dump(mode="json")
    arguments = ["app", "ledger", "classify", transaction_id]
    for name in fields:
        arguments.extend((CLASSIFY_OPTIONS[name], str(values[name])))
    arguments.extend(("--actor", actor))
    return tuple(arguments)


def unmapped_classify_fields(persona: Persona) -> frozenset[str]:
    """Classification patch fields of the persona's rows with no ``ledger classify`` option."""
    return frozenset(
        name for row in persona.ledger for name in classify_patch(persona, row)[1] if name not in CLASSIFY_OPTIONS
    )


def invoice_arguments(persona: Persona, row: LedgerRow, envelope: YearEnvelope) -> tuple[str, ...] | None:
    """The ``ledger invoice add`` of the invoice behind one row; ``None`` for a row no invoice backs."""
    if row.invoice_kind is None or row.invoice_number is None or row.counterparty is None:
        return None
    counterparty = persona.identities.role(row.counterparty)
    arguments = [
        "app",
        "ledger",
        "invoice",
        "add",
        "--kind",
        row.invoice_kind,
        "--counterparty-name",
        party_name(persona, row.counterparty),
        "--counterparty-nif",
        counterparty.value,
        "--country-code",
        counterparty.country or "ES",
        "--invoice-number",
        row.invoice_number,
        "--invoice-date",
        row.operation_date(envelope).isoformat(),
        "--currency",
        row.currency,
    ]
    arguments.extend(_invoice_amounts(row))
    return tuple(arguments)


def _invoice_amounts(row: LedgerRow) -> tuple[str, ...]:
    """The invoice's stated amounts as options: its IVA rate as a percentage, the rest as the row states them."""
    rate = None if row.iva_rate is None else _percentage(row.iva_rate)
    optional: tuple[tuple[str, Decimal | str | None], ...] = (
        ("--taxable-base", row.taxable_base),
        ("--iva-rate", rate),
        ("--iva-category", row.iva_category),
        ("--retention-rate", row.retencion_rate),
        ("--retention-amount", row.retencion_amount),
        ("--recargo", row.recargo_amount),
    )
    return tuple(
        item
        for option, value in optional
        if value is not None
        for item in (option, _decimal(value) if isinstance(value, Decimal) else value)
    )


def statement_key(row: LedgerRow, envelope: YearEnvelope) -> tuple[str, Decimal, str, str]:
    """How a statement row is found again in ``ledger list``: its date, magnitude, direction and concept."""
    direction = "INCOMING" if row.amount > 0 else "OUTGOING"
    return row.operation_date(envelope).isoformat(), abs(row.amount), direction, row.description


def listed_key(listed: Mapping[str, object]) -> tuple[str, Decimal, str, str] | None:
    """The same key read from one ``ledger list`` row; ``None`` when the row does not carry it."""
    try:
        amount = abs(Decimal(str(listed.get("amount"))))
    except ArithmeticError:
        return None
    day = str(listed.get("date") or "")[:10]
    return day, amount, str(listed.get("direction", "")).upper(), str(listed.get("description", ""))


def correlate_rows(
    rows: Sequence[LedgerRow], listed: Sequence[Mapping[str, object]], envelope: YearEnvelope
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Map each row's ``ref`` to the listed transaction it became; refs found ambiguous or absent come back apart."""
    by_key: dict[tuple[str, Decimal, str, str], list[str]] = {}
    for item in listed:
        key = listed_key(item)
        if key is not None:
            by_key.setdefault(key, []).append(str(item.get("transaction_id")))
    mapped: dict[str, str] = {}
    unmatched: list[str] = []
    for row in rows:
        found = by_key.get(statement_key(row, envelope), [])
        if len(found) == 1:
            mapped[row.ref] = found[0]
        else:
            unmatched.append(row.ref)
    return mapped, tuple(unmatched)


def withholding_arguments(
    persona: Persona, certificate: WithholdingCertificate, envelope: YearEnvelope
) -> tuple[str, ...]:
    """One certificate the taxpayer declares as ``ledger retencion-soportada record``; nothing in kind is stated."""
    zero = "0.00"
    return (
        "app",
        "ledger",
        "retencion-soportada",
        "record",
        persona.identities.role(certificate.payer).value,
        "--ejercicio",
        str(certificate.ejercicio.resolve(envelope)),
        "--income-class",
        certificate.income_class,
        "--origin",
        "operator_declaration",
        "--importe-integro",
        _decimal(certificate.importe_integro),
        "--valoracion-especie",
        zero,
        "--retencion",
        _decimal(certificate.retencion),
        "--ingreso-a-cuenta",
        zero,
        "--ingreso-a-cuenta-repercutido",
        zero,
        "--payer-name",
        party_name(persona, certificate.payer),
    )


def inventory_create_arguments(book: InventoryBook, year: int) -> tuple[str, ...]:
    """The ``ledger inventory create`` that opens one existencias book."""
    return (
        "app",
        "ledger",
        "inventory",
        "create",
        book.activity,
        "--year",
        str(year),
        "--valuation-method",
        book.valuation_method,
        "--opening-stock",
        _decimal(book.opening_stock),
    )


def inventory_closing_facts(
    book: InventoryBook, year: int, *, reference: str, content_digest: str
) -> dict[str, object]:
    """The closing decision ``ledger inventory closing-value-record --file`` reads: derived from the book's movements.

    The statement evidences both the closing and the prior year's closing the
    opening continues from, as in the in-process replay.
    """
    return {
        "decision_id": f"persona-{book.activity}-{year}",
        "authority": "movement_derived",
        "reason": book.statement,
        "decision_evidence": [
            {
                "reference": {"reference": reference},
                "role": "authority_reconciliation",
                "content_digest": content_digest,
            }
        ],
        "prior_evidence": [{"reference": {"reference": reference}, "content_digest": content_digest}],
    }


def local_observation_arguments(observation: LocalObservation, envelope: YearEnvelope, actor: str) -> tuple[str, ...]:
    """One return the taxpayer knows from his own copy as ``modelo filing-record observe-local``."""
    values = (item for casilla, value in observation.casillas for item in ("--set", f"{casilla}={value}"))
    return (
        "app",
        "modelo",
        "filing-record",
        "observe-local",
        "--modelo",
        observation.modelo,
        "--year",
        str(observation.year.resolve(envelope)),
        "--period",
        observation.period,
        "--reason",
        observation.reason,
        "--by",
        actor,
        *values,
    )


def wallet_seed_arguments(filed: FiledReturns, envelope: YearEnvelope) -> tuple[str, ...] | None:
    """The compensation balance a filed Modelo 303 block starts from, as ``iva-wallet seed``; ``None`` if unstated."""
    if filed.iva_compensation_carried_in is None:
        return None
    period = preceding_quarter(filed.year.resolve(envelope), filed.periods[0])
    return (
        "app",
        "modelo",
        "iva-wallet",
        "seed",
        "--filing-year",
        str(period.filing_year),
        "--period",
        str(period.code),
        "--amount",
        _decimal(filed.iva_compensation_carried_in.normalize()),
        "--confirm",
    )


def withholding_capture_arguments(capture: WithholdingCapture) -> tuple[str, ...]:
    """One withheld payment as ``modelo aggregate --received-invoice-retencion``, for the quarter it was paid in."""
    return (
        "app",
        "modelo",
        "aggregate",
        "--modelo",
        capture.modelo,
        "--year",
        str(capture.period.filing_year),
        "--period",
        str(capture.period.code),
        "--received-invoice-retencion",
        capture.evidence.model_dump_json(),
    )


def work_create_arguments(modelo: str, year: int, period: str, actor: str) -> tuple[str, ...]:
    """The ``modelo work create`` of one return."""
    return (
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        modelo,
        "--year",
        str(year),
        "--period",
        period,
        "--by",
        actor,
    )


def attestation_arguments(year: int, period: str, actor: str) -> tuple[str, ...]:
    """The Modelo 390 exoneration attestation the last Modelo 303 period calculates with, observed at year end."""
    return (
        "app",
        "modelo",
        "work",
        "attest-m303-exonerado-390",
        "--year",
        str(year),
        "--period",
        period,
        "--observed-at",
        f"{year}-12-31T12:00:00+00:00",
        "--by",
        actor,
    )


def calculate_arguments(
    work_unit_id: str, *, modelo: str, attestation: tuple[str, str] | None, actor: str
) -> tuple[str, ...]:
    """The ``modelo work calculate`` of one unit: a Modelo 303 states no joint return and any attestation it holds."""
    evidence: list[str] = []
    if modelo == "303":
        evidence.append("--no-joint-return-elected")
    if attestation is not None:
        attachment_id, sha256 = attestation
        evidence.extend(("--m303-exonerado-390-attachment-id", attachment_id, "--m303-exonerado-390-sha256", sha256))
    return ("app", "modelo", "work", "calculate", work_unit_id, *evidence, "--by", actor)
