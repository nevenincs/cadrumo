"""Bite tests for the redacted frontend-neutral workbench search contract."""

from __future__ import annotations

import ast
import hashlib
import inspect
import math
from collections.abc import Sequence
from itertools import permutations
from typing import Any, cast

import pytest
from pydantic import ValidationError

import cadrumo.application.search.workbench as workbench_module
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
    digest_operator_safe_tokens,
)
from cadrumo.core.period import Period
from cadrumo.domain.modelos.codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_ID = "f" * 64


def _id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _address(
    *,
    modelo: str = "303",
    revision_id: str | None = None,
    filing_record_id: str | None = None,
) -> WorkbenchModeloAddress:
    return WorkbenchModeloAddress(
        modelo=modelo,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id=revision_id,
        filing_record_id=filing_record_id,
    )


def _admission(
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(
        destination="workbench.declarations",
        state=state,
        reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else "admission.profile_locked",
    )


def _status(kind: WorkbenchSearchKind) -> str:
    return {
        WorkbenchSearchKind.LEDGER_ENTRY: "ledger.entry.ready",
        WorkbenchSearchKind.LEDGER_EVIDENCE: "ledger.evidence.captured",
        WorkbenchSearchKind.DECLARATION: "declaration.ready",
        WorkbenchSearchKind.MODELO: "modelo.available",
        WorkbenchSearchKind.REVISION: "revision.current",
        WorkbenchSearchKind.FILING: "filing.accepted",
        WorkbenchSearchKind.HISTORY: "history.observed",
        WorkbenchSearchKind.RECONCILIATION: "reconciliation.needs_review",
        WorkbenchSearchKind.NOTIFICATION: "notification.unread",
    }[kind]


def _kind_address(kind: WorkbenchSearchKind) -> WorkbenchModeloAddress | None:
    if kind is WorkbenchSearchKind.REVISION:
        return _address(revision_id="m303-2025-r1")
    if kind is WorkbenchSearchKind.FILING:
        return _address(filing_record_id=_FILING_ID)
    if kind in {
        WorkbenchSearchKind.DECLARATION,
        WorkbenchSearchKind.MODELO,
        WorkbenchSearchKind.HISTORY,
    }:
        return _address()
    return None


def _document(
    seed: str,
    label: str,
    *,
    kind: WorkbenchSearchKind = WorkbenchSearchKind.DECLARATION,
    token_digests: tuple[str, ...] = (),
    admission: WorkbenchDestinationAdmission | None = None,
    action_candidate_id: str | None = None,
    stable_id: str | None = None,
) -> WorkbenchSearchDocument:
    return WorkbenchSearchDocument(
        stable_id=stable_id or _id(seed),
        kind=kind,
        source="modelo.local_projection",
        label=label,
        token_digests=token_digests,
        address=_kind_address(kind),
        status_code=_status(kind),
        admission=admission or _admission(),
        action_candidate_id=action_candidate_id,
    )


def _result_data(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "stable_id": _id("result"),
        "kind": WorkbenchSearchKind.DECLARATION,
        "source": "modelo.local_projection",
        "label": "Modelo 303",
        "address": _address(),
        "status_code": "declaration.ready",
        "admission": _admission(),
        "action_candidate_id": None,
        "rank": 0,
        "score": 1.0,
    }
    data.update(changes)
    return data


def test_complete_human_facing_kind_vocabulary_has_no_work_unit_or_flattened_message_kind() -> None:
    assert {kind.value for kind in WorkbenchSearchKind} == {
        "ledger_entry",
        "ledger_evidence",
        "declaration",
        "modelo",
        "revision",
        "filing",
        "history",
        "reconciliation",
        "notification",
    }


@pytest.mark.parametrize("kind", list(WorkbenchSearchKind))
def test_each_kind_accepts_only_its_source_native_status_prefix(kind: WorkbenchSearchKind) -> None:
    assert _document(kind.value, kind.value, kind=kind).status_code == _status(kind)
    with pytest.raises(ValidationError, match="status_code must start"):
        WorkbenchSearchDocument(
            stable_id=_id(f"wrong-{kind.value}"),
            kind=kind,
            source="search.provider",
            label="Redacted label",
            address=_kind_address(kind),
            status_code="nonsense.ready",
            admission=_admission(),
        )


def test_ledger_evidence_and_notification_are_first_class_unaddressed_results() -> None:
    documents = (
        _document("evidence", "Captured invoice evidence", kind=WorkbenchSearchKind.LEDGER_EVIDENCE),
        _document("notice", "Unread AEAT notification", kind=WorkbenchSearchKind.NOTIFICATION),
    )
    service = WorkbenchSearchService(documents)

    assert (
        service.search(WorkbenchSearchRequest(query="evidence")).results[0].kind is WorkbenchSearchKind.LEDGER_EVIDENCE
    )
    assert (
        service.search(WorkbenchSearchRequest(query="notification")).results[0].kind is WorkbenchSearchKind.NOTIFICATION
    )


def test_stable_identity_is_canonical_hex64_and_canonical_duplicates_are_refused() -> None:
    canonical = _id("same")
    with pytest.raises(ValidationError):
        _document("bad", "Bad", stable_id="raw-database-id")
    first = _document("first", "First", stable_id=f" {canonical} ")
    second = _document("second", "Second", stable_id=canonical)
    with pytest.raises(ValueError, match="unique stable identities"):
        WorkbenchSearchService((first, second))


def test_token_digest_folds_case_accents_unicode_composition_and_whitespace_canonically() -> None:
    composed = digest_operator_safe_tokens("  DECLARACIÓN   ÍVA ")
    decomposed = digest_operator_safe_tokens("declaracio\u0301n iva")

    assert composed == decomposed
    assert composed == tuple(sorted(set(composed)))
    assert all(len(digest) == 64 for digest in composed)


def test_filing_reference_plaintext_is_never_retained_or_serialized() -> None:
    raw_reference = "CSV-ÁBC-123-SECRET"
    document = _document(
        "filing",
        "Filed Modelo 303",
        kind=WorkbenchSearchKind.FILING,
        token_digests=digest_operator_safe_tokens(raw_reference),
    )
    request = WorkbenchSearchRequest(query=raw_reference)
    response = WorkbenchSearchService([document]).search(request)

    assert response.results[0].stable_id == document.stable_id
    for serialized in (document.model_dump_json(), request.model_dump_json(), response.model_dump_json()):
        assert raw_reference.casefold() not in serialized.casefold()
        assert "secret" not in serialized.casefold()
    assert "token_digests" not in WorkbenchSearchResult.model_fields


def test_modelo_year_and_period_are_searchable_from_the_canonical_natural_address() -> None:
    document = _document("modelo", "Modelo 303 IVA", kind=WorkbenchSearchKind.MODELO)

    result = WorkbenchSearchService([document]).search(WorkbenchSearchRequest(query="MODELO 303 2025 1t")).results[0]

    assert result.address is not None
    assert isinstance(result.address.modelo, ModeloCode)


def test_modelo_address_uses_canonical_modelo_code_and_matching_year() -> None:
    assert _address().modelo == ModeloCode("303")
    with pytest.raises((ValidationError, ValueError)):
        _address(modelo="30A")
    with pytest.raises(ValidationError, match="filing_year must match"):
        WorkbenchModeloAddress(
            modelo=ModeloCode("303"),
            filing_year=2025,
            period=Period.from_year_and_code(2024, "1T"),
        )


def test_revision_and_filing_kinds_require_their_canonical_specific_identity() -> None:
    revision = _document("revision", "Revision", kind=WorkbenchSearchKind.REVISION)
    with pytest.raises(ValidationError, match="revision_id"):
        WorkbenchSearchDocument(
            stable_id=revision.stable_id,
            kind=revision.kind,
            source=revision.source,
            label=revision.label,
            token_digests=revision.token_digests,
            address=_address(),
            status_code=revision.status_code,
            admission=revision.admission,
        )
    filing = _document("filing", "Filing", kind=WorkbenchSearchKind.FILING)
    with pytest.raises(ValidationError, match="filing_record_id"):
        WorkbenchSearchDocument(
            stable_id=filing.stable_id,
            kind=filing.kind,
            source=filing.source,
            label=filing.label,
            token_digests=filing.token_digests,
            address=_address(),
            status_code=filing.status_code,
            admission=filing.admission,
        )
    with pytest.raises(ValidationError):
        _address(revision_id="UPPERCASE INVALID")
    with pytest.raises(ValidationError):
        _address(filing_record_id="f" * 63)


def test_action_candidate_is_unresolved_metadata_and_only_available_results_carry_it() -> None:
    candidate = _document(
        "candidate",
        "Open declaration",
        action_candidate_id="operator.declaration.open",
    )
    result = WorkbenchSearchService([candidate]).search(WorkbenchSearchRequest(query="open")).results[0]
    assert result.action_candidate_id == "operator.declaration.open"
    assert "action" not in WorkbenchSearchDocument.model_fields

    with pytest.raises(ValidationError, match="cannot carry an action candidate"):
        _document(
            "locked",
            "Locked declaration",
            admission=_admission(WorkbenchDestinationAdmissionState.LOCKED),
            action_candidate_id="operator.declaration.open",
        )


def test_service_exposes_no_document_snapshot_accessor() -> None:
    service = WorkbenchSearchService([_document("private", "Private snapshot")])
    assert not hasattr(service, "documents")
    assert tuple(name for name, _ in inspect.getmembers(WorkbenchSearchService, inspect.isfunction)) == (
        "__init__",
        "search",
    )


def test_exact_title_then_title_match_then_digest_match_define_ranking() -> None:
    documents = (
        _document("metadata", "Annual declaration", token_digests=digest_operator_safe_tokens("IVA")),
        _document("contains", "IVA quarterly"),
        _document("exact", "IVA"),
    )
    response = WorkbenchSearchService(documents).search(WorkbenchSearchRequest(query="iva"))
    assert [result.label for result in response.results] == ["IVA", "IVA quarterly", "Annual declaration"]
    assert response.results[0].score > response.results[1].score > response.results[2].score


def test_input_permutations_produce_identical_ranked_results() -> None:
    documents = tuple(_document(seed, "IVA quarterly") for seed in ("c", "a", "b"))
    orders = {
        tuple(
            result.stable_id
            for result in WorkbenchSearchService(order).search(WorkbenchSearchRequest(query="iva")).results
        )
        for order in permutations(documents)
    }
    assert len(orders) == 1


def test_bounded_page_preserves_full_total_and_only_query_digests() -> None:
    documents = tuple(_document(str(index), f"IVA declaration {index}") for index in range(105))
    response = WorkbenchSearchService(documents).search(WorkbenchSearchRequest(query="iva", limit=100))
    assert len(response.results) == 100
    assert response.total_matches == 105
    assert response.query_token_digests == digest_operator_safe_tokens("iva")
    assert "query" not in WorkbenchSearchResponse.model_fields


def test_locked_admission_requires_and_preserves_a_reason() -> None:
    with pytest.raises(ValidationError, match="requires an admission reason"):
        WorkbenchDestinationAdmission(
            destination="workbench.declarations",
            state=WorkbenchDestinationAdmissionState.LOCKED,
        )
    locked = _admission(WorkbenchDestinationAdmissionState.LOCKED)
    result = (
        WorkbenchSearchService([_document("locked", "Locked declaration", admission=locked)])
        .search(WorkbenchSearchRequest(query="locked"))
        .results[0]
    )
    assert result.admission == locked


def test_public_result_schema_excludes_raw_or_sensitive_fields() -> None:
    forbidden = {
        "account",
        "amount",
        "counterparty",
        "currency",
        "name",
        "nif",
        "payload",
        "query",
        "raw_id",
        "secret",
        "token_digests",
        "url",
    }
    assert forbidden.isdisjoint(WorkbenchSearchResult.model_json_schema()["properties"])


def test_module_dependencies_and_service_bytecode_have_no_io_or_authority_resolution() -> None:
    tree = ast.parse(inspect.getsource(workbench_module))
    imported_modules = {
        module
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for module in (
            *((node.module or "",) if isinstance(node, ast.ImportFrom) else ()),
            *(alias.name for alias in node.names if isinstance(node, ast.Import)),
        )
    }
    forbidden_modules = {"pathlib", "socket", "urllib", "requests", "httpx", "sqlite3"}
    assert all(module.split(".")[0] not in forbidden_modules for module in imported_modules)
    assert "operator_actions" not in inspect.getsource(workbench_module)
    assert {"open", "read", "write", "connect", "request"}.isdisjoint(WorkbenchSearchService.search.__code__.co_names)


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf])
def test_result_refuses_non_finite_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        WorkbenchSearchResult(**_result_data(score=score))


@pytest.mark.parametrize("control", ["\u0000", "\u000a", "\u0085"])
def test_human_readable_text_boundaries_refuse_control_characters(control: str) -> None:
    with pytest.raises(ValidationError, match="control characters"):
        _document("control", f"Bad{control}label")
    with pytest.raises(ValidationError, match="control characters"):
        WorkbenchSearchRequest(query=f"bad{control}query")
    with pytest.raises(ValueError, match="control characters"):
        digest_operator_safe_tokens(f"bad{control}term")


def test_service_and_models_refuse_wrong_boundary_types() -> None:
    with pytest.raises(TypeError, match="WorkbenchSearchDocument"):
        WorkbenchSearchService(cast(Sequence[WorkbenchSearchDocument], [object()]))
    service = WorkbenchSearchService([_document("safe", "Safe")])
    with pytest.raises(TypeError, match="WorkbenchSearchRequest"):
        service.search(cast(WorkbenchSearchRequest, object()))
    with pytest.raises(ValidationError):
        WorkbenchSearchRequest(query=cast(str, 123))
