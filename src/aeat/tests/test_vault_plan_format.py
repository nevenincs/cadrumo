"""Vault plan format gate — every ``.vault/plan/*.md`` parses cleanly.

The vault plan CLI (``vaultspec-core vault plan step add`` and friends)
calls :func:`vaultspec_core.plan.parser.parse_plan` on the target plan
before performing any mutation. A pre-existing row missing the canonical
``;`` action/scope separator (or any other parser violation) makes the
CLI raise :class:`PlanParseError` and abort, blocking all future
programmatic step-add against that plan — exactly the symptom that
surfaced as ``W09.P21.S141`` (11 historical rows hand-fixed during
landing).

This gate runs the parser against every ``.vault/plan/*.md`` and
aggregates failures so a future drift fails at ``just test`` rather
than only at the next mutating CLI call. Sibling to ``S141`` (the
one-time format-hygiene fix). Closes ``W09.P21.S142``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from vaultspec_core.plan.frontmatter import PlanFrontmatterError
from vaultspec_core.plan.parser import PlanParseError, parse_plan

# Both error classes share ``ValueError`` as their nearest common base but
# only because every vaultspec-core plan failure subclasses it; capture both
# explicitly so an unrelated ``ValueError`` propagates instead of being
# silently absorbed into the gate's report.
_PlanLoadError = (PlanParseError, PlanFrontmatterError)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_DIR = REPO_ROOT / ".vault" / "plan"


def _plan_paths() -> list[Path]:
    if not PLAN_DIR.is_dir():
        return []
    return sorted(p for p in PLAN_DIR.glob("*.md") if p.is_file())


def test_at_least_one_vault_plan_was_discovered() -> None:
    """Sanity: the gate found vault plans to validate.

    Guards against a future refactor that moves ``.vault/plan/`` or
    changes the file extension and turns the format gate into a
    zero-row no-op.
    """
    paths = _plan_paths()
    assert len(paths) > 5, (
        f"Discovered only {len(paths)} vault plan(s) under {PLAN_DIR} — "
        f"the vault layout probably moved."
    )


# Allow-list of plans that fail to parse as of W09.P21.S142 landing.
# Each entry is a known pre-existing format-hygiene gap that needs the
# same canonical-action-semicolon-scope sweep we ran on the
# schema-hardening plan in S141. The gate fails when a NEW plan starts
# failing (regression — drift introduced by foreign WIP) or when an
# allow-list entry now parses cleanly (silent fix — trim the entry).
# Burndown is tracked separately; this set is the W09.P21 close state.
_PLANS_KNOWN_TO_FAIL_PARSING: frozenset[str] = frozenset(
    {
        "2026-04-12-base-module-structure-plan.md",
        "2026-04-12-casilla-db-plan.md",
        "2026-04-12-cert-auth-plan.md",
        "2026-04-12-ci-github-actions-plan.md",
        "2026-04-12-data-storage-plan.md",
        "2026-04-12-deadline-engine-plan.md",
        "2026-04-12-dev-scaffolding-plan.md",
        "2026-04-12-docs-rewrite-plan.md",
        "2026-04-12-filing-draft-engine-plan.md",
        "2026-04-12-google-fixtures-plan.md",
        "2026-04-12-gsuite-bootstrap-plan.md",
        "2026-04-12-modelo-303-390-plan.md",
        "2026-04-12-normatives-plan.md",
        "2026-04-12-notifications-inbox-plan.md",
        "2026-04-12-playwright-anti-bot-plan.md",
        "2026-04-12-release-please-plan.md",
        "2026-04-12-self-healing-sync-plan.md",
        "2026-04-12-setup-wizard-plan.md",
        "2026-04-12-status-reader-plan.md",
        "2026-04-12-submission-engine-plan.md",
        "2026-04-12-synthetic-filing-fixtures-plan.md",
        "2026-04-12-trilingual-i18n-plan.md",
        "2026-04-12-workflow-engine-plan.md",
        "2026-04-13-aeat-mantenimiento-detection-plan.md",
        "2026-04-13-cert-pre-expiry-gate-plan.md",
        "2026-04-13-filing-complementaria-plan.md",
        "2026-04-13-modelo-inventory-plan.md",
        "2026-04-13-r1-vat-enumeration-plan.md",
        "2026-04-14-run-trace-plan.md",
        "2026-04-16-aeat-history-fetch-plan.md",
        "2026-04-17-aeat-access-gate-plan.md",
        "2026-04-17-export-first-roadmap-plan.md",
        "2026-04-17-modelo-303-formulas-plan.md",
        "2026-04-17-pytest-markers-plan.md",
        "2026-04-17-pytest-only-testing-plan.md",
        "2026-04-17-relative-imports-plan.md",
        "2026-04-17-schema-extraction-plan.md",
        "2026-04-18-aeat-filing-detail-fetch-plan.md",
        "2026-04-18-category-assignment-cli-plan.md",
        "2026-04-18-cert-provider-migration-plan.md",
        "2026-04-18-unified-review-queue-plan.md",
        "2026-04-30-inventory-management-cli-design-plan.md",
        "2026-04-30-inventory-management-hardening-plan.md",
        "2026-05-04-multilang-externalization-phase1-plan.md",
        "2026-05-08-aeat-cli-hardening-plan.md",
        "2026-05-09-exception-restructure-phase-1-plan.md",
        "2026-05-13-google-oauth-plan.md",
        "2026-05-21-state-architecture-plan.md",
    }
)


def test_vault_plans_parse_against_baseline() -> None:
    """Every ``.vault/plan/*.md`` parses via vaultspec-core's plan parser, modulo baseline.

    A ``PlanParseError`` means a hand-edited row violates the canonical
    schema (commonly: missing ``;`` separator between the action clause
    and the scope clause). The vaultspec-core CLI refuses to mutate
    the plan until the offending row is fixed.

    Symmetric to the ``W09.P19`` synthetic-data fixture gate and the
    ``W09.P20`` cross-module-import gate: pin the contract at
    suite-collection time so drift fails fast, not only at the next
    mutating CLI call.

    Gate enforces both directions:
    - New plan starts failing → regression, fix the offending row.
    - Allow-list plan now parses → silent fix, trim the allow-list.

    The set is W09.P21's close state; burndown is tracked separately.
    """
    live_failures: set[str] = set()
    for plan_path in _plan_paths():
        try:
            parse_plan(plan_path)
        except _PlanLoadError:
            live_failures.add(plan_path.name)

    regressions = live_failures - _PLANS_KNOWN_TO_FAIL_PARSING
    silent_fixes = _PLANS_KNOWN_TO_FAIL_PARSING - live_failures

    failure_lines: list[str] = []
    if regressions:
        failure_lines.append(
            "Plans newly failing to parse (regression — fix the canonical "
            "action; scope row format):"
        )
        failure_lines.extend(f"  + {name}" for name in sorted(regressions))
    if silent_fixes:
        failure_lines.append(
            "Plans in allow-list that now parse cleanly (trim "
            "_PLANS_KNOWN_TO_FAIL_PARSING):"
        )
        failure_lines.extend(f"  - {name}" for name in sorted(silent_fixes))

    assert not failure_lines, "\n" + "\n".join(failure_lines)
