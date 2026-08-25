"""Directory-mode authorization-manifest loader coverage.

The multi-year-renta gate's manifest is directory-mode: each enrolled
modelo owns one ``authorization.d/<modelo>.toml`` fragment, and
:func:`load_authorization_manifest` merges every fragment under a registry
root. These tests drive the real loader against real ``tmp_path`` fragment
files with no test doubles, proving default-deny-by-absence, TOML-boundary
hydration, the fragment stem/id cross-check, and the >=2-distinct-renta-year
and duplicate-modelo invariants that make a malformed enrollment
unconstructable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._authorization import (
    AUTHORIZATION_MANIFEST_DIRNAME,
    AuthorizationState,
    derive_modelo_authorization,
    load_authorization_manifest,
    manifest_dir,
)
from ..errors import AuthorizationManifestError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_fragment(root: Path, stem: str, body: str) -> None:
    directory = root / AUTHORIZATION_MANIFEST_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.toml").write_text(body, encoding="utf-8")


_VALID_130 = """
[modelo]
modelo = "130"
renta_years = [2025, 2026]
evidence_class = "calculation"
enrolling_test = "src/cadrumo/application/calculations/test_modelo_130_carry_forward_continuity.py"
"""

_VALID_303 = """
[modelo]
modelo = "303"
renta_years = [2025, 2026]
evidence_class = "calculation"
enrolling_test = "src/cadrumo/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py"
"""


def test_absent_or_empty_directory_authorizes_nothing(tmp_path: Path) -> None:
    """Default-deny: absent or empty authorization.d roots authorize nothing."""

    absent_root = tmp_path / "absent"
    empty_root = tmp_path / "empty"
    (empty_root / AUTHORIZATION_MANIFEST_DIRNAME).mkdir(parents=True)

    for case_id, root in (("absent", absent_root), ("empty", empty_root)):
        manifest = load_authorization_manifest(root)
        assert manifest.entries == (), case_id
        assert manifest.authorized_modelos == frozenset(), case_id


def test_valid_fragments_hydrate_merge_and_drive_authorization_state(tmp_path: Path) -> None:
    """Well-formed fragments hydrate entries, merge, and authorize enrolled modelos."""

    _write_fragment(tmp_path, "130", _VALID_130)
    _write_fragment(tmp_path, "303", _VALID_303)

    manifest = load_authorization_manifest(tmp_path)
    entry = manifest.entry_for("130")
    assert entry is not None
    assert entry.distinct_renta_years == (2025, 2026)
    assert manifest.authorized_modelos == frozenset({"130", "303"})

    authorized = derive_modelo_authorization("130", manifest=manifest, has_engine=True)
    assert authorized.state is AuthorizationState.AUTHORIZED
    assert authorized.is_authorized
    unauthorized = derive_modelo_authorization("390", manifest=manifest, has_engine=True)
    assert unauthorized.state is AuthorizationState.UNAUTHORIZED
    assert not unauthorized.is_authorized


def test_invalid_manifest_fragments_are_rejected(tmp_path: Path) -> None:
    """Malformed fragments fail loudly at the TOML/entry boundary.

    The stem cross-check forces distinct filenames, so the duplicate must be
    smuggled in via a fragment whose stem matches but whose internal id is
    re-used by a sibling. Here both 130.toml and 130-dup.toml declare 130;
    the stem cross-check rejects the second before the manifest-level dedup,
    which is the stricter, earlier failure — either way it does not load.
    """

    single_year = """
[modelo]
modelo = "130"
renta_years = [2025]
evidence_class = "calculation"
enrolling_test = "x.py"
"""
    cases = (
        ("stem-mismatch", (("131", _VALID_130),), "does not match"),
        ("single-year", (("130", single_year),), None),
        ("missing-modelo-table", (("130", "renta_years = [2025, 2026]\n"),), "exactly one"),
        ("duplicate-modelo", (("130", _VALID_130), ("130-dup", _VALID_130)), None),
    )

    for case_id, fragments, match in cases:
        root = tmp_path / case_id
        for stem, body in fragments:
            _write_fragment(root, stem, body)
        with pytest.raises(AuthorizationManifestError, match=match):
            load_authorization_manifest(root)


def test_unknown_modelo_fragment_is_rejected_before_capability_derivation(tmp_path: Path) -> None:
    """An unknown ID must not load into the manifest's capability source."""
    _write_fragment(
        tmp_path,
        "999",
        """
[modelo]
modelo = "999"
renta_years = [2025, 2026]
evidence_class = "calculation"
enrolling_test = "tests/unknown-modelo.py"
""",
    )

    with pytest.raises(AuthorizationManifestError, match="non-enrollable modelo"):
        load_authorization_manifest(tmp_path)


def test_manifest_dir_resolves_under_root(tmp_path: Path) -> None:
    """manifest_dir points at authorization.d under the registry root."""
    assert manifest_dir(tmp_path) == tmp_path / AUTHORIZATION_MANIFEST_DIRNAME
