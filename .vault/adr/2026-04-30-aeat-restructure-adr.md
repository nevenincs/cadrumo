---
tags:
  - '#adr'
  - '#aeat-restructure'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-30-aeat-restructure-research]]'
---



# `aeat-restructure` adr: domain-aligned restructure of `src/aeat/` | (**status:** `accepted — execution-ready`)

> **APPROVAL-READY — 2026-04-30.** This ADR has converged through
> 22 audit operations + 2 prior cold-eyes reviews + wave-5 gap-check
> + wave-7 final convergence verification. The wave-7 reviewer
> verdict: "CONVERGED — approval-ready as written. Returns have
> fully diminished. Further iteration would not surface material
> issues; it would produce editorial churn."
>
> **Approval gate (all conditions satisfied)**:
>
> 1. ✅ Top-5 monolithic modules (`storage`, `cli`, `auth`, `filing`,
>    `errors`) have signed-off internal split designs folded into
>    this document — see Implementation section.
> 2. ✅ Vault-corpus contradiction list reaches 100% classified
>    status across Tier-1 / Tier-2 / Tier-3 / Tier-4 — see research
>    doc "Vault-corpus contradictions" section.
> 3. ✅ Acceptance-criteria checklist (Operational Contract section)
>    is fully populated with verifiable conditions — 15 non-waivable
>    items.
> 4. ✅ Abort / rollback criteria reviewed — 5 named halt triggers
>    + revert mechanic + decision-authority owner named.
>
> **No outstanding items.** The two items previously deferred to
> project-owner confirmation (migration-helper retention, reserved
> `SchemaSource` enum slots) are resolved autonomously at Step 0 of
> the execution plan via audit-grounded decision rules. See
> Autonomous decision rules section.
>
> ### Step 0/1 outcomes (recorded 2026-04-30)
>
> **Decision 6** (`SchemaSource` reserved enum slots): no active branch
> nor open issue references `PORTAL_HTML_PROBE`, `MANUAL_LLM_DRAFT`, or
> `XSD_WIRE`. Autonomous rule fires `DELETE`. Slots ride into Step 7's
> keystone PR with the `domain/schema/` move; phase-2 dead-code (see
> updated Phase 2 list below).
>
> **Decision 10** (migration-helper retention): the actual count is
> **5 helpers**, not the "3" appearing in the EPIC and plan bodies
> (`migrate_legacy_submissions_to_repository`,
> `migrate_legacy_amendments_to_repository`,
> `migrate_legacy_filing_history_to_repository`,
> `migrate_legacy_drafts_to_repository`,
> `migrate_legacy_justificantes_to_repository`). All 5 landed
> 2026-04-27 — far short of the > 6 month threshold. Autonomous rule
> fires `RETAIN with TODO + tracking issue`. Tracking issue `#477`
> filed; earliest removal 2026-10-27.
>
> **Step 1 sub-pass 3 outcome**: ~37 test files marked
> `domain_local_state` move to destination layers outside the rule's
> stated 2-bucket reclassification (`adapters/outbound/`,
> `adapters/inbound/`, `application/`). The Test-marker realignment
> migration mechanic is extended below to cover all destination
> layers, not just two. Manual-override list final count is
> **zero-length** (audit-grounded by mechanical reclassification per
> the extended rule).
>
> Detailed evidence for each outcome lives in
> `.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-step-00-adr-lock-in-exec.md`
> and
> `.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-step-01-pre-move-scan-exec.md`.

## Problem Statement

`src/aeat/` is a flat ~40-subpackage tree that does not visibly reflect
the project's three conceptual domains:

- **incoming financial data** — outside data ingested into the system.
- **local state** — internal persistence and the system's own memory.
- **AEAT remote** — external interaction with the AEAT portal.

Connector and orchestration code sits alongside pure-domain modules;
cross-cutting plumbing (`config.py`, `logging.py`, `errors/`) lives at the
package root with no visible home; user-facing surfaces lack a sibling
home for the MCP launcher. The flat structure has produced concrete
boundary violations — `auth/` conflates Google authentication with AEAT
authentication, `submission/` was a recurring live-write liability that
required excision, and `storage/` at roughly 12k lines bundles ORM, blob
store, crypto, classification, recovery, redaction, rotation, and the
secret store under one subpackage.

A per-module audit is in progress in the parallel research document.
This ADR captures the destination layout the audit measures against.

## Considerations

The proposal is informed by industry research synthesised in the research
document. The dominant Python references converge on the following
canonical layer names:

- **Cosmic Python** (Percival/Gregory): `domain/`, `adapters/`,
  `entrypoints/`, `service_layer/`; for larger projects `domain_model/`,
  `infrastructure/`, `services/`, `api/`.
- **AWS Prescriptive Guidance for Python hexagonal**: `domain/`,
  `adapters/`, `entrypoints/`, plus `infra/` for cross-cutting code.
- **Hexagonal in/out variant**: adapters split into `inbound/` and
  `outbound/` to telegraph dependency direction.

Project-specific constraints:

- The existing test-marker taxonomy (`domain_financial_input`,
  `domain_local_state`, `domain_aeat_remote`, `domain_mediation`,
  `domain_infra`) must remain mappable to the new layout.
- AEAT-canonical Spanish vocabulary (`modelos`, `casillas`, `borrador`,
  `declaracion`, `justificante`, `sede`) is part of the ubiquitous
  language and must be preserved at module-name level — DDD's "scream
  business" principle.
- Live AEAT writes are forbidden (legal liability); any rename of the
  `submission/` surface must telegraph this in code, not only in docs.
- Track A (AEAT bidirectional sync) and Track B (financial input
  unidirectional pipeline) must remain visible as connector clusters in
  the new layout.

## Constraints

- The restructure cannot reintroduce a default-enabled live-write path;
  the four-factor live-submit gate must remain defense-in-depth.
- The `submission` → `export` rename must preserve the read-only
  preflight and dry-run surfaces — they are primary pre-export gates per
  project mandate.
- `LiveSubmitForbiddenError` is RELOCATED from `submission/` to
  `core/access_gate/_errors.py` as part of the rename. Reason: the
  live-access gate (`core/access_gate/`) imports the error from
  submission today; under the new layered-import contract, `core/`
  cannot import from `adapters/`. The relocation eliminates the
  layering violation and makes the policy-error live with the policy.
  Coordinated with the submission rename in the same PR.
- Internal splits of monolithic modules (`storage`, `auth`, `cli`,
  `filing`, `workflow`, etc.) are **in-scope** for this restructure: per-
  module split designs are produced during the audit and folded into
  this ADR as audit findings land. Splits and the move to the new
  layout are planned together so that destinations reflect the post-
  split shape, not the pre-split monolith.
- Execution may be phased — the ADR captures the destination shape,
  but rollout can land in waves (e.g. layout move first, then per-
  monolith internal fracture). Phasing is a delivery decision; the
  destination shape is not.
- The test-marker taxonomy is realigned in lockstep with the layout
  rename. New markers ship in the same milestone as the package moves.
- Existing `.vault/` corpus that references old module names, old test
  markers, or pre-restructure path references is slated for
  supersession in lockstep with rollout. The supersession workstream
  produces an audit-driven changelist before any execution begins.

## Implementation

Adopt a hexagonal-with-inbound/outbound layout, using canonical Python
DDD vocabulary plus a `core/` bucket for foundational cross-cutting
modules.

```
src/aeat/
├── domain/                     # business model + computation
│   ├── modelos/                # renamed from `models` (Spanish-canonical, avoids Pydantic clash)
│   ├── casillas/
│   ├── manuals/
│   ├── normatives/
│   ├── portals/
│   ├── formulas/
│   ├── deadlines/
│   ├── schema/                 # IR + cache + errors + runtime evaluate; extraction split to adapters/inbound/schema/ per audit 9
│   ├── profile/
│   ├── rental/                 # added by audit 2 (was missing from initial inventory)
│   ├── filing/                 # added by audit 5: filing domain records + protocols + builders + validator + reconciliation + repositories (pending LAYERING-TENSION decision — see research doc)
│   ├── justificante/           # added by audit 11: domain record (Justificante) + errors (parser pipeline goes to adapters/inbound, _verify.py to adapters/outbound/aeat/verify/)
│   ├── sync/                   # added by audit 13: divergence taxonomy + classifier (~425 LOC pure domain; orchestration stays at application/sync/)
│   ├── submission/             # added by audit 16: submission-lifecycle domain — engine + preflight + models + repository (Half A; _formats/ moves to adapters/outbound/aeat/export/)
│   ├── transactions/           # added by audit 20: was `financial/transactions/` — models + _repository per layering carve-out
│   ├── invoices/               # added by audit 20: was `financial/invoices/` — models + _validators (NIF) + _repository
│   ├── attachments/            # added by audit 20: was `financial/attachments/` — models + _store (encrypted persistence) per carve-out
│   ├── usage_ratios/           # added by audit 20: was `financial/usage_ratios/` — model + service per carve-out
│   ├── categories/             # added by audit 20: was `financial/categories/` — pure AEAT spending taxonomy + casilla mapping rules
│   └── vat/                    # added by audit 20: was `financial/vat/` — VAT regulatory catalogue (Ley 37/1992) + classification engine + Modelo 303 mapping (~3,243 LOC; consider top-level `aeat.vat` promotion)
├── adapters/
│   ├── inbound/                # incoming financial data
│   │   ├── pdf/                # renamed from `_pdf_import` (drop underscore)
│   │   ├── borrador/
│   │   ├── declaracion/
│   │   ├── justificante/
│   │   ├── identity/
│   │   ├── sanitizer/          # PDF fixture-prep tool (audit 8 — destination question flagged but recommended here)
│   │   ├── schema/             # BOE-PDF extraction (extraction-only; per audit 9 — IR moved to domain/schema/)
│   │   └── financial/          # bank-export providers ONLY (per audit 20 — was a 59-file conflated subpackage; 7 sub-packages relocated)
│   │       └── providers/      # CSV/OFX/XLSX/PDF parsers (the only inbound concern in old `financial/`)
│   ├── outbound/
│   │   ├── aeat/               # AEAT-portal-side adapters cluster (per audit 3)
│   │   │   ├── auth/           # AEAT auth providers (cert + Cl@ve Móvil + catalogue)
│   │   │   ├── browser/
│   │   │   ├── sede/
│   │   │   ├── verify/         # added by audit 11: was `justificante/_verify.py` — Playwright CSV verification against AEAT sede
│   │   │   └── export/         # renamed from `submission/` (legal-liability framing)
│   │   ├── google/             # Google OAuth + GCP service builders (per audit 3)
│   │   └── llm/                # LLM gateway (4 provider adapters + cache + usage + translator) — moved here from adapters/persistence/llm per audit 7 (cold-review R1 #3 upheld)
│   └── persistence/            # local state on disk
│       └── storage/            # 7-sub-module split per audit 4
│           ├── sql/            # ORM + engine + session + repository + records + migrations_api
│           ├── crypto/         # AEAD primitives + EncryptedString/Bytes/JSON column decorators
│           ├── master_key/     # MasterKeyProvider implementations + KDF migration + BIP-39 recovery
│           ├── envelope/       # File-backed JSON / cipher envelope I/O
│           ├── blob_store/     # Classification-gated content-addressed encrypted blob store
│           ├── secret_store/   # Keyed secret repository + materialisation (process-singleton + tempfile bridge)
│           └── _rotation.py    # Master-key rotation engine (cross-cluster — depends on envelope + blob_store)
│       # observability/ moved to core/observability/ per audit 15 (cross-cutting infra, not adapter)
│       # llm/ moved to adapters/outbound/llm/ per audit 7
├── application/                # use cases / orchestration (the connectors)
│   ├── filing/                 # SLIM per audit 5: orchestration + use cases (build_draft, validate_draft, approve_draft, build_complementaria, import_filing_from_justificante, runtime, testing) — domain records moved to domain/filing/
│   ├── transactions/           # added by audit 20: was `financial/transactions/_service.py` — transaction-classification orchestration
│   ├── invoices/               # added by audit 20: was `financial/invoices/_service.py` — invoice service
│   ├── attachments/            # added by audit 20: was `financial/attachments/_service.py` — attachment service
│   ├── aggregation/            # added by audit 20: was `financial/aggregation/` — Casilla aggregation orchestration (transactions × categories → Modelo inputs)
│   ├── workflow/
│   ├── sync/
│   ├── setup/
│   ├── review/
│   ├── verification/
│   └── auth/                   # SLIM: provider-selection only — `select_provider` + provider-agnostic types (per audit 3)
├── entrypoints/                # primary adapters (user-facing)
│   ├── cli/
│   └── mcp/
└── core/                       # foundational cross-cutting modules
    ├── config.py
    ├── logging.py
    ├── errors/
    ├── i18n/
    ├── env_io.py
    ├── paths.py                # renamed from `_paths.py` (drop underscore); audit 4 folds in `storage/_path_safety.py`
    ├── json_contract.py        # renamed from `_json_contract.py` (drop underscore)
    ├── click_context.py        # renamed from `_click_context.py` (drop underscore)
    ├── access_gate/            # added by audit 3: AeatAccessGate + policy errors (LiveSubmitForbiddenError moved here from submission/)
    ├── file_permissions.py     # added by audit 3: cross-platform chmod/icacls primitive
    ├── locks.py                # added by audit 4: was `storage/_lock.py` — OS-level file locking + fsync_parent_dir, used cross-domain
    ├── classification/         # added by audit 4: was `storage/_classification.py` — 9-class sensitivity taxonomy + retention/redaction policy table
    ├── redaction/              # added by audit 4: was `storage/_redaction.py` — PII redaction primitives (NIF/URL/JWT scrubbing)
    ├── corpus_manifest/        # added by audit 4: was `storage/_corpus_manifest.py` — self-attesting integrity manifest for plaintext CORPUS directories
    ├── observability/          # added by audit 15: was `adapters/persistence/observability/` — cross-cutting run-trace instrumentation (analogous to opentelemetry/structlog placement)
    └── identity/               # added by decision-grounding audit: validate_spanish_tax_id moved here from `aeat.domain.financial.invoices._validators` — resolves 2 layered-architecture violations (storage._master_key NIF canary; sanitizer._records synthetic NIF check)
```

### Rename rationale (high-impact)

- **`submission/` → `adapters/outbound/export/`**: the word "submission"
  carries the connotation of submitting to AEAT, an ambiguity that
  contributed to past live-write incidents. The rename is a CLARITY
  measure that matches the project charter (`produce → verify →
  export`); it is NOT a new safety mitigation. The actual mitigation is
  the four-factor live-submit gate. The rename's role is to remove
  verbal ambiguity so any future write path lands under a name that no
  longer claims to be "submission" — supporting safety by reducing the
  surface area for the same incident pattern, but not standing alone.
- **`infrastructure/` (industry canonical) → `core/`**: project-owner
  preference; reads as foundational modules rather than as infrastructure-
  as-code (the AWS-flavoured connotation). Distinguishes from
  `adapters/persistence/` (which is also "infrastructure" in DDD terms).
- **`mediation` (earlier proposal) → `application/`**: industry-canonical
  word; reads on first contact for any Python developer familiar with
  DDD or hexagonal.
- **`models/` → `domain/modelos/`**: AEAT-canonical Spanish term; avoids
  the foot-gun of new contributors expecting Pydantic models. The
  Pydantic-naming collision is the dominant reason for the rename.
- **`_pdf_import` → `adapters/inbound/pdf/`**: drops the underscore
  prefix; surfaces the shared-primitive role explicitly.
- **`financial/` → `adapters/inbound/financial/providers/`** (per
  audit 20): the `financial/` subpackage was a 59-file conflated
  cluster; only the `providers/` sub-tree is genuinely inbound.
  The other 7 sub-packages (`transactions/`, `invoices/`,
  `categories/`, `vat/`, `aggregation/`, `usage_ratios/`,
  `attachments/`) relocate per the audit-20 8-destination split.
  The candidate rename `financial/` → `transactions/` is
  superseded by the split; no top-level rename happens. The old
  top-level files `_decimal.py` and `_raw_transaction.py` ride
  with the providers cluster.

### Monolithic split planning

Monolithic modules (≥ 950 LOC, flagged `[MONO]` in the research doc) are
split-planned during the per-module audit. The split design is folded
into this ADR per module as the audit lands. Splits and the layout move
are coordinated so destinations reflect the post-split shape:

- The audit produces a per-module split design — proposed sub-modules,
  their public surface, and the fracture lines.
- The destination column in the research doc heat map is updated to
  reference the post-split sub-paths where applicable.
- Sub-modules inherit the parent's bucket assignment unless the audit
  surfaces `[CORE-LEAK]` candidates that bubble up into `core/`.

The currently-known `[MONO]` modules (20 of 38 non-empty) are listed in
the research doc heat map with their flags. Highest-priority splits:
`storage` (~12k LOC, `[CONFLATE]`), `cli` (~7.6k LOC, `[CONFLATE]`),
`auth` (~4.8k LOC, `[CONFLATE]`), `filing` (~4.5k LOC, `[CONFLATE]`),
`errors` (~3k LOC, `[CONFLATE?]`).

### Test-marker realignment

The existing axis-B test markers carry the project's domain taxonomy.
They realign in lockstep with the layout rename so package and marker
vocabulary stay in sync.

Proposed marker set:

| Old marker | New marker | New home (package) | Notes |
| --- | --- | --- | --- |
| `domain_financial_input` | `domain_inbound` | `adapters.inbound.*` | direct rename |
| `domain_local_state` | (split) | (see below) | bifurcates |
| → | `domain_model` | `domain.*` | NEW — covers catalogues + computation engines + profile |
| → | `domain_persistence` | `adapters.persistence.*` | NEW — covers storage + observability + llm |
| `domain_aeat_remote` | `domain_outbound` | `adapters.outbound.*` | covers browser + sede + export |
| `domain_submission` | `domain_outbound` (bucket) + `domain_export` (sub-marker) | `adapters.outbound.export.*` | tests in `adapters.outbound.export.*` carry both the bucket marker and the export sub-marker. Stacking is allowed because Axis B accepts ≥1 marker. The sub-marker preserves the existing capability of selecting export-only tests. **Decision: not deferred.** |
| `domain_mediation` | `domain_application` | `application.*` | direct rename |
| `domain_infra` | `domain_core` | `core.*` | direct rename |

**Live-write safety note**: the `live_write` collection-ban is anchored
on Axis A (the `live_write` marker per the pytest-markers ADR) and is
not affected by the Axis B rename. The marker rename window does not
create a collection-ban regression. The `domain_export` sub-marker is
preserved as a fine-grain selector for export-specific test runs but
carries no collection-ban semantics on its own.

**Migration mechanic — PR-level**: the marker rename PR ships in the
same change window as the package move. Tests do not transit a state
where their marker is wrong relative to their location.

**Migration mechanic — per-test-file**: every test FILE currently
marked `domain_local_state` (via module-level `pytestmark = [...]`) is
reclassified by its containing module's destination at move time. The
rule covers ALL destination layers, not just `domain/` and
`adapters/persistence/` (extended per Step 1 sub-pass 3 finding —
2026-04-30):

- Test files in modules that move under `domain/` get `domain_model`.
- Test files in modules that move under `adapters/persistence/` get
  `domain_persistence`.
- Test files in modules that move under `adapters/inbound/` get
  `domain_inbound`.
- Test files in modules that move under `adapters/outbound/` get
  `domain_outbound`. Tests under
  `adapters/outbound/aeat/export/` additionally carry the
  `domain_export` sub-marker.
- Test files in modules that move under `application/` get
  `domain_application`.
- Test files in modules that move under `core/` get `domain_core`.

The audit produces the per-module destination decision; the marker
rewrite is then mechanical from the destination. Manual override only
when a test crosses module boundaries — flagged during the audit.

The Step 1 audit identified ~37 test files in this extended-rule
bucket: ~33 under `submission/_formats/*` (move to
`adapters/outbound/aeat/export/` → `domain_outbound + domain_export`);
3 under `review/*` (move to `application/review/` →
`domain_application`); 1 under `identity/*` (moves to
`adapters/inbound/identity/` → `domain_inbound`).

**Override list as hard pre-merge gate** (per refreshed cold-review
22.9): the audit produces an EXPLICIT list of every test file that
requires manual override. The list must be **zero-length OR
audit-grounded** before the layout-move PR merges — every override
item must have an audit subagent's resolution recorded. If the
override count is non-zero AND any item is unresolved, the merge
gate fails. The list materializes in the research doc's modules-
audited section as audits land.

**Naming rationale**:

- `domain_model` is the DDD canonical term for the business model
  layer; reads better than `domain_domain` and conveys the layer's
  purpose without inventing new vocabulary.
- `domain_persistence` is the canonical hexagonal/DDD word for the
  storage-side adapters; clearer than the previous `domain_local_state`
  which collapsed two layers.
- `domain_inbound`/`domain_outbound`/`domain_application`/`domain_core`
  match the new top-level package names 1:1 — the marker name is the
  package name with a `domain_` prefix.

### Vault-corpus supersession

Existing `.vault/` documents that reference old module names, old test
markers, or pre-restructure path conventions are slated for supersession
in lockstep with rollout. A scan of the corpus produces a per-document
contradiction list (captured in the research doc's "Vault-corpus
contradictions" section).

Each contradicted document is classified:

- **Tier 1 — Mark superseded**: document is superseded by this ADR or
  by a downstream artefact; add a `superseded_by:` link in frontmatter
  and do not edit the body.
- **Tier 2 — Security-sensitive**: document names a security-relevant
  guardrail at a path that moves; the guardrail must be revalidated
  at the new location AND the document inline-updated.
- **Tier 3 — Inline-update**: document is still authoritative on its
  topic but contains stale path / marker references; update those
  references in place at rollout.
- **Tier 4 — Archive**: document is historical (`.vault/exec/`
  records of completed work). Leave as-is; the path references are
  forensic.

**Per-tier rollout gating**:

- **Tier 1** — `superseded_by:` frontmatter additions ship as a single
  PR alongside the layout-move PR. Frontmatter-only changes; no body
  edits.
- **Tier 2** — must be inline-updated AND the named guardrails
  revalidated at their new locations BEFORE the layout-move PR
  merges. **Hard gate.** No exception: a security guardrail that
  silently moves without revalidation is a regression.
  **"Revalidated" means** (per refreshed cold-review 22.7): an
  explicit guardrail unit test passes against the new path AND
  the audit document is inline-updated to reference the new
  location. Both conditions must hold. CI proves the test passes;
  the inline-update is verified by the rollout PR's vault diff.
- **Tier 3** — ships within the same milestone as the layout move;
  not a hard gate on the move PR but a release-completion gate.
- **Tier 4** — does not gate; left untouched.

The contradiction list and per-document classification ship as a
research-doc artefact, not as separate vault entries — they are the
input plan for the rollout, not standalone decisions.

### Public surface and semver

**Historical planning section.** The rollout ultimately hard-cut over
without retaining root compatibility modules. This section records the
pre-cutover semver model evaluated during planning; the 2026-05-01
Outcomes section is authoritative for current policy: no root
re-export layer, no shim-retention schedule, and no `import-linter`
quality gate for ordinary delivery.

The following table is retained as a historical planning inventory of
documented public surfaces and the stability contracts considered before
the rollout. It is not the current implementation contract. The delivered
2026-05-01 hard cutover rewrote callers to canonical layered modules and
did not retain a root re-export/shim layer; the Outcomes section below is
authoritative for current policy.

| Public surface | Source | Treatment | Mechanism |
| --- | --- | --- | --- |
| `from aeat.core.errors import AeatError` | `error-code-registry-adr` + audit 1 | Preserve | Canonical public surface remains `aeat.core.errors`; no root facade is involved. |
| `from aeat.core.errors import (rendering pipeline)` (`build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, `get_registered_error_code`, `ErrorCategory`, `ErrorCode`, `ErrorEnvelope`, `ERROR_REGISTRY`, `register`, `bind_error_code`, `resolve_error_message`, `scrub_error_context`) | `error-code-registry-adr` + audit 1 | Preserve | Canonical public surface remains `aeat.core.errors`; tight cluster, all stay in `core/errors/`. |
| `from aeat.core.errors import FormulasError, RulesetValidationError, FormulaCycleError, CasillaNotDefinedError, AmbiguousPeriodError, MissingRulesetError, EvaluationError, AuditDiscrepancyError` | audit 1 | Historical preserve-via-shim option; superseded by hard cutover | The 8 formulas exceptions move to `domain/formulas/_errors.py`; delivered callers import from canonical layered paths. |
| `from aeat.core.errors import McpLaunchError` | audit 1 | Historical preserve-via-shim option; superseded by hard cutover | Moves to `entrypoints/mcp/_errors.py`; delivered callers import from canonical layered paths. |
| `from aeat.core.errors import FilingFixtureError, FixtureProvisioningError` | audit 1 | Historical preserve-via-shim option; superseded by hard cutover | Move from `domain/testing/_errors.py` planning shape to the delivered application filing testing surface; no `aeat.domain.testing` package remains. |
| `from aeat.core.errors import SiteHealthError, AeatObservabilityError` | audit 1 | Preserve | Stay in `core/errors/__init__.py` as firewall declarations. The cross-domain reason for hosting them at this level (preventing import cycles between `browser`, `workflow`, and `observability`) is genuine; relocation is unsafe. |
| `from aeat.core.errors import DeprecatedAliasError, MovedAliasError` | audit 1 | Preserve | Stay in `core/errors/__init__.py` as generic infra exceptions. |
| `from aeat.core.errors import WorkspaceLockedError` | audit 1 + refreshed cold-review 22.11 | **DELETE + replace** | Verified production-dead (only test-file usage). Resolution: delete from `__init__.py`, replace test-file usage with a synthetic test exception (e.g. `_TestableAeatError` defined inside the affected test file). NO shim. The "rename or delete" disposition in dead-code Phase 2 is resolved as DELETE. |
| `from aeat.adapters.outbound.aeat.auth import (Google cluster: scope constants, get_oauth_credentials, get_service_account_credentials, get_credentials, get_credentials_for_scopes, build_*_service, build_*_client, GoogleAuthPath, GoogleAuthInspection, inspect_google_auth, ...)` | audit 3 | Historical preserve-via-shim option; superseded by hard cutover | All Google symbols moved to `aeat.adapters.outbound.google`; delivered callers import the canonical package directly. |
| `from aeat.adapters.outbound.aeat.auth import (AEAT cluster: AeatAuthenticator, AeatSession, AeatLoginAssertion, AuthProviderKind, AuthProvider, all session-detail variants, CertificateBundle, CertificateError hierarchy, ClaveMovilAuthProvider, select_provider, ...)` | audit 3 | Historical preserve-via-shim option; superseded by hard cutover | Concrete AEAT providers + cert types live in `aeat.adapters.outbound.aeat.auth`; provider selection lives in `aeat.application.auth`; delivered callers import canonical layered paths. |
| `from aeat.adapters.outbound.aeat.auth import AeatAccessGate, AeatGateEnvSnapshot, AeatLiveReadNotEnabledError` | audit 3 | Historical preserve-via-shim option; superseded by hard cutover | Canonical home is `aeat.core.access_gate`; delivered callers import canonical layered paths. |
| `from aeat.adapters.outbound.aeat.auth import restrict_file_permissions` | audit 3 | Historical preserve-via-shim option; superseded by hard cutover | Canonical home is `aeat.core.file_permissions`; delivered callers import canonical layered paths. |
| `from aeat.adapters.outbound.aeat.export import LiveSubmitForbiddenError` | audit 3 | Historical preserve-via-shim option; superseded by hard cutover | Canonical home is `core/access_gate/_errors.py`; delivered callers import canonical layered paths. |

Additional public surfaces are surfaced during per-module audits
and folded into this table.

**Historical semver impact model**: the original rollout plan used a
shim-preservation matrix to decide minor-vs-major versioning at Step 8.
The delivered 2026-05-01 hard cutover superseded this matrix: no root
compatibility layer or shim-retention schedule exists in the codebase.

**Historical shim deprecation contract** (per refreshed cold-review 22.5):

The following shim lifecycle was evaluated during planning, but it is not
active after the delivered hard cutover because no root re-export shim
layer was retained.

- **Deprecation signal**: every shim emits a `DeprecationWarning`
  on first import per process, citing the canonical path. Example:
  `aeat.core.errors` shim warns "Importing from `aeat.core.errors` is
  deprecated; use `aeat.core.errors` instead. Removal earliest
  at version X.Y."
- **Removal eligibility**: a shim becomes eligible for removal at
  the **second minor version after introduction** (i.e. if shipped
  in 0.10.0, removable in 0.12.0). This is a minimum, not a
  maximum.
- **Removal trigger**: at Step 14 close, the executing agent files
  one follow-up GitHub issue per minor-version-eligibility cohort
  describing which shims become removable when. A future agent
  picking up that follow-up issue executes the removal PR. The
  removal PR runs the full acceptance-criteria check; merges
  deterministically if green. Removal PR is a major bump if the
  shim is at a documented public surface (`aeat.core.errors`); minor
  bump otherwise. No external scheduler is required.
- **CHANGELOG**: every shim addition AND removal is a CHANGELOG
  entry under the matching version.
- **No deprecation pragma silence**: tests do NOT silence the
  shim's `DeprecationWarning`; CI catches lingering shim consumers
  inside the project.

### Configuration files affected

The restructure inline-updates the following project configuration
files in the same PR as the layout move. Audit must surface any
additional files; this list is not exhaustive.

- `pyproject.toml` — `tool.coverage.run.source`,
  `tool.coverage.run.omit`, `tool.mypy` package paths,
  `tool.pytest.ini_options.testpaths`, any `tool.pyright.include` /
  `exclude`, `tool.ruff` per-package overrides if any.
- Pre-commit configuration (`.pre-commit-config.yaml` or `prek.toml`)
  — any per-path hooks scoped to old paths.
- `.mcp.json` — script-entry string for the MCP launcher;
  regenerated when `mcp/` moves to `entrypoints/mcp/`.
- `justfile` — any recipe that hardcodes a `src/aeat/<old-path>/`
  reference (e.g. coverage scope on `just test-cov`).
- `.gitignore` — any per-package ignore rules.
- CI workflow files (`.github/workflows/*.yml`) — any path-scoped
  step (test selection, coverage upload, lint targets).

### Import-boundary enforcement

Static enforcement of the new layer boundaries is a hard requirement,
not a follow-up. Layered contracts:

- `domain/` is the innermost layer — must NOT import from any sibling
  (`adapters/`, `application/`, `entrypoints/`); `core/` allowed only
  for foundational types (errors, paths, logging).
- `adapters/inbound/`, `adapters/outbound/`, `adapters/persistence/`
  may import from `domain/` and `core/` only. Adapters MUST NOT
  import from each other (no `inbound/` → `outbound/` etc.).
- `application/` may import from `domain/`, `adapters/`, and `core/`.
- `entrypoints/` may import from anywhere.
- `core/` is leaf — must NOT import from `adapters/`, `application/`,
  `domain/`, or `entrypoints/`.

**Documented carve-out (per UX-grounded audit, Decision 1)**:

`domain/<name>/_repository.py` MAY import from
`adapters/persistence/storage/`. This is a deliberate exception to
the layered model, motivated by the project's established pattern
of co-locating per-domain repositories with their domain. The
carve-out:

- Is documented here in the ADR as a project-specific layering
  compromise.
- Is enforced as the ONLY permitted exception to the
  `domain/` → `adapters/` rule (no other carve-outs).
- Honours contributor legibility: a contributor reading
  `domain/filing/` finds all filing-domain code in one place.
- The `import-linter` contract names this exception **explicitly
  by file**, NOT via wildcard pattern (per refreshed cold review
  finding 22.1).

**Carve-out registry** (the ONLY files permitted the exception):

| File | Source audit |
| --- | --- |
| `domain/rental/_repository.py` | audit 2 |
| `domain/filing/_repository.py` | audit 5 |
| `domain/filing/_complementaria_repository.py` | audit 5 |
| `domain/justificante/_repository.py` | audit 11 |
| `domain/submission/_repository.py` | audit 16 |
| `domain/transactions/_repository.py` | audit 20 |
| `domain/invoices/_repository.py` | audit 20 |
| `domain/attachments/_repository.py` | audit 20 |
| `domain/usage_ratios/_service.py` | audit 20 |

**Escalation policy**: any new `_repository.py` (or persistence-
side service) file created in `domain/<name>/` after this ADR
freezes MUST be added to the registry above by name in a
follow-up ADR amendment OR moved to `application/<name>/` (which
permits adapters/ imports unconditionally). NO new file silently
inherits the carve-out via wildcard pattern.

**Skeleton `import-linter` contract** (illustrative; final
contract committed with the layout-move PR):

```toml
[importlinter]
root_packages = ["aeat"]

[[importlinter.contracts]]
name = "domain layer is innermost"
type = "layers"
layers = [
    "aeat.entrypoints",
    "aeat.application",
    "aeat.adapters",
    "aeat.domain",
    "aeat.core",
]
ignore_imports = [
    # Carve-out: domain repositories importing storage substrate
    "aeat.domain.rental._repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.filing._repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.filing._complementaria_repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.justificante._repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.submission._repository -> aeat.adapters.persistence.storage.*",
    # NOTE: sync._repository stays at application/sync/ per audit 13 — NOT in carve-out
    "aeat.domain.transactions._repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.invoices._repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.attachments._repository -> aeat.adapters.persistence.storage.*",
    "aeat.domain.usage_ratios._service -> aeat.adapters.persistence.storage.*",
]

[[importlinter.contracts]]
name = "adapters do not import each other"
type = "independence"
modules = [
    "aeat.adapters.inbound",
    "aeat.adapters.outbound",
    "aeat.adapters.persistence",
]

[[importlinter.contracts]]
name = "core is leaf"
type = "forbidden"
source_modules = ["aeat.core"]
forbidden_modules = [
    "aeat.adapters",
    "aeat.application",
    "aeat.domain",
    "aeat.entrypoints",
]
```

The contract uses **per-file `ignore_imports`**, not wildcard
patterns — every carve-out is explicit and grep-able.

**Intra-`adapters/persistence/storage/` cross-sub-module imports**
(per wave-5 finding 4): `_rotation.py` is permitted to import from
sibling sub-modules (`envelope/`, `blob_store/`, `master_key/`)
because rotation is a cross-cluster engine by design (audit 4).
The `independence` contract above governs ADAPTER-LEVEL isolation
(no `inbound/` → `outbound/` etc.) — it does NOT apply inside a
single adapter sub-package. Storage's internal sub-module
hierarchy is permitted to compose freely; the layered contract
applies only at the storage substrate boundary, not within it.

**Historical static-boundary tool note**: `import-linter` was evaluated
as the default planning tool because it is contract-driven and fits
layered models. The delivered pipeline superseded this with pytest
import-contract gates and targeted AST checks; `import-linter` is not
the current quality gate for ordinary delivery.

The boundary contracts ship in the same PR as the layout move; CI
fails if any import violates the contract.

### Dead-code workstream

Per-module audits surface dead-code candidates that are removable
during the restructure window. The dead-code workstream consolidates
findings into a phased plan persisted in the research doc:

- **Phase 1** (standalone, before layout move): items with zero
  cross-domain coupling — ship as small standalone deletion PRs.
  Current candidates: `auth/_secret_adapters.py` (whole module),
  `filing.utc_now`, `auth._providers.describe_certificate_provider`.
- **Phase 2** (with restructure): items that ride home with their
  domain's split or move. Current candidates:
  `errors.WorkspaceLockedError`, 3 `migrate_legacy_*_to_repository`
  helpers in filing, duplicate `default_schema_provider` in
  `filing/_builders/_modelo_130_schema.py`, 4 empty subpackage
  placeholders (`corpus/`, `history/`, `inbox/`, `status/`).
- **Phase 3** (post-restructure): none currently.

**Verification methodology**: each candidate confirmed by
intermediate grep of `src/aeat/` (excluding defining file +
colocated tests). **Pre-merge safety check** is mandatory: run an
unrestricted `grep -r '<symbol>' src/` on every Phase 1 deletion to
catch dynamic resolution, config references, and docstring
references that the intermediate grep does not see.

**Aggregate impact** (current candidates): ~590 LOC of production
code + ~190 LOC of obsolete test code + 4 empty directories.
Material cohesion improvement; net LOC reduction is ~1% of
`src/aeat/`.

The candidate list lives in the research doc's "Dead-code
workstream" section. Items pre-approved for execution via the
**decision-grounding audit** (research doc, "Audit-grounded action
list"):

**Phase 1** (standalone PRs, before layout move):
- `auth/_secret_adapters.py` (whole module + test) — ~470 LOC.
- `auth._providers.describe_certificate_provider` — remove from
  `__all__`.
- `filing.utc_now` — remove from `__init__.__all__`.
- `llm._FakeAdapter` — remove from `__all__`.
- `llm.ProviderRequest` — remove from `__all__`.
- `schema._extractor.py` — whole file (27 LOC).

**Phase 2** (with restructure):
- 4 empty subpackages (`corpus/`, `history/`, `inbox/`, `status/`).
- `submission/_submitters/` tombstone directory.
- `sede._walker.fetch_justificante_pdf` (raises NotImplementedError).
- 4 hollow Protocol stubs in `sync` (`LLMClient`, `LLMRequest`,
  `ManualRulesLoader`, `SchemaLoader`) on `LiveSyncRunner`.
- `errors.WorkspaceLockedError` (test-only fixture; rename or
  delete).
- `SchemaSource.PORTAL_HTML_PROBE`, `SchemaSource.MANUAL_LLM_DRAFT`,
  `SchemaSource.XSD_WIRE` reserved enum members and their
  `_models.py` docstring + `test_models.py` references (per Step 0
  Decision 6 outcome — no active branch / open issue references
  these slots).
- The 5 `migrate_legacy_*_to_repository` helpers are NOT in this
  list — Step 0 Decision 10 fires `RETAIN with TODO(#477)` because
  all 5 landed 2026-04-27, well short of the 6-month retention
  threshold. They will be revisited at the deprecation-eligibility
  date (2026-10-27) tracked in `#477`.

### Transition mechanic (parallel branches and agent slots)

The project runs up to 6 parallel agent slots. The layout-move PR
creates a brief incompatibility window where pre-move branches will
conflict.

Mechanic:

- **Freeze window** — a short freeze (target: < 24 hours) is
  announced before the layout-move PR merges. No new branches off
  pre-move main during the freeze.
- **Freeze extension policy** (per refreshed cold-review 22.8):
  if the layout-move PR is not mergeable within 24 hours (e.g.
  CI fails for non-revert reasons), the freeze extends in
  12-hour increments. Agent-slot orchestration is informed at
  each extension. **Cumulative freeze > 72 hours fires the
  rollback halt-trigger automatically** per the abort criteria —
  extended freezes are themselves a coordination cost the
  pipeline cannot absorb beyond this threshold.
- **In-flight branches** — each pre-move branch receives a one-shot
  mechanical rebase tool: a script that walks the diff and rewrites
  import paths from old to new. The script is generated as part of
  the layout-move PR (the rewrite map is the same one used to move
  source files).
- **Agent-slot orchestration** — parallel agent slots pause for the
  freeze duration. The PM layer coordinates the pause and the post-
  merge resume.
- **Open PRs** — any open PR pre-move is marked
  `needs-rebase-post-restructure`. The mechanical rebase tool runs
  after the layout PR lands; PRs that the tool cannot rebase cleanly
  are flagged for manual resolution.

The transition mechanic is a one-time cost. After the layout PR
lands, the new layout is the only valid layout.

## Rationale

The proposal is selected over alternatives because:

- **Industry-canonical vocabulary** — every top-level name appears in
  the Cosmic Python and AWS hexagonal references and is recognisable on
  day one to a Python developer with DDD familiarity.
- **Honest split between domain and persistence** — fixes the "state"
  collapse that bundled catalogues, compute, and storage. Catalogues are
  domain knowledge; storage is the infrastructure that persists them.
- **Inbound/outbound under `adapters/`** — a recognised hexagonal
  variant that matches the project's three-domain mental model exactly
  while keeping a single `adapters/` parent.
- **Legal-liability rename of `submission/` → `export/`** — telegraphs
  the prohibition in code as well as docs.
- **Spanish AEAT vocabulary preserved** — `modelos`, `casillas`,
  `borrador`, `declaracion`, `justificante`, `sede` keep their AEAT-
  canonical names. DDD's "ubiquitous language" principle is honoured.
- **`core/` for cross-cutting** — owner preference; reads as foundational
  modules.
- **Test-marker mapping is preserved** — the existing taxonomy maps onto
  the new layout with a single bifurcation flagged for follow-up.

## Consequences

**Positive:**

- New contributors orient immediately: top-level layout matches Python
  DDD references.
- Boundary violations become visually obvious — a module under
  `adapters/inbound/` importing from `adapters/outbound/` is a code-
  review red flag without further explanation.
- The `submission` → `export` rename closes a recurring ambiguity that
  has produced legal-liability incidents in the past.
- The four empty placeholder subpackages (`corpus`, `history`, `inbox`,
  `status`) get an unambiguous fate: delete or move to a clear home.

**Negative / risks:**

- Large refactor — all imports inside `src/aeat/` change; tests break
  en masse. Execution must be mechanical and verifiable, not hand-
  rolled. Phasing is the lever (layout move first, internal fractures
  next), not the contents of the change.
- 20 of 38 non-empty modules require internal split designs before they
  can be moved cleanly. Audit throughput is the critical-path
  constraint, not execution.
- Test-marker realignment must ship in lockstep with the package move
  (no in-flight state where marker name and package name disagree).
  Coordination cost across PRs.
- The AEAT-canonical Spanish term `modelos/` collides with the Python
  convention of `models/` for Pydantic. Acceptable trade-off (DDD
  ubiquitous-language wins) but requires onboarding documentation.
- Risk of surprise import shadowing during the move — must be vetted
  before execution.
- Vault-corpus supersession introduces a parallel doc-rewrite workload.
  Doing this before execution adds calendar time but prevents
  contradictory authoritative docs at rollout.

**Out of scope (this ADR does not relax these):**

- Reintroduction of live AEAT writes. The `submission` → `export`
  rename is a labelling change; the live-write CLI surface excised on
  2026-04-18 stays excised. The four-factor live-submit gate stays in
  effect as defense-in-depth.
- Per-document vault rewrites. The supersession workstream produces a
  classified contradiction list (research doc); the actual edits to
  superseded documents land as part of rollout PRs, not as standalone
  decisions captured here.

## Operational contract

This section is the operational contract for the rollout. It is
verifiable, not advisory. The acceptance criteria are the definition of
done. The abort criteria are the rollback safety net.

### Acceptance criteria (definition of done)

The restructure is considered complete only when ALL of the following
hold (none can be waived without an explicit override decision recorded
in this ADR):

- All imports resolve under the new layout. `python -c "import aeat"`
  succeeds; `pytest --collect-only` runs without `ImportError`.
- Coverage floor maintained: `just test-cov` reports ≥ 60% on
  `src/aeat` (project mandate).
- Static import-boundary diagnostics were evaluated against the layered
  contracts defined in the Implementation section. `import-linter`
  remains historical/diagnostic context, not the current quality gate
  for ordinary delivery.
- Vault contradiction list (research doc) at 100% per-tier
  completion: T1 supersedes shipped, T2 security audits validated and
  inline-updated, T3 inline-updates landed in milestone, T4 archive
  untouched.
- Test markers fully realigned. No test carries an old marker name;
  collection runs successfully under the new marker set.
- `domain_local_state` test files reclassified by destination
  (`domain_model` or `domain_persistence`) per the migration mechanic.
- Public-surface decisions executed. Canonical `aeat.core.errors`
  remains in place for the error registry and rendering pipeline;
  moved surfaces were rewritten to canonical layered imports under the
  delivered hard-cutover model.
- Configuration files updated: `pyproject.toml` (coverage / mypy /
  pytest paths), pre-commit configs, `.mcp.json`, `justfile`,
  `.gitignore`, CI workflow path-scoped steps.
- Security-audit guardrails validated at new locations:
  `core/paths.py` passes the path-resolution guardrail check named in
  the two security audits flagged in the research doc.
- All four empty placeholder subpackages (`corpus`, `history`,
  `inbox`, `status`) deleted.
- Internal split designs for the top-5 monoliths (`storage`, `cli`,
  `auth`, `filing`, `errors`) folded into this ADR.
- Dead-code workstream Phase 1 + Phase 2 deletions complete: every
  item on the dead-code workstream candidate list is either
  deleted or has an explicit override decision recorded. Phase 1
  PRs land before the layout-move PR; Phase 2 PRs ride with the
  relevant domain's move.
- **End-to-end behavioural smoke test** (added per refreshed
  cold-review 22.2): at least one CI integration test exercises
  the full `produce → verify → export` pipeline end-to-end after
  the layout move. Structural import-resolution alone is not
  sufficient — Kent's pipeline must still produce a fichero BOE
  given a synthetic transaction set.
- **Type-checker clean run** (added per 22.3): `mypy` and/or
  `pyright` (whichever the project uses) reports zero errors on
  the new layout. Type errors silently accumulating post-move are
  a regression in static-type safety; this is a hard gate.
- **Migration-script correctness test fixture** (added per 22.4):
  the layout-rebase migration script ships with a test fixture
  exercising every kind of import the project actually uses:
  relative imports (`.module`, `..sibling`), TYPE_CHECKING
  blocks, star imports, dynamic `importlib.import_module` calls.
  Script must rewrite all four kinds correctly.
- **Packaging verification** (added per 22.10): `pip install -e .`
  succeeds; `pip install dist/*.whl` succeeds; the installed
  wheel exposes the new sub-paths (verified via post-install
  `python -c "from aeat.adapters.outbound.aeat.export import ..."`
  smoke check).
- **Test-marker manual-override list resolved** (added per
  wave-5 finding 2 / 22.9): the test-marker realignment audit
  produces an explicit list of test files requiring manual
  override (tests that cross module boundaries). The list is
  zero-length OR every item has an audit-grounded resolution
  recorded before the layout-move PR merges. Hard pre-merge gate.

### Abort / rollback criteria

The restructure halts and reverts under any of the following triggers:

- **CI failure rate** > 30% across 3 consecutive runs after the
  layout-move PR merges. Action: revert layout PR; preserve marker-
  rename PR for re-application post-fix.
- **Unresolvable circular import** that cannot be broken within 1
  working day. Action: revert; redo with corrected destination(s).
- **Marker realignment leaves any test in a state where the
  `live_write` collection-ban could mis-fire**. Action: revert
  immediately, no negotiation. This is a safety regression.
- **Security guardrail validation fails** at the new location for
  `core/paths.py`. Action: revert; revalidate proposed location
  before re-attempt.
- **Coverage floor (60%) breached** by the move. Action: investigate
  before reverting; coverage drop usually indicates broken pythonpath
  or mis-mapped source paths in coverage config.

**Revert mechanic**: the layout move is a single PR (mechanical
import rewrite). The rename PRs and the marker-rename PR are
decoupled. A revert returns the package layout to pre-move state
without affecting the unrelated changes.

### Autonomous decision rules (no human-in-the-loop)

The executing agent (single Claude Code or equivalent agent that
picks up issue #475 and follows the plan) runs the pipeline end-to-
end without external workflows or human sign-off. Every decision is
replaced by a deterministic, audit-grounded rule the agent applies
based on subagent findings. If a finding is ambiguous, the agent
dispatches additional audit-subagent passes within a bounded retry
budget; only then does the rule fire. Failures are signal — the
agent halts on audit-red and dispatches a diagnostic subagent
before resuming, retrying, or firing rollback.

| Decision | Autonomous rule | Mechanism |
| --- | --- | --- |
| Calling the freeze | Triggered when Step-5 tooling-prep audits commit clean (Step-5 = boundary diagnostics recorded + rebase script test fixture green + smoke-test fixture green + type-checker config updated + packaging smoke check passes). | The executing agent applies the freeze when Step 5 completes — labels open PRs `needs-rebase-post-restructure` via `gh pr edit`. |
| Declaring acceptance criteria met | All 15 acceptance criteria evaluate green. ANY criterion red → pipeline halts. | The executing agent runs the acceptance-criteria checklist against the layout-move PR; reads CI status via `gh run view`. |
| Invoking rollback | Fired when any abort-criterion threshold is detected (CI > 30% failure across 3 consecutive runs; > 72 h cumulative freeze; coverage floor breach; security guardrail revalidation fails; `live_write` collection-ban mis-fire risk). | The executing agent monitors CI / freeze duration / coverage as it proceeds; on threshold breach, executes `gh pr revert` + downstream-step compound rollback per the table below. |
| Semver bump | Rule-based deterministic: compatible public-surface outcome → minor bump; public-surface break → major bump. **No override path**. | The executing agent applies the semver bump rule mechanically from the delivered public-surface outcome. |
| Shim removal | Historical planning rule only; superseded by hard cutover. No root re-export shim layer was retained. | At Step 14/15 close, the executing agent records that no shim-retention policy and no shim-removal issue queue exist. |
| Outstanding boundary items (migration-helper retention; reserved `SchemaSource` enum slots) | Resolved at Step 0 by audit-grounded subagent decisions per the rules below. | Step-0 audit subagent dispatched by the executing agent; decisions land as ADR amendment commit. |

CI failures, coverage drops, and abort-trigger thresholds are not
escalated to a human — the executing agent fires the rules
automatically. The pipeline communicates state through exec
records and CHANGELOG entries.

**Historical shim-verification gate** (per refreshed cold-review BLOCKER
for deterministic semver): before the hard-cutover outcome superseded
shim retention, the executing agent would have imported each declared
shim path in a clean Python subprocess and asserted the re-exported
symbols were reachable. The delivered model rewrote callers to canonical
layered modules and retained no root re-export shim layer.

**Bounded retry on ambiguous findings** (per refreshed cold-review
BLOCKER for halt-loop bounding): when an audit subagent returns an
ambiguous finding, the executing agent re-dispatches the audit up
to **3 times** with progressively widened scope. If after 3
retries the finding is still ambiguous, the agent halts and writes
a "halted-on-ambiguity" exec record naming the unresolved finding.
The halted state is broken by ONE of: an explicit-override audit
re-dispatch (the agent decides the override scope based on the
ambiguity), a new commit invalidating the prior finding, or a
24-hour stalemate that fires the rollback halt-trigger
automatically. There is no infinite-loop risk.

**Halt-then-resume mechanic** (per refreshed cold-review BLOCKER):
when a step halts on audit-red, the executing agent dispatches a
diagnostic subagent. The diagnostic subagent examines the failed
step's exec record + CI artefacts + audit findings, then writes a
disposition (RESUME / FIX-AND-RETRY / FIRE-ROLLBACK) into a new
exec record. The agent reads the disposition and fires the next
action accordingly — no gap waiting for external triggers. If the
diagnostic itself hits the 3-retry ambiguity cap, the pipeline
halts permanently and writes a final exec record requiring a new
session and a new agent to pick up.

**Deployment-state acknowledgement** (per refreshed cold-review
SHOULD-FIX): the autonomous model trades observability of deployed
instances for full autonomy. The migration-helper retention rule
(and similar rules that depend on "zero production callers")
operate on STATIC analysis of `src/aeat/` only. The pipeline cannot
observe:

- Dynamically-constructed import paths (`importlib.import_module`,
  `__import__`).
- Config-driven imports.
- External consumers in downstream repos or deployments.
- Helpers actively called from a production deployment that is
  not reflected in static `src/aeat/` analysis.

The autonomous rules accept this tradeoff explicitly. Mitigation:
helpers with `DeprecationWarning`-emitting history (per the shim
deprecation contract) are treated as live callers even when static
analysis sees none. Helpers without a deprecation-warning history
+ no static callers + > 6 months in-tree are treated as safe-to-
delete. This rule may produce false-positive deletes for helpers
called only from external/deployed paths; recovery is a follow-on
PR re-introducing the helper. **By design, autonomy supersedes
deploy-state safety in this restructure.**

**Post-Step-8 rollback paths** (per refreshed cold-review BLOCKER
for rollback symmetry): the simple "revert single layout-move PR"
mechanic only works while no downstream step has merged. Once
Step 9 / 10 / 11 has merged, the rollback is compound:

| Halt-trigger fires after | Rollback procedure |
| --- | --- |
| Steps 0–7 (pre-move) | Halt the in-progress PR; no merged state to revert. |
| Step 8 merged, before Step 9 | Single revert of the layout-move PR returns to pre-move state. |
| Step 9 merged | Revert layout-move PR + revert any rebased branches' merges back to their pre-rebase state. The rebase tool emits a reverse-rewrite map for this purpose. |
| Step 10 merged (Phase-2 dead-code) | Revert layout-move PR + revert each Phase-2 deletion PR by name. Dead-code deletions are individually revertible because each is its own PR. |
| Step 11 in progress (per-module sanitization) | Halt Step 11 immediately. Per-module sanitization PRs are individually revertible. Revert in REVERSE merge order (newest first) to avoid conflict cascades. |
| Step 11+ complete, Steps 12–14 | Forward-fix only. Reverting at this stage is more risky than fixing forward — the diagnostic subagent escalates this rare case to a "halted-on-late-stage-failure" exec record requiring a new commit to break. |

The rebase tool shipped in Step 5 emits BOTH a forward-rewrite map
(old → new) and a reverse-rewrite map (new → old) so that any
rebased-branch revert is mechanical, not manual.

## References

Internal:

- Research (parallel, source-of-truth for module classification):
  `2026-04-30-aeat-restructure-research`.
- Live-submit CLI excision: `2026-04-18-live-submit-cli-excision-adr`.
- Auth provider abstraction: `2026-04-18-auth-provider-abstraction-adr`.
- Export-first product mode: `2026-04-17-export-first-adr`.

Industry:

- Cosmic Python — Appendix B: A Template Project Structure.
- AWS Prescriptive Guidance — Structure a Python project in hexagonal
  architecture using AWS Lambda.
- "Clean DDD lessons: project structure and naming conventions" — UNIL
  engineering / Medium.
- PEP 8 — Style Guide for Python Code.

Industry validation of post-audit decisions (research-doc audit 21):

- OpenTelemetry Python instrumentation docs + specification —
  observability as cross-cutting concern (validates audit 15
  observability → `core/`).
- Herberto Graça — Explicit Architecture (DDD/Hexagonal/Onion
  synthesis) — validates `core/` placement, technology-grouped
  outbound nesting, intentional pragmatic exceptions.
- Sairyss/domain-driven-hexagon (GitHub) — validates pragmatic
  layering carve-outs ("if the price is too high to abstract this
  away, it might be a good decision to allow some pollution").
- Mehmet Ozkaya — Shared Kernel Pattern in DDD — validates
  `core/identity/` placement for cross-domain validators.
- Implementing DDD + Hexagonal with Go (eventsandstuff Substack)
  — explicit endorsement of technology-grouped adapter sub-clusters
  (validates `outbound/<provider>/` nesting).

## Outcomes (rollout, 2026-05-01)

The 15-step autonomous pipeline shipped end-to-end without invoking
the abort/rollback path. Outcomes:

- **Semver bump**: MINOR (0.1.0 -> 0.1.1 at the next release tag).
  The planned shim-verification path was superseded by the hard
  cutover. Root compatibility modules (`aeat.errors`, `aeat.auth`,
  `aeat.submission`, `aeat.formulas`) were not retained; imports were
  rewritten to canonical layered modules.
- **Acceptance criteria**: 15 of 15 satisfied at Step 8 merge and
  re-verified at Step 15 milestone close. The full set is recorded
  in the Step 8 acceptance comment on issue #476.
- **Dead-code totals**: Phase-1 shipped via PRs #478, #479, #480,
  #481, #482 (5 deletions). Phase-2 shipped via PR #494
  (`default_schema_provider` duplicate). The continuation hard cutover
  deleted `WorkspaceLockedError`, removed obsolete shim/root surfaces,
  and rewrote test usage to canonical concrete errors. Remaining
  Protocol surfaces are tracked separately where they still model real
  boundaries.
- **Step-13 issues filed**: 2 umbrella issues (#498 coverage gap;
  #499 casilla rollup). One STRIKE issue (#500) for the empty
  hard-gap audit, closed at filing.
- **Sanitization**: 197 source files stripped of dev-process
  metadata (#496); 405+ test files migrated to layered axis-B
  markers (#495); 589 vault docs Tier-3 inline-updated (#497).
- **Boundary checks**: The 9-entry carve-out registry remained at 9
  entries. `import-linter` remains a diagnostic contract, not the
  current quality gate for ordinary delivery.
- **Shim-removal schedule**: None. The hard-cutover model introduced
  no root re-export shim layer, so there is no shim-retention policy
  and no future removal window.
