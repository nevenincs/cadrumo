---
tags:
  - '#adr'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:77075bb99ceaf32ce3090ef67e20a0c64492ba2d2a86f7099d2b13b3b42c18b2'
related:
  - "[[2026-08-24-deadline-window-revision-authority-research]]"
  - '[[2026-08-24-deadline-window-revision-authority-reference]]'
  - '[[2026-08-14-registry-temporal-coverage-adr]]'
  - '[[2026-07-09-m210-plazo-keying-adr]]'
---

# `deadline-window-revision-authority` adr: `deadline windows are revision-owned law facts` | (**status:** `accepted`)

## Problem Statement

Deadline-window rows can currently be copied across revisions and emitted multiple
times as distinct obligations, while periodic selectors can be represented by only a
few sample rows and silently omit the rest. A fleet-wide decision is needed for window
identity, revision ownership, cadence completeness, canonical projection, and M210's
non-standard plazo axes. Grounding is in the related research and reference.

## Considerations

- Revision selection remains law-derived from the canonical filing coordinate.
- Dates may fall in the following calendar year without changing tax-year identity.
- Registry validation must fail closed; runtime consumers must not arbitrate corrupt data.
- Periodic calendario coverage must be complete for every declared supported year.
- M210's resultado and tipo-renta axes are not profile predicates or period aliases.

## Considered options

**Runtime deduplication.** Rejected: it hides invalid authority and cannot safely choose
between conflicting dates, qualifiers, or provenance.

**Registry data cleanup only.** Rejected: it removes today's copies but permits the same
defect to recur.

**Modelo-level deadline catalogue outside revisions.** Deferred: it creates a broad new
authority structure while revision provenance and applicability remain necessary.

**Revision-owned canonical windows with strict validation.** Proposed: validate identity,
ownership, and semantic uniqueness during registry build; project only validated rows.

## Constraints

- `select_revision` and the validated-authority pipeline are stable parent authorities.
- `DeadlineWindowDefinition.filing_year` remains during migration but must equal
  `period.filing_year`; removal or derivation can follow as a separate schema change.
- M210 must complete its typed plazo-keying design before the fleet invariant can pass;
  no modelo-specific exemption is permitted.
- Deadline completeness consumes the shared supported-filing-year coverage declaration
  owned by the accepted registry-temporal-coverage architecture; it does not add a
  deadline-specific horizon. Validation makes no claim about unpublished future dates.
- Any changed legal date requires verification against bundled and official authority.
- Exact filing dates are revision-owned legal facts. Registry source-fidelity tests assert
  those literal values and provenance; architecture and fleet behavior tests derive their
  horizon from the supported-filing-year catalogue and assert relational or semantic
  invariants instead of copying a year list or exact-count pass condition.
- “Today” is not registry data or a durable legal fact. Status calculations accept an
  explicit reference date and default only through the canonical Europe/Madrid civil clock
  seam; deterministic tests inject or freeze that seam.
- Feature acceptance is attributable and finite. Revision-scoped whole-repository
  checkpoints remain honest release evidence, but unrelated concurrent failures do not
  become deadline-window defects or keep this feature open; this follows the accepted
  quality-gate-zero-closure decision.

## Implementation

Define the semantic coordinate as `(modelo, period.filing_year,
period.registry_token, typed deadline qualifiers)`. Registry validation requires
the redundant year to match the period year, the containing revision to be the unique
law-selected owner, and IDs and semantic coordinates to be unique across revisions.
For periodic schedules, validation requires every selected cadence token for each
filing year declared supported by the canonical temporal-coverage projection. Sparse
coverage is permitted only for an explicitly typed ad-hoc/event schedule, never inferred
from missing rows.

Repair all affected modelo data. M190 and M193 align identity year while retaining
physical filing dates. M210 uses canonical `EVENT-N`/`0A` identity plus the existing
`ResultDisposition` and official two-digit tipo-renta code authorities as qualifiers,
completing rather than bypassing its plazo-keying decision. M303, M322, and M353 retain
rows only in their canonical revisions, including the M303 2024 cutover. The complete
measured periodic fleet—M111, M115, M123, M130, M131, M202, M216, M303, M322, M349,
M353, and M369—is materialised through the canonical declared supported-year horizon
from bundled official evidence. Open frontier revisions do not imply unpublished future
dates.

The authority deadline projection traverses validated canonical rows and asserts the
invariant defensively. The engine, overview application, workflow, declaration and
calculation notices, and CLI remain thin consumers and add no dedupe logic.

## Rationale

This is the only option that makes invalid registry state unrepresentable at the
production authority boundary while preserving one shared behavior for every consumer.
It composes with the established revision resolver and addresses M210 through typed tax
semantics instead of weakening the invariant.

## Consequences

- Calendar, agenda, backlog, workflow, filing-window lookup, and CLI regain exact-one
  obligation semantics from one repair.
- Future stale copies fail registry validation before reaching operators.
- M210 plazo completion expands the change beyond mechanical data deletion and requires
  careful legal and calculation-output integration.
- Fleet-wide and real CLI regressions become permanent gates on multiplicity.
- The calendar stops silently under-declaring monthly and quarterly obligations that
  were absent because only sample rows had been authored.
