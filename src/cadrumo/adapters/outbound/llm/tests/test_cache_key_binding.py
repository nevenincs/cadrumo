"""A cached entry must belong to the row it was read out of.

``LLMCache`` derives its secure-object key from the request, so the key
identifies the entry — but until the binding check existed, nothing tied the
DECRYPTED payload back to it. A valid entry re-encrypted under another entry's
row was returned verbatim, so a caller asking for one provider and model could
be answered with another's text and ``cache_hit`` set. Decrypting proves
custody of the bucket key; it never proves the row holds what was asked for.

The tamper here re-encrypts a genuine entry B under entry A's associated data,
which is the exact shape a substituted row takes: every layer beneath the cache
— the AAD, the schema version, the sensitivity class, the logical partition —
still agrees, so only an identity check at the cache boundary can catch it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....llm.errors import LLMCacheError
from .....llm.models import LLMProvider, LLMRequest, LLMResponse
from .._cache import _CACHE_NAMESPACE, LLMCache
from ._engine_binding_fixtures import _ENGINE_HOLDER, _bind_engine  # noqa: F401

# The encrypted-SQL substrate is imported inside the helpers below, matching
# the sibling round-trip proof. Pulling ``adapters.persistence.storage`` in at
# module scope from this package resolves it before ``cadrumo.core`` has
# finished initialising and the settings load inside it fails on a partially
# initialised core — an import-order artefact of the test module, not of the
# code under test.

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CREATED_AT = datetime(2026, 5, 28, 12, 30, 0, tzinfo=UTC)

_REQUEST_A = LLMRequest(prompt="Explain casilla 03.", temperature=0.0, language="es")
_REQUEST_B = LLMRequest(prompt="Explain casilla 04.", temperature=0.0, language="es")


def _response(provider: LLMProvider, model: str, text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        provider=provider,
        model=model,
        input_tokens=11,
        output_tokens=7,
        cost_estimate_usd=Decimal("0.0031"),
        cache_hit=False,
        created_at=_CREATED_AT,
        request_id="b" * 64,
    )


_RESPONSE_A = _response(LLMProvider.ANTHROPIC, "claude-opus-4-7", "ANSWER-FOR-A")
_RESPONSE_B = _response(LLMProvider.OPENAI, "gpt-model-b", "TAMPERED-B")


def _repository_engine():
    return _ENGINE_HOLDER[0]


def _row_payload(model: str) -> bytes:
    """Return the plaintext of the cache row holding ``model``'s entry.

    Rows are identified by decrypting each payload and reading the entry's own
    model, not by a WHERE clause on ``object_key``: that column is a
    hashed-lookup type, so its stored bytes are a digest rather than the key
    and a raw-bytes predicate is not a narrower query but a different one.
    """
    from sqlalchemy import select

    from ....persistence.storage.crypto.encrypted_columns import (
        decrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....persistence.storage.sql import SecureObjectRow
    from ....persistence.storage.sql.session import session_scope

    with session_scope(_repository_engine()) as session:
        for row in session.execute(
            select(SecureObjectRow).where(SecureObjectRow.namespace == _CACHE_NAMESPACE),
        ).scalars():
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            plaintext = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
            if json.loads(plaintext.decode("utf-8"))["entry"]["model"] == model:
                return plaintext
    raise AssertionError(f"no cache row holds an entry for model {model!r}")


def _substitute_row(*, victim_model: str, donor_model: str) -> None:
    """Re-encrypt the donor row's genuine plaintext under the victim row's identity."""
    from sqlalchemy import select

    from ....persistence.storage.crypto.encrypted_columns import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ....persistence.storage.sql import SecureObjectRow
    from ....persistence.storage.sql.session import session_scope

    donor_plaintext = _row_payload(donor_model)
    with session_scope(_repository_engine()) as session:
        for row in session.execute(
            select(SecureObjectRow).where(SecureObjectRow.namespace == _CACHE_NAMESPACE),
        ).scalars():
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            plaintext = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
            if json.loads(plaintext.decode("utf-8"))["entry"]["model"] != victim_model:
                continue
            row.payload = encrypt_secure_object_payload(donor_plaintext, associated_data=aad)
            return
    raise AssertionError(f"no cache row holds an entry for model {victim_model!r}")


def test_a_foreign_entry_re_encrypted_under_another_row_is_refused(tmp_path: Path) -> None:
    """The substituted row raises instead of answering with the foreign response.

    Before the binding check this returned ``TAMPERED-B`` for a request whose
    key names the Anthropic entry — a wrong-answer failure rather than a
    detected one.
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    cache.write(_REQUEST_A, _RESPONSE_A)
    cache.write(_REQUEST_B, _RESPONSE_B)

    _substitute_row(victim_model=_RESPONSE_A.model, donor_model=_RESPONSE_B.model)

    with pytest.raises(LLMCacheError):
        cache.read(_REQUEST_A, _RESPONSE_A.provider, _RESPONSE_A.model)


def test_the_substitution_really_lands_a_valid_foreign_entry(tmp_path: Path) -> None:
    """The tamper's positive control: the substituted bytes decode cleanly.

    Without this the refusal above could be earned by a corrupted payload
    failing to parse, which would prove the pre-existing parse guard rather
    than the new identity check. Here the row's plaintext is asserted to be a
    well-formed entry for the OTHER key, so the only thing left to reject it
    is the binding.
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    cache.write(_REQUEST_A, _RESPONSE_A)
    cache.write(_REQUEST_B, _RESPONSE_B)

    _substitute_row(victim_model=_RESPONSE_A.model, donor_model=_RESPONSE_B.model)

    # Both rows now carry B's entry; either lookup returns the substituted
    # plaintext, which is the point — A's row no longer holds A's entry.
    plaintext = _row_payload(_RESPONSE_B.model)
    decoded = json.loads(plaintext.decode("utf-8"))

    # Same logical partition, so the pre-existing partition guard cannot be
    # what refuses; a complete, parseable entry, so the parse guard cannot be
    # either.
    assert decoded["logical_root"] == cache._logical_root()
    entry = cache._entry_from_payload(plaintext)
    assert entry.provider is _RESPONSE_B.provider
    assert entry.model == _RESPONSE_B.model
    assert entry.response.text == "TAMPERED-B"


def test_an_untampered_entry_still_reads_back(tmp_path: Path) -> None:
    """The binding must not turn every legitimate hit into a refusal.

    The stored payload is redacted before persistence, so this also proves no
    redaction rule rewrites a key-bearing field — which would file every row
    under a key nothing could derive and turn the cache into a permanent miss.
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    cache.write(_REQUEST_A, _RESPONSE_A)
    cache.write(_REQUEST_B, _RESPONSE_B)

    hit_a = cache.read(_REQUEST_A, _RESPONSE_A.provider, _RESPONSE_A.model)
    hit_b = cache.read(_REQUEST_B, _RESPONSE_B.provider, _RESPONSE_B.model)

    assert hit_a is not None
    assert hit_a.text == "ANSWER-FOR-A"
    assert hit_a.provider is _RESPONSE_A.provider
    assert hit_b is not None
    assert hit_b.text == "TAMPERED-B"
    assert hit_b.provider is _RESPONSE_B.provider


def test_a_substituted_row_does_not_escape_retention_pruning(tmp_path: Path) -> None:
    """Pruning keys rows off the decoded entry, so it must still reach the row.

    A substituted row decodes to the donor's identity, and pruning that
    reconstructs a key from the decoded entry would then delete the donor's
    row (or nothing) and leave the substituted one stored forever. Both cache
    entries are older than a zero-day retention window, so a correct prune
    empties the namespace.
    """
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    cache.write(_REQUEST_A, _RESPONSE_A)
    cache.write(_REQUEST_B, _RESPONSE_B)
    assert cache.stats().entries == 2

    cache.prune(retention_days=0, max_records=0)

    assert cache.stats().entries == 0
