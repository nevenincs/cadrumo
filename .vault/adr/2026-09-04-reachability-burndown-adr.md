---
tags:
  - '#adr'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e5fc4db9602ccfc657f58ae7747e3e76b90962fadb7ce8be8e146310ff2a9631'
related:
  - "[[2026-09-04-reachability-burndown-reference]]"
---
# `reachability-burndown` adr: `Reachability closure through owning mechanisms` | (**status:** `accepted`)

## Problem Statement

The reachability campaign must remove unreachable code and missing wiring without turning its investigation state into a second product model. The original decision required every finding to be entered in a closed classification ledger. Execution showed that this persisted transient judgements such as staged, deferred, superseded, and should-be-live; encouraged production docstrings to describe campaign state; and made quality gates depend on a hand-maintained list of module and symbol names. This amendment replaces that mechanism while preserving the requirement that every live finding is resolved through its owner.

## Considerations

- Reachability proves the absence of a runtime path, not the reason for it; `2026-09-04-reachability-burndown-reference`.
- Production code and tests must stand on their own and cannot cite campaign state, development tools, plans, or audits.
- A maintained classification or exception inventory becomes a second authority and can outlive the code fact it describes.
- The live source graph, command tree, fixture registry, typed contracts, and owning behavioral tests can establish implementation facts without a development-status catalogue.
- Baseline, threshold, allowlist, frozen-prefix, and deferred-owner widening can all turn an unresolved signal green.

## Considered options

- **Retain the classification ledger and strengthen its consistency tests.** Rejected because stronger bookkeeping still makes development metastate a code dependency.
- **Move the same catalogue into another development file or generated form.** Rejected because generation changes transport, not authority; the maintained status model remains.
- **Keep investigation state only in the active plan and Step Records, and make code-quality checks derive current structural facts from their owning sources.** Chosen.
- **Delete the audits with the ledger.** Rejected because removing the detector would hide the defect rather than remove the invalid ownership mechanism.

## Constraints

- No production source, test, configuration, audit, or quality gate may read or cite a reachability disposition catalogue or carry campaign states such as staged, deferred, superseded, ignored, implemented, or in flight as an exception mechanism.
- No quality gate may maintain a list of module names, symbol names, code-name prefixes, frozen owners, or accepted findings to decide whether the current tree passes.
- Audits derive their population from the live tree and report exact identities. A release gate is green only when the structural property it names is satisfied; an open campaign signal remains visibly red until its owning mechanism resolves it.
- Resolution means deletion of displaced code, wiring through the real product boundary, relocation to the narrowest genuine owner, or replacement by a live structural declaration and detector. Classification alone never resolves a finding.
- Tests assert behavior and structural relationships, not implementation status. Temporary triage and ownership notes live only in the plan and its Step Records.
- Source under `src/` has no dependency on or prose awareness of `dev/`, Vaultspec, campaign state, or development-only exception mechanisms.

## Implementation

Delete the reachability classification ledger and every parser, consistency test, citation check, and source comment coupled to it. Preserve independent live detectors, but remove their exception and disposition joins. Replace identity baselines and frozen-prefix exclusions with live zero-target reports, then burn each reported finding down through the code or contract that owns it.

For TUI and command surfaces, derive availability and coverage from the executable route or fixture registry and from class structure. Do not maintain parallel `implemented`, `needed`, `development-only`, or ignored lists. A concrete surface is either registered and exercised or remains a live finding.

Each iteration re-measures the live signals, grounds one coherent finding, applies the owning repair, runs the focused gate, and records only the resulting file changes and verification in its Step Record. Contradicted decisions are amended before dependent plan work continues.

## Rationale

The chosen option keeps product truth in executable structures and keeps temporary coordination state in the lifecycle documents designed to expire with the work. It removes the closed-loop failure where a hand-authored exception and a test of that exception agree while the product remains unwired. It also makes closure unambiguous: the detector has no sanctioned identity to subtract, so only a real product change can clear the signal.

## Consequences

- The previous closed-taxonomy, classification-ledger, intentional-disposition, and frozen-prefix requirements are withdrawn.
- Existing ratchet and render-coverage baselines must be retired or converted to live zero-target detectors; they may remain red while the campaign burns down their exact findings.
- Development-only prototypes and fixtures must live at their actual development boundary, while production registries expose only executable product structure.
- More quality checks will be red during the campaign, but none can claim green by preserving a reviewed exception.
- The plan and Step Records become the sole home for temporary triage, ownership, and sequencing state.
