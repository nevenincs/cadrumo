"""Generate the persona-derived frames of the seed recipes, and check them for drift.

A seed recipe (``docs/_sequences/seeds/<name>.seq``) opens with directive lines
that declare where its frames come from, then holds a generated region and any
frames the recipe authors itself::

    :persona: autonomo-alta-reciente
    :profile: activity-start-date
    :ledger: all
    @step State when the activity started.
    :generated: begin
    @setup aeat config profile edit docs-sequence-sandbox --quiet --activity-start-date 2026-01-01
    ...the persona's ledger, invoice and evidence frames...
    :generated: end

``:persona:`` names the catalogue persona and ``:profile:`` the wizard questions
the recipe states: the persona supplies every value, the recipe only chooses
which answers its page needs. The optional directives add frames the persona's
own files state:

- ``:ledger: all`` records every row of the persona's ledger with its tax
  fields, then the invoice behind each invoiced row (linked to the row), then
  each document (attached to its rows), as the persona materialiser replays
  them. A specimen document must live in the docs fixtures tree the sandbox
  copies; a document the persona generates from its row (a Facturae invoice)
  is written to ``fixtures/personas/<persona>/`` and checked for drift like
  the frames.
- ``:carry: <modelo>`` records, before any filing, the Modelo 303 compensation
  balance the persona's first period of its fiscal year starts from: the
  casilla 110 (cuotas pendientes de compensación de periodos anteriores) of
  that period's expectation, zero when the expectation states none.
- ``:file: <modelo> ...`` opens, calculates, verifies and records as filed every
  period of each modelo the persona's expectations make applicable in its
  fiscal year. Captures name the work unit and calculation revision of each
  period (``m303_1t_work_unit_id``, ``m303_1t_calculation_revision_id``).

An optional ``:identities:`` line lists the catalogue identity roles the
authored frames name; the check refuses a recipe whose text no longer states a
listed identity's value and name as the catalogue does. Every generated frame
is an ordinary executed frame, so its output is golden-gated like any other.

The directive lines are blanked by the recipe loader before the frame grammar
runs, so a recipe without them is still an ordinary recipe.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from cadrumo.tests.persona_invoices import GeneratedDocument, generated_documents
from cadrumo.tests.personas import LedgerRow, Persona, YearEnvelope
from dev.paths import REPO_ROOT, UTF_8

from .persona_profile import SANDBOX_PERSONA_ID, pinned_persona, profile_option_arguments
from .sandbox import SANDBOX_PROFILE_LABEL, default_fixtures_root
from .seeds import SEED_SUFFIX, default_seeds_root

__all__ = [
    "SeedHeader",
    "check_seeds",
    "parse_seed_header",
    "render_seed",
    "render_statement_fixture",
    "write_seeds",
]

_DIRECTIVE: Final = re.compile(
    r"^:(?P<name>persona|profile|identities|ledger|carry|file|generated):[ \t]*(?P<value>.*?)[ \t]*$"
)
_BEGIN: Final = "begin"
_END: Final = "end"
_LEDGER_ALL: Final = "all"
_M303: Final = "303"
#: The Modelo 303 casilla holding the compensation balance pending from earlier periods.
_M303_PENDING_FROM_EARLIER: Final = "110"
#: Quarter codes and the month each one closes in.
_QUARTER_END_MONTH: Final = {"1T": 3, "2T": 6, "3T": 9, "4T": 12}
_QUARTER_END_DAY: Final = {3: 31, 6: 30, 9: 30, 12: 31}
#: The docs fixtures subdirectory holding the documents personas generate from their rows.
_GENERATED_DOCUMENTS: Final = "personas"


@dataclass(frozen=True, slots=True)
class SeedHeader:
    """The declared persona inputs of one seed recipe and where its generated region sits."""

    persona: str
    questions: tuple[str, ...]
    identities: tuple[str, ...]
    """Identity roles the recipe's authored frames name; their catalogue values must appear in the text."""
    ledger: bool
    """Whether the region records the persona's ledger, invoices and documents."""
    carry: tuple[str, ...]
    """Modelos whose opening compensation balance the region records."""
    files: tuple[str, ...]
    """Modelos the region opens, calculates, verifies and files for every applicable period."""
    begin: int
    """Index of the ``:generated: begin`` line."""
    end: int
    """Index of the ``:generated: end`` line."""


def _scan_directives(lines: list[str], *, name: str) -> tuple[dict[str, str], list[tuple[int, str]]]:
    """The seed's declared directives and the line index and value of each ``:generated:`` marker."""
    declared: dict[str, str] = {}
    markers: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        matched = _DIRECTIVE.match(line)
        if matched is None:
            continue
        directive, value = matched["name"], matched["value"]
        if directive == "generated":
            markers.append((index, value))
        elif directive in declared:
            raise ValueError(f"seed:{name} line {index + 1}: ':{directive}:' is declared twice")
        else:
            declared[directive] = value
    return declared, markers


def _require_persona_directives(declared: dict[str, str], markers: list[tuple[int, str]], *, name: str) -> None:
    missing = {"persona", "profile"} - declared.keys()
    if missing:
        raise ValueError(
            f"seed:{name}: a persona recipe also declares {', '.join(f':{item}:' for item in sorted(missing))}"
        )
    if [value for _, value in markers] != [_BEGIN, _END]:
        raise ValueError(f"seed:{name}: expected exactly one ':generated: begin' then one ':generated: end' line")
    if not declared["profile"].split() or not declared["persona"]:
        raise ValueError(f"seed:{name}: ':persona:' and ':profile:' must each carry a value")
    _require_supported_values(declared, name=name)


def _require_supported_values(declared: dict[str, str], *, name: str) -> None:
    ledger = declared.get("ledger")
    if ledger is not None and ledger != _LEDGER_ALL:
        raise ValueError(f"seed:{name}: ':ledger:' takes only {_LEDGER_ALL!r}, found {ledger!r}")
    if any(modelo != _M303 for modelo in declared.get("carry", "").split()):
        raise ValueError(f"seed:{name}: ':carry:' records only the Modelo {_M303} compensation balance")


def parse_seed_header(text: str, *, name: str) -> SeedHeader | None:
    """Return the recipe's persona header, ``None`` for a recipe that declares no persona.

    Raises:
        ValueError: When the header is incomplete, repeated or its region is not one begin/end pair.
    """
    declared, markers = _scan_directives(text.splitlines(), name=name)
    if not declared and not markers:
        return None
    _require_persona_directives(declared, markers, name=name)
    questions = tuple(declared["profile"].split())
    ledger = declared.get("ledger")
    carry = tuple(declared.get("carry", "").split())
    return SeedHeader(
        persona=declared["persona"],
        questions=questions,
        identities=tuple(declared.get("identities", "").split()),
        ledger=ledger is not None,
        carry=carry,
        files=tuple(declared.get("file", "").split()),
        begin=markers[0][0],
        end=markers[1][0],
    )


def render_seed(text: str, *, name: str) -> str:
    """Return ``text`` with its generated region rendered from the declared persona."""
    header = parse_seed_header(text, name=name)
    if header is None:
        return text
    with pinned_persona(header.persona) as (persona, envelope):
        options = profile_option_arguments(persona, envelope, header.questions)
        flow = _ledger_frames(persona, envelope, name=name) if header.ledger else []
        if header.carry:
            flow.extend(_carry_frames(persona, envelope, name=name))
        for modelo in header.files:
            flow.extend(_filing_frames(persona, envelope, modelo, name=name))
    for role in header.identities:
        identity = persona.identities.role(role)
        stated = [identity.value, identity.legal_name or " ".join(filter(None, (identity.name, identity.surnames)))]
        absent = [value for value in stated if value not in text]
        if absent:
            raise ValueError(f"seed:{name}: the authored frames do not state {role} as the catalogue does ({absent})")
    frame = " ".join(("aeat config profile edit", SANDBOX_PROFILE_LABEL, "--quiet", *options))
    lines = text.splitlines()
    region = [lines[header.begin], f"@setup {frame}", *flow, lines[header.end]]
    rendered = [*lines[: header.begin], *region, *lines[header.end + 1 :]]
    return "\n".join(rendered) + "\n"


# -- ledger, invoices and documents --------------------------------------------------------------------------------


def _capture_name(ref: str) -> str:
    """The capture a row's transaction id is bound to: its ref in lower snake case."""
    return re.sub(r"[^0-9a-z]+", "_", ref.lower()).strip("_")


def _quoted(value: str) -> str:
    if '"' in value:
        raise ValueError(f"a generated frame cannot quote {value!r}")
    return f'"{value}"' if re.search(r"[\s{}]", value) else value


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _percentage(fraction: Decimal) -> str:
    """A ledger fraction as an invoice or evidence rate takes it: a percentage without trailing zeros."""
    return _decimal((fraction * 100).normalize())


def _party_name(persona: Persona, role: str) -> str:
    identity = persona.identities.role(role)
    return identity.legal_name or f"{identity.field('name')} {identity.field('surnames')}"


def _ledger_frames(persona: Persona, envelope: YearEnvelope, *, name: str) -> list[str]:
    """The persona's rows, invoices and documents, in the order the materialiser replays them."""
    rows = sorted(persona.ledger, key=lambda row: (row.operation_date(envelope), row.ref))
    attached = {ref for document in persona.documents for ref in document.attach_to}
    lines: list[str] = []
    for row in rows:
        consumed = row.ref in attached or (row.invoice_kind is not None and row.invoice_number is not None)
        lines.extend(_row_frames(persona, envelope, row, name=name, captured=consumed))
    for row in rows:
        lines.extend(_invoice_frames(persona, envelope, row))
    for document in persona.documents:
        path = document.path if document.path is not None else _generated_document_path(persona.id, document.id)
        lines.extend(_document_frames(persona, document.id, path, document.attach_to, name=name))
    return lines


def _generated_document_path(persona_id: str, document_id: str) -> Path:
    """Where a persona's generated document lies in the docs fixtures tree the sandbox copies."""
    return default_fixtures_root() / _GENERATED_DOCUMENTS / persona_id / f"{document_id}.xml"


def _row_frames(persona: Persona, envelope: YearEnvelope, row: LedgerRow, *, name: str, captured: bool) -> list[str]:
    """One row's manual entry; its transaction id is captured only when a later frame links or attaches to it."""
    if row.recargo_amount is not None:
        raise ValueError(f"seed:{name}: {persona.id} {row.ref} bears recargo, which the manual entry refuses here")
    arguments = [
        "--date",
        row.operation_date(envelope).isoformat(),
        "--amount",
        _decimal(abs(row.amount)),
        "--direction",
        "INCOMING" if row.amount > 0 else "OUTGOING",
        "--description",
        _quoted(row.description),
        "--currency",
        row.currency,
    ]
    if row.counterparty is not None:
        arguments.extend(("--counterparty", _quoted(_party_name(persona, row.counterparty))))
        country = persona.identities.role(row.counterparty).country
        if country is not None:
            arguments.extend(("--counterparty-country", country))
    arguments.extend(("--classification", row.classification))
    optional: tuple[tuple[str, str | Decimal | None], ...] = (
        ("--category-id", row.category_id),
        ("--irpf-category", row.irpf_category),
        ("--iva-category", row.iva_category),
        ("--taxable-base", row.taxable_base),
        ("--iva-rate", row.iva_rate),
        ("--iva-amount", row.iva_amount),
        ("--deduction-kind", row.deduction_kind),
    )
    for option, value in optional:
        if value is not None:
            arguments.extend((option, _decimal(value) if isinstance(value, Decimal) else value))
    arguments.extend(("--idempotency-key", row.ref))
    lines = [
        f"@step Record {row.ref}, {row.description}, with its tax fields.",
        f"@setup aeat --format json app ledger add {' '.join(arguments)}",
    ]
    if captured:
        lines.append(f"@capture {_capture_name(row.ref)} result.transaction_id")
    return lines


def _present(value: Decimal | None, render: Callable[[Decimal], str]) -> str | None:
    return None if value is None else render(value)


def _optional_invoice_arguments(row: LedgerRow) -> list[str]:
    optional: tuple[tuple[str, str | None], ...] = (
        ("--taxable-base", _present(row.taxable_base, _decimal)),
        ("--iva-rate", _present(row.iva_rate, _percentage)),
        ("--iva-category", row.iva_category),
        ("--retention-rate", _present(row.retencion_rate, _decimal)),
        ("--retention-amount", _present(row.retencion_amount, _decimal)),
    )
    return [token for option, value in optional if value is not None for token in (option, value)]


def _invoice_frames(persona: Persona, envelope: YearEnvelope, row: LedgerRow) -> list[str]:
    if row.invoice_kind is None or row.invoice_number is None or row.counterparty is None:
        return []
    counterparty = persona.identities.role(row.counterparty)
    arguments = [
        "--kind",
        row.invoice_kind,
        "--counterparty-name",
        _quoted(_party_name(persona, row.counterparty)),
        "--counterparty-nif",
        counterparty.value,
        "--country-code",
        counterparty.country or "ES",
        "--invoice-number",
        _quoted(row.invoice_number),
        "--invoice-date",
        row.operation_date(envelope).isoformat(),
        "--currency",
        row.currency,
    ]
    arguments.extend(_optional_invoice_arguments(row))
    transaction = _capture_name(row.ref)
    invoice = f"{transaction}_invoice"
    return [
        f"@step Record the {row.invoice_kind} invoice {row.invoice_number} behind {row.ref} and link it to the row.",
        f"@setup aeat --format json app ledger invoice add {' '.join(arguments)}",
        f"@capture {invoice} result.invoice_id",
        f"@setup aeat app ledger link {{{transaction}}} --invoice-id {{{invoice}}}",
    ]


def _document_frames(
    persona: Persona, document_id: str, path: Path, attach_to: tuple[str, ...], *, name: str
) -> list[str]:
    fixtures = default_fixtures_root().resolve()
    resolved = (path if path.is_absolute() else REPO_ROOT / path).resolve()
    if not resolved.is_relative_to(fixtures):
        raise ValueError(
            f"seed:{name}: {persona.id} document {document_id} lies outside the docs fixtures tree the sandbox copies"
        )
    sandbox_path = Path("fixtures", resolved.relative_to(fixtures)).as_posix()
    evidence = f"{_capture_name(document_id)}_evidence"
    lines = [
        f"@step Register document {document_id} as encrypted evidence bytes and attach it to its rows.",
        (
            f"@setup aeat --format json app ledger evidence add {sandbox_path} "
            f"--idempotency-key persona-{persona.id}-{document_id}"
        ),
        f"@capture {evidence} result.evidence_id",
    ]
    lines.extend(
        f"@setup aeat app ledger attach {{{_capture_name(ref)}}} --purchase-invoice-evidence-id {{{evidence}}}"
        for ref in attach_to
    )
    return lines


# -- Modelo work ---------------------------------------------------------------------------------------------------


def _applicable_periods(persona: Persona, envelope: YearEnvelope, modelo: str, *, name: str) -> tuple[str, ...]:
    year = persona.fiscal_year.resolve(envelope)
    periods = tuple(
        period
        for obligation in persona.expectations.obligations
        if obligation.modelo == modelo and obligation.applicable is True and obligation.year.resolve(envelope) == year
        for period in obligation.periods
    )
    if not periods:
        raise ValueError(f"seed:{name}: {persona.id} states no applicable Modelo {modelo} period in its fiscal year")
    return periods


def _carry_frames(persona: Persona, envelope: YearEnvelope, *, name: str) -> list[str]:
    """Record the compensation balance the first Modelo 303 period of the fiscal year starts from."""
    year = persona.fiscal_year.resolve(envelope)
    first = _applicable_periods(persona, envelope, _M303, name=name)[0]
    if first != "1T":
        raise ValueError(f"seed:{name}: {persona.id} files Modelo {_M303} from {first}; a carry precedes 1T only")
    expected = next(
        (
            value
            for value in persona.expectations.values
            if value.modelo == _M303 and value.period == first and value.year.resolve(envelope) == year
        ),
        None,
    )
    if expected is None:
        raise ValueError(f"seed:{name}: {persona.id} states no Modelo {_M303} {first} expectation to carry from")
    amount = dict(expected.casillas).get(_M303_PENDING_FROM_EARLIER, "0")
    return [
        f"@step Record the compensation balance the {year} first quarter starts from, as the persona's figures state.",
        (
            f"@setup aeat --format json app modelo iva-wallet seed --filing-year {year - 1} --period 4T "
            f"--amount {_decimal(Decimal(amount).normalize())} --confirm"
        ),
    ]


def _filing_frames(persona: Persona, envelope: YearEnvelope, modelo: str, *, name: str) -> list[str]:
    year = persona.fiscal_year.resolve(envelope)
    if modelo != _M303:
        raise ValueError(f"seed:{name}: ':file:' files Modelo {_M303} only; found {modelo}")
    lines: list[str] = []
    periods = _applicable_periods(persona, envelope, modelo, name=name)
    for period in periods:
        prefix = f"m{modelo}_{period.lower()}"
        work, revision = f"{prefix}_work_unit_id", f"{prefix}_calculation_revision_id"
        lines.extend(
            (
                f"@step Open, calculate, verify and record as filed the {year} {period} Modelo {modelo}.",
                f"@setup aeat --format json app modelo work create --modelo {modelo} --year {year} --period {period}",
                f"@capture {work} result.work_unit_id",
            )
        )
        attestation = ""
        if period == periods[-1] and period == "4T":
            month = _QUARTER_END_MONTH[period]
            observed = date(year, month, _QUARTER_END_DAY[month]).isoformat()
            lines.extend(
                (
                    (
                        f"@setup aeat --format json app modelo work attest-m303-exonerado-390 --year {year} "
                        f"--period {period} --observed-at {observed}T12:00:00+00:00"
                    ),
                    f"@capture {prefix}_attestation result.attachment_id",
                    f"@capture {prefix}_attestation_sha256 result.sha256",
                )
            )
            attestation = (
                f" --m303-exonerado-390-attachment-id {{{prefix}_attestation}}"
                f" --m303-exonerado-390-sha256 {{{prefix}_attestation_sha256}}"
            )
        lines.extend(
            (
                (
                    f"@setup aeat --format json app modelo work calculate {{{work}}} "
                    f"--no-joint-return-elected{attestation}"
                ),
                f"@capture {revision} result.calculation_revision_id",
                f"@setup aeat --format json app modelo work verify {{{revision}}}",
                f"@setup aeat --format json app modelo work file {{{revision}}}",
            )
        )
    return lines


# -- the sandbox persona's bank statement --------------------------------------------------------------------------

_STATEMENT_HEADER: Final = "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda;Referencia"


def render_statement_fixture(persona_id: str = SANDBOX_PERSONA_ID) -> tuple[str, str]:
    """Return ``(fixture name, text)`` of the persona's first-quarter bank statement.

    The pages that demonstrate a statement import read this file. Its rows are
    the persona's ledger in the statement columns ``app ledger import --file``
    reads, with each row's ref as the bank reference and a running balance, as
    the persona materialiser writes its own statement.
    """
    with pinned_persona(persona_id) as (persona, envelope):
        year = persona.fiscal_year.resolve(envelope)
        rows = sorted(persona.ledger, key=lambda row: (row.operation_date(envelope), row.ref))
        dates = [row.operation_date(envelope) for row in rows]
    if any(day.year != year or day.month > _QUARTER_END_MONTH["1T"] for day in dates):
        raise ValueError(f"{persona_id}: the statement fixture holds the first quarter of {year} only")
    lines = [_STATEMENT_HEADER]
    balance = Decimal("0.00")
    for row, day in zip(rows, dates, strict=True):
        balance += row.amount
        text_day = day.strftime("%d/%m/%Y")
        amount, running = (_decimal(value).replace(".", ",") for value in (row.amount, balance))
        lines.append(";".join((text_day, text_day, row.description, amount, running, row.currency, row.ref)))
    return f"movimientos-{year}-1t.csv", "\n".join(lines) + "\n"


def _statement_problem(fixtures_root: Path) -> str | None:
    name, text = render_statement_fixture()
    path = fixtures_root / name
    if not path.is_file() or path.read_text(encoding=UTF_8) != text:
        return (
            f"fixture:{name}: the statement differs from the sandbox persona's ledger; "
            "regenerate it with: python -m dev.docs.sequences seeds"
        )
    return None


# -- the documents personas generate --------------------------------------------------------------------------------


def _ledger_personas(seeds_root: Path) -> list[str]:
    """The personas whose ledger a recipe records, and so whose documents the sandbox must hold."""
    personas: set[str] = set()
    for recipe in _recipes(seeds_root):
        header = parse_seed_header(recipe.read_text(encoding=UTF_8), name=recipe.stem)
        if header is not None and header.ledger:
            personas.add(header.persona)
    return sorted(personas)


def _expected_documents(seeds_root: Path) -> dict[Path, str]:
    expected: dict[Path, str] = {}
    for persona_id in _ledger_personas(seeds_root):
        with pinned_persona(persona_id) as (persona, envelope):
            documents: tuple[GeneratedDocument, ...] = generated_documents(persona, envelope)
        for document in documents:
            expected[_generated_document_path(persona_id, document.document_id)] = document.text
    return expected


def _present_documents() -> set[Path]:
    directory = default_fixtures_root() / _GENERATED_DOCUMENTS
    return set(directory.glob("*/*.xml")) if directory.is_dir() else set()


def _fixture_name(path: Path) -> str:
    return path.relative_to(default_fixtures_root()).as_posix()


def _document_problems(seeds_root: Path) -> list[str]:
    expected = _expected_documents(seeds_root)
    problems = [
        f"fixture:{_fixture_name(path)}: the generated document differs from its persona row; "
        "regenerate it with: python -m dev.docs.sequences seeds"
        for path, text in expected.items()
        if not path.is_file() or path.read_text(encoding=UTF_8) != text
    ]
    problems.extend(
        f"fixture:{_fixture_name(path)}: no persona generates this document; "
        "regenerate with: python -m dev.docs.sequences seeds"
        for path in sorted(_present_documents() - set(expected))
    )
    return problems


def _write_documents(seeds_root: Path) -> list[Path]:
    expected = _expected_documents(seeds_root)
    written: list[Path] = []
    for stale in sorted(_present_documents() - set(expected)):
        stale.unlink()
        written.append(stale)
    for path, text in expected.items():
        if not path.is_file() or path.read_text(encoding=UTF_8) != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding=UTF_8, newline="\n")
            written.append(path)
    return written


# -- check and write -----------------------------------------------------------------------------------------------


def _recipes(seeds_root: Path) -> list[Path]:
    return sorted(seeds_root.glob(f"*{SEED_SUFFIX}"))


def check_seeds(*, seeds_root: Path | None = None) -> tuple[str, ...]:
    """Return one problem per recipe whose committed text differs from its regeneration."""
    root = seeds_root if seeds_root is not None else default_seeds_root()
    problems: list[str] = []
    if seeds_root is None:
        statement = _statement_problem(default_fixtures_root())
        if statement is not None:
            problems.append(statement)
        problems.extend(_document_problems(root))
    for recipe in _recipes(root):
        committed = recipe.read_text(encoding=UTF_8)
        try:
            expected = render_seed(committed, name=recipe.stem)
        except ValueError as error:
            problems.append(str(error))
            continue
        if committed != expected:
            problems.append(
                f"seed:{recipe.stem}: the generated region differs from the persona it declares; "
                "regenerate it with: python -m dev.docs.sequences seeds"
            )
    return tuple(problems)


def write_seeds(*, seeds_root: Path | None = None) -> tuple[Path, ...]:
    """Rewrite every recipe whose generated region is stale; return the recipes written."""
    root = seeds_root if seeds_root is not None else default_seeds_root()
    written: list[Path] = []
    if seeds_root is None and _statement_problem(default_fixtures_root()) is not None:
        name, text = render_statement_fixture()
        target = default_fixtures_root() / name
        target.write_text(text, encoding=UTF_8, newline="\n")
        written.append(target)
    if seeds_root is None:
        written.extend(_write_documents(root))
    for recipe in _recipes(root):
        committed = recipe.read_text(encoding=UTF_8)
        expected = render_seed(committed, name=recipe.stem)
        if committed != expected:
            recipe.write_text(expected, encoding=UTF_8, newline="\n")
            written.append(recipe)
    return tuple(written)
