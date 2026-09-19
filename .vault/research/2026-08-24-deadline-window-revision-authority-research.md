---
tags:
  - '#research'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5fdc21ab2ba9296a5a775f7a600cb512ac2c3f5cf5aafbcff0df29b8ed6d8b6d'
related:
  - '[[2026-08-24-deadline-window-revision-authority-reference]]'
---

# `deadline-window-revision-authority` research: `registry-wide deadline ownership and calendar consistency`

Deadline lookup currently emits stale window copies retained under non-governing
revisions. The defect affects six modelos and every consumer of the shared deadline
engine. Evidence favors a registry ownership invariant, canonical projection, and data
repair; output-layer deduplication would conceal contradictory authority.

## Findings

### Filing-year identity is the tax period, not the physical filing date

The resolver contract requires the window year and embedded `Period.filing_year` to
name the work unit's tax year. A following-January campaign belongs in `opens_on` and
`closes_on`, not a changed identity year (`src/cadrumo/domain/deadlines/_plazo.py:28`,
`src/cadrumo/domain/calculations/registry/_schema.py:572`). Modelo 190 and 193 each
violate this axis.

### The current authority projects every authored copy

`deadline_windows` scans every revision, filters only on `window.filing_year`, and
appends every match without law-selecting the revision
(`src/cadrumo/domain/calculations/registry/_authority.py:318`). Existing validation
checks revision-selector overlap, not nested-window ownership
(`src/cadrumo/domain/calculations/registry/_validate_revision_rules.py:25`).

### The fleet inventory exposes 27 duplicated obligations

The bundled authority contains 501 rows. Grouping by `(modelo, period.filing_year,
period.registry_token)` finds 27 duplicated coordinates: M210 has 8, M303 has 14, M322
has 2, and M353 has 3. Canonical selection also exposes M190/M193 year-axis errors.
M303's seven sampled 2025 periods each occur under five revisions
(`src/cadrumo/_data/registry/aeat/modelos/303/revisions`).

### Every calendar and CLI surface amplifies the defect

`DeadlineEngine.compute` emits one obligation per tuple
(`src/cadrumo/domain/deadlines/_engine.py:197`). Overview projection preserves all rows
(`src/cadrumo/application/overview/_calendar.py:780`); CLI calendar, agenda, backlog,
workflow gates, filing-window lookup, and explain inherit the same defect.

### Modelo 210 needs canonical plazo keying, not an exemption

M210 work units use `EVENT-N` and `0A`, while duplicated deadlines use `1T`-`4T`. The
proposed plazo-keying record identifies missing resultado and tipo-renta axes and
rejects fabricated period tokens (`.vault/adr/2026-07-09-m210-plazo-keying-adr.md`).

### Exact-one ownership is insufficient without periodic completeness

Comparing each revision's periodic selector with its declared windows finds systematic
under-materialisation. M303, M322, M353, and M369 contain monthly or quarterly sample
rows while their selectors admit the complete cadence; M303 2022 contains only `4T`,
and the 2026 open revision lacks December. A canonical engine that merely removes
duplicates would still silently omit real obligations. The validator therefore needs a
typed completeness contract: periodic schedules enumerate every selected period for
each supported closed year, while genuinely ad-hoc/event schedules declare their
different coverage shape explicitly.

### Validation plus canonical projection is the favored architecture

Output deduplication cannot adjudicate conflicting dates or citations. Data-only cleanup
permits recurrence. Evidence favors refusing duplicate IDs, duplicate semantic
coordinates, year divergence, non-owner rows, and incomplete periodic cadences during
registry validation, then projecting validated canonical rows. The ADR must settle
M210's typed qualifiers, open-ended-year materialisation, and the migration of redundant
`filing_year`.

### Verification must span registry, engine, and real CLI behavior

Existing dictionaries and `any`/`next` assertions erase multiplicity. A focused M303
test already expects four quarterly rows and is red for 2024/2025
(`src/cadrumo/domain/deadlines/tests/test_engine.py:463`). Required coverage includes a
validator bite, bundled fleet invariant, historical engine schedule, and real CLI JSON.

### Bounds

This research inventories all 501 loaded windows structurally. It has not independently
re-adjudicated every date against live AEAT publications; implementation must verify any
changed date against its declared source and authoritative corpus.

## Sources

- `src/cadrumo/domain/calculations/registry/_authority.py:318`
- `src/cadrumo/domain/calculations/registry/_schema.py:572`
- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py:25`
- `src/cadrumo/domain/deadlines/_engine.py:197`
- `src/cadrumo/domain/deadlines/_plazo.py:28`
- `src/cadrumo/application/overview/_calendar.py:780`
- `src/cadrumo/domain/deadlines/tests/test_engine.py:463`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions`
- `.vault/adr/2026-07-09-m210-plazo-keying-adr.md`
