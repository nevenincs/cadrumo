"""A field that carries a currency code uses the one annotation for it.

This gate exists because the manual search kept succeeding. Four consecutive
rounds of the consolidation campaign each found a currency declaration the
previous round had missed -- a length-only alias in the ledger models, a
length-only bound on the invoice record, a bare ``min_length=1`` on a filing
snapshot, a hand-rolled ``^[A-Z]{3}$`` pattern -- and each time the fix was the
same and the next one was still out there. Four policies were live at once and
they disagreed on ordinary input: ``"eur"`` normalised at one site, passed
through unchanged at another and was refused at a third; ``"12A"`` was accepted
by two; a filing snapshot accepted the single character ``"E"``.

The rule is therefore structural rather than a list of known sites. Any field
whose NAME says it carries a currency code must be annotated
:obj:`~core.parsing.IsoCurrencyCode`, which trims, uppercases and requires three
letters -- or be recorded below with the reason it does not.

The allowlist is where the judgement lives, so every entry states a reason and a
stale entry fails. It deliberately does not accept a bare "legacy" or "TODO":
the entries here are decisions, and a decision that cannot be written down in a
sentence is not one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent.parent

#: The canonical annotation, and the spellings a field may use to name it.
_CANONICAL = {"IsoCurrencyCode", "IsoCurrencyCode | None"}

#: Field names that carry an ISO 4217 code. Deliberately narrow: a name like
#: ``local_recurrence_amount`` contains no currency code however it reads, and
#: ``financial_base_currency`` on a settings object is a configuration key.
_CURRENCY_FIELD_NAMES = {"currency", "currency_code", "invoice_currency", "source_currency", "target_currency"}

#: Fields that carry a currency code under a different annotation, each with the
#: reason. A reason naming a REVIEWED difference in behaviour is the only kind
#: that belongs here.
DECLARED_EXCEPTIONS: dict[str, str] = {
    "application/operations/financial_operand.py::currency": (
        "a registry-AUTHORED declaration rather than operator or bank input, so "
        "a sloppy code should fail the author at load; IsoCurrencyCode would "
        "normalise an authored 'eur' and repair it behind them"
    ),
    "adapters/inbound/financial/providers/csv.py::currency": (
        "a raw parsed cell, held exactly as the bank exported it so the adapter "
        "can name the offending value; normalisation happens once at the "
        "RawTransaction boundary this feeds, not twice"
    ),
    "adapters/inbound/financial/providers/_mapped_tabular.py::currency": (
        "the same raw parse struct as the CSV provider, for the same reason: it "
        "carries the source cell, and RawTransaction normalises it"
    ),
    "entrypoints/cli/ledger_business_payloads.py::currency": (
        "one field of an EvidenceExtractResult, the extractor's reading of a "
        "document, sitting beside taxable_base and iva_rate which are strings "
        "for the same reason: the payload shows the operator what was read, "
        "including when what was read is wrong"
    ),
    "application/ledger/invoice_draft_records.py::currency": (
        "read off a document rather than declared, so it must hold whatever the "
        "invoice actually said -- a refusal that cannot quote the unreadable "
        "value tells the operator nothing about which document to fix"
    ),
    "llm/invoice_field_grounding.py::currency": (
        "an extraction result awaiting grounding; refusing a malformed code at "
        "the model boundary would discard the evidence the grounding check "
        "exists to evaluate"
    ),
    "llm/suggestions.py::currency": (
        "a suggestion the operator has not accepted yet, so it carries the "
        "model's output verbatim; it is validated when accepted, not when read"
    ),
    "domain/renta/ledger_expenses.py::currency": (
        "Literal['EUR'] is STRICTER than the canonical annotation, not looser: "
        "this expense projection is euro-only by construction and the literal "
        "states that in the type rather than in a comment"
    ),
    "domain/calculations/registry/detail_record_bindings.py::currency_code": (
        "governed by the shared uppercase_alpha_code validator this model "
        "already applies to country_code beside it, which REFUSES a lowercase "
        "code rather than folding it -- a Modelo 720 declaration states the "
        "code, and a normalising annotation here would layer a second policy "
        "over the one its sibling field follows"
    ),
    "domain/transactions/raw_transaction.py::currency": (
        "carries the length bound as an annotation but normalises through "
        "normalise_iso_4217_currency in a mode='before' validator, so it "
        "already applies the canonical policy and raises its own "
        "TransactionValidationError rather than a generic one"
    ),
}


def _currency_fields() -> dict[str, set[str]]:
    """Map ``path::field`` -> the set of annotations declared under that name.

    A SET, not a single annotation. Five modules declare a currency field name
    more than once -- ``application/ledger/models.py`` does it four times -- and
    keying to a single value let the last declaration overwrite the rest, so the
    gate could see only one of four and reported nothing about the others. The
    sibling country gate had the identical flaw and a mutation probe exposed it
    there; this is the same fix applied before it could hide anything here.

    The key stays ``path::field`` rather than gaining a line number, because an
    exception keyed by line goes stale on the next edit above it.
    """
    found: dict[str, set[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        parts = path.relative_to(_SRC).parts
        if "tests" in parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        relative = path.relative_to(_SRC).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id not in _CURRENCY_FIELD_NAMES:
                continue
            annotation = ast.unparse(node.annotation)
            # A settings CONSTANT is not a model field carrying a value.
            if annotation.startswith("Final["):
                continue
            found.setdefault(f"{relative}::{node.target.id}", set()).add(annotation)
    return found


def test_every_currency_field_uses_the_canonical_annotation() -> None:
    """A new currency field must adopt the one annotation or declare why not."""
    offenders = {
        site: sorted(annotations - _CANONICAL)
        for site, annotations in _currency_fields().items()
        if not annotations <= _CANONICAL and site not in DECLARED_EXCEPTIONS
    }

    assert not offenders, (
        "these fields carry an ISO 4217 code under their own annotation. Use "
        "core.parsing.IsoCurrencyCode, which trims, uppercases and requires "
        "three letters; if this field genuinely must differ, record it in "
        f"DECLARED_EXCEPTIONS with the reason: {offenders}"
    )


def test_declared_exceptions_still_exist() -> None:
    """An exception whose field moved or adopted the canonical loses its entry."""
    sites = _currency_fields()
    stale = sorted(site for site in DECLARED_EXCEPTIONS if site not in sites)

    assert not stale, (
        "these declared exceptions name a currency field that no longer exists "
        f"at that path: drop them from DECLARED_EXCEPTIONS: {stale}"
    )


def test_declared_exceptions_have_not_quietly_adopted_the_canonical() -> None:
    """An exception that now uses the canonical is a stale entry, not a permission."""
    sites = _currency_fields()
    redundant = sorted(site for site in DECLARED_EXCEPTIONS if site in sites and sites[site] <= _CANONICAL)

    assert not redundant, f"these fields now use the canonical annotation and need no exception: {redundant}"


def test_every_exception_states_a_reason() -> None:
    """The judgement lives in the reason, so a placeholder is not an entry."""
    unreasoned = sorted(
        site
        for site, reason in DECLARED_EXCEPTIONS.items()
        if len(reason.strip()) < 40 or reason.strip().lower().startswith(("todo", "legacy", "temporary"))
    )

    assert not unreasoned, f"these currency exceptions carry no usable reason: {unreasoned}"


def test_the_gate_finds_currency_fields_at_all() -> None:
    """Anti-vacuity: a rename of the field vocabulary must fail, not pass silently.

    Without this, narrowing ``_CURRENCY_FIELD_NAMES`` to nothing -- or a sweep
    that renames the fields -- would make every assertion above trivially true.
    """
    sites = _currency_fields()

    assert len(sites) >= 10, f"only {len(sites)} currency fields discovered; the checks above would prove little"
    assert any(annotations & _CANONICAL for annotations in sites.values()), (
        "no field uses the canonical annotation, so the gate is measuring the wrong thing"
    )
