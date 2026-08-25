"""In-memory reading needs no encryption and no consent gate.

Pins the operator ruling of 2026-08-06 as an executable gate rather than as
prose, because prose carries none and nothing fails when it goes stale.

**The ruling, and the line it does not cross.** A user who points a *local*
tool at a file has by that action accepted the file will be processed, and the
secure-storage rule governs how data is STORED inside the product rather than
what a local processor reads -- that rule already permits decrypted bytes to
exist "transiently in process memory". So reading, rasterising and local
inference over in-flight bytes require no encryption, no consent prompt and no
custody wrapper.

What the exemption does NOT reach is enumerated in the same rule and in terms
that bear directly on a reading path: "no temp files, no scratch directories,
no plaintext side stores, no on-disk caches, no logs." Anything DURABLE returns
to the core's encrypted storage. The rule's own worked failure is exactly this
shape -- an early design routed decrypted bytes through a temp file for a
subprocess to read by path, and it was rejected -- so an exemption for
in-memory bytes cannot be read as reopening the temp-file question.

These tests therefore guard in BOTH directions. A later agent must not
reintroduce custody ceremony the operator ruled unnecessary, and must not read
the exemption as permission to persist.
"""

from __future__ import annotations

import inspect
from hashlib import sha256

import pytest

from ..evidence_input import EvidenceInput

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PDF_BYTES = b"%PDF-1.7\nin-flight evidence bytes\n"


def _evidence() -> EvidenceInput:
    return EvidenceInput(
        mime_type="application/pdf",
        data=_PDF_BYTES,
        content_sha256=sha256(_PDF_BYTES).hexdigest(),
        evidence_id="ev_inflight",
        attachment_id=None,
    )


def test_in_flight_bytes_are_readable_with_no_consent_gate_and_no_unwrapping() -> None:
    """Constructing and reading in-flight evidence takes no capability check.

    The positive half of the ruling. If a later change adds a consent prompt,
    a capability toggle or a custody wrapper to this path, this test is what
    fails -- the read must stay a plain attribute access on plain bytes.
    """
    evidence = _evidence()

    assert evidence.data == _PDF_BYTES
    assert isinstance(evidence.data, bytes)
    assert evidence.content_sha256 == sha256(_PDF_BYTES).hexdigest()


def test_the_resolver_signature_carries_no_consent_or_acknowledgement_parameter() -> None:
    """No parameter on the in-flight construction path gates reading on consent.

    Structural rather than behavioural on purpose: a consent gate reintroduced
    as an optional parameter defaulting to permissive would pass a behavioural
    test while re-establishing exactly the ceremony the ruling removed.
    """
    parameters = set(inspect.signature(EvidenceInput).parameters)

    forbidden = {name for name in parameters if any(token in name for token in ("consent", "acknowledg", "permitted"))}
    assert forbidden == set(), f"in-flight reading must need no consent parameter; found {sorted(forbidden)}"


def test_the_in_flight_record_still_refuses_to_serialize() -> None:
    """The exemption covers PROCESSING, never PERSISTENCE.

    The other half of the ruling, and the one a later reader is most likely to
    get wrong. Decrypted bytes may live in memory freely; the moment anything
    tries to turn them into a durable artefact the tripwires must fire. A
    version of this record that serialized cleanly would let an exemption about
    in-memory reading quietly authorise a plaintext side store.
    """
    evidence = _evidence()

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        evidence.model_dump()

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        evidence.model_dump_json()
