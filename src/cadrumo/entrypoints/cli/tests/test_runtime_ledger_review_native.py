"""Real Windows worker reviews against a controlled loopback inference endpoint.

No inference or live provider runs. Only HTTP answers are authored: provider
clients/parsers, immutable profile workers, encrypted review continuations and
canonical ledger writes are real. The shared fixture explicitly enables the
development session override and uses a synthetic native secret store; this is
not desktop/custody acceptance.
"""

from __future__ import annotations

import base64
import json
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import override

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.login_session import login_profile
from ....core.config import load_settings, reset_settings_cache
from ....domain.buckets.event import BucketEvent, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ....domain.transactions.models import TransactionCatalogue
from ....tests.cli_envelope import unwrap_cli_result
from ....tests.llm_vision_evidence_support import json_array, json_object, png_image
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ....tests.pdf_fixtures import text_pdf_bytes
from ._ledger_llm_support import _PROFILE_FACTS
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


@dataclass(frozen=True)
class _Answer:
    content: str
    images: bool = False


@dataclass
class _EndpointState:
    answers: dict[str, _Answer] = field(default_factory=dict)
    arriving: Queue[dict[str, object]] = field(default_factory=Queue)
    observed: list[dict[str, object]] = field(default_factory=list)
    unexpected: Queue[str] = field(default_factory=Queue)

    def posts(self) -> list[dict[str, object]]:
        """Collect completed real HTTP requests without discarding earlier evidence."""
        while not self.arriving.empty():
            self.observed.append(self.arriving.get_nowait())
        assert self.unexpected.empty(), "unexpected loopback provider request"
        return list(self.observed)


@dataclass(frozen=True)
class _Snapshot:
    catalogue: TransactionCatalogue
    events: tuple[BucketEvent, ...]


@dataclass(frozen=True)
class _NativeReview:
    profile: NativeCliProfileFixture
    operation: PinnedAuthorityOperation
    endpoint: _EndpointState

    def invoke(self, *command: str) -> Result:
        """Admit the exact registered profile using the canonical protected stdin."""
        assert self.profile.label is not None
        close_active_bucket_session()
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                "json",
                "--profile",
                self.profile.label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": self.profile.passphrase}),
        )
        assert self.profile.passphrase not in result.output
        return result

    def snapshot(self) -> _Snapshot:
        """Decrypt canonical data with a separate password session as the oracle."""
        assert self.profile.label is not None
        close_active_bucket_session()
        login = login_profile(
            name=self.profile.label,
            passphrase_callback=lambda: self.profile.passphrase,
            profile_decode_context=self.operation.profile_decode_context(),
        )
        try:
            catalogue = TransactionCatalogueRepository(bucket_id=login.bucket_id).load()
            # Password observation emits login events. Compare ledger domain
            # events only, so a successful login cannot look like a row write.
            events = tuple(
                sorted(
                    (
                        event
                        for event in BucketEventHistoryRepository().load().events.values()
                        if event.event_type.value.startswith("ledger.")
                    ),
                    key=lambda event: event.event_id,
                )
            )
            assert all(event.bucket_id == login.bucket_id for event in events)
            return _Snapshot(catalogue, events)
        finally:
            close_active_bucket_session()


@pytest.fixture
def native_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> Iterator[_NativeReview]:
    """Configure a real socket before the isolated native worker is created."""
    state = _EndpointState()
    configured = load_settings()
    models = (configured.cadrumo_llm_ollama_text_model, configured.cadrumo_llm_ollama_vision_model)

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            if self.path == "/api/ps":
                # This endpoint loads no weights and has no resident models.
                payload: dict[str, object] = {"models": []}
            elif self.path == "/api/tags":
                payload = {"models": [{"name": model, "model": model, "size": 0} for model in models]}
            else:
                state.unexpected.put(self.path)
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            write_json_response(self, payload, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            body = dict(read_json_body(self))
            state.arriving.put(body)
            matches = [answer for marker, answer in state.answers.items() if marker in json.dumps(body)]
            if self.path != "/api/chat" or len(matches) != 1:
                state.unexpected.put("unmatched chat request")
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            answer = matches[0]
            write_json_response(
                self,
                ollama_chat_reply(answer.content, model=str(body["model"]), prompt_eval_count=12, eval_count=4),
                status=HTTPStatus.OK,
            )

    try:
        with serving_loopback(_Endpoint, path="/api/chat") as endpoint, monkeypatch.context() as environment:
            environment.setenv("CADRUMO_LLM_OLLAMA_CHAT_URL", endpoint)
            # Documented operator override admits an unmeasurable accelerator;
            # it still refuses measured shortfalls. This server loads no model.
            environment.setenv("CADRUMO_LLM_CONTENTION_CHECK_OVERRIDE", "true")
            environment.setenv("CADRUMO_LLM_CONTENTION_SAFETY_MARGIN_BYTES", "0")
            reset_settings_cache()
            with native_cli_profile_scope(tmp_path) as profile:
                profile.register(label="native-ledger-reviewed-provider", facts=_PROFILE_FACTS)
                yield _NativeReview(profile, authority_operation, state)
    finally:
        reset_settings_cache()


def _classification_answer(*, saturated: bool = False) -> _Answer:
    values: dict[str, object] = {
        "classification": "BUSINESS",
        "category": "material_oficina",
        "confidence": "0.9",
        "reason": "Synthetic supplier purchase selected from the published vocabulary",
    }
    if saturated:
        values["iva_category"] = "domestic_general"
    return _Answer(json.dumps(values))


def _split_answer(*, single: bool = False) -> _Answer:
    children = [
        {
            "proportion": "1" if single else "0.6",
            "category": "material_oficina",
            "iva_category": "domestic_general",
            "evidence_citation": "synthetic office line",
        },
    ]
    if not single:
        children.append(
            {
                "proportion": "0.4",
                "category": "software_suscripcion",
                "iva_category": "domestic_general",
                "evidence_citation": "synthetic licence line",
            }
        )
    return _Answer(json.dumps({"children": children, "reason": "Synthetic image line selection"}), images=True)


def _success(result: Result) -> dict[str, object]:
    assert result.exit_code == 0, result.output
    return dict(unwrap_cli_result(result))


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _add(review: _NativeReview, marker: str) -> str:
    result = _success(
        review.invoke(
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            marker,
            "--source-jurisdiction",
            "ES",
            "--idempotency-key",
            marker,
        )
    )
    return _text(result["transaction_id"])


def _attach(review: _NativeReview, transaction_id: str, source: Path) -> str:
    evidence = _success(review.invoke("app", "ledger", "evidence", "add", str(source), "--supplier", "Synthetic SL"))
    evidence_id = _text(evidence["evidence_id"])
    _success(review.invoke("app", "ledger", "attach", transaction_id, "--purchase-invoice-evidence-id", evidence_id))
    return evidence_id


def _provider_once(
    review: _NativeReview,
    marker: str,
    *command: str,
    expected_posts: int = 1,
) -> dict[str, object]:
    before = len(review.endpoint.posts())
    result = _success(review.invoke(*command))
    posts = review.endpoint.posts()
    # Identical preview/apply acquisition uses the canonical encrypted cache.
    # Fresh requests reach HTTP once; a resumed decision never adds another POST.
    assert len(posts) == before + expected_posts
    request = posts[-1]
    assert marker in json.dumps(request)
    assert request["stream"] is False
    messages = [json_object(message) for message in json_array(request["messages"])]
    has_images = any(bool(message.get("images")) for message in messages)
    assert has_images is review.endpoint.answers[marker].images
    assert request["model"] in {
        load_settings().cadrumo_llm_ollama_text_model,
        load_settings().cadrumo_llm_ollama_vision_model,
    }
    return result


def _new_events(before: _Snapshot, after: _Snapshot) -> tuple[BucketEvent, ...]:
    prior = {event.event_id for event in before.events}
    return tuple(event for event in after.events if event.event_id not in prior)


def test_native_classification_review_evidence_rejection_and_saturation(
    native_review: _NativeReview,
    tmp_path: Path,
) -> None:
    """Real registered reviews preserve no-write previews and canonical durable outcomes."""
    review = native_review
    marker = "native-basic-classification"
    review.endpoint.answers[marker] = _classification_answer()
    transaction_id = _add(review, marker)
    before = review.snapshot()
    incompatible = review.invoke("app", "ledger", "classify", transaction_id, "--llm", "--classification", "BUSINESS")
    assert incompatible.exit_code != 0
    assert review.endpoint.posts() == []
    assert review.snapshot() == before

    preview = _provider_once(review, marker, "app", "ledger", "classify", transaction_id, "--llm")
    assert preview["persisted"] is False
    assert preview["classification"] == "BUSINESS"
    assert preview["category"] == "material_oficina"
    assert review.snapshot() == before
    _provider_once(review, marker, "app", "ledger", "classify", transaction_id, "--llm", "--apply", expected_posts=0)
    applied = review.snapshot()
    row = applied.catalogue.transactions[transaction_id]
    assert row.business_classification is BusinessClassification.BUSINESS
    assert row.category_id == "material_oficina"
    assert row.classified_by == preview["provenance"]
    assert [event.event_type for event in _new_events(before, applied)] == [
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED
    ]

    rejected_marker = "native-rejected-classification"
    review.endpoint.answers[rejected_marker] = _classification_answer()
    rejected_id = _add(review, rejected_marker)
    before_reject = review.snapshot()
    rejection = _provider_once(review, rejected_marker, "app", "ledger", "classify", rejected_id, "--llm", "--reject")
    after_reject = review.snapshot()
    assert rejection["rejected"] is True and rejection["persisted"] is False
    assert after_reject.catalogue == before_reject.catalogue
    events = _new_events(before_reject, after_reject)
    assert len(events) == 1
    assert events[0].event_type is BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED
    assert events[0].event_id == rejection["bucket_event_id"]
    assert events[0].object_id == rejected_id

    evidence_marker = "native-text-evidence-classification"
    review.endpoint.answers[evidence_marker] = _classification_answer()
    evidence_id = _add(review, evidence_marker)
    pdf = tmp_path / "synthetic-review.pdf"
    printed_marker = "UNIQUE PRINTED SYNTHETIC INVOICE LINE"
    pdf.write_bytes(text_pdf_bytes((printed_marker, "Base 100,00 IVA 21,00 Total 121,00")))
    linked = _attach(review, evidence_id, pdf)
    before_saturate = review.snapshot()
    _provider_once(review, evidence_marker, "app", "ledger", "classify", evidence_id, "--llm", "--read-evidence")
    assert printed_marker in json.dumps(review.endpoint.posts()[-1])
    assert review.snapshot() == before_saturate
    review.endpoint.answers[evidence_marker] = _classification_answer(saturated=True)
    saturated = _provider_once(
        review,
        evidence_marker,
        "app",
        "ledger",
        "classify",
        evidence_id,
        "--llm",
        "--read-evidence",
        "--saturate",
    )
    assert saturated["rate_derivable"] is True
    assert Decimal(_text(saturated["taxable_base"])) == Decimal("100")
    assert Decimal(_text(saturated["iva_amount"])) == Decimal("21")
    assert review.snapshot() == before_saturate
    saturated_apply = _provider_once(
        review,
        evidence_marker,
        "app",
        "ledger",
        "classify",
        evidence_id,
        "--llm",
        "--read-evidence",
        "--saturate",
        "--apply",
        expected_posts=0,
    )
    after_saturate = review.snapshot()
    row = after_saturate.catalogue.transactions[evidence_id]
    assert row.taxable_base == Decimal("100") and row.iva_amount == Decimal("21")
    assert row.iva_rate == Decimal("0.21")
    assert row.iva_category is not None and row.iva_category.value == "domestic_general"
    assert row.purchase_invoice_evidence_id == linked
    assert row.classified_by == saturated["provenance"]
    events = _new_events(before_saturate, after_saturate)
    assert len(events) == 2
    assert Counter(event.event_type for event in events) == Counter(
        {
            BucketEventType.LEDGER_TRANSACTION_UPDATED: 1,
            BucketEventType.LEDGER_TRANSACTION_CLASSIFIED: 1,
        },
    )
    assert len({event.event_id for event in events}) == 2
    assert Counter(event.event_id for event in events) == Counter(
        _text(value) for value in json_array(saturated_apply["bucket_event_ids"])
    )
    for event in events:
        assert event.bucket_id == before_saturate.events[0].bucket_id
        assert event.object_type.value == "ledger_transaction" and event.object_id == evidence_id
        assert event.payload["previous_transaction_id"] == evidence_id
        assert event.payload["source_command"] == "aeat app ledger classify --llm --saturate --apply"
        assert event.payload["mutation_kind"] == (
            "edit" if event.event_type is BucketEventType.LEDGER_TRANSACTION_UPDATED else "classification"
        )
        if event.event_type is BucketEventType.LEDGER_TRANSACTION_CLASSIFIED:
            assert event.payload["classification"] == "BUSINESS"
            assert event.payload["category_id"] == "material_oficina"

    invalid_marker = "native-invalid-provider-selection"
    invalid_id = _add(review, invalid_marker)
    review.endpoint.answers[invalid_marker] = _Answer(
        json.dumps(
            {
                "classification": "BUSINESS",
                "category": "not_a_published_spending_category",
                "confidence": "0.9",
                "reason": "Synthetic malformed selection",
            }
        )
    )
    before_invalid = review.snapshot()
    calls = len(review.endpoint.posts())
    invalid = review.invoke("app", "ledger", "classify", invalid_id, "--llm", "--apply")
    assert invalid.exit_code != 0, invalid.output
    assert len(review.endpoint.posts()) == calls + 1
    assert review.snapshot() == before_invalid


@pytest.mark.parametrize("route", ["auto_split", "split"])
def test_native_image_split_review_and_atomic_children(
    native_review: _NativeReview,
    tmp_path: Path,
    route: str,
) -> None:
    """Both real review definitions persist one coherent evidence-linked child cohort."""
    review = native_review
    marker = f"native-image-{route}-parent"
    review.endpoint.answers[marker] = _split_answer()
    parent_id = _add(review, marker)
    image = tmp_path / "synthetic-review.png"
    image.write_bytes(png_image())
    linked = _attach(review, parent_id, image)
    command = (
        ("app", "ledger", "classify", parent_id, "--read-evidence", "--auto-split")
        if route == "auto_split"
        else ("app", "ledger", "split", parent_id, "--llm", "--read-evidence")
    )
    before = review.snapshot()
    if route == "split":
        refused = review.invoke(*command, "--apply")
        assert refused.exit_code != 0
        assert review.endpoint.posts() == []
        assert review.snapshot() == before
    preview = _provider_once(review, marker, *command)
    assert preview["persisted"] is False
    assert preview["parent_transaction_id"] == parent_id
    assert review.snapshot() == before
    proposed = [json_object(item) for item in json_array(preview["proposed_children"])]
    assert len(proposed) == 2
    assert [Decimal(_text(item["amount"])) for item in proposed] == [Decimal("72.60"), Decimal("48.40")]
    messages = [json_object(message) for message in json_array(review.endpoint.posts()[-1]["messages"])]
    images = [_text(encoded) for message in messages for encoded in json_array(message.get("images", []))]
    assert len(images) == 1 and base64.b64decode(images[0], validate=True) == image.read_bytes()
    applied = _provider_once(
        review,
        marker,
        *command,
        "--apply",
        *(("--yes",) if route == "split" else ()),
        expected_posts=0,
    )
    assert applied["persisted"] is True
    after = review.snapshot()
    child_ids = tuple(_text(value) for value in json_array(applied["child_transaction_ids"]))
    assert len(child_ids) == 2
    assert len(set(child_ids)) == 2
    parent = after.catalogue.transactions[parent_id]
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
    assert parent.split_lineage is not None
    assert parent.split_lineage.split_group_id == applied["split_group_id"]
    assert set(parent.split_lineage.sibling_transaction_ids) == set(child_ids)
    children = [after.catalogue.transactions[child_id] for child_id in child_ids]
    assert sum((child.raw.amount for child in children), Decimal("0")) == parent.raw.amount
    assert len(after.catalogue.transactions) == len(before.catalogue.transactions) + 2
    for child in children:
        assert child.lifecycle_state is TransactionLifecycleState.ACTIVE
        assert child.business_classification is BusinessClassification.BUSINESS
        assert child.purchase_invoice_evidence_id == linked
        assert child.classified_by == preview["provenance"]
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == abs(child.raw.amount)
        assert child.iva_rate == Decimal("0.21")
    events = _new_events(before, after)
    assert sum(event.event_type is BucketEventType.LEDGER_TRANSACTION_SPLIT for event in events) == 1
    classified_ids = {
        event.object_id for event in events if event.event_type is BucketEventType.LEDGER_TRANSACTION_CLASSIFIED
    }
    assert classified_ids == set(child_ids)

    if route == "auto_split":
        single_marker = "native-image-single-line-parent"
        review.endpoint.answers[single_marker] = _split_answer(single=True)
        single_id = _add(review, single_marker)
        _attach(review, single_id, image)
        before_single = review.snapshot()
        command = ("app", "ledger", "classify", single_id, "--read-evidence", "--auto-split")
        single_preview = _provider_once(review, single_marker, *command)
        assert single_preview["persisted"] is False
        assert single_preview["classification"] == "BUSINESS"
        assert review.snapshot() == before_single
        single_apply = _provider_once(review, single_marker, *command, "--apply", expected_posts=0)
        after_single = review.snapshot()
        assert len(after_single.catalogue.transactions) == len(before_single.catalogue.transactions)
        single = after_single.catalogue.transactions[single_id]
        assert single.lifecycle_state is TransactionLifecycleState.ACTIVE
        assert single.business_classification is BusinessClassification.BUSINESS
        assert single.taxable_base == Decimal("100") and single.iva_amount == Decimal("21")
        assert single.classified_by == single_preview["provenance"]
        events = _new_events(before_single, after_single)
        assert len(events) == 2
        assert Counter(event.event_type for event in events) == Counter(
            {
                BucketEventType.LEDGER_TRANSACTION_UPDATED: 1,
                BucketEventType.LEDGER_TRANSACTION_CLASSIFIED: 1,
            },
        )
        assert len({event.event_id for event in events}) == 2
        assert Counter(event.event_id for event in events) == Counter(
            _text(value) for value in json_array(single_apply["bucket_event_ids"])
        )
        for event in events:
            assert event.bucket_id == before_single.events[0].bucket_id
            assert event.object_type.value == "ledger_transaction" and event.object_id == single_id
            assert event.payload["previous_transaction_id"] == single_id
            assert event.payload["source_command"] == "aeat app ledger classify --read-evidence --auto-split --apply"
            assert event.payload["mutation_kind"] == (
                "edit" if event.event_type is BucketEventType.LEDGER_TRANSACTION_UPDATED else "classification"
            )
            if event.event_type is BucketEventType.LEDGER_TRANSACTION_CLASSIFIED:
                assert event.payload["classification"] == "BUSINESS"
                assert event.payload["category_id"] == "material_oficina"
