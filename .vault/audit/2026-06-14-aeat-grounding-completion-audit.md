---
tags:
  - '#audit'
  - '#aeat-grounding-completion'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - "[[2026-06-14-aeat-grounding-completion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-grounding-completion with a kebab-case feature tag, e.g. #foo-bar.
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

# `aeat-grounding-completion` audit: `Campaign-Close Honesty Review — Centralization + Grounding`

## Scope

Fresh-context campaign-close honesty review (per `aeat-campaign-close-honesty-review`)
dispatched on the completed centralization remediation plan (7/7) and the
grounding-completion W01.P01 módulos build. An independent code-reviewer agent read each
substantive commit, verified claims against the bundled corpus + tests, and reported
what is wrong / missing / unverified. This document persists its findings and their
resolution.

## Findings

### C1 (CRITICAL — FIXED) — DT 32ª agent-authored corpus had a fabricated year-list

The W01.P01 módulos build (`47b903cd5`) authored a NEW DT 32ª corpus excerpt from a
secondary source with the year-list "...2025 y 2026". The repository ALREADY bundles the
authoritative consolidated LIRPF (`corpus/normatives/html/ley-35-2006.html`
`#dttrigesimasegunda`), whose real DT 32ª reads "en los ejercicios 2016 a 2024" and
records that the 2025/2026 extensions (RD-ley 9/2024, 16/2025, 2/2026) were each DEROGADAS
by Congreso acuerdos (BOE-A-2026-4667). The agent year-list was wrong, and the corpus
cross-check was tautological (agent wrote both the `required_text` and the corpus).
**Resolution:** repointed `corpus_ref` to the authoritative bundled corpus
(`ley-35-2006.html#dttrigesimasegunda`), corrected the scope to 2016-2024, flagged the
2025/2026 derogation in the legal entry + all three parameter notes (a consumer must gate
on filing year and treat 2025+ as unresolved), deleted the orphaned agent excerpt. The
strict cross-check now validates against the real bundled BOE text (non-tautological);
the parameter values (250000/125000/250000) and article mapping were faithful and stand.
56 corpus/catalogue tests pass.

### H1 (HIGH — FIXED) — incomplete citation sweep, 6 stragglers

The citation campaign (`3281d2024`, `50e9adaa6`) corrected the primary sites but left six
docstring/comment stragglers with the old wrong articles: `_descendant_facts.py:157`
(Art. 59→61), `test_external_constants_centralisation_part1.py:435` (art. 31.1→33.1),
`test_descendant_info.py:236` (Art. 58.3→58.2), and `test_custodia_compartida.py` ×3
(Art. 59→61). The corrected provisions were verified legally correct by the reviewer.
**Resolution:** all six swept to the correct articles; 129 affected tests pass.

### M1 (MEDIUM — FIXED) — F3 `available` extra-probe contradicted the "exactly preserving" claim

`_iva_compensation_history.py` routed the semantic-only `iva.compensacion-disponible-fin-periodo`
casilla through the registry resolver, adding a second probe key vs the original
single-probe. That casilla has no numeric AEAT box, so it was never an inline-number
routing literal (the finding's target). **Resolution:** reverted it to the direct
single-probe `_casilla_value` lookup — behaviour-preserving and correct.

### M2 (MEDIUM — TRACKED) — EO exclusion parameters have no consumers yet

The three módulos magnitudes are inert grounded data: no production resolver/advisory gate
consumes them (the W01.P02 advisory gate is honestly deferred). Audit finding V3 is thus
HALF closed — the limits now exist as grounded registry data, still unenforced. Tracked as
grounding-completion W01.P02 (which also needs a declared-volume input).

### L1 / N1 (LOW / NIT — awareness only) — F4 process + registry-load nit

L1: F4 (`69d3ecd50`) landed with three `application/calculations` test helpers red, fixed
in the follow-up `0ab778724` — net HEAD green, flagged as a clean-collection process note.
N1: `_casilla_id_to_number` loads the whole registry tree (lru-cached, off hot path) to
resolve ~7 box numbers — acceptable.

### W02 blocker verification (C1-lesson applied) — remaining steps need authoritative human-reviewed sourcing

Applying the C1 lesson (check the bundled authoritative corpus before authoring), the three
remaining grounding-completion steps were each verified blocked on operator input, not merely
asserted:

- **W02.P03 (IS ERD INCN<10M schedule):** the claimed 24/23/22/21 (2025–2028) schedule is
  **NOT present in the bundled authoritative corpus** — `ley-27-2014-dt-44.html`
  contains only the micro-empresa INCN<1M part (21/22 for 2025, 19/21 for 2026), and there
  is no full `ley-27-2014.html` consolidation bundled. The verification-swarm claim came from
  a secondary AEAT web page. Authoring it would repeat the C1 fabrication error. BLOCKED on an
  operator-provided authoritative BOE excerpt (or confirmation the schedule is real and its
  exact text).
- **W02.P04 (M200 casilla 00558 two-tranche echo):** the cuota is already correct; only the
  scalar rate echo is stale (flat 23 % for 2025/2026 micro-empresa). The fix needs AEAT's
  exact 00558 convention for a two-tranche micro rate (does the box show 21, 23, or is it
  computed?) — not derivable without the AEAT form spec. BLOCKED on that convention.
- **W01.P02 (módulos advisory gate):** needs a *declared per-activity volume input* (250k
  general / 125k factura / 250k compras) that the profile/ledger does not yet collect, AND
  must gate on filing year because — per C1 — the limits are settled only for 2016–2024 and
  derogated/unresolved for 2025+. Building it is a categorized-volume feature with a legal
  year-scope, not a quick step.

These are documented blockers, not skipped work: completing them by fabricating legal text
from secondary sources or guessing a regulated form convention is exactly what the
safety-legal-gates discipline and the C1 finding forbid.

### Verified-sound (honest green surface)

The reviewer independently confirmed: F4 binding selectors correct (rate_kind=zero does not
drop observations; production resolves via the mesh, non-tautological 5000/3000 test); F4
completeness-manifest edit consistent; F3 behaviour-preserving for every box number (zero
cross-revision conflicts); F1 tier-resolver parity-preserving with a non-tautological
causality proof; all landed citation fixes legally correct; F2 prorrata retain-and-defer
decision consistent with `no-legacy-compatibility`. Clean `--collect-only` (15467, 0 errors).

## Recommendations

- C1/H1/M1 fixed this pass. M2 (W01.P02 advisory gate + declared-volume input) remains the
  open grounding-completion step; until it lands, do not represent the módulos exclusion as
  enforceable. W02 (ERD<10M schedule, M200 echo) still needs human-reviewed corpus.
- Operator action: re-stamp the now-authoritatively-grounded DT 32ª legal entry after
  confirming the 2016-2024 scope + the 2025/2026 derogation handling.
- Lesson for future grounding work: always check the bundled authoritative corpus
  (`ley-35-2006.html` etc.) BEFORE authoring a new excerpt from a secondary source — the
  authoritative consolidated text is already shipped and is the faithful source.

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
