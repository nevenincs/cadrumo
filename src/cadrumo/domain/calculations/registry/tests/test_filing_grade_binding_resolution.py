"""Filing-grade binding selectors, route enrollment, and provenance gates.

This module deliberately derives its corpus from the validated bundled authority:
the test never maintains a hand-written modelo/revision inventory.  Every
revision declared at the FILING grade is selected again through the same
grade-constrained snapshot boundary the runtime uses.

An ENROLLED source must have a live calculation-route resolver.  A DEFERRED
source is not treated as resolved: it must have exactly one source-connectivity
census owner at the same modelo, revision, filing-year, and period coordinate,
with a bounded follow-up.  The existing source-casilla plan owns promotion of
those rows; this gate only prevents their authority from becoming invisible.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from .....application.aggregation import BindingSourceDisposition
from .....application.filing import _binding_provenance
from .....application.modelo import (
    CALCULATION_ROUTE_ENROLLED_SOURCES,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
    assert_no_novel_source_kinds,
)
from .....application.registry import (
    SourceConnectivityCensusEntry,
    SourceConnectivityCensusManifest,
    load_source_connectivity_census,
)
from .....core import BindingSourceKind, RegistryAuthorityGrade
from .....domain.filing import ModeloBuilderError
from .. import DataBindingDefinition, ModeloRevision, PeriodSelector, selector_model_for_source
from .._authority import bundled_authority
from .._bindings import validate_binding_selector_shape

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@dataclass(frozen=True, slots=True)
class _FilingGradeRevision:
    modelo_id: str
    revision_id: str
    filing_year: int
    period: str
    revision: ModeloRevision


@dataclass(frozen=True, slots=True)
class _FilingGradeBinding:
    modelo_id: str
    revision_id: str
    filing_year: int
    period: str
    binding: DataBindingDefinition


def _representative_scope(period_selector: PeriodSelector) -> tuple[int, str]:
    """Return one filing coordinate covered by a revision's period selector."""
    filing_year = period_selector.years[0] if period_selector.years else period_selector.year_from
    assert filing_year is not None
    return int(filing_year), period_selector.periods[0]


def _filing_grade_revisions() -> tuple[_FilingGradeRevision, ...]:
    """Select every filing-grade revision through the validated authority."""
    authority = bundled_authority()
    records: list[_FilingGradeRevision] = []
    for modelo in authority.modelos:
        for declared_revision in modelo.revisions.values():
            if declared_revision.effective_authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            filing_year, period = _representative_scope(declared_revision.period_selector)
            snapshot = authority.snapshot(
                str(modelo.id),
                filing_year=filing_year,
                period=period,
                grade=RegistryAuthorityGrade.FILING,
            )
            assert snapshot.revision.id == declared_revision.id
            records.append(
                _FilingGradeRevision(
                    modelo_id=str(modelo.id),
                    revision_id=str(snapshot.revision.id),
                    filing_year=filing_year,
                    period=period,
                    revision=snapshot.revision,
                ),
            )
    return tuple(records)


def _filing_grade_bindings() -> tuple[_FilingGradeBinding, ...]:
    """Flatten the live filing corpus without declaring a separate inventory."""
    return tuple(
        _FilingGradeBinding(
            modelo_id=record.modelo_id,
            revision_id=record.revision_id,
            filing_year=record.filing_year,
            period=record.period,
            binding=binding,
        )
        for record in _filing_grade_revisions()
        for binding in record.revision.bindings
    )


def _matching_census_entries(
    record: _FilingGradeBinding,
    manifest: SourceConnectivityCensusManifest,
) -> tuple[SourceConnectivityCensusEntry, ...]:
    """Find exact census ownership without recreating the census authority."""
    return tuple(
        entry
        for entry in manifest.entries
        if any(
            candidate.kind == "binding_source"
            and str(candidate.modelo_id) == record.modelo_id
            and str(candidate.revision_id) == record.revision_id
            and candidate.filing_year == record.filing_year
            and candidate.period_token == record.period
            and candidate.source_kind is record.binding.source
            for candidate in entry.registry_destination_candidates
        )
    )


def _source_route_violations(
    records: tuple[_FilingGradeBinding, ...],
    manifest: SourceConnectivityCensusManifest,
) -> list[str]:
    """Report binding sources absent from live enrollment or bounded ownership."""
    violations: list[str] = []
    for record in records:
        source = record.binding.source
        disposition = CALCULATION_ROUTE_SOURCE_DISPOSITIONS.get(source)
        identity = f"{record.modelo_id}/{record.revision_id}/{record.binding.id}/{source.value}"
        if disposition is BindingSourceDisposition.ENROLLED:
            if source not in CALCULATION_ROUTE_ENROLLED_SOURCES:
                violations.append(f"{identity}: enrolled disposition has no route resolver")
            continue
        if disposition is BindingSourceDisposition.DEFERRED:
            owners = _matching_census_entries(record, manifest)
            if len(owners) != 1:
                violations.append(f"{identity}: deferred source lacks one exact census owner")
                continue
            owner = owners[0]
            if owner.bounded_follow_up is None or owner.follow_up_owner() is None:
                violations.append(f"{identity}: deferred source lacks bounded accountable follow-up")
            continue
        rendered = "absent" if disposition is None else disposition.value
        violations.append(f"{identity}: unsupported route disposition {rendered}")
    return violations


def test_every_filing_grade_binding_has_a_validated_selector_and_calculation_boundary() -> None:
    """Every filing-grade binding reaches its typed selector and live source guard."""
    revisions = _filing_grade_revisions()
    records = _filing_grade_bindings()

    assert revisions, "validated authority yielded no filing-grade revisions"
    assert records, "filing-grade revision corpus yielded no bindings"
    violations: list[str] = []
    for record in records:
        if selector_model_for_source(record.binding.source) is None:
            violations.append(f"{record.modelo_id}/{record.revision_id}/{record.binding.id}: no selector model")
        diagnostics = validate_binding_selector_shape(record.binding)
        if diagnostics:
            violations.append(
                f"{record.modelo_id}/{record.revision_id}/{record.binding.id}: " + "; ".join(diagnostics),
            )
    for record in revisions:
        assert_no_novel_source_kinds(record.revision)

    assert not violations, "filing-grade selector validation failed:\n" + "\n".join(violations)


def test_selector_gate_bites_when_a_live_filing_binding_is_routed_to_the_wrong_family() -> None:
    """Selector dispatch cannot be weakened into a source-agnostic pass-through."""
    records = _filing_grade_bindings()
    target = next(
        record.binding for record in records if record.binding.source is BindingSourceKind.LEDGER_IVA_AGGREGATION
    )
    mutated = target.model_copy(update={"source": BindingSourceKind.MANUAL_INPUT})

    assert validate_binding_selector_shape(mutated)


def test_every_filing_grade_binding_source_is_enrolled_or_exactly_census_owned() -> None:
    """Deferred sources remain explicit owned work, never implied enrollment."""
    violations = _source_route_violations(_filing_grade_bindings(), load_source_connectivity_census())

    assert not violations, "filing-grade binding route gaps:\n" + "\n".join(violations)


def test_m193_2024_deferred_binding_loses_its_owner_when_its_exact_census_destination_is_removed() -> None:
    """The historical M193 deferred row is guarded independently of M193 2025+."""
    records = _filing_grade_bindings()
    target = next(
        record
        for record in records
        if record.modelo_id == "193"
        and record.revision_id == "2024"
        and record.binding.source.value == "gasto193_contributor"
    )
    manifest = load_source_connectivity_census()
    entry = next(
        candidate_entry
        for candidate_entry in manifest.entries
        if _matching_census_entries(target, manifest) == (candidate_entry,)
    )
    without_target = entry.model_copy(
        update={
            "registry_destination_candidates": tuple(
                candidate
                for candidate in entry.registry_destination_candidates
                if not (
                    candidate.kind == "binding_source"
                    and str(candidate.modelo_id) == target.modelo_id
                    and str(candidate.revision_id) == target.revision_id
                    and candidate.filing_year == target.filing_year
                    and candidate.period_token == target.period
                    and candidate.source_kind is target.binding.source
                )
            ),
        },
    )
    mutated = manifest.model_copy(
        update={"entries": tuple(without_target if item is entry else item for item in manifest.entries)},
    )

    violations = _source_route_violations(records, mutated)

    assert any("193/2024/" in violation and "lacks one exact census owner" in violation for violation in violations)


def test_filing_binding_provenance_is_copied_verbatim_from_validated_authority() -> None:
    """Filing values inherit non-empty typed provenance from each binding declaration."""
    records = _filing_grade_bindings()
    for record in records:
        source, legal_refs, source_refs = _binding_provenance(record.binding)
        assert source is record.binding.source
        assert legal_refs == record.binding.legal_refs
        assert source_refs == record.binding.source_refs
        assert legal_refs
        assert source_refs

    ungrounded = records[0].binding.model_copy(update={"legal_refs": ()})
    with pytest.raises(ModeloBuilderError) as raised:
        _binding_provenance(ungrounded)
    assert raised.value.translated_message == "application.filing.build_draft.errors.binding_provenance_missing"
