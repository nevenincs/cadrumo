"""LLM CLI routes preserve admitted review facts and reject misbound results.

The registered-operation port supplies typed review/result documents; these are
frontend unit contracts, without native admission or encrypted persistence proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType, SimpleNamespace
from typing import Literal, cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.ledger.classify_result_contracts import (
    LedgerClassifyOperationResult,
)
from ....application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmChildProjection,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmReviewResponse,
    LedgerLlmSuggestionProjection,
)
from ....application.ledger.llm_review_results import LedgerLlmOperationResult
from ....application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ....application.ledger.operator_iva_contracts import (
    LEDGER_OPERATOR_IVA_DEFINITION_ID,
    LedgerOperatorIvaRequest,
    LedgerOperatorIvaResult,
)
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.operations.schema_identity import OperationSchemaIdentityV1
from ....application.review.filter import LedgerReviewStatus
from ....core.json_contract import Notice
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.iva.schema import IvaCategory
from .. import _ledger_llm_cli as classify
from .. import ledger_lifecycle_cli as lifecycle
from .. import runtime_ledger_classify as operator_bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000bb")
_TRANSACTION = "b" * 64
_DIGEST = "d" * 64
_OPERATION = "f" * 64
_PROVENANCE = "llm:local-text:fixture-model"
_Mode = Literal["classification", "saturated", "auto_split", "split"]
_Action = Literal["preview", "apply", "reject"]


def _review(mode: _Mode, *, children: int = 2) -> LedgerLlmReviewProjection:
    split = mode in {"auto_split", "split"}
    child = LedgerLlmChildProjection(
        proportion="0.5" if children == 2 else "1",
        amount="50" if children == 2 else "100",
        description="Reviewed invoice component",
        category="office_supplies",
        iva_category=None,
        iva_rate=None,
        taxable_base=None,
        iva_amount=None,
        rate_derivable=False,
        derivation_note="No IVA derivation",
        evidence_citation="invoice page 1",
    )
    return LedgerLlmReviewProjection(
        profile_id=_PROFILE,
        reviewed_proposal_digest=_DIGEST,
        suggestion=LedgerLlmSuggestionProjection(
            kind="split" if split else "saturated" if mode == "saturated" else "classification",
            transaction_id=_TRANSACTION,
            provenance=_PROVENANCE,
            reason="Reviewed invoice",
            evidence_id="invoice-1",
            classification="BUSINESS",
            category="office_supplies",
            confidence="0.9",
            multiple_components=True,
            parent_amount="100" if split else None,
            children=(child,) * children if split else (),
        ),
    )


def _classified(*, profile: UUID = _PROFILE, transaction_id: str = _TRANSACTION) -> LedgerClassifyOperationResult:
    transaction = LedgerTransactionProjection(
        transaction_id=transaction_id,
        date="2026-01-01",
        booked_date="2026-01-01",
        value_date=None,
        amount="100",
        currency="EUR",
        direction="expense",
        counterparty="Fixture supplier",
        description="Reviewed invoice",
        business_classification="BUSINESS",
        business_pct="0.25",
        category_id="office_supplies",
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id="invoice-1",
        invoice_id=None,
        attachment_ids=(),
        notes="",
        lifecycle_state="active",
        classified_by=_PROVENANCE,
        classified_at="2026-01-01T00:00:00Z",
        classification_reason="Reviewed invoice",
        classification_confidence="0.9",
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at="2026-01-01T00:00:00Z",
        modified_at="2026-01-01T00:00:00Z",
    )
    return LedgerClassifyOperationResult(
        outcome="classified",
        profile_id=profile,
        transaction=transaction,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e" * 64,),
    )


def _settled(review: LedgerLlmReviewProjection, action: _Action) -> LedgerLlmOperationResult:
    common = {
        "profile_id": review.profile_id,
        "reviewed_proposal_digest": review.reviewed_proposal_digest,
        "transaction_id": review.suggestion.transaction_id,
        "provenance": review.suggestion.provenance,
    }
    if action == "preview":
        return LedgerLlmOperationResult.model_validate({**common, "outcome": "preview", "preview": review})
    if action == "reject":
        return LedgerLlmOperationResult.model_validate(
            {
                **common,
                "outcome": "rejected",
                "bucket_event_id": "e" * 64,
                "suggestion_kind": "split" if review.suggestion.kind == "split" else "classification",
                "operator_reason": "Operator review",
            }
        )
    if review.suggestion.kind == "split" and len(review.suggestion.children) > 1:
        return LedgerLlmOperationResult.model_validate(
            {
                **common,
                "outcome": "split",
                "split_group_id": "a" * 64,
                "child_transaction_ids": ("1" * 64, "2" * 64),
                "classified_child_count": 2,
            }
        )
    return LedgerLlmOperationResult.model_validate({**common, "outcome": "classified", "classification": _classified()})


@dataclass
class _ReviewPort:
    review: LedgerLlmReviewProjection
    settled: LedgerLlmOperationResult | None = None
    effect: OperationEffect = OperationEffect.UPDATED
    requests: list[LedgerLlmReviewRequest] = field(default_factory=list)
    decisions: list[str | None] = field(default_factory=list)
    output: list[dict[str, object]] = field(default_factory=list)
    completion_override: (
        RegisteredOperationCompletion[LedgerLlmOperationResult]
        | RegisteredOperationReviewCompletion[LedgerLlmReviewProjection]
        | None
    ) = None

    def bind(self, monkeypatch: pytest.MonkeyPatch, module: ModuleType, *, definition_id: str) -> None:
        client = SimpleNamespace(profile_id=_PROFILE)
        monkeypatch.setattr(module, "bound_profile_client", lambda _ctx: client)

        def submit(
            bound: object, request: LedgerLlmReviewRequest, **kwargs: object
        ) -> (
            RegisteredOperationCompletion[LedgerLlmOperationResult]
            | RegisteredOperationReviewCompletion[LedgerLlmReviewProjection]
        ):
            assert bound is client
            assert kwargs["definition_id"] == definition_id
            assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
            assert kwargs["result_type"] is LedgerLlmOperationResult
            assert kwargs["request_version"] == kwargs["result_version"] == 1
            handler = cast(RegisteredOperationReviewHandler[LedgerLlmReviewProjection], kwargs["review"])
            assert handler.review_type is LedgerLlmReviewProjection
            assert handler.review_schema == OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".projection", schema_version=1, model_type=LedgerLlmReviewProjection
            )
            assert handler.response_schema == OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".response", schema_version=1, model_type=LedgerLlmReviewResponse
            )
            self.requests.append(request)
            if request.preview:
                if self.completion_override is not None:
                    return self.completion_override
                return RegisteredOperationCompletion(_OPERATION, _settled(self.review, "preview"), OperationEffect.NONE)
            decision = handler.decide(self.review)
            self.decisions.append(decision)
            if decision is None:
                return RegisteredOperationReviewCompletion(_OPERATION, self.review, OperationEffect.NONE)
            result = self.settled or _settled(self.review, "reject" if decision == "reject" else "apply")
            return RegisteredOperationCompletion(_OPERATION, result, self.effect)

        def emit(_ctx: object, *, command: str, result: BaseModel, **kwargs: object) -> None:
            self.output.append({"command": command, "result": result.model_dump(mode="json"), **kwargs})

        monkeypatch.setattr(module, "run_registered_operation", submit)
        monkeypatch.setattr(module, "emit_envelope", emit)


def _invoke(mode: _Mode, action: _Action, *, business_pct: str = "0.25") -> None:
    ctx = cast(typer.Context, cast(object, None))
    if mode == "split":
        lifecycle.ledger_split(
            ctx,
            transaction_id=_TRANSACTION[:12],
            llm=True,
            apply=action == "apply",
            yes=action == "apply",
            actor="operator",
            read_evidence=True,
            vision_model="fixture-vision",
            reason="Operator review",
        )
    elif mode == "auto_split":
        classify.dispatch_autosplit(
            ctx,
            transaction_id=_TRANSACTION[:12],
            classification=None,
            file=None,
            apply=action == "apply",
            reject=action == "reject",
            actor="operator",
            read_evidence=True,
            vision_model="fixture-vision",
            reason="Operator review",
        )
    else:
        handler = classify.ledger_saturate_llm if mode == "saturated" else classify.ledger_classify_llm
        handler(
            ctx,
            transaction_id=_TRANSACTION[:12],
            classification=None,
            file=None,
            business_pct=business_pct,
            apply=action == "apply",
            reject=action == "reject",
            actor="operator",
            read_evidence=True,
            vision_model="fixture-vision",
            reason="Operator review",
        )


@pytest.mark.parametrize("mode", ["classification", "saturated", "auto_split", "split"])
@pytest.mark.parametrize("action", ["preview", "apply"])
def test_review_routes_bind_exact_profile_options_and_render_worker_facts(
    monkeypatch: pytest.MonkeyPatch, mode: _Mode, action: _Action
) -> None:
    port = _ReviewPort(_review(mode))
    definition = LEDGER_SPLIT_REVIEW_DEFINITION_ID if mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    port.bind(monkeypatch, lifecycle if mode == "split" else classify, definition_id=definition)
    _invoke(mode, action)

    origins = {
        "classification": LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        "saturated": LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
        "auto_split": LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
        "split": LlmReviewInvocationOrigin.SPLIT_LLM,
    }
    assert port.requests == [
        LedgerLlmReviewRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION[:12],
            mode=mode,
            origin=origins[mode],
            preview=action == "preview",
            business_pct="0.25" if action == "apply" and mode in {"classification", "saturated"} else None,
            actor="operator",
            read_evidence=True,
            vision_model="fixture-vision",
            reason="Operator review",
        )
    ]
    assert port.decisions == ([] if action == "preview" else ["apply"])
    assert len(port.output) == 1
    payload = cast(dict[str, object], port.output[0]["result"])
    if mode in {"auto_split", "split"}:
        assert port.output[0]["command"] == "ledger.split"
        assert payload["parent_transaction_id"] == _TRANSACTION
        assert payload["persisted"] is (action == "apply")
        if action == "apply":
            assert payload["child_transaction_ids"] == ["1" * 64, "2" * 64]
        else:
            children = cast(list[dict[str, object]], payload["proposed_children"])
            assert [child["amount"] for child in children] == ["50", "50"]
    elif action == "preview":
        assert payload["persisted"] is False
        assert payload["confidence"] == "0.9"
        assert payload["transaction_id"] == _TRANSACTION
        notices = cast(list[Notice], port.output[0]["notices"])
        assert len(notices) == 1
        assert notices[0].code == "ledger.classify.split_recommended"
    else:
        assert payload["transaction_id"] == _TRANSACTION
        assert payload["bucket_event_ids"] == ["e" * 64]
        transaction = cast(dict[str, object], payload["transaction"])
        assert transaction["classified_by"] == _PROVENANCE
        assert transaction["business_pct"] == "0.25"


@pytest.mark.parametrize("mode", ["classification", "saturated", "auto_split", "split"])
def test_terminal_preview_never_requests_response_and_later_apply_reviews_fresh_invocation(
    monkeypatch: pytest.MonkeyPatch, mode: _Mode
) -> None:
    port = _ReviewPort(_review(mode))
    definition = LEDGER_SPLIT_REVIEW_DEFINITION_ID if mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    port.bind(monkeypatch, lifecycle if mode == "split" else classify, definition_id=definition)
    _invoke(mode, "preview")
    assert port.requests[0].preview is True
    assert port.decisions == []
    assert len(port.output) == 1
    _invoke(mode, "apply")
    assert port.requests[1].preview is False
    assert port.decisions == ["apply"]
    assert len(port.output) == 2


@pytest.mark.parametrize("mode", ["classification", "split"])
@pytest.mark.parametrize("mismatch", ["profile", "digest", "transaction", "kind", "provenance"])
def test_terminal_preview_refuses_misbound_projection_before_rendering(
    monkeypatch: pytest.MonkeyPatch, mode: _Mode, mismatch: str
) -> None:
    review = _review(mode)
    original = _settled(review, "preview")
    if mismatch == "profile":
        malformed = original.model_copy(update={"profile_id": _OTHER_PROFILE})
    elif mismatch == "digest":
        malformed = original.model_copy(update={"reviewed_proposal_digest": "a" * 64})
    elif mismatch == "transaction":
        malformed = original.model_copy(update={"transaction_id": "c" * 64})
    elif mismatch == "provenance":
        malformed = original.model_copy(update={"provenance": "llm:local-text:another-model"})
    else:
        wrong = review.suggestion.model_copy(update={"kind": "saturated" if mode == "split" else "split"})
        malformed = original.model_copy(update={"preview": review.model_copy(update={"suggestion": wrong})})
    port = _ReviewPort(review)
    port.completion_override = RegisteredOperationCompletion(_OPERATION, malformed, OperationEffect.NONE)
    definition = LEDGER_SPLIT_REVIEW_DEFINITION_ID if mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    port.bind(monkeypatch, lifecycle if mode == "split" else classify, definition_id=definition)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(mode, "preview")
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert refused.value.context["operation_id"] == _OPERATION
    assert refused.value.context["effect"] == OperationEffect.NONE.value
    assert port.decisions == []
    assert port.output == []


@pytest.mark.parametrize("mode", ["classification", "split"])
@pytest.mark.parametrize("mismatch", ["effect", "condition", "refusal", "detached"])
def test_preview_refuses_mutating_unsettled_or_detached_completion(
    monkeypatch: pytest.MonkeyPatch, mode: _Mode, mismatch: str
) -> None:
    review = _review(mode)
    effect = OperationEffect.UPDATED if mismatch == "effect" else OperationEffect.NONE
    port = _ReviewPort(review)
    port.completion_override = (
        RegisteredOperationReviewCompletion(_OPERATION, review, effect)
        if mismatch == "detached"
        else RegisteredOperationCompletion(
            _OPERATION,
            _settled(review, "preview"),
            effect,
            terminal_condition=OperationTerminalCondition.REFUSED
            if mismatch == "condition"
            else OperationTerminalCondition.SUCCEEDED,
            refusal_code="runtime_unavailable" if mismatch == "refusal" else None,
        )
    )
    definition = LEDGER_SPLIT_REVIEW_DEFINITION_ID if mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    port.bind(monkeypatch, lifecycle if mode == "split" else classify, definition_id=definition)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(mode, "preview")
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert refused.value.context["operation_id"] == _OPERATION
    assert refused.value.context["effect"] == effect.value
    assert port.decisions == []
    assert port.output == []


@pytest.mark.parametrize("mode", ["classification", "saturated", "auto_split"])
def test_explicit_rejection_renders_settled_audit_without_claiming_row_persistence(
    monkeypatch: pytest.MonkeyPatch, mode: _Mode
) -> None:
    port = _ReviewPort(_review(mode))
    port.bind(monkeypatch, classify, definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    _invoke(mode, "reject")
    assert port.decisions == ["reject"]
    assert port.requests[0].origin is LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT
    payload = cast(dict[str, object], port.output[0]["result"])
    assert payload["rejected"] is True
    assert payload["persisted"] is False
    assert payload["bucket_event_id"] == "e" * 64
    assert payload["operator_reason"] == "Operator review"
    assert payload["provenance"] == _PROVENANCE
    assert payload["suggestion_kind"] == ("split" if mode == "auto_split" else "classification")


@pytest.mark.parametrize("mode", ["classification", "saturated"])
def test_noncanonical_percentage_refuses_before_submitting_review(monkeypatch: pytest.MonkeyPatch, mode: _Mode) -> None:
    port = _ReviewPort(_review(mode))
    port.bind(monkeypatch, classify, definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    with pytest.raises(typer.BadParameter):
        _invoke(mode, "apply", business_pct="0.2500")
    assert port.requests == []
    assert port.decisions == []
    assert port.output == []


@pytest.mark.parametrize("action", ["preview", "apply"])
def test_autosplit_lone_child_keeps_single_classification_payload(
    monkeypatch: pytest.MonkeyPatch, action: _Action
) -> None:
    port = _ReviewPort(_review("auto_split", children=1))
    port.bind(monkeypatch, classify, definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID)
    _invoke("auto_split", action)
    assert port.output[0]["command"] == "ledger.classify"
    payload = cast(dict[str, object], port.output[0]["result"])
    assert payload["transaction_id"] == _TRANSACTION
    assert "child_transaction_ids" not in payload
    if action == "preview":
        assert payload["classification"] == "BUSINESS"
        assert payload["confidence"] == "1"
        assert payload["category"] == "office_supplies"
        assert payload["persisted"] is False
    else:
        assert payload["bucket_id"] == str(_PROFILE)
        assert payload["bucket_event_ids"] == ["e" * 64]


@pytest.mark.parametrize("mode", ["classification", "split"])
@pytest.mark.parametrize("mismatch", ["profile", "digest", "transaction", "effect"])
def test_misbound_settled_result_refuses_with_operation_id_and_known_effect(
    monkeypatch: pytest.MonkeyPatch, mode: _Mode, mismatch: str
) -> None:
    review = _review(mode)
    original = _settled(review, "apply")
    data = original.model_dump(mode="python")
    if mismatch == "profile":
        data["profile_id"] = _OTHER_PROFILE
        if mode == "classification":
            data["classification"] = _classified(profile=_OTHER_PROFILE)
    elif mismatch == "digest":
        data["reviewed_proposal_digest"] = "a" * 64
    elif mismatch == "transaction":
        data["transaction_id"] = "c" * 64
        if mode == "classification":
            data["classification"] = _classified(transaction_id="c" * 64)
    effect = OperationEffect.NONE if mismatch == "effect" else OperationEffect.UPDATED
    port = _ReviewPort(review, LedgerLlmOperationResult.model_validate(data), effect)
    definition = LEDGER_SPLIT_REVIEW_DEFINITION_ID if mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    port.bind(monkeypatch, lifecycle if mode == "split" else classify, definition_id=definition)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(mode, "apply")
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert refused.value.context["operation_id"] == _OPERATION
    assert refused.value.context["effect"] == effect.value
    assert port.output == []


@pytest.mark.parametrize("wrong_effect", [False, True])
def test_operator_iva_public_handler_uses_exact_profile_runtime_result(
    monkeypatch: pytest.MonkeyPatch, wrong_effect: bool
) -> None:
    category = IvaCategory("fixture_category")
    result = LedgerOperatorIvaResult(
        profile_id=_PROFILE,
        transaction_id=_TRANSACTION,
        iva_category=category.value,
        derivable=True,
        iva_rate="0.21",
        taxable_base="100",
        iva_amount="21",
        classification=_classified(),
    )
    output: list[BaseModel] = []
    monkeypatch.setattr(operator_bridge, "bound_profile_client", lambda _ctx: SimpleNamespace(profile_id=_PROFILE))

    def submit(
        _client: object, request: LedgerOperatorIvaRequest, **kwargs: object
    ) -> RegisteredOperationCompletion[LedgerOperatorIvaResult]:
        assert request == LedgerOperatorIvaRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION[:12],
            iva_category=category.value,
            actor="operator",
        )
        assert kwargs["definition_id"] == LEDGER_OPERATOR_IVA_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerOperatorIvaResult
        return RegisteredOperationCompletion(
            _OPERATION, result, OperationEffect.NONE if wrong_effect else OperationEffect.UPDATED
        )

    def emit(_ctx: object, *, command: str, result: BaseModel, **_kwargs: object) -> None:
        assert command == "ledger.classify"
        output.append(result)

    monkeypatch.setattr(operator_bridge, "run_registered_operation", submit)
    monkeypatch.setattr(classify, "emit_envelope", emit)

    def invoke() -> None:
        classify.ledger_operator_iva_derive(
            cast(typer.Context, cast(object, None)),
            transaction_id=_TRANSACTION[:12],
            classification=None,
            file=None,
            iva_category=category,
            actor="operator",
        )

    if wrong_effect:
        with pytest.raises(CliRefusedBoundaryError) as refused:
            invoke()
        assert refused.value.context is not None
        assert refused.value.context["operation_id"] == _OPERATION
        assert refused.value.context["reason"] == "runtime_invalid_frame"
        assert refused.value.context["effect"] == OperationEffect.NONE.value
        assert output == []
    else:
        invoke()
        assert len(output) == 1
        payload = output[0].model_dump(mode="json")
        assert payload["bucket_id"] == str(_PROFILE)
        assert payload["transaction_id"] == _TRANSACTION
        assert payload["bucket_event_ids"] == ["e" * 64]
