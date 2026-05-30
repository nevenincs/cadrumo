"""Inventory test: inline ``datetime.now(UTC)`` / ``datetime.now(tz=UTC)`` enrollment gate.

Rule
----
Production modules under ``src/aeat/`` must not call ``datetime.now(UTC)`` or
``datetime.now(tz=UTC)`` inline.  Every call-site must delegate to
:func:`aeat.core.time._clock._now` so the production clock is uniform and
traceable.

Enrollment progress
-------------------
W03.P15 (S328–S337) migrated the first cohort of 19+ sites.  The remaining
sites below are the Wave 3 audit enumeration output; they are tracked as
follow-up Steps.  The test asserts that the live violation set is a **subset**
of the declared pending set — new inline calls cannot be added without
updating this file.

Exclusions (permanent)
----------------------
- ``test_*.py`` files: test suites may exercise clock behaviour directly.
- ``src/aeat/core/time/_clock.py``: the canonical implementation itself.
- ``src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py``:
  shared test-suite helper (treated as test infrastructure).
- ``src/aeat/tests/secure_sql.py``: test-support module.

Documented conditional-default escapes (exempt; must not grow without a Step)
-----------------------------------------------------------------------------
- ``src/aeat/adapters/outbound/aeat/auth/_authenticator.py`` — ``is_stale``
  method injectable-clock default.
- ``src/aeat/adapters/outbound/aeat/browser/_site_health_parsers.py`` —
  ``_parse_http_date_retry_after`` / ``parse_site_health_response`` defaults.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

# The canonical module — exempt from the rule.
_CLOCK_MODULE = _SRC_ROOT / "core" / "time" / "_clock.py"

# Test-infrastructure modules excluded from production-code rules.
_TEST_INFRA_MODULES: frozenset[pathlib.Path] = frozenset(
    {
        _SRC_ROOT / "adapters" / "persistence" / "storage" / "envelope" / "_repository_test_suite.py",
        _SRC_ROOT / "tests" / "secure_sql.py",
    }
)

# Documented conditional-default escape hatch pattern.
# Lines matching this are exempt because they only fire when the caller
# passes no ``now`` argument; the enclosing function signature already
# propagates an injectable clock.  Covers both plain ``now`` and
# ``_coerce_utc_aware(now)`` forms that the linter applies.
_ESCAPE_HATCH_PATTERN = re.compile(
    r"if\s+now\s+is\s+not\s+None\s+else\s+datetime\.now\s*\("
)

# Patterns that constitute an inline clock violation.
_VIOLATION_PATTERNS: tuple[str, ...] = (
    "datetime.now(UTC)",
    "datetime.now(tz=UTC)",
)

# ---------------------------------------------------------------------------
# Pending enrollment — Wave 3 follow-up targets
# ---------------------------------------------------------------------------
# Format: POSIX path relative to repo root (src/aeat/…).
# These are the sites identified in the Wave 3 audit enumeration (S328–S337
# pass, 2026-05-30). Remove entries as their Steps land.  The test asserts
# that no NEW sites appear beyond this declared pending set.

PENDING_ENROLLMENT: frozenset[str] = frozenset(
    {
        "src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py",
        "src/aeat/adapters/inbound/declaracion/_parser.py",
        "src/aeat/adapters/inbound/financial/providers/_base.py",
        "src/aeat/adapters/inbound/justificante/_extract.py",
        "src/aeat/adapters/inbound/pdf/_scrub.py",
        "src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py",
        "src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py",
        "src/aeat/adapters/outbound/aeat/auth/_session_store.py",
        "src/aeat/adapters/outbound/aeat/auth/certificate.py",
        "src/aeat/adapters/outbound/aeat/browser/session.py",
        "src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        "src/aeat/adapters/outbound/aeat/sede/_notifications.py",
        "src/aeat/adapters/outbound/aeat/sede/_observation_store.py",
        "src/aeat/adapters/outbound/aeat/sede/_walker.py",
        "src/aeat/adapters/outbound/google/_oauth_flow.py",
        "src/aeat/adapters/outbound/google/_refresh.py",
        "src/aeat/adapters/outbound/google/_session_store.py",
        "src/aeat/adapters/outbound/llm/_cache.py",
        "src/aeat/adapters/outbound/llm/_client.py",
        "src/aeat/adapters/outbound/storage/_google_drive.py",
        "src/aeat/adapters/persistence/profile/assets.py",
        "src/aeat/adapters/persistence/profile/inventory.py",
        "src/aeat/adapters/persistence/storage/attachment.py",
        "src/aeat/adapters/persistence/storage/blob_store/_blob_store.py",
        "src/aeat/adapters/persistence/storage/envelope/_secure_repository.py",
        "src/aeat/adapters/persistence/storage/master_key/_active_session.py",
        "src/aeat/adapters/persistence/storage/master_key/_master_key.py",
        "src/aeat/adapters/persistence/storage/runtime.py",
        "src/aeat/adapters/persistence/storage/secret_store/_secret_store.py",
        "src/aeat/adapters/persistence/storage/sql/secure_objects.py",
        "src/aeat/application/auth/_acquisition_lock.py",
        "src/aeat/application/auth/_apoderado.py",
        "src/aeat/application/auth/_diagnostics.py",
        "src/aeat/application/auth/_operator.py",
        "src/aeat/application/auth/_sessions.py",
        "src/aeat/application/calculations/_binding_prefill.py",
        "src/aeat/application/calculations/_iva_compensation_history.py",
        "src/aeat/application/calculations/_iva_wallet_reconciliation.py",
        "src/aeat/application/calculations/_observations_repository.py",
        "src/aeat/application/calculations/_relation_prefill.py",
        "src/aeat/application/diagnostics.py",
        "src/aeat/application/evidence/_models.py",
        "src/aeat/application/filing/_export.py",
        "src/aeat/application/filing/_review.py",
        "src/aeat/application/filing/reconciliation/_reconcile.py",
        "src/aeat/application/ledger/_actions.py",
        "src/aeat/application/live/__init__.py",
        "src/aeat/application/live/_borrador_100.py",
        "src/aeat/application/live/_censo.py",
        "src/aeat/application/live/_snapshot_base.py",
        "src/aeat/application/live/_verify.py",
        "src/aeat/application/modelo/_actions.py",
        "src/aeat/application/modelo/_export.py",
        "src/aeat/application/modelo/_reconcile.py",
        "src/aeat/application/overview/__init__.py",
        "src/aeat/application/overview/_agenda.py",
        "src/aeat/application/overview/_backlog.py",
        "src/aeat/application/overview/_explain.py",
        "src/aeat/application/user_profile/_censo_sync.py",
        "src/aeat/application/user_profile/_orchestration.py",
        "src/aeat/application/user_profile/_profile_repository.py",
        "src/aeat/application/user_profile/_repository.py",
        "src/aeat/application/verification/_verify.py",
        "src/aeat/core/_time.py",
        "src/aeat/core/observability/_recorder.py",
        "src/aeat/domain/buckets/_event_repository.py",
        "src/aeat/domain/calculations/registry/_parity_tapes.py",
        "src/aeat/domain/deadlines/_engine.py",
        "src/aeat/domain/invoices/_repository.py",
        "src/aeat/domain/manuals/_fetch.py",
        "src/aeat/domain/modelos/_calculation_repository.py",
        "src/aeat/domain/modelos/_filing_repository.py",
        "src/aeat/domain/modelos/_repository.py",
        "src/aeat/domain/modelos/_verification_repository.py",
        "src/aeat/domain/transactions/_classification_rule.py",
        "src/aeat/domain/transactions/_repository.py",
        "src/aeat/domain/transactions/_service.py",
        "src/aeat/domain/usage_ratios/_service.py",
        "src/aeat/entrypoints/cli/_app_live.py",
        "src/aeat/entrypoints/cli/_config/_profile_census.py",
        "src/aeat/entrypoints/cli/_ledger.py",
    }
)


def _is_excluded(path: pathlib.Path) -> bool:
    if path.name.startswith("test_"):
        return True
    if path in _TEST_INFRA_MODULES:
        return True
    try:
        path.relative_to(_CLOCK_MODULE.parent)
        return path.name == _CLOCK_MODULE.name
    except ValueError:
        return False


def _collect_violations() -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline clock call."""
    repo_root = _SRC_ROOT.parent.parent
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if _is_excluded(path):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in _VIOLATION_PATTERNS:
                if pattern not in line:
                    continue
                code_part = line.split("#")[0]
                if _ESCAPE_HATCH_PATTERN.search(code_part):
                    continue
                # Skip pattern that appears only inside a string literal
                # (docstring text referencing the pattern as documentation).
                pattern_idx = code_part.find(pattern)
                if pattern_idx > 0:
                    pre = code_part[:pattern_idx].rstrip()
                    if pre and pre[-1] in ('"', "'"):
                        continue
                rel = path.relative_to(repo_root).as_posix()
                violations.append(f"{rel}:{lineno}")
                break
    return violations


def test_no_inline_datetime_now_utc() -> None:
    """Inline ``datetime.now(UTC)`` / ``datetime.now(tz=UTC)`` calls must not grow.

    All enrolled sites use ``_now()`` from ``aeat.core.time._clock``.
    Remaining pending-enrollment sites are tracked in ``PENDING_ENROLLMENT``
    above and will be addressed in follow-up Wave 3 Steps.

    This test fails if a new inline call is added outside the declared pending
    set, preventing regressions while enrollment proceeds incrementally.
    """
    repo_root = _SRC_ROOT.parent.parent
    violations = _collect_violations()

    # Split violations into pending (known follow-ups) vs new (regressions).
    new_violations: list[str] = []
    for hit in violations:
        file_path = hit.rsplit(":", 1)[0]
        posix_path = file_path.replace("\\", "/")
        if posix_path not in PENDING_ENROLLMENT:
            new_violations.append(hit)

    if new_violations:
        joined = "\n  ".join(new_violations)
        raise AssertionError(
            f"{len(new_violations)} NEW inline datetime.now(UTC) call(s) found outside the declared pending set:\n  {joined}\n\n"
            "Either migrate the call-site to _now() from aeat.core.time._clock,\n"
            "or add it to PENDING_ENROLLMENT in test_clock_enrollment_inventory.py\n"
            "with a comment referencing the follow-up Step."
        )

