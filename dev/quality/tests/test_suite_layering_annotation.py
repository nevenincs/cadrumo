"""A layering run that evaluated nothing must say so, not read as one complaint.

``lint-imports`` stops on the first ``ignore_imports`` pin that matches nothing,
before any contract is evaluated. Its whole output is then a single line naming
that pin, and exit 1. Read quickly, that looks like one narrow failure; it is
actually every layering contract going unchecked.

That has happened twice in this repository, and both times the gate was dead for
days. The reason it is easy to miss is structural rather than careless: a pin
stops matching exactly when somebody FIXES the violation it excused, so the
person whose change killed the gate was improving the tree and has no reason to
open ``.importlinter`` at all.

The fixture strings below are real captured output, not paraphrase.
"""

from __future__ import annotations

from typing import Final

import pytest

from ..suite import annotate_unevaluated_contracts

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Real output from the run that found the gate dead, before the pin was removed.
_ABORTED_RUN: Final = """=============
Import Linter
=============


No matches for ignored import cadrumo.application.aggregation._modelo_bindings
-> cadrumo.adapters.persistence.**.
"""

#: Real output from the same command once the stale pin was gone.
_EVALUATED_RUN: Final = """=============
Import Linter
=============

Analyzed 5627 files, 33968 dependencies.
Contracts: 4 kept, 6 broken.
"""


#: Real output from a later dead-gate run whose pin wrapped inside the module path.
#: The wrap point moves with the pin's length, and this one leaves the marker
#: line carrying no pin at all -- the case the first fixture did not reproduce.
_WRAPPED_MID_IDENTIFIER_RUN: Final = (
    "=============\n"
    "Import Linter\n"
    "=============\n"
    "\n"
    "\n"
    "No matches for ignored import \n"
    "cadrumo.domain.calculations.registry.tests.test_ledger_renta_gastos_estimacion_\n"
    "directa_binding -> cadrumo.domain.renta.\n"
)


def test_a_pin_wrapped_mid_identifier_is_quoted_whole() -> None:
    """The quoted pin must be copy-pasteable back into .importlinter.

    This is the defect a real run exposed. The tool had wrapped inside the
    module path, so reading only the marker line quoted the reader the word
    "import" and nothing else, and rejoining with a space split the identifier.
    Both forms name a pin that cannot be found in the file.
    """
    annotated = annotate_unevaluated_contracts(_WRAPPED_MID_IDENTIFIER_RUN)

    quoted = annotated.rsplit("delete the pin", 1)[1]
    assert "test_ledger_renta_gastos_estimacion_directa_binding" in quoted
    assert "estimacion_ directa" not in quoted


def test_an_aborted_run_is_named_as_evaluating_nothing() -> None:
    """The annotation states the blast radius, which the raw output does not."""
    annotated = annotate_unevaluated_contracts(_ABORTED_RUN)

    assert "NO CONTRACTS WERE EVALUATED" in annotated
    assert _ABORTED_RUN.strip() in annotated


def test_the_stale_pin_is_quoted_so_it_can_be_deleted_without_a_rerun() -> None:
    """Naming the situation is not enough; the reader needs the offending line."""
    annotated = annotate_unevaluated_contracts(_ABORTED_RUN)

    assert "cadrumo.application.aggregation._modelo_bindings" in annotated.rsplit("delete the pin", 1)[1]


def test_the_reader_is_pointed_at_a_repaired_import_not_a_new_one() -> None:
    """The counter-intuitive half: this failure is caused by a FIX, not a regression.

    Without this, the natural response is to hunt for a newly added bad import,
    which does not exist. Both real occurrences were a repaired edge.
    """
    annotated = annotate_unevaluated_contracts(_ABORTED_RUN)

    assert "FIXED" in annotated


def test_a_run_that_evaluated_contracts_is_left_exactly_alone() -> None:
    """A genuine contract failure must not be dressed up as a dead gate."""
    assert annotate_unevaluated_contracts(_EVALUATED_RUN) == _EVALUATED_RUN


def test_an_unrelated_gate_failure_is_left_exactly_alone() -> None:
    """The annotator keys on the linter's own markers, not on failure itself."""
    unrelated = "ruff: 3 errors found\n"

    assert annotate_unevaluated_contracts(unrelated) == unrelated


def test_a_broken_contract_reported_beside_a_stale_pin_still_counts_as_evaluated() -> None:
    """The tally, not the pin warning, decides whether anything was checked.

    import-linter can warn about an unmatched pin under an alerting mode that
    does not abort, and still evaluate every contract. Annotating that run would
    claim nothing was checked when everything was.
    """
    both = _EVALUATED_RUN + "\nNo matches for ignored import cadrumo.a -> cadrumo.b.\n"

    assert annotate_unevaluated_contracts(both) == both
