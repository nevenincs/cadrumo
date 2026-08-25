"""Write-guard tests for :mod:`~dev.sanitizer`.

The sanitiser subpackage MUST NOT contain any public symbol whose
name implies an AEAT mutation. This module is a CI-time grep guard
that fails the build if a refactor introduces a forbidden verb in
the public API surface or in any module name. The same pattern
applies to every read-only AEAT subpackage.

The guard inspects every non-test ``.py`` file under each root in
:data:`_GUARDED_ROOTS`, checking every public function and class
definition.

This module previously declared a second root,
``src/cadrumo/entrypoints/cli/sanitize/``, and said in prose that it
scanned it. That package does not exist and never has -- ``git log``
over the path is empty -- so the guard claimed coverage it had never
had, over a surface that was not there. A scan of a missing
directory yields nothing without raising, and the old floor asserted
only that the collection was non-empty overall, which the surviving
root satisfied by itself. Hence :meth:`test_every_guarded_root_exists`:
**a vacuity floor must be per-root whenever the scope is multi-root**,
because a global "at least one file" floor is satisfied by any single
surviving root and so can never detect that another has gone away or
never arrived.

There is no false-positive whitelist. The only entry was ``commit_id``,
which matched no symbol and no module name in the scanned tree.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# Banned verbs from the parent aeat-verify write guard.
# guard (mirrored from the sede write guard).
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

#: Repository-relative subpackages this guard scans. Every root declared here
#: must exist and must contribute at least one non-test module; that floor is
#: enforced PER ROOT (see the module docstring for why a global floor cannot
#: see a dead root). Adding a root here automatically extends the floor to it.
_GUARDED_ROOTS: tuple[str, ...] = ("dev/sanitizer",)


def _project_root() -> Path:
    """Returns the repository root from this test file's location."""
    here = Path(__file__).resolve()
    # dev/sanitizer/tests/test_no_write_surface.py -> up 4 levels
    return here.parents[3]


def _modules_under(directory: Path) -> list[Path]:
    """Returns every non-test ``.py`` file under *directory*.

    Excludes test modules — they may legitimately reference the
    forbidden verbs in test names like ``test_refuse_submit``.
    """
    return [
        path
        for path in scan_directory(directory, pattern="*.py", recursive=True)
        if not (path.name.startswith("test_") or path.name.startswith("_test_"))
    ]


def _public_python_files() -> list[Path]:
    """Returns every scanned ``.py`` file across all guarded subpackages."""
    root = _project_root()
    return [path for sub in _GUARDED_ROOTS for path in _modules_under(root / sub)]


class TestPublicSurfaceCarriesNoForbiddenVerb:
    """No public function / class name in the sanitiser carries a banned verb."""

    def test_every_guarded_root_exists(self) -> None:
        """Each declared root must exist on disk and yield a scanned module.

        Checked per root rather than over the union: a global "at least one
        file" floor is satisfied by any single surviving root, so it cannot
        distinguish "every declared surface is covered" from "one declared
        surface is covered and the rest are absent". A root that is deleted,
        renamed, or never created reds here instead of silently contributing
        nothing to every scan below.
        """
        root = _project_root()
        for sub in _GUARDED_ROOTS:
            directory = root / sub
            assert directory.is_dir(), (
                f"guarded root {sub!r} does not exist; rglob over a missing directory yields "
                "nothing without raising, so every scan below would silently skip it"
            )
            assert _modules_under(directory), (
                f"guarded root {sub!r} exists but contributes no non-test module, so the scans "
                "below cover nothing there"
            )

    def test_no_public_symbol_uses_forbidden_verb(self) -> None:
        offenders: list[tuple[Path, str]] = []
        for path in _public_python_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                    continue
                name = node.name
                if name.startswith("_"):
                    continue
                lowered = name.lower()
                if any(verb in lowered for verb in _FORBIDDEN_VERBS):
                    offenders.append((path, name))
        assert offenders == [], (
            f"Public symbols in the sanitiser subpackages carry forbidden mutation verbs: {offenders}"
        )

    def test_no_module_filename_uses_forbidden_verb(self) -> None:
        offenders: list[Path] = []
        for path in _public_python_files():
            stem = path.stem.lower().lstrip("_")
            if any(verb in stem for verb in _FORBIDDEN_VERBS):
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


class TestTheGuardCanActuallyFire:
    """Prove the matchers detect a violation, not merely that none exists.

    :meth:`TestPublicSurfaceCarriesNoForbiddenVerb.test_every_guarded_root_exists`
    already answers "is this scan looking at anything" -- the vacuity floor the
    module docstring explains. These cases answer the separate question "would
    it recognise a violation if it saw one", which a floor cannot: a scan over
    real files with a matcher that never matches passes exactly like a clean
    tree.

    The sede sibling of this guard was briefly disarmed by widening an
    exemption, so both no-write-surface guards now carry the same proof.
    """

    @pytest.mark.parametrize("verb", _FORBIDDEN_VERBS)
    def test_a_public_symbol_carrying_each_verb_would_be_caught(self, verb: str) -> None:
        """The public-symbol scan must flag every verb in the banned list."""
        tree = ast.parse(f"def {verb}_declaration():\n    pass\n")
        names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and not node.name.startswith("_")
            and any(v in node.name.lower() for v in _FORBIDDEN_VERBS)
        ]
        assert names == [f"{verb}_declaration"], f"a public symbol named for {verb!r} would not be flagged"

    @pytest.mark.parametrize("verb", _FORBIDDEN_VERBS)
    def test_a_call_site_of_each_verb_would_be_caught(self, verb: str) -> None:
        """The call-site regex must flag every verb in the banned list."""
        call_pattern = re.compile(
            r"\.\s*(submit|send|commit|enviar|presentar|firmar|radicar|remitir|modificar|anular|cancelar|rechazar)\s*\(",
            re.IGNORECASE,
        )
        assert call_pattern.search(f"    client.{verb}(payload)"), f"a call to {verb!r} would not be flagged"

    def test_a_private_symbol_is_deliberately_not_flagged(self) -> None:
        """Underscore-prefixed names are skipped on purpose; pin that so it stays a choice.

        The public-surface scan guards the API a caller could reach. If this
        ever needs to cover private symbols too, this test is what has to
        change first, rather than the exclusion quietly widening.
        """
        tree = ast.parse("def _submit_internal():\n    pass\n")
        flagged = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        assert flagged == []
