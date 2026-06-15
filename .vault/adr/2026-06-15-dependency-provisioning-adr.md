---
tags:
  - '#adr'
  - '#dependency-provisioning'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - "[[2026-06-15-service-capabilities-research]]"
  - "[[2026-06-15-service-capabilities-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace dependency-provisioning with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, or deprecated. A new ADR starts as proposed; it moves to
     accepted or rejected when the decision is made, and to deprecated
     when a later ADR supersedes it.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `dependency-provisioning` adr: `Dependency management and graceful degradation: cohesive missing-dependency behaviour, provisioning, and a single doctor` | (**status:** `accepted`)

## Problem Statement

On a fresh workstation, the app's external dependencies fail incohesively
(research F3, F5). Subprocess LLM CLIs, Google export, the OS keychain, and ECB FX
degrade gracefully (typed refusals, fallbacks); but the **on-host Ollama vision
path emits a raw `httpx.ConnectError` traceback** when the server is down or the
model is unpulled — no probe, and the CLI catches neither the connection error nor
`LLMProviderError`. Playwright's browser-missing case is typed but gives no
`playwright install` hint. Provisioning is fragmented: `just bootstrap` never
verifies, `just env-doctor` hard-crashes on a non-existent
`aeat.entrypoints.cli.browser.health` module, nothing pulls the Playwright browser
or the Ollama model, the README (`uv sync`) and the justfile (`just bootstrap`)
give conflicting entry points, and the retired April `aeat setup`/`aeat doctor`
verification loop was never replaced. There is no single command that tells the
operator what is missing and exactly how to fix it. This is the companion to the
profile-capabilities ADR: a service runs only when (capability opted-in) AND
(dependency available) AND (safety posture permits).

## Considerations

- The in-tree graceful-degradation references are strong: the keychain provider's
  `KeyringUnavailableError` + file fallback, the Google `GoogleAuthError` →
  locale-rendered `_google_refusal`, and the subprocess-CLI typed pre-check. The
  fix is to make the Ollama/vision and Playwright paths *match* these, not invent a
  new pattern.
- Diagnostics belong on the typed `Notice`/refusal channel
  (`cli-notices-are-the-only-diagnostic-channel`); a missing dependency is an
  instructive refusal, never a stack trace and never a silent no-op
  (`no-silent-under-declaration`).
- The dependency surface should mirror the capability surface: a capability the
  operator can opt into should have an installable extra and a doctor row.
- `torch` is a ~GB CUDA core dependency that **no runtime path imports** (deptry
  DEP002-suppressed) — it exists only for the dev-only vaultspec-rag pin. Carrying
  it in `[project.dependencies]` bloats every install (`aeat-source-hygiene`,
  `no-legacy-compatibility` spirit: don't ship dead weight).
- The CLI root surface is `config` + `app` only (enforced); a workstation doctor
  must live under `config` (e.g. `aeat config doctor`), not a third root family
  (`aeat-architecture-boundaries`).

## Constraints

- The shared-Windows-worktree exe-lock hazard forbids `uv sync` in `bootstrap`
  (documented); provisioning recipes must stay additive (`uv pip install`).
- Live AEAT writes remain permanently forbidden (`aeat-safety-legal-gates`); the
  doctor probes reachability/availability only, never performs a live write.
- The Ollama probe must not block the hot path with a long timeout; a fast
  reachability check (short connect timeout to `/api/tags`) plus a model-presence
  read, surfaced as a typed refusal before the expensive inference call.
- Parent surfaces (the LLM client/adapter, the browser session, the justfile, the
  CLI config surface) are shipped and stable; this layers additively.

## Implementation

**Decision: define one cohesive missing-dependency contract — probe → typed
refusal/Notice with the exact remediation command → opt-in provisioning — apply it
to the ungraceful paths, give pyproject a capability-mapped extras structure, and
add a single `aeat config doctor` (plus a `just doctor`) that reports every
external dependency's availability, the active profile's capability posture, and
the provisioning command to fix each gap.**

1. **A dependency-probe layer (application/adapters).** A small typed
   `DependencyStatus` model (`available: bool`, `detail`, `remediation` command)
   and per-service probes: Ollama reachability + vision-model presence (fast
   `/api/tags` read), Playwright browser-binary presence, Google credential
   presence (reuse the `GoogleAuthError` typing), subprocess-CLI PATH (reuse
   `is_llm_provider_available`). Probes never raise on absence — they return a
   typed status.

2. **Close the Ollama headline gap.** Before the vision inference, probe Ollama;
   on unreachable/model-missing, raise the existing typed
   `PurchaseInvoiceEvidenceInputError` / a `LLMClassifierError`-class refusal (which
   the classify CLI already catches) carrying a `Notice` that names the fix
   (`ollama serve` / `ollama pull <model>`). Also widen the classify CLI to catch
   `LLMProviderError` and connection errors and render them as the same instructive
   refusal — no raw traceback. Add an Ollama/vision row to `aeat app ledger
   providers`.

3. **Playwright remediation hint.** The `BrowserError(BROWSER_LAUNCH_FAILED)`
   message gains the `playwright install chromium` remediation when the failure is
   browser-not-installed.

4. **pyproject capability-mapped extras + torch relocation.** Introduce
   `[project.optional-dependencies]` extras that mirror capabilities (`vision`,
   `google`, `browser`) over a leaner core, and move `torch` out of runtime
   `[project.dependencies]` into the dev/rag group it actually serves (or a
   `[dev]`/rag extra), removing the deptry suppression. The default install keeps
   working; the extras make the capability/dependency surfaces congruent.

5. **A single `aeat config doctor`.** Under the `config` family, a read-only report
   that, for every external service, prints: dependency availability (from the
   probe), the active profile's capability posture (from ADR A's resolver), the
   global safety posture, and — when a gap exists — the exact remediation command
   (`ollama pull …`, `playwright install chromium`, `aeat config google …`,
   `aeat config profile capabilities set …`). It emits the typed envelope + notices
   and a non-zero exit when a required dependency for an opted-in capability is
   missing. This is the product-side "is my workstation set up for what I asked
   for" the retired `aeat doctor` used to be.

6. **`just doctor` + provisioning recipes + fixes.** A `just doctor` aggregate that
   runs `aeat config doctor` and the dev-toolchain checks; fix the broken
   `env-playwright` (point it at the real browser-health path or `playwright
   install`), add `env-vision` (ollama model pull guidance) and a `provision`
   recipe, make `bootstrap` end by running `just doctor`, and reconcile the
   README/justfile so there is one documented entry point.

## Rationale

The graceful paths already in the tree are the template; the work is to bring the
two ungraceful paths (Ollama vision, Playwright) up to that bar and to give the
operator one place to see and fix gaps. Routing every missing-dependency outcome
through the typed refusal/Notice channel (not a traceback, not a silent skip)
satisfies `cli-notices-are-the-only-diagnostic-channel` and
`no-silent-under-declaration`. Mapping extras to capabilities makes the install
surface mirror the runtime opt-in surface, so "I want vision" maps to one extra and
one doctor row. A single `aeat config doctor` replaces the dissolved
`aeat doctor` from the provisioning angle without re-adding a third CLI root.

## Consequences

- A fresh-workstation operator runs one command (`just doctor` / `aeat config
  doctor`) and gets a per-service table of availability + the exact fix — no more
  unguided tracebacks.
- `classify --read-evidence` with Ollama down/model-missing now refuses
  instructively instead of crashing — the headline reliability win.
- The default install can become leaner over time as integrations move behind
  extras; the doctor makes the capability/dependency/safety axes legible together
  (it consumes ADR A's resolver, so the two ADRs ship as one coherent surface).
- Cost/risk: probes add a small pre-flight latency (bounded by short timeouts);
  the `torch` relocation must be verified against the vaultspec-rag dev workflow so
  contributors' RAG still installs.
- Pitfall: the doctor must not itself crash when a probe target is absent — every
  probe returns a typed status, never raises.

## Codification candidates

- **Rule slug:** `missing-dependency-is-a-typed-refusal-with-remediation`.
  **Rule:** When an external dependency (Ollama/model, Playwright browser, Google
  credentials, a provider CLI) is unavailable, the runtime MUST surface a typed
  refusal / `Notice` that names the exact provisioning command, never a raw stack
  trace and never a silent no-op; a new external-service integration MUST ship its
  probe + remediation string and a `config doctor` row. Deferred until the doctor
  surface ships and a review confirms the ungraceful paths are closed.

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

<!-- Example:

- **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
