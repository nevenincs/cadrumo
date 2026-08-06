---
tags:
  - '#audit'
  - '#cadrumo-product-rename-authority-lock'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:946465155354117fea7418c9703cdaf4f749699fa43a175c0658da787ebcdc4c'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-authority-lock` audit: `Authority lock commit review`

## Scope

Commit `2651c91ccb77a886a12a5a410c68b74b50c0c717` was reviewed independently
against the accepted parent rename decision, the binding CLI executable
decision, the active rename plan, the S86 execution record, the promoted rule,
all generated provider copies, and the runtime identity contract. The review
also checked commit-scope cleanliness and focused real behavior without changing
the implementation.

## Findings

### vault-hygiene | low | The changed CLI ADR fails two repository hygiene checks

`vaultspec-core vault check all` reports the changed CLI ADR with a stale
`modified` stamp and one extra blank line. The shared vault has many unrelated
warnings and one unrelated schema error, but these two warnings are introduced
on a path owned by this commit. This contradicts the S86 record's claim that the
vault structures were verified.

**Re-review state: resolved by `e34952e37bacf9509ba3ba8a5733ee61cfd5bbaf`.**
The CLI ADR now carries `modified: '2026-07-13'`; focused modified-stamp and
markdown checks no longer report that document. `git diff --check` is also
clean. The rename plan's one remaining annotation warning predates both reviewed
commits and is not remediation-owned.

### supersession-contract | medium | The binding ADR misstates and incompletely records its overrides

The binding CLI ADR says the human executable is the sole parent-tuple element
it overrides and later says it only changes that element. This commit also
changes the accepted display casing from `Cadrumo` to `CADRUMO`. Its section
labelled the canonical identity tuple also omits the exact repository, MCP
server/tool/resource/plugin, and companion-distribution identifiers that the
superseded parent decision defined. Although the runtime tuple and promoted
rule cover most of those values, the accepted superseding decision is internally
inaccurate and does not itself provide the complete referent matrix downstream
work is expected to obey.

**Re-review state: resolved by `e34952e37bacf9509ba3ba8a5733ee61cfd5bbaf`.**
The ADR now names both overrides explicitly: display casing `CADRUMO` and sole
human executable `aeat`. Its complete matrix also records the lowercase
`cadrumo` package, distribution, repository, MCP server/tool/resource, and
plugin identifiers; `cadrumo-mcp`; `CADRUMO_`; both companion distributions;
`cadrumo_data`; and the external authority short name `AEAT`.

### plan-closure-honesty | high | Checked steps now claim behavior the commit tree does not provide

The plan rewrites already-checked S25 to require an `aeat` program identity and
`CADRUMO` help surfaces, and rewrites already-checked S62 to require `aeat`
help invocations plus `CADRUMO` product copy, without reopening either Step or
adding an open remediation Step. At the reviewed commit, the real CLI still
pins `prog_name="cadrumo"`, recognizes `cadrumo` rather than `aeat` in its full
invocation parser, and the locale authorities still render title-case
`Cadrumo` plus `cadrumo <command>` guidance. A real `uv run aeat --help`
confirmed the stale product casing and command guidance. S78 also remains
checked despite claiming focused CLI behavior. The active plan therefore
reports completed work that is observably incomplete, so downstream execution
and closure cannot rely on its checkbox state.

**Re-review state: resolved by `e34952e37bacf9509ba3ba8a5733ee61cfd5bbaf`.**
The plan reopens exactly 24 contradicted Steps: S25; S37-S40; S43 and S45;
S48-S55; S57-S58; S62-S67; and S78. Direct target-tree evidence justifies
each lane: the CLI pins and parses `cadrumo`; core/extras/Docker/split smoke
probes expect or invoke the wrong human command/version identity; MCP server
and prompt copy remains title-case; agent generator, generated marketplace,
MCPB, recipes, CI, and smoke workflows retain stale product or command copy;
all four locale catalogues retain stale display and command strings; and their
dependent regeneration, validation, and aggregate behavior gates must rerun.
The reopened set is therefore complete for the contradicted checked contracts
and not excessive. Closed adjacent Steps retain already-correct machine
identities, such as `cadrumo-mcp`, rather than falsely asserting completed
display or human-command remediation.

## Recommendations

Verdict: **FAIL**. The high-severity plan-closure finding blocks downstream
execution from treating the authority-lock phase as reviewed and complete.

Reopen the affected implementation and verification Steps, or add explicit open
repair Steps that own the runtime/help/locale corrections and their real
behavior gates. Amend the superseding ADR so it accurately names both operator
overrides and carries the complete exact identity tuple. Refresh the CLI ADR
through the Vaultspec workflow and repair its markdown hygiene before review is
rerun.

## Re-review

Commit `e34952e37bacf9509ba3ba8a5733ee61cfd5bbaf` resolves all three findings.
S87 is traceable in both the active plan and its matching execution record, and
the record truthfully leaves the audit unresolved for this independent pass.
Its checked state describes completed authority remediation and reopening, not
completion of the newly reopened downstream implementation.

Focused verification passed: all five product-identity tests passed;
`git diff --check` passed; the CLI ADR is absent from focused modified-stamp and
markdown findings; and the full Vaultspec check reports no new error on the
remediation paths. The full shared-vault check still has one unrelated schema
error and pre-existing warnings. The audit feature also lacks an index because
the review task restricts this commit to the exact audit path.

Final verdict: **PASS**. No HIGH or CRITICAL findings remain. The pre-existing
plan annotation and shared-vault warnings are nonblocking for this remediation.
