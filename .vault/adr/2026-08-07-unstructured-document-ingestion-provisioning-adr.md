---
tags:
  - '#adr'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:36f906f61536bd78c98e3a67e5e20c0245b58f683751808be2bd4a7486151d63'
related:
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `unstructured-document-ingestion` adr: `Model provisioning, adaptive selection, and the cadrumo[llm] distribution boundary` | (**status:** `proposed`)

## Problem Statement

The ingestion pipeline the sibling ADR decides runs on local models, and the
operator's finding is that nothing real stands underneath them: "there is no
'real local' provider that is capable of pulling, starting, checking hardware
requirements, system resource state contentions, exponential backoff, managing
resource contentions, or adaptive model options based on hardware requirements,
nor is there any real wiring with the packaging and deployment lanes." The
operator's second, repeatedly raised concern is packaging: "we're shipping the
llm and classification lanes as a bundled feature into the cadrumo core
package... think of cadrumo as cadrumo[core]... perhaps bundling the
programmatic canonical schema-driven OCR, xml, csv and pdf parsing is core but
the llm vision wrangling, provisioning is a cadrumo[llm] extra."

Ground state at HEAD, verified by reading the epicentre whole rather than
assumed: `application/provisioning.py` exists and carries typed
`DependencyStatus` probes — Ollama reachability plus model presence
(`probe_ollama_vision`), Playwright, the optional-extras walk, and
`probe_model_runtime_hardware_floor`, a **total-system-memory** floor check.
`LLM_EXTRA` is already registered in `core/_optional_extras.py`
(`OPTIONAL_EXTRAS`), guarded by `require_optional_extra` with an instructive
`MissingOptionalExtraError` install hint, and `aeat config check` renders all
of it. What does NOT exist, and is this record's subject: any accelerator or
VRAM awareness, any *free*-resource or live-contention measurement, any model
catalogue or hardware-adaptive selection, any licence axis, any model pull or
lifecycle verb, any retry or backoff semantics, and any packaging-lane proof
of the absent-extra behaviour on the inference surfaces.

The motivating case for contention detection is live and current: the
development machine shows under 4 GB free of 16 GB at 100 % GPU utilisation
under a resident service, and every agent has been prohibited from inference
all session because nothing in the product can answer whether a load is safe.
A provisioning layer that cannot answer that question on the machine it was
designed on has not answered the question.

The licence finding makes selection more than an ergonomics feature: the
shipped default vision model `qwen2.5vl:3b`
(`core/_config_runtime_fields.py:40`) carries a research licence barring
commercial use, while `qwen3-vl:2b` is Apache-2.0 and measured equivalent on
the corpus — and the settings docstring says nothing about licence at all. A
tax-filing product whose default inference model may not be used commercially
is a shipping defect, not a preference.

## Considerations

- **The canonical home already exists.** `application/provisioning.py` is the
  read-only doctor authority and `aeat config check` its renderer; the
  dependency-provisioning ADR (accepted) fixed the contract: probe → typed
  refusal or Notice with the exact remediation → opt-in provisioning. This
  record extends that surface; a parallel provisioning package would be the
  duplicate-authority failure the discovery mandate exists to prevent.
- **The packaging cohort is accepted and binding.**
  `2026-06-28-product-packaging-adr`: one exact-version three-distribution
  cohort; models, browser binaries and credentials are operator-provisioned
  capabilities, never package data; optional integrations are capability
  extras whose absence yields declared install guidance, never
  `ModuleNotFoundError`.
- **The subpackage boundary is decided; the distribution question sits on top
  of it.** `2026-08-06-llm-package-split-adr` chose `src/cadrumo/llm/` behind
  an `llm` extra (its Option B) and explicitly deferred a separate
  distribution (its D2) behind re-scoping the persistence gates. The
  operator's `cadrumo[llm]` ask is satisfiable by the extra without touching
  that deferral.
- **The existing floor probe is diagnostically honest but load-unsafe.**
  `probe_model_runtime_hardware_floor` measures *total* memory and reports
  unknown as available — the right direction for a report row, the wrong
  direction for deciding whether to load three more gigabytes into a machine
  with under four free. Reporting and acting need opposite failure
  directions, and conflating them is how the current prohibition became
  necessary.
- **Ollama exposes what contention detection needs.** `/api/tags` (already
  probed) lists pulled models; `/api/ps` lists *resident* models with sizes;
  free system memory is readable by the same `ctypes`/`sysconf` route the
  total already uses; NVML answers free VRAM where an NVIDIA accelerator
  exists. No new daemon and no vendor lock is required for the first tier.
- **`ANTHROPIC_EXTRA` is already separate from `LLM_EXTRA`.** The cloud SDK
  and the local-inference closure are independently installable, which the
  boundary below preserves: a local-only install never pulls a cloud SDK,
  and a consented-cloud install never needs Pillow.
- **The sibling ADR's D8/D8a govern the cloud interaction.** Degradation
  design here must not become a route around the reinstated consent gate.
- **Injectable observed values are parameters, not mocks.**
  `probe_model_runtime_hardware_floor(total_memory_bytes=...)` is the shipped
  precedent: every probe takes its measurement as an optional argument so CI
  tests real logic against real values without patching, keeping the
  no-mocks discipline intact for a subsystem whose inputs are hardware.

## Considered options

- **A — leave provisioning implicit: settings docstrings advise, operators
  pull models by hand, inference fails raw on contention.** The status quo
  minus the probes that exist. Rejected: it is the measured failure — the
  fleet-wide inference ban exists because nothing can answer the safety
  question, and a docstring cannot flip a licence default.
- **B — a provisioning authority extending the existing probe layer, with a
  typed model catalogue, live contention detection, explicit lifecycle verbs,
  and the extra as the distribution boundary (chosen).** Builds on the
  accepted doctor contract and the registered extra; every piece is
  deterministic and CI-testable.
- **C — own the model runtime: ship or supervise the Ollama daemon,
  auto-start it, auto-pull models on demand.** Rejected: the packaging ADR
  places runtimes and models on the operator side of the line; a multi-GB
  download or a daemon spawn as a side effect of `calculate` is exactly the
  implicit behaviour the doctor contract replaced with instructive refusals;
  and process supervision drags in a platform-service problem this product
  does not need.
- **D — a separate `cadrumo-llm` distribution now.** Rejected here without
  prejudice: package-split D2 already defers it behind gate re-scoping, and
  the operator's stated need — core does not carry the inference closure —
  is met by the extra.

## Constraints

- No agent may load, pull, or invoke a local GPU model while designing or
  building this; the contention detector's own development runs against
  injected measurements and the live probe endpoints only.
- The consent gate of the sibling ADR's D8a binds every degradation path;
  nothing here may route an unconsented request off-host.
- The packaging cohort is immutable: no model bytes, no runtime binaries in
  any wheel; `cadrumo.core.resources` remains the only resource access path.
- The doctor surface stays read-only; provisioning actions live behind
  explicit verbs. The CLI root surface stays `config` + `app`.
- Regulated values are unaffected: model choice never alters a tax figure,
  and the catalogue is deployment configuration, not registry data.
- Licence claims about specific models must be verified against the
  publisher's licence text when the catalogue is authored, not inherited
  from this record's prose.

## Implementation

### D1 — one provisioning authority, extended in place

All new capability lands in the existing `application/provisioning` surface
and its `aeat config check` renderer. New probes follow the shipped shape:
typed result models, injectable measurements, never raising on absence,
remediation strings naming the exact command. No second home, no parallel
"llm doctor".

### D2 — the hardware profile: totals for reporting, free amounts for acting

A typed `HardwareProfile` carries total AND free system memory, accelerator
presence and kind, and total AND free VRAM where an accelerator is readable.
System memory extends the existing `ctypes`/`sysconf` readers with the free
counterpart they already fetch structurally (`ullAvailPhys` is in the struct
the Windows reader fills today). VRAM reads through NVML (`pynvml`), declared
in the `llm` extra; absent NVML or a non-NVIDIA accelerator reports
`unknown`, and the *diagnostic* rows keep the shipped direction — unknown is
reported as unverified, never manufactured into a shortfall.

### D3 — live contention detection, fail-closed at the act

Before any model load — the first inference against a model not currently
resident, and any explicit pull-and-run — a contention check compares the
selected model's declared memory requirement plus a configured safety margin
against measured free headroom (free RAM, free VRAM when readable) and the
runtime's resident set (`/api/ps`). Insufficient headroom is a typed
contention refusal naming the resident models, the observed free figures and
the requirement — never a thrash, never an OOM kill mid-read. **Acting fails
closed where reporting fails open:** an *unreadable* free figure on a machine
whose total is also unknown refuses the load with a remediation naming the
override setting, because "could not tell" is precisely the state that
destroyed running work on this machine. The check runs at the same
`llm/_client.py` dispatch choke point as the capability and consent
boundaries, so no primitive reaches inference around it. The motivating
acceptance case is executable without inference: against the current
machine's live readings, the detector must refuse, and against injected
post-quiesce readings, it must permit.

Admission control is the full shape, not the single check. **Concurrency is
bounded:** a configured in-process concurrent-inference limit (default one)
queues or refuses further requests with a typed busy refusal, because two
concurrent vision reads on consumer hardware are the same OOM by another
route. **A peer process holding the device is a first-class observation, not
an error:** the contention snapshot distinguishes the runtime's own
residents (`/api/ps`) from other processes' device usage (a free-VRAM
shortfall not explained by residents), and the refusal names which is which,
because the remediation differs — unload a model versus close another
application. **Teardown under pressure is explicit and self-scoped:** the
provision verb family gains an unload action for Cadrumo-selected models,
the contention refusal names it when residents explain the shortfall, and
Cadrumo never evicts or interferes with another process's device usage —
pressure caused by a peer is reported and refused, never "managed".

### D4 — the typed model catalogue and adaptive, licence-aware selection

A single typed catalogue declares, per model role (vision transcription, text
extraction, tabular mapping), the candidate models with: runtime identifier,
declared memory requirement, licence (SPDX identifier plus an explicit
commercial-use-permitted flag, verified against the publisher's text at
authoring), and a reference to its measured corpus baseline where one exists.
Selection resolves a role to the best candidate whose requirement fits the
measured hardware tier AND whose licence permits the deployment posture; the
operator's explicit model setting overrides selection but never silently —
an override naming a non-commercial-licence model surfaces a visible licence
advisory. **The shipped default flips as a consequence of the licence axis:**
`qwen2.5vl:3b` (research licence, commercial use barred) cannot remain the
default of a commercial tax product while `qwen3-vl:2b` (Apache-2.0) is
measured equivalent; the catalogue records both, the default selects the
Apache-2.0 candidate, and a licence gate asserts no default candidate in any
role carries a commercial-use bar. The catalogue is deployment configuration
with one home beside the settings it informs — not registry data (it encodes
no tax semantics) and not scattered docstring prose (the current state, where
the licence constraint is invisible).

**Selection is bounded from below, not maximised.** By operator directive
the design point is the weakest vision-capable model that clears the
capability bar — the 2B–4B on-host class, with the cloud Haiku tier as its
measurement proxy — never the strongest model the hardware could hold. The
catalogue's quality reference for each candidate is its measured baseline
at that discipline, and an operator override upward is a choice the
selection surfaces, not a default it drifts toward.

**Per-model parameter support is a first-class capability axis, beside
vision support.** Two shipped defects share one shape — a request field the
transport assumed universal: the `images` field silently dropped by three
of four adapters until the `supports_images` boundary landed, and
`temperature` sent unconditionally (`llm/_providers/anthropic.py:195,204`,
populated always by `llm/_client.py:156-159`), which current top-tier
models reject with a 400, so the product can presently reach only Sonnet
4.6 and older. The provider capability model therefore declares, per
adapter and per model where vendors differ, which request parameters are
supported; the dispatch omits unsupported parameters rather than sending
assumed defaults, and the capability declaration is data enforced at the
same single dispatch point as the image and consent boundaries, proven the
same way (send the unsupported field, observe the typed refusal, never the
vendor 400).

### D5 — lifecycle: explicit verbs, no implicit pulls, no daemon ownership

A verb family under the existing `config` root — `aeat config provision` —
owns the actions: report (the doctor rows plus the hardware profile and a
contention snapshot), model pull (per role or per model, with progress,
resumable via the runtime's pull API, contention-checked before any
post-pull load), and readiness verification (model resident and answering a
trivial prompt within a bound). The runtime daemon itself stays
operator-owned per the packaging ADR: an unreachable runtime is an
instructive refusal naming `ollama serve`, never a spawn. Inference paths
never pull implicitly — a multi-gigabyte download is an explicit operator
action, and the inference-time behaviour on a missing model remains the
typed refusal naming the provision verb.

Deinstallation is the same verb family run backwards, and it is designed
rather than assumed: a remove action deletes a pulled model through the
runtime's delete API and reports the freed bytes; removing the `[llm]` extra
is a package operation (`pip uninstall` of the extra's closure) after which
every guarded surface returns to the instructive install refusal — that is
the already-tested absent state, so deinstallation cannot strand a
half-working surface. What removal never touches: persisted records.
Transcriptions, drafts, provenance stamps and classifications derived from
model reads remain valid history — a stamp naming a removed model is honest
provenance, not a dangling reference — and the doctor reports a
partially-installed state (extra present but models unpulled, or models
resident for an absent extra) as its own detectable row with the remediation
in whichever direction the operator intends.

### D6 — retry and backoff, scoped to the transient

The `LLMClient` transport gains a typed retry policy: exponential backoff
with jitter and a bounded total budget, applied only to transient transport
failures (connection refused or reset during model load, HTTP 5xx from the
runtime, read timeout on a model that `/api/ps` shows still loading). Never
retried: schema-validation refusals (retrying a semantic failure launders
it), contention refusals (the condition does not decay on a timer it decays
when load changes), consent refusals, and capability refusals. The policy is
data on the client, visible in the request record, and CI-tested against a
real local HTTP server exhibiting each failure shape.

### D7 — degradation that cannot launder the consent gate

Local runtime unavailable, model unpullable, hardware below floor, or
contention standing: each yields its typed refusal with the exact
remediation. Where the deployment has the cloud route configured and the
surface is consent-eligible, the refusal MAY name the gated cloud
alternative in its remediation prose — but degradation never *selects* it:
there is no automatic fallback from a local failure to an off-host read,
because an outage must not convert into an unconsented upload. The consent
gate of the sibling ADR's D8a is upstream of any cloud dispatch regardless
of why the dispatch was attempted.

### D8 — the `cadrumo[llm]` boundary: the operator's cut, tested and adopted

Core (a default `cadrumo` install, no extras): every deterministic reading
surface — the e-invoice XML parsers (Facturae, EN16931 CII and UBL,
VeriFactu/SII), PDF text-layer extraction, tabular dialect normalization and
deterministic row projection, the S3 grounding stage, the shape probe, the
draft and transcription contracts, and the provisioning *probes* (the doctor
must be able to report an absent extra). The `[llm]` extra: everything
model-bearing — vision wrangling and rasterisation handoff, semantic
extraction, classification, the tabular mapping *call*, prompt and
model-response machinery, and the NVML-backed hardware detail. The cut lands
awkwardly in three places, named rather than smoothed: S3 grounding is core
even though it exists chiefly to check model output (correct — it equally
grounds structured parses and operator input); the tabular lane splits
mid-pipeline (a known fixed-layout file imports fully with no extra; an
unknown vocabulary reaches the point of needing the mapping call and refuses
with the install hint); and the hardware profile degrades to `unknown`
detail without the extra while the row itself stays core.

Absent-extra behaviour is the shipped prior art, uniformly applied: every
`cadrumo.llm` entry point sits behind `require_optional_extra(LLM_EXTRA)`,
surfaces stay visible and discoverable, and invocation without the extra is
one instructive `MissingOptionalExtraError` naming
`pip install cadrumo[llm]` — never a `ModuleNotFoundError`, never a silently
absent verb. What never crosses the boundary: core and domain never import
`cadrumo.llm` outside the guarded lazy seam (the import-linter enrolment the
package-split ADR's D12 mandates); the extra holds no storage handle (its
D3); `ANTHROPIC_EXTRA` stays a separate extra so the local closure and the
cloud SDK remain independently installable. The separate `cadrumo-llm`
*distribution* remains deferred exactly as package-split D2 left it, behind
the persistence-gate re-scoping precondition; this record satisfies the
operator's core-versus-extra requirement without reopening it.

### D9 — packaging and deployment wiring

The `[llm]` extra's dependency list is completed (Pillow per the
package-split ADR's finding, `pynvml` for D2, and any future model-runtime
SDK), and the packaging smoke lanes gain an absent-llm lane: install the
core wheel cohort without the extra, drive every inference-adjacent surface,
and assert each refusal is the declared install guidance — proving at the
artifact level what `require_optional_extra` promises at the source level.
`aeat config check` gains the new rows: accelerator and VRAM, the contention
snapshot, and the per-role selected model with its licence. No wheel gains
model bytes; the cohort contract is untouched.

## Rationale

Option B wins because both halves of the operator's ask are extensions of
surfaces the corpus already accepted: the doctor contract (probe, typed
refusal, opt-in provisioning) generalises directly to contention and
lifecycle, and the extras machinery already carries the exact absent-extra
behaviour the packaging ADR requires — the work is to make them real on the
inference path, not to invent a frame. Option C fails on an accepted ADR's
line (operator-provisioned runtimes) and on the implicit-side-effect
principle the doctor contract replaced. The fail-closed direction for D3 is
the one measured lesson this machine keeps teaching: the cost of refusing a
safe load is a retry after quiesce; the cost of permitting an unsafe one was
four terminated agent sessions and a session-long fleet prohibition.

The licence-aware catalogue is the smallest structure that makes model
choice a decision instead of a docstring: hardware fit and licence are both
hard constraints, they interact (the smallest model is not always the
permitted one), and neither is visible today at the point of choice. Making
the default flip fall out of catalogue data rather than a one-off edit is
what keeps the next licence surprise a data change with a red gate instead
of an incident.

## Consequences

**Gains.** The session-motivating question — is a load safe on this machine
right now — becomes answerable and enforced at the choke point. The
commercial-licence defect in the shipped default is closed structurally. A
default install carries no inference closure, satisfying the operator's
`cadrumo[core]` framing, while every deterministic reading lane keeps
working. Provisioning becomes an explicit, reportable, testable operator
surface wired into the packaging smoke lanes.

**Costs and risks.** NVML covers only NVIDIA; other accelerators report
unknown VRAM and fall back to system-memory headroom — stated, not solved.
Declared model memory requirements are estimates; the safety margin setting
absorbs estimate error and is tunable per machine. The fail-closed D3
direction will refuse on machines that cannot report free memory until the
operator sets the override — an ergonomic cost accepted deliberately. The
default-model flip changes measured-baseline continuity: the harness lane
must re-baseline on the new default, and results name their model identity
precisely so the discontinuity is visible. Retry semantics add a bounded
latency tail to genuinely-down runtimes.

**Coupling.** The sibling pipeline ADR's D8/D8a own the cloud gate this
record's degradation must respect; its D9 harness lane owns every model
quality figure. The package-split ADR's D2 deferral and D12 enrolment are
consumed unchanged. The dependency-provisioning and product-packaging ADRs
are extended, not contradicted.

**Deliberately out of scope.** Daemon supervision and service management;
non-NVIDIA VRAM probing; *automatic* model eviction (D3's teardown is an
explicit operator unload of Cadrumo-selected models, never a background
eviction, and never another process's memory); GPU scheduling across
concurrent agents (a development-fleet concern, not a product concern); and
the separate `cadrumo-llm` distribution, which stays behind package-split
D2's precondition.

## Codification candidates

None. The accepted doctor contract, the packaging ADR's extras rule,
`no-silent-under-declaration` (the fail-closed act direction) and
`aeat-architecture-boundaries` govern everything here; the durable artefacts
are the licence gate and the contention refusal, carried as executable gates.
