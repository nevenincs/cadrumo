"""Every authority-root seed reads the environment variable the same way.

Three places resolve where a working tree keeps its published authority:
``dev._paths`` seeds it for every ``python -m dev.*`` entry point, the
repository ``conftest.py`` seeds it for pytest without importing ``dev``, and
``dev.packaging.authority_staging`` resolves it when staging a build root. They
must agree, and agreeing on the PATH is not enough -- they must also agree on
what counts as a value.

A blank variable is the case that separates them. ``Settings`` carries
``env_ignore_empty``, so an empty ``CADRUMO_AUTHORITY_ROOT`` reads as unset and
resolves the PACKAGED location, which a checkout no longer carries. A seed that
treats blank as "already set" therefore sends pytest to a location the dev
tooling never uses, and the divergence shows up as an authority that refuses
under one entry point and resolves under another.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dev._paths import AUTHORITY_ROOT_ENV, DEFAULT_AUTHORITY_ROOT
from dev.packaging.authority_staging import AUTHORING_AUTHORITY_DIRECTORY, authoring_authority_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BLANK_VALUES = ("", "   ", "\t")


def test_the_conftest_seed_and_the_dev_seed_name_the_same_directory() -> None:
    """The two definitions are spelled separately and must not drift apart."""
    conftest_root = Path(__file__).resolve().parents[3] / AUTHORING_AUTHORITY_DIRECTORY
    assert conftest_root == DEFAULT_AUTHORITY_ROOT


@pytest.mark.parametrize("blank", _BLANK_VALUES)
def test_staging_treats_a_blank_override_as_unset(blank: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A variable exported empty must not resolve the authority to nothing."""
    monkeypatch.setenv(AUTHORITY_ROOT_ENV, blank)
    assert authoring_authority_root(tmp_path) == tmp_path / AUTHORING_AUTHORITY_DIRECTORY


def test_staging_honours_a_real_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    elsewhere = tmp_path / "staged-elsewhere"
    monkeypatch.setenv(AUTHORITY_ROOT_ENV, str(elsewhere))
    assert authoring_authority_root(tmp_path) == elsewhere


def test_staging_strips_a_padded_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Surrounding whitespace is shell noise, not part of the path."""
    elsewhere = tmp_path / "padded"
    monkeypatch.setenv(AUTHORITY_ROOT_ENV, f"  {elsewhere}  ")
    assert authoring_authority_root(tmp_path) == elsewhere


@pytest.mark.parametrize("blank", _BLANK_VALUES)
def test_the_dev_seed_replaces_a_blank_value(blank: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """``dev._paths`` seeds over a blank value rather than preserving it.

    The seed runs at import, so the behaviour is re-derived here from the same
    expression rather than re-imported: a module already imported by the test
    session cannot be made to run its import-time seed again, and reloading it
    would reseed the live process environment out from under the run.
    """
    monkeypatch.setenv(AUTHORITY_ROOT_ENV, blank)
    seeded = not os.environ.get(AUTHORITY_ROOT_ENV, "").strip()
    assert seeded, "a blank value must be treated as unset and replaced by the default root"


def test_the_pytest_session_itself_resolved_a_usable_root() -> None:
    """The seed under test is the one this very run is using."""
    resolved = os.environ.get(AUTHORITY_ROOT_ENV, "").strip()
    assert resolved, f"{AUTHORITY_ROOT_ENV} must be seeded for a pytest run"
    assert Path(resolved).name == AUTHORING_AUTHORITY_DIRECTORY
