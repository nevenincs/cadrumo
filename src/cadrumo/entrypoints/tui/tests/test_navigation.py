"""Focused contracts for the TUI navigation composition boundary."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError
from textual.screen import Screen

from ....application.search.workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchModeloAddress,
    WorkbenchSearchKind,
    WorkbenchSearchLabelKey,
    WorkbenchSearchResult,
    WorkbenchSearchSource,
    WorkbenchSearchStatus,
)
from ....core.identifier_grammar import NamespacedId
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ..navigation import (
    DestinationAdmissionError,
    DestinationFactoryError,
    DestinationUnavailableError,
    TUI_DESTINATION_CATALOGUE,
    TuiActionCandidateV1,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiDestinationIdV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    UnknownDestinationError,
    UnresolvedActionCandidateError,
    WorkbenchDestinationAdmissionState,
    build_destination_catalogue,
    declared_destination_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class MarkerScreen(Screen[None]):
    """Concrete test-only screen supplied through the factory seam."""


def _available_admission(destination: str) -> TuiDestinationAdmissionV1:
    return TuiDestinationAdmissionV1(destination=destination, state=WorkbenchDestinationAdmissionState.AVAILABLE)


def _admissions(
    *, state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
) -> dict[str, TuiDestinationAdmissionV1]:
    return {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination,
            state=state,
            reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else "navigation.reason",
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }


def _factories() -> dict[str, TuiScreenFactoryV1]:
    return {descriptor.destination: lambda _context: MarkerScreen() for descriptor in TUI_DESTINATION_CATALOGUE}


def _catalogue(
    *,
    admissions: Mapping[str, TuiDestinationAdmissionV1] | None = None,
    action_candidates: tuple[TuiActionCandidateV1, ...] = (),
) -> TuiDestinationCatalogueV1:
    return build_destination_catalogue(
        admissions=_admissions() if admissions is None else admissions,
        factories=_factories(),
        action_candidates=action_candidates,
    )


def _search_result(
    *,
    admission: WorkbenchDestinationAdmission,
    action_candidate_id: NamespacedId | None = None,
) -> WorkbenchSearchResult:
    return WorkbenchSearchResult(
        stable_id="a" * 64,
        kind=WorkbenchSearchKind.DECLARATION,
        source=WorkbenchSearchSource.DECLARATION,
        status=WorkbenchSearchStatus.DECLARATION_READY,
        label_key=WorkbenchSearchLabelKey.DECLARATION,
        address=WorkbenchModeloAddress(
            modelo=ModeloCode("303"),
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
        ),
        admission=admission,
        action_candidate_id=action_candidate_id,
        rank=0,
        score=100.0,
    )


def test_catalogue_is_closed_and_uses_only_locale_keys() -> None:
    assert declared_destination_ids() == {
        "workbench.home",
        "workbench.ledger",
        "workbench.declarations",
        "workbench.aeat_sync",
        "workbench.profile",
    }
    assert {entry.destination for entry in TUI_DESTINATION_CATALOGUE} == declared_destination_ids()
    assert all(entry.label_key.startswith("tui.destination.") for entry in TUI_DESTINATION_CATALOGUE)
    assert all(" " not in entry.label_key for entry in TUI_DESTINATION_CATALOGUE)


@pytest.mark.parametrize("state", list(WorkbenchDestinationAdmissionState))
def test_each_explicit_admission_state_has_truthful_reason_contract(
    state: WorkbenchDestinationAdmissionState,
) -> None:
    kwargs = {
        "destination": "workbench.home",
        "state": state,
        "reason_code": None if state is WorkbenchDestinationAdmissionState.AVAILABLE else "navigation.reason",
    }
    TuiDestinationAdmissionV1(**kwargs)
    if state is WorkbenchDestinationAdmissionState.AVAILABLE:
        with pytest.raises(ValidationError):
            TuiDestinationAdmissionV1(**{**kwargs, "reason_code": "navigation.reason"})
    else:
        with pytest.raises(ValidationError):
            TuiDestinationAdmissionV1(**{**kwargs, "reason_code": None})


def test_catalogue_requires_all_admissions_and_injected_factory_for_available_routes() -> None:
    missing = _admissions()
    del missing["workbench.profile"]
    with pytest.raises(Exception, match="every destination"):
        build_destination_catalogue(admissions=missing, factories=_factories())

    with pytest.raises(DestinationFactoryError, match="injected screen factory"):
        build_destination_catalogue(admissions=_admissions())


def test_non_available_route_has_no_factory_and_cannot_be_opened() -> None:
    admissions = _admissions(state=WorkbenchDestinationAdmissionState.LOCKED)
    with pytest.raises(DestinationFactoryError, match="non-available"):
        _catalogue(admissions=admissions)

    route_admissions = _admissions()
    route_admissions["workbench.profile"] = TuiDestinationAdmissionV1(
        destination="workbench.profile",
        state=WorkbenchDestinationAdmissionState.LOCKED,
        reason_code="navigation.reason",
    )
    factories = _factories()
    del factories["workbench.profile"]
    catalogue = build_destination_catalogue(admissions=route_admissions, factories=factories)
    focus = TuiFocusIdentityV1(destination="workbench.profile", semantic_key="navigation.profile")
    with pytest.raises(DestinationUnavailableError):
        catalogue.create_screen(TuiNavigationTargetV1(destination="workbench.profile", focus=focus))


def test_factory_protocol_receives_semantic_context_and_returns_screen() -> None:
    seen: list[TuiScreenContextV1] = []

    def factory(context: TuiScreenContextV1) -> Screen[None]:
        seen.append(context)
        return MarkerScreen()

    factories = _factories()
    factories["workbench.home"] = factory
    catalogue = build_destination_catalogue(admissions=_admissions(), factories=factories)
    focus = TuiFocusIdentityV1(destination="workbench.home", semantic_key="navigation.home")
    screen = catalogue.create_screen(TuiNavigationTargetV1(destination="workbench.home", focus=focus))
    assert isinstance(screen, MarkerScreen)
    assert seen == [TuiScreenContextV1(destination="workbench.home", focus=focus)]


def test_focus_identity_is_semantic_and_target_rejects_cross_destination_focus() -> None:
    first = TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry", restore_token="b" * 64)
    second = TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry", restore_token="b" * 64)
    assert first == second
    assert "row" not in type(first).model_fields
    with pytest.raises(ValidationError, match="must belong"):
        TuiNavigationTargetV1(
            destination="workbench.home",
            focus=first,
        )


def test_search_result_resolves_to_semantic_focus_and_admitted_action() -> None:
    action = TuiActionCandidateV1(action_candidate_id="operator.declaration.open", destination="workbench.declarations")
    catalogue = _catalogue(action_candidates=(action,))
    result = _search_result(
        admission=WorkbenchDestinationAdmission(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        ),
        action_candidate_id="operator.declaration.open",
    )
    target = catalogue.target_for_search_result(result)
    assert target.destination == "workbench.declarations"
    assert target.focus.semantic_key == "search.declaration"
    assert target.focus.restore_token == "a" * 64
    assert target.action_candidate_id == "operator.declaration.open"


def test_search_result_fails_closed_for_unknown_action_or_admission_drift() -> None:
    catalogue = _catalogue()
    result = _search_result(
        admission=WorkbenchDestinationAdmission(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        ),
        action_candidate_id="operator.declaration.open",
    )
    with pytest.raises(UnresolvedActionCandidateError):
        catalogue.target_for_search_result(result)

    locked = _admissions()
    locked["workbench.declarations"] = TuiDestinationAdmissionV1(
        destination="workbench.declarations",
        state=WorkbenchDestinationAdmissionState.LOCKED,
        reason_code="navigation.reason",
    )
    factories = _factories()
    del factories["workbench.declarations"]
    unavailable_catalogue = build_destination_catalogue(admissions=locked, factories=factories)
    with pytest.raises(DestinationUnavailableError):
        unavailable_catalogue.target_for_search_result(
            _search_result(
                admission=WorkbenchDestinationAdmission(
                    destination="workbench.declarations",
                    state=WorkbenchDestinationAdmissionState.LOCKED,
                    reason_code="navigation.reason",
                )
            )
        )


def test_unknown_destination_and_raw_dependency_imports_fail_closed() -> None:
    with pytest.raises(UnknownDestinationError):
        _catalogue().resolve("workbench.unknown")

    source = ast.parse((Path(__file__).parent.parent / "navigation.py").read_text())
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not imported & {"httpx", "socket", "pathlib", "requests"}
