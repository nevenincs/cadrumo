"""The binding overlay of a real calculation, run end to end through ``resolve_calculation_binding_channels``.

The registry revision, the profile resolver and the overlay are the published
ones; only the operator's values are chosen here, so each expected value is the
one the test itself supplied.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.export_layout_format import ExportLayoutFormat
from ....core.hashing import content_hash_hex
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.export_xml_dictionary import xml_dictionary_entries
from ....domain.calculations.registry.filing_bound_reach import official_export_casilla_ids, snapshot_filing_bound_reach
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.modelos.calculation_revision_sources import CalculationSourceRef
from ....domain.modelos.source_disagreement import (
    DisagreementDecimalValue,
    DisagreementEnumValue,
    SourceDisagreementRole,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...aggregation import source_profile
from ...aggregation.source_resolution_operations import PrecedenceOverlay, PrecedenceTier
from .. import calculation_resolution
from ..calculation_resolution import (
    PRECEDENCE_TIER_DIVERGENCE_REASON,
    ResolvedCalculationChannels,
    precedence_tier_issue,
    resolve_calculation_binding_channels,
)
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "10000000-0000-4000-8000-000000000591"
_PERIOD = "0A"
_CCAA_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_CLOCK = datetime(1980, 5, 21, 10, 0, 0, tzinfo=UTC)


def _latest_snapshot_declaring_the_ccaa_binding() -> RegistrySnapshot:
    """The newest supported Modelo 100 revision whose profile tier carries the residence CCAA."""
    support = published_supported_filing_years()
    assert support is not None
    for year in sorted(support.years, reverse=True):
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        if any(binding.id == _CCAA_BINDING for binding in snapshot.revision.bindings):
            return snapshot
    raise AssertionError("no supported Modelo 100 revision declares the residence CCAA binding")


def _work_unit(snapshot: RegistrySnapshot) -> WorkUnit:
    year = snapshot.snapshot_ref.modelo_year
    period = Period.from_year_and_code(year, _PERIOD)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID, modelo="100", filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_PROFILE_ID,
        modelo="100",
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="precedence-screen",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _profile(ccaa: str, operation: PinnedAuthorityOperation) -> ModeloWorkProfile:
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="tax_residence.ccaa", value=ccaa),
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def _resolve(
    operation: PinnedAuthorityOperation, *, profile_ccaa: str, caller_enums: Mapping[BindingId, str]
) -> ResolvedCalculationChannels:
    snapshot = _latest_snapshot_declaring_the_ccaa_binding()
    return resolve_calculation_binding_channels(
        work_unit=_work_unit(snapshot),
        snapshot=snapshot,
        casilla_inputs={},
        caller_binding_values={},
        caller_enum_binding_values=caller_enums,
        backend_binding_values={},
        borrador_snapshot_id=None,
        borrador_snapshot_repository=None,
        operation=operation,
        profile=_profile(profile_ccaa, operation),
    )


def test_the_profile_value_reaches_the_calculation_and_nothing_diverges(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    channels = _resolve(authority_operation, profile_ccaa="madrid", caller_enums={})

    assert channels.enum_bindings[_CCAA_BINDING] == "madrid"
    assert channels.precedence_diagnostics == ()


def test_an_operator_value_equal_to_the_profiles_is_silent(authority_operation: PinnedAuthorityOperation) -> None:
    channels = _resolve(authority_operation, profile_ccaa="madrid", caller_enums={_CCAA_BINDING: "madrid"})

    assert channels.enum_bindings[_CCAA_BINDING] == "madrid"
    assert channels.precedence_diagnostics == ()


def test_an_operator_value_over_a_different_profile_value_is_used_and_blocks_with_both_values(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    channels = _resolve(authority_operation, profile_ccaa="madrid", caller_enums={_CCAA_BINDING: "cataluna"})
    snapshot = _latest_snapshot_declaring_the_ccaa_binding()
    reached = snapshot_filing_bound_reach(snapshot, operation=authority_operation).binding_reach(_CCAA_BINDING)

    assert channels.enum_bindings[_CCAA_BINDING] == "cataluna"
    (diagnostic,) = channels.precedence_diagnostics
    # The residence CCAA selects the autonomic scale, whose boxes the Modelo 100 XML dictionary files.
    assert reached
    assert diagnostic.reason == PRECEDENCE_TIER_DIVERGENCE_REASON
    assert precedence_tier_issue(diagnostic) is not None
    assert diagnostic.binding_id == _CCAA_BINDING
    assert "madrid" not in diagnostic.message
    assert "cataluna" not in diagnostic.message
    fact = diagnostic.disagreement
    assert fact is not None
    assert fact.selected_role is SourceDisagreementRole.CALLER
    assert fact.reached_casillas == reached
    assert [(source.role, source.value) for source in fact.sources] == [
        (SourceDisagreementRole.PROFILE, DisagreementEnumValue.model_validate({"token": "madrid"})),
        (SourceDisagreementRole.CALLER, DisagreementEnumValue.model_validate({"token": "cataluna"})),
    ]
    assert fact.sources[0].source_family == "profile"
    assert fact.sources[0].source_ref == f"profile:{_PROFILE_ID}:binding:{_CCAA_BINDING}"
    assert fact.sources[1].source_family == "operator_input"
    assert fact.sources[1].source_ref == f"operator_input:binding:{_CCAA_BINDING}"
    assert fact.sources[1].resolver_id == "calculate_caller_bindings"


def test_a_published_modelo_303_revision_has_filing_bound_figures(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The screen blocks somewhere: the newest supported Modelo 303 revision carries exported, bound boxes."""
    support = published_supported_filing_years()
    assert support is not None
    snapshot = published_snapshot("303", filing_year=max(support.years), period="1T")
    revision = snapshot.revision
    reach = snapshot_filing_bound_reach(snapshot, operation=authority_operation)
    exported_bound = {
        casilla.binding for casilla in revision.casillas if casilla.export_refs and casilla.binding is not None
    }

    assert revision.authority_grade is RegistryAuthorityGrade.FILING
    assert exported_bound
    assert exported_bound <= set(reach.bindings)


def test_the_published_modelo_100_dictionary_makes_its_boxes_exported_without_export_refs(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 100 declares no ``export_refs``; the boxes its published XML dictionary emits are what it files."""
    snapshot = _latest_snapshot_declaring_the_ccaa_binding()
    revision = snapshot.revision
    (layout,) = (
        layout
        for layout in derive_export_layouts_from_bindings(revision)
        if layout.format is ExportLayoutFormat.XML_DICTIONARY
    )
    assert layout.dictionary_source_ref is not None
    payloads = {layout.dictionary_source_ref: authority_operation.source_evidence(layout.dictionary_source_ref).payload}
    declared = {casilla.id for casilla in revision.casillas}
    emitted = {
        entry.casilla_id
        for entry in xml_dictionary_entries(
            layout, sources=snapshot.sources, source_payloads=payloads, casillas=revision.casillas
        )
        if entry.casilla_id is not None and entry.casilla_id in declared
    }
    exported = official_export_casilla_ids(revision, sources=snapshot.sources, source_payloads=payloads)
    reach = snapshot_filing_bound_reach(snapshot, operation=authority_operation)

    assert not any(casilla.export_refs for casilla in revision.casillas)
    assert emitted
    assert emitted <= exported
    assert _CCAA_BINDING in reach.bindings
    assert set(reach.binding_reach(_CCAA_BINDING)) <= exported


def _caller_over_profile_is_reported(operation: PinnedAuthorityOperation) -> bool:
    """The check the two defects below must fail: an operator CCAA over a different profile CCAA is reported."""
    channels = _resolve(operation, profile_ccaa="madrid", caller_enums={_CCAA_BINDING: "cataluna"})
    return any(diagnostic.binding_id == _CCAA_BINDING for diagnostic in channels.precedence_diagnostics)


def test_the_check_fails_when_the_lower_tier_leaves_out_the_keys_a_higher_tier_supplies(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    """The suppression the screen replaced: a profile resolver told which keys the caller owns hides the contest."""
    assert _caller_over_profile_is_reported(authority_operation)
    real_resolver = source_profile.ProfileSourceResolver

    def excluding_resolver(**kwargs: Any) -> source_profile.ProfileSourceResolver:
        return real_resolver(caller_binding_ids={_CCAA_BINDING}, **kwargs)

    monkeypatch.setattr(source_profile, "ProfileSourceResolver", excluding_resolver)

    assert not _caller_over_profile_is_reported(authority_operation)


def test_the_check_fails_when_the_overlay_replaces_values_without_comparing_them(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    """The silent overwrite the screen replaced: a plain later-wins update that reports nothing."""
    assert _caller_over_profile_is_reported(authority_operation)
    real_overlay = calculation_resolution.merge_source_resolutions_by_precedence

    def bare_update(tiers: Sequence[PrecedenceTier]) -> PrecedenceOverlay:
        overlay = real_overlay(tiers)
        return PrecedenceOverlay(
            resolution=overlay.resolution, divergences=(), selected_binding_roles=overlay.selected_binding_roles
        )

    monkeypatch.setattr(calculation_resolution, "merge_source_resolutions_by_precedence", bare_update)

    assert not _caller_over_profile_is_reported(authority_operation)


def test_a_backend_value_is_named_by_its_declared_source_and_located_by_its_evidence_fingerprints(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The backend entry names the binding, never a source object, and digests the fingerprints behind it."""
    snapshot = _latest_snapshot_declaring_the_ccaa_binding()
    reach = snapshot_filing_bound_reach(snapshot, operation=authority_operation)
    binding = next(
        binding
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.PREVIOUS_FILING and reach.binding_reach(binding.id)
    )
    fingerprints = ("b" * 64, "a" * 64)
    provenance = tuple(
        CalculationSourceRef(
            resolver_id="previous_filing",
            resolved_binding_source=BindingSourceKind.PREVIOUS_FILING,
            contributor_source_kind="previous_filing",
            contributor_binding_source=BindingSourceKind.PREVIOUS_FILING,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"perceptor:{index}",
            parent_source_ref=None,
            fingerprint=fingerprint,
        )
        for index, fingerprint in enumerate(fingerprints)
    )

    channels = resolve_calculation_binding_channels(
        work_unit=_work_unit(snapshot),
        snapshot=snapshot,
        casilla_inputs={},
        caller_binding_values={binding.id: Decimal("12.500")},
        caller_enum_binding_values={},
        backend_binding_values={binding.id: Decimal("10.000")},
        borrador_snapshot_id=None,
        borrador_snapshot_repository=None,
        operation=authority_operation,
        profile=_profile("madrid", authority_operation),
        backend_source_provenance=provenance,
    )

    (diagnostic,) = (item for item in channels.precedence_diagnostics if item.binding_id == binding.id)
    assert diagnostic.disagreement is not None
    backend, caller = diagnostic.disagreement.sources
    assert backend.role is SourceDisagreementRole.BACKEND
    assert backend.source_ref == f"previous_filing:binding:{binding.id}"
    assert backend.evidence_ref == f"sha256:{content_hash_hex(sorted(fingerprints))}"
    assert all("perceptor" not in (entry.source_ref or "") for entry in (backend, caller))
    assert caller.source_ref == f"operator_input:binding:{binding.id}"
    assert caller.value == DisagreementDecimalValue(amount="12.500")
