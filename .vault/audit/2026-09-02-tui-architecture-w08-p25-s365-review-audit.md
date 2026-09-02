---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:00e9e002324b169459b31d9e1ba17272b348d8e478d53891dc402861ca73a86b'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `w08 p25 s365 review`

## Scope

Focused review of `HomeProjectionV1` and its constituent account-session,
zone-availability, next-action, declaration-resume, Ledger-readiness and agenda
records against `W08.P25.S365`, the accepted navigation decision and the Home
product research. The review covered strict/frozen typing, missing-versus-zero
semantics, separation of local and AEAT evidence, address and ordering
invariants, operator vocabulary, application/frontend boundaries and the
strength of the focused tests. The canonical strict/frozen model configuration
is used throughout and the focused suite passed with 5 tests; that passing run
does not cover the contract gaps below.

## Findings

### agenda-authority | high | One zone state collapses legal, local and AEAT evidence availability

`HomeAgendaEntry` correctly carries separate local-filing and AEAT-submission
axes, but `HomeProjectionV1` gives the whole agenda only one `agenda_state` and
forbids every row when that state is never-captured, stale, locked or
unavailable. A locally known legal agenda with no AEAT capture therefore has no
truthful representation: it must either suppress valid local rows or mark the
zone available and use `NOT_OBSERVED`, which cannot distinguish never checked
from checked with no observed submission. This contradicts the accepted
requirement that local data, AEAT-observed state, missing evidence, stale
evidence and a proven empty result remain distinct.

### home-ordering-contract | medium | Ranking, limits and chronology are not enforced by the projection

The accepted Home contract permits no more than three application-ranked next
actions and a short chronological agenda. The projection accepts any number of
actions, duplicate or unordered ranks, and any number or ordering of agenda
rows. A renderer must consequently sort, slice or tolerate invalid input,
either moving application-owned prioritisation into the frontend or allowing a
projection that violates the approved layout.

### natural-address-integrity | medium | Declaration and action context can carry partial or contradictory addresses

`HomeDeclarationResume` accepts a `filing_year` that disagrees with
`period.filing_year`. `HomeNextAction` independently makes Modelo, filing year
and period optional and applies no consistency rule when more than one is
present. These records can therefore name a declaration or action context that
cannot correspond to one canonical Modelo/year/period case, despite the
decision assigning that natural address to the application boundary.

### declaration-state-vocabulary | medium | Resume state is an unconstrained presentation string

`HomeDeclarationResume.state` is a free string rather than a closed semantic
state or stable presentation key. It accepts typos, localized prose and internal
terms such as WorkUnit lifecycle tokens, leaving the frontend unable to exhaust
states and making vocabulary leakage possible. The surrounding records use
closed enums and reason codes, so this field is the principal typing exception.

### stale-freshness | medium | A stale zone can omit the observation time that explains its staleness

`HomeZoneState` rejects an observation time for never-captured state but permits
`STALE` with no `observed_at`. The resulting projection claims staleness without
carrying the freshness evidence the decision says every zone preserves, so the
interface cannot tell the operator how old the state is.

### contract-test-teeth | medium | The focused tests exercise only a small subset of the declared invariants

The five tests prove canonical freezing, known zero, one non-available Ledger
case, never-captured timestamp rejection, one Ledger subset bound and one
session-label rule. They do not construct next actions, declarations or agenda
entries; distinguish local-only from AEAT-observed evidence; exercise each
non-available row/count refusal; cover strict or extra-field rejection; cover
session expiry shapes; or bite ordering, limits, address consistency and stale
freshness. The test named for locked Ledger or Messages fails at the Ledger
branch and never proves the Messages branch.

### remediation-verification | high | The agenda authority split permits contradictory AEAT claims

The remediation adds `agenda_evidence_state`, and the new positive test proves
that locally known agenda rows now survive when AEAT evidence was never
captured. That closes the original row-suppression half of
`agenda-authority`. It does not yet close the authority invariant: no validator
relates `agenda_evidence_state` to each row's `aeat_submission_state`, so a
never-captured, locked or unavailable evidence state can coexist with a row
claiming `SUBMITTED_OBSERVED`, `ACCEPTED` or `JUSTIFICANTE_VERIFIED`. The model
therefore still admits an authoritative AEAT claim while explicitly stating
that the authority was never captured or cannot be read. A stale evidence
state may legitimately retain observed row values because it carries their age;
states with no readable or captured evidence must refuse positive AEAT claims.

The other production remediations are sound at this review depth: stale zones
now require `observed_at`; action and declaration natural addresses are checked;
declaration state is closed; and action and agenda limits and ordering are
enforced. The focused suite passed with 9 tests. Test coverage remains
incomplete: the agenda test named for chronology and preview bound exercises
chronology only, and there is still no negative test for action ranking or
limit, next-action address completeness, isolated Messages refusal, or the
contradictory AEAT shape above. No critical issue was found; the unresolved
contradiction keeps one high-severity issue open.

## Recommendations

1. Resolve `agenda-authority` before S365 is credited by representing schedule,
   local filing and AEAT evidence authority/freshness independently enough to
   express locally known rows with never-captured or stale AEAT evidence.
2. Resolve `home-ordering-contract` by validating the accepted three-action
   ceiling, unique ordered ranks, agenda preview bound and chronological order
   at the application projection boundary.
3. Resolve `natural-address-integrity` with year/period agreement and an
   explicit action-context shape that cannot be accidentally partial.
4. Resolve `declaration-state-vocabulary` with a closed application-owned
   semantic vocabulary or stable localization key; do not render internal
   WorkUnit state tokens directly.
5. Resolve `stale-freshness` by requiring an observation time for stale state,
   unless a separately typed state records why age is unknowable.
6. Resolve `contract-test-teeth` with positive and bite-proven negative cases
   for every validator and cross-authority combination above, including an
   isolated Messages refusal that reaches that branch.
7. Complete `remediation-verification` by rejecting positive per-row AEAT
   submission states whenever `agenda_evidence_state` is never-captured,
   locked or unavailable, while retaining stale observed values with their
   required observation time; add a direct negative test for each side of that
   rule.
