---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:62c53cb60734990b2cc15ab763ae7ff2213e2bb46c31108c5003e302c3ba0618'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# `calculation-export-import-adjudication` `P03` summary

P03 adjudicated seven inbound steps without changing production source,
tests, registry data, or parser implementations.

- Modified: P03.S16-P03.S22 Step Records, the rolling audit, and the plan.
- Created: no production or registry artefacts.

## Description

P03 preserved the existing generic ingestion architecture. Submitted files
continue through the registry-driven export parser; declaration PDFs
continue through `parse_declaracion_bytes` and registry-owned extraction
profiles. No per-Modelo parser was authorized.

| Step | Candidate/window | Gate | Disposition |
|---|---|---|---|
| S16 | Modelo 037 active extraction from 2025-02-03 | F/T/F/F | `retired` |
| S17 | Modelo 200 submitted file, 2025 | T/T/F/T | `delivered-equivalent` |
| S17 | Modelo 200 declaration PDF, 2025 | T/T/T/F | `evidence-gated` |
| S18 | Modelo 308, 2009-2018 | T/F/T/F | `authority-gated` |
| S18 | Modelo 308, 2019+ | T/T/T/F | `evidence-gated` |
| S19 | Modelo 309, 2004-2022 | T/F/T/F | `authority-gated` |
| S19 | Modelo 309, 2023+ | T/T/T/F | `evidence-gated` |
| S20 | Modelo 322, 2008-2025 | T/F/T/F | `authority-gated` |
| S20 | Modelo 322, 2026+ | T/T/T/F | `evidence-gated` |
| S21 | Modelo 353, 2008-2025 | T/F/T/F | `authority-gated` |
| S21 | Modelo 353, 2026+ | T/T/T/F | `evidence-gated` |
| S22 | Modelo 360, 2010-04-01+ | T/T/T/F | `evidence-gated` |

No P03 candidate is `implementation-admitted`.

## Evidence and verification

- S16: 8 selected real-registry tests passed in 44.98 seconds after an
  earlier invalid pytest invocation.
- S17: 7 tests passed in 45.79 seconds. One test described as real redacted
  evidence actually uses a synthetic Modelo 130 fixture and satisfies no
  specimen gate.
- S18-S21 name relevant real suites, but their records do not persist pass
  counts or execution results; this summary does not claim they passed.
- S22's two-suite run timed out after 64.1 seconds without a pytest summary;
  its verification remains inconclusive.
- No sanitized filed declaration PDF or Modelo-specific declaration-parser
  corpus test was found for Modelos 200, 308, 309, 322, 353, or 360.

## Decisions and unresolved gates

- Modelo 037 remains retired in favor of Modelo 036.
- Modelo 200's 2025 submitted-file path is already delivered through the
  generic parser.
- Exact historical declaration-copy authority remains missing for the
  historical Modelo 308, 309, 322, and 353 windows.
- Sanitized filed specimens remain missing for every active declaration-PDF
  candidate.
- Future work must add reviewed registry data and real corpus coverage
  through the existing generic parser, never duplicate parser code.

## Step and commit coverage

- P03.S16: `458630490375f304cd9090bbfe057adb66e3ddab`.
- P03.S17: `1c1c23753c61c26a2db61bbf1cb8073e02793a62`.
- P03.S18 correction: `469d72bfd43bafcc77139219732109d8e403b909`.
- P03.S19: `39d08918c037cd08a297720009dbc950f8da7009`.
- P03.S20: `2bd39b9cdfeba77584a7c0a0426b268886bae24d`.
- P03.S21: `6cdab432941d985d32607bec47a26fef059a7b2e`.
- P03.S22 review: `427a98e02b7ee831f0abacf143f3cc18fce21c9c`.

P03.S18 required a HIGH correction after its first record omitted the
accepted live-filing mandate. P03.S22's initial commit also changed P02.S09,
and its closure landed in a later plan-only commit. These process defects are
disclosed rather than hidden; the corrected records and audit are the
current adjudication authority.
