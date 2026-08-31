"""Validation-verdict cache location and helper roundtrip behavior.

These tests exercise the real filesystem helpers of ``_verdict_cache``:
the settings-derived writable location, the shipped bundled-tree location, the
atomic write/read roundtrip, foreign-file tolerance, and the delete-on-mismatch
branch. The authority-integration regression pin (skip-validation on a hit,
corpus-cache write counts, re-validation on a fingerprint change) lives in the
sibling ``test_validation_verdict_cache`` module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ..... import __version__
from .....core.config import override_settings
from .....core.resources.bundled_data import bundled_path
from .._verdict_cache import (
    VERDICT_OUTCOME_GREEN,
    RegistryValidationVerdict,
    bundled_verdict_path,
    certify_registry_validation,
    compute_shipped_verdict_key,
    compute_verdict_key,
    read_verdict,
    registry_validation_is_certified,
    shipped_verdict_location,
    verdict_cache_path,
    write_verdict,
)
from ..identity import RegistryIdentity, RegistryIdentityOrigin, compute_walked_tree_digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"cache", "registry-verdict"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``tmp_path / "state" / "cache" / "registry-verdict"`` in
``test_verdict_cache_path_derives_under_cache_namespace`` is the independent
oracle for ``verdict_cache_path``'s default-derivation, called with no
``cadrumo_validation_verdict_cache_dir`` override. The ``"registry"`` in the
other functions' ``tmp_path / "registry" / "aeat"`` scaffolding is the
calculation registry's bundled TOML authoring tree, an unrelated
different-namespace concept -- not the storage taxonomy's ``cache/registry``
member this file is otherwise about.
"""


def test_verdict_cache_path_derives_under_cache_namespace(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    with override_settings(cadrumo_local_storage_root=tmp_path / "state"):
        path = verdict_cache_path(root)
    assert path.parent == tmp_path / "state" / "cache" / "registry-verdict"
    assert path.name.startswith("cadrumo_validation_verdict_")
    assert path.suffix == ".json"


def test_distinct_roots_get_distinct_verdict_files(tmp_path: Path) -> None:
    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        first = verdict_cache_path(tmp_path / "registry-a" / "aeat")
        second = verdict_cache_path(tmp_path / "registry-b" / "aeat")
    assert first != second


def test_bundled_verdict_path_is_a_sibling_of_the_bundled_tree() -> None:
    bundled_root = bundled_path("registry", "aeat").resolve()
    shipped = bundled_verdict_path(bundled_root)
    assert shipped is not None
    assert shipped == bundled_root.parent / "aeat-validation-verdict.json"
    # The shipped verdict is never inside the fingerprinted tree it certifies.
    assert bundled_root not in shipped.parents


def test_bundled_verdict_path_is_none_for_a_mutable_authoring_tree(tmp_path: Path) -> None:
    assert bundled_verdict_path(tmp_path / "registry" / "aeat") is None


def test_write_read_roundtrip_preserves_the_verdict(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    verdict = RegistryValidationVerdict(
        verdict_key="abc123",
        package_version="9.9.9",
        outcome=VERDICT_OUTCOME_GREEN,
    )
    write_verdict(path, verdict)
    assert path.is_file()
    assert read_verdict(path) == verdict


def test_read_verdict_ignores_a_foreign_file(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert read_verdict(path) is None
    # A green-shaped but extra-field payload is rejected by the strict model.
    path.write_text('{"verdict_key": "k", "package_version": "1", "outcome": "green", "extra": 1}', encoding="utf-8")
    assert read_verdict(path) is None


def test_read_verdict_returns_none_when_absent(tmp_path: Path) -> None:
    assert read_verdict(tmp_path / "missing.json") is None


def _walked_identity(fingerprints: tuple[tuple[str, int, int, str], ...]) -> RegistryIdentity:
    """Build a walked identity the way the canonical resolver would for a mutable tree."""
    return RegistryIdentity(
        digest=compute_walked_tree_digest(fingerprints),
        origin=RegistryIdentityOrigin.WALKED,
        fingerprints=fingerprints,
    )


def test_certify_then_matching_key_is_certified(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    identity = _walked_identity((("a.toml", 1, 2, "digest-a"),))
    key = compute_verdict_key(
        identity_digest=identity.digest,
        source_evidence_fingerprints=(("b.pdf", 3, 4),),
        package_version="1.2.3",
    )
    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        written = certify_registry_validation(root, verdict_key=key, package_version="1.2.3")
        assert written.is_file()
        assert registry_validation_is_certified(root, verdict_key=key, identity=identity) is True


def test_mismatched_key_is_not_certified_and_deletes_the_stale_verdict(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    identity = _walked_identity((("a.toml", 1, 2, "digest-a"),))
    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        written = certify_registry_validation(root, verdict_key="stored-key", package_version="1.2.3")
        assert written.is_file()
        assert registry_validation_is_certified(root, verdict_key="different-key", identity=identity) is False
        # Delete-not-migrate: the stale writable verdict is removed so the next
        # load re-validates rather than trusting a superseded identity.
        assert not written.exists()


def test_compute_verdict_key_is_sensitive_to_every_input() -> None:
    """The verdict key moves with the tree identity, the evidence set, and the version.

    The tree half is now one opaque digest rather than the raw tuples, so this
    asserts the key is sensitive to that digest changing; that the digest itself
    is sensitive to every fingerprint field is the identity module's own gate and
    is not restated here.
    """
    src = (("b.pdf", 3, 4),)
    key = compute_verdict_key(
        identity_digest="identity-a",
        source_evidence_fingerprints=src,
        package_version="1.0.0",
        loader_code_fingerprint_override="registry-code-a",
    )
    assert key != compute_verdict_key(
        identity_digest="identity-a",
        source_evidence_fingerprints=src,
        package_version="1.0.1",
        loader_code_fingerprint_override="registry-code-a",
    )
    assert key != compute_verdict_key(
        identity_digest="identity-b",
        source_evidence_fingerprints=src,
        package_version="1.0.0",
        loader_code_fingerprint_override="registry-code-a",
    )
    assert key != compute_verdict_key(
        identity_digest="identity-a",
        source_evidence_fingerprints=(("b.pdf", 9, 4),),
        package_version="1.0.0",
        loader_code_fingerprint_override="registry-code-a",
    )
    assert key != compute_verdict_key(
        identity_digest="identity-a",
        source_evidence_fingerprints=src,
        package_version="1.0.0",
        loader_code_fingerprint_override="registry-code-b",
    )


def test_shipped_verdict_key_moves_with_registry_validation_code() -> None:
    """A release stamp cannot certify validation code other than its build's."""
    key = compute_shipped_verdict_key(
        identity_digest="stamped-identity",
        package_version="1.0.0",
        loader_code_fingerprint_override="registry-code-a",
    )

    assert key != compute_shipped_verdict_key(
        identity_digest="stamped-identity",
        package_version="1.0.0",
        loader_code_fingerprint_override="registry-code-b",
    )


def test_a_shipped_verdict_cannot_certify_a_walked_tree(tmp_path: Path) -> None:
    """A verdict beside a mutable tree is never honoured, whatever it contains.

    The shipped branch is reachable only for a STAMPED identity. Without that
    gate a verdict file planted beside an authoring tree would certify it, which
    is precisely the "cache over a validation gate made silently permissive"
    failure the verdict cache is meant not to have.
    """
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)
    identity = _walked_identity((("a.toml", 1, 2, "digest-a"),))
    shipped = shipped_verdict_location(root)
    write_verdict(
        shipped,
        RegistryValidationVerdict(
            verdict_key=compute_shipped_verdict_key(identity_digest=identity.digest, package_version=__version__),
            package_version=__version__,
            outcome=VERDICT_OUTCOME_GREEN,
        ),
    )
    assert shipped.is_file(), "the planted verdict must exist, or this proves nothing"

    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        assert registry_validation_is_certified(root, verdict_key="unmatched", identity=identity) is False
