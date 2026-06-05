"""Directory-mode authorization-manifest loader coverage.

The multi-year-renta gate's manifest is directory-mode: each enrolled
modelo owns one ``authorization.d/<modelo>.toml`` fragment, and
:func:`load_authorization_manifest` merges every fragment under a registry
root. These tests drive the real loader against real ``tmp_path`` fragment
files — no mocks — proving default-deny-by-absence, TOML-boundary
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
from .._errors import AuthorizationManifestError

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
enrolling_test = "src/aeat/application/calculations/test_modelo_130_carry_forward_continuity.py"
"""


def test_absent_directory_authorizes_nothing(tmp_path: Path) -> None:
    """Default-deny-by-absence: no authorization.d directory -> empty manifest."""
    manifest = load_authorization_manifest(tmp_path)
    assert manifest.entries == ()
    assert manifest.authorized_modelos == frozenset()


def test_empty_directory_authorizes_nothing(tmp_path: Path) -> None:
    """An authorization.d directory with no fragments authorizes nothing."""
    (tmp_path / AUTHORIZATION_MANIFEST_DIRNAME).mkdir()
    assert load_authorization_manifest(tmp_path).entries == ()


def test_valid_fragment_hydrates_from_toml(tmp_path: Path) -> None:
    """A well-formed fragment hydrates renta_years (array) + evidence_class (string)."""
    _write_fragment(tmp_path, "130", _VALID_130)
    manifest = load_authorization_manifest(tmp_path)
    entry = manifest.entry_for("130")
    assert entry is not None
    assert entry.distinct_renta_years == (2025, 2026)
    assert manifest.authorized_modelos == frozenset({"130"})


def test_multiple_fragments_merge(tmp_path: Path) -> None:
    """Every fragment in the directory merges into one manifest."""
    _write_fragment(tmp_path, "130", _VALID_130)
    _write_fragment(
        tmp_path,
        "303",
        """
[modelo]
modelo = "303"
renta_years = [2025, 2026]
evidence_class = "calculation"
enrolling_test = "src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py"
""",
    )
    manifest = load_authorization_manifest(tmp_path)
    assert manifest.authorized_modelos == frozenset({"130", "303"})


def test_fragment_stem_must_match_modelo_id(tmp_path: Path) -> None:
    """A fragment whose filename stem disagrees with its modelo id is rejected."""
    # Body declares 130 but the file is named 131.toml.
    _write_fragment(tmp_path, "131", _VALID_130)
    with pytest.raises(AuthorizationManifestError, match="does not match"):
        load_authorization_manifest(tmp_path)


def test_single_year_fragment_is_rejected(tmp_path: Path) -> None:
    """A fragment claiming fewer than two distinct renta years fails to load."""
    _write_fragment(
        tmp_path,
        "130",
        """
[modelo]
modelo = "130"
renta_years = [2025]
evidence_class = "calculation"
enrolling_test = "x.py"
""",
    )
    with pytest.raises(AuthorizationManifestError):
        load_authorization_manifest(tmp_path)


def test_missing_modelo_table_is_rejected(tmp_path: Path) -> None:
    """A fragment with no [modelo] table fails loudly."""
    _write_fragment(tmp_path, "130", "renta_years = [2025, 2026]\n")
    with pytest.raises(AuthorizationManifestError, match="exactly one"):
        load_authorization_manifest(tmp_path)


def test_duplicate_modelo_across_fragments_is_rejected(tmp_path: Path) -> None:
    """Two fragments cannot both enroll the same modelo id.

    The stem cross-check forces distinct filenames, so the duplicate must be
    smuggled in via a fragment whose stem matches but whose internal id is
    re-used by a sibling. Here both 130.toml and 130-dup.toml declare 130;
    the stem cross-check rejects the second before the manifest-level dedup,
    which is the stricter, earlier failure — either way it does not load.
    """
    _write_fragment(tmp_path, "130", _VALID_130)
    _write_fragment(tmp_path, "130-dup", _VALID_130)
    with pytest.raises(AuthorizationManifestError):
        load_authorization_manifest(tmp_path)


def test_manifest_dir_resolves_under_root(tmp_path: Path) -> None:
    """manifest_dir points at authorization.d under the registry root."""
    assert manifest_dir(tmp_path) == tmp_path / AUTHORIZATION_MANIFEST_DIRNAME


def test_derive_authorization_from_loaded_manifest(tmp_path: Path) -> None:
    """A loaded fragment makes its modelo AUTHORIZED; an absent one stays UNAUTHORIZED."""
    _write_fragment(tmp_path, "130", _VALID_130)
    manifest = load_authorization_manifest(tmp_path)
    authorized = derive_modelo_authorization("130", manifest=manifest, has_engine=True)
    assert authorized.state is AuthorizationState.AUTHORIZED
    assert authorized.is_authorized
    unauthorized = derive_modelo_authorization("303", manifest=manifest, has_engine=True)
    assert unauthorized.state is AuthorizationState.UNAUTHORIZED
    assert not unauthorized.is_authorized
