"""Labelled key derivation and keyed digests over a caller-owned secret.

An unkeyed hash is not a redaction when its preimage is enumerable. A Spanish
tax identifier has about ten million plausible values, so anybody holding
``sha256(nif)`` recovers the identifier by trying them all. A digest keyed with
a secret the holder of the artefact does not have is the only construction that
carries a reference forward without carrying the identity forward with it.

This module owns exactly two primitives, and no policy: derive a subkey from
key material under a domain-separating label, and take a keyed digest of a
message. Deciding which secret to derive from, which label names the purpose,
and which values get digested belongs to the caller -- the same split
:mod:`cadrumo.core.ed25519_signing` keeps against its signing surface, so a
custody rule can never arrive here by accident.

Derivation is HKDF-SHA256 with an empty salt and a caller-supplied ``info``
label. The label is what separates purposes: two subkeys derived from one secret
under different labels are computationally unrelated, so a digest produced for
one purpose cannot be replayed as a digest for another. The salt is empty
deliberately -- a salt buys extraction strength for low-entropy input key
material, and every caller here derives from a uniformly random secret, where
the label alone carries the separation that matters.

See Also:
    :mod:`cadrumo.application.modelo.calculation_report_provenance_key`
        The calculation report's labelled provenance key, built on these two.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Final

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

DERIVED_KEY_BYTES: Final[int] = 32
"""Width of a derived subkey, matching the SHA-256 block digest it keys."""

KEYED_DIGEST_ALGORITHM: Final[str] = "hmac-sha256"
"""Algorithm token a record spells beside a keyed digest it stores.

Carried in the value rather than implied by the field, so a reader knows which
construction to recompute and a later second construction cannot be mistaken
for this one.
"""


def derive_labelled_key(*, key_material: bytes, info: bytes) -> bytes:
    """Return the HKDF-SHA256 subkey of ``key_material`` under the ``info`` label.

    Args:
        key_material: The caller's secret. Never logged or persisted here; this
            function neither stores nor returns it.
        info: The domain-separating label naming what the subkey is for. Two
            labels over one secret yield unrelated subkeys.

    Returns:
        :data:`DERIVED_KEY_BYTES` of derived key material.
    """
    return HKDF(algorithm=SHA256(), length=DERIVED_KEY_BYTES, salt=None, info=info).derive(key_material)


def keyed_digest_hex(*, key: bytes, message: bytes) -> str:
    """Return the lowercase hex HMAC-SHA256 of ``message`` under ``key``.

    The digest is deterministic in both inputs, which is what makes it usable as
    a stable reference: the same message under the same derived key yields the
    same value on every build, and a holder of the artefact without the key
    cannot invert it.
    """
    return hmac.new(key, message, hashlib.sha256).hexdigest()


__all__ = [
    "DERIVED_KEY_BYTES",
    "KEYED_DIGEST_ALGORITHM",
    "derive_labelled_key",
    "keyed_digest_hex",
]
