# `llm-package-split` adr: `Local-inference document reading as a gated subpackage inside the trust boundary` | (**status:** `proposed`)

## Problem Statement

The document-ingestion-and-inference path is the only part of Cadrumo that is
probabilistic, hardware-dependent and privacy-sensitive, and it currently sits
undifferentiated inside a deterministic tax engine bound by `aeat-safety-legal-gates`.
Five separate problems trace to that co-location: model licence questions become
core-product blockers; the hardware floor is an undeclared precondition with no probe;
the transport a document takes — and therefore whether it leaves the host — is decided by
whether its PDF happens to carry a text layer; the extraction fork (regex for text,
vision model for scans) has no principled home; and probabilistic output flows into a
filing engine with no declared boundary at which it becomes reviewable data.

A decision is needed now because a proposal exists to lift the path into a separate
package, and the naive form of that proposal would move the code most likely to write a
temp file to the one place where the gates forbidding temp files do not look. What gets
decided here is the boundary's shape, not whether inference is worth having.

## Considerations

- The motivating claim that this decouples the product from `torch` is already satisfied.
  `2026-06-15-dependency-provisioning-adr` §4 relocated torch to `[dependency-groups] dev`
  as the vaultspec-rag backend; no `src/cadrumo/` runtime path imports it. The live
  argument is prospective: a transformers- or vLLM-served model would put a model runtime
  back in-process, and the product currently ships none (`pyproject.toml:181-187`, the
  retired `search` extra).
- Every AST gate enforcing secure-storage-only persistence scans `SRC_CADRUMO`, hard-coded
  as `src/cadrumo` in `src/cadrumo/tests/_inventory.py:11`. Code in a sibling top-level
  package is invisible to all five.
- `.importlinter:2` sets `root_package = cadrumo`; a sibling package participates in no
  layered contract. `aeat-architecture-boundaries` independently forbids new top-level
  packages.
- `EvidenceInput`'s tripwires (`_evidence_input.py:118-146`) block serialization, not
  attribute reads; `instance.data` returns decrypted bytes freely.
  `AttachmentStoreProtocol` is structural, so satisfying it proves call shape, not
  custody. The type system cannot carry this boundary.
- The optional-extra machinery is mature and uniform: `core/_optional_extras.py`,
  `require_optional_extra` at each adapter's lazy import, and the CLI degradation seam
  `_surface_for_import_failure` (`entrypoints/cli/__init__.py:907-947`).
- `2026-06-28-product-packaging-adr` fixes an exact-version three-distribution cohort and
  keeps optional integrations as capability extras, whose absence must yield install
  guidance rather than `ModuleNotFoundError`.
- Nothing outside the ledger uses the cloud subprocess transport; `src/cadrumo/agent/` has
  zero references. The on-host vision path reuses the shared prompt/parse machinery but
  does not depend on the cloud path.
- The cloud path is nonetheless the only way to classify a text-layer PDF today.
- No hardware-capability probe exists anywhere in the product.

## Considered options

- **A — sibling top-level package `src/cadrumo_llm/`, separate distribution.** Matches the
  proposal's literal wording. Gives the strongest dependency isolation. Rejected: it
  breaches `aeat-architecture-boundaries`, escapes every layering contract, and — decisively
  — removes the inference path from all five secure-storage AST gates precisely when that
  path is the one handling decrypted invoice bytes.
- **B — gated subpackage `src/cadrumo/llm/` behind an `llm` extra (chosen).** The code stays
  inside the gate corpus and the layering contract; the dependency closure is isolated by
  the extra, which is the mechanism the project already uses for five integrations. The
  distribution split remains available later without moving code.
- **C — leave the path where it is, add a hardware probe and fix the transports.** Solves
  the hardware and privacy findings without a boundary. Rejected: it leaves probabilistic
  inference undifferentiated inside the deterministic core, so the licence and
  quarantine problems remain, and nothing prevents the next model dependency from landing
  in the base closure.
- **D — subpackage now, separate distribution later as a fourth cohort member.** Not a
  rival to B but its sequel; recorded so the ADR's scope is explicit. Deferred, with the
  gate re-scoping named as its precondition.

## Constraints

- The gates are the boundary. Wherever the inference code lives, `SRC_CADRUMO`-scoped AST
  scanning must cover it. A future distribution split is conditional on re-scoping those
  gates first, in the same change.
- Decrypted evidence bytes stay in process memory and never persist outside secure storage
  (`2026-06-10-llm-evidence-classification-adr`, operator ruling, binding).
- `llm-selects-system-derives-tax-numbers` is unaffected: the regulated figures remain
  registry-derived regardless of which package reads the document.
- Extras absence must degrade to install guidance, never `ModuleNotFoundError`
  (`2026-06-28-product-packaging-adr`).
- Retiring the cloud path removes a live capability; sequencing is a constraint, not a
  preference.
- Frontier risk is low: no new library class is introduced. The one novel element is a
  hardware-capability probe, for which no in-tree precedent exists.

## Implementation

**D1 — the package boundary.** The inference path moves to `src/cadrumo/llm/`, a
subpackage of the existing root, gated by a new `llm` extra registered as an
`OptionalExtra` in `OPTIONAL_EXTRAS` (not hand-rolled like the `agent` extra, which sits
outside the shared classifier and is a precedent to avoid). The extra declares the
runtime packages the path actually needs — including `pypdfium2` and `Pillow`, which the
research found are relied on today without `Pillow` being declared anywhere but the dev
group. Guarding follows the established convention: `require_optional_extra(LLM_EXTRA)`
immediately before the lazy import, at the adapter boundary, converted to a domain error.

**D2 — the distribution boundary is deferred, not decided.** The extra isolates the
dependency closure, which is what the prospective torch argument requires. Splitting a
fourth distribution later is permitted only in a change that first re-scopes the five AST
gates to cover the new root. Recording this as a precondition is the point of the
decision.

**D3 — the trust boundary: the extension sits inside it.** The inference subpackage never
resolves secure storage itself. It receives already-resolved bytes in memory from the
core, and returns a typed result; it holds no repository handle, constructs no
`AttachmentStore`, and imports nothing from `adapters.persistence`. This is a discipline
enforced by the gates and by an import contract, not by the type system — the research
established the type system cannot carry it, since both `EvidenceInput.data` and a
structural `AttachmentStoreProtocol` hand over bytes freely. The three inference-scoped
stores that today write through `secure_object_repository_for_active_bucket`
(`_cache.py`, `_run_telemetry.py`, `_usage.py`) stay on the core side of the boundary,
which also preserves `application/diagnostics_run_health.py:71` — a core, non-ledger
consumer of run telemetry that must not become conditional on an optional install.

**D4 — the output shape is a typed validated payload, never free text.** The core accepts
a single strict model (`extra="forbid"`, closed key set, `STRICT_FROZEN_CONFIG`) and
refuses a malformed one at the boundary rather than coercing it. Markdown or raw model
text may exist *inside* the extension as an intermediate, but it is never the interchange
value: handing free text to the core would make the boundary a laundering channel rather
than a validation point, and the ingestion research established that promoting hostile
document text across a stage boundary is where prompt injection gets worse, because
extraction fields have no allow-list the way classification categories do. Every field
carries the shape-grounding the vision path already applies (checksum-valid tax id,
parseable date, finite decimal), and the payload carries its own provenance: `legal_refs`
and `source_refs`, the typed source kind, and the model identity and revision that
produced it, so a persisted record can always answer how each field was recovered.

**D5 — the cloud subprocess path is deleted, sequenced behind local text inference.**
Under a local-only extension the cloud branch is the only inference left inside the
deterministic core and the only path able to send taxpayer documents off-host, which is
the inversion this ADR exists to remove; `no-legacy-compatibility` forbids keeping it
dormant as a bridge. But it is today the only reader for text-layer PDFs, so the deletion
lands *after* a local text reader is wired, not before. The orphan set is then removed in
one change: `cloud_evidence_read_permitted`, `ServiceCapability.CLOUD_EVIDENCE_UPLOAD` and
its `resolve_capability` branch, `cadrumo_evidence_gestor_mode` and
`cadrumo_evidence_cloud_upload_permitted`, `--evidence-acknowledged`, `--llm`, the
subprocess builder family, `probe_subprocess_providers`, and `aeat app ledger providers`.
The shared prompt/parse machinery survives untouched because the local vision classifier
already reuses it.

**D6 — the third capability axis.** The product distinguishes *installed*
(`OptionalExtra`) from *permitted* (`ServiceCapability`); it has no notion of *capable*.
The extension declares a hardware floor and a probe reporting it through the existing
`DependencyStatus` shape into `aeat config check`, so an under-specified machine gets a
typed refusal naming the shortfall instead of a model that fails to load or thrashes.

## Rationale

Option B wins on a knockout criterion rather than a balance of factors. The purpose of
moving inference out of the core is to contain risk. Option A would relocate the code
that handles decrypted invoice bytes to the only place in the repository where the AST
gates forbidding temp files, plaintext side stores and unreviewed writes do not look, and
where no layering contract applies. That inverts the goal: the most sensitive code would
become the least supervised. No amount of dependency isolation compensates, because the
isolation Option A buys over Option B is a packaging property, while what it gives up is
an enforcement property.

Option B delivers what the proposal actually needs. The dependency closure is isolated by
the extra — that is precisely what keeps a future torch-bearing model off a default
install. The licence question narrows to an opt-in component. The hardware floor becomes a
declared property of an installed extra rather than a hidden precondition. The privacy
inversion disappears with D5. And the extraction fork resolves because the extension owns
one reading path rather than two transports chosen by file format.

Option D is not foreclosed. Because the extra already isolates the closure, the
distribution split becomes a mechanical follow-on whenever it is wanted — conditional on
re-scoping the gates, which is the honest price and is now written down rather than
discovered later.

## Consequences

Gains: probabilistic work is quarantined behind an opt-in boundary while remaining under
every gate that protects sensitive bytes; a default install loses no deterministic
capability; the undeclared `Pillow` dependency is forced into the open by the extra's
explicit declaration.

Costs, stated honestly. The split line runs through
`application/ledger/_llm_classification.py`, 1606 lines mixing inference with core writes
(`set_classification`, bucket-event history, split persistence, the consent gate); it must
be divided rather than moved, and that division is the largest single piece of work here.
`_llm_review_workflow.py` depends only on the apply/reject functions inside that module,
so it cannot settle until the division does. Deleting the cloud path touches 24 test
files, nine deletable wholesale and the rest needing case-level edits because
`_resolve_evidence` branches internally.

The regression risk is real and named: between the cloud deletion and a working local text
reader there is a window in which text-layer PDFs cannot be classified at all. D5 sequences
against it, and the plan must not reorder those steps for convenience.

The pitfall most likely to bite is not architectural but procedural. The
`llm-invoice-read-reconciliation` research records three deliverables that shipped correct,
tested and unreferenced, because a unit test passes whether or not anything calls the code.
A package migration is that failure mode at larger scale: every moved module can be green
while the core still routes around it. Each step needs an enrolment gate proving the core
call site reaches the moved code — not merely that the moved code works.
