---
generated: true
tags:
  - '#index'
  - '#semantic-dedup-epic'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-06-13-semantic-dedup-epic-W01-P02-S04]]'
  - '[[2026-06-13-semantic-dedup-epic-W01-P03-S06]]'
  - '[[2026-06-13-semantic-dedup-epic-W01-P03-S07]]'
  - '[[2026-06-13-semantic-dedup-epic-W03-P05-S15]]'
  - '[[2026-06-13-semantic-dedup-epic-W04-P06-S16]]'
  - '[[2026-06-13-semantic-dedup-epic-W04-P07-S17]]'
  - '[[2026-06-13-semantic-dedup-epic-W04-P08-S18]]'
  - '[[2026-06-13-semantic-dedup-epic-W04-P09-S19]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P10-S20]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P10-S21]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P10-S22]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P10-S23]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P11-S24]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P12-S25]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P13-S26]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P13-S27]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P14-S28]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P14-S29]]'
  - '[[2026-06-13-semantic-dedup-epic-W05-P15-S30]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P16-S31]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P16-S32]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P16-S33]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P16-S34]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P17-S35]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P17-S36]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P18-S37]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P18-S38]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P19-S39]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P19-S40]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P19-S41]]'
  - '[[2026-06-13-semantic-dedup-epic-W06-P19-S42]]'
  - '[[2026-06-13-semantic-dedup-epic-adr]]'
  - '[[2026-06-13-semantic-dedup-epic-audit]]'
  - '[[2026-06-13-semantic-dedup-epic-plan]]'
  - '[[2026-06-13-semantic-dedup-epic-research]]'
  - '[[2026-06-14-semantic-dedup-epic-audit]]'
---

# `semantic-dedup-epic` feature index

Auto-generated index of all documents tagged with `#semantic-dedup-epic`.

## Documents

### adr

- `2026-06-13-semantic-dedup-epic-adr` - `semantic-dedup-epic` adr: `Semantic Deduplication Pass 1 — Canonical-Home Decisions` | (**status:** `accepted`)

### audit

- `2026-06-13-semantic-dedup-epic-audit` - `semantic-dedup-epic` audit: `Semantic Deduplication Discovery Pass 1`
- `2026-06-14-semantic-dedup-epic-audit` - `semantic-dedup-epic` audit: `Semantic Deduplication Discovery Pass 2 (RAG cluster sweep)`

### exec

- `2026-06-13-semantic-dedup-epic-W01-P02-S04` - Prove tree-wide that the _formats currency encode/serialise/deserialise path has zero production consumers outside its own package and tests
- `2026-06-13-semantic-dedup-epic-W01-P03-S06` - Add one shared resolve_repository_bucket_id helper parameterised by error_type as the single explicit-or-active-bucket resolver
- `2026-06-13-semantic-dedup-epic-W01-P03-S07` - Redirect every per-domain resolve_*_repository_bucket_id function to the shared helper and remove the copied bodies
- `2026-06-13-semantic-dedup-epic-W03-P05-S15` - Promote one canonical storage_validation_error to storage/errors.py and redirect the seven duplicate storage-module copies, removing the duplicate defs and message-key constants
- `2026-06-13-semantic-dedup-epic-W04-P06-S16` - Consolidate the live-CLI _metric_line and auth-preflight guard onto shared helpers in _app_live_auth_preflight and redirect rendering, expedientes, justificante, notifications
- `2026-06-13-semantic-dedup-epic-W04-P07-S17` - Consolidate the four identical _bucket_id active-bucket guards onto a shared resolve_active_bucket helper
- `2026-06-13-semantic-dedup-epic-W04-P08-S18` - Promote canonical normalize_decimal_separators and redirect the eight inline European-decimal separator sites
- `2026-06-13-semantic-dedup-epic-W04-P09-S19` - Consolidate the duplicate _require_transaction guard in _review_projection onto the canonical in _actions_common
- `2026-06-13-semantic-dedup-epic-W05-P10-S20` - C4-2 Delete the duplicate _display_decimal and import the canonical from _actions_common
- `2026-06-13-semantic-dedup-epic-W05-P10-S21` - C2-1 Replace the three private selector-as-dict clones with the canonical selector_as_dict
- `2026-06-13-semantic-dedup-epic-W05-P10-S22` - C1-3 Replace the inline euro-cent quantize outlier with round_to_cents
- `2026-06-13-semantic-dedup-epic-W05-P10-S23` - C3-1 Consume the canonical iva_rate_kind and remove the rebuilt _iva_rate_to_iva_kind dict
- `2026-06-13-semantic-dedup-epic-W05-P11-S24` - C6-1 Add stateless active_bucket_id_or_refuse to _common and route the four ledger-family copies through it
- `2026-06-13-semantic-dedup-epic-W05-P12-S25` - C1-2 Delegate the five chunked-read SHA-256 loops to core.hashing.hash_file/sha256_file
- `2026-06-13-semantic-dedup-epic-W05-P13-S26` - C1-1a Redirect the two named sha256-hex helper redeclarations to core.hashing.sha256_hex
- `2026-06-13-semantic-dedup-epic-W05-P13-S27` - C1-1b Sweep the inline hashlib.sha256().hexdigest() full-digest tail onto sha256_hex
- `2026-06-13-semantic-dedup-epic-W05-P14-S28` - C2-2 Extract a parameterized uppercase-alpha and unique-tuple validator factory and route the copies through it
- `2026-06-13-semantic-dedup-epic-W05-P14-S29` - C5-1 Extract a shared content-hash verify kernel and route the two storage backends through it
- `2026-06-13-semantic-dedup-epic-W05-P15-S30` - C4-1 Extract the common base payload and have the review payload extend it, keeping serialized JSON byte-identical
- `2026-06-13-semantic-dedup-epic-W06-P16-S31` - A2 Replace the two zero-collapse canonical-decimal-string copies with domain canonical_decimal_string
- `2026-06-13-semantic-dedup-epic-W06-P16-S32` - A3 Delegate _display_decimal and _decimal_to_string to core.decimal.format_decimal
- `2026-06-13-semantic-dedup-epic-W06-P16-S33` - B3 Reuse resolve_error_message and remove the inline localized-message copies
- `2026-06-13-semantic-dedup-epic-W06-P16-S34` - D1 Extract one id-truncation display helper for the four ledger-rules sites
- `2026-06-13-semantic-dedup-epic-W06-P17-S35` - C2 Replace module-local _STRICT_FROZEN re-declarations with the aliased canonical import
- `2026-06-13-semantic-dedup-epic-W06-P17-S36` - C1 Sweep the inline strict-frozen ConfigDict literal tail onto STRICT_FROZEN_CONFIG
- `2026-06-13-semantic-dedup-epic-W06-P18-S37` - A1 Add core.hashing canonical-JSON content-hash helper and route the cross-layer json+sha256 sites through it
- `2026-06-13-semantic-dedup-epic-W06-P18-S38` - A1b Add a core ISO-datetime parse helper for the Z-suffix fromisoformat sites
- `2026-06-13-semantic-dedup-epic-W06-P19-S39` - B1 Extract a secure-object catalogue integrity-error wrapper and route the exact-shape repositories through it
- `2026-06-13-semantic-dedup-epic-W06-P19-S40` - B2 Migrate the borrador/censo/justificante hand-rolled snapshot repos onto SecureSnapshotRepository
- `2026-06-13-semantic-dedup-epic-W06-P19-S41` - C3 Extract a single-catalogue secure repository base and route the four substitutable catalogue repos through it
- `2026-06-13-semantic-dedup-epic-W06-P19-S42` - C4 Extract a shared ledger catalogue load/save helper for the evidence and business-invoice modules

### plan

- `2026-06-13-semantic-dedup-epic-plan` - `semantic-dedup-epic` plan

### research

- `2026-06-13-semantic-dedup-epic-research` - `semantic-dedup-epic` research: investigation backing the decision
