---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d27e72f2ea4d492a1283dc54364f7e7da50c9b4e93caf717be3fad83758e7109'
step_id: 'S311'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Gate the redaction funnel by property rather than by path, asserting no operator-facing emit primitive in the CLI package reaches stdout without passing a redacting renderer, with a positive control proving the detector fires

## Scope

- `src/cadrumo/entrypoints/cli/tests`

## Description

- Search for an existing owner of the property before building, and abandon the brief's premise when the search falsifies it.
- Prove the premise wrong by measurement rather than by reading: reconstruct the pre-fix blob out of tree and run the existing detector against it.
- Tighten the single existing authority instead of adding a second module with an overlapping matcher and a parallel allow-list.
- Re-key exemptions from path-and-kind to module, enclosing function and primitive, and make the reason structurally mandatory.
- Verify each candidate exemption by running the real redaction primitive over its real content, rather than reasoning about whether it looks sensitive.
- Prove the gate bites from outside the repository, so nothing under source is mutated and no peer sweep can commit the mutation.

## Outcome

**The row's premise was false and the falsification is worth more than the row.** A gate already owned this property. It was not blind: driving its detector against the reconstructed pre-fix blob reproduces the defect as an unowned emit site, and a pickaxe search over the gate's own history shows the offending path was never once in its allow-list. The gate was red from the commit that introduced the bypass until the commit that fixed it.

**It never fired because nothing ran it.** The module carries an integration marker while the project's default arguments select the unit lane, so invoking the file directly reports that nothing ran and exits clean. Four hundred and seventy-four modules carry that marker.

**Tightening beat adding, and the reason was a live defect rather than a preference.** Exemptions keyed on path and primitive meant one entry blanket-exempted every emit in the module that owns the funnel, and the same held for two further modules. That is the vacuous-pass hazard, found live. A second gate would have been shadowed responsibility with two lists certain to drift.

**Two of the three verdicts came back as no-ops, which is the harder result to report.** One stderr progress sink returns byte-identical through the funnel; one newly-found stdout bypass carries a display name the funnel does not mask. Both are latent rather than live, because the message field behind the first is an unconstrained string on a public sink and the second sits beside a sibling that funnels correctly. Their exemptions are worded to read as tolerated rather than clean, so a later reader does not mistake them for blessed.

**A third instance of the class was found outside the row's scope** and left for its own row rather than absorbed here.

## Verification

    gate, integration lane          6 passed
    out-of-tree mutation proof      5 passed
    ruff check / format --check     clean
    type check                      clean

The mutation proof carries a green control before each mutation and a restore after, and ran entirely outside the repository. The observed red names the file, line, enclosing function and primitive, and reproduces the exact callback shape the defect took.

**Marker selection is load-bearing in the verification command.** Without the integration selector the module reports that nothing ran, which is the finding rather than an invocation quirk.

## Notes

**This row does not yet deliver its own stated purpose, and that is recorded here rather than resolved by the checkbox.** The row exists to stop a second instance. The gate is complete and correct as a gate, and it currently cannot fail anything in continuous integration: the lane it lives in was historically absent altogether and is now enrolled non-blocking behind a triaged backlog. So a reintroduced bypass is detected and merges anyway. The row that establishes the lane's execution guarantee is a **prerequisite** for this row's purpose, not a follow-up to it, and this record states that so the three states the campaign-close rule warns about — delivered as specified, delivered narrower, recorded but not enforcing — cannot wear the same mark here.

**A correction against the sibling fix's commit message is owned by the coordinator, not by this row.** That message describes the leaked material as filesystem paths and asserts the funnel masks them. Measured, it does not; it masks embedded identifiers, and the path survives. The probe output carrying the disconfirming evidence had already been read when the claim was written, which is the ordinary shape of reading past it rather than carelessness. The fix is correct and its stated rationale overstates.

**The one-time proof against the real pre-fix blob is deliberately ephemeral.** Its durable equivalent ships in the gate as a synthetic reconstruction of the same callback shape, so the coverage survives the scratch copy and can be rebuilt from the parent commit at any time.

**A tree-wide collection break was observed mid-run and not touched.** It originates in an uncommitted half-finished sweep in another campaign's error registry, is working-tree only rather than a broken head, and self-cleared. It may reopen.
