"""Absence gate: no corpus-manifest refusal carries an authored sentence.

Every refusal this package raises must reach the operator through its
registered locale key plus machine facts on the error context. Pinning the
key and the facts alone is not enough to hold that line: message resolution
prefers ``translated_message``, so English passed alongside the key stays
green under a key-and-context assertion while ``str(exc)`` still prefers the
positional argument and carries the sentence into tracebacks, logs, and every
boundary that renders the exception directly — in every locale.

The assertion here is therefore an *absence* assertion: ``str(exc)`` must
equal the key. Re-introducing a sentence at any of these raise sites fails
this module, which is exactly what a key-and-context assertion cannot do.

Real filesystem, real zip archives, real pydantic validation. No doubles.
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from ...errors.error_codes import get_registered_error_code
from ..errors import CorpusBundleError, CorpusBundleVerificationError, CorpusManifestError, CorpusManifestTamperError
from ..manifest import (
    CorpusEntry,
    CorpusManifest,
    assert_corpus_bundle_verifies,
    assert_corpus_clean,
    build_corpus_bundle,
    build_corpus_manifest,
    load_corpus_manifest,
    manifest_path_for,
    save_corpus_manifest,
)

if TYPE_CHECKING:
    from ...errors.hierarchy import CadrumoError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MANIFEST_KEY = "errors.integrity.integrity_storage_corpus_manifest"
_TAMPER_KEY = "errors.integrity.integrity_storage_corpus_manifest_tamper"
_DRIFT_KEY = "errors.integrity.integrity_storage_corpus_manifest_drift"
_BUNDLE_KEY = "errors.integrity.integrity_storage_corpus_bundle"
_BUNDLE_VERIFICATION_KEY = "errors.integrity.integrity_storage_corpus_bundle_verification"

_BUNDLE_MANIFEST_MEMBER = "corpus.manifest.json"


def _assert_key_only(error: CadrumoError, expected_key: str, expected_context: dict[str, object]) -> None:
    """Assert the refusal renders as its key and carries exactly the given machine facts.

    The registered error code is derived from the key rather than passed
    separately: the registry (``core/errors/registry/_core.py``) names every
    ``INTEGRITY_*`` code as the uppercased final segment of its
    ``errors.integrity.integrity_*`` message key, so a divergent code for a
    given key is itself a registry defect this assertion catches.
    """
    assert error.translated_message == expected_key
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
    assert str(error) == expected_key
    assert error.context == expected_context
    assert get_registered_error_code(error).code == expected_key.rsplit(".", maxsplit=1)[-1].upper()


def _validator_refusal(excinfo: pytest.ExceptionInfo[ValidationError]) -> CorpusManifestError:
    """Recover the typed refusal pydantic wrapped when a field validator raised.

    Pydantic embeds ``str(exc)`` of the raised ``ValueError`` into the rendered
    ``ValidationError`` text, so an authored sentence here would leak through
    the wrapper as well. The original exception object is preserved under the
    error's ``ctx``, which is what lets this module assert on the refusal
    itself rather than on pydantic's rendering of it.
    """
    inner = excinfo.value.errors()[0].get("ctx", {}).get("error")
    assert isinstance(inner, CorpusManifestError)
    return inner


def _corpus_with_one_file(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "doc.txt").write_text("corpus body", encoding="utf-8")
    return root


def _real_manifest(root: Path) -> CorpusManifest:
    return build_corpus_manifest(root, corpus_root_name="manuals")


def _zip_with(target: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(target, mode="w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return target


def test_corpus_entry_path_refusals_are_key_only() -> None:
    """Each of the four path-traversal branches refuses through the key alone."""
    cases: tuple[tuple[str, dict[str, object]], ...] = (
        ("..", {"relative_path": "..", "dot_token": True}),
        ("a\\..\\b", {"relative_path": "a\\..\\b", "posix_separators_only": False}),
        ("/etc/passwd", {"relative_path": "/etc/passwd", "absolute": True}),
        ("a/../b", {"relative_path": "a/../b", "contains_dot_tokens": True}),
    )
    for relative_path, expected_context in cases:
        with pytest.raises(ValidationError) as excinfo:
            CorpusEntry(relative_path=relative_path, sha256="0" * 64, content_length=0)
        error = _validator_refusal(excinfo)
        _assert_key_only(error, _MANIFEST_KEY, expected_context)


def test_naive_generated_at_refusal_is_key_only() -> None:
    """A naive manifest timestamp refuses through the key with typed facts."""
    with pytest.raises(ValidationError) as excinfo:
        CorpusManifest(
            corpus_root_name="manuals",
            generated_at=datetime(2026, 1, 1, 12, 0, 0),
            entries=(),
            manifest_sha256="0" * 64,
        )
    error = _validator_refusal(excinfo)
    _assert_key_only(
        error,
        _MANIFEST_KEY,
        {
            "field": "generated_at",
            "utc_aware": False,
            "validation_error_type": "CoreValidationError",
        },
    )


def test_load_manifest_refusals_are_key_only(tmp_path: Path) -> None:
    """Malformed, over-version, and tampered manifests each refuse key-only."""
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    with pytest.raises(CorpusManifestError) as excinfo:
        load_corpus_manifest(malformed)
    _assert_key_only(
        excinfo.value,
        _MANIFEST_KEY,
        {
            "manifest_path": str(malformed),
            "structurally_valid": False,
            "validation_error_type": "_MalformedManifestPayloadError",
        },
    )

    future = tmp_path / "future.json"
    future.write_text(
        json.dumps(
            {
                "manifest_version": 2,
                "corpus_root_name": "manuals",
                "generated_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
                "entries": [],
                "manifest_sha256": "0" * 64,
            },
        ),
        encoding="utf-8",
    )
    with pytest.raises(CorpusManifestError) as excinfo:
        load_corpus_manifest(future)
    _assert_key_only(excinfo.value, _MANIFEST_KEY, {"manifest_path": str(future), "supported_version": "1"})

    root = _corpus_with_one_file(tmp_path / "corpus")
    tampered = manifest_path_for(root)
    save_corpus_manifest(_real_manifest(root).model_copy(update={"manifest_sha256": "1" * 64}), tampered)
    with pytest.raises(CorpusManifestTamperError) as tamper_info:
        load_corpus_manifest(tampered)
    _assert_key_only(
        tamper_info.value,
        _TAMPER_KEY,
        {
            "manifest_path": str(tampered),
            "manifest_sha256_matches_body": False,
            "digest_field": "manifest_sha256",
        },
    )


def test_corpus_drift_refusal_is_key_only(tmp_path: Path) -> None:
    """A drifted corpus refuses through the key with the drift triple as facts."""
    root = _corpus_with_one_file(tmp_path / "corpus")
    save_corpus_manifest(_real_manifest(root), manifest_path_for(root))
    (root / "intruder.txt").write_text("added after the manifest", encoding="utf-8")

    with pytest.raises(CorpusManifestError) as excinfo:
        assert_corpus_clean(root)
    _assert_key_only(
        excinfo.value,
        _DRIFT_KEY,
        {
            "corpus_root_name": "manuals",
            "added": ("intruder.txt",),
            "removed": (),
            "changed": (),
        },
    )


def test_bundle_refusals_are_key_only(tmp_path: Path) -> None:
    """Every bundle-structure refusal renders as its key with typed facts."""
    from ..manifest import verify_corpus_bundle

    not_a_zip = tmp_path / "not-a-zip.zip"
    not_a_zip.write_bytes(b"plain bytes, not an archive")
    with pytest.raises(CorpusBundleError) as excinfo:
        verify_corpus_bundle(not_a_zip)
    _assert_key_only(
        excinfo.value,
        _BUNDLE_KEY,
        {
            "bundle_path": str(not_a_zip),
            "valid_zip_archive": False,
            "archive_error_type": "BadZipFile",
        },
    )

    no_member = _zip_with(tmp_path / "no-member.zip", {"doc.txt": "body"})
    with pytest.raises(CorpusBundleError) as excinfo:
        verify_corpus_bundle(no_member)
    _assert_key_only(
        excinfo.value,
        _BUNDLE_KEY,
        {
            "manifest_member": _BUNDLE_MANIFEST_MEMBER,
            "manifest_member_present": False,
        },
    )

    malformed = _zip_with(tmp_path / "malformed.zip", {_BUNDLE_MANIFEST_MEMBER: "{not json"})
    with pytest.raises(CorpusBundleError) as excinfo:
        verify_corpus_bundle(malformed)
    _assert_key_only(
        excinfo.value,
        _BUNDLE_KEY,
        {
            "embedded_manifest_structurally_valid": False,
            "validation_error_type": "_MalformedManifestPayloadError",
        },
    )

    future_payload = json.dumps(
        {
            "manifest_version": 3,
            "corpus_root_name": "manuals",
            "generated_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "entries": [],
            "manifest_sha256": "0" * 64,
        },
    )
    future = _zip_with(tmp_path / "future.zip", {_BUNDLE_MANIFEST_MEMBER: future_payload})
    with pytest.raises(CorpusBundleError) as excinfo:
        verify_corpus_bundle(future)
    _assert_key_only(excinfo.value, _BUNDLE_KEY, {"embedded_manifest_version": "3", "supported_version": "1"})

    root = _corpus_with_one_file(tmp_path / "corpus")
    tampered_payload = _real_manifest(root).model_copy(update={"manifest_sha256": "2" * 64}).model_dump_json()
    tampered = _zip_with(tmp_path / "tampered.zip", {_BUNDLE_MANIFEST_MEMBER: tampered_payload})
    with pytest.raises(CorpusManifestTamperError) as tamper_info:
        verify_corpus_bundle(tampered)
    _assert_key_only(
        tamper_info.value,
        _TAMPER_KEY,
        {
            "manifest_member": _BUNDLE_MANIFEST_MEMBER,
            "manifest_sha256_matches_body": False,
            "digest_field": "manifest_sha256",
        },
    )


def test_bundle_verification_refusal_is_key_only(tmp_path: Path) -> None:
    """A bundle carrying an undeclared member refuses through the key alone."""
    root = _corpus_with_one_file(tmp_path / "corpus")
    bundle = tmp_path / "corpus.zip"
    build_corpus_bundle(root, corpus_root_name="manuals", output_path=bundle)
    with zipfile.ZipFile(bundle, mode="a") as archive:
        archive.writestr("stowaway.txt", "not declared by the manifest")

    with pytest.raises(CorpusBundleVerificationError) as excinfo:
        assert_corpus_bundle_verifies(bundle)
    _assert_key_only(
        excinfo.value,
        _BUNDLE_VERIFICATION_KEY,
        {
            "bundle_path": str(bundle),
            "missing": (),
            "unexpected": ("stowaway.txt",),
            "mismatched": (),
        },
    )
