---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:9b46e4db7c59d3c67b7285b48f4229d6e45f949148b76098616319b209d3edcd'
step_id: 'S409'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give Home's actions, resumable declarations, agenda, evidence and messages zones their installed readers. All five are hard-coded UNAVAILABLE in the secure generation input, so the production Home an operator meets is five refusals and a Ledger summary. The application authorities the accepted due-driven decision names -- next actions, backlog, agenda, calendar evidence, notification snapshots -- exist and nothing yet calls them.

## Scope

- `src/cadrumo/application/workbench_generation.py`

## Changes

- `M` `src/cadrumo/application/workbench_generation.py`
- `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `verify:` `pytest -n0 -m '' application/tests/test_workbench_generation.py tui/tests/test_home.py` -> `pass` (23)

## Notes

Step left OPEN: two of Home's six zones are now wired, four remain refused.

Landed. The AGENDA zone reads the real overview agenda, and the LEDGER zone now
reads the Ledger workspace projection the generation door already builds --
`_read_ledger` ran and its result was discarded on the way to Home, which is
what "nothing yet calls them" meant here: the authority was not missing, the
call was.

The interesting part is the refusal rule rather than the wiring.
`LedgerWorkspaceAreaStateV1.item_count` is a plain integer, so an area nobody
measured reports 0 -- the same value a genuinely empty area reports. The Ledger
workspace keeps those apart through `status` and renders UNMEASURED as
"Sin medir" rather than a digit. Home has no such room: its readiness block is
four bare numbers, and a zero there reads as a finding. So the block refuses
when ANY of its four areas is unmeasured rather than publishing three real
counts beside one fabricated one -- partial truth in a summary is
indistinguishable from whole truth once rendered.

Teeth proven by accepting unmeasured areas: `an unmeasured entries area still
produced a readiness block, so Home renders a zero nobody measured`. Restored
by copy and verified.

Remaining and NOT done: actions, resumable declarations and messages. All
three were measured rather than re-labelled, and they are blocked for three
DIFFERENT reasons, which one word was hiding.

ACTIONS -- PARTLY WIRED, and the taxonomy label was wrong in the same way the
declarations one was. Original note follows.

Home declares six reason codes and they are not arbitrary: three of them name
work the door already measures. `ledger_classification_pending` and
`evidence_missing` are now offered from the Ledger workspace's CLASSIFICATION
and EVIDENCE areas, each paired with a catalogue action that takes no
arguments, so nothing was invented to make the zone fill. Ordering is declared
rather than incidental: classification first, because an unclassified entry has
no settled tax treatment, while a missing justificante is a gap in evidence for
a treatment already chosen.

The refusal rule is the same one the readiness block uses. An UNMEASURED area
yields NO action rather than an action for zero items, because `item_count` is
a plain integer and an unmeasured area reports the same zero a finished one
does -- offering "classify 0 entries" sends the operator to an empty screen and
calls it a task.

Gated by `test_home_offers_ledger_work_only_when_there_is_some_and_never_for_an_unmeasured_area`,
which also asserts every offered reason code resolves in the catalogue: a code
without copy renders Home's degraded generic line, so an invented action would
arrive unreadable. Teeth proven by offering work for unmeasured and empty
areas. Restored by copy; 26 passed.

The declaration-addressed action is wired too, and the shape objection was
another thing that dissolved on inspection: `operator.modelo.work.revisions`
takes a `work_unit_id`, which the resume already carries, so no id taking
modelo/year/period was needed at all. Listing a work unit's calculation
revisions is precisely what `declaration_needs_review` asks the operator to do.
The address rides on the action row rather than in the arguments, which is what
Home renders beside it.

Only NEEDS_REVIEW declarations are offered. A verified, filed, draft or
discarded one is not outstanding work, and offering it would make the zone a
list of everything rather than a list of what is left. Addressed actions rank
ahead of the cross-cutting Ledger offers, because each names a single
declaration the operator can finish while "classify the ledger" is spread
across every record.

Gated by `test_a_declaration_needing_review_is_offered_with_its_own_address`,
which asserts the address is present -- a reason without one is advice rather
than a task -- and that exactly one of five declaration states is offered.
Teeth proven by offering every declaration: the gate reports all five.
Restored by copy; 27 passed.

STILL NOT WIRED: the three `blocked_*` reason codes. Measured rather than
asserted this time, and the earlier phrasing was wrong in the usual direction.

There IS a source. `VerificationCompletenessStatus.BLOCKED` is a real domain
state, forced by findings of BLOCKING severity, and
`VerificationReportCatalogueRepository` is a concrete adapter taking a
`bucket_id` -- the same shape as every repository the door already composes,
not buried in an entrypoint the way the notification custody factory is. So
"no source" was false.

What is genuinely missing is the mapping, and only for two of the three.
`ModeloVerificationFindingKind` declares MISSING_REQUIRED_CASILLA,
RECONCILIATION_MISMATCH, CROSS_PERIOD_DEPENDENCY_UNCLEAN, BLOCKING_RULE and
ADVISORY. Exactly one reads across cleanly:
CROSS_PERIOD_DEPENDENCY_UNCLEAN is `blocked_dependency` by its own name.
Nothing in that enum names evidence, so `blocked_evidence` has no source at
all; and `blocked_review` would have to claim either BLOCKING_RULE or
MISSING_REQUIRED_CASILLA on no better grounds than that something must map
there. Those two would be invented, which is what the reason-code gate exists
to prevent.

So the next slice has a known shape: add the verification repository to the
door as an optional dependency, extend the capture-coherence guard to cover the
new read, and offer `blocked_dependency` alone from a
CROSS_PERIOD_DEPENDENCY_UNCLEAN blocking finding -- leaving the other two codes
unproduced rather than guessed. Not started here rather than left half-applied
with the guard inconsistent.

ORIGINAL NOTE, kept because the caution was wrong: blocked on a taxonomy
decision. `HomeNextAction` is built only by
the fixture; the authority the plan names, `build_overview_status_next_steps`,
emits `OverviewStatusNextStepId` values (CREATE_PROFILE, IMPORT_TRANSACTIONS,
REPAIR_STORAGE) which are `overview status` CLI guidance, not Home's task
vocabulary. Home resolves `tui.home.reason.<code>` and declares six codes, all
about declaration review, ledger classification and evidence. Bridging the two
means deciding what Home's actions zone MEANS and minting reason codes plus
copy for it; guessing renders the degraded generic line the fixture gate now
catches.

DECLARATIONS -- WIRED. The "blocked on a decision" label was too cautious, and
re-measuring it is what unblocked it. Original note follows for the record.

The mapping is not an invention: `CalculationRevisionState` names its own
meanings. `VERIFICADO_COMPLETO` says verified and complete, which is the only
thing READY can honestly mean; `BORRADOR` is a calculation that exists and has
not been verified, which is exactly NEEDS_REVIEW; both PRESENTADO forms are
filed; DESCARTADO is discarded. A work unit with no calculation at all is
DRAFT, because there is nothing yet to review or file.

It errs safe in the one direction that matters. Nothing reaches READY except
the state whose name asserts verification, so the failure mode -- telling an
operator a declaration is ready to file when nobody verified it -- cannot be
reached by inference. The display name comes from `WorkUnit.name`, and a
declaration naming a work unit this session did not load refuses the whole zone
rather than inventing a label.

Gated by `test_only_a_verified_calculation_reads_as_ready_on_home`, which
asserts the WHOLE table is declared -- so a new calculation state cannot be
added and silently default -- and that READY has exactly one source. Teeth
proven by mapping BORRADOR to READY: the gate names both offenders. Restored by
copy; 25 passed.

ORIGINAL NOTE, kept because the caution was wrong and the reason is worth
seeing: blocked on a state mapping. The join itself is available: the
ref lacks a display name but `WorkUnit.name` has one and the door already holds
the catalogue, so the earlier note calling this blocked on a missing name was
half wrong. What is genuinely missing is the mapping. `WorkUnitState` has two
values (BORRADOR, DESCARTADO) and `HomeDeclarationState` has five; FILED and
DISCARDED fall out of facts the projection carries, but READY versus
NEEDS_REVIEW needs a grounded rule over `CalculationRevisionState`. Telling an
operator a declaration is READY when it needs review is a filing-grade harm, so
this refuses rather than guesses.

MESSAGES -- still awaiting a pull, but its refusal now names the real
condition. `PersistedNotificationsSnapshot` is the record of an AEAT
notifications capture, so before any pull the reader is perfectly able to
answer and the DATA is what is absent. The zone reported UNAVAILABLE with the
reason `messages_reader_unavailable`, which named the wrong thing twice: an
operator reading that looks for a broken reader, when the action that resolves
the zone is a pull. It now reports NEVER_CAPTURED with
`messages_never_pulled`, a state Home already has copy for.

Gated by `test_a_zone_awaiting_a_pull_is_never_captured_not_unavailable`, which
asserts the reason CODE as well as the availability: a zone carrying the right
state under a code that still blames the reader tells the wrong story wherever
that code is rendered or logged. Teeth proven by restoring the old refusal --
`Home reports never-pulled AEAT notifications as an unavailable reader, which
points the operator at a fault instead of at the pull`. Restored by copy and
verified; 24 passed.
