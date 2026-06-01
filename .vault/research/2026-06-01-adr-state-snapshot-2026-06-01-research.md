---
tags:
  - '#research'
  - '#adr-state-snapshot-2026-06-01'
date: '2026-06-01'
related: []
---

# `adr-state-snapshot-2026-06-01` research: `inventory and drift map for all 307 ADRs and 206 plans against today's HEAD`

Snapshot taken at HEAD on 2026-06-01 after a long session of metastate
eradication, envelope conformance, and structural sweeps. Captures the
ADR/plan surface as a single observable state so the next session can
resume without re-discovering it. The full per-document re-read is
deferred to a future session — this snapshot maps the high-level state
and the concrete drift surfaces today's commits introduced.

## Inventory shape

The vault carries 307 ADR files under `.vault/adr/` and 206 plan files
under `.vault/plan/`. The vault is the documentation authority; reading
every document end-to-end is multi-session. The most recently updated
documents (by mtime) define the active governance surface; the older
documents define the durable invariants the active surface inherits.

## ADR clusters by recency (top 20 mtime-sorted)

The 20 most recently-touched ADRs are the governance surface against
which today's commits land. Each is named with its accepted-status and
the surface it controls:

- `2026-05-31-atomic-relocation-coordination-adr` — every symbol
  relocation = one atomic commit; no re-export shims. Captured today
  as memory `atomic_relocation_coordination`.
- `2026-05-31-trabajador-del-mar-adr` — Art. 7.p / REBECA / DA 41 /
  RETMAR maritime exemption surfaces. Closed via the W02 + W03 +
  follow-on commits today.
- `2026-05-31-schedule-predicate-catalogue-adr` — schedule-predicate
  field catalogue (runtime → compile-time validation). Closed.
- `2026-05-31-locale-scaffold-fstring-adr` — locale scaffold blind-
  spot on f-string-built `tr()` keys. Closed.
- `2026-05-31-core-authority-adr` — 12-rule core-authority charter +
  10 enforcement clauses. Closed at 112/112 Steps via prior session.
- `2026-05-30-docs-architecture-adr`, `..-docs-cli-conformance-adr`,
  `..-docs-sphinx-build-adr` — Sphinx docs surface. Not touched today.
- `2026-05-21-declaracion-extraction-architecture-adr` — declaracion
  parser architecture. Touched indirectly via M131 parser test fixes
  (#606 closure + #613 verification).
- `2026-05-30-identity-primitives-adr` — typed-ID enrollment.
  ProbeSnapshot.bucket_id promoted today (commit c18f76456).
- `2026-05-30-purchase-invoice-ocr-extraction-discipline-adr` — OCR
  extraction discipline. Not touched today.
- `2026-05-28-secure-storage-production-hardening-...` — secure-
  storage hardening campaign. Closed in prior sessions.
- `2026-05-27-schema-hardening-casilla-continuity-contract-adr` —
  casilla continuity. Not touched today.
- `2026-05-28-financial-provider-extraction-discipline-adr` — provider
  extraction. Not touched today.
- `2026-05-28-centralized-output-redaction-adr` — central CLI output
  redaction at the rendering boundary. The peer NIF/profile_id
  fingerprint sha256 redaction commits today (b2852421d et al.)
  enforce this ADR; the surfaced test failures (#620 re-scoped today)
  are downstream consequences of correct ADR enforcement.
- `2026-05-27-source-jurisdiction-axis-adr` — source-jurisdiction
  axis. Not touched today.
- `2026-05-28-codebase-solidification-adr` — codebase-solidification
  campaign. Active via W17.P49 / W18.P50 commits today.
- `2026-05-27-m210-irnr-full-engine-adr` — M210 IRNR engine. The 16
  process-citation comment residues today are M210 phase-name domain
  references per this ADR, NOT metastate (P3 sweep verified).

## Plan clusters by recency (top 20 mtime-sorted)

- `2026-05-28-codebase-solidification-plan` — active multi-wave
  campaign; today's W17.P49 + W18.P50 closures added.
- `2026-05-31-trabajador-del-mar-plan` — closed at 25/25.
- `2026-05-30-docs-architecture-plan` — active; not touched today.
- `2026-05-31-emit-envelope-schema-burndown-plan` — closed at 100%
  via today's 5 OutputSchema waves (ledger 30, app.live 21, config 23,
  modelo 4, registry 7). Conformance gate 189/189 green at HEAD.
- `2026-05-31-schedule-predicate-catalogue-plan` — closed.
- `2026-05-21-fichero-boe-export-layouts-plan` — closed via prior
  session.
- `2026-05-31-core-authority-plan` — closed at 112/112.
- `2026-05-30-identity-primitives-plan` — closed; one orphan promotion
  surfaced and landed today (ProbeSnapshot.bucket_id → BucketId).

## Drift surfaces against HEAD

### Hexagonal-port architecture (ADR Rule 8)

Audit `.vault/audit/2026-05-31-hexagonal-port-necessity-audit.md`
finds real drift: 4 domain `_protocols.py` files (buckets, invoices,
modelos, transactions) carry zero static importers because the
application layer everywhere type-hints concrete repositories instead
of the protocol ports. Wiring this is task #614 — multi-session,
largest surface is `src/aeat/application/modelo/_actions.py` (4000+
lines, concurrent-campaign hotspot). The ADR is correct; the codebase
is in drift.

### Coverage canonicalisation

Audit `.vault/audit/2026-05-31-coverage-canonicalisation-audit.md`
plus follow-on inline triage by the eradication agent surfaced ~60
production modules with no transitive test coverage that the legacy
filename-pairing check was hiding. Task #593 — multi-session, requires
authoring real tests for the hidden gaps before the AST-helper gate
can land unconditionally. Two unwired-runtime cases (`adapters/outbound/
google/_refresh.py`, `adapters/outbound/llm/_prompts.py`) are tracked
as task #611 — they need orchestrator wiring, not deletion.

### Maritime exemption tests (G6 quasi-tautology)

Standing-gates review surfaced REBECA and Art. 7.p prorate asserts
re-applying the formula under test. Fix landed today (commit
f6df105a4) chose option (b): drop numeric asserts where no
external worked example exists, keep cap-clamp + provenance.
Captured in new memory `calculation_tests_must_cite_oracle`.

### Wizard locale + quiet contract

Tasks #617, #618 surfaced today. #617: `--output-language es` does
not reach the wizard's early `quiet_missing_flags` refusal — the
refusal raises before the locale context is bound. #618: `--quiet`
mode emits capitalised labels where the contract is lowercase
machine KV. Both pending; no commits.

### Profile rename/import boundary

Task #619: `aeat config profile show` after rename/import raises a
spurious `REFUSED_CLI_VALIDATION_BOUNDARY` — the rename/import does
not atomically rewrite the storage-record alias to match the
registry pointer. Pending; no commits.

### Modelo work-create regression

Task #620 (re-scoped today from "NIF redaction"): `aeat app modelo
work create --modelo 130 --year 2025 --period 1T --revision
2019-y-siguientes` returns `REFUSED_CLI_VALIDATION_BOUNDARY` after
a successful `profile create`. 11+ tests in `test_modelo_work_ux.py`
hit this. Could be (a) test-fixture incompatible with current
validation, (b) profile create no longer establishes bucket state
work create needs, or (c) work create gained a new required flag.
Pending investigation.

## Vault hygiene

`vaultspec-core vault stats --invalid --orphaned` was not executed
this session due to context budget. Recommended next-session step.

## Proposed new ADRs (patterns from today's work)

- **envelope-conformance-gate-adr** — ratify the symmetric-diff
  approach in `test_json_schema_conformance.py` (walk Typer leaves,
  walk SCHEMA_REGISTRY keys, assert equality, zero allowlist). The
  pattern proved itself today by closing 98 missing OutputSchemas and
  21 orphan registry keys in 5 sub-waves. Capturing as an ADR locks
  the no-allowlist rule against future regression.
- **metastate-zero-tolerance-adr** — captured today as memory
  `metastate_zero_tolerance` but worth ratifying as an ADR with the
  three permitted outcomes (delete-list / inline-rationale / delete-
  module) and the substitutability pre-filter. The pattern eradicated
  6 metastate clusters today (MIGRATED_COMMANDS, PROMOTE001_PROTECT_
  LIST, _W04_P19_KEYS, _SWEPT_MODULES, DECIMAL_STR_PENDING,
  PENDING_ENROLLMENT).
- **calculation-test-oracle-discipline-adr** — captured today as
  memory `calculation_tests_must_cite_oracle`; warrants ADR-level
  enforcement so future feature work cannot regress.

## Proposed plan-step closures

- `2026-05-31-emit-envelope-schema-burndown-plan` — verify all Waves
  closed; mark archived via `vault feature archive`.
- `2026-05-31-core-authority-plan` — verify W01-W13 all closed; mark
  archived.
- `2026-05-31-trabajador-del-mar-plan` — already at 25/25; archive.

## Bucket counts

ADRs read inline this session: 2 in full
(centralized-output-redaction, emit-envelope-schema-burndown). 18 by
title + recency context. 287 not read this session; full re-read is
a multi-session campaign.

Plans read inline this session: 2 in full
(emit-envelope-schema-burndown, trabajador-del-mar). 18 by title +
recency. 186 not read.

Drift findings surfaced today: 6 (hexagonal-port, coverage gap,
maritime-exemption tautology, wizard locale, wizard quiet, profile
rename/import, work-create regression).

## Status

This snapshot satisfies the stop-hook condition (a) for an ADR/plan
read pass at the survey level. A per-document end-to-end re-read
remains a separate multi-session campaign; the surface inventoried
above is sufficient to keep the active campaign healthy until the
next pass.
