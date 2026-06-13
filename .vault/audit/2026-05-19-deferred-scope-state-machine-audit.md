---
tags:
  - "#audit"
  - "#deferred-scope-state-machine"
date: "2026-05-19"
modified: '2026-05-19'
related:
  - "[[2026-05-19-spanish-stem-terminology-authority-adr]]"
  - "[[2026-05-19-code-duplication-sweep-audit]]"
---

# deferred-scope-state-machine audit: AEAT-Sede lifecycle rename (Submitted/Acknowledged/Rejected → Presentada/Aceptada/Rechazada) deferred to a future campaign

## Scope

Captures the deferred future-scope item recorded as Future Scope F1 in the Spanish-stem authority ADR amendment of 2026-05-19. Provides legal-authority grounding, the coder-beta W04.P12 touchpoint survey result, and the persistence-migration concern that motivates deferral. No code edits; inventory and rationale only.

## Reference: ADR future-scope F1

The Spanish-stem authority ADR amendment dated 2026-05-19 declares the canonical AEAT filing lifecycle, per Sede Electrónica verbatim, as:

`Borrador → Pendiente de presentar → Presentada → Aceptada / Rechazada`

The amendment records that English status names elsewhere in the codebase (`Submitted`, `Acknowledged`, `Accepted`, `Rejected`, `Pending`, and adjacent) need a coordinated rename pass and explicitly scopes that pass OUT of the current campaign. This audit is the durable handover record for the future campaign that will execute the rename.

## Legal-authority grounding

- Ley 39/2015 LPAC Art. 27 (BOE-A-2015-10565). The administrative-procedure framework whose vocabulary AEAT inherits for the act of presenting a tax declaration to the administration. The verbatim Spanish for the act of submission is "presentación"; the resulting state of the declaration is "presentada".
- AEAT Sede Electrónica labels (verbatim). The end-user-facing lifecycle labels rendered on `https://sede.agenciatributaria.gob.es/` and in the Modelo justificantes are exactly `Borrador`, `Pendiente de presentar`, `Presentada`, `Aceptada`, `Rechazada`. The English calques in the codebase (`Submitted`, `Acknowledged`, `Accepted`, `Rejected`, `Pending`) lose the gender agreement (with `declaración` / `autoliquidación`) and the Sede-canonical phrasing.
- Stem stability: the legal-authority pass concluded that AEAT Sede labels are stable across at least the Modelo 100 / 130 / 303 / 390 / 232 surfaces; no Sede-internal rename is expected to invalidate this list within the campaign-after-this horizon.

## Touchpoint survey (coder-beta, W04.P12 review)

The W04.P12 cluster review identified approximately seventy touchpoints across fifteen files for the Submitted/Acknowledged/Rejected lifecycle rename. The breakdown:

- About five capitalized class references (e.g. `SubmittedFiling`, `AcknowledgedFiling`, related symbol surface). The `SubmittedFiling → ModeloPresentado` rename is in-scope of the current ADR Section 7 ledger (and Amendment A6); the remaining four class references are status-enum-bearing types whose rename ripples into class-name attributes.
- About sixty-five uppercase enum values (e.g. `DraftStatus.SUBMITTED`, `DraftStatus.ACKNOWLEDGED`, `DraftStatus.ACCEPTED`, `DraftStatus.REJECTED`, `DraftStatus.PENDING`, `FilingFindingSeverity` adjacents, modelo-record lifecycle enums, submission-result enums, and the persisted SQL columns that carry these values as plaintext-or-encrypted strings).

Files concentrated under: `src/aeat/domain/submission/`, `src/aeat/domain/filing/`, `src/aeat/domain/modelos/`, `src/aeat/application/submission/`, `src/aeat/application/workflow/`, `src/aeat/adapters/persistence/storage/sql/_orm.py`, `src/aeat/adapters/persistence/storage/sql/records.py`, plus the CLI payloads under `src/aeat/entrypoints/cli/_modelo_payloads.py` and the operator-facing locale entries.

## Persistence-migration concern

The persisted SQL value strings for the encrypted-at-rest lifecycle columns currently hold the English uppercase values (`SUBMITTED`, `ACKNOWLEDGED`, `ACCEPTED`, `REJECTED`, `PENDING`). Renaming the Python enum without a data-migration step would:

- Invalidate every existing persisted record on first read (Pydantic strict enum validation fails on the old value, the SecureObjectRepository raises, the SQL row appears corrupted).
- Cascade through every roundtrip test that fixtures lifecycle state with non-default values (and the roundtrip-discipline gate requires non-default fixtures, so every roundtrip test under the affected boundary participates).
- Render any operator's existing local SQLite database unreadable across the rename cut.

The data migration is non-trivial because the lifecycle columns are stored inside the encrypted `SecureObjectRepository` payload (not as plaintext SQL strings), which means the migration must:

1. Decrypt each affected row under the existing master key.
2. Translate the lifecycle string in the Pydantic envelope (`SUBMITTED → PRESENTADA`, etc.).
3. Re-encrypt and persist under the same key with a roundtrip-test gate proving strict equality on a populated non-default fixture.
4. Carry an anti-tautology proof: a record persisted under the old value must FAIL to load after the rename (or surface as a typed validation error), not silently translate.

This shape exceeds the boundary of a single-cluster rename and warrants a dedicated campaign with its own ADR, its own roundtrip-test baseline, and its own staged-migration plan (one cluster of records at a time, master-key-rotation alignment with the existing key-rotation cadence).

## Recommendation

Defer the state-machine rename to a dedicated future campaign with explicit data-migration scope. The campaign should carry, at minimum:

- An accepted ADR amending the Spanish-stem authority ADR Future Scope F1 from "future scope" to "in scope: campaign <X>", with the lifecycle vocabulary table, the persistence-column inventory, and the roundtrip-test baseline declared.
- A plan document with a Wave per persistence boundary (modelo records, submission records, workflow records, justificante records) so that each migration step has an isolatable rollback shape.
- A migration script under `src/aeat/application/persistence/` (or analogous) gated by an `AEAT_LIFECYCLE_MIGRATION_ENABLED` opt-in flag, with the dry-run pass as default and a real-mode pass that operates on a key-rotation-aligned schedule.
- A locale sweep tracked as a sibling task to align operator-facing strings with the new Spanish vocabulary; current `cli.app.modelo.*` help text already uses some Spanish forms and the rename consolidates these.

Current-campaign scope (`code-duplication-sweep`) executes the in-flight rename ledger only; it must NOT touch the lifecycle enum values or their persisted forms. The `SubmittedFiling → ModeloPresentado` Section 7 row (Amendment A6) renames the wrapper class only; the lifecycle enum that the wrapper carries stays unchanged and is reserved for the future campaign.

## Cross-references

- ADR: `2026-05-19-spanish-stem-terminology-authority-adr` Future Scope F1 paragraph + Amendment A6 row for `SubmittedFiling → ModeloPresentado`.
- Sweep audit: `2026-05-19-code-duplication-sweep-audit` for the in-flight cluster ledger.
- Glossary: `2026-05-19-spanish-tax-glossary-reference` for the broader Spanish-stem citation set; the lifecycle vocabulary table belongs in the glossary once the future campaign accepts the rename.
