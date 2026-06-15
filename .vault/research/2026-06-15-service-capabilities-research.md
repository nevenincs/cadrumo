---
tags:
  - '#research'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
related: []
---



# `service-capabilities` research: `Profile-linked service capabilities, dependency management, and graceful degradation: current-state map`

The operator can use external services — Google export, on-host LLM vision,
cloud-CLI providers that may receive sensitive evidence — but the app has no
notion of *user-chosen capabilities*: which services a given profile opts in or
out of. Today every service gate is a process-global `Settings`/env flag with no
profile linkage, so two profiles (a personal one allowing cloud upload, a gestor
one barring it) cannot express different postures. Separately, on a fresh
workstation, missing external dependencies (Ollama, the provider CLIs, the
Playwright browser, Google credentials) fail incohesively — some gracefully, the
on-host vision path with a raw stack trace — and there is no single `doctor`
that tells the operator what is missing and how to provision it. This research
maps the current state across three surfaces to ground an ADR pair: (A)
profile-linked service capabilities and (B) dependency management + graceful
degradation + provisioning.

## Findings

### F1 — No per-profile capability surface exists; all gates are global

The `UserProfile` aggregate (`ProfileAggregate` in
`application/user_profile/_aggregate.py`, the encrypted `UserProfileRecord` in
`domain/user_profile/_values.py`) carries tax-identity and AEAT-regime facts only
— no field resembling app-service opt-in/out. The fact catalogue
(`_data/registry/aeat/user_profile/schema.toml`) has sections for identity,
preferences (only `output_language`), contact, tax_residence, censo, taxpayer_type,
iva, obligations, etc. The `iva.*_enrolled` flags (roi/oss/sii/redeme) look
capability-like but are **AEAT-regime enrollment facts**, not app toggles.

Every capability gate keys on the process-global `Settings` model
(`core/config.py`, env-driven, never per-profile). The only profile-aware path
(`settings_for_bucket_route`) rewrites just the database-URL/active-profile pair
and passes every capability field through verbatim. Verdict: **per-profile
capabilities do not exist; the two-profile scenario is inexpressible.**

### F2 — The three capability gates and their global controls

- **Cloud-evidence upload** — `cloud_evidence_read_permitted(settings, *, acknowledged)`
  (`application/ledger/_evidence_input.py:38`): bars on `aeat_evidence_gestor_mode`,
  requires `aeat_evidence_cloud_upload_permitted`, then a per-invocation ack. Both
  flags are global `Settings` defaults (`False`). Consumed at
  `_llm_classification.py:279`.
- **LLM vision / provider availability** — `is_llm_provider_available(provider)` =
  `shutil.which(binary)` (`_llm_classification.py:201`); the on-host vision path
  (`_resolve_evidence`) has **no toggle at all** — it runs whenever evidence is an
  image. There is no "LLM vision enabled" capability.
- **Google export** — gated only by credential presence (a `GoogleAuthError`
  hierarchy), not by an opt-in capability.

None is profile-scoped. The natural attach point (per the reference map) is a new
`capabilities` (or `services`) section in the profile schema TOML, persisted as
encrypted `UserProfileFact` rows, reusing the existing strict-schema / snapshot /
wizard / `EditProfileSectionCommand` machinery — with a resolution layer that
overlays a profile's capability facts onto the global `Settings` default at the
gate call site.

### F3 — Graceful-degradation inventory: one headline gap (Ollama vision)

Reference patterns that degrade well (to mirror): subprocess LLM CLIs (typed
`_bad` pre-check + `LLMClassifierError`), Google export (locale-rendered
`GoogleAuthError` → `_google_refusal` for every mode incl. no-credentials), OS
keychain (`KeyringUnavailableError` + auto file-fallback — the canonical
degradation reference), ECB FX (bundled-snapshot fallback).

The gaps:
- **Ollama vision — UNGRACEFUL (headline).** No reachability probe, no
  model-presence check anywhere. `LocalAdapter.complete` guards only HTTP *status*
  errors; a connection-refused raises `httpx.ConnectError` and a missing model an
  uncaught `LLMProviderError(404)`. The ledger classify CLI catches only
  `LLMClassifierError` / `TransactionValidationError` / pydantic `ValidationError`
  — neither `LLMProviderError` nor `httpx.ConnectError`. So `classify
  --read-evidence` on a box where Ollama is down/model-missing emits a raw
  traceback. `aeat app ledger providers` reports only the three subprocess CLIs,
  not Ollama.
- **Playwright browser-missing — PARTIAL.** `_launch_chromium` wraps the
  browser-not-installed case in a typed `BrowserError` but the message omits the
  `playwright install chromium` remediation hint.
- **Cloud LLM API adapter — PARTIAL.** Typed `LLMProviderError` at the adapter,
  but not caught by the ledger classify CLI.

### F4 — pyproject bundles every integration as a hard core dep; no capability extras

`[project.dependencies]` carries `anthropic`, the three `google-*` libs,
`playwright`/`playwright-stealth`, `keyring`, the PDF stack, and `torch` (~GB CUDA,
**unused by any runtime import** — present only for the vaultspec-rag pin, and
deptry-`DEP002`-suppressed). `[project.optional-dependencies]` has only
`workbook-windows`. There is **no capability-mapped extras structure**
(`[vision]` / `[google]` / `[browser]`), so an operator cannot install a lean core
and opt into capabilities, and the dependency surface does not mirror the
capability surface.

### F5 — Provisioning is fragmented; no single `doctor`, and `env-doctor` is broken

The `justfile` has `bootstrap` (install + vaultspec install + env-setup, but
**never verifies**), `workstation-tools` (Windows auto-installs via scoop; Unix
only checks), `env-doctor` (dev-toolchain version probe only — not ollama/google/
browser), `env-rag-start/stop`, and the `check-*`/`audit-*` gates. Critical
defects: `env-doctor` depends on `env-playwright`, which runs
`python -m aeat.entrypoints.cli.browser.health` — **a module that does not exist**,
so `env-doctor` hard-fails immediately; nothing runs `playwright install`
(chromium binary); no ollama/model provisioning or pre-flight; README says
`uv sync` (no env file) while the justfile says `just bootstrap` (conflicting
entry points). The April `setup-wizard` and `gsuite-bootstrap` ADRs described an
`aeat setup` / `aeat doctor` verification loop that was **retired** in the
config/app restructure and never replaced from the provisioning angle. The
surviving product-side checks (`config profile status/preflight/validate`,
`config auth test`, `config repair connectivity`) are well-guided individually
but data/profile-scoped, scattered, and not workstation-scoped.

## Implications for the ADR pair

**ADR A (profile-linked service capabilities):** add a `capabilities` profile
schema section (boolean opt-in/out for `cloud_evidence_upload`, `llm_vision`,
`google_export`), persisted as encrypted facts through the existing single-writer
profile path, exposed via the wizard/edit flow and a `config profile capabilities
show/set` surface; introduce a capability-resolution layer that overlays the
profile facts onto the global `Settings` default at each gate (gestor-mode stays
an absolute bar regardless of profile). Capabilities are operator *intent*; they
narrow, never widen, the global safety posture.

**ADR B (dependency management + graceful degradation + provisioning):** define
the cohesive missing-dependency behaviour (probe → typed refusal/Notice with
remediation → opt-in provisioning), close the Ollama headline gap (a reachability/
model probe + a typed refusal the CLI catches + an `aeat app ledger providers`-
style vision row), add the Playwright remediation hint, give pyproject a
capability-mapped extras structure (and excise/relocate the unused `torch` core
dep), and add a single `just doctor` (+ a product-side `aeat config doctor`-class
report) that enumerates every external dependency, its status, whether the active
profile opts into it, and the exact provisioning command — fixing the broken
`env-playwright`/`env-doctor` and reconciling the README/justfile entry points.

The two ADRs interlock at the gate: a service runs only when (capability opted-in)
AND (dependency available) AND (global safety posture permits); the `doctor`
reports all three axes per service.
