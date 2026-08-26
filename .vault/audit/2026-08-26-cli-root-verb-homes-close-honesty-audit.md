---
tags:
  - '#audit'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1fb66b026e7a8ca4b49aba7224e30c6328852266acfcd3296e74b5180bca0bff'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
  - "[[2026-08-26-cli-root-verb-homes-adr]]"
---

# `cli-root-verb-homes` audit: `campaign close honesty review`

## Scope

A close review of the `cli-root-verb-homes` campaign, written as if inheriting it
cold. It checks the closure claim against the live command graph rather than
against the plan's checkboxes, because 33 of 35 Steps closed is a statement about
the plan, not about the tree.

The standing goal the loop carried was: every `app` versus `config` CLI command
conflation and command verb family comprehensively tightened, rehomed, reviewed
and verified. That is the bar this review measures against, and it is deliberately
not narrowed to what the plan happened to enumerate.

## Findings

### closed-and-verified-in-the-live-graph | resolved | Eight of the thirteen originating findings are structurally closed, re-checked against the graph rather than the plan.

`sync calc` returns zero leaves; the workbook family is `app modelo spreadsheet`
with `push`, `pull`, `calculate` and `verify`. `config google sync` returns zero
leaves; Google holds only auth, folder, credential-source, probe and status.
`app maintenance` returns zero leaves. The `file` token now names exactly one leaf
in the whole CLI, `app modelo work file`, which is the filing act.

Root placement, transport locus and local-path spelling each have a gate, and each
gate was broken on purpose from a scratchpad script and observed to red. No
tracked file under `src/` was mutated to prove any of them.

### two-steps-blocked-on-a-concurrent-migration | open | S07 and S27 are refused on evidence, not deferred for convenience, and neither is inside this campaign's control.

S07 requires the moved workbook handler to import canonical defining modules
rather than package facades. All four target packages — `application/export`,
`adapters/outbound/google`, `application/storage/calc_sheets` and
`application/calculations` — still expose only `errors.py` publicly, so the
conversion would mean importing a private submodule across a package boundary, or
creating public modules inside packages another actor owns. Re-checked at close;
still true.

S27 would retire `config profile preflight`. It is refused twice over: the verb is
already broken on main by a peer `work_addressing` signature change, so the two
surfaces cannot even be compared; and `app modelo readiness` refuses without an
active login session where preflight did not, which matters because preflight
answers a setup-time question asked while a profile is still incomplete.

### the-standing-goal-is-not-fully-met-and-the-gap-is-named | open | Three findings are closed by ruling rather than by change, and one was never carried as a Step.

What the standing goal still asks for that this campaign did not deliver:

`registry-integrity-reported-from-both-roots` is NOT resolved. `config repair
integrity registry` and `app registry verify` both remain live. The retirement was
refused on proof that they do different work — the config verb builds a
representative `M100` snapshot the app verb never reaches — but an operator still
has two places to ask whether the registry is healthy and gets different answers.
The finding was downgraded from duplication to discoverability and left open. That
is a real conflation the standing goal asks to tighten, and this campaign did not.

`modelo-scoped-profile-readiness-has-two-homes` is NOT resolved, for the S27
reasons. Both verbs are live. A third leaf, `app ledger preflight`, carries the
same noun in a different family and was never in scope at all.

`two-local-inbound-verbs-in-one-modelo-family` was untouched when this review was
written and is now **settled and withdrawn** (S36). `filing-record import` takes
AEAT-attested evidence kinds that `is_official_aeat` accepts; `observe-local`
persists a cert-free operator reconstruction that is non-official by default.
They sit on opposite sides of the boundary `no-silent-under-declaration` governs,
and merging them would be a safety regression. Both stay.

`aeat-network-pull-precedent-is-inconsistently-applied` and
`pull-verb-semantics-diluted-beyond-aeat` are closed by the D2 grammar rather than
by moving anything: `pull` now means read-from-a-remote-counterparty everywhere,
which makes the previously anomalous `config profile censo pull` and `config
provision pull` conformant by definition. That is a legitimate resolution, but it
is a redefinition, and a reader should know the tokens did not move.

### the-tracked-benchmark-census-is-stale | open | `dev/benchmarks/cli/baseline.census.json` does not match the live command set, and this campaign did not refresh it.

It was already stale before the campaign: `app ledger evidence attachment-queue`,
`evidence attachment-view`, `inventory closing-authority-record` and `app modelo
work run` are live peer-added verbs absent from it. The campaign's renames widened
the gap. Re-capture needs an uncontended tree and a full timing run over 365
nodes, and hand-editing would fabricate the `source_snapshot_digest` and the
timing provenance. Recorded rather than faked.

### suite-state-at-close | open | Thirty CLI-suite failures remain, all traced to concurrent peer work, and three modules cannot be collected at all.

1426 passed. Every failure was traced to a cause rather than assumed: inert
`cadrumo.application.wizard` and `cadrumo.application.modelo` namespaces
(seventeen), the modelo-200 `2025-y-siguientes` registry split (four), non-TTY
passphrase-channel refusals (three), output-surface exemptions keyed to
peer-renamed modules (two), `LedgerIssuePayload` gaining an `operator_action`
field (one), and three others.

`test_fast_path_no_state`, `test_ledger_exception_propagation` and
`test_storage_session_preconditions` are excluded from the run entirely, because
peer renames break their imports at collection and one broken import aborts the
whole run. No campaign-owned module fails.

### defect-classes-this-campaign-produced | resolved | The campaign introduced twenty of its own failures, and two classes are worth carrying forward.

A find-and-replace sweep cannot distinguish a RENAME from a MOVE or a DELETION.
Four exact-set census modules ended up carrying keys such as
`config_modelo_spreadsheet_cli_pull` for leaves that had left the family
entirely, and the same error recurred four times before it was addressed as a
class rather than file by file.

A module's obligations change when it moves directory. `_app_maintenance.py`
carried `tr(..., default=...)` translation fallbacks legally; the identical file
inside `_config/` violates that directory's ban on them without a line changing.
Separately, `_command_spec.py` is probed by `runpy.run_path` with no package
context, so the relative core import added in W01 broke a constraint stricter than
the module's own docstring states.

## Recommendations

Do not mark the campaign structurally complete. Two findings from the originating
audit remain open in the live tree: registry-health duplication and readiness
duplication. Both were refused on evidence rather than skipped, and both leave an
operator with two places to ask one question.

Re-open S07 and S27 the moment the concurrent migration lands. Both are
one-session changes once their blocker clears, and both carry their evidence here
so the next session does not re-derive it.

Refresh `baseline.census.json` in an uncontended tree, or retire the tracked
artifact if a captured timing baseline is no longer worth committing. Its
staleness predates this campaign and will keep widening.

A follow-on record owes the `config profile archive pull` restore path. `push` now
writes a remote replica that nothing can read back, and naming it `push` beside a
working local `export` and `import` pair was chosen precisely to keep that gap
visible rather than to close it.

## Addendum: work landed after this review was written

This review was written when the plan stood at 35 Steps and concluded the
campaign was not structurally complete. Six further Steps landed afterwards, and
the closure state below supersedes the Findings above where they conflict.

**S37 — the two surviving duplicate-question pairs were tightened by help text.**
The review's central complaint was that refusing the two retirements left the
discoverability half unaddressed. It was worse than the review recorded: `app
registry verify` said "Verify the integrity of the local registry" and `config
repair integrity registry` said "Run full registry validation", so nothing told
an operator which to reach for. All four verbs across both pairs now state what
they uniquely cover and name their sibling. Both pairs remain live; this is a
tightening, not a resolution, and the standing goal still asks for one home per
question.

**S38 — the transport grammar gained a third verb category.** Sweeping all 294
leaves against the campaign's own D2 found a gap in D2. Its credential-enrolment
carve-out was a special case of an unstated rule: a verb that CREATES a record
names the record, and the file it reads is declared on its parameters. `app
ledger evidence add`, `evidence batch` and `inventory closing-authority-record`
were covered by nothing. The arbitrary carve-out is gone.

**S39 — the verb-grammar gate D6 promised was shipped.** W05.P12 had landed only
the option-spelling half. The verb half now refuses a leaf that declares a
transport locus while wearing a retired token, and is proven to bite.

**S40 and S41 — a conflation the originating audit missed entirely.** The
single-subject read verb was split seventeen `view` against eight `show`, with
the help text using both words interchangeably. All eight `show` leaves are now
`view`: spec keys, envelope identities, help keys, eight handler functions, eight
payload classes, four locale catalogues, six documentation files. The curated
operator help was found printing three dead command strings and was corrected.

**S42 — the rest of the vocabulary was examined and left alone.** `remove`
versus `delete`, `status` versus `check`, and the always-refusing `config auth
apoderado check` are each principled and were not touched. Only one of four
groups was a genuine defect.

**Closure state.** Forty of forty-two Steps closed. The two open Steps are S07
and S27, both refused on evidence and both blocked on a concurrent migration
outside this campaign's control, with their blockers re-verified at close. The
two originating findings this review flagged as unresolved -- registry-health
duplication and readiness duplication -- are still unresolved as duplications and
are now signposted rather than silent.

## Second addendum: the blocker re-check

The two Steps this review recorded as blocked were re-checked rather than
re-asserted, and one of them was blocked on a claim that was simply false.

**S27 is closed; both of its blockers were refuted.** The claim that `app modelo
readiness` refuses without a session where `config profile preflight` did not is
wrong: preflight reads the active profile record through `_read_profile_record`
and needs an unlocked session exactly as readiness does. The second blocker --
that preflight was too broken to compare -- assumed the comparison had to be a
runtime diff. It did not: `ModeloReadinessResult.missing` carries the same six
fields as the retired `ProfilePreflightMissingPayload`, over the same
`modelo_work_profile_preflight_report` gate, plus the registry, binding and
ledger axes preflight never had. Readiness is a superset, and the retirement was
safe.

Retiring the verb exposed a live defect in its replacement. `app modelo readiness
--revision-id` called the PEP 695 `RevisionId` alias as a constructor and raised
`TypeError` on every use. The flag had never worked, and the test that exercised
it asserted an exit code the handler cannot return for an unready profile, so its
failure read as expected noise. Both are fixed (S44).

The documented outcome changed truthfully rather than being preserved. Preflight
exited 0 for a fresh sandbox profile; readiness exits 2 there, because
`binding_ready` is false while four source bindings are unfilled. The goldens and
the guide now record that, and tell the operator to read the failing axis rather
than the overall verdict.

**S07 stays blocked, and the earlier characterisation understated it.** The
blocker is not that four packages happen to expose only `errors.py`; it is that
`application/export`, `adapters/outbound/google`, `application/storage/calc_sheets`
and `application/calculations` are documented re-export facades with 7, 20, 23
and 36 consumers. Retiring them is an 86-consumer relocation that
`aeat-architecture-boundaries` requires to land atomically, and peers are running
exactly that campaign now -- `relocation:` commits landed during this session.
Converting one caller cannot be done without either importing a private module
across a package boundary or opening the whole atomic move.

**The benchmark census stays blocked, and the blocking condition was observed,
not assumed.** The committed artifact is structurally outdated -- it predates the
`generator_digest` field the tool now requires -- so it needs a full re-capture,
not a content refresh. A capture snapshots the source tree and stamps a
`source_snapshot_digest`. During this session the registry tree changed under a
running loader twice within ten minutes, and peers rewrote source files
continuously; a multi-minute capture would invalidate its own digest. The
condition the earlier note called for -- an uncontended tree -- demonstrably does
not hold.

**Two findings this review left open are now resolved.** The readiness
duplication is gone: `app modelo readiness` is the single home for that question.
The registry-health duplication and the missing `config profile archive pull`
remain open by ruling.

**The show-to-view rename was only half swept.** S41 covered specs, handlers,
payloads, catalogues and prose; it did not cover the callers. Eleven
`*_view_help` keys were referenced by code and missing from all four catalogues,
six `*_show_help` keys were orphaned, 98 test invocations across 41 modules still
addressed the retired token, two envelope identity expectations still read
`.show`, and the `config storage` bootstrap-exempt subtree still declared it -- a
surface that fails open. All are closed (S43).

The locale gate did not surface the orphans on its own: `scaffold --check`
reported `extra=0` while ten unreferenced keys sat in the catalogues, and only
reclassified them once the replacement keys existed. A companion hazard: any bulk
locale verb (`remove`, `move-revision`) rewrites the shard from its own snapshot
and silently drops concurrent `set` values, so a catalogue edit must end with the
`set` pass rather than begin with it.

**One repair outside the campaign's own scope.** The plan document had lost rows
S36 to S42 while their execution records remained on disk, so a fresh `plan_edit`
reissued identifiers that already had records describing different work. The rows
were reconstructed from those records' own headings before any new work was
numbered.

## Third addendum: S35 is blocked too, on the same peer campaign as S07

The sequential full-suite pass was attempted and **aborted at collection**, not at
assertion. Seven modules fail to import, and pytest stops the whole run on the
first broken import, so no figure for the tree exists to report:

- `adapters/inbound/justificante/tests/test_corpus_sidecar_roundtrip.py`
- `adapters/inbound/justificante/tests/test_parser.py`
- `adapters/outbound/aeat/sede/tests/test_notifications_date_parsing.py`
- `application/aggregation/tests/test_source_resolver_enrollment.py`
- `application/calculations/tests/test_terminal_preconditions.py`
- `application/modelo/tests/test_workspace_assembly.py`
- `domain/portals/tests/test_terminal_preconditions.py`

Every one is peer-owned and mid-relocation. The failures name private modules
that no longer exist — `cadrumo.application.calculations._errors`,
`cadrumo.domain.portals._errors`,
`cadrumo.adapters.outbound.aeat.sede._notifications` — because those modules were
promoted to public names while their consumers still import the private path. A
sibling failure has the same cause read from the other end:
`Modelo100BorradorSourceResolver` is refused as "not publicly exported" because
it still lives in `application/modelo/_borrador_binding.py`.

This is the same facade-retirement campaign that blocks S07, observed from the
consumer side rather than the package side, and it confirms that campaign is
mid-flight rather than merely pending.

These were not repaired here. `aeat-architecture-boundaries` requires a
relocation to land its move and its consumer sweep in one commit, so the sweep
belongs to whoever opened the move; editing a half-landed relocation from outside
risks colliding with the in-progress half. The campaign's own area is unaffected
and collects cleanly: 1454 tests under `entrypoints/cli/`, no collection error.

The count of excluded-at-collection modules has therefore grown from three to
seven since the close review. S35 should be re-attempted once
`ls src/cadrumo/<pkg>/*.py | grep -v '/_'` shows public defining modules in the
four packages S07 names — the two Steps clear together.

## Fourth addendum: the suite checkpoint had to change method

The full-tree run the third addendum called for was attempted and does not work
in this worktree. Launched against roughly 28,000 tests with the six
peer-broken modules ignored, it produced **no output for fifty minutes and was
killed by its own timeout at 20 per cent**. It emitted no summary line, so it
yielded no figure at all. The cost is not the failure; it is that a run which
cannot finish also cannot be triaged, and repeating it would keep buying zero
information.

The checkpoint now runs in **bounded per-package slices**, each with its own
timeout and its own log on disk. The first slice proves the method: `core`
completed in five minutes with a real figure -- **2,234 passed, 19 failed**.

Every one of those 19 is peer-owned, and the two causes are the same
relocation campaign that blocks S07 and S35. Three `storage_liveness_gate`
claims name modules that no longer exist at the path claimed
(`adapters/persistence/operations/_journal.py`,
`application/auth/_acquisition_lock.py`,
`application/workflow/_persistence.py`) -- private modules promoted to public
names, with the claim not re-pointed in the same change. Nine
`source_connectivity` failures are a peer's removal of
`verify_connected_authority` from `SourceConnectivityCensusRow`. Neither touches
a CLI verb.

One process note worth carrying, because it wasted a slice. The first `core`
slice was piped through `tail -6`, which is exactly what
`aeat-local-execution` forbids: the truncation happens upstream of the read, so
fourteen of the nineteen `FAILED` lines never existed to be read, and the slice
had to be run again to get them. Write the full output to a file, then slice the
file.

## Fifth addendum: the decision-by-decision close review

The earlier addenda measure the campaign against its plan. This one asks the
question a reviewer inheriting the work asks first: is each decision of the
accepted ADR true of the TREE?

Seven decisions. Six hold. One did not, and it was the one nobody would have
found by reading the plan, because the plan recorded the change correctly and the
ADR did not.

**D5 forbade what shipped.** It states in five places that the whole-corpus Drive
mirror lives under a `mirror` subject, and says explicitly that it does NOT join
the `archive` subject, with a reason: "`archive` implies a thing you can restore,
and the mirror cannot be read back — putting it under `archive` would promise
recoverability that does not exist." The tree ships `config profile archive
push`. The operator ruled that change, the close audit recorded the ruling, and
the ADR was never amended — while carrying two other amendments in exactly the
right style. Its Rationale was still arguing for the option that lost. Amended at
S66; the amendment answers the original objection rather than overruling it, and
the superseded text is retained and marked.

**D1, D2, D3, D4, D6 and D7 hold**, each checked against the tree rather than the
plan. D7's four corrections were verified individually in the synced rule. D6's
exemption discipline was verified where it is easiest to skip: the spelling
gate's exemptions carry stated reasons and a stale one fails rather than
lingering to excuse a future parameter.

**One inaccuracy of this campaign's own making.** The S39 row and the second
addendum both call the verb-grammar gate "the gate D6 promised". D6 promises the
placement gate and the spelling gate. The verb-grammar gate enforces D2 and is
MORE than the record committed to — good work, wrongly attributed. Corrected on
the row.

**What the review does not establish.** The app-versus-config criterion recorded
at S60 — config establishes who the operator is and what the tool may use, app
does tax work and observes it — is prose in an execution record, not a gate. All
45 subjects the placement gate declines to judge conform to it today. Nothing
stops a future subject being mounted against it with no test going red. That is
the campaign's largest unenforced claim and it is stated here rather than left
implied.

## Sixth addendum: correcting the fifth

The fifth addendum closed by naming the campaign's "largest unenforced claim":
that the app-versus-config criterion is prose in an execution record, and that a
future subject could be mounted against it with nothing going red. The first half
is true of the criterion's wording. **The second half was overstated, and was
written without checking.**

`application/operator_surface/_contract.py` already declares every mounted family
as a `MountedCommandFamily`, and that model carries `root: RootSurfaceName` and
`operator_question: str` — the two fields a placement census would have had to
invent. Twenty families are declared, twelve `config` and eight `app`.

It is enforced in both directions.
`test_operator_surface_contract_covers_the_live_tree` is a symmetric-difference
assertion with no allowlist: a `root -> child` group mounted by the CLI but
absent from the contract fails, and so does a contract family with no live mount.
It carries an anti-vacuity floor against the lazy-Typer false-green vector. It
passes. So a new top-level family cannot be mounted without someone declaring its
root and the operator question it answers.

The residue is real but much narrower than claimed: the contract binds at
`root -> child` granularity (twenty families), while the criterion was judged over
sixty-five leaf subjects. A new subject nested inside an already-declared family
is not covered by the symmetric difference.

Recorded as its own addendum rather than by editing the fifth, so the
overstatement and its correction both stay readable. The lesson is the operator's
standing instruction: one semantic search for a subject-classification census
returned `_manifest.py` twice, before any code was written. Had the fifth
addendum stood, this campaign would have handed its successor a gate to build
that largely exists.

## Seventh addendum: correcting the sixth's description of the residue

The sixth addendum corrected the fifth's overstatement, then described the
remaining gap as "a new subject nested inside an already-declared family is not
covered by the symmetric difference", and proposed extending the contract to
per-subject granularity. Both parts are wrong.

**Structurally, a nested subject cannot be mis-rooted.** A subject's root is
`path[1]`. Verified over the live tree: all 65 subjects inherit their root from
their path, and none differs from its family's. `app ledger inventory` is under
`app` by construction. The placement decision therefore exists only at the family
level — which the symmetric-difference gate already enforces both ways.

**The proposed fix is one the codebase deliberately removed.**
`test_operator_surface_contract_covers_the_live_tree` states it in its own
docstring: the sub-verb half of the gate is gone because membership is now
derived from the live tree, "and asserting a derivation against the thing it
derives from would be tautological… which is the argument for deriving rather
than declaring, not for keeping the assertion". Re-adding per-subject
declaration would reintroduce precisely that, against a stated reason.

**The real residue is semantic.** A config-shaped concern can be nested inside an
app family — credential management under `app ledger` — and no symmetric
difference over names will see it, because the family is declared and the root is
inherited. That needs judgement, which is what S60 supplied and what none of the
gates proposed so far would replace.

Recorded as its own addendum rather than by editing the sixth, so the sequence
stays readable. The lesson generalises beyond this campaign: guidance a campaign
writes about itself decays exactly as an ADR does. Following this campaign's own
written next-step, one tick after writing it, would have produced work the
codebase had already rejected on stated grounds — and the only thing that caught
it was reading the gate before implementing against it.
