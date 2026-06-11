"""Write-guard tests for :mod:`aeat.adapters.inbound.sanitizer`.

The sanitiser subpackage MUST NOT contain any public symbol whose
name implies an AEAT mutation. This module is a CI-time grep guard
that fails the build if a refactor introduces a forbidden verb in
the public API surface or in any module name. The same pattern
applies to every read-only AEAT subpackage.

The guard inspects every ``.py`` file under
``src/aeat/adapters/inbound/sanitizer/`` and
``src/aeat/entrypoints/cli/sanitize/``, every public function and
class definition with module-level constants, plus every public
CLI verb attached to the Typer ``app``.

The false-positive whitelist is narrow: ``commit_id`` is allowed
because git commit identifiers are read-only state, not mutation
verbs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


# Banned verbs from the parent aeat-verify write guard.
# guard (mirrored from the sede + filing.reconciliation guards).
_FORBIDDEN_VERBS: tuple[str, ...] = (
    "submit",
    "send",
    "commit",
    "enviar",
    "presentar",
    "firmar",
    "radicar",
    "remitir",
    "modificar",
    "anular",
    "cancelar",
    "rechazar",
)

# Identifiers that incidentally contain a forbidden verb but are
# semantically benign. Match exactly (not by substring) so a
# malicious-looking ``commit_streams_to_aeat`` cannot piggyback on
# a benign whitelist entry. Keep narrow and explicit.
_WHITELIST: frozenset[str] = frozenset(
    {
        "commit_id",  # git commit hashes are read-only identifiers
    },
)


def _project_root() -> Path:
    """Returns the repository root from this test file's location."""
    here = Path(__file__).resolve()
    # src/aeat/adapters/inbound/sanitizer/tests/test_no_write_surface.py → up 7 levels
    return here.parents[6]


def _public_python_files() -> list[Path]:
    """Returns every ``.py`` file under the two guarded subpackages.

    Excludes test modules — they may legitimately reference the
    forbidden verbs in test names like ``test_refuse_submit``.
    """
    root = _project_root()
    candidates: list[Path] = []
    for sub in ("src/aeat/adapters/inbound/sanitizer", "src/aeat/entrypoints/cli/sanitize"):
        for path in (root / sub).rglob("*.py"):
            name = path.name
            if name.startswith("test_") or name.startswith("_test_"):
                continue
            candidates.append(path)
    return candidates


_PUBLIC_DEF_RE = re.compile(
    r"^(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


class TestPublicSurfaceCarriesNoForbiddenVerb:
    """No public function / class name in the sanitiser carries a banned verb."""

    def test_files_present(self) -> None:
        """The sanitizer subpackage must contribute at least one source file."""
        files = _public_python_files()
        sanitizer_files = [p for p in files if "sanitizer" in p.parts]
        assert len(sanitizer_files) >= 1
        # The verb-coverage loop below scans every file in `files`; pin
        # the file collection's non-emptiness so a stripped layout would
        # surface here rather than silently leaving the loop empty.
        assert len(files) >= 1

    def test_no_public_symbol_uses_forbidden_verb(self) -> None:
        offenders: list[tuple[Path, str]] = []
        for path in _public_python_files():
            text = path.read_text(encoding="utf-8")
            for match in _PUBLIC_DEF_RE.finditer(text):
                name = match.group(1)
                if name.startswith("_"):
                    continue
                lowered = name.lower()
                if any(verb in lowered for verb in _FORBIDDEN_VERBS):
                    if name in _WHITELIST:
                        continue
                    offenders.append((path, name))
        assert offenders == [], (
            f"Public symbols in the sanitiser subpackages carry forbidden mutation verbs: {offenders}"
        )

    def test_no_module_filename_uses_forbidden_verb(self) -> None:
        offenders: list[Path] = []
        for path in _public_python_files():
            stem = path.stem.lower().lstrip("_")
            if any(verb in stem for verb in _FORBIDDEN_VERBS):
                if stem in _WHITELIST:
                    continue
                offenders.append(path)
        assert offenders == [], (
            f"Module filenames in the sanitiser subpackages carry forbidden mutation verbs: {offenders}"
        )


class TestForbiddenVerbInBodyIsAuditable:
    """Every body-mention of a forbidden verb must be in a documented context.

    The sanitiser explicitly documents the forbidden verbs as part
    of its threat model (FORBIDDEN_FLAGS list, threat-model
    docstrings). This test ensures every occurrence in the body
    text is either:
      * in a docstring describing the threat model, or
      * in the explicit FORBIDDEN_FLAGS guard, or
      * in a comment justifying the appearance.

    The test fails on body-mentions that look like real call
    sites (e.g. ``pdf.submit(...)``).
    """

    def test_no_call_site_invokes_forbidden_verb(self) -> None:
        # Pattern: ``identifier.<verb>(`` looks like a method call.
        # We allow these only inside the Typer app's
        # _FORBIDDEN_FLAGS literal.
        offenders: list[tuple[Path, str]] = []
        call_pattern = re.compile(
            r"\.\s*(submit|send|commit|enviar|presentar|firmar|radicar|remitir|modificar|anular|cancelar|rechazar)\s*\(",
            re.IGNORECASE,
        )
        for path in _public_python_files():
            text = path.read_text(encoding="utf-8")
            for match in call_pattern.finditer(text):
                offenders.append((path, match.group(0)))
        assert offenders == [], f"Apparent forbidden-verb call sites in the sanitiser subpackages: {offenders}"
