"""Terminal-attachment is probed in exactly one place.

``core.tty`` owns the ``isatty`` probe. Production code asks it whether a
stream is a terminal; it never calls ``stream.isatty()`` itself.

This gate exists because the singularity was claimed and false. The probe
lived in ``entrypoints/cli/_tty.py`` under a docstring stating it "centralises
the rules every CLI command uses" — while **nothing imported it**, and seven
production sites open-coded ``sys.stdin.isatty()`` instead. The cause was
structural: ``entrypoints`` is the top layer of the hexagonal contract, so the
adapters that most needed the probe (Google OAuth consent, the master-key
passphrase prompt) could not legally import it and each rolled their own. The
primitive moved to ``core``, where every layer may reach it.

A bare ``stream.isatty()`` is not merely duplication, it is weaker: it raises
on a missing, closed or detached stream, which is exactly the headless
condition the caller is asking about, so the guard dies instead of refusing.

Legitimate stricter checks are NOT barred. ``_secure_input`` pairs the probe
with a real-console check because on Windows both ``NUL`` and a console-less
host report ``isatty() is True``; it calls ``stdin_is_tty()`` and keeps its own
extra probe on top. Layering a stronger condition over the shared primitive is
the sanctioned shape — re-deriving the primitive is not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...tests import production_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_OWNER = Path("core") / "tty.py"


def _probes_a_stream(tree: ast.AST) -> bool:
    """Whether the module reaches the terminal probe itself.

    Two spellings count, because the owner uses the second and a re-derivation
    would too: a direct ``stream.isatty()`` attribute call, and a
    ``getattr(stream, "isatty", ...)`` lookup that defers the same syscall
    behind a local name. Matching only the attribute form would let the exact
    shape the owner uses reappear elsewhere unnoticed.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "isatty":
                return True
            if (
                isinstance(func, ast.Name)
                and func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "isatty"
            ):
                return True
    return False


def test_only_core_tty_probes_the_terminal_directly() -> None:
    """No production module outside ``core.tty`` may probe a stream itself."""
    offenders: list[str] = []
    owner_seen = False

    for path in production_python_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        if "isatty" not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover - a syntax error is another gate's job
            continue
        if not _probes_a_stream(tree):
            continue  # a docstring or comment mentioning it, not a probe
        if path.parts[-2:] == _OWNER.parts:
            owner_seen = True
            continue
        offenders.append(str(path))

    # Anti-vacuity: if the owner itself stops probing, the scan proves nothing
    # and an empty offender list would read as compliance. This assertion has
    # already earned its place — the first version of this gate matched only
    # attribute calls, missed the owner's own getattr form, and fired here
    # rather than reporting a false clean.
    assert owner_seen, "core/tty.py no longer probes a stream; this gate is inspecting nothing"

    assert offenders == [], (
        "production code must ask core.tty rather than probe a stream itself "
        "(a bare isatty() raises on a closed or detached stream, which is the "
        f"very case being guarded): {offenders}"
    )
