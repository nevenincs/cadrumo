---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-adr]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: cross-revision drift inventory

## Mandate

Per the AEAT registry design contract every casilla id has
identical legally-bound responsibilities across every revision of
a modelo. A casilla declared with role X and data_type Y in
revision A must declare the same in revision B. Drifting these
fields is a critical correctness issue: it means the calculation
engine treats the same legal concept as two different things
depending on which revision it loads.

## Snapshot (corrected)

A direct multi-line-aware drift scan against the current corpus
surfaces **10 strict-legal drift cases** under the validator
signature `(label, section, data_type, semantic_role,
legal_refs)`.

An earlier scan reported 291 cases; that count was inflated by
a regex that couldn't span multi-line `legal_refs` arrays and
treated them as drift. The validator implementation parses the
real pydantic-validated objects, so the validator's enforcement
surface sees 10 not 291.

| modelo | cases | cause |
|--------|------:|-------|
| M123   | 8 | AEAT renumbered the form between 2019-2023 and 2024-y-siguientes: casillas 01-08 carry completely different concepts in each revision. |
| M369   | 2 | `decl.periodo` declared once per OSS esquema (exterior, union, importacion); each esquema uses a legally-distinct period family. |
| **total** | **10** | |

## Case classification

### M123: AEAT form renumbering between revisions

The 2024-y-siguientes revision of M123 renumbered the form. Every
casilla id from 01 through 08 carries an entirely different
concept compared to the 2019-2023 revision:

| id | 2019-2023 | 2024-y-siguientes |
|----|-----------|---------------------|
| 01 | "Numero de perceptores" | "Numero de rentas dividendos y participaciones" |
| 02 | "Base de retenciones e ingresos a cuenta" (money) | "Numero de rentas resto" (integer) |
| 03 | "Retenciones e ingresos a cuenta" (money, retenciones_ingresos_a_cuenta) | "Numero de rentas total" (integer) |
| 04 | "Ingresos de ejercicios anteriores" | "Base dividendos y participaciones" |
| 05 | "Regularizacion" | "Base resto de rentas" |
| 06 | "Suma de retenciones y regularizacion" | "Base total" |
| 07 | "Resultado de anteriores autoliquidaciones" | "Retenciones dividendos y participaciones" (retenciones_ingresos_a_cuenta) |
| 08 | "Resultado a ingresar" (cuota_a_ingresar) | "Retenciones resto de rentas" (retenciones_ingresos_a_cuenta) |

This is the AEAT id-reuse pattern. The casilla number is the
form's printed cell label, which AEAT renumbers freely when
re-issuing a form. The validator catches it correctly but the
"fix" requires per-revision-family ids — either keep `01-08`
on one revision and rename the other to `01-v2024..08-v2024`,
which touches every formula/binding/export_refs entry that names
those ids.

Remediation path: a separate `m123-renumbering` plan that
covers the rename + downstream consumer updates atomically. Not
in scope for the schema-hardening landing.

### M369: per-esquema period casillas

The `decl.periodo` casilla appears in three M369 revisions, one
per OSS scheme (esquema-exterior, esquema-union, esquema-importacion).
Each declares a different period family with an explicit label:

- esquema-exterior: `"Periodo trimestral del esquema exterior (EXT-1T / EXT-2T / EXT-3T / EXT-4T)"`
- esquema-union: `"Periodo trimestral (1T / 2T / 3T / 4T)"`
- esquema-importacion: `"Periodo mensual (01..12)"`

Each esquema files on a legally-distinct cadence; the casilla
label encodes which. This is legitimately divergent — the same
casilla id carries the same role (`filing_period`) and the same
data_type (`period_code`), with only the label encoding the
sub-scheme. The drift surface flags it but the divergence is
intentional.

Remediation path: either accept (current state) or split into
three distinct casilla ids (`decl.periodo-exterior` etc.) so
each esquema's filing_period role lands on its own id.

## Severity-band remediation

- **S1 (AEAT renumbering, M123 8 cases)**: defer to a separate
  m123-renumbering plan. The schema-hardening campaign documents
  the drift; the rename is a follow-on structural change.
- **S2 (per-esquema variance, M369 2 cases)**: accept. The
  divergence is legitimate.

## Wiring

The validator function `validate_cross_revision_casilla_consistency`
(public, fatal) is implemented. Snapshot-build wiring at
`RegistryValidator.validate_registry` calls the soft
`_emit_cross_revision_drift_warnings` variant, which emits one
`warnings.warn` per drift case rather than raising.

When M123 lands its renumbering and M369 lands its esquema
split (or accepts the variance via an aliases mechanism on
labels), the wiring flips to fatal by changing one line in
`_validate.py`:

```
- _emit_cross_revision_drift_warnings(modelo_tuple)
+ failures.extend(_validate_cross_revision_casilla_consistency(modelo_tuple))
```

## Validator test surface

`test_cross_revision_drift.py` covers 10 cases:

- Identity (same casilla across revisions passes).
- Per-field drift catches (label, section, data_type, semantic_role, legal_refs).
- Single-revision casilla tolerance.
- Three-revision-one-diverges canonical-order semantics.
- Multi-modelo independence.
- Canonical revision appears in failure message.
- One real-corpus test that loads the bundled registry and asserts
  the M123/01 label drift is surfaced — this proves the validator
  works against the actual committed state.

## Acceptance — corpus is now drift-free

Both remediation paths landed in the same session as this audit:

- **M369 unification** (commit `a6cbda6e3`): the three
  per-esquema `decl.periodo` casillas now share the label
  "Periodo de la declaracion". The period_code value (`EXT-NT`
  vs `1T..4T` vs `01..12`) continues to encode the esquema
  family; the label no longer needs to. Removes 2 drift cases.
- **M123 -legacy rename** (commit `01c117d56`): the 2019-2023
  casillas 01-08 are renamed to 01-legacy through 08-legacy,
  giving the AEAT-renumbered 2024+ revision a clean canonical
  namespace. 34 lines touched (casilla declarations + formula
  / binding / export references inside the 2019-2023 revision
  block). Removes 8 drift cases.

Cross-revision drift count goes from 10 to **zero**. The
validator wiring at `RegistryValidator.validate_registry`
already calls the fatal
`_validate_cross_revision_casilla_consistency` (since commit
`2f352d9fa`); the gate now enforces strictly because the corpus
is clean.

A future modeller introducing a casilla with a divergent shape
across revisions will fail registry load. The schema-hardening
campaign's core directive — *every year every casilla has
identical and legally bound responsibilities* — is now enforced
at the load boundary, not just documented.
