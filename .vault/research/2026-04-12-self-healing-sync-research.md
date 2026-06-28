---
tags:
  - "#research"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
title: Self-Healing Live-to-Local Sync Runner
related:
  - "[[2026-04-12-playwright-anti-bot-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# research: self-healing sync (issue #11)

## problem

The AEAT portals (sede.agenciatributaria.gob.es, "Mis expedientes",
modelo landing pages) are living HTML surfaces that change without
notice: casillas get added, labels get translated, deadlines
(`vigencia`) extend, portal URLs rotate, occasionally formulas
change. Our local catalogues (corpus snapshots under #17, schema
extractions under #9, manual rules under #25, modelo enum #6,
portal enum #7) are the authoritative local state. When live and
local diverge we must detect it, classify it, and either heal the
local state (bounded) or escalate to a human — we NEVER touch
AEAT-side state. The runner is strictly read-only against AEAT.

## goals

- Detect every kind of divergence a browser fetch can reveal.
- Classify each divergence as ADDITIVE / BREAKING / BENIGN /
  SUSPICIOUS.
- Auto-heal ONLY additive + explicitly allowlisted kinds via
  local-schema migration records (never a destructive write).
- Escalate BREAKING / SUSPICIOUS through structured divergence
  records that a human must resolve.
- Persist every fetch, validation, diff, and heal action for audit.
- Provide a CLI surface so humans can list / inspect / approve /
  reject divergences.
- Stay read-only against AEAT; the "healing" is always local.

## non-goals

- Filing a modelo or mutating AEAT state in any way.
- Multi-user orchestration.
- A UI beyond the CLI listing.
- Remediating AEAT-side errors (retrying server-side failures).
- Notifications beyond the structured log + divergence records.

## constraints (hard)

- **Pydantic v2 strict, everywhere.** Every wire payload, every
  divergence record, every classification result, every healing
  plan, every run result is a strict frozen pydantic v2 model.
  Closed enumerations are `enum.StrEnum`. No bare `dict[str, Any]`
  in public signatures or persisted files.
- **Public API discipline.** Callers import from `aeat.application.sync` only.
  Internal modules are `_`-prefixed.
- **Subpackage layout.** All Python under `src/aeat/application/sync/`.
- **Errors** inherit from `aeat.core.errors.AeatError` via `SyncError`.
- **Logging** via `aeat.core.logging.get_logger(__name__)`.
- **Tests** use pytest, `@pytest.mark.unit` / `@pytest.mark.live`.
  NO mocks/patches/fakes — test doubles are real Protocol-
  conforming classes.
- **Protocol stubs for every in-flight cross-module dependency.**
  Branches #6, #7, #8, #9, #10, #17, #21, #25 are all in flight;
  hard imports would break the branch. Define local Protocol
  contracts and a rebase ticket to swap them in.
- **Read-only against AEAT.**

## investigation: validation library

Pydantic v2 is already mandated project-wide (core tenant, pinned
comment on issue #11). Alternatives (attrs+cattrs, msgspec,
marshmallow) were considered and rejected because:

- The project has standardized on pydantic v2 for every boundary-
  crossing type (`CLAUDE.md` pydantic mandate + memory record).
- pydantic v2 gives strict mode, frozen models, discriminated
  unions, and model_validator hooks for free — exactly what we
  need for the divergence payload union.
- pydantic-settings already owns env vars; one library across the
  boundary layer reduces cognitive load.

Decision: **pydantic v2, strict + frozen where sensible.**

## investigation: diffing approach

Two candidate approaches:

1. **Key-by-key structural diff** (deep-dict-diff). Easy but
   blind to semantics — it flags `label` changes the same as
   `formula` changes, and can't recognise that "a new casilla
   appeared in the middle of the list" is ADDITIVE.
2. **Semantic diff.** Model the live payloads as pydantic
   schemas, model the local state the same way, then hand-roll
   per-field comparators that know the meaning of each field
   (e.g. casilla ID sets, label trees, formula AST, vigencia
   intervals). Each comparator emits typed `DivergencePayload`
   discriminated-union values.

Decision: **semantic diffing.** Structural diffing loses the
information we need to classify; the whole point of the runner
is *classification*, not flagging.

## investigation: bounded auto-heal policy

The safe envelope is **additive + allowlisted**. Anything else
escalates. "Additive" means the new live shape is a pure
superset of the local shape (no field removed, no field's
semantic meaning altered). "Allowlisted" means the specific
divergence kind is in the operator-configured allowlist
(`AEAT_SYNC_AUTO_HEAL_ALLOWLIST`).

Starting allowlist (intentionally small):

- `casilla_added_with_default` — a new casilla appeared in the
  live modelo with a default value, and nothing else changed.
- `label_translation_added` — a translation key appeared in a
  `Translatable` where it was previously missing; does not
  alter authoritative `es`.
- `vigencia_extended` — the modelo's vigencia end date moved
  forward with no other field changes.

Everything else — including `casilla_removed`, `formula_changed`,
`label_es_changed`, `portal_url_changed`, `casilla_type_changed`,
`unknown_shape` — classifies as BREAKING or SUSPICIOUS and routes
to a PENDING divergence record for human review.

The key invariant, which code review must enforce: **even with
`auto_heal=True`, BREAKING and SUSPICIOUS records never auto-
apply.** Auto-heal is gated twice: classification ∈ ADDITIVE AND
kind ∈ allowlist. This is the single most important correctness
property of the runner.

## investigation: live fetch approach

- Authenticated Playwright browser session via `aeat.adapters.outbound.aeat.browser.
  BrowserSession` (already merged from #16).
- Certificate loaded via #8's planned `LoadedCertificate` +
  `preload_into_browser_context` surface — Protocol-stub for now.
- Read-only navigation; no form submission against AEAT.
- Rate-limited via existing `aeat_rate_limit_delay_seconds`.
- Retry on transient navigation errors, bounded by
  `AEAT_SYNC_RETRY_MAX` / `AEAT_SYNC_RETRY_BACKOFF_S`.

## investigation: persistence

- Divergence records are pydantic v2 models; persistence goes
  through a `DivergenceRecordRepository` Protocol so #10's real
  storage layer can drop in without touching the runner.
- Default sink until #10 lands: JSON files under
  `AEAT_SYNC_DIVERGENCE_FILE_DIR` (`var/divergences/`) — one file
  per record, `{record_id}.json`.
- STORAGE sink is stubbed and marked rebase-swap.

## open questions

- The exact set of wire schemas will expand as #9 (schema
  extraction) matures — we start with three representative shapes
  (`WireModeloDefinition`, `WireFilingHistory`,
  `WirePortalManifest`) and accept that more will follow.
- The `formula_changed` divergence classification currently
  routes to BREAKING; this is conservative. When #25 (manual
  practico) lands we can cross-reference manual rules and
  possibly reclassify some formula changes as BENIGN.

## references

- Issue wgergely/aeat#11
- Issue wgergely/aeat#6, #7, #8, #9, #10, #17, #21, #25 (cross-
  module stubs)
- `[[2026-04-12-playwright-anti-bot-adr]]`
- `[[2026-04-12-base-module-structure-adr]]`
- `CLAUDE.md` — pydantic mandate, public API discipline, testing
  rules
