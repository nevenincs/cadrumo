---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-research]]"
---

# 2026-04-30-aeat-restructure step-00 adr lock-in

## status

**COMPLETE** — both autonomous decisions resolved per ADR Approval gate / Autonomous decision rules. No items remain "uncertain" in the ADR.

## scope

Step 0 per the execution plan resolves the two boundary items previously deferred to project-owner sign-off:

- Decision 6 — reserved `SchemaSource` enum slots (`PORTAL_HTML_PROBE`, `MANUAL_LLM_DRAFT`, `XSD_WIRE`)
- Decision 10 — migration-helper retention window (`migrate_legacy_*_to_repository` family)

Both decisions are resolved autonomously via the audit-grounded decision rules in the ADR's Autonomous decision rules section. No subagent dispatch was required: each rule's audit method is a tightly-scoped grep + git-log + GitHub-search operation that does not benefit from agent parallelism.

## decision 6 — schemasource enum slots: DELETE

### audit method

- `Grep` for `PORTAL_HTML_PROBE|MANUAL_LLM_DRAFT|XSD_WIRE` across `src/aeat/`.
- `gh issue list --state all --search "PORTAL_HTML_PROBE OR MANUAL_LLM_DRAFT OR XSD_WIRE OR SchemaSource" --repo wgergely/aeat`.
- `git branch -r` filtered for schema/portal/llm-draft/xsd-related branch names.

### evidence

Source-code references — 3 files in `src/aeat/`:

- `src/aeat/domain/schema/_enums.py` lines 21–23 — slot definitions (`PORTAL_HTML_PROBE`, `MANUAL_LLM_DRAFT`, `XSD_WIRE`).
- `src/aeat/domain/schema/_models.py` lines 112–113 — docstring documenting them as "reserved enum slots for follow-up extractors".
- `src/aeat/domain/schema/test_models.py` lines 351–353 — test exercising the reserved values.

Vault-doc references — 3 historical docs:

- `.vault/research/2026-04-17-schema-extraction-research.md`
- `.vault/plan/2026-04-17-schema-extraction-plan.md`
- `.vault/adr/2026-04-17-schema-extraction-adr.md`

GitHub state:

- Open issues actively planning the slots: **0** in `wgergely/aeat`.
- Closed issues referencing the slots: 1 (`#9`, the original 2025-era schema-extraction research issue, closed and historical).
- EPIC `#475` references the slots only as items "to-be-decided" by this audit; not actively planning use.
- Active branches: 0. The only schema-related branch (`origin/feature/7-portal-catalogue`) is the portals catalogue feature, unrelated to the `PORTAL_HTML_PROBE` extractor type.

### decision rule application

ADR rule: *any active branch / open issue references the slot → KEEP. Otherwise → DELETE with rationale recorded.*

- Active branch: none.
- Open issue: none planning use.

→ **DELETE** all three reserved slots and their docstring + test references.

### action

The deletion rides into Step 7's keystone PR with the schema module's move. Concrete edits:

- `src/aeat/domain/schema/_enums.py` lines 21–23 — remove the three enum members.
- `src/aeat/domain/schema/_models.py` lines 112–113 — remove the reserved-slots docstring sentence.
- `src/aeat/domain/schema/test_models.py` lines 351–353 — remove the test references (verify whether the entire iteration target should go at edit time).
- The 3 schema-extraction vault docs (research/plan/ADR from 2026-04-17) get Tier-3 inline-updates in Step 12 to drop the "reserved future extractors" mention.

This deletion lands on the dead-code workstream Phase 2 list (rides with the `domain/schema/` move at Step 7), not on the Phase 1 list.

### rationale

The slots have been speculative since the 2026-04-17 schema-extraction ADR (~2 weeks unused). No concrete branch or roadmap commitment exists. The autonomous rule classifies them as deletable; the rationale fires deterministically.

## decision 10 — migration-helper retention: RETAIN

### audit method

- `Grep` for `migrate_legacy_.*_to_repository` across `src/aeat/`.
- `git log --all --diff-filter=A --reverse -G "def <fn>" --format="%ai %h %s"` per helper to find first-add commit.
- Unrestricted cross-file caller scan: `grep -rn "migrate_legacy_" --include="*.py" --include="*.toml" --include="*.cfg" --include="*.md" --include="*.json" --include="*.yaml" --include="*.yml" .` excluding test files, vault, and the helper's defining file.

### evidence

Helper inventory — 5 helpers (the EPIC `#475` body / plan / `#476` checkbox text undercount of "3" is corrected by this audit):

| Helper | File | Landed | Production callers | Test fixtures |
|---|---|---|---|---|
| `migrate_legacy_submissions_to_repository` | `src/aeat/adapters/outbound/aeat/export/_repository.py:194` | 2026-04-27 (`0bb4ca6`) | 0 | yes (`_test_repository.py`) |
| `migrate_legacy_amendments_to_repository` | `src/aeat/application/filing/_complementaria_repository.py:181` | 2026-04-27 (`430627d`) | 0 | yes (`_test_complementaria_repository.py`) |
| `migrate_legacy_filing_history_to_repository` | `src/aeat/application/filing/_history_repository.py:179` | 2026-04-27 (`a7bb565`) | 0 | yes (`_test_history_repository.py`) |
| `migrate_legacy_drafts_to_repository` | `src/aeat/application/filing/_repository.py:205` | 2026-04-27 (`00d7a5b`) | 0 | yes (`_test_repository.py`) |
| `migrate_legacy_justificantes_to_repository` | `src/aeat/domain/justificante/_repository.py:178` | 2026-04-27 (`ad49cbb`) | 0 | yes (`_test_repository.py`) |

Cross-file caller scan: zero non-test, non-defining-file callers in production code. The only adjacent match (`migrate_legacy_to_secret_store` in `auth/_secret_adapters.py`) is a separate symbol on the Phase-1 dead-code list and not part of this rule.

### decision rule application

ADR rule: *helpers landed > 6 months ago AND zero production callers AND test fixtures cover the migration path → DELETE in Phase 2. Otherwise → RETAIN with TODO(#issue) annotation and file a removal-tracking issue.*

- Landed > 6 months ago: **NO** (3 days ago — 2026-04-27; today is 2026-04-30).
- Zero production callers: yes.
- Test fixtures cover migration: yes.

→ rule fires `RETAIN with TODO + tracking issue`.

### action

- Tracking issue filed: `#477`. Removal eligibility: 2026-10-27 (6 months after landing).
- `# TODO(#477):` annotation rides into Step 2's first PR per the no-design-only-PRs rule — annotations colocate with the dead-code workstream's first PR. Annotations point at `#477` (the retention tracker) on each helper's `def` line.
- The 5 helpers MOVE with their domain in Step 7 (`submission/` → `domain/submission/`, `filing/_*` → `domain/filing/`, `justificante/` → `domain/justificante/`). They retain their TODO annotations across the move.

### rationale

3-day-old code with active operator-facing migration purpose cannot meet the static "zero callers" bar safely — operators run these helpers once from the CLI / one-shot scripts, not from in-tree code. The 6-month retention window gives time for any unobserved external caller (deployed instances, downstream consumers, ops scripts) to surface before the rule fires `DELETE`. The autonomous decision rule's deployment-state-acknowledgement clause is the operative caveat.

## discrepancies surfaced (FIX / FILE / STRIKE)

**Plan / EPIC body undercount** — the plan body, issue `#476` checkbox text, and EPIC `#475` body all describe "3 `migrate_legacy_*_to_repository` helpers" in the Phase-2 dead-code list. The audit found **5**.

- Disposition: **STRIKE** (incorrect body language).
- Application:
  - Plan + ADR amendments ride in Step 2's first PR (per no-design-only-PRs rule).
  - `gh issue edit #476` body update at Step 8 close (rolled into the Step 8 acceptance comment).
  - `gh issue edit #475` body update at Step 8 close (same rollup).

## artefacts produced by this step

- this exec record (uncommitted; rides into Step 2's first PR)
- issue `#477` — migration-helper retention tracking issue
- ADR amendment text (committed in Step 2's first PR per handover prompt's no-design-only-PRs rule):
  - Approval gate / Autonomous decision rules section: append "Step 0 outcomes: Decision 6 → DELETE; Decision 10 → RETAIN with TODO(#477)."
  - Public-surface table: no change (neither decision touched the public surface).
  - Dead-code workstream: clarify Phase 2 list — the migration-helper count is **RETAIN**, not DELETE; add the 3 schema enum members + their docstring + test references to the Phase 2 deletion list.
- Plan amendment text (same PR): correct the migration-helper count from 3 to 5 in the Step 0 description and the Step 10 list.

## next step

Step 1 — Pre-move scan (3 sub-passes). Precondition met (Step 0 complete with both decisions audit-grounded).
