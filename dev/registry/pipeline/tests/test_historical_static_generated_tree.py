"""A pre-floor generated target may be checked as static authority only."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from cadrumo.domain.calculations.registry.errors import (
    FilingYearOutsideSupportEnvelopeError,
    NoRevisionForPeriodError,
    RegistryValidationError,
)

from ...compiler.authority import compiled_bundled_authority
from .._tree_validation import ValidatedHistoricalStaticGeneratedExportTree, validate_generated_export_tree
from ..cli import GeneratedTreeInvocation, _render_candidate, prepare_generated_tree_invocation
from ..render_check import _select_record_design_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_m232_historical_tree_has_static_inspection_and_no_filing_snapshot(tmp_path) -> None:
    authority = compiled_bundled_authority()
    prepared = prepare_generated_tree_invocation(
        GeneratedTreeInvocation("232", "2016-2017", "aeat-dr-232-2016", 2016, "0A"),
        tmp_path,
        authority=authority,
    )
    rendered = _render_candidate(prepared)

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
    assert str(result.inspection.revision_id) == "2016-2017"
    assert result.layout == rendered.layout
    assert result.provenance_manifest == rendered.provenance_manifest

    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        validate(replace(prepared.validation, historical_static_source_ref=None))
    with pytest.raises(RegistryValidationError, match="source differs from the exact selected official design"):
        validate(replace(prepared.validation, historical_static_source_ref="aeat-dr-232-2018"))
    with pytest.raises(RegistryValidationError, match="below the unchanged filing support floor"):
        validate(replace(prepared.validation, filing_year=2022))
    with pytest.raises(NoRevisionForPeriodError, match="period"):
        validate(replace(prepared.validation, period="1T"))
    with pytest.raises(RegistryValidationError, match="selected authored revision"):
        validate(replace(prepared.validation, filing_year=2018))


def test_historical_source_selection_refuses_two_applicable_official_designs() -> None:
    authority = compiled_bundled_authority()
    revision = authority.modelo("232").revisions["2016-2017"]
    sources = dict(authority.catalogues.sources)
    late_ref = next(ref for ref in sources if str(ref) == "aeat-dr-232-2018")
    sources[late_ref] = sources[late_ref].model_copy(
        update={"applies_from": date(2016, 1, 1), "applies_to": date(2017, 12, 31)}
    )
    changed_revision = revision.model_copy(update={"source_refs": (*revision.source_refs, late_ref)})
    with pytest.raises(ValueError, match="exactly one record-design source"):
        _select_record_design_source(
            changed_revision,
            sources,
            modelo="232",
            revision="2016-2017",
            source_ref=None,
            filing_year=2016,
            period="0A",
        )
