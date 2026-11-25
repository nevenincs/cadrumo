"""Cross-slice gate for facts that closed the retired global provider."""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    ResolvedEntitySetFact,
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ..compiler import fact_providers
from ..compiler.authority import compile_validated_authority
from ..compiler.fact_providers import compile_registered_fact_providers
from ..compiler.fact_validation import retired_fact_provider_closure_failures
from ..compiler.loader import load_shared_catalogues
from ..compiler.validator import RegistryValidator
from ..pipeline.candidate_staging import stage_generated_export_candidate
from ..pipeline.published_edition_staging import supporting_modelos
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _registry_root():
    return bundled_path("registry", "aeat")


def _catalogue() -> GovernedFactCatalogue:
    return compile_registered_fact_providers(_registry_root())


def _compiler_catalogues() -> RegistryCatalogues:
    root = _registry_root()
    catalogues = load_shared_catalogues(root)
    return catalogues.model_copy(update={"facts": compile_registered_fact_providers(root)})


def _resolve_scalar(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
        authority_digest="6" * 64,
        support=committed_supported_filing_years(),
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def _resolve_entities(fact_id: str, effective_date: date) -> ResolvedEntitySetFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        EntitySetFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
        authority_digest="6" * 64,
        support=committed_supported_filing_years(),
    )
    assert isinstance(resolved, ResolvedEntitySetFact)
    return resolved


def test_direct_canonical_compilation_closes_the_retired_provider_slices() -> None:
    root = _registry_root()
    shared = load_shared_catalogues(root)

    assert retired_fact_provider_closure_failures(_catalogue(), source_refs=shared.sources) == ()


def test_gate_detects_a_missing_fact_and_non_filing_date_axis() -> None:
    catalogue = _catalogue()
    missing = GovernedFactCatalogue(
        facts={
            fact_id: fact for fact_id, fact in catalogue.facts.items() if fact_id != "liva-art-161:recargo-rate-general"
        }
    )
    fact = catalogue.facts["liva-art-161:recargo-rate-general"]
    malformed_variant = fact.variants[0].model_copy(update={"date_axis": DateAxis.DEVENGO_DATE})
    malformed = fact.model_copy(update={"variants": (malformed_variant,)})
    wrong_axis = GovernedFactCatalogue(
        facts={**catalogue.facts, malformed.fact_id: malformed},
    )
    sources = load_shared_catalogues(_registry_root()).sources

    missing_failures = retired_fact_provider_closure_failures(missing, source_refs=sources)
    wrong_axis_failures = retired_fact_provider_closure_failures(wrong_axis, source_refs=sources)

    assert any("is not authored" in failure for failure in missing_failures)
    assert any("must use the filing_period date axis" in failure for failure in wrong_axis_failures)


def test_gate_detects_a_gap_in_source_grounded_temporal_coverage() -> None:
    catalogue = _catalogue()
    fact = catalogue.facts["liva-art-161:recargo-rate-general"]
    gapped_variant = fact.variants[0].model_copy(update={"valid_to": date(1996, 12, 30)})
    gapped_fact = fact.model_copy(update={"variants": (gapped_variant, *fact.variants[1:])})
    gapped = GovernedFactCatalogue(facts={**catalogue.facts, gapped_fact.fact_id: gapped_fact})

    failures = retired_fact_provider_closure_failures(
        gapped,
        source_refs=load_shared_catalogues(_registry_root()).sources,
    )

    assert any("has a gap in its source-grounded temporal coverage" in failure for failure in failures)


def test_canonical_compiler_validator_reports_a_missing_migrated_fact() -> None:
    catalogues = _compiler_catalogues()
    missing = GovernedFactCatalogue(
        facts={
            fact_id: fact
            for fact_id, fact in catalogues.facts.facts.items()
            if fact_id != "liva-art-161:recargo-rate-general"
        }
    )
    malformed_catalogues = catalogues.model_copy(update={"facts": missing})

    expected = "retired-provider fact 'liva-art-161:recargo-rate-general' is not authored"
    with pytest.raises(RegistryValidationError, match=expected):
        RegistryValidator(malformed_catalogues, source_root=bundled_path()).validate_registry(())


def test_real_resolution_tracks_known_legal_change_boundaries() -> None:
    """Inside the supported filing years, each authored legal change is its own variant."""
    envelope = committed_supported_filing_years().date_envelope()

    def changes_inside_the_envelope(fact_id: str) -> list[date]:
        return sorted(
            variant.valid_from
            for variant in _catalogue().facts[fact_id].variants
            if variant.valid_from is not None and envelope.floor < variant.valid_from <= envelope.horizon
        )

    def assert_each_change_is_its_own_variant(fact_id: str) -> list[date]:
        changes = changes_inside_the_envelope(fact_id)
        assert changes, f"{fact_id} authors no legal change inside the supported filing years"
        for change in changes:
            assert (
                _resolve_scalar(fact_id, change - timedelta(days=1)).variant_id
                != _resolve_scalar(fact_id, change).variant_id
            ), f"{fact_id} does not change variant on {change}"
        return changes

    assert_each_change_is_its_own_variant("lirpf-art-101:retencion-administrador-reducida")
    assert_each_change_is_its_own_variant("rirpf-art-95:retencion-actividades-profesionales-general")
    exclusion = "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur"
    latest_change = assert_each_change_is_its_own_variant(exclusion)[-1]
    assert _resolve_scalar(exclusion, latest_change - timedelta(days=1)).payload.value == Decimal("250000")
    assert _resolve_scalar(exclusion, latest_change).payload.value == Decimal("150000")
    assert _resolve_entities(
        "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario", envelope.floor
    ).payload.entities == frozenset({"subvencion_capital", "indemnizacion"})
    assert _resolve_entities(
        "rd-439-2007-art-109:conceptos-ingreso-excluidos-base-agraria", envelope.floor
    ).payload.entities == frozenset({"subvencion_corriente", "subvencion_capital", "indemnizacion"})


def test_real_resolution_below_the_floor_reads_the_authored_variant_as_a_backward_projection() -> None:
    """A standing rate reaches below the floor and before its first window; it never claims grade there."""
    rate = "liva-art-161:recargo-rate-general"
    floor = committed_supported_filing_years().date_envelope().floor
    starts = sorted(
        variant.valid_from for variant in _catalogue().facts[rate].variants if variant.valid_from is not None
    )
    below_floor_start = max(start for start in starts if start < floor)

    inside_a_window = _resolve_scalar(rate, below_floor_start)
    assert inside_a_window.variant_id.endswith(below_floor_start.isoformat())
    assert inside_a_window.published_on_date
    assert inside_a_window.projection_direction is TemporalProjectionDirection.BACKWARD
    assert inside_a_window.projected_from_date == floor

    before_every_window = _resolve_scalar(rate, starts[0] - timedelta(days=1))
    assert before_every_window.variant_id.endswith(starts[0].isoformat())
    assert not before_every_window.published_on_date
    assert before_every_window.projection_direction is TemporalProjectionDirection.BACKWARD
    assert before_every_window.projected_from_date == starts[0]

    # A threshold declares no standing rate, so the floor stays a refusal for it.
    with pytest.raises(RegistryValidationError, match="falls outside the supported filing years"):
        _resolve_scalar("lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur", floor - timedelta(days=1))


def test_the_gate_applies_only_to_a_registry_that_enrolls_fact_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The obligation exists where the migration happened: in a registry enrolling governed-fact providers."""
    empty = GovernedFactCatalogue(facts={})

    enrolled_failures = retired_fact_provider_closure_failures(empty, source_refs={})
    monkeypatch.setattr(fact_providers, "FACT_PROVIDER_REGISTRATIONS", ())
    unenrolled_failures = retired_fact_provider_closure_failures(empty, source_refs={})

    assert "retired-provider fact 'liva-art-161:recargo-rate-general' is not authored" in enrolled_failures
    assert unenrolled_failures == ()


_STAGED_MODELO = "210"
#: An edition of the modelo's delta chain; staging resolves it into the complete edition it stands for.
_STAGED_REVISION = str(authored_revisions(_STAGED_MODELO)[-2].id)
_REMOVED_FACT_ID = "lirpf-art-101:retencion-administrador-general"
_REMOVED_FACT_FILE = "0001-lirpf-art-101-retencion-administrador-general.toml"


def _staged_bundled_copy(work: Path) -> Path:
    """Stage a copy of the bundled registry's shared authority plus one modelo, export tree included."""
    source_root = _registry_root()
    candidate_root = work / "registry" / "aeat"
    stage_generated_export_candidate(
        source_root,
        candidate_root,
        modelo=_STAGED_MODELO,
        revision=_STAGED_REVISION,
        supporting_modelos=supporting_modelos(_STAGED_MODELO),
    )
    shutil.copytree(
        source_root / "modelos" / _STAGED_MODELO / "revisions" / _STAGED_REVISION / "export",
        candidate_root / "modelos" / _STAGED_MODELO / "revisions" / _STAGED_REVISION / "export",
    )
    return candidate_root


def test_a_copy_of_the_bundled_tree_compiles_with_its_migrated_facts(tmp_path: Path) -> None:
    candidate_root = _staged_bundled_copy(tmp_path)

    authority = compile_validated_authority(candidate_root, bundled_path())

    assert _REMOVED_FACT_ID in authority.catalogues.facts.facts


def test_a_copy_of_the_bundled_tree_missing_one_migrated_fact_is_refused_by_name(tmp_path: Path) -> None:
    candidate_root = _staged_bundled_copy(tmp_path)
    (candidate_root / "facts" / _REMOVED_FACT_FILE).unlink()

    with pytest.raises(RegistryValidationError, match=f"retired-provider fact '{_REMOVED_FACT_ID}' is not authored"):
        compile_validated_authority(candidate_root, bundled_path())
