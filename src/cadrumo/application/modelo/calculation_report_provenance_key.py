"""The per-profile key a calculation report's source references are digested with.

A revision's resolver provenance names the source objects behind each casilla,
and one of those names is a third party's tax identifier: the retenciones
resolver builds its reference as ``perceptor:{nif}``
(``src/cadrumo/application/aggregation/modelo_bindings_retenciones.py:213``). A
calculation report is carried off-host by operators and handed to accountants,
so that identifier must not travel in it -- and an unkeyed hash of a NIF is not
a redaction, because the whole space is enumerable. Every reference is therefore
carried as a digest keyed with a secret only this profile holds.

No new stored secret enters custody. The key is DERIVED, in memory, from the
profile's existing Ed25519 review-package signing key through the capability
that already owns that key's custody
(:class:`~cadrumo.application.modelo.review_package_signing_ports.ReviewPackageSigningKeypairCapability`),
under the fixed label :data:`CALCULATION_REPORT_PROVENANCE_KEY_INFO`. The label
is the domain separation: the derived key is computationally unrelated to the
signing key, so a provenance digest can never be mistaken for or replayed as a
review-package signature, and losing the profile loses the ability to recompute
provenance digests exactly as it already loses the ability to sign.

The reference's FAMILY stays legible and only its subject is digested, so a
reader can still tell a perceptor rollup from an invoice without learning which
perceptor. That split is applied conservatively: a family token is a lowercase
name, and a reference whose leading segment is not one has the whole value
digested instead. A Spanish tax identifier's canonical form is uppercased
(``cadrumo.core.identity.nif_iva.normalise_nif_iva``), so no identifier can pass
the family test and appear in the clear.

See Also:
    :mod:`cadrumo.core.keyed_digest`
        The derivation and keyed-digest primitives, with no policy of their own.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, SecretBytes

from ...core.hashing import CONTENT_DIGEST_PREFIX, HEX_ALPHABET
from ...core.identity.bucket import BucketId
from ...core.keyed_digest import KEYED_DIGEST_ALGORITHM, derive_labelled_key, keyed_digest_hex
from ...core.models import STRICT_FROZEN_CONFIG
from .review_package_signing import ensure_review_package_signing_keypair

if TYPE_CHECKING:
    from .review_package_signing_ports import ReviewPackageSigningKeypairCapability

CALCULATION_REPORT_PROVENANCE_KEY_INFO: Final[bytes] = b"cadrumo/calculation-report-provenance/v1"
"""The label separating the provenance key from every other use of the profile key.

Versioned, because a later change to what the key digests would need a key that
cannot verify the digests this one produced.
"""

OPAQUE_PROVENANCE_FAMILY: Final[str] = "opaque"
"""The family named for a reference whose leading segment is not a family token.

Used when nothing about the reference's shape proves its prefix is safe to
print, so the whole reference is digested. A report that shows ``opaque`` says
"a source object of an unrecognised shape", which is exactly what is known.
"""

_FAMILY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_UTF_8: Final[str] = "utf-8"


class CalculationReportProvenanceKey(BaseModel):
    """One profile's in-memory provenance key and the digests it produces.

    The key is held as :class:`~pydantic.SecretBytes`, so it is redacted in every
    representation a log line, exception or model dump could reach; the raw bytes
    are read only inside this class's own digest methods. It is never persisted:
    it is re-derived from the profile's signing key whenever a report is built.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    key: SecretBytes

    def reference_digest(self, reference: str) -> str:
        """Return ``reference`` as ``<family>:hmac-sha256:<hex>``.

        The digest covers the WHOLE reference, family segment included, so two
        references differing only in their family produce different digests. The
        family is reprinted beside the digest because it names a kind of source
        object rather than a party.
        """
        return f"{self._family(reference)}:{KEYED_DIGEST_ALGORITHM}:{self._digest(reference)}"

    def content_digest(self, fingerprint: str) -> str:
        """Return the resolver's content fingerprint in a self-describing form.

        A resolver fingerprint is normally the product's canonical SHA-256 over
        the source object's own facts, and that is carried through unchanged as
        ``sha256:<hex>``: a 256-bit digest over a whole fact row is not
        enumerable, and keeping it verbatim is what lets a store holder compare
        it against the stored fingerprint directly.

        A fingerprint in any other spelling is not provably high-entropy, so it
        is keyed instead and spelled ``hmac-sha256:<hex>``. The prefix tells a
        verifier which of the two it is holding rather than leaving it to guess.
        """
        if _is_canonical_sha256_hex(fingerprint):
            return f"{CONTENT_DIGEST_PREFIX}{fingerprint}"
        return f"{KEYED_DIGEST_ALGORITHM}:{self._digest(fingerprint)}"

    def _digest(self, message: str) -> str:
        return keyed_digest_hex(key=self.key.get_secret_value(), message=message.encode(_UTF_8))

    @staticmethod
    def _family(reference: str) -> str:
        """Return the legible family of ``reference``, or the opaque family.

        Conservative in both directions: the segment must look like a family
        name, and something must remain after it. A reference that is nothing
        but a bare token has no family to show, because the token itself is the
        subject being protected.
        """
        family, separator, subject = reference.partition(":")
        if not separator or not subject:
            return OPAQUE_PROVENANCE_FAMILY
        if _FAMILY_PATTERN.match(family) is None:
            return OPAQUE_PROVENANCE_FAMILY
        return family


def derive_calculation_report_provenance_key(
    *,
    bucket_id: str,
    signing_keypair: ReviewPackageSigningKeypairCapability,
) -> CalculationReportProvenanceKey:
    """Derive the profile's provenance key through its signing-keypair capability.

    Args:
        bucket_id: The active profile bucket the report is built for.
        signing_keypair: The capability that owns custody of this profile's
            Ed25519 signing key. It mints the keypair on first use, so a profile
            that has never signed a review package still gets a key.

    Returns:
        :class:`CalculationReportProvenanceKey`: the derived key, in memory only.
    """
    keypair = ensure_review_package_signing_keypair(bucket_id=bucket_id, signing_keypair=signing_keypair)
    return CalculationReportProvenanceKey(
        bucket_id=keypair.bucket_id,
        key=SecretBytes(
            derive_labelled_key(
                key_material=bytes.fromhex(keypair.private_key_hex),
                info=CALCULATION_REPORT_PROVENANCE_KEY_INFO,
            ),
        ),
    )


def _is_canonical_sha256_hex(value: str) -> bool:
    """Whether ``value`` is the product's canonical bare SHA-256 spelling."""
    return len(value) == 64 and all(character in HEX_ALPHABET for character in value)


__all__ = [
    "CALCULATION_REPORT_PROVENANCE_KEY_INFO",
    "OPAQUE_PROVENANCE_FAMILY",
    "CalculationReportProvenanceKey",
    "derive_calculation_report_provenance_key",
]
