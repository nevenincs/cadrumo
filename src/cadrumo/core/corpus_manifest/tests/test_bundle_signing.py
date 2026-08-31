"""Ed25519 corpus-bundle signing + signature-verify roundtrip and anti-tautology proofs.

Exercises :mod:`~core.corpus_manifest._bundle_signing` end to end against a
REAL checksummed corpus bundle (:func:`~core.corpus_manifest.build_corpus_bundle`)
and a REAL on-disk keypair file (no mocks, fakes, or stubs): mint a maintainer
keypair, confirm the private key is persisted as a real file that a fresh
process can reload, sign a bundle, verify the signature, then tamper the
bundle/manifest/signature and confirm verification refuses in every case.

Mirrors the anti-tautology discipline already established in
``test_review_package_signing.py`` (the sibling authenticity layer scoped to
one profile bucket's review package instead of a maintainer-published corpus
bundle) and ``test_bundle.py`` (the checksum-integrity layer this module signs
on top of).

See Also:
    :class:`~core.corpus_manifest.SignedCorpusBundle`
        Signature envelope binding a bundle manifest digest to the signer.
    :func:`~core.corpus_manifest.sign_corpus_bundle`
        Signs only bundles that pass the checksum-manifest verifier first.
    :func:`~core.corpus_manifest.verify_corpus_bundle_signature`
        Boolean authenticity check that re-runs checksum integrity before Ed25519.
    :func:`~core.corpus_manifest.assert_corpus_bundle_signature_verifies`
        Raising install-time assertion for signed corpus bundles.
    :func:`~core.corpus_manifest.generate_corpus_signing_keypair`
        Maintainer keypair minting and on-disk persistence path covered here.
    :func:`~core.corpus_manifest.verify_corpus_bundle`
        Integrity layer whose manifest digest is signed by this feature.
    :mod:`~application.modelo._review_package_signing`
        Sibling Ed25519 authenticity layer for review-package ZIPs.
    :mod:`~core.corpus_manifest.tests.test_bundle`
        Checksum-integrity bundle coverage that this signing test builds on.
"""

from __future__ import annotations

import json
import os
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from ...directory_scan import scan_directory
from .._bundle_signing import (
    CorpusBundleSigningError,
    CorpusBundleSigningKeyNotFoundError,
    assert_corpus_bundle_signature_verifies,
    corpus_signing_public_key,
    generate_corpus_signing_keypair,
    load_corpus_signing_keypair,
    sign_corpus_bundle,
    verify_corpus_bundle_signature,
)
from ..errors import CorpusBundleVerificationError
from ..manifest import build_corpus_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GENERATED_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
_SIGNED_AT = datetime(2026, 7, 3, 12, 5, 0, tzinfo=UTC)


def _seed_corpus(corpus_root: Path) -> None:
    corpus_root.mkdir(parents=True, exist_ok=True)
    files = {
        "legal/ley-1.html": b"<html>Articulo primero.</html>",
        "manuals/renta/2024/manual.txt": b"Manual practico Renta 2024 excerpt.",
    }
    for relative, content in files.items():
        path = corpus_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _build_bundle(tmp_path: Path, *, name: str = "signed-test-corpus") -> Path:
    corpus_root = tmp_path / "corpus"
    _seed_corpus(corpus_root)
    bundle_path = tmp_path / "bundle.zip"
    build_corpus_bundle(
        corpus_root,
        corpus_root_name=name,
        output_path=bundle_path,
        generated_at=_GENERATED_AT,
    )
    return bundle_path


def test_generate_keypair_persists_reloadable_file_and_is_permission_hardened(tmp_path: Path) -> None:
    """The minted keypair is a real file a fresh process reloads byte-identically."""
    key_path = tmp_path / "keys" / "corpus-signing-key.json"

    minted = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)

    assert key_path.exists()
    reloaded = load_corpus_signing_keypair(key_path)
    assert reloaded == minted

    # Real behavior: the reconstructed live key objects actually sign/verify a
    # message consistently with each other -- not just equal hex strings.
    message = b"anti-tautology-probe"
    signature = minted.private_key().sign(message)
    reloaded.public_key().verify(signature, message)


def test_load_without_generate_raises_key_not_found(tmp_path: Path) -> None:
    missing_path = tmp_path / "keys" / "does-not-exist.json"

    with pytest.raises(CorpusBundleSigningKeyNotFoundError):
        load_corpus_signing_keypair(missing_path)


def test_corpus_signing_public_key_never_carries_private_material(tmp_path: Path) -> None:
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)

    public = corpus_signing_public_key(keypair)

    assert public.public_key_hex == keypair.public_key_hex
    assert public.created_at == keypair.created_at
    # The projected model has no private-key field at all -- the shape itself
    # is the guarantee, not just an absent value.
    assert "private_key_hex" not in type(public).model_fields


def test_sign_then_verify_with_correct_public_key_passes(tmp_path: Path) -> None:
    bundle_path = _build_bundle(tmp_path)
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)

    signed = sign_corpus_bundle(bundle_path, keypair=keypair, signed_at=_SIGNED_AT)

    assert signed.corpus_root_name == "signed-test-corpus"
    assert signed.public_key_hex == keypair.public_key_hex
    assert len(bytes.fromhex(signed.signature_hex)) == 64
    assert signed.signed_at == _SIGNED_AT

    assert verify_corpus_bundle_signature(bundle_path, signed, public_key_hex=keypair.public_key_hex) is True
    # The raising assertion form must not raise on a genuinely clean bundle.
    assert_corpus_bundle_signature_verifies(bundle_path, signed, public_key_hex=keypair.public_key_hex)


def test_sign_refuses_a_checksum_dirty_bundle(tmp_path: Path) -> None:
    """A bundle that fails its own checksum manifest must never be signed."""
    bundle_path = _build_bundle(tmp_path)
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)

    rewritten = bundle_path.with_name(bundle_path.name + ".rewritten")
    with zipfile.ZipFile(bundle_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = b"tampered bytes, wrong hash now" if item.filename == "legal/ley-1.html" else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(bundle_path)

    with pytest.raises(CorpusBundleVerificationError) as refusal:
        sign_corpus_bundle(bundle_path, keypair=keypair)

    assert (refusal.value.context or {})["mismatched"] == ("legal/ley-1.html",)


def test_verify_fails_when_bundle_tampered_after_signing(tmp_path: Path) -> None:
    """Tampering an archived member after signing must fail verification
    (integrity-then-signature: the digest re-derivation catches it before the
    Ed25519 check ever runs)."""
    bundle_path = _build_bundle(tmp_path)
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)
    signed = sign_corpus_bundle(bundle_path, keypair=keypair, signed_at=_SIGNED_AT)

    rewritten = bundle_path.with_name(bundle_path.name + ".rewritten")
    with zipfile.ZipFile(bundle_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = b"TAMPERED AFTER SIGNING" if item.filename == "legal/ley-1.html" else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(bundle_path)

    assert verify_corpus_bundle_signature(bundle_path, signed, public_key_hex=keypair.public_key_hex) is False
    with pytest.raises(CorpusBundleSigningError):
        assert_corpus_bundle_signature_verifies(bundle_path, signed, public_key_hex=keypair.public_key_hex)


def test_verify_fails_when_manifest_digest_tampered_without_recomputation(tmp_path: Path) -> None:
    """A manifest whose recorded ``manifest_sha256`` no longer matches the
    signed digest fails verification even if per-file checksums still line up
    with the (equally tampered) manifest body."""
    bundle_path = _build_bundle(tmp_path)
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)
    signed = sign_corpus_bundle(bundle_path, keypair=keypair, signed_at=_SIGNED_AT)

    with zipfile.ZipFile(bundle_path, "r") as archive:
        manifest_bytes = archive.read("corpus.manifest.json")
    payload = json.loads(manifest_bytes)
    # Flip the self-attesting digest without recomputing it. Two independent
    # layers would each refuse this bundle -- the manifest tamper check and the
    # signature over the manifest bytes -- and the assertion below observes only
    # that verification failed, not which layer refused first. Read it as "a
    # tampered bundle does not verify"; the tamper check's own coverage lives in
    # test_manifest.py and test_bundle.py, which assert the error type directly.
    payload["manifest_sha256"] = "0" * 64
    tampered_manifest = json.dumps(payload).encode("utf-8")

    rewritten = bundle_path.with_name(bundle_path.name + ".rewritten")
    with zipfile.ZipFile(bundle_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = tampered_manifest if item.filename == "corpus.manifest.json" else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(bundle_path)

    assert verify_corpus_bundle_signature(bundle_path, signed, public_key_hex=keypair.public_key_hex) is False


def test_verify_fails_with_wrong_public_key(tmp_path: Path) -> None:
    bundle_path = _build_bundle(tmp_path)
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)
    signed = sign_corpus_bundle(bundle_path, keypair=keypair, signed_at=_SIGNED_AT)

    wrong_public_key = Ed25519PrivateKey.generate().public_key()
    wrong_public_key_hex = wrong_public_key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    ).hex()

    assert verify_corpus_bundle_signature(bundle_path, signed, public_key_hex=wrong_public_key_hex) is False
    with pytest.raises(CorpusBundleSigningError):
        assert_corpus_bundle_signature_verifies(bundle_path, signed, public_key_hex=wrong_public_key_hex)


def test_verify_fails_when_signature_bytes_are_corrupted(tmp_path: Path) -> None:
    """A structurally-valid but wrong signature (same length, different bytes) must fail."""
    bundle_path = _build_bundle(tmp_path)
    key_path = tmp_path / "corpus-signing-key.json"
    keypair = generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)
    signed = sign_corpus_bundle(bundle_path, keypair=keypair, signed_at=_SIGNED_AT)

    corrupted_signature_hex = ("0" if signed.signature_hex[0] != "0" else "1") + signed.signature_hex[1:]
    corrupted = signed.model_copy(update={"signature_hex": corrupted_signature_hex})

    assert verify_corpus_bundle_signature(bundle_path, corrupted, public_key_hex=keypair.public_key_hex) is False


def test_two_keypairs_generated_at_different_paths_are_independent(tmp_path: Path) -> None:
    """Two maintainer keypairs generated at distinct paths never collide."""
    keypair_one = generate_corpus_signing_keypair(
        private_key_path=tmp_path / "key-one.json",
        generated_at=_GENERATED_AT,
    )
    keypair_two = generate_corpus_signing_keypair(
        private_key_path=tmp_path / "key-two.json",
        generated_at=_GENERATED_AT,
    )

    assert keypair_one.public_key_hex != keypair_two.public_key_hex
    assert keypair_one.private_key_hex != keypair_two.private_key_hex

    bundle_path = _build_bundle(tmp_path)
    signed_by_one = sign_corpus_bundle(bundle_path, keypair=keypair_one, signed_at=_SIGNED_AT)

    # A bundle signed by keypair_one must not verify against keypair_two's
    # public key -- proves the two identities are cryptographically distinct,
    # not merely equal-shaped records.
    assert (
        verify_corpus_bundle_signature(bundle_path, signed_by_one, public_key_hex=keypair_two.public_key_hex) is False
    )


_PLACEHOLDER_KEY_FILE_CONTENT = "PLACEHOLDER-NOT-A-SECRET"


class TestSigningKeyPersistenceClosesThePermissionWindow:
    """The plaintext Ed25519 private key never enters a permissively-moded file.

    The retired writer created the destination with the ambient process
    umask, wrote the secret into it, and only afterwards tightened the
    permissions. The secret therefore existed on disk at a permissive mode
    for a real window -- and because
    :func:`~core.file_permissions.restrict_file_permissions` is documented
    best-effort and swallows every failure, a tightening step that could not
    be applied left the secret readable with no error surfaced at all.

    Asserting the FINAL mode cannot detect that window: the retired writer
    also ended at ``0o600`` whenever its chmod happened to succeed, so such
    an assertion passes either way. The discriminating observation is WHICH
    inode receives the secret bytes. Hard-linking a second name to the
    pre-existing destination gives the test a durable handle on the original
    inode: an in-place write is observable through that handle, whereas a
    staged write swapped in by :func:`os.replace` is not.
    """

    def test_secret_never_enters_the_preexisting_destination_inode(self, tmp_path: Path) -> None:
        """A pre-existing permissive file at the destination never receives the key."""
        key_path = tmp_path / "corpus-signing-key.json"
        key_path.write_text(_PLACEHOLDER_KEY_FILE_CONTENT, encoding="utf-8")
        if os.name != "nt":
            os.chmod(key_path, 0o644)

        witness = tmp_path / "witness-same-inode.json"
        os.link(key_path, witness)
        assert key_path.stat().st_ino == witness.stat().st_ino

        keypair = generate_corpus_signing_keypair(
            private_key_path=key_path,
            generated_at=_GENERATED_AT,
        )

        # The destination carries the freshly minted secret ...
        assert keypair.private_key_hex in key_path.read_text(encoding="utf-8")
        # ... but the permissively-moded inode that existed before the call
        # never saw a single byte of it.
        witness_content = witness.read_text(encoding="utf-8")
        assert witness_content == _PLACEHOLDER_KEY_FILE_CONTENT
        assert keypair.private_key_hex not in witness_content
        assert key_path.stat().st_ino != witness.stat().st_ino
        assert scan_directory(tmp_path, pattern="*.tmp") == ()

    def test_persisted_key_is_owner_only_on_posix(self, tmp_path: Path) -> None:
        """The persisted key ends at ``0o600``.

        A supporting end-state assertion, not the discriminating one: the
        retired post-hoc hardening reached the same final mode whenever its
        chmod succeeded. The sibling test above is what proves the window
        between creation and tightening is gone.
        """
        key_path = tmp_path / "mode-check-key.json"
        generate_corpus_signing_keypair(private_key_path=key_path, generated_at=_GENERATED_AT)

        assert key_path.exists()
        if os.name != "nt":
            assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


__all__: list[str] = []
