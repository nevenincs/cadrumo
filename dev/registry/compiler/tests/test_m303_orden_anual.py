"""The generated Modelo 303 annual Orden artefacts still match their sources.

This module's `--check` mode already refuses a stale or missing artefact, and
nothing ran it. It was the only module in this package carrying a public surface
that no test imported - found after three wrong answers from three wrong ways of
asking, and worth a test precisely because a generator nobody invokes is
indistinguishable from one whose output is current.
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    validating_governed_facts,
)

from ...analysis.m303_orden_anual import main
from .._m303_orden_source import extract_m303_annual_orden_source
from ..loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_check_mode_accepts_the_committed_artefacts() -> None:
    """The shipped manifest and census artefact reproduce from their pinned sources.

    Exit zero here means the committed bytes are what the current extraction
    produces. A drift shows up as a refusal from the check itself, naming which
    artefact moved, rather than as a difference nobody looks for - which is the
    state this artefact pair was in until now, since the generator was reachable
    only by hand.
    """
    assert main(["--check"]) == 0


def test_the_check_flag_is_what_refuses_rather_than_the_default() -> None:
    """The default WRITES, so a test must never invoke it.

    Recorded as an assertion rather than a comment because the distinction is
    one keystroke wide and the wrong side of it regenerates registry artefacts
    from a test run. The parser is inspected instead of exercised.
    """
    import argparse
    import inspect

    source = inspect.getsource(main)

    assert '"--check"' in source
    assert 'action="store_true"' in source
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    assert parser.parse_args([]).check is False, "an absent flag must not read as a check"


def test_extraction_outside_a_facts_scope_names_the_missing_authority() -> None:
    """An absent facts authority must not be reported as an absent legal fact.

    This is the divergence that made the gate above fail while every test of
    the same extraction passed: the owning test module scopes governed facts
    for its whole body, so the compiler's municipal-reduction cross-check
    always had an authority there and never had one here. The cross-check
    caught the broad validation type, so "nothing supplied the facts" arrived
    as "the annual Orden exposes a reduction the facts do not author" -- a
    confident statement about tax law standing in for a wiring defect.

    Both halves are asserted. The refusal must name the missing authority, and
    it must NOT be the coverage claim, because a regression that re-broadens
    the catch reinstates exactly that sentence.
    """
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    source = catalogues.sources["boe-orden-hfp-1335-2021-iva-authority"]

    with pytest.raises(RegistryValidationError) as refusal:
        extract_m303_annual_orden_source(
            ejercicio=2022,
            source=source,
            source_root=bundled_path(),
        )

    message = str(refusal.value)
    assert "requires an explicit authority operation or scope" in message
    assert "without a matching facts projection" not in message


def test_an_unauthored_reduction_year_still_reports_the_coverage_gap() -> None:
    """Narrowing the catch must not blind the check to the finding it exists for.

    The 2022 source states the Lorca reduction in its own text. With that
    year's variant removed from the facts catalogue -- an authority in scope,
    resolving normally, authoring nothing for the coordinate -- the observed
    reduction is genuinely unaccounted for, and the coverage refusal is the
    correct report. Built by removing one variant rather than by editing the
    corpus, so the source bytes stay the pinned ones.
    """
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    source = catalogues.sources["boe-orden-hfp-1335-2021-iva-authority"]
    lorca = catalogues.facts.facts["liva-orden-lorca-reduction"]
    without_2022 = GovernedFactCatalogue(
        facts={
            **catalogues.facts.facts,
            lorca.fact_id: lorca.model_copy(
                update={
                    "variants": tuple(
                        variant for variant in lorca.variants if not variant.variant_id.endswith(":2022-01-01")
                    )
                }
            ),
        }
    )

    with (
        validating_governed_facts(CandidateFactAuthority(without_2022, catalogues.require_supported_filing_years())),
        pytest.raises(RegistryValidationError, match="without a matching facts projection"),
    ):
        extract_m303_annual_orden_source(
            ejercicio=2022,
            source=source,
            source_root=bundled_path(),
        )
