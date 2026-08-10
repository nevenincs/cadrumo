---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:af451e68785bc78237b60a5f883b0ff14badbefadf959df19f4e89ff01aa7062'
step_id: 'S32'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Resolve only absent exact-anchor wire facts through the validated render profile, refuse official-content conflicts and uncovered or hash-drifting profiles, keep variable envelopes outside fixed-width output, and add the canonical profile digest and schema version to provenance

## Scope

- `dev/registry/`
- Narrow canonical-boundary repair for stale development-tool `CasillaId` imports after the public forwarding alias was deleted.

## Description

- Require the exact SHA-bound `RenderProfile` and `RenderProfileSourceEvidence` throughout rendering, validation, publication, recovery, check mode, and provenance verification.
- Keep `ExportTreeTransportProfile` transport-only and remove the ambiguous `ExportRenderProfile` name without an alias.
- Resolve only blank numeric source fields through exact validated profile anchors; retain every nonblank official wire fact unchanged and refuse uncovered anchors or variable envelopes.
- Map every public singleton export policy explicitly to one generated schema shape, carrying the exact enumeration domain and refusing unknown or generic fallthrough behavior.
- Add one order-independent digest over every profile rule, membership, fragment identity, allowed-value domain, and resolved source-evidence fact.
- Hard-cut the provenance, generator, and render-normalization schemas and require render-profile schema and digest fields in emitted and loaded manifests.
- Verify interrupted publication candidates and live targets against the retry's current joined design, semantic map, rendered layout, profile, and evidence before any move, finalization, rollback deletion, or early return.

## Outcome

Generation now validates the wire-authority profile before creating a target and uses it only when the exact official numeric content cell is absent. Width-17 unsigned and signed amount rules hydrate the canonical decimal and money shapes, and all eleven singleton policies hydrate their exact public schema constraints. The real loader sees exactly the rendered layout, while provenance binds the current profile schema and canonical digest alongside source, map, loader, output, and derivation evidence.

Validation, publication, and check mode require the same profile and evidence rather than accepting a caller-optional or legacy path. Crash recovery re-verifies a journaled package through the canonical provenance verifier with every current authority. Separate real interrupted-journal mutations prove profile drift and source-evidence drift refuse without changing the live target or deleting the retained backup and journal.

The former layout-wide `ExportRenderProfile` is now `ExportTreeTransportProfile`; `RenderProfile` remains the sole wire-authority profile and `render_profile_digest` has one canonical owner. Exact discovery found no compatibility alias, duplicate digest, development-only policy taxonomy, or generic policy mapper. The canonical registry codec remains the only runtime render/parse policy owner.

Focused generation, profile, provenance, publication, recovery, check, and variable-envelope verification passed with 105 tests. The full development-registry lane passed with 165 tests. Scoped Ruff passed, strict scoped BasedPyright reported zero diagnostics, and the production/dev path-isolation gate passed with 23 tests. Independent formal review passed after remediation with no open high, medium, or low findings.

## Notes

The full development-registry run initially exposed four stale `CasillaId` imports left after deletion of the registry forwarding alias. The narrowly authorized repair points `_parity_tapes.py`, `_workbook_parity.py`, `_workbook_parity_models.py`, and `test_workbook_parity.py` directly at the canonical `cadrumo.core` owner; no alias was restored.

A broader schema/filing lane collected 328 tests and retained 19 failures in pre-existing strict fixed-width/XML verification behavior outside S32. An earlier collection attempt also encountered a transient peer core-facade race; the retry collected after that surface stabilized. These boundaries were not weakened or modified.

The shared files also carried concurrent link-detection relocation hunks. Those hunks remain peer-owned and are excluded from this Step's staged payload. Unrelated Modelo 303, relation, auth, TUI, identifier, locale, and plan work remained untouched.
