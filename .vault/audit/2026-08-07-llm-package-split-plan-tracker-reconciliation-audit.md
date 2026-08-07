---
tags:
  - '#audit'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:15d301c7dc10660331d50ba70bfb0cf37d2bbd37643b0d6c4cef760878e2dfe6'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace llm-package-split with a kebab-case feature tag, e.g. #foo-bar.
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

# `llm-package-split` audit: `Plan-to-code reconciliation: 50 steps landed against a tracker reading zero`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Plan-to-code reconciliation: 50 steps landed against a tracker reading zero | {level} | {summary}

     followed by a paragraph carrying the detail. Plan-to-code reconciliation: 50 steps landed against a tracker reading zero is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

## Context

The tracker read `0/83 steps, 0%, next W01.P01.S01` while roughly 50 steps were already landed in code across 20 commits. Anyone orienting from `vaultspec-core status` alone would have concluded the campaign was untouched and started at S01 — straight into a live agent's working files. This audit records the evidence mapping so the boxes can be ticked against something checkable rather than against a claim.

## How the done-set was established

Not from the plan, and not from the code alone. Each step below is carried by a commit whose body cites it by identifier, AND has an artifact confirmed present in the tree at HEAD. Steps cited as partial are excluded and named as such. Steps whose artifacts exist but which no commit body claims are also excluded — an artifact is not evidence that a specific Step's contract was met.

## Step-to-commit mapping

| Phase | Steps | Carrying commit |
| --- | --- | --- |
| W01.P01 | S01-S04, S65 | `796914c2e3` |
| W01.P02 | S06-S09 | `796914c2e3` |
| W02.P03 | S10 | `796914c2e3` |
| W02.P04 | S13-S17, S67, S79, S82 | `796914c2e3` |
| W02.P05 | S18, S22, S58, S68 | `796914c2e3` |
| W02.P05 | S19, S20 | `48b0430134` |
| W02.P05 | S21 | `a6a55f04e7` |
| W03.P06 | S23-S28 | `cdb874c245` |
| W03.P07 | S64 | `345fe7ea1a` |
| W04.P08 | S32 | `f9b7a6de3d` |
| W04.P08 | S33 | `bf48f35957` |
| W04.P09 | S40, S43 | `7b86bbb5cb` |
| W04.P12 | S30, S31, S60, S61, S73-S76 | `b3d4381442` |
| W05.P10 | S44, S45, S46 | `4ca4a36f0e`, `1adfb27151` |
| W05.P11 | S52 | `dbe38493c1` |
| W05.P11 | S51 | `5d96d24034` |
| W05.P11 | S48, S53, S54 | `dd43e0b8bd`, `04561ef0f6` |
| W05.P11 | S49 | `04561ef0f6` |

## Deliberately left unticked

**S50 — cited as "in part".** The commit body for `dd43e0b8bd` says "S50 in part", so the step's contract is not discharged. Ticking a partial step is how a campaign reports itself complete while work remains.

**Every step no commit body cites.** S05, S11, S12, S29, S34-S39, S41, S42, S47, S55-S57, S59, S62, S63, S66, S69-S71, S77, S78, S80, S81, S83. Some of these are visibly present in the tree — the `_xml.py` hardening reads as S16-adjacent and the parsers' own docstring describes the S80 refusal contract — but presence is not the same as a claimed, verified discharge, and the difference is exactly what a tracker exists to record honestly.

## Structural findings

The plan structure itself is sound: 83 checkbox rows, 83 distinct identifiers, no duplicates, no gaps across S01-S83, five waves, twelve phases, every phase carrying steps, no step under an undeclared phase, and the `L3` tier matching the wave depth. Seven identifiers appear twice in the document, but every second occurrence is a prose cross-reference in the coverage and parallelization sections, not a duplicate row. `vaultspec-core vault check all` reports no finding against this feature.

## One implementation-versus-plan deviation worth recording

W03.P06 names `src/cadrumo/application/ledger/_llm_suggestions.py` as the interchange contract's home. It landed as `src/cadrumo/llm/_suggestions.py` — the extension side rather than the core side. W03.P07 is titled "Keep every durable artefact on the core side", so the two read in tension. The Step text is left unedited: the identifier is load-bearing, and whoever made the placement decision owns the rationale. This is flagged, not resolved.

## Loose ends this reconciliation closed

Three surfaces kept describing things the campaign's W05 deletions had removed, none of which any single gate scans together:

- The operator-surface contract still declared `app ledger providers` after `dbe38493c1` deleted the verb, so the drift gate was red. The `config auth providers` entry is a different, live verb and was left alone.
- Four locale leaves outlived their only reference — `cli.ledger.providers.help`, both `evidence_acknowledged_help` strings from the retired consent gate, and the `cloud_evidence_upload` capability label.

Two apparent loose ends were checked and cleared rather than "fixed": `SubprocessProvider` is still exported and its tests still collect (`5d96d24034` deleted the probe and the doctor branch, not the enum), and the `cloud_evidence_upload` mention surviving in `_capabilities.py` is a docstring explaining the deletion.

## The process defect underneath

Twenty commits landed with zero execution records. The commit bodies are unusually good — they cite step identifiers and explain reasoning — which is the only reason this reconciliation was possible at all. That is fragile: it worked here because one author wrote careful messages, not because anything enforced it. `plan-closure-requires-exec-records` is the gate, and it was not being run.
