---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8c8170830c8a0e59fe24f4fa7a80a9a83cb7685af99301bfd36a0bc22e213194'
step_id: 'S168'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh finish the bucket-event taxonomy repair on the five command-line profile-fact doors the wizard-scoped repair did not reach, since they call the same fact-writing authority with a free string the closed event enum does not contain and therefore crash the operator's manager edit path exactly as the wizard doors did, the ruling that a profile-fact write emits the values-updated lifecycle member and carries its door identity in the payload being already settled and needing only application

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py and _manager_actions.py and _capabilities_cli.py and _descendiente.py`

## Description

- Reproduce the crash on a command-line door end to end against a real encrypted capsule before touching anything.
- Enumerate every command-line profile-fact door and repoint each at a typed door member.
- Extend the closed door taxonomy with the five surface identities the wizard set lacks.
- Type the record repository's event parameter to the closed catalogue, so a free string is refused at the boundary rather than deep in the writer.
- Add a structural door contract gate and prove it bites on a reverted stamp without editing a tracked file.

## Outcome

**The crash is real, was reproduced, and is repaired.** Driving the manager field door on a real
capsule — real custody envelope, real DEK, real encrypted secure-object store — the write dies with
`TypeError: apply_wizard_fact_changes() got an unexpected keyword argument 'event_type'`. That is a
*different* failure from the one the row describes, and the difference matters: the row's premise
(a free string reaching the closed enum and surfacing as a record integrity error) was the state
before the wizard repair renamed the shared writer's parameter. Since that rename the command-line
doors have not been reaching the taxonomy at all — they die at the call. Both states lose the whole
command; the current one is louder. The underlying premise is unchanged and still governs, because
the parameter rename is exactly what made these callers a hard break rather than a silent one.

**Six doors, not five.** The row names five sites. A further call in the manager actions module
stamps `profile.auth.facts.applied` and was missed by the row's list, though the wizard repair's own
notes had counted it. The full set is: two in the manager frontend (the standalone field-persist
helper and the manager session's bound persist closure, both `profile.manager.field.applied`), two
in the manager actions module (`profile.auth.facts.applied` on the authentication page commit and
`profile.manager.row.added` on the add-row action), one in the capabilities surface
(`profile.capability.changed`), one in the descendiente surface
(`profile.wizard.descendants.changed`). A tree-wide sweep of every call to the shared writer now
shows twelve sites, all passing a typed member and none passing a string.

**What each door now emits.** All six emit the one lifecycle member the ruling settled, and carry
their surface in the `door` payload key: the two field sites `manager.field`, the authentication
page `manager.auth`, the add-row action `manager.row`, the capabilities verb `cli.capability`, the
descendiente verbs `cli.descendiente`. The taxonomy gained five members; no bucket-event member was
added, so no new value entered the closed event catalogue.

**The descendiente door gets its own member rather than reusing the wizard's.** The interactive
wizard's repeating group and the non-interactive descendiente verb family are two surfaces an
operator can distinguish, and the door axis exists precisely so a history query can say which one
last rewrote the set. Collapsing them onto the wizard's member would have destroyed the only
information the key carries. The value keeps the Spanish stem the domain mandate requires.

**Boundary ruling: the field CAN be typed, no version bump is needed, and half of it is closed.**
The command-event model is a transient in-process command object — built by the record repository,
consumed by the capsule writer's event builder, and never serialised; the thing that reaches disk is
the bucket event the builder returns. So typing its event field to the closed enum is a pure
in-memory shape change with no persisted format implication and no upgrader. Under the model's
strict configuration a plain string is refused outright, so every construction site would pass a
member; that is four sites, all mechanical.

What was closed: the record repository's fact-change command now DECLARES the closed catalogue as
its parameter type, and narrows the value through the catalogue as its first act — before the record
is read and the replacement composed. A caller-invented string is now refused at the call with the
catalogue's own message naming the offending value, and nothing is written. Every caller was swept
to pass members.

What was NOT closed, and why: the model field itself belongs to another agent's file in this
campaign and was left untouched. It is a one-line change to the annotation, plus dropping the value
read at the writer's own creation site and passing a member at the one remaining internal
construction. Until it lands, the runtime guarantee rests on the repository's narrowing rather than
on pydantic; the annotation and the narrowing together make a further untyped site refuse loudly at
its own call site, which is the practical closure, but the model still accepts any string from a
caller that reaches it directly.

**Bite proof, and the needle does bite.** Three regressions were driven against a temporary copy of
the source tree with the gate functions re-pointed at it from a scratchpad script; no tracked file
was modified, and the tracked sources were digested before and after to prove it. Reverting one
command-line door to its free string reds two assertions, naming the exact file and line and the
member that stopped being reached. Reverting ONE of the two same-member sites in the manager
frontend also reds — this is the case the wizard repair warned about, where a text needle cannot
tell two call sites in one module apart, and it is why the new gate reads the call arguments out of
the syntax tree rather than matching file text. Reverting the lifecycle stamp reds the emission
gate with the exact missing token. The control run over an unmodified copy is green on all four.

**The emission gate's needle was updated and re-proved.** Typing the repository parameter turned the
wizard's stamp from a value read into a member, so the pinned needle no longer matched its own
emission. It was repointed at the new expression and re-proved by the same reverted-stamp method;
it still pins the emission rather than the symbol, so the module's own prose cross-reference does
not satisfy it.

**Verification.** All six doors were driven end to end on a real capsule inside one session. The
bucket history shows six values-updated rows carrying five distinct door values, with the record
revision advancing 2 to 8 and every row's door key present. The negative was confirmed too: a
genuinely invalid event value is refused with the catalogue's own message and the record revision is
unchanged afterwards, so the refusal costs nothing.

The door contract gate and the emission gate pass. Lint and format are clean on all eleven changed
files, and all three type checkers report zero diagnostics on them. The command-line config, wizard,
buckets and user-profile suites run 669 passed, 25 failed, 4 errors; the terminal-interface suite
runs 110 passed, 2 failed. **No failure is attributable to this change.** A search of the whole
failure log for the door taxonomy, the shared writer, the record repository command, the event
catalogue and every changed module returns nothing. The failures are peer breakage and pre-existing
debt: registry authority-grade and export-layout validation errors dominate, plus a minimal-profile
registration signature mismatch from a half-landed relocation, absent command-line verbs, a notice
validator refusing raw command prose, and two missing relocated symbols. The import-hygiene gate
runs 56 passed, 9 failed, and every failure names pre-existing sites; no changed file appears in any
of them.

## Notes

- **The row's premise had partly dissolved and this is stated rather than smoothed over.** The row
  describes a free string crashing against the closed enum. At the time of execution the doors were
  crashing one layer earlier, on the parameter name. The repair is the same either way, but a report
  claiming to have reproduced the enum coercion error at these sites would have been false.
- **Scope beyond the four named files.** The row scopes four command-line modules. The repair also
  touched the wizard persistence module (the five new members, sanctioned by the dispatch), the
  record repository and the cotejo apply path (the boundary typing and its caller sweep), the shared
  capsule test helper and one lifecycle test (callers of the newly typed parameter), and the two
  gate modules. None of these is on another agent's hold list. The one file that IS held — the
  capsule record model — was deliberately not touched, which is why the boundary is half closed.
- **The shared writer and its door type still carry the wizard's name** while five of their nine
  door members and six of their twelve call sites are not the wizard. Renaming both to a
  surface-neutral pair is the right end state and is a cross-package relocation with consumers in
  two packages; it was not attempted inside a crash repair. Carried forward.
- **A naming inconsistency was left rather than silently corrected.** The wizard's existing
  descendant member uses an English stem while the new command-line member uses the Spanish one the
  domain mandate requires. Correcting the older value would rewrite a member another agent shipped
  and reasoned about, and it changes an emitted history value; flagged for the owner rather than
  taken.
- **The add-row door needed a valid row to prove its write.** A first drive filled the socios row
  with placeholders and was refused by schema validation from inside the shared writer — which
  itself proved the door reached the writer, but produced no history row. Driving the same door
  against the activities section with valid values produced the manager-row event. No refusal was
  bypassed and no validation was relaxed to get there.
- **Peer interference, reported not remedied.** Mid-task a series of peer sweep commits captured
  every uncommitted edit under registry-sweep subjects, so this repair is already in history under
  unrelated commit messages rather than sitting in the working tree. Every change was verified
  present and intact afterwards. Nothing was reset, stashed, rewritten or committed by this agent.
- **A harness quirk worth recording.** Running a probe from the shared temporary directory races
  peer test processes creating and removing session directories under the same root, which aborts
  collection before any test is found. Rooting the run at the probe's own directory avoids it.
- **Not done:** no locale key was added or needed. No bucket-event catalogue member was added. No
  surface events were introduced for these verbs. The plan row was not checked.
