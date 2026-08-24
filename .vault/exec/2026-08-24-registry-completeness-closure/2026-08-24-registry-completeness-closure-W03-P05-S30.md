---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e2ecbf3ecefb620a24690c5f832e323c2c68ae61d45cf147465fe20ac56ca468'
step_id: 'S30'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---




# Verify every shipped modelo and revision localization key across supported output locales

## Scope

- `dev/locales/`

## Description

- Discover the canonical Modelo locale compiler, resolver, scanner, and catalogue-routing surfaces with Vaultspec-RAG, then confirm the unique builder declarations by exact source audit.
- Add a registry-derived runtime gate that compares the scanner inventory to the keys attached to every loaded Modelo, revision, construct, casilla, help, and alias surface.
- Resolve every required presentation scalar and every authored optional scalar through each supported output locale using the public schema accessors.
- Add mutation bites for an unresolvable real casilla label and a second canonical identity-builder declaration.

## Outcome

- The loaded corpus contains 58 Modelos, 102 revisions, 26,066 casillas, 162 constructs, no aliases, and 55,095 derived Modelo-schema locale keys.
- The new focused gate passes all five checks. It establishes that the scanner equals the live schema inventory, the public accessors render every required scalar across the supported output locales, and no canonical locale-key builder is redeclared outside `_modelo_localization.py`.
- Spanish continues to be enforced by the required resolver paths. Optional revision labels and help remain optional; their absence is not promoted into unsupported source text, while any authored value must be non-blank and render successfully.

## Notes

- No locale catalogue was edited. A general `dev.locales audit` remains red on concurrent non-Modelo locale work: two missing adapter error keys and one stale flow key in all catalogue sets.
- The shared full `bundled_authority()` validation is concurrently red on fourteen Modelo 303 construct deadline-source-reference findings. This Step's localization gate intentionally uses the canonical schema loader, as does the production locale scanner, and makes no claim that the unrelated cross-layer authority gate passed.
