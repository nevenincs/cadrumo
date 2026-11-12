"""Registry build refuses a pension-contribution placement it cannot ground or that contradicts its edition.

Each refusal is exercised on one isolated defect: a copy of a compiled Modelo 100
revision with exactly one placement changed in memory. The compiled corpus is the
passing control, so a rule that refused everything, or nothing, fails here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.prevision_social_contribution_bindings import (
    prevision_social_contribution_binding_by_casilla,
)
from cadrumo.domain.calculations.registry.prevision_social_placement import PrevisionSocialPlacement
from cadrumo.domain.calculations.registry.schema_base import SourceCitation

from ..validate_evidence import EvidenceValidator
from ..validate_prevision_social_placements import validate_prevision_social_placement_section

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


def _placing_revisions(authority: ValidatedRegistryAuthority) -> list[ModeloRevision]:
    (modelo,) = [modelo for modelo in authority.modelos if modelo.id == "100"]
    revisions = sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from)
    return [revision for revision in revisions if revision.prevision_social_placements]


def _failures(authority: ValidatedRegistryAuthority, revision: ModeloRevision) -> list[str]:
    sources = authority.catalogues.sources
    evidence = EvidenceValidator(legal_refs=authority.catalogues.legal, source_refs=sources, source_root=bundled_path())
    return validate_prevision_social_placement_section(
        prefix="modelo", revision=revision, source_refs=sources, evidence=evidence
    )


def _row(revision: ModeloRevision, row_id: str) -> PrevisionSocialPlacement:
    (row,) = [row for row in revision.prevision_social_placements if row.id == row_id]
    return row


def _with_rows(revision: ModeloRevision, *rows: PrevisionSocialPlacement) -> ModeloRevision:
    return revision.model_copy(update={"prevision_social_placements": (*revision.prevision_social_placements, *rows)})


def _replacing(revision: ModeloRevision, row: PrevisionSocialPlacement) -> ModeloRevision:
    kept = tuple(item for item in revision.prevision_social_placements if item.id != row.id)
    return revision.model_copy(update={"prevision_social_placements": (*kept, row)})


def test_every_compiled_revision_passes_and_only_modelo_100_places(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    """The passing control: each Modelo 100 placing edition grounds every row; no other modelo declares one."""
    authority = _worker_compiled_authority
    placing = _placing_revisions(authority)
    assert placing
    for revision in placing:
        assert _failures(authority, revision) == [], revision.id
    for modelo in authority.modelos:
        if modelo.id != "100":
            assert all(not revision.prevision_social_placements for revision in modelo.revisions.values()), modelo.id


def test_a_casilla_outside_the_edition_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    revision = _placing_revisions(_worker_compiled_authority)[0]
    stray = _row(revision, "a-01").model_copy(update={"casilla_id": "9999"})

    failures = _failures(_worker_compiled_authority, _replacing(revision, stray))

    assert failures == [
        f"modelo: prevision social placement 'a-01' places casilla '9999', which revision {revision.id!r} "
        "does not declare"
    ]


def test_a_box_bound_to_no_family_binding_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    revision = _placing_revisions(_worker_compiled_authority)[0]
    bound = {str(casilla_id) for casilla_id in prevision_social_contribution_binding_by_casilla(revision)}
    unbound = next(str(casilla.id) for casilla in revision.casillas if str(casilla.id) not in bound)
    stray = _row(revision, "a-01").model_copy(update={"casilla_id": unbound})

    failures = _failures(_worker_compiled_authority, _replacing(revision, stray))

    assert failures == [
        f"modelo: casilla {unbound!r} is placed by a pension contribution row but bound to no single family binding"
    ]


def test_a_placing_revision_without_the_family_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    revision = _placing_revisions(_worker_compiled_authority)[0]
    unbound = revision.model_copy(
        update={
            "bindings": tuple(
                binding
                for binding in revision.bindings
                if binding.source is not BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION
            )
        }
    )

    failures = _failures(_worker_compiled_authority, unbound)

    assert failures == [f"modelo: revision {revision.id!r} places pension contributions but declares no family binding"]


def test_a_key_declared_twice_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    revision = _placing_revisions(_worker_compiled_authority)[0]

    failures = _failures(_worker_compiled_authority, _with_rows(revision, _row(revision, "c-01")))

    assert failures == ["modelo: prevision social placement key 'c-01' is declared 2 times"]


def test_a_split_pair_missing_one_answer_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    revision = _placing_revisions(_worker_compiled_authority)[0]
    halved = revision.model_copy(
        update={
            "prevision_social_placements": tuple(
                row for row in revision.prevision_social_placements if row.id != "j-01-employer-same-plan"
            )
        }
    )

    failures = _failures(_worker_compiled_authority, halved)

    assert failures == [
        "modelo: prevision social placement pair 'j-01' must declare both same-plan answers and no unsplit row"
    ]


def test_a_placed_row_without_the_casilla_citation_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    row = _row(_placing_revisions(_worker_compiled_authority)[0], "a-01").model_dump()
    del row["casilla_citation"]

    with pytest.raises(ValidationError, match="without quoting the Modelo 100 text"):
        PrevisionSocialPlacement.model_validate(row)


def test_a_row_without_the_design_citation_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    row = _row(_placing_revisions(_worker_compiled_authority)[0], "a-01").model_dump()
    del row["design_citation"]

    with pytest.raises(ValidationError, match="design_citation"):
        PrevisionSocialPlacement.model_validate(row)


def test_a_quotation_its_source_does_not_contain_is_refused(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> None:
    revision = _placing_revisions(_worker_compiled_authority)[0]
    original = _row(revision, "a-01")
    assert original.casilla_citation is not None
    misquoted = original.model_copy(
        update={
            "casilla_citation": SourceCitation(
                source_ref=original.casilla_citation.source_ref,
                required_text=("[0465][Aportaciones del promotor]",),
            )
        }
    )

    (failure,) = _failures(_worker_compiled_authority, _replacing(revision, misquoted))

    assert "prevision social placement a-01 casilla_citation source citation" in failure
    assert "missing text" in failure


def test_a_refusal_the_row_cannot_own_is_refused(_worker_compiled_authority: ValidatedRegistryAuthority) -> None:
    row = _row(_placing_revisions(_worker_compiled_authority)[0], "b").model_dump()

    with pytest.raises(ValidationError, match="depends on the record or the edition"):
        PrevisionSocialPlacement.model_validate({**row, "refusal": "design_not_bundled"})
