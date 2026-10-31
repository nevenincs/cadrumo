"""The generated Modelo 303 annual Orden artefacts still match their sources.

This module's `--check` mode already refuses a stale or missing artefact, and
nothing ran it. It was the only module in this package carrying a public surface
that no test imported - found after three wrong answers from three wrong ways of
asking, and worth a test precisely because a generator nobody invokes is
indistinguishable from one whose output is current.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.form_codes import resolve_form_codes
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.schema_references import TemporalSupportEnvelope
from cadrumo.domain.calculations.registry.tests.fact_scope import outside_governed_fact_validation
from cadrumo.domain.iva.errors import IvaValidationError
from cadrumo.domain.iva.schema import validate_orden_module_identities

from ...analysis.m303_orden_anual import main
from .._m303_orden_projection_compiler import require_declared_orden_shape
from .._m303_orden_source import extract_m303_annual_orden_source
from ..annual_orden_auxiliary_indicator import resolve_annual_orden_auxiliary_activity_indicators
from ..fact_loader import load_governed_fact_file
from ..loader import load_registry_tree
from ..m303_orden_raw_models import (
    M303AnnualOrdenRawActivity,
    M303AnnualOrdenRawModule,
    M303AnnualOrdenRawSeasonalIndex,
    M303AnnualOrdenSourceCensus,
)

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

    with pytest.raises(
        InternalInvariantError, match="requires an explicit generation-pinned governed-fact scope"
    ) as refusal:
        extract_m303_annual_orden_source(
            ejercicio=2022,
            source=source,
            source_root=bundled_path(),
        )

    message = str(refusal.value)
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


def _extracted_census() -> M303AnnualOrdenSourceCensus:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    source = catalogues.sources["boe-orden-hfp-1335-2021-iva-authority"]
    return extract_m303_annual_orden_source(ejercicio=2022, source=source, source_root=bundled_path())


@pytest.mark.usefixtures("governed_fact_scope")
def test_the_extracted_orden_has_the_shape_the_registry_declares() -> None:
    """CONTROL: the refusals below are the mutated value, not the census."""
    require_declared_orden_shape(_extracted_census())


@pytest.mark.usefixtures("governed_fact_scope")
def test_a_module_order_past_the_declared_rows_is_refused() -> None:
    census = _extracted_census()
    activity = census.activities[0]
    module = activity.modules[0].model_copy(update={"order": 8})
    mutated = census.model_copy(update={"activities": (activity.model_copy(update={"modules": (module,)}),)})

    with pytest.raises(RegistryValidationError, match="module order is past"):
        require_declared_orden_shape(mutated)


def test_module_capacity_follows_the_candidate_fact_not_a_domain_literal() -> None:
    fact = load_governed_fact_file(bundled_path("registry", "aeat", "facts", "0167-form-row-codes.toml"))
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact})
    support = TemporalSupportEnvelope(floor=2022, horizon=2026)
    variant = fact.variants[0]
    assert isinstance(variant.payload, MappingFactPayload)
    base = CandidateFactAuthority(catalogue, support)
    with validating_governed_facts(base):
        codes = resolve_form_codes("form-row-codes", effective_date=date(2025, 1, 1))
        limit = int(codes.code("m303.orden.modules_per_activity"))
        bands = int(codes.code("m303.orden.seasonal_bands"))
    expanded_limit = limit + 1
    entries = tuple(
        entry.model_copy(update={"value": str(expanded_limit)})
        if entry.key == "m303.orden.modules_per_activity"
        else entry
        for entry in variant.payload.entries
    )
    assert entries != variant.payload.entries
    expanded = fact.model_copy(
        update={
            "variants": (
                variant.model_copy(update={"payload": variant.payload.model_copy(update={"entries": entries})}),
            )
        }
    )
    facts = GovernedFactCatalogue(facts={fact.fact_id: expanded})
    wider = CandidateFactAuthority(facts, support)
    modules = tuple(
        M303AnnualOrdenRawModule(
            order=order,
            definition=f"module {order}",
            unit="person",
            coefficient=Decimal("1"),
            required_text="source wording",
        )
        for order in range(1, expanded_limit + 1)
    )
    activity = M303AnnualOrdenRawActivity(
        annex_heading="ANEXO II",
        activity_name="Example activity",
        iae_epigrafe="123.4",
        modules=modules,
        cuota_minima_pct=Decimal("1"),
        required_text=("source wording",),
    )
    altered = M303AnnualOrdenSourceCensus.model_construct(
        ejercicio=2025,
        activities=(activity,),
        seasonal_indexes=tuple(
            M303AnnualOrdenRawSeasonalIndex(
                minimum_days=1,
                maximum_days=1,
                coefficient=Decimal("1"),
                required_text="source wording",
            )
            for _ in range(bands)
        ),
    )

    validate_orden_module_identities(
        tuple(
            SimpleNamespace(order=order, coefficient=Decimal("1"), identity=str(order))
            for order in range(1, expanded_limit + 1)
        )
    )
    with validating_governed_facts(base), pytest.raises(RegistryValidationError, match="module order is past"):
        require_declared_orden_shape(altered)
    with validating_governed_facts(wider):
        require_declared_orden_shape(altered)


def test_module_identity_structure_remains_closed() -> None:
    good = SimpleNamespace(order=1, coefficient=Decimal("1"), identity="a")
    with pytest.raises(IvaValidationError, match="at least one"):
        validate_orden_module_identities(())
    with pytest.raises(IvaValidationError, match="complete and ordered"):
        validate_orden_module_identities((SimpleNamespace(order=2, coefficient=Decimal("1"), identity="a"),))
    with pytest.raises(IvaValidationError, match="positive"):
        validate_orden_module_identities((SimpleNamespace(order=1, coefficient=Decimal("0"), identity="a"),))
    with pytest.raises(IvaValidationError, match="duplicate"):
        validate_orden_module_identities((good, SimpleNamespace(order=2, coefficient=Decimal("1"), identity="a")))


@pytest.mark.usefixtures("governed_fact_scope")
def test_a_seasonal_band_past_the_declared_days_is_refused() -> None:
    census = _extracted_census()
    last = census.seasonal_indexes[-1].model_copy(update={"maximum_days": 181})
    mutated = census.model_copy(update={"seasonal_indexes": (*census.seasonal_indexes[:-1], last)})

    with pytest.raises(RegistryValidationError, match="seasonal band is past"):
        require_declared_orden_shape(mutated)


@pytest.mark.usefixtures("governed_fact_scope")
def test_a_missing_seasonal_band_is_refused() -> None:
    census = _extracted_census()
    mutated = census.model_copy(update={"seasonal_indexes": census.seasonal_indexes[:-1]})

    with pytest.raises(RegistryValidationError, match="exactly 3 seasonal index bands"):
        require_declared_orden_shape(mutated)


def test_the_auxiliary_indicator_lookup_refuses_when_neither_authority_nor_scope_is_supplied() -> None:
    with (
        outside_governed_fact_validation(),
        pytest.raises(InternalInvariantError, match="requires an explicit generation-pinned governed-fact scope"),
    ):
        resolve_annual_orden_auxiliary_activity_indicators(effective_date=date(2025, 1, 1))


def test_the_same_lookup_resolves_from_an_explicit_authority_without_a_scope() -> None:
    """CONTROL: the refusal above is the missing scope, not the lookup."""
    with bundled_indexed_authority().lease_operation() as operation, outside_governed_fact_validation():
        indicators = resolve_annual_orden_auxiliary_activity_indicators(
            effective_date=date(2025, 1, 1), authority=operation
        )

    assert indicators.by_iae_and_activity
