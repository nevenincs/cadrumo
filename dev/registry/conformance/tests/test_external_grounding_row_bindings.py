"""A box a filing-grade property-row binding fills is engine-produced for the oracle.

Each let property's row is computed by the ``renta_inmueble`` resolver from the
property's records, so an oracle figure for a box such a row column targets is
checked against the engine exactly as a formula target is, although the casilla
is a row field rather than ``input_kind=computed``. Real behaviour: the bundled
Modelo 100 revisions and the bundled oracle corpus, folded by the production
audit; the refusal cases change one fact of the real revision each.
"""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.binding_grade_cap import BindingGradeCap
from cadrumo.domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_columns
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ...maintenance_support import load_bundled_external_oracle_inventory
from ..external_grounding import RegistryExternalGroundingAudit, build_external_grounding_audit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("governed_fact_scope")]

_MODELO = "100"


def _audit(modelo: ModeloDefinition) -> RegistryExternalGroundingAudit:
    return build_external_grounding_audit(
        (modelo,), inventory=load_bundled_external_oracle_inventory(), registry_validated=False
    )


def _row_boxes(revision: ModeloRevision) -> set[CasillaId]:
    return {provider.target_casilla_id for _binding, provider in renta_inmueble_columns(revision)}


def _grounded_row_boxes(modelo: ModeloDefinition) -> dict[str, set[CasillaId]]:
    """The row boxes the oracle corpus carries a figure for, by revision."""
    found: dict[str, set[CasillaId]] = {}
    for row in _audit(modelo).rows:
        boxes = _row_boxes(modelo.revisions[row.revision]) & set(row.oracle_evidence_casilla_ids)
        if boxes:
            found[str(row.revision)] = boxes
    return found


def _with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _any_grade_cap(authority: ValidatedRegistryAuthority) -> BindingGradeCap:
    return next(
        binding.grade_cap
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for binding in revision.bindings
        if binding.grade_cap is not None
    )


def _modelo(authority: ValidatedRegistryAuthority) -> ModeloDefinition:
    return next(modelo for modelo in authority.modelos if modelo.id == _MODELO)


def test_an_oracle_figure_for_a_property_row_box_is_engine_produced_and_enrolled(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    modelo = _modelo(registry_authority)
    grounded = _grounded_row_boxes(modelo)
    assert grounded, "no oracle carries a property-row box, so this proves nothing"

    findings = {
        (str(finding.revision), finding.casilla_id)
        for finding in _audit(modelo).findings
        if finding.kind in {"oracle_casilla_not_computed", "oracle_casilla_not_enrolled"}
    }
    assert not {(revision, box) for revision, boxes in grounded.items() for box in boxes} & findings


def test_a_grade_capped_row_column_is_not_engine_produced(registry_authority: ValidatedRegistryAuthority) -> None:
    modelo = _modelo(registry_authority)
    cap = _any_grade_cap(registry_authority)
    for revision_id, boxes in _grounded_row_boxes(modelo).items():
        revision = modelo.revisions[revision_id]
        capped = revision.model_copy(
            update={
                "bindings": tuple(
                    binding.model_copy(update={"grade_cap": cap})
                    if binding.id in {column.id for column, _provider in renta_inmueble_columns(revision)}
                    else binding
                    for binding in revision.bindings
                )
            }
        )

        refused = {
            finding.casilla_id
            for finding in _audit(_with_revision(modelo, capped)).findings
            if finding.kind == "oracle_casilla_not_computed" and str(finding.revision) == revision_id
        }

        assert boxes <= refused


def test_an_unenrolled_row_box_is_reported(registry_authority: ValidatedRegistryAuthority) -> None:
    modelo = _modelo(registry_authority)
    for revision_id, boxes in _grounded_row_boxes(modelo).items():
        revision = modelo.revisions[revision_id]
        unenrolled = revision.model_copy(
            update={
                "verification_expectations": tuple(
                    expectation.model_copy(
                        update={
                            "reconcile_when_present_casilla_ids": tuple(
                                box for box in expectation.reconcile_when_present_casilla_ids if box not in boxes
                            ),
                            "computed_casilla_ids": tuple(
                                box for box in expectation.computed_casilla_ids if box not in boxes
                            ),
                            "externally_grounded_casilla_ids": tuple(
                                box for box in expectation.externally_grounded_casilla_ids if box not in boxes
                            ),
                        }
                    )
                    for expectation in revision.verification_expectations
                )
            }
        )

        reported = {
            finding.casilla_id
            for finding in _audit(_with_revision(modelo, unenrolled)).findings
            if finding.kind == "oracle_casilla_not_enrolled" and str(finding.revision) == revision_id
        }

        assert boxes <= reported
