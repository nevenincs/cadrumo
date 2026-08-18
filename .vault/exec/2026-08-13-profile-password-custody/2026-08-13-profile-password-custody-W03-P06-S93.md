---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:acfa497ea4f3b104df36d720b932fa2d2a60470d27cc276b8d1023053685db92'
step_id: 'S93'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh retire or rewrite the two hundred and ninety-four tests asserting a wizard profile-creation capability this campaign deliberately removed, which is the single largest cause of failure in the whole integration lane at roughly twenty-three percent of it and is stale tests rather than broken code, sequencing the work behind the ruling on whether scripted profile creation is permitted at all so the rewrite is not done twice

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/application/wizard/`

## Description

- Measure the real population mechanically instead of working from the row's
  figure, using an out-of-repo pytest plugin that observes construction of the
  retired-creation refusal and records the running test.
- Classify every measured test into delete / re-point / re-found before
  touching any of them.
- Re-point fixture-only seeding onto the credential registration door;
  re-found surviving intents onto the ``edit`` arm and the registration door;
  delete only what asserts a capability with no surviving contract.
- Prove three representative re-pointed clusters still bite by breaking the
  production behaviour each covers from outside the repository.
- Re-run the owned trees and attribute the residual red.

## Outcome

**The row's population figure was stale by roughly a factor of four. The real
measured population is 79 tests across 20 modules, of which 73 were
actionable.**

**How it was derived.** The refusal is raised deep inside the wizard and is
swallowed by the CLI error boundary, so grepping a suite log finds only the
subset whose assertion happens to print the command output. The measurement
therefore used an instrument rather than a search: a pytest plugin loaded from
outside the repository wrapped the constructor of the registration error that
carries the retired-creation message, let the real exception proceed unchanged,
and recorded the node id of the running test. That found 67 in-process tests.
Subprocess and installed-console tests run the CLI in a child interpreter the
plugin cannot reach, so a second pass grepped the captured suite log for the
refusal text inside each failure section and contributed 20 more; 8 of those
were false positives -- the refusal text had reached the log from an unrelated
test's captured output or from a ``modelo work create`` invocation -- and were
removed after checking each module for an actual profile-create call. Union
after filtering: 79. Six belong to the subject-access-request module this row
was told not to touch, leaving 73.

The gap to the row's figure is not a measurement disagreement. Several modules
had already been swept by earlier rows in this campaign and carry retirement
notes in their own docstrings; the population genuinely shrank.

**Three-bucket classification, with counts.**

- **Delete -- asserts the retired capability succeeds, no surviving intent: 13.**
  Seven in the profile-lifecycle verb module, two in the output-language
  module, one each in the create-wizard, choice-help, work-readiness and
  cold-start modules. Each deletion is named in its module's docstring with
  what, if anything, answers it now.
- **Re-point -- the assertion is still true, only the fixture seeded through
  the retired door: 42.** The two bundle modules (export roundtrip, import
  idempotency) are the bulk of it at 20; the rest are spread across the
  overview-status notice, JSON-schema conformance, root guard, modelo 202
  binding gate and modality, custody lifecycle, cold-start, help-without-secrets
  and installed-console modules. Every one of these kept its assertions intact
  and changed only how the profile came to exist.
- **Re-found -- the intent survives on a different surface: 18.** The seven
  INCN and new-entity fact tests and the modulos fact test moved to
  ``edit --quiet``, which carries the same flags and writes the same facts. The
  three localized answer-validation refusals moved to the ``edit`` arm, which
  still validates every supplied flag. The output-language storage and
  validation tests moved to the registration door plus ``edit``. The
  second-profile identity test and the show-versus-status contradiction test
  moved to the registration door.

**What was deleted, and why each had no successor.** The largest cluster is the
missing-required-flags refusal. It is now unreachable from every live surface:
``create`` refuses above it, and a non-interactive ``edit`` routes to the patch
path, which never checks required flags. That is dead production code, not a
test gap, and four tests asserting its wording were deleted rather than moved.
The same holds for the confirmation line of a creation success that cannot
occur, and for the refusal CONTENT of the retired path -- the manager frontend
renders its own refusals and the application layer renders none.

**Two of the three intents the ruling nominated for re-founding did not need
it, and one of them could not have it.** Duplicate-label collision is still
live coverage: that refusal fires ahead of the retirement check, so the test
asserting it never entered the population. CCAA-default disclosure is dead --
its predicate requires create mode -- and no test covered it, so nothing was
deleted. Only missing-flag naming was in the population, and it is the dead
path above.

**The blocker the row was warned about did not reproduce.** The brief said a
second in-process registration fails with an active-pointer transaction error,
and that any fixture needing two profiles would hit it. Registering two
profiles back to back in one process succeeded at the tree state this row ran
against. That changed two dispositions: the second-profile identity test was
re-founded rather than left unre-foundable, and the two-profile selection
precedence test was re-pointed.

**The cross-process record-read defect the predecessor rows left open is also
fixed.** Reading a registered profile's record from a subprocess against the
same storage root returns zero and reports the record valid. That is what made
the eight subprocess and installed-console tests re-pointable at all; the
sanctioned shape is to register in-process and hand the storage root to the
child, which then reaches the profile through its own login.

**Three bite-proofs, each run from outside the repository so no tracked file
was mutated.** Breaking the non-interactive patch write reds exactly the four
tests whose subject is a fact written through ``edit``. Dropping the initial
facts registration is handed reds six of the seven tests that seed through the
credential door and read those facts back. Replacing the localized
validation-refusal builder with raw pydantic prose reds all three localization
tests. A fourth attempted mutation did not bite and is recorded in the notes.

**Kept rather than deleted where the intent was unclear, as instructed.** Three
three-state absence tests (a fact must be absent when never supplied) survive a
broken write path by construction, because they assert absence. They were kept
and re-pointed rather than deleted; each is paired with a positive sibling in
the same module that the write-path mutation does red, so the pair as a whole
bites.

## Notes

**Attribution incident.** Every edit this row made was committed by other
sessions before this row committed anything. The work is in the tree and none
of it was lost, but it is spread across at least three commits authored under
other rows' subjects, including two that name a different step id. This row
committed nothing itself.

**A dropped assertion class, stated plainly rather than buried.** Several
re-pointed tests carried assertions on the file-fallback secret store
(``master.key`` and ``master.kdf``) and on the plaintext bucket manifest. No
live door writes either any more -- a registered profile's custody rides its
own capsule envelope, and a whole subprocess lifecycle runs against a root that
never grows a secrets directory. Those assertions were dropped, not moved, and
each drop is stated in the test's own docstring with the reason. Where a
dropped assertion carried a guarantee the test still needs, the guarantee was
re-anchored: the provisioning helper's loud-failure property is now carried by
the successful listing run that cannot pass against an empty root.

**A bite-proof that did not bite, recorded because it corrects a belief.**
Making the non-interactive patch projection accept every value without
validating it left the three localization tests green. The localized refusal
does not flow through that projection; it flows through the pydantic answer
model and the translation-key mapping that renders its errors. The mutation was
replaced with one that targets the mapping, which does red all three. The first
attempt is worth recording because it is the kind of proof that would have
passed for a proof while testing nothing.

**Residual red, none of it this row's.** Four causes, each confirmed by reading
the failure rather than by assumption. Absent CLI verbs -- profile export,
import and rename have registry keys and no mounted leaf, and the
passphrase-change verb does not exist. Registry validation and load errors from
a concurrent authority-grade registry sweep, one of which names the concurrency
outright in its message. Profiles seeded by the older minimal-record helper,
which writes no custody envelope and so cannot be logged into. And the
deliberately-failing assertions this row was told to leave alone.

**Two open defects surfaced and not fixed.** Reading a NON-ACTIVE profile's
record while another profile holds the session refuses, which is custody
working; but the write-side equivalent through the auth-configure verb raises
an unhandled traceback at the CLI boundary rather than refusing. Separately,
the ``profile show`` surface renders the manifest label in-process but not
across a process boundary, which is why one precedence test had to change its
observable to a per-profile fact.

**Not done, and deliberately.** The production surfaces that still advertise
the retired capability were not touched: the create arm still carries the
non-interactive flags, its help still prints a minimal-create example that
cannot succeed, and the two locale strings describing those flags are still
false. This row's scope is the tests; the ruling that retired the capability
opened no implementing row for the advertisement, and that gap is reported to
the campaign rather than closed here.

**One absorbed regression outside the population.** The pinned setup-question
inventory had drifted by five ids added by another session. The pin was updated
to match the declared flow, which is the response the gate's own docstring
prescribes.

- 2026-08-18 completion of the residual cluster named above (commit 61cf0a57f7). Retired the remaining absent-verb modules: rename maintenance events (negative pin kept), export roundtrip (11 retired, payload-contract test kept), subject-access-request (all retired), import idempotency (all retired). Re-founded the lifecycle-navigation module on the live surfaces: active-delete refusal, delete-success with the `deleted\ttrue` shape (target created through the production door so the legal-hold snapshot the preflight requires exists — the test seeding door deliberately records none per the S205 ruling), name reuse after delete, and a negative pin for the retired rename verb. Trimmed the surface-inventory verb list to the live set and re-founded the create-wizard module on the scripted arm. Relocated `test_cli_module_size.py` to `dev/audit/tests/` beside its moved baseline owner, fixing the collection error that blocked collect-only on the whole CLI test tree since the c0a7feef24 relocation; regenerated both audit baselines with the gate's own tool. Routed finding: the size gate now runs again after being uncollectable at HEAD and reports standing growth — six modules (`_config/__init__.py`, `_app_live.py`, `_app_live_payloads.py`, `_common.py`, `_ledger_read_cli.py`, `_modelo_discovery_cli.py`) and one callable (`_modelo_review_package_cli.py::review_package_build`) over budget; not laundered with `--accept-growth`, routed to the CLI module owners. Gates: touched modules green under `-m integration`; verb-input-schema/json-schema-conformance/repair-policy untouched; collect-only on the CLI trees clean (988 collected, 0 errors); ruff clean.
