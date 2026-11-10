"""A persisted blocking calculation note refuses checking, exporting and recording; the check's own reasons are left to it.

The refusal is the application's, so every entrypoint meets it. It is worded
by the note's own catalogue sentence and names every blocking reason. Reasons
a check step adjudicates with its own evidence, such as an empty withholdings
detail the filer may attest, are not refused here, and a revision with no
blocking note passes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import get_args

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import validated_casilla_id
from ....core.config import override_settings
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_covering
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_sources import DISAGREEMENT_REASONS, CalculationSourceIssue
from ....domain.modelos.source_disagreement import (
    DisagreementDecimalValue,
    SourceDisagreementEntry,
    SourceDisagreementFact,
    SourceDisagreementRole,
)
from ..calculation_note_gate import (
    NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
    ModeloCalculationBlockedError,
    SourceDisagreementResolutions,
    blocking_calculation_issues,
    gate_refuses,
    require_no_blocking_calculation_notes,
)
from ..calculation_notes import (
    BLOCKING_REASONS,
    CALCULATION_NOTE_ATTENTION,
    CHECK_REFUSED_REASONS,
    EXPORT_REFUSED_REASONS,
    GATE_REFUSED_REASONS,
)
from ..work_form_findings import ModeloFormAttention

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT = "e" * 64
_CLOCK = datetime(1980, 4, 2, 9, 0, tzinfo=UTC)
_YEAR = filing_year_envelope().horizon


def _revision(*issues: CalculationSourceIssue) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=_WORK_UNIT,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=_WORK_UNIT,
        registry_snapshot_ref=_SNAPSHOT_REF,
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
    )


_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="130", revision_id=str(revision_covering("130", _YEAR).id), modelo_year=_YEAR, period="1T"
)


def _disagreement() -> SourceDisagreementFact:
    """A carried value an operator's value replaced, on a box the filing reaches."""
    casilla = validated_casilla_id("03")
    return SourceDisagreementFact.of(
        modelo=_SNAPSHOT_REF.modelo,
        filing_year=_SNAPSHOT_REF.modelo_year,
        period=_SNAPSHOT_REF.period,
        work_unit_id=_WORK_UNIT,
        registry_revision_id=_SNAPSHOT_REF.revision_id,
        inputs_digest="d" * 64,
        key=str(casilla),
        value_channel="decimal",
        reached_casillas=(casilla,),
        sources=(
            SourceDisagreementEntry(
                role=SourceDisagreementRole.BACKEND,
                source_family="ledger_renta_aggregation",
                value=DisagreementDecimalValue.of(Decimal("120.00")),
            ),
            SourceDisagreementEntry(
                role=SourceDisagreementRole.CALLER,
                source_family="operator_input",
                value=DisagreementDecimalValue.of(Decimal("125.00")),
            ),
        ),
        selected_role=SourceDisagreementRole.CALLER,
    )


def _issue(reason: str, **fields: object) -> CalculationSourceIssue:
    disagreement = {"disagreement": _disagreement()} if reason in DISAGREEMENT_REASONS else {}
    return CalculationSourceIssue.model_validate(
        {
            "reason": reason,
            "binding_source": None,
            "message": f"the calculation noticed {reason}",
            **disagreement,
            **fields,
        }
    )


def test_a_blocking_note_refuses_with_its_own_sentence_and_names_every_reason() -> None:
    revision = _revision(
        _issue("unrouted_declarable_quantity", binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION),
        _issue("invoice_reverse_charge_cuota_not_derivable"),
    )

    with override_settings(cadrumo_output_language="en"), pytest.raises(ModeloCalculationBlockedError) as refused:
        require_no_blocking_calculation_notes(revision, action="export")

    error = refused.value
    context = error.context or {}
    assert error.code.code == "REFUSED_MODELO_CALCULATION_BLOCKED"
    assert context["reasons"] == "invoice_reverse_charge_cuota_not_derivable,unrouted_declarable_quantity"
    assert context["action"] == "export"
    assert error.translated_message == "application.modelo.calc_diagnostic.unrouted_declarable_quantity.what"


@pytest.mark.parametrize(
    "issue",
    [
        _issue("withholding_detail_absent", binding_source=BindingSourceKind.WITHHOLDING),
        _issue("iva_selected_scope_evidence_failure", binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION),
        _issue("unrouted_observation", binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION),
    ],
    ids=["withholding-attestable", "iva-evidence", "oss-unrouted"],
)
def test_a_reason_the_check_adjudicates_itself_is_left_to_the_check(issue: CalculationSourceIssue) -> None:
    assert blocking_calculation_issues(_revision(issue)) == ()
    require_no_blocking_calculation_notes(_revision(issue), action="file")


@pytest.mark.parametrize(
    ("reason", "fields"),
    [
        ("unresolved_binding", {"casilla_id": "01"}),
        ("unhandled_binding_source", {}),
        ("source_domain_not_ready", {}),
    ],
)
def test_a_box_or_source_the_calculation_could_not_work_out_refuses(reason: str, fields: dict[str, object]) -> None:
    """Their producers report only sources that apply to the filer, so each one stands for a real gap."""
    with pytest.raises(ModeloCalculationBlockedError) as refused:
        require_no_blocking_calculation_notes(_revision(_issue(reason, **fields)), action="export")

    assert (refused.value.context or {})["reasons"] == reason


def test_a_value_by_an_undeclared_route_is_shown_but_not_refused() -> None:
    """It still fires on a route kept without a terminal origin by design, so it withholds nothing yet."""
    revision = _revision(_issue("terminal_origin_mismatch", binding_source=BindingSourceKind.FOREIGN_ASSET))

    assert blocking_calculation_issues(revision) == ()
    assert CALCULATION_NOTE_ATTENTION["terminal_origin_mismatch"] is ModeloFormAttention.CHECK


def test_a_revision_with_no_blocking_note_passes() -> None:
    """Teeth for the refusal above: the same call on a clean revision does not refuse."""
    require_no_blocking_calculation_notes(_revision(), action="verify")
    assert blocking_calculation_issues(
        _revision(_issue("unrouted_observation", binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION))
    )


def test_the_editor_blocks_on_exactly_the_reasons_the_application_refuses() -> None:
    """One definition: the editor's blocking level, and the gate, check steps and export that refuse."""
    blocking_level = {
        reason for reason, level in CALCULATION_NOTE_ATTENTION.items() if level is ModeloFormAttention.BLOCKS
    }
    persisted = get_args(CalculationSourceIssue.model_fields["reason"].annotation)
    refused_by_the_gate = {
        reason
        for reason in persisted
        if blocking_calculation_issues(
            _revision(_issue(reason, binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION))
        )
    }

    assert blocking_level == BLOCKING_REASONS == GATE_REFUSED_REASONS | CHECK_REFUSED_REASONS | EXPORT_REFUSED_REASONS
    assert refused_by_the_gate == set(GATE_REFUSED_REASONS)


@pytest.mark.parametrize("action", ["check", "export", "record"])
def test_a_contested_filed_figure_refuses_every_action_with_its_own_sentence(action: str) -> None:
    revision = _revision(_issue("precedence_tier_divergence"))

    with override_settings(cadrumo_output_language="en"), pytest.raises(ModeloCalculationBlockedError) as refused:
        require_no_blocking_calculation_notes(revision, action=action)

    context = refused.value.context or {}
    assert context["reason"] == "precedence_tier_divergence"
    assert refused.value.translated_message == "application.modelo.calc_diagnostic.precedence_tier_divergence.what"


def test_a_contested_working_figure_is_shown_but_never_refused() -> None:
    assert not gate_refuses("precedence_tier_divergence_advisory", None)
    assert blocking_calculation_issues(_revision(_issue("precedence_tier_divergence"))) != ()


def test_only_a_resolution_of_the_exact_finding_releases_a_contested_figure() -> None:
    finding_key = _disagreement().finding_key
    covering = SourceDisagreementResolutions(finding_keys=frozenset({finding_key}))
    other = SourceDisagreementResolutions(finding_keys=frozenset({"0" * 64}))

    assert gate_refuses("precedence_tier_divergence", None, finding_key=finding_key)
    assert gate_refuses(
        "precedence_tier_divergence", None, finding_key=finding_key, resolutions=NO_SOURCE_DISAGREEMENT_RESOLUTIONS
    )
    assert gate_refuses("precedence_tier_divergence", None, finding_key=finding_key, resolutions=other)
    assert gate_refuses("precedence_tier_divergence", None, finding_key=None, resolutions=covering)
    assert not gate_refuses("precedence_tier_divergence", None, finding_key=finding_key, resolutions=covering)


def test_a_resolution_never_releases_a_note_that_states_no_disagreement() -> None:
    covering = SourceDisagreementResolutions(finding_keys=frozenset({_disagreement().finding_key}))

    assert gate_refuses(
        "unresolved_binding",
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        finding_key=_disagreement().finding_key,
        resolutions=covering,
    )
