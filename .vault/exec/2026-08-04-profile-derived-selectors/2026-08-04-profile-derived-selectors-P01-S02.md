---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:0f817697d43b5dd132cbf7da3e795a4451817f3098c223125fe9a714343ed424'
step_id: 'S02'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Declare the derived-selector pattern namespace as ONE atomic commit over three interlocked files, the schema TOML array, the typed entry model and its field on the schema definition, and the loader payload that passes the key through, because the TOML alone is silently dropped and the loader alone raises at every schema load, compiling the filing-year placeholder as a four-digit terminal-anchored fragment so a shorter pattern cannot swallow a longer sibling

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `src/cadrumo/domain/user_profile/_schema.py`
- `src/cadrumo/domain/user_profile/_loader.py`

## Description

## Outcome

The derived-selector pattern namespace ships and hydrates. Five entries cover the twenty
derived paths, each carrying its path pattern, the source paths it derives from, the
operator surface that edits those sources, a description, and its governing legal
references.

Verification here was coordinator-side and independent, because the executor had not
reported when the artefact was inspected. Every claim below was measured directly against
the shipped code rather than taken from a report.

The namespace hydrates through the real loader: the schema exposes five entries, and each
carries the grounding the design required rather than a bare pattern string.

The placeholder anchoring — the constraint whose absence would have made the anti-rot gate
unfalsifiable — is correct. The shorter of the two prefix-sharing patterns compiles with
its literal segments escaped, a four-digit fragment for the placeholder, and a terminal
anchor. Probed against four inputs: it matches its own path, does NOT match the longer
autonomico sibling, rejects a non-year suffix, and rejects a trailing extra segment. An
unknown placeholder raises a validation error rather than silently matching, which is the
fourth property the grounding pass specified.

The measured baseline is preserved exactly. The registry contract report is valid across
seventy-three modelos with zero errors and eighty-one issues, all on the export-layout
surface — identical to the pre-change measurement. The step was expected to be a
behavioural no-op because no selector currently reaches the miss branch, and it is.

The anti-rot gate landed against the namespace in the test module the grounding pass
identified, where a sibling test already pays the registry load and the result is
identity-cached.

Process note, consistent with the sibling Steps: the loader half of the change appears
under one of the bulk sweep commits from the revert incident rather than under a
pathspec commit of its own, while the gate landed separately under its own subject. The
three-file interlock the grounding pass warned about therefore did not land as one
authored commit. It caused no breakage — the namespace hydrates and the baseline holds at
the current head — but the atomicity was preserved by the sweep rather than by the
discipline, and that distinction is recorded rather than glossed.

Not verified here: the executor's own gate transcript, which had not arrived. The
functional properties above were confirmed independently, so the Step is closed on measured
evidence rather than on an unreceived report.

The executor's report arrived after this Step was closed on independent verification. It
corroborates every measurement above and adds three items worth recording.

A near-miss on the atomicity constraint. The executor confirms a peer bulk-sweep commit
captured its four production files mid-Step, and that the three interlocked files happened
to land together only because the sweep caught it after all three were written. Its own
assessment is that had the sweep fired one edit earlier it would have landed the schema TOML
without the typed model and killed tree-wide collection. The invariant held by timing, not
by design. This is the sharpest evidence yet that a no-pathspec sweep is not merely an
attribution problem but a correctness hazard for any change whose files are interlocked.

A test was changed, disclosed rather than buried, and the disclosure was correct. The
existing gate asserting that dropping a per-year field makes its selector unresolvable began
failing, because the pattern now legitimately resolves it. Rather than relax the assertion,
the executor split it: one test pins that the pattern alone resolves the selector, and the
original now removes BOTH routes and still pins that nothing silently excuses an undeclared
selector. Coordinator verification confirms the original guarantee survives intact and a
second was added, so net coverage rose. The executor explicitly asked for this to be checked,
naming adjust-the-failing-test as the move that quietly deletes guarantees. That is the right
instinct and it was warranted.

Gate discrimination was proved in both directions, and the second proof avoided a hazard.
Deleting a pattern was shown to fail the coverage count, but deletion is the opposite
direction from what the anti-rot gate detects, so a permanent negative control was added that
injects a dead pattern in memory. That avoids opening a mutation window on a tracked file,
which in this worktree is shippable state, as the sweep incident above demonstrates.

The executor also correctly ran the documentation stub check in verify-only mode, declining
the scaffold verb because it is tree-wide and would sweep peer stubs.

Residual risks it named honestly: the namespace field defaults to empty, so a loader
regression that stopped passing the key would silently yield zero patterns, caught only
because the gate asserts an exact count rather than a subset; and the patterns are validated
against today's live selectors, so no future year's binding is yet proved to resolve end to
end because none exists.

CORRECTION, measured by an independent coherence audit after this record was written.

The atomicity claim above is wrong as stated. This record and the executor's report both
said the three-file interlock survived by timing rather than by design. The audit measured
the sweep commit directly and found it carries all FOUR files together — the schema TOML,
the typed model, the loader passthrough and the validator hop — in one commit. There is no
intermediate commit in which the TOML exists without its model, so no broken state was ever
reachable from history.

What remains true is the counterfactual: had the sweep fired one edit earlier it would have
landed a partial state that kills tree-wide collection. The hazard was real and the
interlock warning was correct. But the landing itself was atomic, and describing it as luck
overstated the danger that actually materialised. The only later touch to the typed model
was a two-line docstring fix making the terminal anchor render literally, plus the gate and
one facade export.

The audit also confirmed the validator change is exactly four hunks — the import, the index
field and its accessor, the population, and the membership condition with its comment. The
four sibling issue functions are absent from the diff entirely and therefore byte-unchanged,
and each still reads only its disjoint namespace. The empty-selector arm is intact and still
returns before the hop. The accessor's docstring names why the other four surfaces must not
route through it, so the mis-classification risk the grounding pass raised is closed in prose
at the method itself rather than left to discipline.

## Notes
