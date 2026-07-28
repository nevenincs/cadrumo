---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S149'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S149 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Assert operator help, risk, mutability, schema, and live-registration inventories remain exact mirrors and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert operator help, risk, mutability, schema, and live-registration inventories remain exact mirrors

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py`

## Description

- Run the operator-surface drift gate and confirm the help, risk, mutability, schema, and live-registration inventories mirror each other.

## Outcome

The named gate passes. It holds the operator-facing inventories in mirror: a command present in the help surface but absent from the risk table, or registered as a schema without a live registration, fails the gate.

This mirror is what makes the preceding metadata rows durable rather than point-in-time: the risk, help, and contract surfaces cannot drift apart from the live command tree without reddening here.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.

## Corrected 2026-07-28

The Outcome above overstates what the gate did, and the overstatement is the
kind this campaign exists to catch: it describes a mirror the gate did not
implement.

It claimed "a command present in the help surface but absent from the risk
table, or registered as a schema without a live registration, fails the gate".
Neither held. Before this correction the module asserted exactly one thing --
that the `OperatorSurfaceContract` declares the families and sub-verbs the live
Click tree mounts. It read neither the help surface, nor the risk table, nor the
schema registry.

The help-versus-risk claim is not merely unimplemented, it is false as stated:
26 live commands carry no risk row today, so a gate enforcing it would have been
red. That absence is designed rather than drift -- `classify` derives safe
without a row, so read-only verbs are intentionally undeclared -- which means
the row's own "exact mirrors" wording is wrong for two of its five inventories
and could only be satisfied by declaring rows that say nothing.

What has now landed is the direction that is genuinely a defect: no risk row may
outlive the command it classifies. An orphan row survives a verb removal
silently and reads to the next author as evidence the door is still mounted.
Verified by mutation with a retired custody verb.

The other inventories the row names are not in this file. Schema-versus-live is
already asserted by the registered-schema gate, and the risk and mutability
mirrors against the MCP annotations are separate rows owned by the MCP surface.
This record should not be read as claiming this module asserts all five.
