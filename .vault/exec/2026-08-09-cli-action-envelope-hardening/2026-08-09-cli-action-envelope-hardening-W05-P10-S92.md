---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0109fb9f431bffee8f02a22286193276177cc68746b5077735b924c9c1a35097'
step_id: 'S92'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Replace overview renderer action producers and co-located renderers with the shared resolved action projection

## Scope

- `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `src/cadrumo/locales/{ca,en,es,hu}.yml`
- Owned proof: `src/cadrumo/entrypoints/cli/tests/test_overview_rendering.py`

## Description

- Delete the notice builder that recovered a message by splitting the text line on a separator, and the four line builders that emitted localized sentences with embedded commands.
- Add one resolution helper that turns a producer declaration into a resolved notice action, and one notice projector per surface: status guidance rows and calendar warnings.
- Render every warning text line from its own notice's message so the line and the envelope cannot disagree.
- Emit one notice per prepare step and per pipeline row that has somewhere to go, so the shared envelope renders an executable line for exactly the rows the payload marks actionable.
- Retire nine locale keys carrying command prose and add nine explanation-only keys in all four catalogues.
- Rewrite the rendering proof onto the one-projection contract and prove it bites.

## Outcome

The defect this Step existed to close was concrete: the text surface printed a locale sentence beginning with a command, and the JSON surface produced its notice message by partitioning that same sentence on `" - "`. Both are gone. Guidance is now a localized explanation plus a resolved action, and the executable text line is rendered by the shared envelope helper from the very notices the JSON envelope carries.

Text and JSON share one projection, and the evidence is mechanical rather than asserted. The rendering proof drives the production envelope helper over the notices the status projection returns and asserts the executable line count equals the actionable notice count, that each line contains its own action's live CLI path tokens, and that every notice message appears in the text body. It runs over eight real workspace states.

Both new gates were proven to bite by mutating the running module from outside the repository, with nothing under the source tree changed. Substituting a hand-assembled wire action for the resolved one - the shape a producer bypassing live resolution would produce - failed 16 parameterisations across the one-projection and live-resolution gates. Restoring the retired command-prose sentence as a guidance message failed 8 parameterisations of the prose gate. Both mutations were applied through a scratch pytest plugin on the path, so no tracked file was ever modified and a crashed run would have left no residue.

Locale keys retired: `next_import_command`, `next_landing_command`, `next_modelo_210_unsupported_command`, `next_modelo_work_command`, `next_review_command`, `next_work_calculate_command`, `next_work_create_command`, `next_step_available`, `integrity_next`. Locale keys added, in Catalan, English, Spanish and Hungarian: the nine `next_step` explanations `create_profile`, `resume_work_unit`, `start_another_work_unit`, `start_work_unit_from_ledger`, `modelo_210_sede_only`, `review_ledger`, `import_transactions`, `repair_storage`, `command_guide`. Three existing keys lost their embedded commands: `profile_missing`, `work_units_present`, `work_units_present_with_discarded`.

The rendering proof passes at 39 tests. The catalogue-resolution, JSON-conformance and docstring cross-reference gates are green on this surface.

## Notes

- The installed-product proof for this feature was extended rather than duplicated. It now asserts, for every supported output language, that no overview notice states a command as prose and that every notice action carries a live CLI path, and that the count of fully resolved actions is identical across locales - prose is translated, executable identity is not, so a locale resolving fewer would be one whose guidance had decayed back into prose. That module builds and installs real wheels and was not run to completion here; it is left for the reviewer's full-lane run.
- A guidance row whose continuation needs operator-supplied input now shows an explanation with no command. The blank-workspace import row is the visible case. This is a deliberate loss of a placeholder instruction, not an oversight: `ledger import` requires a file and a provider, so no honest ready-to-run command exists. Restoring executable guidance for such rows would need the shared envelope helper to render a requires-arguments precondition action onto the text surface, which is owned by the shared CLI module and outside this Step.
- The locale keys were first held in a lookup table, which the locale scanner cannot see; they were reported as unreferenced extras. They are now spelled as literal arguments to the translation call, following the existing shape used for calendar shift reasons.
- One stale docstring cross-reference in this module, naming a constant a peer had relocated out of the core package, was repaired here rather than left as a pre-existing failure, since the file is this Step's own surface.
- The four locale catalogues carried a peer's uncommitted addition. The commit was built as a HEAD-anchored own-only change with the peer's block removed by explicit marker, staged by blob rather than from the working tree, and verified after the fact to contain none of the peer's markers. The peer's uncommitted work is intact in the working tree.
