"""Inventory test: bare ``encoding="utf-8"``, ``.encode("utf-8")``, and
``.decode("utf-8")`` must be absent from enrolled production modules.

Rule
----
Every enrolled production module must use :data:`aeat.core.external_constants.UTF_8_ENCODING`
instead of the bare string literal ``"utf-8"``.  Idiomatic hash sites
(where the encode feeds a ``hashlib`` or ``hmac`` digest call on the
same logical line) are allowlisted because the encoding is
protocol-fixed and mechanical substitution adds no value.

Exclusions
----------
- ``test_*.py`` files: tests may use bare literals freely.
- Lines containing ``hashlib``, ``hmac``, ``sha256``, ``sha1``, or
  ``md5`` on the same line as the literal (hash-protocol allowlist).
- The ``external_constants.py`` module itself (defines the constant).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

# Patterns that indicate a bare UTF-8 literal (string form only).
_BARE_UTF8_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'encoding="utf-8"'),
    re.compile(r'\.encode\("utf-8"\)'),
    re.compile(r'\.decode\("utf-8"\)'),
)

# Lines on which any of these substrings appear are exempted because the
# UTF-8 encoding is required by the hash/HMAC protocol, not the
# application's text I/O conventions.
_HASH_ALLOWLIST_TOKENS = frozenset({"hashlib", "hmac", "sha256", "sha1", "md5"})

# Modules enrolled in the W07.P31 UTF-8 sweep.  Once enrolled, a module
# must stay at zero bare-literal violations forever.
_ENROLLED_MODULES: frozenset[str] = frozenset(
    {
        # S502 — auth session store
        "adapters/outbound/aeat/auth/_session_store.py",
        # S503 — auth certificate + clave_movil
        "adapters/outbound/aeat/auth/certificate.py",
        "adapters/outbound/aeat/auth/_clave_movil.py",
        # S504 — persistence layer
        "adapters/outbound/storage/_local.py",
        "adapters/persistence/storage/bucket/_lockfile.py",
        "adapters/persistence/storage/secret_store/_secret_store.py",
        "adapters/persistence/storage/_rotation.py",
        # S505 — application layer
        "application/auth/_acquisition_lock.py",
        "application/ledger/_evidence.py",
        "application/ledger/_business_operation_invoice.py",
        "application/invoices/_importing.py",
    }
)


def _is_hash_site(line: str) -> bool:
    """Return True when the line contains a hash/HMAC function call."""
    return any(token in line for token in _HASH_ALLOWLIST_TOKENS)


def _bare_utf8_violations(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return (lineno, line) pairs where a bare UTF-8 literal survives."""
    violations: list[tuple[int, str]] = []
    source = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _is_hash_site(line):
            continue
        if any(pat.search(line) for pat in _BARE_UTF8_PATTERNS):
            violations.append((lineno, line.strip()))
    return violations


def test_no_bare_utf8_literals_in_enrolled_modules() -> None:
    """Enrolled modules must contain zero bare UTF-8 encoding literals.

    Each enrolled module has been migrated to use
    ``UTF_8_ENCODING`` from :mod:`aeat.core.external_constants`.
    Any regression that re-introduces the bare string literal will be
    caught here.

    Idiomatic hash sites (``hashlib``/``hmac`` lines) are exempt
    because the encoding is protocol-fixed.
    """
    violations: list[str] = []
    for rel_module in sorted(_ENROLLED_MODULES):
        path = _SRC_ROOT / rel_module
        if not path.exists():
            violations.append(f"MISSING: {rel_module}")
            continue
        module_violations = _bare_utf8_violations(path)
        for lineno, snippet in module_violations:
            violations.append(f"{rel_module}:{lineno} — {snippet!r}")

    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare UTF-8 literal(s) found in enrolled modules:\n"
            f"  {joined}\n\n"
            "Replace with UTF_8_ENCODING from aeat.core.external_constants.\n"
            "Hash/HMAC sites (hashlib, hmac, sha*) are allowlisted."
        )
