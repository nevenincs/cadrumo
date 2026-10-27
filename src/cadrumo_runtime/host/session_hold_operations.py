"""Registered operations relayed for the held person session.

The hold names no definition, subject, item or wording. Its parent names a
definition id, a subject and a typed request; the runtime's registered
operation validation decides whether the person's session may submit it. The
hold then relays what the runtime publishes: the observation of an operation
it submitted, the settled result or refusal document, the pending review document with a
digest of exactly what it showed, an answer bound to that digest, and a
cancellation at the observed revision. Every document passes unchanged, so the
product that registered the operation owns its meaning and its words.

An operation whose contract takes its amounts as a transient financial
operand is submitted with ``operation_financial_submit``: the parent's input
object travels once, as the runtime's financial input, and the relay keeps no
reference to it afterwards. The runtime refuses it for any definition whose
contract declares no such operand, so the hold still names no definition.

A refusal is a closed reply that keeps the hold holding. The runtime's
``operation_changed`` cue is forwarded only while an operation this session
relayed is unsettled. A sign-in to a provider is one more registered
operation the parent submits and answers like any other.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, MutableMapping
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, JsonValue, ValidationError

from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition
from cadrumo_client.commands.registered_operation_responses import (
    require_registered_response_control,
    submit_registered_review_response,
)
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import (
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    deadline_after,
    remaining_budget,
)
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationClaimableReviews,
    OperationClaimableReviewsListed,
    OperationControl,
    OperationFinancialInput,
    OperationManage,
    OperationManaged,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationReply,
    OperationRequest,
    OperationReview,
    OperationReviewClaim,
    OperationReviewClaimed,
    OperationSubmitted,
)
from cadrumo_client.contracts.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_settlement import PinnedConnection, submit_operation

RELAY_ACTION_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "operation_submit": frozenset({"definition_id", "subject_ref", "payload"}),
    "operation_financial_submit": frozenset({"definition_id", "subject_ref", "input"}),
    "operation_observe": frozenset({"operation_id", "after_cursor"}),
    "operation_result": frozenset({"operation_id"}),
    "operation_review": frozenset({"operation_id"}),
    "operation_review_claimable": frozenset[str](),
    "operation_review_claim": frozenset({"operation_id", "interaction_id", "revision", "review_digest"}),
    "operation_respond": frozenset({"operation_id", "interaction_id", "revision", "review_digest", "decision"}),
    "operation_cancel": frozenset({"operation_id", "expected_revision"}),
}
"""The relay actions of the held person bridge and the fields each takes beside ``request_id`` and ``action``."""

# One budget for the entire relay action, including all of its exchanges.
# The desktop holder allows 140 s for this runtime budget plus bridge overhead.
_LOGGER = logging.getLogger(__name__)
_EVENT_PAGE: Final = 64
_MAX_WATCHED: Final = 16
_MAX_PAYLOAD_TEXT: Final = 12_288


class RelayRefusedError(Exception):
    """A relayed action refused with a closed code; the hold keeps holding."""

    def __init__(self, code: str, *, holder_operation_id: str | None = None) -> None:
        """Keep the closed code and, for a busy subject, the operation that holds it."""
        super().__init__(code)
        self.code = code
        self.holder_operation_id = holder_operation_id


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("expected text")
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise TypeError("expected a count")
    return value


def _document(model: BaseModel) -> dict[str, JsonValue]:
    loaded: object = json.loads(model.model_dump_json())
    if not isinstance(loaded, dict):
        raise TypeError("expected a document")
    return {str(key): value for key, value in loaded.items()}


class OperationRelay:
    """The registered operations one held person session submitted and still follows."""

    def __init__(self, client: FrontendClient) -> None:
        """Bind the hold's own verified client."""
        self._client = client
        self._watched: set[str] = set()

    def watching(self) -> bool:
        """Whether a cue may matter: an operation this session relayed is unsettled."""
        return bool(self._watched)

    def handle(self, action: str, request: Mapping[str, object]) -> dict[str, object]:
        """Run one relay action and return its reply fields; refusals raise :class:`RelayRefusedError`."""
        deadline = deadline_after(MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS)
        try:
            if action == "operation_submit":
                return self._submit(request, deadline=deadline)
            if action == "operation_financial_submit":
                return self._submit_financial(request, deadline=deadline)
            if action == "operation_review_claimable":
                return self._claimable_reviews(deadline=deadline)
            operation_id = _text(request["operation_id"])
            if action == "operation_observe":
                observation = self._observe(operation_id, _count(request["after_cursor"]), deadline=deadline)
                return {"kind": "operation_observed", "observation": _document(observation)}
            if action == "operation_result":
                return self._result(operation_id, deadline=deadline)
            if action == "operation_review":
                pending, document = self._review(operation_id, deadline=deadline)
                return {
                    "kind": "operation_review",
                    "operation_id": operation_id,
                    "interaction_id": pending.interaction_id,
                    "revision": pending.revision,
                    "expires_at": None if pending.expires_at is None else pending.expires_at.isoformat(),
                    "review_digest": content_hash_hex(document),
                    "document": document,
                }
            if action == "operation_review_claim":
                return self._claim_review(operation_id, request, deadline=deadline)
            if action == "operation_respond":
                return self._respond(operation_id, request, deadline=deadline)
            if action == "operation_cancel":
                return self._cancel(operation_id, _count(request["expected_revision"]), deadline=deadline)
            raise ValueError("unknown relay action")
        except FrontendRefusedError as error:
            raise RelayRefusedError(error.reason, holder_operation_id=error.holder_operation_id) from None
        except (RefusalError, ValidationError) as error:
            diagnostic_event(
                _LOGGER,
                "session_hold_operation_refused",
                level=logging.WARNING,
                fields={
                    "action": action if action in RELAY_ACTION_KEYS else "invalid",
                    "reason": error.reason.value if isinstance(error, RefusalError) else "invalid_projection",
                    "error_type": type(error).__name__,
                },
            )
            raise RelayRefusedError("unavailable") from None

    # ── Exchanges ───────────────────────────────────────────────────────────

    def _exchange(self, request: OperationRequest, *, deadline: float) -> OperationReply:
        remaining_budget(deadline)
        return self._client.operation(request, deadline=deadline)

    def _watch(self, projection: OperationPublicProjectionV1) -> None:
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            self._watched.discard(projection.operation_id)
        elif projection.operation_id in self._watched or len(self._watched) < _MAX_WATCHED:
            self._watched.add(projection.operation_id)

    def _submit(self, request: Mapping[str, object], *, deadline: float) -> dict[str, object]:
        payload = request["payload"]
        if not isinstance(payload, dict):
            raise TypeError("expected a request object")
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(payload_json) > _MAX_PAYLOAD_TEXT:
            raise ValueError("request too large")
        pinned = PinnedConnection.of(self._client)
        submitted = submit_operation(
            self._client,
            pinned,
            definition_id=_text(request["definition_id"]),
            subject_ref=_text(request["subject_ref"]),
            payload_json=payload_json,
            deadline=deadline,
        )
        return self._start(pinned, submitted.receipt.operation_id, deadline=deadline)

    def _submit_financial(self, request: Mapping[str, object], *, deadline: float) -> dict[str, object]:
        """Hand the parent's input to the runtime once, as financial input, and let go of it."""
        body = request["input"]
        if isinstance(request, MutableMapping):
            # The bridge's own copy of the input is dropped before anything else can read it.
            request.pop("input", None)
        if not isinstance(body, dict):
            raise TypeError("expected an input object")
        input_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        body = None
        try:
            if len(input_json) > SUBMISSION_PAYLOAD_MAX_BYTES:
                raise ValueError("input too large")
            pinned = PinnedConnection.of(self._client)
            submitted = self._exchange(
                OperationFinancialInput(
                    request_id=uuid4(),
                    profile_id=pinned.profile_id,
                    session_id=pinned.session_id,
                    definition_id=_text(request["definition_id"]),
                    subject_ref=_text(request["subject_ref"]),
                    payload_json=input_json,
                ),
                deadline=deadline,
            )
        finally:
            input_json = ""
        if not isinstance(submitted, OperationSubmitted):
            raise RelayRefusedError("unavailable")
        return self._start(pinned, submitted.receipt.operation_id, deadline=deadline)

    def _start(self, pinned: PinnedConnection, operation_id: str, *, deadline: float) -> dict[str, object]:
        started = self._exchange(
            OperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=pinned.profile_id,
                session_id=pinned.session_id,
                operation_id=operation_id,
            ),
            deadline=deadline,
        )
        if not isinstance(started, OperationAcknowledged) or started.operation_id != operation_id:
            raise RelayRefusedError("unavailable")
        if len(self._watched) < _MAX_WATCHED:
            self._watched.add(operation_id)
        return {"kind": "operation_submitted", "operation_id": operation_id}

    def _observe(self, operation_id: str, after_cursor: int, *, deadline: float) -> OperationObservationSuccessV1:
        reply = self._exchange(
            OperationObserve(
                request_id=uuid4(),
                profile_id=self._client.profile_id,
                session_id=self._client.session_id,
                observation=OperationObservationRequestV1(
                    operation_id=operation_id, after_cursor=after_cursor, page_limit=_EVENT_PAGE
                ),
            ),
            deadline=deadline,
        )
        if not isinstance(reply, OperationObserved):
            raise RelayRefusedError("unavailable")
        observation = reply.observation
        if not isinstance(observation, OperationObservationSuccessV1):
            raise RelayRefusedError("unavailable")
        if observation.projection.operation_id != operation_id:
            raise RelayRefusedError("unavailable")
        self._watch(observation.projection)
        return observation

    def _result(self, operation_id: str, *, deadline: float) -> dict[str, object]:
        projection = self._observe(operation_id, 0, deadline=deadline).projection
        contract = projection.definition_contract
        schema = contract.result_schema
        # A refusal its definition declares carries a detail document, read the same way as a result.
        documented = projection.result_ref is not None or (
            projection.terminal_condition is OperationTerminalCondition.REFUSED
            and projection.refusal_ref in contract.refusal_detail_codes
        )
        if projection.lifecycle is not OperationLifecycle.TERMINAL or not documented or schema is None:
            raise RelayRefusedError("no_result")
        document = self._client.read_result_document(
            OperationResultProjectionRequestV1(
                operation_id=projection.operation_id,
                terminal_revision=projection.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=schema,
            ),
            timeout=remaining_budget(deadline),
            deadline=deadline,
        )
        if document.get("result_schema") != schema.model_dump(mode="json") or document.get(
            "definition_contract_digest"
        ) != str(contract.definition_contract_digest):
            raise RelayRefusedError("unavailable")
        return {
            "kind": "operation_result",
            "operation_id": operation_id,
            "definition_id": projection.definition_id,
            "document": json.loads(canonical_json_bytes(document)),
        }

    def _pending(self, operation_id: str, *, deadline: float) -> OperationReviewAvailableInteractionV1:
        pending = self._observe(operation_id, 0, deadline=deadline).projection.pending_interaction
        if not isinstance(pending, OperationReviewAvailableInteractionV1):
            raise RelayRefusedError("not_pending")
        return pending

    def _review(
        self, operation_id: str, *, deadline: float
    ) -> tuple[OperationReviewAvailableInteractionV1, dict[str, JsonValue]]:
        pending = self._pending(operation_id, deadline=deadline)
        reply = self._exchange(
            OperationReview(
                request_id=uuid4(),
                profile_id=self._client.profile_id,
                session_id=self._client.session_id,
                review=OperationReviewProjectionRequestV1(reference=pending.review_reference),
            ),
            deadline=deadline,
        )
        if (
            not isinstance(reply, OperationProjected)
            or reply.operation_id != pending.operation_id
            or reply.projection_kind != "review"
            or reply.document.get("outcome") != "success"
        ):
            raise RelayRefusedError("not_pending")
        reference = pending.review_reference
        if reply.document.get("projection_schema") != reference.review_projection_schema.model_dump(
            mode="json"
        ) or reply.document.get("definition_contract_digest") != str(reference.definition_contract_digest):
            raise RelayRefusedError("unavailable")
        document: object = json.loads(canonical_json_bytes(reply.document))
        if not isinstance(document, dict):
            raise RelayRefusedError("unavailable")
        return pending, {str(key): value for key, value in document.items()}

    def _claimable_reviews(self, *, deadline: float) -> dict[str, object]:
        reply = self._exchange(
            OperationClaimableReviews(
                request_id=uuid4(), profile_id=self._client.profile_id, session_id=self._client.session_id
            ),
            deadline=deadline,
        )
        if not isinstance(reply, OperationClaimableReviewsListed):
            raise RelayRefusedError("unavailable")
        return {"kind": "operation_reviews_claimable", "operation_ids": list(reply.operation_ids)}

    def _claim_review(self, operation_id: str, request: Mapping[str, object], *, deadline: float) -> dict[str, object]:
        pending, document = self._review(operation_id, deadline=deadline)
        digest = _text(request["review_digest"])
        if (pending.interaction_id, pending.revision) != (
            _text(request["interaction_id"]),
            _count(request["revision"]),
        ):
            raise RelayRefusedError("not_pending")
        if content_hash_hex(document) != digest:
            raise RelayRefusedError("review_changed")
        reference = pending.review_reference
        reply = self._exchange(
            OperationReviewClaim(
                request_id=uuid4(),
                profile_id=self._client.profile_id,
                session_id=self._client.session_id,
                reference=reference,
                reviewed_document_digest=digest,
            ),
            deadline=deadline,
        )
        if (
            not isinstance(reply, OperationReviewClaimed)
            or reply.reviewed_document_digest != digest
            or reply.reference.model_copy(update={"revision": reference.revision}) != reference
            or reply.reference.revision not in (reference.revision, reference.revision + 1)
            or not {"apply", "reject"}.issubset(reply.allowed_intents)
        ):
            raise RelayRefusedError("unavailable")
        # The claim commits a successor checkpoint. Display its exact current document
        # and use only the coordinates acknowledged by the runtime for the answer.
        successor, document = self._review(operation_id, deadline=deadline)
        if successor.review_reference != reply.reference:
            raise RelayRefusedError("not_pending")
        return {
            "kind": "operation_review_claimed",
            "operation_id": operation_id,
            "interaction_id": successor.interaction_id,
            "revision": successor.revision,
            "expires_at": None if successor.expires_at is None else successor.expires_at.isoformat(),
            "review_digest": content_hash_hex(document),
            "document": document,
        }

    def _respond(self, operation_id: str, request: Mapping[str, object], *, deadline: float) -> dict[str, object]:
        decision = request["decision"]
        if decision not in {"apply", "reject"}:
            raise ValueError("invalid decision")
        answer: Literal["apply", "reject"] = "apply" if decision == "apply" else "reject"
        interaction_id = _text(request["interaction_id"])
        revision = _count(request["revision"])
        digest = _text(request["review_digest"])
        # Read the review again: an answer approves exactly the document the person saw.
        pending, document = self._review(operation_id, deadline=deadline)
        if (pending.interaction_id, pending.revision) != (interaction_id, revision):
            raise RelayRefusedError("not_pending")
        if content_hash_hex(document) != digest:
            raise RelayRefusedError("review_changed")
        profile_id, session_id = self._client.profile_id, self._client.session_id

        def exchange(request: OperationRequest) -> OperationReply:
            return self._exchange(request, deadline=deadline)

        actor_ref = require_registered_response_control(pending, profile_id, session_id, answer, exchange)
        responded_at = datetime.now(UTC)
        mutation = (
            OperationResponseApplyRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=actor_ref,
                responded_at=responded_at,
            )
            if answer == "apply"
            else OperationResponseRejectRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=actor_ref,
                responded_at=responded_at,
            )
        )
        submit_registered_review_response(pending, profile_id, session_id, answer, mutation, exchange)
        return {"kind": "operation_responded", "operation_id": operation_id, "decision": answer}

    def _cancel(self, operation_id: str, expected_revision: int, *, deadline: float) -> dict[str, object]:
        reply = self._exchange(
            OperationManage(
                request_id=uuid4(),
                profile_id=self._client.profile_id,
                session_id=self._client.session_id,
                management=OperationCancellationRequestV1(
                    operation_id=operation_id, expected_revision=expected_revision
                ),
            ),
            deadline=deadline,
        )
        if not isinstance(reply, OperationManaged) or reply.operation_id != operation_id:
            raise RelayRefusedError("unavailable")
        encoded = canonical_json_bytes(reply.document)
        if reply.document.get("outcome") == "refused":
            raise RelayRefusedError(OperationCancellationRefusalV1.model_validate_json(encoded).code.value)
        OperationCancellationSuccessV1.model_validate_json(encoded)
        return {"kind": "operation_cancel_requested", "operation_id": operation_id}


def relay_reply(
    *,
    request_id: UUID,
    profile_id: UUID,
    session_id: UUID,
    runtime_boot_id: UUID,
    connection_id: UUID,
    fields: Mapping[str, object] | None = None,
    refusal: RelayRefusedError | None = None,
) -> dict[str, object]:
    """Build the bridge line answering one relay action: its fields, or its closed refusal."""
    document: dict[str, object] = {
        "request_id": str(request_id),
        "profile_id": str(profile_id),
        "session_id": str(session_id),
        "runtime_boot_id": str(runtime_boot_id),
        "connection_id": str(connection_id),
    }
    if refusal is not None:
        return {
            "kind": "operation_refused",
            **document,
            "code": refusal.code,
            "holder_operation_id": refusal.holder_operation_id,
        }
    if fields is None or "kind" not in fields:
        raise ValueError("a relay reply carries its fields or a refusal")
    return {**document, **fields}


__all__ = [
    "RELAY_ACTION_KEYS",
    "OperationRelay",
    "RelayRefusedError",
    "relay_reply",
]
