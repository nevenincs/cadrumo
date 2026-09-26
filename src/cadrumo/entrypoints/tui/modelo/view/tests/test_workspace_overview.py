"""Real Textual-pilot proof for the modelo.workspace.overview destination.

The two properties under test are the ones where rendering the obvious
thing would assert something untrue: that the revision block shows
coordinates and not a chronology, and that absent recovery actions are
STATED rather than shown as an empty list.
"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Input, Select, Static
from textual.widgets.select import InvalidSelectValueError

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.edit_models import ModeloEditWritableScalarSurfaceEntryV1
from ......application.modelo.work_addressing import ModeloExactWorkUnitTarget
from ......application.modelo.workspace import graded_snapshot_refusal, modelo_workspace_recovery_action
from ......application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceLegalEvidenceReferenceV1,
    ModeloWorkspaceLifecycleProjectionV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceTextFactValueV1,
)
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.payment_election import PaymentElection
from ......core.prior_domiciliation_election import PriorDomiciliationElection
from ......core.refund_election import RefundElection
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....components.widgets import ContentDataTable, NoticeBand
from ...lifecycle import ModeloLifecycleActionUnavailableError
from ..controller import ModeloWorkspaceReadSession, open_workspace_read_session
from ..models import (
    evidence_reference_label,
    recovery_action_label,
    workspace_refusal_fact_label,
    workspace_refusal_reason_label,
)
from ..overview import (
    PAYMENT_ELECTION_LOCALE_KEYS,
    PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS,
    REFUND_ELECTION_LOCALE_KEYS,
    ModeloWorkspaceOverviewScreen,
    edit_control_id,
)
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    return open_workspace_read_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection)


def _graded_refusal(
    session: ModeloWorkspaceReadSession,
    *,
    code: ModeloWorkspaceRefusalCode,
    capability: ModeloWorkspaceCapabilityName,
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...],
    recovery_action_id: str,
    with_evidence: bool = False,
) -> ModeloWorkspaceDomainRefusalV1:
    """Build one domain refusal through the exact producer function that ships it.

    Reusing :func:`graded_snapshot_refusal` and :func:`modelo_workspace_recovery_action`
    -- rather than hand-assembling :class:`ModeloWorkspaceDomainRefusalV1` --
    keeps the fixture a faithful proxy for what ``resolve_graded_snapshot_result``
    actually returns for these three taxpayer-facing codes.
    """
    target = session.projection.target
    assert target.work_unit_id is not None
    result = graded_snapshot_refusal(
        code,
        requested_target=ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=target.work_unit_id, bucket_id=target.bucket_id)
        ),
        selected_target=target,
        capability=capability,
        reconsideration_condition="test reconsideration condition, never rendered directly",
        facts=facts,
        evidence=(ModeloWorkspaceLegalEvidenceReferenceV1(legal_ref_id="test-legal-ref"),) if with_evidence else (),
        source_disposition=None,
        recovery_action=modelo_workspace_recovery_action(recovery_action_id, work_unit_id=target.work_unit_id),
    )
    return result.refusal


class _UnavailableLifecycleActions:
    """One typed refusal proves the view renders application errors without a generic fallback."""

    async def calculate(self) -> object:
        raise ModeloLifecycleActionUnavailableError(
            translated_message="application.modelo.lifecycle.refusal.calculation_required"
        )


def _lifecycle_session(bucket_id: str, repository: WorkUnitCatalogueRepository) -> ModeloWorkspaceReadSession:
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    lifecycle = ModeloWorkspaceLifecycleProjectionV1(target=projection.target)
    return open_workspace_read_session(
        projection,
        lifecycle=lifecycle,
        lifecycle_actions=_UnavailableLifecycleActions(),
    )


@pytest.mark.asyncio
async def test_a_session_without_a_graded_refusal_mounts_no_notice(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The static fallback stays reachable and unexplained when it was never a fallback.

    A session opened directly at STATIC_INSPECTION -- no graded read was ever
    attempted for it -- carries ``graded_refusal=None``, and the overview must
    not invent an explanation for a gap that never occurred.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    assert session.graded_refusal is None
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query("#workspace-overview-graded-refusal")


@pytest.mark.parametrize(
    ("code", "capability", "fact_name", "fact_value", "recovery_action_id", "with_evidence"),
    [
        (
            ModeloWorkspaceRefusalCode.TARGET_NOT_FOUND,
            ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
            "modelo",
            "130",
            "operator.modelo.work.create",
            False,
        ),
        (
            ModeloWorkspaceRefusalCode.AUTHORITY_GRADE_UNAVAILABLE,
            ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION,
            "required_grade",
            "calculation",
            "operator.modelo.work.status",
            False,
        ),
        (
            ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
            ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
            "work_unit_id",
            "test-work-unit",
            "operator.modelo.work.calculate",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_each_taxpayer_facing_refusal_code_renders_its_reason_facts_and_recovery_action(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
    code: ModeloWorkspaceRefusalCode,
    capability: ModeloWorkspaceCapabilityName,
    fact_name: str,
    fact_value: str,
    recovery_action_id: str,
    with_evidence: bool,
) -> None:
    """The graded refusal renders honestly instead of a silent static fallback.

    Every one of the three codes ``resolve_graded_snapshot_result`` actually
    returns (``TARGET_NOT_FOUND``, ``AUTHORITY_GRADE_UNAVAILABLE``,
    ``CALCULATION_UNAVAILABLE``) must show its own translated reason, its
    facts, its recovery action, and -- underneath -- the same static content
    a fallback-free session shows, so the operator sees both what happened
    and what the page is showing instead.
    """
    bucket_id, repository = bucket_and_repository
    base_session = _session(bucket_id, repository)
    fact = ModeloWorkspaceEvidenceFactV1(name=fact_name, value=ModeloWorkspaceTextFactValueV1(value=fact_value))
    refusal = _graded_refusal(
        base_session,
        code=code,
        capability=capability,
        facts=(fact,),
        recovery_action_id=recovery_action_id,
        with_evidence=with_evidence,
    )
    assert refusal.code is code
    assert refusal.recovery_action is not None
    session = open_workspace_read_session(base_session.projection, graded_refusal=refusal)
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))

    async with app.run_test() as pilot:
        await pilot.pause()
        band = app.screen.query_one("#workspace-overview-graded-refusal", NoticeBand)
        rendered = " | ".join(str(static.content) for static in band.query(Static))

        assert workspace_refusal_reason_label(code) in rendered
        assert recovery_action_label(refusal.recovery_action) in rendered
        assert workspace_refusal_fact_label(fact) in rendered
        assert tr("tui.modelo.workspace_refusal.static_fallback") in rendered
        if with_evidence:
            assert refusal.evidence
            for reference in refusal.evidence:
                assert evidence_reference_label(reference) in rendered

        # The static content underneath stays reachable: this session's
        # capability denominator still renders in full, exactly as the
        # fallback-free session's does.
        table = app.screen.query_one("#workspace-overview-capability-table", ContentDataTable)
        assert table.row_count == len(ModeloWorkspaceCapabilityName)


@pytest.mark.asyncio
async def test_the_actions_line_names_the_catalogued_steps_the_producers_attached(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The line reports the projection's own recovery actions, in both directions.

    The expected sentence is derived from the capabilities rather than pinned,
    because which steps are addressable depends on whether the target carries
    a work unit. Pinning the empty sentence would keep passing on a screen that
    had stopped reading ``recovery_action`` at all.

    Deduplication is asserted separately from presence: two capabilities share
    the status action, and listing it twice would read as two different things
    to do.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository)
    labels: list[str] = []
    for capability in session.projection.capabilities:
        if capability.recovery_action is None:
            continue
        label = recovery_action_label(capability.recovery_action)
        if label not in labels:
            labels.append(label)
    expected = (
        tr("flows.modelo_workspace_overview.actions_none")
        if not labels
        else tr("flows.modelo_workspace_overview.actions_suggested", actions="; ".join(labels))
    )

    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))
    async with app.run_test() as pilot:
        await pilot.pause()
        notice = app.screen.query_one("#workspace-overview-actions", Static)
        assert str(notice.content) == expected
        for label in labels:
            assert str(notice.content).count(label) == 1


@pytest.mark.asyncio
async def test_the_revision_block_shows_coordinates_and_no_chronology(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Three coordinate rows, none of them a sequence over time.

    The page states the two point assertions and the review status; the
    law-selected revision id is a technical detail. A row count above that
    would mean the screen had synthesised history the projection does not
    carry.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-revision-table", ContentDataTable)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_every_capability_appears_exactly_once_with_a_distinguishing_glyph(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The screen shows the whole denominator, not a filtered subset.

    A capability omitted from the display would be indistinguishable from
    one the producer never answered, which is the distinction the closed
    denominator exists to preserve.
    """
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-capability-table", ContentDataTable)
        assert table.row_count == len(ModeloWorkspaceCapabilityName)


@pytest.mark.asyncio
async def test_an_absent_work_unit_renders_its_own_value_rather_than_a_blank_cell(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The address table always has four rows, present work unit or not."""
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#workspace-overview-address-table", ContentDataTable)
        assert table.row_count == 4


@pytest.mark.asyncio
async def test_the_destination_offers_no_editing_affordance(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Overview is a read destination like every other C2 screen."""
    from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for editing_widget in (Input, Button, Checkbox, RadioSet, SelectionList):
            assert not app.screen.query(editing_widget), (
                f"the read destination mounted an editing widget: {editing_widget.__name__}"
            )


def test_edit_control_ids_keep_valid_keys_and_encode_the_rest_distinctly() -> None:
    """Numeric and hyphenated keys keep their spelling; everything else is escaped one-to-one."""
    assert edit_control_id("scalar", "0165") == "modelo-edit-scalar-0165"
    assert edit_control_id("binding", "renta-certificado-trabajo-retenciones") == (
        "modelo-edit-binding-renta-certificado-trabajo-retenciones"
    )
    assert edit_control_id("scalar", "iva.prorrata-volumen-con-derecho") == (
        "modelo-edit-scalar-iva_2e_prorrata-volumen-con-derecho"
    )
    adversarial = ("a.b", "a_2e_b", "a_b", "a_5f_b", "a__b", "a-b", "ab")
    encoded = [edit_control_id("scalar", key) for key in adversarial]
    assert len(set(encoded)) == len(adversarial)


class _DottedCasillaEditActions:
    """A lifecycle door whose edit surface admits one semantic, dotted casilla id."""

    def __init__(self) -> None:
        self.edit_baseline = SimpleNamespace(
            permitted_surface=(
                ModeloEditWritableScalarSurfaceEntryV1.model_construct(
                    casilla_id="iva.prorrata-volumen-con-derecho", data_type="money", allowed_intents=("set",)
                ),
            )
        )
        self.applied: list[dict[str, object]] = []

    async def apply_edits(self, **kwargs: object) -> object:
        self.applied.append(kwargs)
        raise ModeloLifecycleActionUnavailableError(
            translated_message="application.modelo.lifecycle.refusal.calculation_required"
        )


@pytest.mark.asyncio
async def test_a_dotted_semantic_casilla_edit_control_composes_and_submits_its_value(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """One casilla id that is not a valid widget id must not stop the whole workspace from composing."""
    bucket_id, repository = bucket_and_repository
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    actions = _DottedCasillaEditActions()
    session = open_workspace_read_session(
        projection,
        lifecycle=ModeloWorkspaceLifecycleProjectionV1(target=projection.target),
        lifecycle_actions=actions,
    )
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(session))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one("#modelo-lifecycle-calculate", Button)
        field = app.screen.query_one(f"#{edit_control_id('scalar', 'iva.prorrata-volumen-con-derecho')}", Input)
        field.value = "150.00"
        app.screen.query_one("#modelo-edit-apply", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()

    assert actions.applied == [{"scalar_values": {"iva.prorrata-volumen-con-derecho": "150.00"}, "binding_values": {}}]


@pytest.mark.asyncio
async def test_lifecycle_controls_require_confirmation_or_a_typed_precondition(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The installed actions have stable controls and never turn a refusal into success."""
    bucket_id, repository = bucket_and_repository
    app = ScreenHostApp(ModeloWorkspaceOverviewScreen(_lifecycle_session(bucket_id, repository)))

    async with app.run_test() as pilot:
        await pilot.pause()
        for identifier in (
            "#modelo-lifecycle-calculate",
            "#modelo-lifecycle-verify",
            "#modelo-lifecycle-file",
            "#modelo-lifecycle-export",
        ):
            assert app.screen.query_one(identifier, Button)
        assert app.screen.query_one("#modelo-lifecycle-export-path", Input)

        app.screen.query_one("#modelo-lifecycle-export", Button).press()
        await pilot.pause()
        assert str(app.screen.query_one("#modelo-lifecycle-notice", Static).content) == tr(
            "application.modelo.lifecycle.refusal.export_destination_required"
        )

        app.screen.query_one("#modelo-lifecycle-file", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("escape")
        await pilot.pause()

        app.screen.query_one("#modelo-lifecycle-calculate", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert str(app.screen.query_one("#modelo-lifecycle-notice", Static).content) == tr(
            "application.modelo.lifecycle.refusal.calculation_required"
        )


class _ExportRecordingActions:
    """A lifecycle door that records what the export control submitted, then refuses it."""

    def __init__(self) -> None:
        self.exported: list[dict[str, object]] = []

    async def export(self, **kwargs: object) -> object:
        self.exported.append(kwargs)
        raise ModeloLifecycleActionUnavailableError(
            translated_message="application.modelo.lifecycle.refusal.calculation_required"
        )


_ELECTION_CONTROLS: tuple[str, ...] = (
    "#modelo-lifecycle-export-refund-election",
    "#modelo-lifecycle-export-payment-election",
    "#modelo-lifecycle-export-prior-domiciliation-election",
)


def _export_session(
    bucket_id: str, repository: WorkUnitCatalogueRepository, *, modelo: str, actions: _ExportRecordingActions
) -> ModeloWorkspaceReadSession:
    projection = resolve_real_result(bucket_id, repository, OutputLanguage.ES, modelo=modelo).projection
    return open_workspace_read_session(
        projection,
        lifecycle=ModeloWorkspaceLifecycleProjectionV1(target=projection.target),
        lifecycle_actions=actions,
    )


@pytest.mark.asyncio
async def test_a_modelo_303_export_offers_each_election_preset_to_its_neutral_default(
    m303_bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The operator sees and can change every declaration-shaping choice; nothing is decided out of sight."""
    bucket_id, repository = m303_bucket_and_repository
    actions = _ExportRecordingActions()
    app = ScreenHostApp(
        ModeloWorkspaceOverviewScreen(_export_session(bucket_id, repository, modelo="303", actions=actions))
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        assert [app.screen.query_one(control, Select).value for control in _ELECTION_CONTROLS] == [
            RefundElection.COMPENSAR.value,
            PaymentElection.INGRESO.value,
            PriorDomiciliationElection.KEEP.value,
        ]
        for control in _ELECTION_CONTROLS:
            with pytest.raises(InvalidSelectValueError):
                app.screen.query_one(control, Select).clear()
        app.screen.query_one("#modelo-lifecycle-export-path", Input).value = "modelo-303.boe"
        app.screen.query_one(_ELECTION_CONTROLS[0], Select).value = RefundElection.DEVOLVER.value
        app.screen.query_one(_ELECTION_CONTROLS[2], Select).value = PriorDomiciliationElection.CANCEL_OR_MODIFY.value
        app.screen.query_one("#modelo-lifecycle-export", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()

    assert actions.exported == [
        {
            "refund_election": RefundElection.DEVOLVER,
            "payment_election": PaymentElection.INGRESO,
            "prior_domiciliation_election": PriorDomiciliationElection.CANCEL_OR_MODIFY,
            "output_path": "modelo-303.boe",
        }
    ]


@pytest.mark.asyncio
async def test_a_modelo_without_those_elections_exports_with_the_command_line_defaults(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Modelo 130 offers no Modelo 303 choice, and submits what the command line applies when they are omitted."""
    bucket_id, repository = bucket_and_repository
    actions = _ExportRecordingActions()
    app = ScreenHostApp(
        ModeloWorkspaceOverviewScreen(_export_session(bucket_id, repository, modelo="130", actions=actions))
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query(Select)
        app.screen.query_one("#modelo-lifecycle-export-path", Input).value = "modelo-130.boe"
        app.screen.query_one("#modelo-lifecycle-export", Button).press()
        await pilot.pause()
        await app.workers.wait_for_complete()

    assert actions.exported == [
        {
            "refund_election": RefundElection.COMPENSAR,
            "payment_election": PaymentElection.INGRESO,
            "prior_domiciliation_election": PriorDomiciliationElection.KEEP,
            "output_path": "modelo-130.boe",
        }
    ]


@pytest.mark.parametrize(
    ("election", "keys"),
    [
        (RefundElection, REFUND_ELECTION_LOCALE_KEYS),
        (PaymentElection, PAYMENT_ELECTION_LOCALE_KEYS),
        (PriorDomiciliationElection, PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS),
    ],
)
def test_every_election_member_has_a_label(election: type[Enum], keys: dict[object, str]) -> None:
    """A member added to an election set must be offered, not silently missing from the form."""
    assert set(keys) == set(election)
