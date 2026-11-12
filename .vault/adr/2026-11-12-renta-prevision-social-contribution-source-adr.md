---
tags:
  - '#adr'
  - '#renta-prevision-social-contribution-source'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:2c1f17b8ec1b42701a16023426b4f5b2cc70de10c8922f271c0821616850d105'
related:
  - "[[2026-11-11-renta-savings-income-source-adr]]"
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - '[[2026-11-12-renta-prevision-social-contribution-source-research]]'
---

# `renta-prevision-social-contribution-source` adr: `Source the Modelo 100 pension-plan contribution boxes from contribution certificate records` | (**status:** `accepted`)

Proposed 2026-11-12 by CALCULATORS for slice S40 (b), on CADRUMO-PRIME's split of 15:03. Accepted 2026-11-12 15:14 by CADRUMO-PRIME under the operator's delegation, with four conditions written into Constraints (ruling: the 15:14 entry of PRIME's ADR acceptance log). Grounding: lane note `.tmp/2026-11-12-calculators-s40/pension-limits-grounding.md` (Manual práctico Renta capítulo 13 for 2020 to 2025, LIRPF arts. 51 to 53 and DA 16), and the Modelo 345 record design `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_345/files/01-345-ejercicio-2025.pdf.extracted.md:318-720`.

## Problem Statement

Modelo 100 has no source for the contributions behind the reduction for social-welfare systems. The contribution boxes (in the 2022 to 2025 editions 0465, 0426, 0427, 0438, 0499 and 0466; the earlier editions' equivalents are declared at `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:3187-3236` with edition overrides) carry no binding: the operator types them or leaves them out, and 0467 and 0468 compute from whatever is typed. A typed figure carries no evidence and no contribution kind, so the limit formula of S40 (a) cannot tell a worker's own contribution from an employer's or an autónomo's, which is exactly what its limits turn on.

## Considerations

- The taxpayer's evidence is the certificate the plan manager, mutualidad or insurer issues. It mirrors what that entity declares on Modelo 345, keyed by the official clave (A to L) and subclave (`01-345-ejercicio-2025.pdf.extracted.md:318-720`). The clave and subclave decide the contribution kind; the box follows from the kind and the edition.
- The suffered-withholding payer record (`src/cadrumo/domain/renta/retencion_soportada.py:104`) already has the shape this needs: one record per issuer, ejercicio and class, an evidence fingerprint, a correction chain, registered operations and encrypted custody.
- Employer contributions imputed to the worker are also work income in kind (casilla 0008, `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:1626`), stated by the employer's withholding certificate. The two figures come from different issuers and can disagree.
- Ledger rows show what the taxpayer paid but not the clave, the plan or any employer contribution, so they cannot source the boxes alone.
- Coordinator ruling 2026-11-12 09:00: an uncomputed deduction is disclosed and never blocks unless a stored fact shows it applies.
- Project rules: registry data per edition, declared once and delta keyed; no year in Python; private payloads only in encrypted custody.

## Considered options

- (a) A contribution certificate record per issuer, plan and ejercicio, keyed by the Modelo 345 clave and subclave, mapped to boxes by registry data. Chosen.
- (b) Ledger rows linked to a plan position, as the savings slice does. Rejected as the source: no clave, no employer contribution, no dependency-insurance split. A later cross-check stays possible.
- (c) Keep the boxes operator-typed and fix only the limit formula. Rejected: the limits depend on the contribution kind, which a typed total does not carry.
- (d) A profile fact per plan with yearly amounts. Rejected: contributions are per-ejercicio evidence, not standing profile facts, and a profile fact carries no certificate.

## Constraints

- The record stores the issuer NIF and name, the plan NIF and name (casilla 0397 where the edition has it), the ejercicio, the official clave and subclave, the amount, the beneficiary role, the certificate fingerprint and the correction chain. It computes nothing.
- The clave/subclave to box mapping is registry data per edition, declared once at the earliest edition where the design holds, with deltas only where the official design changed. No box id or year appears in Python.
- Condition of acceptance 3: the clave/subclave mapping is authored from each edition's official design and the manual's casilla list, declared once at the earliest edition where it holds. A clave or subclave the design does not place is refused at record time with served words, never mapped by analogy and never filed under another box.
- Condition of acceptance 4: the oracles are the manual's worked examples for each rule period, wired as tests through the real resolver.
- Clave map ruling of CADRUMO-PRIME 2026-11-12 15:27 (rulings log), on the evidence that no official text maps a Modelo 345 clave to a Modelo 100 casilla, so a row is admitted only where the 345 subclave wording and the Modelo 100 dictionary or manual capítulo 13 box wording name the same instrument and payer:
  - Every admitted row cites both texts by locator. Filing grade holds only for years whose own texts are cited.
  - Clave J subclave 01 goes to one box or another depending on whether the employer contributed to the same plan; that split is a stated and cited fact on the record, and a record that does not state it is refused.
  - Refused rows (clave B without subclave, H, K and M, which match only indirectly; C.04, D, E.02, I and L.03, which no text places), and every clave for the 2020 and 2021 ejercicios, whose Modelo 345 designs are not bundled, carry served words and the door to enter the box as an operator value, and block under condition 1 until the value is entered or stated.
  - Bundling the official 2020 and 2021 Modelo 345 designs is a later CALCULATORS item. Those years are never mapped from later designs.
- Spouse contributions (art. 51.7) and contributions to a disabled person's system (art. 53) are refused at record time in this slice, with served words saying why. Their boxes stay operator inputs until a later slice.
- Condition of acceptance 1: with no certificate recorded for an ejercicio, the reduction is disclosed as a limitation and does not block (ruling 09:00), unless a stored fact shows that a contribution exists for that ejercicio: an employer contribution imputed on the work-income record, a ledger row classified as a social-welfare contribution, or a typed contribution box. Then a blocking not-computed finding reaches the user with the record door.
- Condition of acceptance 2: a typed contribution box beside certificate records for the same box is an aggregation conflict, resolved only through the existing override door with provenance. A record never silently overrides an operator entry, nor the reverse.
- When a clave B or C record (employer contribution imputed to the worker) and the employer's work-income certificate disagree on the imputed amount, a structured finding reaches the user. Neither figure overrides the other.
- Custody: one registered secure namespace, schema v1, encrypted; certificate bytes only through the existing evidence custody; nothing private in logs.

## Implementation

We will add a pension contribution record and a source resolver that fills the Modelo 100 contribution boxes from it through a registry mapping, and register record, correct and remove operations for the CLI, TUI and window.

- Domain: the record and its admission (clave, subclave, beneficiary role, amount not negative, ejercicio inside the support envelope).
- Registry: a mapping family keyed by clave and subclave per edition, hydrated and validated at registry build, and a binding source kind for the contribution boxes in the edition that first declares them, inherited after.
- Application: a resolver enrolled in the canonical resolver stages beside the capital mobiliario position source (`src/cadrumo/application/modelo/calculation_route.py:134`, `src/cadrumo/application/modelo/calculation_source_mesh_actions.py:640`, `src/cadrumo/application/aggregation/ledger_membership.py:250`), summing records per box with provenance per record.
- Operations: record, correct and remove, revision guarded, with served words, and the frontend record-group read (`user-profile.record-groups`) extended to the new group.
- Evidence: real stores and resolvers for every Modelo 100 year the envelope admits; a worked example from the manual for each rule period (2020, 2021, 2022, 2023 onward); a refused clave; the disagreement finding.
- Hypotheses that may change: the exact box for each clave and edition, read from each edition's official design and the manual's casilla list when the mapping is authored; whether the record keys by plan as well as by issuer.

## Rationale

Only the certificate carries the contribution kind that the art. 52 limits depend on, and keying it by the official Modelo 345 clave keeps the classification in the official vocabulary rather than a Cadrumo one. Mapping clave to box in the registry keeps edition differences as data. Reusing the payer-record shape keeps custody, correction and evidence rules that are already reviewed.

## Consequences

- An employee, an autónomo or a saver with a pension plan gets the contribution boxes from evidence, and the S40 (a) limits apply to the right kinds.
- A new secure namespace, operations and served words; the operation contract manifest and the window wire types are regenerated.
- Spouse and disability contributions remain operator inputs until their own slice.
- The art. 52.2 excess carry is decided separately (`prior-carry-attestation`, topic `prevision-social-excesses`).
- Reconsider if AEAT changes the Modelo 345 claves, or if the window imports certificates directly.
