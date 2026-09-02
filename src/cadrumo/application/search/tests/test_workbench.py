"""Contract tests for the frontend-neutral workbench search service."""

from __future__ import annotations

import inspect
import math
from collections.abc import Sequence
from itertools import permutations
from typing import Any, cast

import pytest
from pydantic import ValidationError

from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.search.workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchModeloAddress,
    WorkbenchSearchDocument,
    WorkbenchSearchKind,
    WorkbenchSearchRequest,
    WorkbenchSearchResponse,
    WorkbenchSearchResult,
    WorkbenchSearchService,
    WorkbenchSearchStatus,
)
from cadrumo.core.period import Period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _address(*, modelo: str = "303", year: int = 2025, period: str = "1T") -> WorkbenchModeloAddress:
    return WorkbenchModeloAddress(
        modelo=modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, period),
    )


def _admission(
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(
        destination="workbench.declarations",
        state=state,
        reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else "admission.profile_locked",
    )


def _document(
    stable_id: str,
    label: str,
    *,
    kind: WorkbenchSearchKind = WorkbenchSearchKind.DECLARATION,
    search_terms: tuple[str, ...] = (),
    admission: WorkbenchDestinationAdmission | None = None,
    action: ActionReference | None = None,
) -> WorkbenchSearchDocument:
    return WorkbenchSearchDocument(
        stable_id=stable_id,
        kind=kind,
        source="modelo.local_projection",
        label=label,
        search_terms=search_terms,
        address=None if kind in {WorkbenchSearchKind.LEDGER, WorkbenchSearchKind.MESSAGE} else _address(),
        status=WorkbenchSearchStatus.READY,
        admission=admission or _admission(),
        action=action,
    )


def _result_data(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "stable_id": "declaration:303:2025:1T",
        "kind": WorkbenchSearchKind.DECLARATION,
        "source": "modelo.local_projection",
        "label": "Modelo 303",
        "address": _address(),
        "status": WorkbenchSearchStatus.READY,
        "admission": _admission(),
        "action": None,
        "rank": 0,
        "score": 1.0,
    }
    data.update(changes)
    return data


def test_human_facing_result_kinds_cover_cross_domain_search_without_work_unit_vocabulary() -> None:
    assert {kind.value for kind in WorkbenchSearchKind} == {
        "declaration",
        "filing",
        "history",
        "ledger",
        "message",
        "modelo",
        "reconciliation",
        "revision",
    }
    assert "work_unit" not in str(WorkbenchSearchDocument.model_json_schema()).casefold()


def test_search_normalizes_unicode_accents_case_and_whitespace() -> None:
    service = WorkbenchSearchService([_document("declaration:303:2025:1T", "Declaración trimestral de ÍVA")])

    response = service.search(WorkbenchSearchRequest(query="  DECLARACION   trimestral de iva  "))

    assert [result.stable_id for result in response.results] == ["declaration:303:2025:1T"]


def test_modelo_year_and_period_are_searchable_as_the_natural_address() -> None:
    document = _document(
        "modelo:303:2025:1T",
        "Modelo 303 IVA",
        kind=WorkbenchSearchKind.MODELO,
    )

    result = WorkbenchSearchService([document]).search(WorkbenchSearchRequest(query="MODELO 303 2025 1t")).results[0]

    assert result.address == _address()
    assert result.kind is WorkbenchSearchKind.MODELO


def test_filing_reference_is_searchable_without_becoming_a_result_payload() -> None:
    document = _document(
        "filing:303:2025:1T",
        "Presentación Modelo 303",
        kind=WorkbenchSearchKind.FILING,
        search_terms=("Referencia CSV ÁBC-123",),
    )

    result = WorkbenchSearchService([document]).search(WorkbenchSearchRequest(query="abc-123")).results[0]

    assert result.stable_id == document.stable_id
    assert "search_terms" not in WorkbenchSearchResult.model_fields


def test_exact_title_then_title_match_then_metadata_match_define_ranking() -> None:
    documents = (
        _document("c", "Declaración anual", search_terms=("IVA",)),
        _document("b", "IVA trimestral"),
        _document("a", "IVA"),
    )

    response = WorkbenchSearchService(documents).search(WorkbenchSearchRequest(query="iva"))

    assert [result.stable_id for result in response.results] == ["a", "b", "c"]
    assert [result.rank for result in response.results] == [0, 1, 2]
    assert response.results[0].score > response.results[1].score > response.results[2].score


def test_input_permutation_cannot_change_ranked_results() -> None:
    documents = (
        _document("c", "IVA trimestral"),
        _document("a", "IVA trimestral"),
        _document("b", "IVA trimestral"),
    )

    orders = {
        tuple(
            result.stable_id
            for result in WorkbenchSearchService(order).search(WorkbenchSearchRequest(query="iva")).results
        )
        for order in permutations(documents)
    }

    assert orders == {("a", "b", "c")}


def test_result_page_is_bounded_while_total_matches_counts_the_full_snapshot() -> None:
    documents = tuple(_document(f"declaration:{index:03d}", f"IVA declaration {index}") for index in range(105))

    response = WorkbenchSearchService(documents).search(WorkbenchSearchRequest(query="iva", limit=100))

    assert len(response.results) == 100
    assert response.total_matches == 105
    with pytest.raises(ValidationError, match="at most 100 items"):
        WorkbenchSearchResponse(query="iva", results=(*response.results, response.results[0]), total_matches=105)


def test_duplicate_stable_identity_is_refused_before_search() -> None:
    with pytest.raises(ValueError, match="unique stable identities"):
        WorkbenchSearchService([_document("same", "First"), _document("same", "Second")])


@pytest.mark.parametrize(
    "kind",
    [
        WorkbenchSearchKind.DECLARATION,
        WorkbenchSearchKind.MODELO,
        WorkbenchSearchKind.REVISION,
        WorkbenchSearchKind.FILING,
        WorkbenchSearchKind.HISTORY,
    ],
)
def test_modelo_related_documents_and_results_require_a_natural_address(kind: WorkbenchSearchKind) -> None:
    with pytest.raises(ValidationError, match="require a Modelo address"):
        WorkbenchSearchDocument(
            stable_id="missing-address",
            kind=kind,
            source="modelo.local_projection",
            label="Addressed record",
            status=WorkbenchSearchStatus.READY,
            admission=_admission(),
        )
    with pytest.raises(ValidationError, match="require a Modelo address"):
        WorkbenchSearchResult(**_result_data(kind=kind, address=None))


def test_locked_admission_requires_and_preserves_its_reason_without_an_action() -> None:
    with pytest.raises(ValidationError, match="requires an admission reason"):
        WorkbenchDestinationAdmission(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.LOCKED,
        )
    with pytest.raises(ValidationError, match="cannot carry an admission reason"):
        WorkbenchDestinationAdmission(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
            reason_code="admission.profile_locked",
        )

    locked = _admission(WorkbenchDestinationAdmissionState.LOCKED)
    document = _document("message:locked", "Locked message", kind=WorkbenchSearchKind.MESSAGE, admission=locked)
    result = WorkbenchSearchService([document]).search(WorkbenchSearchRequest(query="locked")).results[0]

    assert result.admission == locked
    assert result.action is None


def test_non_available_destination_cannot_claim_an_actionable_reference() -> None:
    with pytest.raises(ValidationError, match="cannot carry an actionable reference"):
        _document(
            "message:locked",
            "Locked message",
            kind=WorkbenchSearchKind.MESSAGE,
            admission=_admission(WorkbenchDestinationAdmissionState.LOCKED),
            action=ActionReference(action_id="operator.message.open"),
        )


def test_result_preserves_source_status_admission_address_and_action() -> None:
    action = ActionReference(action_id="operator.declaration.open")
    document = _document("declaration:303", "Modelo 303", action=action)

    result = WorkbenchSearchService([document]).search(WorkbenchSearchRequest(query="303")).results[0]

    assert result.source == document.source
    assert result.status is document.status
    assert result.admission == document.admission
    assert result.address == document.address
    assert result.action == action


def test_public_schemas_expose_only_redacted_search_metadata() -> None:
    forbidden = {
        "account",
        "amount",
        "counterparty",
        "currency",
        "name",
        "nif",
        "payload",
        "raw_id",
        "secret",
        "url",
    }
    for model in (WorkbenchSearchDocument, WorkbenchSearchResult, WorkbenchSearchResponse):
        assert forbidden.isdisjoint(model.model_json_schema()["properties"])


def test_query_service_has_no_io_or_repository_dependency() -> None:
    constructor = inspect.signature(WorkbenchSearchService)
    search = inspect.signature(WorkbenchSearchService.search)

    assert tuple(constructor.parameters) == ("documents",)
    assert tuple(search.parameters) == ("self", "request")
    assert not ({"open", "read", "write", "connect", "request"} & set(WorkbenchSearchService.search.__code__.co_names))


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf])
def test_result_refuses_non_finite_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        WorkbenchSearchResult(**_result_data(score=score))


@pytest.mark.parametrize("control", ["\u0000", "\u000a", "\u0085"])
def test_every_free_text_surface_refuses_control_characters(control: str) -> None:
    with pytest.raises(ValidationError, match="control characters"):
        _document(f"bad{control}id", "Safe")
    with pytest.raises(ValidationError, match="control characters"):
        _document("safe", f"Bad{control}label")
    with pytest.raises(ValidationError, match="control characters"):
        _document("safe", "Safe", search_terms=(f"bad{control}term",))
    with pytest.raises(ValidationError, match="control characters"):
        WorkbenchSearchRequest(query=f"bad{control}query")
    with pytest.raises(ValidationError, match="control characters"):
        WorkbenchSearchResult(**_result_data(label=f"bad{control}result"))
    with pytest.raises(ValidationError, match="control characters"):
        WorkbenchSearchResponse(query=f"bad{control}response")


def test_service_and_models_refuse_wrong_boundary_types() -> None:
    with pytest.raises(TypeError, match="WorkbenchSearchDocument"):
        WorkbenchSearchService(cast(Sequence[WorkbenchSearchDocument], [object()]))
    service = WorkbenchSearchService([_document("safe", "Safe")])
    with pytest.raises(TypeError, match="WorkbenchSearchRequest"):
        service.search(cast(WorkbenchSearchRequest, object()))
    with pytest.raises(ValidationError):
        WorkbenchSearchRequest(query=cast(str, 123))
    with pytest.raises(ValidationError):
        WorkbenchSearchRequest(query="safe", limit=True)  # type: ignore[arg-type]
