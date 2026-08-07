---
tags:
  - '#audit'
  - '#llm-package-split'
date: '2026-08-06'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:186692c158f80d2538548330e1d7796273b9c5adaa7255f3903bf284d97138ad'
related:
  - "[[2026-08-06-llm-package-split-adr]]"
  - "[[2026-08-06-llm-package-split-plan]]"
---

# `llm-package-split` audit: `Enforcement gaps, the vacuous-green defect class, and the disposition register`

## Scope

A fresh-context honesty review of the `llm-package-split` campaign, performed by a reviewer
who authored none of the documents under review, plus the remediation that followed. It is
landed here because the original review, the source discovery it checked against, and the
measurement harness all lived in a scratch directory outside the git tree and would not
survive a session handoff. Everything load-bearing is restated here in a form that is
auditable from the repository alone.

Read this document before executing the plan. Its findings are the reason the plan is shaped
the way it is, and the defect class in the last finding is the one most likely to reappear
when a different team re-sequences the work.

Two negatives worth stating up front, because both were verified rather than assumed. No
production code was modified by the review or by the remediation. No live model inference was
run at any point: a prior session's inference crashed the development host and terminated four
concurrent agent sessions, so every measurement here is a static analysis of captured results.

## Findings

### enumerated-gate-tier-fails-open | critical | The strictest secure-storage gate reports success for a surface that does not exist or has been emptied

`_SENSITIVE_SURFACES` in `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`
is an **enumerated tuple, not a walk**. Verified at HEAD: it carries exactly **eighteen**
entries, and `adapters/outbound/llm` is one of them, so the modules this campaign relocates
sit in the gate's strictest tier today. The iteration feeds each entry to
`non_test_python_files_under` in `src/cadrumo/tests/_inventory.py`, which filters an rglob.
There is no existence check, no `is_dir()`, and no non-vacuity assertion anywhere in either
file.

The consequence: **a surface path that does not exist, or that has been emptied, yields the
empty tuple with no error, no warning and no failure.** A named entry pointing at an empty
directory is indistinguishable from a named entry pointing at clean code. The instrument
cannot tell you it lost a surface.

This campaign is precisely the event that exercises the failure, in two directions at once.
Relocating modules out of `adapters/outbound/llm` empties that entry. Enrolling the new
subpackage before the directory exists enumerates a path that iterates nothing. Both pass
green, and the original plan did both.

The severity is not campaign-scoped: the same hole applies to all eighteen surfaces, and any
future deletion, rename, or relocation touching any of them is silently unguarded.

### layering-contract-has-no-opinion | high | A subpackage inherits no layering, and importing it from core would be caught by nothing

The campaign's central architectural argument was that a subpackage stays inside the layering
contract where a sibling top-level package would escape it. Verified at HEAD, the second half
is true and the first half is false.

`.importlinter` sets `root_package = cadrumo`, declares exactly **five** contracts (four
`forbidden`, one `layers`), and sets **`exhaustive = false`** on the layers contract.
`cadrumo.llm` appears in **none** of them. `root_package` governs graph membership, not
contract membership, and the two were conflated.

Worse than neutral: because `cadrumo.llm` is absent from every `forbidden_modules` list,
**`cadrumo.core` or `cadrumo.domain` importing the optional inference package would be caught
by nothing** — a hole that exists for no current package. A step that said "confirm the
layered import contract covers the new subpackage" would have passed, because import-linter
has no opinion on an unenrolled module.

**Exactly what must be added**, so a receiving team does not have to re-derive it:

- The `layered` contract's `layers` list currently reads, outer to inner: entrypoints,
  adapters, application, domain, core. Add `cadrumo.llm` at the **adapter tier**. The position
  follows from the governing ADR's persistence decision rather than from convenience: the
  extension receives already-resolved bytes and returns a typed payload, holds no repository
  handle, and imports nothing from persistence — so it is callable by application code and
  forbidden from reaching inward past its own tier.
- The `core-not-outer` contract lists `cadrumo.core` as its source module. Add `cadrumo.llm` to
  its `forbidden_modules` so a core module importing the optional inference package fails.
- The domain-facing forbidden contracts need the same addition, so a domain module importing it
  fails for the same reason.
- **Do not set `exhaustive = true`.** It is `false` today, and flipping it surfaces a much
  larger backlog belonging to no campaign; taking that as a side effect of an inference boundary
  would be unearned scope. The narrow enrolment is sufficient.
- A separate contract forbids any persistence import *from* the subpackage. That is the outward
  half of the boundary; the enrolments above are the inward half. Both are needed and neither
  substitutes for the other.

Verify by mutation in every case: introduce a deliberate violating import, observe import-linter
red, revert. An import contract that has never been made to fail has not been shown to work.

### gate-coverage-claim-not-checkable | medium | "The five AST gates scan the subpackage" compresses three different mechanisms into one unverifiable sentence

The five secure-storage checks span three files and **do not share a scanning mechanism**, so
a single sentence asserting they all "scan" a new directory is not a checkable outcome. The
whole-tree file-write inventory and the storage-provenance restriction scan by rglob and
therefore reach any new directory under the scanned root automatically. The sensitive-surface
check **enumerates** and reaches a new directory only when its list is edited — this is the
tier that matters and the one that fails open. The staging-directory pin and the
ephemeral-key hygiene check have narrower scopes that do not bear on a new subpackage at all.

A coverage claim must therefore be stated per check, naming the mechanism each uses. A
mutation proof aimed at the rglob tier proves the tier that was never in doubt.

### undefined-target-record | high | Three parser steps mapped to "the typed invoice record", a phrase with no referent

The phrase appeared nowhere else in the campaign, and both available readings carried a
defect. Read as the extraction draft: verified at HEAD, `InvoiceDraft` carries **nine flat
optional scalars** and a single base/rate/amount triple, so it structurally cannot hold a
per-rate breakdown — an exact parser feeding it would produce the same collapsed scalars the
regex path already produces, leaving the multi-rate silent collapse alive in a campaign whose
claim is that the structured path is exact. Read as the persisted invoice: the parser would
bypass the confirm boundary, which is where the sibling campaign's plausibility gate lives and
where the governing ADR says it must stay.

This is load-bearing across campaigns rather than cosmetic. The sibling campaign's writer half
explicitly names this campaign as the dependency for the reader half, and the original plan
carried no step producing per-rate lines into anything.

### accepted-decision-narrowed-in-silence | medium-high | Deleting the cloud read path narrows a still-accepted ADR whose status was untouched

The campaign deletes the cloud consent gate and the capability behind it. An accepted decision
record explicitly sanctions a cloud read behind that gate, and its status was left untouched,
so the corpus would have carried two accepted records — one sanctioning a capability the other
deletes. Neither the ADR nor the plan recorded the narrowing. The provenance stamp's provider
axis also changes meaning once the cloud providers are gone, and nothing said so.

### parser-behind-a-closed-front-door | medium | The ingest gate refuses the formats the new parsers read

The two-member media kind is derived at **two** closed sites, not one. The read-time
derivation lives in `_evidence_input.py`; the **ingest-time** suffix gate lives in
`application/ledger/_evidence.py` and refuses anything outside `.pdf` and eight image
extensions. The original plan named only the first. Left alone, a standalone Facturae XML —
one of the two formats the campaign adds a parser for — is still refused at
`evidence add --file` and becomes readable only if it happened to arrive through a different
channel. The same refusal message cites a decision record that does not exist, which also
breaches the *Code Stands Alone* mandate by naming a vault stem from source.

### parsers-in-the-wrong-layer | medium | External-format parsing was placed in the application layer

Three new external-document-format parsers and a content-shape probe were scoped to
`application/ledger/`. The established home for parsing externally-authored formats is
`adapters/inbound/`, which already carries seven sibling packages doing exactly that. A record
whose subject *is* a boundary decision cannot place format parsing in the application layer
without contradicting itself, and relocating it later is more expensive because the project
requires a relocation to land as one atomic explicit-path commit.

### evidence-record-identity-is-clock-bound | medium | A derived record id folds the clock, breaching a codified rule — but the naive fix is also wrong

`derive_purchase_invoice_evidence_id` in `application/ledger/_evidence.py` takes `created_at`
as a parameter and folds it into the digest, with a `disambiguator` ordinal to break
same-instant collisions. The codified rule on single-subject mutation is explicit that the
record's identity must be clock-free and the timestamp a non-identity body field, so this is a
straight breach: re-running `evidence add` on one file mints a second record and a second
bucket event over one shared blob.

**The obvious remedy is wrong, and this is the part worth carrying.** Reading the derivation at
HEAD shows the clock is deliberate: the docstring states that two evidence records for the
same file must keep distinct ids, and the disambiguator exists to preserve that case rather
than to collapse a retry. Simply dropping `created_at` would silently collapse genuine
duplicates. The governing rule already supplies the correct shape — a deliberately-additive
verb is documented as such, while a **caller-supplied idempotency key** provides the guarded
path for callers that need one.

The defect is small today and corrupting at scale: any directory-ingest or resumable batch verb
multiplies evidence records on every re-run, which is why the source discovery names fixing
identity as a **prerequisite** for batch work rather than a tidiness item.

### steps-that-cannot-fail | critical | The campaign's recurring defect class, and the one most likely to reappear

Every finding above is an instance of one shape: **a step that passes without proving
anything.** Three concrete forms appeared, and each would have closed a checkbox while leaving
its stated property unestablished.

A **gate enrolled before its target exists** — the surface enumeration scheduled two waves
before the directory was created, iterating zero files and reporting success. A **mutation
proof that cannot run** — scheduled against a subpackage that would not exist for another two
waves, leaving an executor only the options of skipping it, faking it against a stub, or
deferring it; it was also the single control that would have caught the first defect. And a
**"confirm" against a check with no opinion** — import-linter passing because nothing enrolled
the module it was asked to confirm.

The compounding property is what makes this critical rather than merely untidy: the encryption
exemption the campaign rests on is valid only while the controls establishing its
persists-nothing premise actually exist. An execution that lands all three of these defects
produces a correctly reasoned exemption resting on controls that check nothing, **with every
checkbox closed and every gate green.**

### ingest-findings-dropped-without-scope-statement | medium | Fourteen source-discovery findings were neither actioned nor declared out of scope

The campaign's research scoped itself narrowly and legitimately, but the ADR then annexed a
large piece of ingestion territory. Once a record claims a surface it inherits the duty to say
what it is *not* doing there, and no campaign document carried a deliberately-out-of-scope
section — while the sibling campaign's record did, which made the omission conspicuous. The
full register is below.

### semantic-sweep-of-the-load-bearing-negatives | low | All four absence claims survive a search by meaning, and the sweep surfaced three adjacent hazards a symbol grep could not

Recorded because an absence claim is only as good as the search that established it, and a
symbol-name grep cannot find a concept implemented under a name nobody guessed. Four claims this
campaign rests on — one of them the entire premise of D7, one of them a deletion authorisation —
were re-established by semantic search and then confirmed by anchored search at HEAD.

**Index conditions, stated because they determine what the sweep is worth.** Run against a
healthy service: all three index generations `succeeded`, `degraded_reasons` empty, integrity
verdict `consistent`, **79,273 code chunks across 5,331 files**, queries returning in 0.8–1.3 s
with no queue wait. An earlier caveat that the index reported itself shrunken had cleared by this
point; a sweep run under that condition would have been worthless and is not what this records.

| Claim | What it rests on | Semantic sweep | Anchored confirmation | Verdict |
|---|---|---|---|---|
| No e-invoice parser exists in production | the premise of D7 and all of `W02` | "parse a structured electronic invoice XML document into invoice fields" — **top score 0.10**, no candidate | 0 hits, word-anchored, production only | **survives** |
| No hardware-capability probe exists | D6 | "detect GPU VRAM or device capability before running a model" — **top score 0.036**, every hit a different concept | 0 production hits for VRAM, NVIDIA, NVML, CUDA, GPU or device-capability | **survives** |
| The cloud-subprocess orphan set is complete | the `W05.P11` deletions | "shell out to an external command line tool to classify a document" — **high signal, 0.62/0.57/0.53** | 7 production files, all already covered by a Step | **survives, with a caveat below** |
| `defusedxml` has exactly two production consumers | placing new parsers against it | "safely parse untrusted XML with entity resolution disabled" | exactly two, as claimed | **survives** |

**The low scores are themselves the evidence** on the first two. A semantic index of 79,273
chunks returning nothing above 0.10 for "parse a structured electronic invoice" is a stronger
negative than a grep returning zero, because it also rules out the same concept living under an
unguessed name.

Three things the sweep surfaced that the greps did not, each actionable:

**A neighbouring subprocess transport that must NOT be deleted.**
`entrypoints/mcp/_call_runtime.py` shells the deterministic CLI for every MCP tool call. It is a
subprocess transport, it is not the cloud LLM transport, and an executor sweeping for
`subprocess` while working `W05.P11` could plausibly over-delete into it. The same applies to a
duplication-audit helper that shells a Node tool. The deletion Steps name symbols rather than the
word `subprocess`, and they must stay that way.

**Two builder functions the ADR named only as a family.** `build_codex_classifier` and
`build_claude_classifier` in `domain/transactions/_llm.py`. Naming them makes the deletion
scope checkable rather than descriptive.

**"Capability" is overloaded across at least four unrelated concepts** in this tree: modelo
*revision* capability in the registry conformance surface, *frontend/terminal* capability in the
flow substrate, operator-selectable *service* capability in core, and *optional-extra* capability
in provisioning. A new hardware probe named "capability probe" would collide with all four. The
hardware axis should be named for what it measures — the model runtime's hardware floor — not for
the generic word. This is naming guidance for `S06`, and it is exactly the class of collision the
discovery mandate exists to prevent.

One clarification the sweep forced on the ADR's own wording. "Nothing outside the ledger uses the
cloud subprocess transport" is true of *callers* but loose as a scope statement: the symbol set
reaches the config-check surface, provisioning, the core capability enum and the domain facade.
Every one of those is already covered by a Step, so no orphan is unaccounted for — but an
executor reading the sentence as "this deletion is ledger-local" would under-sweep.

### stale-docstring-propagated-a-false-scope-decision | medium | Prose in the tree asserted a gap a same-day commit had closed, and it travelled two campaigns before anyone checked the enum

The most instructive near-miss of the campaign, recorded because the mechanism will recur and
because the stale source is **still in the tree** for the next reader to find.

`application/invoices/_source_resolver.py:271-280` states that intra-community services *"map to
no `IvaCategory` member at all, because the enum names goods, acquisitions and triangulation but
not services."* **That is false.** `IvaCategory` in `domain/iva/_schema.py` carries
`INTRA_COMMUNITY_SERVICE_SUPPLY` and `INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE`, added
by commit `7502ee65ed` — *"represent intra-community services, which no category could express"* —
dated the same day the docstring's claim was relayed. The prose was accurate when written and
was not updated when the commit landed.

**The propagation path is the finding, not the docstring.** A peer campaign read the docstring
and relayed it as grounding. This campaign received it, treated it as verified because it named
a specific file and line, and wrote it into an out-of-scope section warning future readers not to
"fix" an unset category. Each hop added apparent confirmation and no new evidence. Had it
shipped, an accepted decision record would have carried a warning steering a reader away from
mapping a category the tree can express — **the warning would have been the hazard**, and it
would have been near-impossible to dislodge, because it was in a decision record and cited a real
file.

It was caught only because the peer campaign re-verified its own earlier claim against the enum
rather than restating it, and because this campaign then checked the enum directly rather than
accepting the correction on report. Both halves were necessary.

**The generalisable rule: a docstring is prose, not a checked artefact.** It carries no gate, and
nothing fails when it goes stale. A claim about what a closed value set *can express* must be
verified against the value set, never against prose describing it — and that holds however
precise the prose's file-and-line citation looks, because precision of citation is not evidence of
currency.

This is the third instance of one shape in this campaign: a wrong instrument or a stale framing
producing output plausible enough to ship. The other two were an accuracy metric read from the
wrong field of the right artefact, and a clock-in-a-derived-id pattern-matched to a rule breach
without reading what the clock was for. In all three the output was coherent, specific, and
wrong, and in all three the correction came from **re-measuring rather than re-reasoning**. A
finding that is more damning than expected is a signal to re-measure, not to write up.

## Disposition register against the source discovery

Built by enumerating the source discovery's findings independently, then checking each against
the campaign documents. **Silent drop** means: not actioned, and not declared out of scope
anywhere. Every row is now resolved — actioned with a Step id, or named in the ADR's
deliberately-out-of-scope section.

| Source finding | Original disposition | Resolution |
|---|---|---|
| Inverted privacy posture: text-layer to cloud with gestor barred, scan local | actioned | ADR D5, wave `W05` |
| The local provider never wired as a text reader | actioned | `S44` |
| Regex-versus-vision extraction fork | honestly open | D8; D7 removes most of its traffic |
| ZUGFeRD mishandled, embedded XML never opened | actioned | D7, `W02.P04` |
| Vacuous ZUGFeRD assertion checking only a German word | actioned | `S18` |
| Accept-then-refuse trap | partial, residue unnamed | XML closed by `S22`; CSV, XLSX, text and `.eml` now named out of scope |
| Ingest suffix gate refuses XML | **silent drop** | now `S22` |
| Dangling decision-record reference in an operator-facing refusal | **silent drop** | now `S68` |
| No normalization seam; resolved evidence is a tagged union | partial | shape probe in `S10`; the seam itself rides D8 and is now named out of scope |
| Seam must inherit the evidence-input custody discipline | **silent drop** | now named out of scope, with two obligations recorded for whoever builds it |
| Multi-rate IVA silent collapse | **not actioned, blocking sibling** | now `S67`, proven end to end by `S70` |
| Recargo absent from the extraction draft | **silent drop** | now owned here by agreement with the sibling lane |
| Retención correctly absent from the draft | correctly out of scope | unchanged; sibling owns it |
| Supplier name unreadable | **silent drop** | named out of scope; D7 recovers it for structured documents |
| Credit notes and rectificativas unreadable | **silent drop** | named out of scope |
| Foreign currency and the FX triple unreadable | **silent drop** | named out of scope |
| Series, operation date, payment terms, address, intra-EU VAT-ID | **silent drop** | named out of scope |
| Extraction has no allow-list; grounding is shape-only | acknowledged | D4 and D8 both cite it |
| Injection-through-markdown regression gate | out of scope, defensibly | now explicitly named as a precondition of any two-stage ADR |
| Printed-total discrepancy generalised beyond one entry path | **silent drop** | named out of scope |
| `evidence add` non-idempotent, breaching a codified rule | **silent drop** | now `S69` and `S71`, in the corrected keyed shape |
| Inverted caching: paid path uncached, free path cached | actioned by side effect | D5 deletes the uncached path |
| The extraction draft never persisted on either path | partial | `S59`, `S62` |
| Manifest merge discards the second observation's channel reference | **silent drop** | named out of scope, distinguished from the identity fix |
| No directory ingest, batch extract, batch confirm or resume | **silent drop** | named out of scope as scale verbs; this campaign clears their blockers |
| No ingest path sanitizes anything | **silent drop** | named out of scope with its reasoning |
| A decision record is owed for evidence-source expansion | answered in substance, undeclared | D7 now explicitly discharges the deferral |
| An amending record is owed for the cloud retirement | not done | now D5's supersession paragraph plus `S77` |
| Joint record with the sibling lane | actioned | cross-references verified accurate |

## Recommendations

Ranked. Each is tied to a finding above and each has been actioned; the Step ids are given so a
receiving team can check the work rather than redo it.

**1. Make the enumerated gate tier non-vacuous, before anything else.** Every entry in
`_SENSITIVE_SURFACES` must resolve to at least one non-test module or the gate fails naming the
entry. This protects all eighteen surfaces, not only this campaign's, and it must land before
any Step creates or empties a surface — an instrument repaired after the interval it was
supposed to police proves nothing about that interval. Prove the assertion itself by mutation:
point an entry at a nonexistent path and observe red. *Architecturally significant: this is a
decision about a shared enforcement instrument, not a campaign detail, and the governing ADR
records it as one.* Actioned as `S08`, `S09`, `S72`.

**2. Re-sequence every control that names the inference subpackage into the wave that creates
it.** The surface enumeration is the sole exception and lands *inside* the atomic commit that
creates the directory, because the interval between creation and enumeration is unguarded.
Actioned as `W04.P12` in full, with the enumeration riding `S32`.

**3. Enrol the subpackage in the layering contract rather than confirming it.** Add it to the
layer list and to the forbidden contracts that must catch a core or domain module importing it,
and verify by introducing a deliberate violating import and observing red. Do **not** set
`exhaustive = true`: that surfaces a much larger backlog belonging to no campaign. *Also
architecturally significant, and likewise recorded as a decision.* Actioned as `S73`, `S74`.

**4. Name the record the parsers target, and give it somewhere to put a per-rate breakdown.**
The extraction draft extended with a line set, crossing the confirm boundary unchanged so the
sibling campaign's plausibility gate keeps its placement. Actioned as `S67`, proven end to end
by `S70`.

**5. Declare the supersession and amend the superseded record's status in the same change as
the deletion.** Actioned as `S77`, with the provenance-stamp consequence as `S78`.

**6. Open the ingest front door for the formats the parsers read, and remove the dangling
decision-record reference.** Actioned as `S22`, `S68`.

**7. Add a deliberately-out-of-scope section naming every dropped finding.** Actioned in the
ADR; the register above is its evidence.

**8. Move the parsers to the inbound adapter layer** rather than recording why the application
layer is correct — the seven sibling packages settle it. Actioned across `S10`, `S13`-`S17`,
`S56`, `S57`.

**9. Fix evidence-record identity by adding a key, not by dropping the clock.** Actioned as
`S69`, `S71`, with the every-field comparison requirement carried explicitly.

**10. State gate coverage per check with its mechanism named.** Actioned as `S72` and in the
plan's verification section.

**11. Restate every quantitative claim with its key, sample size and provenance.** Completed;
the full trace lives in the measurement-basis reference for this feature, which is the document
to read before quoting any number from this campaign.
