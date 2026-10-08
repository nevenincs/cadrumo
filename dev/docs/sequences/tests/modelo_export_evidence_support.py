"""Canonical event derivation shared by the recorded export evidence tests."""

from __future__ import annotations

from typing import cast

from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType, derive_bucket_event_id

from ..runner import SequenceTranscript


def changed_modelo_export_event(
    transcript: SequenceTranscript,
    *,
    destination: str | None = None,
    actor: str = "docs-sequence-sandbox",
    unsupported: bool = False,
) -> str:
    """Use canonical domain derivation; public evidence alone is never sufficient for hidden branches."""
    frame = transcript.result_frame
    assert frame.envelope is not None and isinstance(frame.envelope["result"], dict)
    result = frame.envelope["result"]
    period = result["period"]
    assert isinstance(period, dict)
    prior = result["prior_domiciliation_election"]
    assert isinstance(prior, dict)
    payload = {
        "calculation_revision_id": cast(str, result["calculation_revision_id"]),
        "work_unit_id": cast(str, result["work_unit_id"]),
        "output_path": destination or cast(str, result["output_path"]),
        "byte_size": str(result["byte_size"]),
        "file_sha256": cast(str, result["file_sha256"]),
        "format": cast(str, result["format"]),
        "modelo": cast(str, result["modelo"]),
        "filing_year": str(result["filing_year"]),
        "period": cast(str, period["code"]),
        "prior_domiciliation_election": cast(str, prior["election"]),
    }
    for key in ("resolved_result_disposition", "payment_election", "refund_election"):
        if result[key] is not None:
            payload[key] = cast(str, result[key])
    wallet = result.get("iva_wallet_decision_provenance")
    if isinstance(wallet, dict):
        target_period = wallet["target_period"]
        kinds, refs = wallet["authority_source_kinds"], wallet["authority_source_refs"]
        assert isinstance(target_period, dict) and isinstance(kinds, list) and isinstance(refs, list)
        assert all(isinstance(value, str) for value in (*kinds, *refs))
        payload.update(
            {
                "iva_wallet_decision_ref": cast(str, wallet["decision_ref"]),
                "iva_wallet_selected_authority": cast(str, wallet["selected_authority"]),
                "iva_wallet_divergence": cast(str, wallet["divergence"]),
                "iva_wallet_target_year": str(wallet["target_year"]),
                "iva_wallet_target_period": cast(str, target_period["code"]),
                "iva_wallet_authority_source_kinds": ",".join(cast(str, value) for value in kinds),
                "iva_wallet_authority_source_refs": ",".join(cast(str, value) for value in refs),
            }
        )
    if unsupported:
        payload["selected_account_role"] = "charge"
        payload["selected_own_account_id"] = "private-account-reference"
    return derive_bucket_event_id(
        bucket_id=transcript.profile_id,
        event_type=BucketEventType.MODELO_EXPORTED,
        occurred_at=transcript.frozen_instant,
        actor=actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=cast(str, result["calculation_revision_id"]),
        payload=payload,
    )
