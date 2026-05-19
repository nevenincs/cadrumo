---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-adr]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy]]"
---

# `schema-hardening` audit: cross-revision drift inventory

## Mandate

Per the AEAT registry design contract every casilla id has
identical legally-bound responsibilities across every revision of
a modelo. A casilla declared as `data_type = "decimal"` with
`semantic_role = "base_imponible_irpf"` in M100/2020 must declare
the same shape in M100/2025. Drifting these fields is a critical
correctness issue: it means the calculation engine treats the
same legal concept as two different things depending on which
revision it loads.

## Snapshot

A standalone drift scan against the current corpus surfaced
**291 strict-legal drift cases** spanning the fields
`data_type`, `semantic_role`, and `constraints`. Fields where
drift is legitimately tolerated (`label`, `section`, `formula`,
`legal_refs`, `source_refs`) were excluded from the count
because BOE phrasing, form layout, and authority chains evolve
across revisions in ways that don't change the underlying legal
concept.

| modelo | drift cases | dominant pattern |
|--------|------------:|------------------|
| M100   | 287 | `data_type = "decimal"` (2020) vs implicit-default `money` (2025); explicit-vs-default declaration drift across the IRPF intermediate-precision casillas |
| M123   | 4 | id-reuse across revisions: casilla 02 means "Numero de perceptores" (integer) in 2019-2023 and "Base de retenciones" (money) in 2024+; same for 03/07/08 |
| M202   | 14 | minor data_type / constraints drift across LIS revisions |
| M369   | 2 | `decl.periodo` role-binding consistent but period-family-specific (esquema-exterior uses EXT-1T..4T, esquema-union uses 1T..4T, esquema-importacion uses 01..12); legitimately divergent |

## Patterns by severity

### S1: id reuse for unrelated concepts

The most severe class. AEAT has repurposed casilla numbers between
form versions; the registry has carried the reuse silently. Known
instances:

- **M100/0700**: "Parte estatal: Importe de la deducción" in
  2020-2023; "Resultado a ingresar o a devolver" in 2024-2025.
  Already caught by the role rollout — only 2024/2025 carry
  `resultado_ingresar_o_devolver_irpf`.
- **M123/02**: "Numero de perceptores" (integer) in 2019-2023;
  "Base de retenciones" (money) in 2024-y-siguientes. Two
  completely unrelated concepts on the same id.
- **M123/03, 07, 08**: similar pattern — form layout was
  renumbered in 2024 and the registry preserved the legacy
  numbering on the old revisions.

Remediation: separate casilla ids per revision-family. The 2024+
M123 casillas should be renamed (e.g., `02-v2024`) or the
2019-2023 set should be (e.g., `02-legacy`). Either is a schema
edit affecting calculation engine references; cannot be done
unilaterally.

### S2: explicit-vs-default data_type drift

The bulk of M100's 287 cases. The 2020 revision declares
`data_type = "decimal"` explicitly on many casillas; the 2025
revision omits the declaration and the schema default (`money`)
applies. The legal value type effectively flipped from decimal
to money for hundreds of IRPF casillas.

Two interpretations:

- **A: legitimate evolution.** AEAT moved IRPF intermediate
  fields from decimal precision to money precision in 2025. The
  2020-2023 declarations are correct for those revisions; the
  2024-2025 omissions are correct (intentional simplification).
  In this case the drift is a *feature*, not a bug, and the
  validator should record but not block.
- **B: authoring drift.** The 2024-2025 modeller simply forgot to
  declare `data_type = "decimal"` and the default silently
  replaced it. In this case every affected casilla needs the
  explicit declaration restored.

Interpretation A is the operating assumption pending AEAT-source
verification. The validator emits warnings; no fatal block.

### S3: cross-revision role-or-constraint drift

The four M123 cases above plus a small number of intentional
divergences where role + constraint reconciliation across
revisions hasn't fully landed. M123/07 (cuota_a_ingresar in
2024+, no role in 2019-2023) is an artifact of incremental
rollout; reconciling means either retroactively roling the older
revisions or accepting that the role lands only on currently-
filed revisions.

## Wiring decision

The validator function
`_validate_cross_revision_casilla_consistency` is implemented and
tested. The snapshot-build pipeline emits **warnings** for every
drift case rather than failing the load, because the corpus
carries 291 historical drift instances that need staged
remediation across multiple agents.

`RegistryValidator.validate_registry` calls
`_emit_cross_revision_drift_warnings` after the other consistency
gates; flipping that one line to `failures.extend(...)` switches
to fatal enforcement.

## Staged remediation path

1. **S1 (id reuse)**: design decision required. Cleanest
   resolution is per-revision-family ids (e.g., `02-v2024`).
   Affects every formula and binding that references the
   renamed ids. Single-PR atomic landing.
2. **S2 (decimal vs money)**: AEAT-source verification needed.
   Read the M100/2025 BOE dictionary to confirm whether
   `data_type` was deliberately simplified. If A, document and
   tolerate. If B, restore the explicit declarations.
3. **S3 (role/constraint drift)**: retrofit older revisions to
   match the canonical shape declared on the latest revision.
   Already happening as side-effect of monetary-role rollouts;
   the warning surface highlights remaining gaps.
4. **Final**: flip the wiring to fatal once all three classes
   are reconciled. The validator stays; the corpus catches up.

## Acceptance

This audit documents the corpus state on 2026-05-19. The drift
count is the baseline; subsequent rollouts should reduce it.
A follow-up audit at the next milestone records progress.
