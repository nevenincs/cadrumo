---
tags:
  - '#audit'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-10'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-adr]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-reader-review-audit]]'
---

# `aeat-cli-userdocs-hardening` audit: `userdocs hardening waves A-C session audit`

## Scope

Orchestrated docs-hardening session (2026-06-09 to 2026-06-10) executing twelve open
steps of the userdocs hardening plan through the documentation pipeline: per page,
a wireframe, a zero-context refinement review, live-CLI context gathering, isolated
drafting, a technical review against the live CLI, and a zero-context editorial
review. Every page change passed the documented-command conformance gate (38/38 at
session close) before commit.

Landed commits: `948621a9c` (Wave A: verification-reports, file-at-aeat,
choose-modelo guides), `7c3a19c89` (CLI verification-report hint-path fix),
`68c1c1cfe` (Wave B: symptom-first troubleshooting rewrite, modelo-036,
ledger-evidence, correct-ledger-entries guides plus ownership handoffs),
`f62cd2ce5` (docs terminology sweep), `0fd9a9119` (locale-side terminology +
registry-help fix + locale-CLI multi-line writer fix, code-reviewed APPROVE),
plus plan checkbox syncs (`cbb544367`, `1d2875b83`). Plan steps closed: S19,
S24, S25, S29, S34, S35, S36, S38, S41, S43, S53, S54.

## Findings

### TRUST-001 | HIGH | Docs cited commands and behaviors the CLI does not have

The technical-review phase caught, before publication: a retired verb cited in
`docs/how-to/profile-setup.md` (`aeat config profile switch`; live verb is
`aeat config unlock`); a false restore claim for stashed ledger rows in
`docs/how-to/import-bank-statements.md` (no un-stash verb exists; archive is
equally irreversible); a wrong period-token family for `ledger preflight`
(calendar periods such as `2026Q1`, not modelo tokens such as `1T`); doclink
sources overstated (only GMAIL, GOOGLE_DRIVE, URL are accepted); evidence add
described as storing file bytes when it records path plus SHA-256 fingerprint
plus typed facts; and a verify `--select` example offering selectors verify
refuses (only drafts can be verified). All fixed in the landed pages. The
conformance gate catches dead command paths but none of these behavioral
drifts; only live-CLI technical review caught them.

### TRUST-002 | MEDIUM | Product surfaces the docs must stay honest about

Confirmed against source and documented honestly rather than papered over:
M036 declarations have no read-back command (the command output is the only
confirmation) and no downstream calendar or profile effect today; stashed and
archived ledger transactions cannot be returned to active from the CLI; the
root `--language` flag does not localize help text for every command while
`AEAT_OUTPUT_LANGUAGE` does; `ledger update` re-derives the transaction id.
Each is stated plainly in the relevant page. These are product-gap candidates
for the backlog steps already in the plan (S20, S26, S32, S37, S52).

### FIX-001 | MEDIUM | In-scope production fixes landed by the campaign

The CLI's own verification-report failure hint pointed at a nonexistent
command path (`aeat app modelo work verification-report list`); fixed in
`src/aeat/entrypoints/cli/_modelo_rendering.py` and
`src/aeat/application/workflow/_engine.py`, now pinned by tests. The
`aeat.locales set` writer corrupted multi-line values (single-quoted scalars
with raw line breaks fold on the next YAML parse); fixed in
`src/aeat/locales/manager.py` with a real-behavior roundtrip regression test.
The `integrity registry` help string said "profile registry" while the probe
checks the calculation registry; corrected in all four locales via the locale
CLI.

### PROCESS-001 | MEDIUM | The plan-step CLI dry-run revealed serializer corruption

`vaultspec-core vault plan step check --dry-run` on this plan showed the
serializer would insert a stray backtick into the unrelated step `W07.P14.S59`
text. Per the dry-run discipline, checkbox flips were applied as minimal
manual edits instead, preserving canonical identifiers byte-for-byte. This is
the same serializer family as the known plan-body-preservation defect.

### OPEN-001 | INFO | Remaining open steps after this session

Highest-impact remaining: S56 (plain-language reorder of modelo lifecycle
prose across quickstart, filing-spine, modelo-303, modelo-390, tutorial),
W02 navigation steps (S10, S13, S14, S50, S51, S55, S57, S58), S15-S17
(profile facts rewrite), S18 (censo guide hardening), S21-S23 (ledger
readiness loop), S28, S30, S31, S33, S39, S40, S42, and the W07 gate steps
(S44-S47, S49, S59). Backlog/product steps S11, S20, S26, S32, S36-follow-on,
S37, S52 depend on CLI surfaces.

## Recommendations

- Run S56 as the next wave through the same per-page pipeline; it touches five
  committed pages and needs the dual technical plus editorial review.
- Keep the live-CLI technical-review phase mandatory for every page: it is the
  only gate that catches behavioral drift (TRUST-001) the conformance test
  cannot see.
- Action the product-gap backlog steps with the honest-limitation sentences in
  the landed pages as their acceptance criteria: when a product surface lands
  (un-stash, M036 list, guided manual values), the sentence that documents the
  limitation is the one to update.
- Report the plan-step serializer corruption (PROCESS-001) against the
  plan-body-preservation work so the dry-run finding is not lost.

## Codification candidates

- **Source:** finding TRUST-001 (behavioral drift survives the conformance
  gate; only live-CLI review catches it).
  **Rule slug:** `userdocs-pages-require-live-cli-technical-review`.
  **Rule:** Every new or rewritten user-facing docs page must pass a technical
  review that runs each cited command's live `--help` (and verifies behavioral
  claims against source) before commit; the documented-command conformance
  gate alone is insufficient because it validates command existence, not
  behavior.

No other finding meets the three durability criteria: FIX-001 items are fixed
and test-pinned, PROCESS-001 is already covered by the dry-run discipline rule
and the plan-body-preservation ADR, TRUST-002 items are tracked plan steps.
