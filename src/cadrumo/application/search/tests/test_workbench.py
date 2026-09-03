"""Adversarial tests for the intrinsically safe workbench search projection."""

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
    WorkbenchFilingAddress,
    WorkbenchModeloAddress,
    WorkbenchRevisionAddress,
    WorkbenchSearchDocument,
    WorkbenchSearchKind,
    WorkbenchSearchLabelKey,
    WorkbenchSearchRequest,
    WorkbenchSearchResponse,
    WorkbenchSearchResult,
    WorkbenchSearchService,
    WorkbenchSearchSource,
    WorkbenchSearchStatus,
)
from cadrumo.core.period import Period
from cadrumo.domain.modelos.codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALCULATION_REVISION_ID = "c" * 64
_FILING_RECORD_ID = "f" * 64
_PRIVATE_IDENTITY_BASIS = "synthetic-private-record-basis"
_ADDRESS_UNSET = object()

_SOURCE_BY_KIND = {
    WorkbenchSearchKind.LEDGER_ENTRY: WorkbenchSearchSource.LEDGER_ENTRY,
    WorkbenchSearchKind.LEDGER_EVIDENCE: WorkbenchSearchSource.LEDGER_EVIDENCE,
    WorkbenchSearchKind.DECLARATION: WorkbenchSearchSource.DECLARATION,
    WorkbenchSearchKind.MODELO: WorkbenchSearchSource.MODELO,
    WorkbenchSearchKind.REVISION: WorkbenchSearchSource.REVISION,
    WorkbenchSearchKind.FILING: WorkbenchSearchSource.FILING,
    WorkbenchSearchKind.HISTORY: WorkbenchSearchSource.HISTORY,
    WorkbenchSearchKind.RECONCILIATION: WorkbenchSearchSource.RECONCILIATION,
    WorkbenchSearchKind.NOTIFICATION: WorkbenchSearchSource.NOTIFICATION,
}
_STATUS_BY_KIND = {
    WorkbenchSearchKind.LEDGER_ENTRY: WorkbenchSearchStatus.LEDGER_ENTRY_READY,
    WorkbenchSearchKind.LEDGER_EVIDENCE: WorkbenchSearchStatus.LEDGER_EVIDENCE_CAPTURED,
    WorkbenchSearchKind.DECLARATION: WorkbenchSearchStatus.DECLARATION_READY,
    WorkbenchSearchKind.MODELO: WorkbenchSearchStatus.MODELO_AVAILABLE,
    WorkbenchSearchKind.REVISION: WorkbenchSearchStatus.REVISION_CURRENT,
    WorkbenchSearchKind.FILING: WorkbenchSearchStatus.FILING_ACCEPTED,
    WorkbenchSearchKind.HISTORY: WorkbenchSearchStatus.HISTORY_OBSERVED,
    WorkbenchSearchKind.RECONCILIATION: WorkbenchSearchStatus.RECONCILIATION_OPEN,
    WorkbenchSearchKind.NOTIFICATION: WorkbenchSearchStatus.NOTIFICATION_UNREAD,
}
_LABEL_BY_KIND = {kind: WorkbenchSearchLabelKey(f"search.{kind.value}") for kind in WorkbenchSearchKind}


def _admission(
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(
        destination="workbench.destination",
        state=state,
        reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else "admission.profile_locked",
    )


def _modelo_address() -> WorkbenchModeloAddress:
    return WorkbenchModeloAddress(
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
    )


def _revision_address() -> WorkbenchRevisionAddress:
    return WorkbenchRevisionAddress(
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        calculation_revision_id=_CALCULATION_REVISION_ID,
    )


def _filing_address() -> WorkbenchFilingAddress:
    return WorkbenchFilingAddress(
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        filing_record_id=_FILING_RECORD_ID,
    )


def _address(
    kind: WorkbenchSearchKind,
) -> WorkbenchModeloAddress | WorkbenchRevisionAddress | WorkbenchFilingAddress | None:
    if kind is WorkbenchSearchKind.REVISION:
        return _revision_address()
    if kind is WorkbenchSearchKind.FILING:
        return _filing_address()
    if kind in {
        WorkbenchSearchKind.DECLARATION,
        WorkbenchSearchKind.MODELO,
        WorkbenchSearchKind.HISTORY,
    }:
        return _modelo_address()
    return None


def _document(
    kind: WorkbenchSearchKind = WorkbenchSearchKind.DECLARATION,
    *,
    source: WorkbenchSearchSource | None = None,
    status: WorkbenchSearchStatus | None = None,
    address: object = _ADDRESS_UNSET,
    admission: WorkbenchDestinationAdmission | None = None,
    action_candidate_id: str | None = None,
    identity_basis: str | None = None,
) -> WorkbenchSearchDocument:
    natural_address = (
        _address(kind)
        if address is _ADDRESS_UNSET
        else cast(
            WorkbenchModeloAddress | WorkbenchRevisionAddress | WorkbenchFilingAddress | None,
            address,
        )
    )
    return WorkbenchSearchDocument(
        kind=kind,
        source=source or _SOURCE_BY_KIND[kind],
        status=status or _STATUS_BY_KIND[kind],
        label_key=_LABEL_BY_KIND[kind],
        address=natural_address,
        admission=admission or _admission(),
        action_candidate_id=action_candidate_id,
        identity_basis=(
            identity_basis
            if identity_basis is not None
            else _PRIVATE_IDENTITY_BASIS
            if kind
            in {
                WorkbenchSearchKind.LEDGER_ENTRY,
                WorkbenchSearchKind.LEDGER_EVIDENCE,
                WorkbenchSearchKind.HISTORY,
                WorkbenchSearchKind.RECONCILIATION,
                WorkbenchSearchKind.NOTIFICATION,
            }
            else None
        ),
    )


def _result_data(**changes: Any) -> dict[str, Any]:
    document = _document()
    data: dict[str, Any] = {
        "stable_id": "a" * 64,
        **document.model_dump(),
        "rank": 0,
        "score": 1.0,
    }
    data.update(changes)
    return data


def test_provider_authored_labels_terms_hashes_and_stable_ids_are_not_fields() -> None:
    fields = set(WorkbenchSearchDocument.model_fields)
    assert fields.isdisjoint({"label", "search_terms", "token_digests", "stable_id"})
    assert "digest_operator_safe_tokens" not in workbench_module.__all__


def test_nif_iban_label_raw_hex_identity_and_search_terms_fail_closed() -> None:
    base = _document().model_dump()
    attacks = (
        {"label": "X2482300W · ES91 2100 0418 4502 0005 1332"},
        {"stable_id": "1" * 64},
        {"search_terms": ("X2482300W",)},
        {"token_digests": (hashlib.sha256(b"x2482300w").hexdigest(),)},
    )
    for attack in attacks:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            WorkbenchSearchDocument.model_validate({**base, **attack})


def test_serialized_document_and_response_contain_no_plaintext_or_dictionary_token_hash() -> None:
    sensitive_tokens = ("x2482300w", "es9121000418450200051332", _PRIVATE_IDENTITY_BASIS)
    dictionary_hashes = tuple(hashlib.sha256(token.encode()).hexdigest() for token in sensitive_tokens)
    document = _document(WorkbenchSearchKind.LEDGER_ENTRY)
    request = WorkbenchSearchRequest(query="ledger entry")
    response = WorkbenchSearchService([document]).search(request)

    serialized = " ".join(
        (document.model_dump_json(), request.model_dump_json(), response.model_dump_json(), repr(document))
    ).casefold()
    assert all(token not in serialized for token in sensitive_tokens)
    assert all(token_hash not in serialized for token_hash in dictionary_hashes)
    assert "query" not in WorkbenchSearchResponse.model_fields


@pytest.mark.parametrize("kind", list(WorkbenchSearchKind))
def test_each_kind_accepts_its_exact_source_status_and_label_key(kind: WorkbenchSearchKind) -> None:
    document = _document(kind)
    assert document.source is _SOURCE_BY_KIND[kind]
    assert document.status is _STATUS_BY_KIND[kind]
    assert document.label_key is _LABEL_BY_KIND[kind]


def test_valid_status_under_wrong_source_and_kind_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requires source"):
        _document(WorkbenchSearchKind.LEDGER_ENTRY, source=WorkbenchSearchSource.REVISION)
    with pytest.raises(ValidationError, match="is not declared by source"):
        _document(WorkbenchSearchKind.REVISION, status=WorkbenchSearchStatus.NOTIFICATION_UNREAD)
    with pytest.raises(ValidationError, match="requires label_key"):
        WorkbenchSearchDocument(
            kind=WorkbenchSearchKind.REVISION,
            source=WorkbenchSearchSource.REVISION,
            status=WorkbenchSearchStatus.REVISION_CURRENT,
            label_key=WorkbenchSearchLabelKey.NOTIFICATION,
            address=_revision_address(),
            admission=_admission(),
        )


def test_arbitrary_valid_looking_source_and_status_suffixes_are_rejected() -> None:
    data = _document(WorkbenchSearchKind.LEDGER_ENTRY).model_dump()
    with pytest.raises(ValidationError):
        WorkbenchSearchDocument.model_validate({**data, "source": "ledger.other_projection"})
    with pytest.raises(ValidationError):
        WorkbenchSearchDocument.model_validate({**data, "status": "ledger.entry.filed"})
    with pytest.raises(ValidationError):
        WorkbenchSearchDocument.model_validate({**data, "status": "ledger.entry.nif_exposed"})


def test_every_declared_status_is_accepted_only_by_its_source_family() -> None:
    for status in WorkbenchSearchStatus:
        matching_kinds = [
            kind
            for kind, source_status in _STATUS_BY_KIND.items()
            if status.value.rsplit(".", 1)[0] == source_status.value.rsplit(".", 1)[0]
        ]
        assert len(matching_kinds) == 1
        kind = matching_kinds[0]
        assert _document(kind, status=status).status is status


def test_revision_address_uses_calculation_revision_id_not_registry_revision_id() -> None:
    assert set(WorkbenchRevisionAddress.model_fields) == {
        "address_kind",
        "modelo",
        "filing_year",
        "period",
        "calculation_revision_id",
    }
    assert "revision_id" not in WorkbenchRevisionAddress.model_fields
    assert _revision_address().calculation_revision_id == _CALCULATION_REVISION_ID


def test_kind_requires_its_exact_discriminated_address_variant() -> None:
    with pytest.raises(ValidationError, match="exact WorkbenchRevisionAddress"):
        _document(WorkbenchSearchKind.REVISION, address=_modelo_address())
    with pytest.raises(ValidationError, match="exact WorkbenchFilingAddress"):
        _document(WorkbenchSearchKind.FILING, address=_revision_address())
    with pytest.raises(ValidationError, match="exact WorkbenchModeloAddress"):
        _document(WorkbenchSearchKind.DECLARATION, address=_filing_address())
    with pytest.raises(ValidationError, match="cannot carry"):
        _document(WorkbenchSearchKind.LEDGER_EVIDENCE, address=_modelo_address())


def test_address_variants_reject_irrelevant_or_simultaneous_exact_ids() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkbenchModeloAddress.model_validate({**_modelo_address().model_dump(), "filing_record_id": _FILING_RECORD_ID})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkbenchRevisionAddress.model_validate(
            {**_revision_address().model_dump(), "filing_record_id": _FILING_RECORD_ID}
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkbenchFilingAddress.model_validate(
            {**_filing_address().model_dump(), "calculation_revision_id": _CALCULATION_REVISION_ID}
        )


def test_address_uses_canonical_modelo_and_matches_period_year() -> None:
    assert isinstance(_modelo_address().modelo, ModeloCode)
    with pytest.raises((ValidationError, ValueError)):
        WorkbenchModeloAddress(
            modelo="30A",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
        )
    with pytest.raises(ValidationError, match="filing_year must match"):
        WorkbenchModeloAddress(
            modelo=ModeloCode("303"),
            filing_year=2025,
            period=Period.from_year_and_code(2024, "1T"),
        )


def test_stable_identity_is_derived_and_duplicate_safe_projections_are_refused() -> None:
    response = WorkbenchSearchService([_document()]).search(WorkbenchSearchRequest(query="declaration"))
    assert len(response.results[0].stable_id) == 64
    with pytest.raises(ValueError, match="unique derived identities"):
        WorkbenchSearchService([_document(), _document()])


@pytest.mark.parametrize(
    "kind",
    [
        WorkbenchSearchKind.LEDGER_ENTRY,
        WorkbenchSearchKind.LEDGER_EVIDENCE,
        WorkbenchSearchKind.HISTORY,
        WorkbenchSearchKind.RECONCILIATION,
        WorkbenchSearchKind.NOTIFICATION,
    ],
)
def test_distinct_same_state_multi_record_families_coexist_with_opaque_ids(
    kind: WorkbenchSearchKind,
) -> None:
    documents = (
        _document(kind, identity_basis="synthetic-record-a"),
        _document(kind, identity_basis="synthetic-record-b"),
    )
    response = WorkbenchSearchService(documents).search(WorkbenchSearchRequest(query=kind.value.replace("_", " ")))
    identities = tuple(result.stable_id for result in response.results)

    assert response.total_matches == 2
    assert len(set(identities)) == 2
    assert all(
        identity
        not in {
            hashlib.sha256(basis.encode()).hexdigest()
            for basis in (
                "synthetic-record-a",
                "synthetic-record-b",
            )
        }
        for identity in identities
    )


def test_opaque_identity_is_stable_across_mutable_projection_state() -> None:
    identity_basis = "synthetic-stable-ledger-record"
    documents = (
        _document(WorkbenchSearchKind.LEDGER_ENTRY, identity_basis=identity_basis),
        _document(
            WorkbenchSearchKind.LEDGER_ENTRY,
            status=WorkbenchSearchStatus.LEDGER_ENTRY_CLASSIFIED,
            identity_basis=identity_basis,
        ),
        _document(
            WorkbenchSearchKind.LEDGER_ENTRY,
            admission=_admission(WorkbenchDestinationAdmissionState.LOCKED),
            identity_basis=identity_basis,
        ),
        _document(
            WorkbenchSearchKind.LEDGER_ENTRY,
            action_candidate_id="operator.ledger.open",
            identity_basis=identity_basis,
        ),
    )
    identities = {
        WorkbenchSearchService([document]).search(WorkbenchSearchRequest(query="ledger entry")).results[0].stable_id
        for document in documents
    }

    assert len(identities) == 1


def test_opaque_identity_basis_is_required_only_for_multi_record_families() -> None:
    with pytest.raises(ValidationError, match="requires a private opaque identity basis"):
        WorkbenchSearchDocument.model_validate(_document(WorkbenchSearchKind.NOTIFICATION).model_dump())
    with pytest.raises(ValidationError, match="derives identity from its natural address"):
        _document(WorkbenchSearchKind.REVISION, identity_basis="synthetic-unexpected-basis")


def test_unicode_case_accent_and_address_search_are_normalized() -> None:
    service = WorkbenchSearchService([_document()])
    assert service.search(WorkbenchSearchRequest(query="  DÉCLARATION  ")).total_matches == 1
    assert service.search(WorkbenchSearchRequest(query="modelo 303 2025 1t")).total_matches == 1


def test_permutation_determinism_and_bounded_total() -> None:
    documents = (
        _document(WorkbenchSearchKind.DECLARATION),
        _document(WorkbenchSearchKind.MODELO),
        _document(WorkbenchSearchKind.HISTORY),
    )
    orders = {
        tuple(
            result.stable_id
            for result in WorkbenchSearchService(order).search(WorkbenchSearchRequest(query="modelo")).results
        )
        for order in permutations(documents)
    }
    assert len(orders) == 1
    limited = WorkbenchSearchService(documents).search(WorkbenchSearchRequest(query="modelo", limit=2))
    assert len(limited.results) == 2
    assert limited.total_matches == 3


def test_locked_admission_requires_reason_and_rejects_action_candidate() -> None:
    with pytest.raises(ValidationError, match="requires an admission reason"):
        WorkbenchDestinationAdmission(
            destination="workbench.destination",
            state=WorkbenchDestinationAdmissionState.LOCKED,
        )
    with pytest.raises(ValidationError, match="cannot carry an action candidate"):
        _document(
            admission=_admission(WorkbenchDestinationAdmissionState.LOCKED),
            action_candidate_id="operator.declaration.open",
        )


def test_private_service_and_module_have_no_io_or_authority_resolution_dependency() -> None:
    service = WorkbenchSearchService([_document()])
    assert not hasattr(service, "documents")
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
    forbidden = {"pathlib", "socket", "urllib", "requests", "httpx", "sqlite3", "operator_actions"}
    assert all(not any(part in forbidden for part in module.split(".")) for module in imported_modules)
    called_attributes = {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    called_names = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {"open", "read", "write", "connect", "request", "Path"}.isdisjoint(called_attributes | called_names)


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf])
def test_result_refuses_non_finite_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        WorkbenchSearchResult(**_result_data(score=score))


def test_query_is_transient_and_type_checked() -> None:
    request = WorkbenchSearchRequest(query="declaration")
    assert request.model_dump() == {"limit": 20}
    with pytest.raises(ValidationError):
        WorkbenchSearchRequest(query=cast(str, 123))
    with pytest.raises(ValidationError, match="control characters"):
        WorkbenchSearchRequest(query="bad\nquery")
    service = WorkbenchSearchService([_document()])
    with pytest.raises(TypeError, match="WorkbenchSearchRequest"):
        service.search(cast(WorkbenchSearchRequest, object()))
    with pytest.raises(TypeError, match="WorkbenchSearchDocument"):
        WorkbenchSearchService(cast(Sequence[WorkbenchSearchDocument], [object()]))
