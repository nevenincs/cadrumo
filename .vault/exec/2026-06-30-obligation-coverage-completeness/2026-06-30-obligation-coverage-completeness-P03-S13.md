---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S13'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---




# Ratchet UNMODELED_OBLIGATIONS toward AEATs full form set and promote each to a grounded registry definition.

## Scope

- `src/aeat/_data/registry/aeat/modelos`

## Description

- Attempt to promote Modelo 216 (IRNR retenciones e ingresos a cuenta) out of `UNMODELED_OBLIGATIONS` in `src/aeat/core/_modelo.py` into a grounded registry definition, per the S13 ratchet.
- Ground the M216 approving orden and its filing-deadline provision against the bundled authoritative corpus and the IRNR legal catalogue before authoring any registry manifest, revision, or deadline window.
- Verify which bundled orden establishes the M216 deadline versus which merely modifies the form.

## Outcome

M216 is reported ungroundable-this-pass. No registry definition was authored, M216 remains in `UNMODELED_OBLIGATIONS`, and step S13 stays open. The blocker is a genuine bundled-corpus gap, not a modeling gap: the binding provision that establishes the M216 filing deadline is absent from the authoritative corpus.

Grounding findings:

- M216 is approved and its deadline is set by Orden EHA/3290/2008, de 6 de noviembre ("por la que se aprueban el modelo 216 ... y el modelo 296"). That orden and its plazo-de-presentacion article are NOT present under the bundled corpus tree; the Reglamento IRNR RD 1776/2004 is likewise absent.
- The bundled Orden HAC/56/2024 (BOE-A-2024-1772) is a MODIFYING orden. Its articulo segundo modifies EHA/3290/2008 only at the "Obligados a presentar el modelo 216" apartado and the retencion desglose; it does not touch the M216 deadline. The "veinte primeros dias naturales de los meses de abril, julio, octubre y enero" deadline text that DOES appear in HAC/56/2024 is the modification of article 5 of Orden EHA/3316/2010, which is the Modelo 210 deadline, not the Modelo 216 deadline. Citing HAC/56/2024 as the M216 deadline binding provision would be the C1 mis-grounding pattern.
- The bundled AEAT M216 instructions (`aeat-modelo-216-procedure`, evidence tier official_source_guidance) carry the deadline verbatim ("Declaracion trimestral: durante los veinte primeros dias naturales de los meses de abril, julio, octubre y enero, por las retenciones e ingresos a cuenta que correspondan al trimestre natural inmediato anterior"; monthly for grandes empresas). Guidance-tier instructions are not the binding establishing provision that `registry-calculation-legal-grounding` requires for a deadline window, so this alone is insufficient grounding.
- What IS already grounded for M216: the withholding obligation (TRLIRNR art 13.1.h, a legal_authority entry in the IRNR catalogue) and two source_refs (the AEAT M216 instructions and the HAC/56/2024 form-layout authority). The only bundled IRNR orden legal_authority entry is `orden-eha-3316-2010:art-1`, which anchors M210, not M216.

To promote M216 in a future pass, the approving/deadline orden EHA/3290/2008 (art 1 approval + art 3 plazo de presentacion) must first be fetched from BOE into the bundled corpus and cross-checked against the live consolidated BOE text, then added as legal_authority entries in the IRNR catalogue with corpus_ref resolving to that bundled text. Only then can a M216 manifest + revision with a legally-grounded trimestral/mensual deadline window be authored without fabrication.

Ratchet status unchanged: `UNMODELED_OBLIGATIONS` still carries M216; residual recognized-unmodeled set is not reduced this pass.

## Notes

- Deferred, not failed: S13 left unchecked because the binding deadline provision is genuinely absent from the bundle. Per the task gate and `legal-grounding-verifies-bundled-authoritative-corpus`, a promotion was not forced.
- The locale catalogues `ca.yml`, `en.yml`, `es.yml`, `hu.yml` are peer-staged in the shared index; had M216 been groundable, the locale leaf would have been deferred per the task's locale-WIP rule. Moot this pass.
- RAG grounding queries run this pass: code search "Modelo 210 IRNR non-resident income tax registry revision deadline"; targeted corpus/grep confirmation of Orden HAC/56/2024 (BOE-A-2024-1772) M216 vs M210 deadline attribution, the IRNR legal catalogue `orden-*` legal_authority inventory, and the bundled corpus normatives listing for EHA/3290/2008 and RD 1776/2004 (both absent).
- Follow-up candidate: fetch Orden EHA/3290/2008 consolidated BOE text into corpus (mirroring the codex M210 EHA/3316/2010 fetch precedent) as the precondition for the M216 promotion.
