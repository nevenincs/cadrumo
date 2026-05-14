"""Forbidden-import test for the Google OAuth Desktop adapter.

Guards `src/aeat/adapters/outbound/google/` against the reintroduction
of pre-teardown scaffold modules (`_oauth_legacy*`, `_gcloud*`) and
asserts the v1 module list stays minimal — every file in the package
must be one of the canonical v1 modules from the master plan's
`P01.S00` description, plus the public `__init__.py`.

The test introspects the source tree directly (not via Python import)
so it stays runnable even when the broader import chain is broken
mid-restructure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


_PACKAGE_ROOT = Path(__file__).resolve().parent

_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "_errors.py",
        "_oauth_flow.py",
        "_profile_binding.py",
        "_records.py",
        "_refresh.py",
        "_session_store.py",
        "test_no_legacy_modules.py",
        "test_oauth_live.py",
        "test_records.py",
    }
)


_FORBIDDEN_PREFIXES: tuple[str, ...] = ("_oauth_legacy", "_gcloud", "_paths")
_FORBIDDEN_FILE_NAMES: frozenset[str] = frozenset({"test_google_auth.py"})


def test_google_package_directory_exists() -> None:
    assert _PACKAGE_ROOT.is_dir(), (
        f"expected {_PACKAGE_ROOT} to exist; if the package was deleted by mistake, restore it"
    )


def test_no_legacy_or_scaffold_modules_survive() -> None:
    """No pre-teardown scaffold artifact may live under the v1 package."""

    offending: list[str] = []
    for entry in _PACKAGE_ROOT.iterdir():
        if entry.is_dir():
            continue
        name = entry.name
        if name.startswith(_FORBIDDEN_PREFIXES):
            offending.append(name)
        if name in _FORBIDDEN_FILE_NAMES:
            offending.append(name)
    assert offending == [], (
        f"forbidden scaffold/legacy modules found under {_PACKAGE_ROOT.name}: {offending}; "
        "remove them or extend the allow-list above with intentional rationale"
    )


def test_only_v1_modules_present_in_package() -> None:
    """Every `.py` in the package must be on the canonical v1 module list.

    A new untracked `.py` file means somebody added a module without
    updating the v1 allow-list above. Either add it to `_ALLOWED_MODULES`
    with rationale or remove the file.
    """

    found_files = {entry.name for entry in _PACKAGE_ROOT.iterdir() if entry.is_file() and entry.suffix == ".py"}
    unexpected = sorted(found_files - _ALLOWED_MODULES)
    assert unexpected == [], (
        f"unexpected .py files in {_PACKAGE_ROOT.name}: {unexpected}; "
        f"add to _ALLOWED_MODULES with rationale or remove"
    )
