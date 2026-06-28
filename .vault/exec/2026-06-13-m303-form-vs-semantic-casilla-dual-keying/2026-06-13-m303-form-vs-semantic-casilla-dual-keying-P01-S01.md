---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S01'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Author the authoritative box-to-semantic projection map as a reference document, pairing each in-scope cuota box with its single semantic casilla id, cross-checked box-label against semantic-label, and copying each box's existing legal_refs

## Scope

- `.vault/reference/2026-06-13-m303-form-vs-semantic-casilla-dual-keying-reference.md`

## Description

- Read both casillas TOML parts read-only and cross-checked every box label against its candidate semantic source label.
- Authored the authoritative box-to-semantic projection map as the feature reference document.
- Paired each in-scope cuota box (09/06/03/11/13/27 devengado, 29/33/37/45 deducible) with its single semantic casilla id.
- Copied each box's existing `legal_refs` verbatim into the map (devengado boxes carry art. 88/90/91; deducible carry art. 92/94/95) rather than rewriting to the narrower ADR prose.
- Documented which boxes REMAIN manual (base, tipo, recargo, regimen simplificado, informativa) so the advisory narrowing stays honest.

## Outcome

- Reference document committed with a complete 10-box projection table, the box-37 collision resolution, and the advisory-narrowing consequence.
- Box 11 source pinned to `iva.autorepercutido.intracomunitaria.devengado` (the official 10/11 parity casilla), NOT the netted `iva.autorepercutido.intracomunitaria`.

## Notes

- No code or TOML changed in this Step; reference-only.
