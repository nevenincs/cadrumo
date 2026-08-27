"""Gate: every parser of official regulatory prose is declared in the channel ledger.

Grammars over AEAT and BOE prose are sanctioned -- the variability they absorb is
the outside world's. What is not sanctioned is an UNDECLARED one: a reader cannot
otherwise tell an entitled parser from a regulatory value hiding in a pattern.

The gate is on the PROPERTY -- every derived parser is enrolled -- never on a
tally of modules or patterns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..analysis.regulatory_prose_parser_channel import (
    ProseChannelLedgerError,
    ProseParserEnrolment,
    derive_prose_parsers,
    load_ledger,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_derivation_yields_a_non_empty_parser_set() -> None:
    """An empty derivation would make the enrolment assertion vacuous."""
    assert derive_prose_parsers(), (
        "the regulatory-prose parser derivation yielded nothing; a gate over an empty set is not a green gate"
    )


def test_every_prose_parser_is_declared_in_the_channel() -> None:
    """No module may read official regulatory prose without declaring it.

    Closing a red here means enrolling the module with the corpus it reads and
    why it must read it -- or, if it derives a regulatory VALUE, landing that
    value in the registry authoring tree with its establishing provision and
    removing it from the pattern.
    """
    unenrolled, stale = reconcile()

    assert unenrolled == (), (
        f"undeclared regulatory-prose parser(s): {list(unenrolled)}. Enrol each in "
        "regulatory_prose_parser_channel.toml naming the corpus and the reason, or move the "
        "regulatory value it derives into the registry authoring tree."
    )
    assert stale == (), (
        f"enrolment rows the derivation no longer yields: {list(stale)}. Remove them; a stale row "
        "silently keeps a channel open for a module that no longer exists."
    )


def test_an_undeclared_parser_refuses() -> None:
    """Anti-tautology: withhold one enrolment and reconciliation must report it."""
    parsers = derive_prose_parsers()
    assert parsers, "no derived parsers to withhold"
    full = {
        parser.module: ProseParserEnrolment(module=parser.module, corpus="c", reason="r")
        for parser in parsers
    }
    withheld = parsers[0].module
    partial = {key: row for key, row in full.items() if key != withheld}

    unenrolled, stale = reconcile(parsers, partial)

    assert unenrolled == (withheld,), f"the gate failed to report a withheld enrolment; it reported {unenrolled!r}"
    assert stale == ()


def test_a_stale_enrolment_refuses() -> None:
    """Anti-tautology: an enrolment for a module the derivation no longer yields is reported."""
    parsers = derive_prose_parsers()
    rows = {
        parser.module: ProseParserEnrolment(module=parser.module, corpus="c", reason="r")
        for parser in parsers
    }
    rows["dev/gone.py"] = ProseParserEnrolment(module="dev/gone.py", corpus="c", reason="r")

    unenrolled, stale = reconcile(parsers, rows)

    assert stale == ("dev/gone.py",)
    assert unenrolled == ()


def test_an_enrolment_must_name_its_corpus_and_reason(tmp_path: Path) -> None:
    """A row that declares nothing declares nothing; it must not load."""
    ledger = tmp_path / "channel.toml"
    ledger.write_text('[[parser]]\nmodule = "dev/x.py"\ncorpus = "  "\nreason = "why"\n', encoding="utf-8")

    with pytest.raises(ProseChannelLedgerError, match="corpus"):
        load_ledger(ledger)


def test_the_shipped_record_design_authority_is_enrolled() -> None:
    """Fixture anchor: the largest shipped prose parser is named, not silently absent.

    Without this, a derivation that stopped yielding the record-design authority
    would make the enrolment assertion pass while the module this gate most needs
    to cover went unwatched.
    """
    rows = load_ledger()

    assert "src/cadrumo/domain/calculations/registry/record_design.py" in rows
    assert rows["src/cadrumo/domain/calculations/registry/record_design.py"].corpus
