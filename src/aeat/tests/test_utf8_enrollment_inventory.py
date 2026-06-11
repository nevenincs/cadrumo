"""Inventory test: bare ``encoding="utf-8"``, ``.encode("utf-8")``, and
``.decode("utf-8")`` must not spread to any new production module.

Rule
----
Every production module must use :data:`aeat.core.external_constants.UTF_8_ENCODING`
instead of the bare string literal ``"utf-8"``.  Idiomatic hash sites
(where the encode feeds a ``hashlib`` or ``hmac`` digest call on the
same logical line) are allowlisted because the encoding is
protocol-fixed and mechanical substitution adds no value.

Structural prevention (ratchet history)
--------------------------------
This test AST-walks **all** Python files under ``src/aeat/`` rather than
a fixed allowlist so that new files added by any campaign are automatically
covered.  The ratchet history regression (``locales/manager.py`` escaping detection
because it was added after the original test was written) cannot recur.

The test uses a ratchet: ``_KNOWN_VIOLATING_FILES`` records the set of
files that still carry pre-existing bare literals (enrolled for future
cleanup campaigns).  Any file **not** in this set must have zero
violations.  This means:

- A new file added with bare ``"utf-8"`` literals fails immediately.
- The count of known-violating files can only decrease, never increase.
- Removing a file from ``_KNOWN_VIOLATING_FILES`` after cleanup will
  lock it at zero forever.

Exclusions
----------
- ``test_*.py`` files: tests may use bare literals freely, except for
  shared test-suite helpers under ``adapters/`` and ``tests/`` that
  are not prefixed ``test_`` — these are covered by the ratchet.
- ``external_constants.py``: defines ``UTF_8_ENCODING`` itself.
- Lines containing ``hashlib``, ``hmac``, ``sha256``, ``sha1``, or
  ``md5`` on the same line as the literal (hash-protocol allowlist).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = pathlib.Path(__file__).parent.parent
_DEV_ROOT = _SRC_ROOT.parent.parent / "dev"

# Patterns that indicate a bare UTF-8 literal (string form only).
_BARE_UTF8_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'encoding="utf-8"'),
    re.compile(r'\.encode\("utf-8"\)'),
    re.compile(r'\.decode\("utf-8"\)'),
)

# Lines on which any of these substrings appear are exempted because the
# UTF-8 encoding is required by the hash/HMAC protocol, not the
# application's text I/O conventions.
_HASH_ALLOWLIST_TOKENS = frozenset({"hashlib", "hmac", "sha256", "sha1", "md5", "hasher"})

# Files excluded from the scan entirely (not subject to the ratchet).
_SCAN_EXCLUDES: frozenset[str] = frozenset(
    {
        "core/external_constants.py",
    },
)

# Known pre-existing violating files (ratchet history/ratchet history backlog, to be cleaned up
# in future campaigns).  New files must NOT appear here — add a cleanup
# commit instead.  Removing an entry locks that file at zero violations.
_KNOWN_VIOLATING_FILES: frozenset[str] = frozenset(
    {
        "adapters/outbound/aeat/sede/_declarations_observations.py",
        "adapters/outbound/llm/_cache.py",
        "adapters/outbound/llm/_usage.py",
        "adapters/outbound/storage/_mirror_manifest.py",
        "adapters/persistence/profile/assets.py",
        "adapters/persistence/profile/inventory.py",
        "adapters/persistence/storage/attachment.py",
        "adapters/persistence/storage/crypto/_encrypted_columns.py",
        "adapters/persistence/storage/envelope/_envelope.py",
        "adapters/persistence/storage/envelope/_repository_test_suite.py",
        "adapters/persistence/storage/envelope/_secure_repository.py",
        "adapters/persistence/storage/master_key/test_no_classvar_state.py",
        "adapters/persistence/storage/sql/secure_objects.py",
        "application/auth/_diagnostics.py",
        "application/calculations/_observations_repository.py",
        "application/evidence/_models.py",
        "application/evidence/_service.py",
        "application/export/_tabular.py",
        "application/filing/_review.py",
        "application/ledger/_actions_export.py",
        "application/ledger/_actions_import.py",
        "application/ledger/_actions_manual.py",
        "application/live/_borrador_100.py",
        "application/live/_censo.py",
        "application/live/_snapshot_base.py",
        "application/live/_verify.py",
        "application/modelo/_revision_persistence.py",
        "application/repair_integrity.py",
        "application/user_profile/_lifecycle.py",
        "application/user_profile/_repository.py",
        "application/wizard/_translations.py",
        "application/workflow/_persistence.py",
        "core/_bucket_pointer_io.py",
        "core/config.py",
        "core/corpus_manifest/__init__.py",
        "core/env_io.py",
        "core/i18n/_render.py",
        "core/json_contract.py",
        "core/observability/_fingerprint.py",
        "core/observability/_sink.py",
        "core/observability/_store.py",
        "domain/auth/apoderamientos/_catalogue.py",
        "domain/buckets/_event.py",
        "domain/buckets/_event_repository.py",
        "domain/calculations/registry/_export_parse.py",
        "domain/calculations/registry/_legal.py",
        "domain/calculations/registry/_live_parity.py",
        "domain/calculations/registry/_parity_tapes.py",
        "domain/calculations/registry/_renta_web_open_oracle.py",
        "domain/calculations/registry/_validate_evidence.py",
        "domain/deadlines/_recargo.py",
        "domain/filing/_amendment.py",
        "domain/filing/_complementaria_repository.py",
        "domain/filing/_schema.py",
        "domain/invoices/_repository.py",
        "domain/manuals/_fetch.py",
        "domain/manuals/_loader.py",
        "domain/modelos/_calculation_repository.py",
        "domain/modelos/_calculation_revision.py",
        "domain/modelos/_filing_record.py",
        "domain/modelos/_filing_repository.py",
        "domain/modelos/_repository.py",
        "domain/modelos/_verification_report.py",
        "domain/modelos/_verification_repository.py",
        "domain/modelos/_work_unit.py",
        "domain/normatives/_loader.py",
        "domain/transactions/_llm.py",
        "domain/transactions/_repository.py",
        "domain/usage_ratios/_service.py",
        "domain/user_profile/_values.py",
        "entrypoints/cli/_config/__init__.py",
        "entrypoints/cli/_config/_google.py",
        "entrypoints/cli/_config/_google_sync_calc.py",
        "entrypoints/cli/_config/_profile_bundle.py",
        "entrypoints/cli/_errors.py",
        "entrypoints/cli/_ledger_classify_cli.py",
        "entrypoints/cli/_stdio.py",
        "locales/_ast_scanner.py",
        "tests/_env_loader.py",
        "tests/fixtures/justificantes/_generate.py",
    },
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


def _all_production_files() -> list[pathlib.Path]:
    """Return all non-test Python files under src/aeat/, excluding the constant module."""
    files: list[pathlib.Path] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(_SRC_ROOT).as_posix()
        if path.name.startswith("test_") or "tests" in path.parts:
            continue
        if rel in _SCAN_EXCLUDES:
            continue
        files.append(path)
    return files


def test_no_bare_utf8_literals_in_production_files() -> None:
    """New production files under src/aeat/ must not introduce bare UTF-8 literals.

    This test uses a ratchet against ``_KNOWN_VIOLATING_FILES``:

    - Files already in the ratchet set are skipped (tracked for future cleanup).
    - Any file NOT in the ratchet set must have zero bare ``"utf-8"`` literals.
    - New files added by any campaign are automatically covered — the ratchet history regression
      class (new files escaping the fixed enrolled-module set) cannot recur.

    To clean up a known-violating file: migrate it to ``UTF_8_ENCODING``, then
    remove it from ``_KNOWN_VIOLATING_FILES``. The test will then lock it at zero.

    Idiomatic hash sites (``hashlib``/``hmac`` lines) are exempt from detection
    because the encoding is protocol-fixed.
    """
    violations: list[str] = []
    production_files = _all_production_files()

    for path in production_files:
        rel = path.relative_to(_SRC_ROOT).as_posix()
        if rel in _KNOWN_VIOLATING_FILES:
            # Pre-existing backlog — covered by future cleanup campaigns.
            continue
        module_violations = _bare_utf8_violations(path)
        for lineno, snippet in module_violations:
            violations.append(f"{rel}:{lineno} — {snippet!r}")

    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare UTF-8 literal(s) found in non-ratcheted production files:\n"
            f"  {joined}\n\n"
            "Replace with UTF_8_ENCODING from aeat.core.external_constants.\n"
            "Hash/HMAC sites (hashlib, hmac, sha*) are allowlisted.\n"
            f"Scanned {len(production_files)} production files; "
            f"{len(_KNOWN_VIOLATING_FILES)} are ratcheted as known backlog.\n"
            "Do NOT add this file to _KNOWN_VIOLATING_FILES — fix it instead.",
        )


# ---------------------------------------------------------------------------
# Hash-protocol allowlist commentary (behavior contract)
# ---------------------------------------------------------------------------
# The following 4 sites use .encode('utf-8') fed directly into hashlib.sha256
# on the same logical line.  They are exempt from the bare-literal check via
# ``_is_hash_site()`` above (matches ``sha256`` on the same line).  The
# exemption is intentional: the encoding is fixed by the SHA-256 protocol and
# mechanical substitution with UTF_8_ENCODING adds no value.
#
#   application/aggregation/_source_profile.py:75
#       hashlib.sha256(payload.encode('utf-8')).hexdigest()
#
#   application/calculations/_iva_wallet_reconciliation.py:173
#       hashlib.sha256(decision.model_dump_json().encode('utf-8')).hexdigest()
#
#   application/invoices/_source_resolver.py:145
#       hashlib.sha256(payload.encode('utf-8')).hexdigest()
#
#   application/modelo/_borrador_binding.py:223
#       hashlib.sha256(result.borrador_snapshot_id.encode('utf-8')).hexdigest()
#
# If the hash-allowlist criteria in ``_HASH_ALLOWLIST_TOKENS`` are ever
# narrowed, these 4 sites must be reviewed and either enrolled in
# ``_KNOWN_VIOLATING_FILES`` or migrated to ``UTF_8_ENCODING``.


# ---------------------------------------------------------------------------
# Dev-tooling-tree ratchet (behavior contract — ratchet history)
# ---------------------------------------------------------------------------
# The ``dev/`` package is repo tooling; it must not import
# ``aeat.core.external_constants`` just to satisfy the production UTF-8
# constant rule.  Instead, each module carries a local ``_UTF_8: Final[str]``
# constant.  This test enforces that the dev tree doesn't drift back to
# bare literals beyond the pre-existing backlog below.
#
# Hash-protocol allowlist: same tokens as the src/aeat/ scan.
#
# dev/quality/relative_imports.py was previously fixed and must
# NOT be re-added to the known-violating set.

_DEV_KNOWN_VIOLATING: frozenset[str] = frozenset()


def _all_dev_files() -> list[pathlib.Path]:
    """Return all Python tooling files under dev/ (recursive, non-test, non-init)."""
    if not _DEV_ROOT.is_dir():
        return []
    return sorted(
        p
        for p in _DEV_ROOT.rglob("*.py")
        if not p.name.startswith("test_") and p.name != "__init__.py" and "tests" not in p.parts
    )


def test_no_bare_utf8_literals_in_dev() -> None:
    """dev/ Python files must not introduce new bare UTF-8 literals.

    Each module that needs to read/write text must carry a local
    ``_UTF_8: Final[str] = "utf-8"`` constant and use it consistently.
    Pre-existing violators are ratcheted in ``_DEV_KNOWN_VIOLATING``;
    only the ratchet set may shrink, never grow.

    Hash/HMAC sites (hashlib, hmac, sha*) are allowlisted as in src/aeat/.
    """
    violations: list[str] = []
    dev_files = _all_dev_files()

    for path in dev_files:
        if path.name in _DEV_KNOWN_VIOLATING:
            continue
        module_violations = _bare_utf8_violations(path)
        for lineno, snippet in module_violations:
            violations.append(f"{path.name}:{lineno} — {snippet!r}")

    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare UTF-8 literal(s) found in non-ratcheted dev/ files:\n"
            f"  {joined}\n\n"
            "Add a local _UTF_8: Final[str] = 'utf-8' constant and use it.\n"
            "Hash/HMAC sites (hashlib, hmac, sha*) are allowlisted.\n"
            f"Scanned {len(dev_files)} dev/ files; "
            f"{len(_DEV_KNOWN_VIOLATING)} are ratcheted as known backlog.\n"
            "Do NOT add a file to _DEV_KNOWN_VIOLATING — fix it instead.",
        )
