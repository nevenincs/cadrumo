"""Inventory test: bare ``encoding="utf-8"``, ``.encode("utf-8")``, and
``.decode("utf-8")`` must not spread to any new production module.

Rule
----
Every production module must use :data:`~core.external_constants.UTF_8_ENCODING`
instead of the bare string literal ``"utf-8"``.  Idiomatic hash sites
(where the encode feeds a ``hashlib`` or ``hmac`` digest call on the
same logical line) are allowlisted because the encoding is
protocol-fixed and mechanical substitution adds no value.

Structural prevention (ratchet history)
--------------------------------
This test AST-walks **all** Python files under ``src/cadrumo/`` rather than
a fixed allowlist so that any new file is automatically
covered.  The ratchet history regression (``locales/manager.py`` escaping detection
because it was added after the original test was written) cannot recur.

The test uses a ratchet: ``_KNOWN_VIOLATING_FILES`` records the set of
files that still carry pre-existing bare literals (enrolled for future
cleanup).  Any file **not** in this set must have zero
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

See Also:
    :mod:`~tests._inventory`
        Provides the production-file scanner and bare UTF-8 literal detector
        used by the ratchet.
    :mod:`~core.external_constants`
        Defines ``UTF_8_ENCODING`` as the shared encoding authority.

A bare ``"utf-8"`` literal must route through the shared constant so an
encoding-name change is fixed in one place, never re-typed at each call site.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.tests import (
    aeat_relative,
    bare_utf8_literal_violations,
    non_test_package_python_files,
)

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEV_ROOT = REPO_ROOT / "dev"

# Files excluded from the scan entirely (not subject to the ratchet).
_SCAN_EXCLUDES: frozenset[str] = frozenset(
    {
        "core/external_constants.py",
    },
)

# Known pre-existing violating files, to be cleaned up over time. New files must
# NOT appear here — add a cleanup commit instead. Removing an entry locks that
# file at zero violations.
#
# Every entry must still exempt a REAL violation, and
# :func:`test_no_ratchet_entry_has_gone_inert` enforces that. A file that was
# cleaned up, or deleted, but left listed here does not become a harmless
# leftover: it becomes a standing pre-authorisation for that exact path to
# reacquire bare UTF-8 literals with no review. This list was measured on
# 2026-08-03 and 35 of its 78 entries had gone inert that way — 29 files since
# cleaned, 6 no longer present — so 35 paths were silently exempt for nothing.
# They are deleted here rather than left as backlog decoration.
_KNOWN_VIOLATING_FILES: frozenset[str] = frozenset(
    {
        "adapters/outbound/llm/_cache.py",
        "adapters/outbound/llm/_usage.py",
        "adapters/outbound/storage/_mirror_manifest.py",
        "adapters/persistence/profile/filing_amendments.py",
        "adapters/persistence/storage/crypto/_encrypted_columns.py",
        "adapters/persistence/storage/envelope/secure_bound_repository.py",
        "application/live/verify.py",
        "application/modelo/_revision_persistence.py",
        "application/repair_integrity.py",
        "application/user_profile/repository.py",
        "application/wizard/_translations.py",
        "core/bucket_pointer.py",
        "core/corpus_manifest/__init__.py",
        "core/i18n/_render.py",
        "core/json_contract.py",
        "core/observability/_fingerprint.py",
        "core/observability/_sink.py",
        "core/observability/_store.py",
        "domain/auth/apoderamientos/_catalogue.py",
        "domain/calculations/registry/_export_parse.py",
        "domain/calculations/registry/_legal.py",
        "domain/calculations/registry/_live_parity.py",
        "domain/calculations/registry/_renta_web_open_oracle.py",
        "domain/calculations/registry/_validate_evidence.py",
        "domain/manuals/_fetch.py",
        "domain/manuals/_loader.py",
        "entrypoints/cli/_config/_google.py",
        "entrypoints/cli/_modelo_spreadsheet_cli.py",
        "entrypoints/cli/errors.py",
        "entrypoints/cli/_ledger_classify_cli.py",
        "entrypoints/cli/_stdio.py",
    },
)


def _all_production_files() -> tuple[Path, ...]:
    """Return all non-test Python files under src/cadrumo/, excluding the constant module."""
    return non_test_package_python_files(include_data=True, scan_excludes=_SCAN_EXCLUDES)


def test_no_ratchet_entry_has_gone_inert() -> None:
    """Every ratchet entry must still exempt a file that really violates.

    A ratchet only ratchets in one direction on its own: the check below refuses
    a NEW violation, but nothing ever forced an entry out when its file was
    cleaned or deleted. An entry left behind is not spent, it is loaded — the
    listed path stays exempt, so that exact file may silently reacquire bare
    UTF-8 literals without review, and a deleted path pre-exempts whatever is
    created there later.

    Measured on 2026-08-03, 35 of 78 entries had gone inert this way. This is the
    check that keeps the backlog honest as it drains.
    """
    by_relative_path = {aeat_relative(path): path for path in _all_production_files()}
    cleaned: list[str] = []
    vanished: list[str] = []
    for entry in sorted(_KNOWN_VIOLATING_FILES):
        path = by_relative_path.get(entry)
        if path is None:
            vanished.append(entry)
        elif not bare_utf8_literal_violations(path):
            cleaned.append(entry)

    assert not (cleaned or vanished), (
        "ratchet entries that exempt nothing and now stand as silent pre-authorisations:\n"
        + "".join(f"  cleaned, still listed: {entry}\n" for entry in cleaned)
        + "".join(f"  no longer in the tree: {entry}\n" for entry in vanished)
        + "\nDelete them from _KNOWN_VIOLATING_FILES in this commit."
    )


def test_no_bare_utf8_literals_in_production_files() -> None:
    """New production files under src/cadrumo/ must not introduce bare UTF-8 literals.

    This test uses a ratchet against ``_KNOWN_VIOLATING_FILES``:

    - Files already in the ratchet set are skipped (tracked for future cleanup).
    - Any file NOT in the ratchet set must have zero bare ``"utf-8"`` literals.
    - Any new file is automatically covered — the ratchet history regression
      class (new files escaping the fixed enrolled-module set) cannot recur.

    To clean up a known-violating file: migrate it to ``UTF_8_ENCODING``, then
    remove it from ``_KNOWN_VIOLATING_FILES``. The test will then lock it at zero.

    Idiomatic hash sites (``hashlib``/``hmac`` lines) are exempt from detection
    because the encoding is protocol-fixed.
    """
    violations: list[str] = []
    production_files = _all_production_files()

    for path in production_files:
        rel = aeat_relative(path)
        if rel in _KNOWN_VIOLATING_FILES:
            # Pre-existing backlog — covered by future cleanup.
            continue
        module_violations = bare_utf8_literal_violations(path)
        for lineno, snippet in module_violations:
            violations.append(f"{rel}:{lineno} — {snippet!r}")

    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare UTF-8 literal(s) found in non-ratcheted production files:\n"
            f"  {joined}\n\n"
            "Replace with UTF_8_ENCODING from cadrumo.core.external_constants.\n"
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
# ``bare_utf8_literal_violations()`` above (matches ``sha256`` on the same line).  The
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
#   application/modelo/borrador_binding.py:223
#       hashlib.sha256(result.borrador_snapshot_id.encode('utf-8')).hexdigest()
#
# If the hash-allowlist criteria in ``UTF8_HASH_ALLOWLIST_TOKENS`` are ever
# narrowed, these 4 sites must be reviewed and either enrolled in
# ``_KNOWN_VIOLATING_FILES`` or migrated to ``UTF_8_ENCODING``.


# ---------------------------------------------------------------------------
# Dev-tooling-tree ratchet (behavior contract — ratchet history)
# ---------------------------------------------------------------------------
# The ``dev/`` package is repo tooling; it must not import
# ``cadrumo.core.external_constants`` just to satisfy the production UTF-8
# constant rule.  Instead, each module carries a local ``_UTF_8: Final[str]``
# constant.  This test enforces that the dev tree doesn't drift back to
# bare literals beyond the pre-existing backlog below.
#
# Hash-protocol allowlist: same tokens as the src/cadrumo/ scan.
#
# dev/quality/relative_imports.py was previously fixed and must
# NOT be re-added to the known-violating set.

_DEV_KNOWN_VIOLATING: frozenset[str] = frozenset()


def _all_dev_files() -> list[Path]:
    """Return all Python tooling files under dev/ (recursive, non-test, non-init)."""
    if not _DEV_ROOT.is_dir():
        return []
    return sorted(
        p
        for p in scan_directory(_DEV_ROOT, pattern="*.py", recursive=True)
        if not p.name.startswith("test_") and p.name != "__init__.py" and "tests" not in p.parts
    )


def test_no_bare_utf8_literals_in_dev() -> None:
    """dev/ Python files must not introduce new bare UTF-8 literals.

    Each module that needs to read/write text must carry a local
    ``_UTF_8: Final[str] = "utf-8"`` constant and use it consistently.
    Pre-existing violators are ratcheted in ``_DEV_KNOWN_VIOLATING``;
    only the ratchet set may shrink, never grow.

    Hash/HMAC sites (hashlib, hmac, sha*) are allowlisted as in src/cadrumo/.
    """
    violations: list[str] = []
    dev_files = _all_dev_files()

    for path in dev_files:
        if path.name in _DEV_KNOWN_VIOLATING:
            continue
        module_violations = bare_utf8_literal_violations(path)
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


#: Floors for the two corpora this module scans. Both sit an order of magnitude
#: below the live counts (1553 production files, 228 dev files), because their
#: job is to catch a walk that has COLLAPSED, not to track growth. A floor near
#: the live count would fail on ordinary deletions and train the next reader to
#: edit the constant, which is how a floor stops being read at all.
_PRODUCTION_CORPUS_FLOOR = 200
_DEV_CORPUS_FLOOR = 20


def test_the_production_corpus_is_not_empty() -> None:
    """The production scan is meaningless over a corpus that returns nothing.

    ``test_no_bare_utf8_literals_in_production_files`` raises only when it finds
    a violation, so a walk that matches no files reports exactly what a clean
    tree reports. Nothing else in the repository asserts this walk returns
    anything: the accessor is module-local.

    Until this floor existed the scan was protected only as a side effect of
    ``test_no_ratchet_entry_has_gone_inert``, which fails on an empty corpus
    because every ratchet entry then looks vanished. That protection is
    accidental and self-cancelling - it holds only while the ratchet is
    non-empty, and the ratchet exists to be drained to zero. The dev ratchet in
    this same module has already reached zero, which is what left the dev scan
    unfalsifiable.
    """
    production_files = _all_production_files()

    assert len(production_files) > _PRODUCTION_CORPUS_FLOOR, (
        f"the production file walk returned {len(production_files)} files, at or below the "
        f"{_PRODUCTION_CORPUS_FLOOR} floor. The bare-UTF-8 scan over this corpus cannot fail while "
        "the walk is empty or collapsed, so it would report a clean tree either way. "
        "Fix the walk rather than lowering this floor."
    )


def test_the_dev_corpus_is_not_empty() -> None:
    """The dev scan carries no other protection at all.

    ``test_no_bare_utf8_literals_in_dev`` has the same raise-only shape as its
    production sibling, and its ratchet is already empty, so no inert-entry
    check stands behind it. Its accessor also returns an empty list when the
    dev root is not a directory, which makes a collapsed walk silent rather
    than loud.
    """
    dev_files = _all_dev_files()

    assert len(dev_files) > _DEV_CORPUS_FLOOR, (
        f"the dev file walk returned {len(dev_files)} files, at or below the {_DEV_CORPUS_FLOOR} "
        "floor. The bare-UTF-8 scan over dev/ cannot fail while the walk is empty or collapsed. "
        "Fix the walk rather than lowering this floor."
    )
