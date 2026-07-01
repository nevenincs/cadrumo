"""D1 golden scenario: the ledger-evidence add ``--format json`` envelope is deterministic.

The completing proof for Decision 1 (content-address evidence_id): capturing
`ledger.evidence.add`'s emitted envelope across two fresh-bucket runs of the same
add — same file, same fields, same injected profile identity, same frozen instant
— yields a byte-identical envelope with ZERO residual differing fields, because
the content-addressed evidence_id, the content-addressed bucket-event id, and the
frozen-clock timestamps are all deterministic. This confirms no new
`GOLDEN_MASK_FIELDS` entry is warranted for the referenced id (the ADR's
mask-only-as-fallback clause is not triggered).

Distinct from the D4 axis's ledger-add retried-no-op case. Lives at the
entrypoints test surface (not application/ledger/tests) so the registered
`EvidenceAddResult` schema is a same-package import rather than a cross-package
private import — the same placement rationale as the D4 axis.

Real-behaviour: a real PurchaseInvoiceEvidenceService against a real encrypted
bucket runtime, the real registered schema, and the real emit path; the committed
fixture is a synthetic PDF only.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.ledger import PurchaseInvoiceEvidenceService
from ....core.json_contract import emit_json_success
from ....core.observability import (
    canonicalise,
    capture_envelopes,
    differing_field_names,
    differing_paths,
)
from ....core.time import frozen_clock
from ....domain.buckets import BucketEventHistoryRepository
from ....tests.secure_sql import isolated_runtime_profile
from .._ledger_payloads import EvidenceAddResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)
_BUCKET = "2a2a2a2a-2a2a-4a2a-8a2a-2a2a2a2a2a2a"
_COMMAND = "ledger.evidence.add"


def _capture_evidence_add_envelope(storage_root: Path, pdf: Path) -> dict[str, object]:
    """Drive one real ledger evidence add in a fresh bucket and capture its envelope.

    Builds the EvidenceAddResult exactly as the CLI leaf does (record dump +
    bucket_event_ids) and emits it through the real success-envelope path under a
    capture sink. All storage ops stay inside one frozen_clock block (a write under
    a frozen clock resets the session idle deadline to that instant).
    """
    with isolated_runtime_profile(tmp_path=storage_root, bucket_id=_BUCKET) as profile, frozen_clock(_INSTANT):
        service = PurchaseInvoiceEvidenceService(
            settings=profile.settings,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        )
        result = service.add(
            bucket_id=profile.bucket_id,
            source_path=pdf,
            supplier="Acme S.L.",
            invoice_number="INV-001",
            invoice_date="2026-01-15",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            notes="office supplies",
        )
        payload = result.record.model_dump(mode="json")
        payload["bucket_event_ids"] = list(result.bucket_event_ids)
        with capture_envelopes() as sink:
            emit_json_success(_COMMAND, EvidenceAddResult.model_validate(payload), stream=io.StringIO())
        return sink[-1]


def test_evidence_add_envelope_is_byte_identical_across_fresh_runs(tmp_path: Path) -> None:
    # One synthetic PDF, reused across both runs so source_path is identical; each
    # run is a fresh bucket, so the content-addressed evidence_id derives with
    # disambiguator 0 in both (no collision to disambiguate) and matches.
    pdf = tmp_path / "receipt.pdf"
    pdf.write_bytes(b"%PDF-1.4 determinism")

    first = _capture_evidence_add_envelope(tmp_path / "run-a", pdf)
    second = _capture_evidence_add_envelope(tmp_path / "run-b", pdf)

    # The whole --format json envelope is deterministic — no field flaps, so no
    # masking is required and no GOLDEN_MASK_FIELDS entry is warranted.
    assert differing_paths(first, second) == frozenset()
    assert differing_field_names(first, second) == frozenset()
    assert canonicalise(first) == canonicalise(second)
