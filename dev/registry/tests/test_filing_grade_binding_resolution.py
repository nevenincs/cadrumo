"""Filing-grade binding selectors, route enrollment, and provenance gates.

This module deliberately derives its corpus from the validated bundled authority:
the test never maintains a hand-written modelo/revision inventory.  Every
revision declared at the FILING grade is selected again through the same
grade-constrained snapshot boundary the runtime uses.

Every filing-grade source must have a live calculation-route resolver. Missing
routes are reported directly from the current authority, without a development
classification or ownership catalogue.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cadrumo.application.filing.draft_construction import binding_provenance
from cadrumo.application.modelo.calculation_actions import assert_no_novel_source_kinds
from cadrumo.application.modelo.calculation_route import CALCULATION_ROUTE_ENROLLED_SOURCES
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.filing.errors import ModeloBuilderError
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.binding_provider_registration import RouteOwnership, provider_model_for, registration_for
from cadrumo.domain.calculations.registry.bindings import validate_binding_selector_shape
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

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
    binding: BindingDefinition


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


def _source_route_violations(records: tuple[_FilingGradeBinding, ...]) -> list[str]:
    """Report filing-grade binding sources absent from live enrollment."""
    violations: list[str] = []
    for record in records:
        source = record.binding.source
        identity = f"{record.modelo_id}/{record.revision_id}/{record.binding.id}/{source.value}"
        if (
            isinstance(registration_for(source).route, RouteOwnership)
            and source not in CALCULATION_ROUTE_ENROLLED_SOURCES
        ):
            violations.append(f"{identity}: source has no route resolver")
    return violations


def test_every_filing_grade_binding_has_a_validated_selector_and_calculation_boundary() -> None:
    """Every filing-grade binding reaches its typed selector and live source guard."""
    revisions = _filing_grade_revisions()
    records = _filing_grade_bindings()

    assert revisions, "validated authority yielded no filing-grade revisions"
    assert records, "filing-grade revision corpus yielded no bindings"
    violations: list[str] = []
    for record in records:
        provider_model = provider_model_for(record.binding.source)
        if not isinstance(record.binding.provider, provider_model):
            violations.append(f"{record.modelo_id}/{record.revision_id}/{record.binding.id}: provider model mismatch")
        diagnostics = validate_binding_selector_shape(record.binding)
        if diagnostics:
            violations.append(
                f"{record.modelo_id}/{record.revision_id}/{record.binding.id}: " + "; ".join(diagnostics),
            )
    for record in revisions:
        assert_no_novel_source_kinds(record.revision)

    assert not violations, "filing-grade selector validation failed:\n" + "\n".join(violations)


def test_selector_gate_bites_when_a_live_filing_binding_is_routed_to_the_wrong_family() -> None:
    """The provider discriminator cannot be changed without changing its member."""
    records = _filing_grade_bindings()
    target = next(
        record.binding for record in records if record.binding.source is BindingSourceKind.LEDGER_IVA_AGGREGATION
    )
    mutated_provider = target.provider.model_copy(update={"kind": BindingSourceKind.MANUAL_INPUT})
    mutated = target.model_copy(update={"provider": mutated_provider})

    assert not isinstance(mutated.provider, provider_model_for(mutated.source))


def test_every_filing_grade_binding_source_is_enrolled() -> None:
    """Every filing-grade source reaches an executable calculation route."""
    violations = _source_route_violations(_filing_grade_bindings())

    assert not violations, "filing-grade binding route gaps:\n" + "\n".join(violations)


def test_filing_binding_provenance_is_copied_verbatim_from_validated_authority() -> None:
    """Filing values inherit non-empty typed provenance from each binding declaration."""
    records = _filing_grade_bindings()
    for record in records:
        source, legal_refs, source_refs = binding_provenance(record.binding)
        assert source is record.binding.source
        assert legal_refs == record.binding.legal_refs
        assert source_refs == record.binding.source_refs
        assert legal_refs
        assert source_refs

    ungrounded = records[0].binding.model_copy(update={"legal_refs": ()})
    with pytest.raises(ModeloBuilderError) as raised:
        binding_provenance(ungrounded)
    assert raised.value.translated_message == "application.filing.build_draft.errors.binding_provenance_missing"
