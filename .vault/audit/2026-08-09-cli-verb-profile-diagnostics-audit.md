---
tags:
  - '#audit'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:49dbf938a3d07d417efbef827290ef772a130b5dde985777497d8e527ff1c162'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# `cli-verb-profile-diagnostics` audit: `Fresh-context honesty review`

## Scope

Read back the plan, the ADR, the reference inventory and all twenty-four Step
Records as if inheriting them cold, and verified every claim against the code
as it stands rather than against the prose that described it.

## Findings

### The original inventory was incomplete, twice, in the same way

Two in-scope refusal sites were missed by the first inventory pass and found
only by this review. Both are recorded as their own Phases with their own Steps
rather than folded into closed ones.

The undeclared-taxpayer-model refusal sits within a few lines of the
completeness refusal on all three overview verbs, and is the same defect class
on the same verbs. The inventory recorded one and walked past the other.

The modelo export declarant-identity refusal passed raw dotted paths, plus
Python container punctuation, into a filing-grade operator message. It was
outside both the CLI tree and the site list in the initiating brief, so nothing
in the first pass would have reached it.

The common cause is that the inventory was scoped by LOCATION - the CLI tree
plus a supplied list - rather than by BEHAVIOUR. The sweep that actually found
both was reading the locale catalogue for operator-facing messages that
interpolate a missing-field list. That sweep should have been run to completion
before the plan was written, and it is the durable lesson here.

### One test asserted the defect as the contract

An attribution-entity test asserted that a raw row-indexed path appears in a
readiness refusal. That is precisely the behaviour this work exists to remove.
It was corrected to assert the schema-derived label rather than worked around,
and now derives its expectation from the schema so it cannot pin one spelling.

A second test pinned the export refusal's raw-path context exactly, and was
corrected the same way.

### Coverage is narrower than the Step titles imply, in one place

The overview Steps are titled as routing three verbs through the enrichment
helper, and they do. But no test drives an unanswered PROFILE field through a
real CLI refusal end to end, because the calendar fixture's profile answers
every gating field and its only warning is a non-profile code. The enrichment
is covered against real data at the function level, and the pass-through branch
IS covered end to end, but the headline path is not.

This is recorded in the relevant Step Record rather than left implied. It needs
a calendar fixture whose profile omits a gating field.

Similarly, the agenda and backlog refusals are covered by construction only:
they call the same builder on the same line shape as the calendar, and do not
warn under the available fixture.

### A claimed Step deliverable was a no-op

The facade-promotion Step closed with no code change, because the resolver was
implemented as a method on an already-exported class. Recorded explicitly in
its Step Record, since a closed row with no diff is otherwise
indistinguishable from skipped work.

### Verdicts were not flipped

Checked directly rather than assumed. Every refusal condition in scope is
byte-for-byte what it was: the overview conditions still read `warnings and not
allow_incomplete`, the undeclared-model predicate lives in the domain layer and
was not touched, the export branches trigger on the same absent facts, and the
diagnostics check's missing-key set is still decided upstream. The standing
deferral on the three readiness surfaces is intact - only the diagnostics
surface's rendering changed, not its verdict.

### A red region in the tree is not owned by this work

The application modelo suite carries eleven failures raising
`NoRevisionForPeriodError` for Modelo 200, filing year 2024. The committed
Modelo 200 revision declares `period_selector = { year_from = 2025 }`, so the
year the tests request genuinely has no revision. Nothing in this work touches
the registry modelo tree or revision selection. This is peer work in flight and
is reported as inventory, not absorbed.

The twelfth failure in that suite WAS in scope and was fixed, as recorded above.

The import-hygiene test-debt gate is likewise red, on a peer's new calendar
payload test reaching `OverviewCalendarEventType` from a private module without
a matching debt entry. Checked specifically because this work added three test
modules that reach private symbols: all three reach INTO THEIR OWN package,
which the boundaries rule permits and this gate does not count, and none appears
in the gate's output. An earlier draft did reach across packages and was moved
to the owning package rather than allowlisted.

## Recommendations

1. **Build a calendar fixture whose profile omits a gating field**, and extend
   the overview refusal tests to drive a profile field through a real CLI
   refusal end to end for all three verbs. This is the one coverage gap this
   work knowingly leaves open.
2. **Sweep the remaining locale-catalogue candidates** this review surfaced but
   did not action: the wizard status refusal naming `tax.id` in prose, and the
   export-no-profile message hard-coding two field paths into its sentence.
   Both are the same defect class and neither was in the plan.
3. **Scope the next inventory by behaviour, not location.** The locale
   catalogue is the closest thing this repository has to a census of
   operator-facing messages, and reading it to completion is cheap relative to
   discovering the gap after the plan is closed.

## Context

The known-wrong `orden-hac-1347-2024:art-4` citation on the Modelo 100
declarant-identity cluster was deliberately not touched, per its own audit. It
is worth restating that this work INCREASES that defect's visibility: several
refusals now surface a field's `legal_refs` where they previously surfaced a
raw identifier, so an operator refused on one of those fields will now read the
wrong citation. That is correct behaviour for this mechanism, which reports
what the registry carries, and it raises rather than lowers the value of fixing
the citation.

## Second review pass (Phases P07 through P14)

### The campaign's own enrichment was a silent no-op at two sites

The most serious finding of this pass, and it was in THIS campaign's own
delivered work rather than in pre-existing code.

Registry bindings name the profile fact they consume by its `section.field`
PATH. The deadline engine's completeness gate names its fields by their
declared `model_selectors` TOKEN. These are different namespaces. Two surfaces
delivered earlier - the modelo requires warning and, initially, the date-binding
calculate guidance - hold BINDING keys and were routed through the SELECTOR
renderer, which resolved nothing and passed every key through unchanged.

Both Steps were recorded as delivered, both had tests, and both tests passed.
They passed because they asserted the output was not the BINDING ID. Under the
no-op the output was the profile KEY, which satisfies that assertion while
still being a raw identifier - the exact defect the work exists to remove, one
layer along.

It was caught by a mutation probe that DID NOT FAIL. Disabling the enrichment
entirely left the test green, which is the signal that the assertion was not
measuring the enrichment at all. The correction adds a path-based renderer, a
test that the wrong renderer leaves a binding key raw, and assertions that name
what the output must BE rather than what it must not be.

**Generalised lesson:** an assertion that output is not one specific wrong value
does not establish it is the right value. This is the second time in this
campaign that a test asserting an absence passed against broken code.

### The catalogue census replaced eye-scanning and found four more sites

The first pass's closing sweep was a read-through of grep output. This pass ran
a programmatic census instead: every schema path and selector token from the
loaded schema, checked against every string in all four catalogues. It found
four further refusals embedding an identifier - two live-auth, two Cl@ve
credential - that the earlier eye-scan had passed over.

The census now reports three remaining hits, all in
`cli.config.get`/`cli.config.set` option help, which show example keys the
operator literally types as arguments. Those are correct and are not defects.

### A concurrent author is working in the same plan

Phase `P11` and its Steps `S43` and `S44` were authored by someone else during
this session. Two consequences were handled rather than absorbed silently.

Two Steps of this pass were initially created under that author's Phase, because
the phase id was assumed rather than read back from the CLI. They were
re-parented to their own Phase; nothing of the other author's was modified.

Their `S43` was verified rather than trusted: its implementation is complete and
its renderer choice is CORRECT, since the tokens it passes are genuinely declared
selectors. It is left open for its author. Its adjacent process-metadata defect,
which `S43` does not cover, was fixed separately under `P14`.

### Verdicts remain unflipped

Re-checked across every Phase in this pass. The overview conditions, the Cl@ve
route guards, the export branches and the wizard tax-identifier check are all
byte-for-byte what they were. Only message text and channel changed.

## Remaining open items

1. **`P11.S43` and `P11.S44` belong to a concurrent author** and are left open.
   `S43`'s substance is verified complete; `S44` is the terminal re-verification,
   whose substance this pass ran.
2. **The plan reports a non-monotonic Step ordering warning**, which is the
   documented insert-between case: Steps re-parented out of another author's
   Phase now sit after higher-numbered rows. It reflects intent, not a hand-edit.

## Terminal verification (run after every Phase through P14 landed)

Owner surface, every module this campaign created or edited:

    uv run --no-sync pytest <owner surface> -m "unit or integration" -n 0 -q
    691 passed in 171.12s (0:02:51)

Zero failures and zero skips.

Broad affected tree:

    uv run --no-sync pytest <affected tree> -m "unit or integration" -n 0 -q
    68 failed, 7548 passed, 1 warning in 2749.95s (0:45:49)

Every failure was triaged against the owner surface and none belongs to this
work. Beyond the categories recorded in the first pass, this run surfaced three
modules the earlier run's narrower selection did not reach, and each was
re-checked in isolation rather than assumed:

- The help-without-secrets module PASSES in isolation. Its failures in the broad
  run are ordering pollution from earlier tests in the same session, not a
  defect this work introduced.
- The wizard descendant-door failures reproduce in isolation, and their
  traceback terminates entirely inside the scripted-flow answer handling. That
  is a peer's in-flight descendant-door feature, matching the descendiente
  entry-surface failures in the same run.
- The recovery-lifecycle failures sit in a surface this work adds nothing to.

Locale parity across all four catalogues: clean.

A behavioural probe over every grounded surface confirms zero raw-identifier
leaks: each of the seven distinct selector tokens and paths this work routes
renders as an operator label, most with legal grounding attached.

## Campaign status

**Complete.** All 49 Steps across 14 Phases are closed, each with a Step Record.

`P11.S43` and `P11.S44` were authored by a concurrent author. `S43` was verified
rather than trusted - its implementation and its renderer choice are correct -
and its author closed it. `S44`, the terminal re-verification, was held open
through two reports so its author could close it, and was closed only after
they closed `S43` and left it, at which point leaving it open would have
misrepresented a verification that had in fact run.

Final re-certification against the tree after every Phase had landed:

    uv run --no-sync pytest <owner surface> -m "unit or integration" -n 0 -q
    691 passed in 177.65s (0:02:57)

Zero failures, zero skips, locale parity clean, zero raw-identifier leaks.

One incident is recorded in that Step's own record: a combined run aborted at
collection on a peer facade re-exporting a symbol its module did not define.
The symbol remains absent, yet the identical selection later collected and
passed, because that facade resolves lazily - so the failure window was the
peer's file being mid-write, not a persistent broken state. Splitting the run
into three subsets during the incident produced counts summing to exactly the
combined total, which is what established the blockage was transient rather
than masking a failure.

## Third review pass (S44 re-execution, P15 and P16)

Run at the team lead's direction as a genuine re-execution of the terminal gate
rather than a restatement of earlier runs.

### The class both prior reviews declared unmeasured is now measured

Both concurrent honesty reviews named the same blind spot in the same words: a
message naming a profile field in prose, with no dotted identifier, could not be
found by any census run so far, because all of them keyed on dotted tokens.

A behaviour-scoped census closed it - every catalogue string carrying an
instruction verb together with a profile noun, regardless of identifier shape.
**59 profile-instruction messages: 22 carry a placeholder, 0 carry a raw dotted
identifier, 37 name things in prose only.** The zero is the campaign's central
claim, now measured by a method that does not presuppose the defect's shape.

Of the 37, the large majority correctly name no field: storage-integrity errors,
help text, and messages naming environment variables or CLI flags the operator
types literally. Three name a field or assert one is missing, and each is
dispositioned in its own Step.

### Two dispositions recorded rather than actioned

The two censal fiscal-ID refusals were deliberately NOT grounded. The mechanism
would render that field with its registry citations, and those include the
known-wrong módulos citation this campaign is instructed to leave alone. Where a
refusal previously showed a raw path, grounding was a clear gain even carrying
that citation, because a raw path is unusable; where the prose is already
actionable, spreading the citation is the dominant effect. Recorded explicitly so
a later reader does not "finish the job", and correct as soon as the citation is
fixed.

The registered profile-preflight-missing error carries an unactionable message
and has **zero raise sites** anywhere in the tree. Recorded rather than fixed:
grounding a message nothing can emit has no observable effect, and deleting the
class reaches into the error registry, a different surface from operator-facing
refusal text.

### The campaign introduced an architecture regression, caught only by the full run

The date-binding resolution added two registry-authority reads to the legacy
modelo CLI root, which an architecture gate budgets at exactly zero. The gate
failed with `assert 2 <= 0`.

Every narrower verification this campaign ran passed, because none of them
included that gate. This is the same structural failure the earlier reviews
identified for the verification Phase, in a different guise: a check that does
not include a constraint cannot report on it.

Fixed the way the gate asked - the resolution moved into the application layer,
where the binding definitions already live, and the CLI root kept only the
addressing. The budget is satisfied at its intended value rather than relaxed.
The owner-surface run now includes the architecture gate, which is the change
that stops this recurring.

### Transient peer state produced two phantom failure sets

Two combined runs reported failures that did not reproduce in isolation: a
collection-blocking ImportError on a peer facade mid-write, and schema and
custody failures that passed cleanly when re-run alone. Both were peers editing
registry and calculation files during the run. Each was re-run in isolation
before being triaged rather than being reported as a regression.
