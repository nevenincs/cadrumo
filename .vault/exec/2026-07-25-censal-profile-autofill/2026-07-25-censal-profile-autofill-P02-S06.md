---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:7721c363ea616e2fb49012769eb001dee980f1f1520747a08f631c4fa1ee1b90'
step_id: 'S06'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Prove the reader cannot write, failing closed at runtime on any BU36- or .zul or ModifDomiDual landing and on the /Sede/procedimientoini/ launcher prefix, with a static string check kept only as the weaker of two walls

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py`

## Description

- Pin seven real censal write surfaces as landings the reader must refuse: both filing tools, both domicile-modification siblings, and three procedure launchers.
- Pin four read surfaces as landings it must not refuse, including the consulta destination itself.
- Exercise the refusal through the reader's own exported landing rule rather than a local copy of it.
- Assert the launcher marker is the path prefix rather than any single procedure code.
- Assert the marker set is non-vacuous, carrying no empty entry that would match every landing.
- Scan the exported censal surface for any member that submits, fills, clicks, follows or sends.
- Prove the surface scan reports a planted writing member, and the static scan a planted filing path.
- Keep the static source check as an explicitly weaker second wall, with the reason recorded in the file.

## Outcome

The reader is provably unable to reach a censal write surface, and the proof is arranged so it cannot pass by measuring nothing.

The primary wall is the runtime landing refusal, because AEAT chooses where a navigation lands. The gate exercises the same rule the runtime guard calls, so it measures the reader's real logic. An earlier draft mirrored that matching locally, since the rule was private at the time. The mirror was reported as a weakness rather than left in place, the rule was then exported, and the mirror was deleted. A test that reimplements the rule it checks agrees with itself by construction and would keep passing if the real rule changed shape, which is the strongest wall failing in the manner of the weakest.

The gate found a live hole on its first run, before it was committed. The declared markers did not carry the procedure-launcher prefix, so a landing on the modification door linked directly from the consulta page passed the guard. Three cases failed for that reason and a fourth asserted the prefix itself. The predicted result once the prefix landed was eighteen passing, computed in advance from which cases the prefix would close and which read surfaces it must not catch; the observed result was eighteen. Predicting the count first is what makes the re-run a test of the model rather than a confirmation of the fix.

The secondary wall is a static source scan, kept because it is cheap and labelled as weak. This step's original text specified exactly one such check, for a token that appears in neither write surface, so an executor implementing it verbatim would have shipped a green no-write proof over a reader parked beside a write surface. The file records that if the runtime half is ever removed as redundant, the proof has failed.

## Notes

The surface scan is name-based, which is a weak signal and is why it is the second wall rather than the first. Its first draft reported three false positives on a serialisation framework's lifecycle hook. The fix excludes that framework's reserved namespace rather than naming the individual hook, because a per-case exemption is the mute-button pattern that turns a gate into a formality.

The launcher prefix refuses every procedure launcher, including consulta ones, and that is deliberate rather than collateral. What makes a landing safe is where the reader is, not what the page it landed on happens to offer, and a launcher is the page that offers the write. A future need to land on one is an amendment with a stated reason, not a hole left open in advance.

The reader this proves has no commit of its own. It landed bundled into an unrelated vault commit belonging to another campaign, along with its tests, the constants, the facade and the generated documentation stubs. Nothing was lost and the tree is coherent, so it was left rather than un-bundled, every tool that could separate it being barred in this worktree. Recorded because the history will not show the reader arriving.
