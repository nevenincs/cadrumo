"""A pre-floor generated target may be checked as static authority only."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.domain.calculations.registry.errors import (
    FilingYearOutsideSupportEnvelopeError,
    NoRevisionForPeriodError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, filing_year_envelope

from ...compiler.authority import compiled_bundled_authority
from ..cli import GeneratedTreeInvocation, prepare_generated_tree_invocation, render_candidate
from ..render_check import select_record_design_source
from ..tree_validation import ValidatedHistoricalStaticGeneratedExportTree, validate_generated_export_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Modelo 232's two editions: the early one lies wholly below the support floor, the late one follows it.
_EARLY, _LATE = authored_revisions("232")[:2]
_EARLY_REVISION = str(_EARLY.id)
_EARLY_EXERCISE = _EARLY.valid_from.year
_EARLY_SOURCE = f"aeat-dr-232-{_EARLY_EXERCISE}"
_LATE_SOURCE = f"aeat-dr-232-{_LATE.valid_from.year}"


def test_m232_historical_tree_has_static_inspection_and_no_filing_snapshot(tmp_path) -> None:
    authority = compiled_bundled_authority()
    prepared = prepare_generated_tree_invocation(
        GeneratedTreeInvocation("232", _EARLY_REVISION, _EARLY_SOURCE, _EARLY_EXERCISE, "0A"),
        tmp_path,
        authority=authority,
    )
    rendered = render_candidate(prepared)

    def validate(context):
        return validate_generated_export_tree(
            context=context,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )

    result = validate(prepared.validation)
    assert isinstance(result, ValidatedHistoricalStaticGeneratedExportTree)
    assert not hasattr(result, "snapshot")
    assert str(result.inspection.revision_id) == _EARLY_REVISION
    assert result.layout == rendered.layout
    assert result.provenance_manifest == rendered.provenance_manifest

    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        validate(replace(prepared.validation, historical_static_source_ref=None))
    with pytest.raises(RegistryValidationError, match="source differs from the exact selected official design"):
        validate(replace(prepared.validation, historical_static_source_ref=_LATE_SOURCE))
    with pytest.raises(RegistryValidationError, match="below the unchanged filing support floor"):
        validate(replace(prepared.validation, filing_year=filing_year_envelope().floor))
    with pytest.raises(NoRevisionForPeriodError, match="period"):
        validate(replace(prepared.validation, period="1T"))
    with pytest.raises(RegistryValidationError, match="selected authored revision"):
        validate(replace(prepared.validation, filing_year=_LATE.valid_from.year))


def test_historical_source_selection_refuses_two_applicable_official_designs() -> None:
    authority = compiled_bundled_authority()
    revision = authority.modelo("232").revisions[_EARLY_REVISION]
    sources = dict(authority.catalogues.sources)
    late_ref = next(ref for ref in sources if str(ref) == _LATE_SOURCE)
    sources[late_ref] = sources[late_ref].model_copy(
        update={"applies_from": _EARLY.valid_from, "applies_to": _EARLY.valid_to}
    )
    changed_revision = revision.model_copy(update={"source_refs": (*revision.source_refs, late_ref)})
    with pytest.raises(ValueError, match="exactly one record-design source"):
        select_record_design_source(
            changed_revision,
            sources,
            modelo="232",
            revision=_EARLY_REVISION,
            source_ref=None,
            filing_year=_EARLY_EXERCISE,
            period="0A",
        )
