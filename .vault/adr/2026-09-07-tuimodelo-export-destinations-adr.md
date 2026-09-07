---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:12241a1cc24545b9abf2751029d4c1b9d435e1c17d0e112a286eef9bf663f93f'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tuimodelo` adr: `export destinations and import surfaces` | (**status:** `proposed`)

## Problem Statement

Everything that moves a declaration into or out of the product lacks a shared contract.
On the outbound side there is no destination abstraction of any kind — no port, no target
enum, no registry — and every verb hardcodes one transport
(`2026-09-07-tuimodelo-reference`). On the inbound side the operation registry enrols zero
import operations out of twenty definitions, so every import bypasses the journal, lease,
cancellation and secure-request machinery that governs every other frontend-triggered
mutation.

The campaign brief asks for an export surface with many targets and for import and
binding-import surfaces. Neither can be built as a frontend feature: a surface that offered
a choice of destinations would be inventing the vocabulary the backend lacks, and a surface
that offered import would be driving application functions the supervisor does not know
about. A decision is needed now because both the export wave and the import wave depend on
contracts that do not yet exist, and because two live correctness defects in this area
would otherwise be wired into the product.

## Considerations

- No destination or target abstraction exists; the word "destination" is already taken
  inside the frontend for screen routing, which is a naming hazard for any new vocabulary
  (`2026-09-07-tuimodelo-reference`).
- The export operation available to the frontend drops the elections the command line
  threads, so the two surfaces can emit different declaration types for the same modelo
  (`2026-09-07-tuimodelo-reference`).
- An offline workbook exporter is fully built and styled with zero production callers
  (`2026-09-07-tuimodelo-reference`).
- A preview seam already exists: the export draft path overloads on destination, with a
  payload-consumer arm currently used only by export proof
  (`2026-09-07-tuimodelo-reference`).
- Layout coverage is 94 layouts across 47 of 58 modelos, is measured per revision rather
  than per modelo, and completeness manifests exist for only 34, so many exports report
  completeness as unverified (`2026-09-07-tuimodelo-reference`).
- No golden byte fixtures exist on disk and the canonical live proof roster is empty
  (`2026-09-07-tuimodelo-reference`).
- An existing output file is silently overwritten, and the output-path docstring
  contradicts its own validator (`2026-09-07-tuimodelo-reference`).
- Interactive authorization for the one remote destination refuses a non-terminal host and
  blocks a loopback receiver for up to five minutes, so a full-screen surface cannot host
  it in-process (`2026-09-07-tuimodelo-reference`).
- Two importers carry real logic inside command handlers with no application service, so no
  second surface can reach them (`2026-09-07-tuimodelo-reference`).
- The ledger side already has the contracts the modelo side lacks: a dry-run flag on the
  import command and a per-item typed batch result (`2026-09-07-tuimodelo-reference`).
- Binding definitions are read-only shipped package data with no runtime write path, so
  importing a binding definition is a source edit plus recompilation, not an operation
  (`2026-09-07-tuimodelo-reference`).
- Every command already emits a typed envelope through one funnel with a global
  machine-readable switch, so import results are already structured
  (`2026-09-07-tuimodelo-reference`).
- One sanctioned recovery path for a sealed revision blocked on evidence exists with no
  command and no operation, reachable only from tests
  (`2026-09-07-tuimodelo-reference`).

## Considered options

**For the outbound vocabulary:**

1. **A closed target enum in the frontend.** Rejected: it would place the vocabulary in an
   adapter, and a second adapter would need its own copy.
2. **A typed registry of destinations declared as registry data.** Rejected: destinations
   are product capabilities, not legal facts about a modelo; putting them in the registry
   confuses two authorities and burdens revision compilation with transport concerns.
3. **A typed application-layer destination contract with a closed capability-gated set.**
   Chosen: it puts the vocabulary where both adapters can consume it, keeps capability
   gating with the services that already own it, and leaves the registry to describe law.

**For the inbound path:**

4. **Drive the existing application import functions directly from the frontend.**
   Rejected: it bypasses the supervisor that governs every other mutation, so imports would
   be the only frontend mutations without journal, lease or cancellation.
5. **Enrol import as supervised operations and lift the ledger's dry-run and per-item
   result contracts to the modelo side.** Chosen: it reuses two proven contracts rather
   than inventing them, and brings import under the same governance as every other
   mutation.

**For binding import:**

6. **Offer binding declaration authoring in the product.** Rejected outright: the bundled
   registry tree is read-only by construction and a binding is filing-grade legal
   declaration requiring validation gates and grounding evidence.
7. **Scope binding-import to source-data admission plus a read-only binding inspector.**
   Chosen: it delivers what the operator actually needs — seeing why a binding is or is not
   satisfied, and feeding the observations it resolves against.

## Constraints

- Import cannot be surfaced before import operations are enrolled in the operation
  registry; this is a backend prerequisite and gates the entire import wave.
- The two command-resident importers must be migrated before either can be surfaced, which
  places them in the CLI-to-backend migration wave.
- The export elections defect must be fixed before the export surface is wired, or the
  product will emit different declaration types depending on which surface the operator
  used.
- Remote authorization must be delegated to a child process; an in-process implementation
  is impossible given the terminal refusal and the blocking receiver.
- Byte-level export correctness cannot currently be proven by fixture, because no golden
  fixtures exist and the proof roster is empty. Any claim that an export is byte-correct
  must be qualified until that changes.
- Completeness is unverified for the modelos without manifests, and the surface must say so
  rather than presenting an unverified export as complete.
- Binding definition authoring is permanently out of scope for any surface this record
  governs.
- Depends on the accepted architecture decision for operation supervision and composition,
  which is accepted and in force.

## Implementation

Outbound movement gains a typed destination contract in the application layer. A
destination names a transport and the artefact family it accepts, carries its own
capability gate, and reports its own availability, so a surface can render the set of
destinations that are actually usable for a given declaration rather than a static list
with runtime failures. The frontend's existing use of the word for screen routing is left
alone and the new contract takes a distinct name, because two meanings of one word in one
codebase is how the next reader is misled.

The single byte producer remains the single byte producer. Destinations differ in where the
bytes go and in what wrapper they carry, never in how a declaration is rendered. The
already-built offline workbook exporter is wired as a destination rather than reimplemented,
and the payload-consumer arm of the export draft path becomes the preview mechanism, so a
preview and an emitted file are produced by the same call with a different sink.

Export elections are threaded through the supervised operation so that the operation and
the command line accept the same declaration-shaping choices. Until that holds, the export
surface is not wired.

Output handling stops silently overwriting. An existing file is a refusal that the operator
resolves explicitly, and the contradictory path contract is corrected so that its
documentation and its validator agree.

Coverage and completeness are surfaced as facts rather than hidden. A declaration whose
revision has no renderable layout is refused with the reason, and an export whose
completeness could not be verified says so on the artefact and in the result.

Inbound movement is brought under supervision. Import becomes a family of registered
operations so that it inherits journalling, leasing, cancellation and secure request
storage like every other mutation, rather than remaining the one mutation class outside
that machinery. The ledger's two contracts are lifted to the modelo side rather than
reinvented: a dry-run that previews without staging, and a per-item typed outcome so a
partial import reports which items succeeded, which were refused, and why. Progress is
reported through the existing operation modal, which is the reason enrolment comes first.

The two command-resident importers move to application services during the migration wave,
after which both surfaces call the same service.

Binding-import means two things and only two. Source-data admission fills the observation
store through the existing typed provenance taxonomy, whose closed source-kind enum already
fails closed on an unknown token. A read-only binding inspector shows, for a declaration,
which bindings are satisfied, which are unsatisfied and why, using the prefill report and
unsatisfied-binding types that already exist. Authoring or importing a binding declaration
is not offered, and the surface says why when asked.

The orphaned evidence-recapture path is given a home, because it is the sanctioned way to
un-strand a sealed revision blocked on evidence and currently exists only for tests.

## Rationale

The outbound decision turns on where a vocabulary belongs. A frontend enum would be copied
by the next adapter; registry data would make transport a property of tax law. The
application layer is the only home that serves both adapters without corrupting the
registry's meaning, and it is where the capability gates already live.

The inbound decision is close to forced. Import is the only mutation family outside the
supervisor, and the brief asks for exactly the affordances — preview, progress, per-row
outcomes, cancellation — that supervision and the ledger contracts already provide
elsewhere. Building them a second time inside an import screen would be the campaign's
clearest violation of its own reuse mandate, and would leave imports uncancellable and
unjournalled.

The binding-import decision is settled by the tree being read-only. What remains after
removing the impossible is the part operators actually want: not authoring a binding, but
understanding why one did not resolve. That inspector is buildable today from types that
already exist, which makes it the cheapest high-value item in this record.

Two defects are promoted to prerequisites rather than backlog. The dropped elections defect
is promoted because it is a correctness divergence between surfaces, which is worse than a
missing feature. Silent overwrite is promoted because an export is the artefact an operator
submits to the authority, and destroying a previous one without asking is not recoverable.

## Consequences

The export surface becomes a thin renderer over a real contract, and adding a transport
later becomes a backend change with no frontend edit. The already-built workbook exporter
stops being dead code, which is the single largest reuse win available in this area.

Honest coverage reporting will make the product visibly narrower than a list of formats
suggests: eleven modelos have no layout at all, several have bare revisions, and most
exports cannot claim verified completeness. Operators will see refusals where they might
have expected files. That is correct, and it is the only alternative to implying a
completeness the product cannot demonstrate.

Byte-correctness remains unproven by fixture until a golden corpus exists. The campaign
inherits that obligation, and until it is discharged no surface may claim an export is
byte-accurate — only that it was produced by the canonical builder and validated against
its manifest where one exists.

Enrolling imports as operations is real backend work that delays the import surface, and it
touches a registry that other campaigns also extend. In exchange, every import gains
cancellation, journalling and progress for free, and the import surface becomes as thin as
the export one.

Remote authorization through a child process introduces a process boundary in an otherwise
in-process application, with its own failure and cancellation semantics to design. There is
no alternative: the existing flow refuses a non-terminal host outright.

Declining to offer binding authoring will disappoint the reading of the brief that expected
it. The inspector delivers the diagnostic value; the authoring path stays where filing-grade
legal declaration belongs, behind source review and validation gates.
