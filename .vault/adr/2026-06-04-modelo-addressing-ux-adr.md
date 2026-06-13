---
tags:
  - '#adr'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-modelo-addressing-ux-research]]'
  - '[[2026-06-03-cli-workflow-redesign-epic-adr]]'
  - '[[2026-06-04-cli-workflow-redesign-epic-research]]'
---

# `modelo-addressing-ux` adr: `natural-key modelo work addressing` | (**status:** `accepted`)

## Problem Statement

The modelo work CLI currently exposes internal content-addressed handles
as the ordinary operator workflow. A basic filing path asks the operator
to copy a `work_unit_id`, then a `calculation_revision_id`, then return
to the `work_unit_id` for export. Both IDs have the same opaque
64-character digest shape while representing different lifecycle objects.
This makes the CLI operating surface dependent on the user's ability to
remember internal taxonomy rather than on the facts of the filing.

The principal directive for this ADR is technical load offloading from
the user. The internal architecture can remain content-addressed and
auditable, but the operator must not be required to route opaque IDs
through the common workflow. The common CLI path must address a filing by
facts the operator already knows: active profile, modelo, filing year,
and filing period.

The design must also handle the failure case where a user starts the same
visible filing twice. The CLI must not silently create two active
same-period workspaces just because the underlying registry revision or
another internal discriminator differs. Duplicate prevention must happen
at the user-visible filing target before the engine creates or selects an
internal exact target.

## Considerations

The existing domain distinction is valid and should be preserved. A
`WorkUnit` is the stable filing workspace. A `CalculationRevision` is one
immutable calculation attempt inside that workspace. Multiple calculation
revisions can exist under one work unit, and recalculation creates or
reuses a revision rather than mutating prior calculation history.

The work unit already carries pointer fields that can support default
operation: `current_calculation_revision_id`,
`filed_calculation_revision_id`, and `current_filing_record_id`. These
fields are the right place to represent the current draft or verified
calculation, the current filed answer, and the current filing record for
normal command defaults.

Current storage derives work-unit identity from `bucket_id`, `modelo`,
`filing_year`, `period`, and `revision_id`. This is the internal exact
target. It is not the operator-facing target. The registry revision is
resolved by the system and is only exposed when needed for
disambiguation, historical inspection, or exact replay.

Current code confirms that `causante_ccaa` is carried on work units but
does not participate in work-unit identity. It must therefore remain
display or calculation context, not a filing-target discriminator. If a
jurisdiction axis later becomes legally part of distinct filing identity,
that axis must be promoted by a separate ADR and storage decision before
the CLI treats it as an addressing dimension.

Current command behavior is only partially aligned with the desired
model. `work create` resolves a registry revision when omitted and reuses
an existing exact work unit. Calculation persistence advances
`current_calculation_revision_id` only when a new calculation revision is
persisted; returning an existing duplicate revision currently does not
necessarily update the current pointer. Verification updates the
calculation revision state, not the work unit current pointer. Filing
updates filed pointers, not the current calculation pointer. These facts
must be reflected in the command-default contract rather than hidden
behind a vague "latest" rule.

## Constraints

Internal content-addressed IDs must remain authoritative for storage,
audit, replay, and machine consumers. This ADR demotes raw IDs from the
ordinary CLI path; it does not remove them.

The resolver must first reason about the operator-facing filing target:
active bucket, modelo, filing year, and period. Only after that visible
target is known to be absent or unambiguous may it resolve or use the
internal exact target that includes registry revision.

The CLI must not silently create a second non-discarded active work unit
for the same visible filing target. Starting, creating, calculating,
verifying, filing, or exporting the same modelo/year/period again must
reuse the existing active work unit or refuse ambiguity.

The CLI must not silently operate on a different registry revision when
an active visible-target work unit already exists. If the operator
supplies `--revision` and the single active visible-target work unit uses
a different registry revision, the command must refuse and explain the
conflict rather than create a parallel workspace.

Ambiguity must refuse, not guess. When multiple non-discarded work units
match the same visible filing target, the CLI must list candidates with
human-readable fields such as modelo, year, period, registry revision
label, state, current revision state, filed state, creation time, and a
short ID suffix. It may then accept an explicit selector or raw ID.

Discarded or superseded history must be retained for audit but must never
be selected by default. Accessing historical work requires an explicit
selector or explicit ID.

Revision defaults are command-specific. A global "latest" rule is unsafe
because `calculate`, `verify`, `file`, and `export` require different
lifecycle states.

Tests for this work must be real-behavior CLI or application tests over
isolated storage. They must not mirror resolver logic with fakes, mocks,
stubs, monkeypatches, `skip`, or `xfail`.

## Implementation

The accepted model is:

- one active work unit per operator-facing filing target;
- one internal exact target per active work unit;
- many immutable calculation revisions under that work unit;
- at most one current filed answer, with older filed answers retained as
  superseded history;
- explicit selection when more than one candidate exists;
- raw IDs retained as advanced escape hatches.

The operator-facing filing target is:

`active profile or bucket + modelo + filing year + filing period`

The internal exact target is:

`operator-facing filing target + resolved registry revision`

Future axes may be added only when they alter legal filing identity and
are promoted into both storage identity and CLI disambiguation by an ADR.
Until then, axes such as `causante_ccaa` are context fields, not default
addressing fields.

Resolution must live at an application selector boundary, not as
command-local CLI string handling. That boundary should expose typed
operations for selecting a work unit, selecting a calculation revision,
and reporting ambiguity. The CLI should render those typed outcomes into
plain operator guidance.

Work-unit resolution must follow this order:

1. Resolve the active profile to the active bucket unless the command
   explicitly accepts and receives a bucket override.
2. If an explicit `work_unit_id` is provided, load it and validate that
   any supplied natural-key flags do not contradict it.
3. If no explicit work-unit ID is provided, search non-discarded work
   units by the visible target: bucket, modelo, filing year, and period.
4. If no visible-target work unit exists, resolve the registry revision
   and create or reuse the internal exact work unit.
5. If exactly one visible-target work unit exists, resume or reuse it.
   If `--revision` was supplied and conflicts with that work unit, refuse
   and show both the requested revision and the existing active work
   unit.
6. If multiple visible-target work units exist, refuse ambiguity and list
   candidates. The user must choose through an explicit selector, exact
   revision label, or raw ID.
7. Discarded work units are excluded from default resolution. They are
   available only through explicit history/listing flows.

`work create`, or any future `work start` spelling, must be idempotent on
the visible filing target. If an active visible-target work unit exists,
the command returns or resumes it and says so plainly. If none exists,
the command creates one using the currently resolved registry revision.
If multiple candidates exist, it refuses and lists them. This command is
part of the first implementation slice because the user's duplicate-draft
failure begins at provisioning.

`work calculate` must target the active work unit by natural key. It
creates a new calculation revision under that work unit or returns an
existing duplicate revision if the content-addressed calculation already
exists. When the resulting revision is draft/current-eligible, the work
unit's `current_calculation_revision_id` must point to that revision
before the command completes. If the duplicate revision is no longer a
draft/current-eligible revision, the CLI must not pretend a new draft was
created; it must explain that no draft revision was advanced and guide
the operator to verify, file, export, recalculate with changed inputs, or
select explicitly.

`work verify` must default to `--select current`. The command may proceed
only when `current_calculation_revision_id` resolves to a draft
calculation revision under the selected work unit. If current is missing,
filed, superseded, verified, or otherwise not draft, verification must
refuse and explain the acceptable selectors.

`work file` must default to the current verified-complete calculation
revision. It may proceed only when `current_calculation_revision_id`
points to a `verificado_completo` revision under the selected work unit.
It must not file an arbitrary latest draft or an old verified revision.
If the current revision is still draft, the CLI should tell the operator
to run verification first. If the operator intends to file a different
verified revision, that must be explicit.

`modelo export` must avoid arbitrary latest selection. The default order
is:

1. export `filed_calculation_revision_id` when it points to the current
   filed answer;
2. otherwise export `current_calculation_revision_id` when it is
   `verificado_completo`;
3. otherwise, for legacy or recovery cases only, export the single
   unambiguous verified-complete revision if no current draft conflicts;
4. otherwise refuse and list available selectors.

The export command must never select superseded filed revisions,
discarded work, or an unrelated latest draft by default.

Revision switching is explicit and stateless. Accepted selectors should
include:

- `--select current`;
- `--select latest-draft`;
- `--select latest-verified`;
- `--select filed`;
- explicit `calculation_revision_id` for advanced exact replay.

A persistent `work use` command is not part of the accepted first design.
It adds hidden state that works against the principal directive. If a
future workflow proves it necessary, it requires a separate decision and
must still render the selected target clearly on every mutating command.

Read-only discovery is required for the first slice. The CLI must provide
operators a way to list and inspect work units and calculation revisions
for a natural target without knowing raw IDs. At minimum, the surface
must expose current revision, latest draft, latest verified revision,
filed revision, work-unit state, registry revision label, and enough
short identifiers to support support/debug workflows.

The first implementation slice therefore includes natural-key addressing
for provisioning, calculation, verification, filing where present, and
export, plus read-only list/status/revisions discovery. Documentation
must not switch tutorials to the new flow until these commands are backed
by real-behavior tests proving that the basic Modelo 130 path can run
without manually copying a `work_unit_id` or `calculation_revision_id`.

## Rationale

The research and code discovery show that the tutorial pain is not only
the presence of opaque IDs. The deeper issue is that the CLI currently
makes the operator maintain internal object identity, lifecycle state,
and current-pointer meaning in their head. That is the work the system
must take over.

Separating the visible filing target from the internal exact target
prevents a subtle duplicate-workspace failure. If the registry revision
is treated as part of the ordinary user target, then a same modelo/year
period can split into parallel active work units without looking
different to the operator. The resolver must therefore scan by the
visible target before exact revision creation.

Keeping one active work unit per visible filing target gives the operator
a stable workspace while preserving multiple immutable calculation
revisions for audit. This reconciles the UX requirement with the
content-addressed persistence model.

Command-specific defaults encode lifecycle safety. `verify` needs a
draft, `file` needs the current verified-complete revision, and `export`
needs the current filed or verified-complete answer. A single "latest"
selector cannot express those safety requirements.

Stateless selectors keep the operating surface transparent. A hidden
session-wide `work use` target would reduce typing but increase the risk
that a later command acts on state the operator cannot see.

## Consequences

The common workflow becomes: "work on Modelo 130 for 2026 1T" rather
than "copy one digest, then another digest, then remember which digest
belongs to which verb." This directly satisfies the ADR's principal
directive by moving technical load from the operator to the resolver.

The application gains a shared selector boundary whose behavior is now a
product contract. Ambiguity rendering, state validation, and candidate
listing must be maintained as first-class UX behavior, not incidental
error output.

Existing internal IDs remain available and authoritative. Machine
consumers, audit workflows, replay workflows, and support investigations
can still use exact IDs.

The implementation must close current-pointer gaps. In particular,
duplicate calculation persistence and verification/file/export defaults
must not leave the user believing one revision is current while the
system later operates on another.

The design intentionally excludes hidden persistent work selection from
the first slice. That keeps the initial operating model stateless and
easier to explain, at the cost of requiring explicit natural-key flags or
selectors on commands.

Future legally meaningful axes have a clear path: promote the axis into
storage identity and resolver disambiguation by ADR, then update the CLI
candidate listing and tests. Until then, display/context fields must not
silently split active workspaces.

## Codification candidates

- **Rule slug:** `modelo-work-visible-target-first`.
  **Rule:** Modelo work CLI resolution MUST search active work units by
  visible filing target before creating or selecting an internal
  revision-specific work unit.

- **Rule slug:** `modelo-work-no-parallel-active-workspaces`.
  **Rule:** Modelo work CLI commands MUST NOT silently create or operate
  across parallel non-discarded work units for the same visible filing
  target; they must reuse one active work unit or refuse ambiguity.

- **Rule slug:** `modelo-work-command-specific-revision-defaults`.
  **Rule:** Modelo work CLI commands MUST use lifecycle-specific revision
  defaults for calculate, verify, file, and export instead of a generic
  latest revision rule.
