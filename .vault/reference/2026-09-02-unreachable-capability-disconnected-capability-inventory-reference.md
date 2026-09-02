---
tags:
  - '#reference'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0f7c4c4ded7b0139c33c9d64e643bbb496d4733a9a9001c760ac9a7f02df988c'
related:
  - "[[2026-09-02-unreachable-capability-research]]"
---

# `unreachable-capability` reference: `capability built but unreachable from the CLI`

## Summary

An inventory of capability that is built, tested, and shipped inside the wheel,
and that no console-script entrypoint can reach. It is not a dead-code list:
the superseded and duplicated surfaces were retired earlier and are gone. What
remains is, in the main, work that functions and was never connected.

The reachability facts come from `python -m dev.audit.unreachable_code`, which
walks the import graph from the declared console scripts, the shipped
`__main__.py` surfaces, and the sibling workspace distribution. At the time of
writing it reports 49 findings spanning 86 modules.

Each entry answers five questions: what the capability is in tax terms, how
complete it is, why it is not connected, what it adds to the filing product,
and the smallest wiring that would reach it. The third answer uses a fixed
vocabulary — bug, oversight, explicit decision, unfinished, sequenced — and an
explicit decision requires a citation, because an absence of callers is
evidence of nothing.

One cross-cutting fact belongs here rather than in any single entry. Every
`consumer` declared across the shipped registry data was checked against the
reachable module set, and exactly one names a module no entrypoint can reach:
the Modelo 100 revision 2025 cross-reference row for the Renta WEB Open portal
surface. That is the only case where registry data declares a consumer that
does not consume.

## The registry axis

A binding declaration and the code that resolves it are two halves that can
drift apart independently, so the registry was checked from both directions.

**Declared consumers that cannot run.** Every `consumer` string across the
shipped registry tree was resolved against the reachable module set. Exactly
one names a module no entrypoint can reach: the Modelo 100 revision 2025
cross-reference row naming the Renta WEB Open portal surface. Registry data
therefore asserts a consumer relationship that cannot execute, and it is the
only such row.

**Resolvers with nothing to resolve.** The canonical `BindingSourceKind`
vocabulary carries 33 members. Thirty-two source families appear across the
9,020 binding declarations in shipped data. Comparing the two sets leaves five
enum members that no registry row anywhere declares:

- `borrador`
- `iva_wallet_decision`
- `ledger_transaction`
- `purchase_invoice_evidence`
- `withholding296`

None is a reserved placeholder. Each is referenced by real resolver and
validator code outside tests, between six and nineteen sites apiece, across
`application/aggregation`, `application/calculations`, `application/review` and
`application/ledger`. So the mechanism can resolve five source families that no
declaration ever asks for.

The `borrador` entry is the sharpest, because its adapter is independently on
the unreachable list: `adapters/inbound/borrador/` parses the Modelo 100 draft
and no entrypoint reaches it, while the binding family that would carry its
values into casillas is declared by no revision. Both halves of that feature
are disconnected, in different ways, which is why neither shows up as a broken
reference anywhere.

A caution for anyone repeating this measurement. A first pass over `source =`
strings also reported `ley_irpf`, `manual_renta`, `reglamento_irpf` and
`aeat_help` as undeclared families. They are not binding sources at all: they
are legal-citation sources on the category proportionality declarations, with
their own enum in `domain/categories/proportionality.py`. Two unrelated
declaration kinds share the `source` key, and conflating them invents four
defects that do not exist.

## Entries

### `domain/fincas/` with `adapters/persistence/profile/fincas.py`

**What it is.** Spanish rental-property income for the IRPF annual return: the
computation an operator needs to declare what a let property earned. Gross
rent per contract, deductible expenses under LIRPF article 23.1 with the
carry-forward the article requires, the article 23.1.f amortisation, the
article 23.2 reducción tier resolution for residential letting, and the
article 85 imputation for property that was not let.

**How complete.** Eleven domain modules and a five-repository persistence
adapter, around 1,800 lines of implementation against roughly 1,400 lines of
tests, all passing. It is registry-grounded rather than hard-coded: sixty
rental parameters ship across the Modelo 100 revisions carrying `legal_refs`
to LIRPF article 23, with the amortisation rate additionally citing RIRPF
article 14, and several carrying source citations whose required text is
verified against the bundled corpus.

The persistence half needs no work at all. The five `rental_*` tables are
declared on the same SQLAlchemy base whose `metadata.create_all` runs at
`adapters/persistence/storage/sql/engine.py`, so every profile database that
exists today already carries them, empty.

Verified against the bundled AEAT manual rather than assumed: all four
reduction tier rates match, both tenant age bounds match, the rent-reduction
threshold matches, and the proportional co-tenant rule is implemented with the
governing BOE sentence quoted at the implementation site in
`domain/fincas/tier_resolver.py`.

**Why not connected.** SEQUENCED, with a real modelling gap behind it. The
source-connectivity census row `fincas.annual-aggregates` is
`grounding_blocked`, and the plan that owns it hard-sequences fincas behind
amortization, whose own promotion step is still open. The row's stated blocker
and the code's stated blocker disagree — `domain/fincas/source_readiness.py`
reports a persistence gap, which is the closed meaning of a different
disposition — and that disagreement is unresolved.

The genuine gap is narrower than either: the `Finca` record carries no
ownership or usufruct share, so it assumes full title, while the manual
requires the owning contribuyente and both percentages as per-property facts.

**What it adds.** Rental income is one of the most common IRPF situations for
an individual filer, and the article 23.2 reduction is worth between 50 and 90
per cent of net income depending on tier, which is a large sum decided by
conditions most filers get wrong by hand. The engine already resolves those
tiers correctly against the manual. Connected, it turns a return that a
landlord cannot presently prepare in this product into one they can.

This is the largest single block of finished, legally grounded capability in
the inventory.

**Wiring needed.** Three things in order, none of them small. Route the
aggregates through the encrypted calculation-revision boundary so readiness can
return true. Add the ownership and usufruct fields the manual specifies. Decide
the destination casilla mapping, which the bundled manual can settle: its
chapter 4 names the destination casillas individually and fixes the grain with
a worked example of one property across two successive tenancies, income per
contract inside a per-property per-year envelope. Only then a CLI subject over
the repositories that already exist.

### `entrypoints/tui/modelo/action/` with `modelo/actions.py`

**What it is.** The six lifecycle mutations on a modelo work unit — rename,
discard, verify, file, export, amend — each submitted as a registered,
journalled, leased operation rather than a direct write, plus the inert table
binding each to its operation-definition id, the capability that gates it, and
where a settled run lands the operator.

**How complete.** 705 production lines against 1,081 test lines, green. Each
enrolment builds a typed request and returns a bound controller. Grounded
through registry definition ids rather than a hand-kept list: a test builds
every registered definition and fails if the table names an unregistered one.
The table also declares the 25 modelo mutations that have no registered
definition, so the gap is stated rather than hidden.

**Why not connected.** SEQUENCED. Interface plan step `W06.P13.S92` is open and
records that the C1 to C4 cohorts all closed on 2026-08-31, so "the only stated
reason for holding Modelo back is discharged". Architecture step `W06.P13.S73`
owns the navigation join. The ratchet freezes the whole TUI prefix as in-flight
work owned elsewhere.

Beyond the mount, these six need an affordance that does not exist. The
workspace read screens mount an actions region that only prints that no
producer supplies recovery actions, and nothing turns a dispatch row into a
button or key binding.

**What it adds.** The largest single gain in the TUI slice, and one of them is
a live defect rather than a missing feature. Today the CLI's rename and discard
call the lifecycle writer directly, with no lease, no journal, no cancellation
and no crash resume, which is the bypass the rename action's own docstring
names as the thing it exists not to repeat. On a tax product that is an
audit-trail hole.

The individual gains are concrete. Verify produces the pre-filing report
against live profile state resolved at execution rather than frozen into the
request. File stamps the local filing intent so a downstream cross-period gate
cannot mistake it for AEAT acceptance. Export writes the official fichero while
keeping the exported bytes out of the journal, because a filing artefact is the
taxpayer's complete declared position and belongs in a store with a different
lifetime. Amend addresses a filing record, requires a reason and at least one
override, and carries values as exact characters so a journalled correction
round-trips to what the operator typed; that is the Modelo 303 rectificativa
and complementaria path. Discard carries an exact-approval baseline that
refuses if the unit moved underneath.

**Wiring needed.** An action bar on the workspace screens rendering enabled
rows from the dispatch table, capability-gated, prompting for exact approval
where the action destroys its subject, submitting and presenting the returned
controller through the operations facade. Owner: interface plan `W06.P13.S92`,
behind `W06.P13.S73`.

### `entrypoints/tui/operations/`

**What it is.** The one door through which a long-running mutation is shown to
an operator: submit, watch progress, read a bounded event log, answer a review
interaction, cancel where permitted, detach and leave it running, and be routed
to the refreshed workspace on settle.

**How complete.** 1,034 production lines against 1,401 test lines.
Architecturally clean: everything derives from public frontend contracts, and
nothing imports a persisted snapshot, journal record or supervisor-private
type. One real functional gap rather than a wiring one: the interaction layer
treats the public input and choice kinds as unsupported, and `modelo.edit.apply`
is precisely the operation that declares an input interaction, so the editor's
apply would meet an unsupported affordance rather than a control.

**Why not connected.** SEQUENCED, on the same three citations. Its only two
production consumers are the rename action and the censal sync review, both
themselves unreachable.

**What it adds.** This is the platform that makes every other mutation
governable, and its value is a filing-safety property rather than a
computation. A Modelo 390 export or a 303 amendment that crashes mid-run
currently leaves the operator with no record of how far it got; the journal,
lease and detach model lets them reattach and see. Honest caveat: it renders
event codes into a plain static widget, so it is a competent progress view, not
a diagnostics console.

**Wiring needed.** Nothing of its own — it is already a facade with a
one-function door, and becomes reachable the moment the action bar or the sync
review is mounted. Separately, enrol a renderer for the input and choice
interaction kinds before the editor's apply is dispatched through it.

### `entrypoints/tui/modelo/edit/`

**What it is.** Direct editing of a modelo's casillas: type a value into a
Modelo 303 casilla, add or remove a counterparty row on Modelo 349, review
what is staged against the contract's preflight, then submit.

**How complete.** 811 production lines against roughly 1,200 test lines, green.
Substantively grounded rather than skeletal. It keeps unchanged, zero-or-false,
cleared and unresolved as four distinct states and refuses to collapse any into
"no answer", which is the no-silent-under-declaration requirement made
concrete. It addresses rows by natural key rather than screen position and
declines to offer reorder, because producers sort by content key before
assigning occurrence numbers so a move would change nothing in the filing. It
distinguishes surface blockers from contract findings and refuses to report
"approved", since the guarded commit point re-checks independently.

**Why not connected.** SEQUENCED and UNFINISHED at one clause. Interface step
`W06.P12b.S77` is open with three of four clauses done: the session's submit
now assembles the apply request but does not dispatch it. So the editor can
stage, review and assemble, and nothing dispatches. The apply operation is the
seventh row in the dispatch table; the seam is declared and unbuilt.

**What it adds.** Correcting a figure before filing without leaving the
workspace, with the four value states preserved, which is the difference
between a lawful declared zero on a Modelo 303 casilla and a silent
under-declaration. The row editor is what makes Modelo 349 and 347 practical at
all, since per-row CLI editing of a counterparty list is hostile.

**Wiring needed.** Close `W06.P12b.S77` so submit dispatches through the
supervisor, enrol the input interaction renderer, then an entry point onto the
editor from the workspace screen.

### `entrypoints/tui/profile/app.py` with `journey_status.py`

**What it is.** A guided five-stage shell — overview, get data, required,
review, ready — walking a taxpayer through completing the profile every modelo
calculation depends on.

**How complete.** 298 production lines against 159 test lines, and only three
of five stages are real. Get data and review mount a placeholder whose own
Spanish text says the surface is not yet available in this journey.
Accessibility is handled properly: an inactive stage leaves the DOM rather than
hiding under CSS, so there is no keyboard trap.

**Why not connected.** UNFINISHED, and separately sequenced. Unlike the Modelo
cohort this is not merely awaiting a mount; two stages carry no content, and
the devtools harness paints the profile manager and status screens but not the
journey.

**What it adds.** Moderate, and partly duplicated. The classification already
reaches an operator through the profile config verbs. What the journey adds is
ordering: a first-time operator does not know that régimen, epígrafe IAE and
territorial applicability must be settled before a Modelo 303 will calculate.
But with two stages empty it cannot presently take anyone from nothing to
ready.

**Wiring needed.** Build the two stage bodies first, then mount. No open step
was found for the stage bodies.

### `entrypoints/tui/profile/sync_review.py`

**What it is.** Per-field review of an AEAT censal observation against the
local profile — observed value, suggested adopt-or-preserve intent, operator
selection, one field at a time — plus a progress summary over the filed-history
pull.

**How complete.** 317 production lines against 568 test lines. It never
re-derives the merge the application layer owns, reads the effective fact
through a public door, and refuses a review whose baseline the profile has
already moved past.

**Why not connected.** SEQUENCED. No record says it is deliberately unwired.

**What it adds.** Real and specific. The CLI equivalent echoes every field and
asks a single confirmation: all or nothing. Census data drives which modelos
are due and which régimen applies, so all-or-nothing means an operator who
disagrees with one AEAT-observed field must reject the whole sync and hand-edit.
Per-field selection is the difference between adopting AEAT's corrected
domicilio while preserving a locally correct epígrafe, and adopting neither.

**Wiring needed.** It is already a modal screen; it needs a caller. Smallest
change is the profile manager pushing it after a censal observation lands.

### `entrypoints/tui/secret/passphrase.py`

**What it is.** A full-screen passphrase rotation with live strength feedback
and inputs frozen while storage mutates.

**How complete.** 278 lines, covered by the secret journey suite, with a
launcher nothing calls.

**Why not connected.** SEQUENCED. It shares its shape with four other unused
launchers: the CLI may not import the TUI, so none of them has a caller.

**What it adds.** Little. The capability is already fully reachable through
`aeat config passphrase change`, which drives the same application door,
supports both interactive and machine-secret channels, and emits the same
envelope. The screen adds strength feedback and a busy state. Not a tax
capability and not an obligation it helps discharge. Lowest wiring priority in
the slice.

### `entrypoints/tui/components/errors.py`, `logs.py`, `_safe_text.py`

**What it is.** Three reusable widgets for showing a failure or a run log
without leaking: a bounded error panel with an action label and runbook id, a
bounded log panel holding at most sixteen severity-tagged entries, and a shared
validator that refuses filesystem paths, URLs, tracebacks and credential
markers before rendering.

**How complete.** 293 lines against 137 test lines. Small and complete.

**Why not connected.** OVERSIGHT, and not merely the mount. The other
components in the same package are reached by live screens; these three are
not, with no record explaining the asymmetry. The operations modal, the natural
consumer of a bounded log panel, rolls its own into a plain static widget and
never imports the component.

**What it adds.** Indirect but real. Nothing tax-domain, but the redaction
guard is a second line of defence against a diagnostic putting a taxpayer's
file path or a credential fragment on screen.

**Wiring needed.** Point the operations modal's log pane at the bounded panel
and route its terminal-refusal copy through the error panel. A small edit
inside the operations cohort that does not wait on the home screen.

### `core/observability/replay.py`

**What it is.** Re-running a previously recorded CLI invocation exactly: load
the trace, recompute the corpus digest, refuse if the registry has drifted, and
re-enter the same command path from the captured arguments.

**How complete.** 281 lines against 561 test lines, and genuinely defensive: it
refuses a trace carrying a removed flag so an old trace cannot promote a dry
run into a live write. The recording half is live and traces are being written
today; only the replay half has no caller.

**Why not connected.** OVERSIGHT. No CLI verb reaches it, and the accepted ADR
that extends it treats it as an existing foundation rather than deciding it
should stay operator-inaccessible.

**What it adds.** Moderate, and mostly assurance. An AEAT query about a filed
Modelo 303 months later could be answered by re-running the exact invocation
against the recorded corpus, refusing loudly if the registry has moved since,
which is a stronger provenance answer than what the current code computes. As
shipped it proves the same arguments re-run, not that the same output emerged.

**Wiring needed.** One diagnostics verb under the existing family, plus a
decision on whether an operator or only the golden gate should reach it.

### `core/telemetry/_producers.py`

**What it is.** Three producers projecting local signals — command invocation,
error frequency by closed label, LLM run — into the allowlisted payload and
handing them to the consent-gated dispatcher.

**How complete.** 174 lines against 173 test lines, green. Pure projections, no
network call, no transaction content or profile identity read.

**Why not connected.** UNFINISHED against a declared follow-up. The telemetry
ADR says the package is deliberately empty of producers until a follow-up wires
real emit call sites, and that the CLI verbs and transport remain open. The
producers have since been written; the call sites and transport have not. Note
this is not a decision that they stay unwired — the record says the opposite.

**What it adds.** Little, for the taxpayer. Nothing here discharges an
obligation or removes a filing risk, and it is default-off with an absolute bar
in gestor mode, so it adds nothing to a default install. Last in the slice for
wiring value.

### `core/corpus_manifest/_bundle_signing.py`

**What it is.** Publisher authenticity over the existing bundle integrity
layer. Today a corpus bundle rebuilt by anyone verifies as clean as one the
project published; this signs the self-attesting manifest digest offline and
verifies against an embedded public key with no network call.

**How complete.** 404 lines against 338 test lines, six public functions. The
key persists as a hardened hex file rather than through the secure repository,
because core may not import adapters. Its two exception classes are registered
with user-facing message keys translated across all four locales — a complete
failure surface for a capability with no caller.

**Why not connected.** OVERSIGHT. No maintainer command signs and no installer
path verifies, and no record decides either way. The integrity layer beneath it
is itself only reachable from tests, so the whole offline-distribution story
lacks an operator entrypoint.

**What it adds.** Real but conditional on a distribution model that does not
yet exist. The corpus is the compiled AEAT registry: rates, thresholds, casilla
definitions, revision windows. An installer fetching a bundle over an untrusted
channel with only the checksum layer cannot distinguish internally consistent
from published-by-the-project, so a substituted corpus with altered IVA rates
would install clean. On a tax product that is a filing-correctness attack, not
merely a supply-chain one. If bundles are never distributed out of band it is
dead weight.

**Wiring needed.** A maintainer signing step in the release process and a
verify call on the installer path, neither of which exists. That is a
distribution decision before it is a wiring one, so it needs a decision record
rather than a patch.

## Gates that are absent at runtime

Three entries below are not merely unreachable. A check the product intends to
run does not run, and in each case something reaches an operator or a filing
that the check exists to stop. They are listed first because they carry filing
consequence rather than missing convenience.

### `application/storage/calc_sheets/evidence.py`

**What it is.** The projection turning a ledger-derived filing's evidence —
contributing transactions with amount, currency, FX rate, taxable base, IVA
rate and amount, counterparty, attachment ids, legal and source refs, plus
manual entries — into the per-casilla facet the exported workbook renders as
its Evidencia tab and its machine-readable evidence sidecar. It refuses rather
than guesses: a contributor with no casilla attribution raises instead of being
dropped.

**How complete.** 97 lines and no tests at all, the only untested module in the
application slice. It would work if called.

**Why not connected.** OVERSIGHT, and the break is one field. The consumer half
is fully built and reachable: the export plan carries an evidence field, the
workbook writer renders it into the worksheet, and the sidecar serialiser
emits it. The sole production constructor of the export plan never passes
`evidence=`, so the field takes its empty default.

**What it adds.** This is the sharpest operator-visible gap found. Every
calc-sheets workbook the product exports today ships an empty Evidencia tab and
an empty evidence sidecar. That workbook is the artefact an operator, their
asesor, or AEAT in a comprobación opens to see why a casilla holds the number
it holds. The value and tariff tabs are populated; the tab that would show the
contributing invoices, their IVA rates, counterparties and legal references is
blank. The export rule requires every exported field to carry the provenance
the calculation used, and the sidecar is where that provenance was meant to
land.

**Wiring needed.** Pass the projection into the export plan where it is built
from a ledger-derived revision, which means threading the filing evidence and
the contributor-to-casilla attribution map into the plan builder, since the
module deliberately refuses to infer that map. Tests must land with it.

### `application/storage/calc_sheets/_row_set_assembly.py`

**What it is.** The boundary check on operator-edited spreadsheet rows before
they become typed observations. Three refusals: an undeclared grouping; a cell
carrying a binding belonging to a different grouping, or none; and a second
submitted block claiming a row coordinate a first block already owns.

**How complete.** 204 lines against 161 test lines covering each refusal by
name. The accepted coordinates derive from the same projection that produced
the workbook, so the guard is registry-derived rather than hand-listed.

**Why not connected.** BUG. A wiring existed and was broken. An open plan step
records it precisely: the package initializer no longer imports the module.
Initializers became inert namespace markers under the import-centralization
rule and every other consumer was repointed at its owning module; this one had
no consumer to repoint, so the re-export was deleted and the module fell off
the graph.

**What it adds.** A real gate absent from the live pull. The spreadsheet pull
command imports the downstream assembler directly and calls it per row-set,
skipping the wrapper. So a cell whose binding belongs to another grouping is
not refused at ingress, and two blocks claiming the same row are not refused.
The wrapper exists precisely because the downstream assembler drops rather than
refuses. The failure is silent: an operator who copies a column between Detalle
tabs, or a pull reading overlapping blocks, gets observations assembled from
data the layout never declared, or one block's rows silently overwriting
another's. Those observations feed casilla values.

**Wiring needed.** Call the wrapper once over the whole tuple rather than per
block, because the cross-block collision check only works when it sees every
block together. The module needs promoting out of its private name first, since
an entrypoint reaching a private module is the boundary violation another open
step is trying to zero.

### `application/wizard/flow_validators.py`

**What it is.** The review-time gate on the taxpayer-profile legal invariants
that decide IRPF and IRNR routing: the impatriado regime, fiscal residency,
country of residence, and the fiscal representative. It runs the real taxpayer
projection constructor over the staged answers before persistence and turns
each failure into a localized, redacted verdict that blocks submit.

**How complete.** 149 lines against 162 test lines that register it against a
real definition and resolve it through the substrate. The three invariants are
real model validators each citing its provision, and every verdict locale key
is present in all four catalogues. Nothing is missing but the registration.

**Why not connected.** OVERSIGHT, though a documented and load-bearing one. Two
sibling modules register their validators and decorate the definition's
validator ids; this one does neither, and its identifiers appear only in its own
tests. The half that landed was the module; the half that did not was one call.
A reference document records the wiring as fact, which is false at HEAD.

**What it adds.** A real gate is absent at runtime, and I checked it is not
caught elsewhere. The answers model carries these as plain strings with no
validators, and persistence writes profile facts without constructing a
taxpayer projection. So setup will persist an impatriado regime with no start
date, or a non-resident outside the EEA with no fiscal representative. The
invariant then fires later at every downstream projection call as raw library
prose, with no jump back to the offending page. Beyond the experience, the
residency and representative facts route Modelo 100 against Modelo 210 and gate
the Beckham window, so the persisted-invalid state is a filing-routing state.

**Wiring needed.** Two lines inside the setup flow definition: register the
validator after the definition is projected, then append its id to the
definition's validator ids, exactly the shape a sibling already uses. The
review surface then runs it and blocks submit with no further change.

## Built, grounded, and never given a verb

### `application/prorrata_register/seed.py` and `sector_lifecycle.py`

**What it is.** The LIVA article 105.Uno carry, which sets this year's
provisional deduction percentage to last year's definitive one, sourced from
the prior Modelo 303 settlement observation and re-confirmed against the
law-selected revision for that period. Plus the per-sector equivalent for a
taxpayer with differentiated sectors under article 101.Uno, which must derive
each sector's provisional from that sector's own prior definitive and settle
its year-end definitive from its own volumes.

**How complete.** 410 and 129 lines against roughly 480 test lines, run against
real filed observations and grounded through the validated registry authority.
Both return nothing rather than defaulting when the prior year holds no settled
definitive.

**Why not connected.** OVERSIGHT, and the plan record makes that a strong
verdict rather than an inference. Every step that built them is checked, no
step anywhere names a consumer, and the read side is live: the IVA ledger loads
the register and reads the in-force percentage. Only the writers are orphaned.

**What it adds.** Modelo 303 and 390 for any taxpayer with prorrata. Today the
register can only be filled by hand, so the default non-discretionary case
under article 105.Uno, where the law leaves no choice at all, is manual data
entry with a typo surface, while the two discretionary cases get identical
treatment. The seed derives the percentage from the taxpayer's own prior
filing, records which observation it came from, and blocks when the carried
figure contradicts that observation or its revision stamp has diverged. A wrong
provisional prorrata mis-states deductible input IVA in all four quarters and
propagates into the year-end regularización. For the sectorized taxpayer the
year-end per-sector regularización has no automated producer at all.

**Wiring needed.** One sub-verb on the existing prorrata command family calling
the evaluate-and-seed pair, surfacing findings through the notice channel with
blocking findings refusing. Cheaper still, call the cross-check from the
existing declare verb so a hand-typed percentage contradicting the prior filing
refuses.

### `application/invoices/_reconciliation.py` with the review lane

**What it is.** Bulk invoice-to-transaction reconciliation: build every match
suggestion across the two catalogues, optionally apply them, and commit both
catalogues in one atomic write.

**How complete.** 156 lines against 344 test lines including an atomicity
suite. It is the more careful of the two writers, co-committing both sides
because two independent saves would leave exactly the one-sided state the link
consistency check reports. Skipped suggestions return with reasons.

**Why not connected.** OVERSIGHT. Its own docstring calls the entry point the
CLI-facing backend workflow, a claim about a CLI that does not exist. No locale
keys for such a verb exist, so none was authored and later removed. Git history
shows real maintenance while unreachable. The review lane beside it is
read-only by declaration and surfaces exactly the invoice and transaction rows
this would close.

**What it adds.** Evidence quality for Modelo 303 and 390 and the Modelo 100
expense side. An invoice with no linked payment has an incomplete evidence
chain, and the ledger contract makes missing evidence a distinct state from a
proven zero. Manual one-at-a-time linking is reachable today, so nothing is
impossible; what is missing is throughput and atomicity. A taxpayer with a
hundred invoices a quarter works the queue one row at a time.

**Wiring needed.** One verb calling the reconciler, defaulting to dry run. The
module must first be promoted out of its private name, since a private module
is not a cross-package API for an entrypoint.

### `adapters/persistence/profile/filing_export_replay.py`

**What it is.** The custody half of the secure replay attestation: re-emit an
approved revision's draft through the canonical writer, verify the bytes
against source-pinned probe expectations at declared offsets, then seal a
receipt in the encrypted store recording the coordinate, both authority ids,
the payload digest, the byte extent and a bounded validity window.

**How complete.** 122 lines against 128 test lines. Disciplined against the
sensitive-data rule: the record persists only through the secure repository on
its own namespace, and the public receipt carries no values, path, digest or
extent. Every conjunct is a literal true, so a partially satisfied proof cannot
be constructed.

**Why not connected.** OVERSIGHT, and it is one of two missing halves. The port
it satisfies is fully declared and so is its counterpart source authority, but
no production implementation of the composing proof authority exists anywhere;
every parameter that takes one is optional and never passed a real one.

**What it adds.** This is the gate separating "the exporter produced bytes"
from "the bytes this taxpayer will file are provably the ones the approved
calculation produced". The coverage report will not mark a filing-export limb
satisfied without it and refuses with a condition naming exactly this receipt.
So no modelo can currently reach a satisfied filing-export coverage limb
through the secure replay channel; the registry's own coverage report is
permanently short by one leg. The probe check catches a canonical writer whose
bytes drift from the source expectation at a declared offset, which is the
difference between a valid fixed-width record and a silently misaligned one.

**Wiring needed.** More than this file. The custody half is finished; the
source authority half does not exist and must be implemented, then composed
with this repository and passed into the coverage and closure paths.

## Deferred by decision, or waiting on the other half

### `application/modelo/edit_session.py`

The operator-level handle for editing a modelo's casillas, 584 lines against
222 test lines. SEQUENCED: its single consumer is the casilla editor covered in
the TUI slice, which is itself unmounted. This is not an orphan but the
application half of a two-half surface. It adds operator override of a computed
casilla where the engine's derived value is right in general and wrong for this
taxpayer, and it holds the in-memory baseline the contract requires so stale
detection works without the frontend seeing a baseline. Nothing to wire on its
own.

### `application/modelo/_edit_facade.py`

The capability row telling a frontend whether the calculate mutation is
available for an edit target. SEQUENCED with a citation: its docstring states
every row is unmeasured in this version because no financial-operand dependency
receipt is green, and the governing decision record names the blocking
artefact. It adds nothing today and that is correct — a facade that can only
answer unmeasured tells an operator nothing actionable, and wiring it now would
put a permanently negative row in front of them. What it needs is the upstream
receipt, not wiring.

### `application/wizard/_registered_values.py`

The review screen's "what you already told us" display strings, with a
localized non-official-evidence suffix when a fact came from the censo artefact
rather than the operator. SEQUENCED behind the full-screen flow frontend, whose
screen is never constructed in production. The provenance suffix is the
load-bearing part: a fact auto-derived from the censo artefact is not an
official AEAT value and the no-silent-under-declaration rule requires that
distinction to reach the operator. In the line frontend that runs today, it
does not.

### `application/wizard/legal_zone.py`

Derived per-page legal grounding: the union of a schema field's legal
references with the registry reverse-grounding index for the same domain key,
so an operator asking why a question is needed gets a cited answer. EXPLICIT
DECISION on the render slot per its own docstring, which says the copy family
exposes no legal-provenance slot and that wiring one is a substrate decision.
That stated blocker is now stale: the page field exists, is assembled into the
page copy, and both frontends render it. Nothing in production populates it.

### `application/wizard/copy_sources.py`

Two resolvers letting a setup page's prompt come from an authority rather than
a hand-written locale string. OVERSIGHT: nothing imports the module so its
import-time registration never runs. Honestly, wiring it alone changes no
rendered pixel, because every setup copy slot is a locale key today. The
capability it would unlock is prompts whose legal citation comes from the
schema rather than being retyped into a catalogue that can drift from it.

### `application/inventory/_source_readiness.py`

A context-independent record answering whether the inventory ledger is a
filing-grade source yet. UNFINISHED with an open step naming the exact path.
Little value, and worth saying plainly: the same fact already has a reachable
home in the connectivity census, whose review condition is a near-verbatim
superset of this module's reason string, and which the source-connectivity
authority actually reads. The census even cites this module as a locator, so
the citation runs the wrong way. Two homes for one fact, and the one that
drifts is the one nothing reads. What it needs is a disposition, not wiring.

## Not capability at all

Three modules in this slice are development artefacts that happen to sit in the
shipped tree, and counting them as unreachable filing capability would
overstate the backlog.

`application/wizard/_translations.py` is a locale-coverage audit whose only two
callers are its own tests. It works, it proves the locale rule, and it is
misfiled rather than disconnected.

`application/operator_surface/calculation_workflows.py` is consumed, by the dev
source-connectivity tooling. Its effect reaches the operator as data one build
step removed: it is what stops the connectivity census claiming a source is
connected through a CLI path that does not exist.

`application/operator_surface/crud_contract.py` with `crud_registry.py` is
conformance scaffolding by its own docstring. This one carries a real problem
though. The docstring promises drift detection between shipped command groups
and the locked design, and that gate does not exist: the only tests assert the
catalogue equals the constants it is built from, and nothing anywhere compares
it against the live command tree. A group could drop a verb tomorrow and every
test here would pass. What it needs is teeth, not wiring: one conformance test
walking the live tree, with a defect-injection proof.

## A fifth disposition the ratchet does not offer

The ratchet header names four remedies for an unreachable module: move harness
code beside its dev consumer, move shared test support into the wheel-excluded
test package, delete capability that lost its last caller, or wire capability
that should be live.

Two entries fit none of them, and both are correctly shaped as they are.

`core/compatibility_lifecycle.py` is dormant by explicit decision. Its own
docstring describes a regime-switched policy that is a no-op today and
activates on a one-line flip, with the regime a one-way repo-committed constant
rather than a setting, so a compliance posture cannot vary per machine or be
silently unset in CI. It is actively armed: a milestone tripwire fails the
build if the package version reaches 1.0 while the regime is still
pre-release. What it protects is multi-year readability of a taxpayer's filed
data across the prescription window. Nothing to wire; flip it at 1.0.

`core/address_components.py` is a design-time vocabulary, explicitly not a
shared address type, because Modelo 210 identifies a municipio by INE code
while Modelo 360 writes its name in thirty characters, and merging them would
assert an interchangeability that does not hold. Its consumer is a gate with
teeth: a test walks every filing producer key, picks the vocabulary from the
key's infix, and fails on any leaf outside it. Having no runtime import is the
intended shape.

Both should be recorded as correctly shaped rather than carried on a wiring
backlog. If the ratchet adopts a fifth disposition, these two are its first
members, and their entries there want a rationale rather than a bare
unreachable comment.
