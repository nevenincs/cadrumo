---
tags:
  - '#reference'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]"
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI persona-task catalogue

The standing backlog for testimonial-driven CLI verification. Each
loop iteration dispatches a batch of these as human-persona agents
(method: the verification playbook). The catalogue is deliberately
broad: the goal is to exercise *actual Spanish tax activity*
end-to-end, so the activity profile is effectively open-ended -
extend this file as new activity shapes are identified.

Every task brief inherits the playbook's hard rules: CLI + `--help`
only, no source reading, isolated `AEAT_LOCAL_STORAGE_ROOT`, verbatim
command log, honest first-person testimonial with a graded bug list,
no live AEAT network calls.

Status legend: `[ ]` not yet run · `[x]` run, testimonial filed ·
`[~]` partially covered.

## D1 - Profile setup and entity shapes

- [x] P-D1-01 First-time autonoma sets up her profile (Lucia).
- [ ] P-D1-02 Sole professional (profesional, IAE pro section) sets up.
- [ ] P-D1-03 Company administrator sets up a sociedad limitada profile
  - does the tool model a company entity at all?
- [ ] P-D1-04 Landlord with only rental income sets up.
- [ ] P-D1-05 Multi-activity taxpayer (freelance + rental) sets up.
- [ ] P-D1-06 Married couple deciding joint vs separate declaration -
  can the profile express a spouse and joint election?
- [ ] P-D1-07 Pensioner with a small side activity sets up.
- [ ] P-D1-08 Non-resident with Spanish-source income - is this even
  in scope, and does the tool say so clearly?
- [x] P-D1-09 Multi-profile manager (Pablo) - switch/duplicate/rename.
- [ ] P-D1-10 Mid-year activity change (alta of a new IAE epigrafe).

## D2 - Layout of the land / responsibilities mapping

- [x] P-D2-01 Owner asks "what do I file and when?" (Sofia).
- [ ] P-D2-02 New autonomo asks "which modelos apply to me?" and
  expects a profile-filtered answer.
- [ ] P-D2-03 Taxpayer maps the full annual calendar - every period,
  every modelo, every deadline.
- [ ] P-D2-04 Taxpayer asks "what have I already done / what is left?"
  mid-quarter.
- [ ] P-D2-05 Taxpayer wants the legal basis for an obligation - does
  `explain` exist and ground it in BOE/AEAT?

## D3 - Transaction management

- [x] P-D3-01 Bookkeeper imports a quarter of transactions (Marco).
- [x] P-D3-09 Meticulous grooming: classify/allocate/attach (Nuria).
- [ ] P-D3-02 Import from each supported bank provider in turn -
  which providers actually work; what does an unknown one do?
- [ ] P-D3-03 Import a messy real-world statement (refunds, reversals,
  foreign currency, duplicates) and groom it.
- [ ] P-D3-04 Correct a mis-imported transaction (update/remove/reset).
- [ ] P-D3-05 Archive / stash transactions and bring them back.
- [ ] P-D3-06 Attach a supplier receipt as purchase-invoice evidence
  end to end (evidence-id creation included).
- [ ] P-D3-07 Reconcile the ledger against a bank balance.
- [ ] P-D3-08 Re-import an overlapping statement - does it dedupe?

## D4 - Categorization and ratios

- [ ] P-D4-01 Categorize a quarter of expenses into IRPF categories.
- [ ] P-D4-02 Categorize income/expense into IVA categories and rates.
- [ ] P-D4-03 Set a mixed-use asset's business percentage and see it
  flow into the modelo (car, home office, phone).
- [ ] P-D4-04 Build and apply a usage-ratio profile.
- [ ] P-D4-05 Apply IVA prorrata (arts. 101/103) to shared inputs.
- [ ] P-D4-06 A transaction the tool cannot categorize - what guidance?

## D5 - Modelo calculation (the engine)

- [x] P-D5-01 Self-employed prepares Modelo 130 (Diego).
- [x] P-D5-02 Company admin prepares Modelo 303 / 200 (Elena).
- [ ] P-D5-03 Modelo 131 (objective-estimation pago fraccionado).
- [ ] P-D5-04 Modelo 111 (retenciones e ingresos a cuenta - payroll).
- [ ] P-D5-05 Modelo 115 (retenciones on urban-property rentals).
- [ ] P-D5-06 Modelo 123 (retenciones on capital income).
- [ ] P-D5-07 Modelo 349 (intra-community operations recapitulative).
- [ ] P-D5-08 Modelo 347 (annual third-party operations).
- [ ] P-D5-09 Modelo 390 (annual IVA summary) reconciled with the 303s.
- [ ] P-D5-10 Modelo 180 / 190 (annual retention summaries).
- [ ] P-D5-11 Modelo 369 (OSS/IOSS one-stop-shop).
- [ ] P-D5-12 Modelo 720 (overseas asset declaration).

## D6 - Manual calculation verification

- [ ] P-D6-01 Taxpayer hand-computes Modelo 130 from AEAT's worked
  example and cross-checks every casilla against the engine.
- [ ] P-D6-02 Same for Modelo 303 against an AEAT workbook.
- [ ] P-D6-03 Taxpayer disputes a casilla value - can the CLI show the
  formula, inputs, and legal_refs that produced it?
- [ ] P-D6-04 Taxpayer checks a binding-sourced casilla traces back to
  the right ledger transactions.

## D7 - Adjustments, corrections, refiling

- [ ] P-D7-01 Taxpayer realises a filed Modelo 303 was wrong and files
  a complementaria.
- [ ] P-D7-02 Sustitutiva (replacement) declaration workflow.
- [ ] P-D7-03 Rectificativa / autoliquidacion rectificativa workflow.
- [ ] P-D7-04 Carry a prior-quarter negative result forward into the
  next 130/131.
- [ ] P-D7-05 Amend a draft after `verify` flagged a problem, then
  re-verify.
- [ ] P-D7-06 Refile a corrected modelo and confirm the prior filing
  is superseded, not lost.

## D8 - Renta (Modelo 100) completion workflow

- [ ] P-D8-01 Salaried taxpayer completes a basic Renta.
- [ ] P-D8-02 Autonomo folds quarterly 130s into the annual Renta.
- [ ] P-D8-03 Renta with rental income and deductible expenses.
- [ ] P-D8-04 Renta with capital gains/losses and integration rules.
- [ ] P-D8-05 Renta with CCAA-specific autonomic deductions.
- [ ] P-D8-06 Renta borrador import / reconciliation against AEAT data.
- [ ] P-D8-07 Joint vs separate Renta comparison.

## D9 - Special regimes

- [ ] P-D9-01 Estimacion objetiva (modulos) activity declaration.
- [ ] P-D9-02 Recargo de equivalencia retailer.
- [ ] P-D9-03 Agricultural regime (REAGP) activity.
- [ ] P-D9-04 Criterio de caja (cash-basis IVA) election and effect.
- [ ] P-D9-05 Reserva de Inversiones Canarias / Illes Balears.
- [ ] P-D9-06 Cooperative-taxation entity.
- [ ] P-D9-07 Entity in atribucion de rentas.

## D10 - Live surface interfacing

- [x] P-D10-01 Configure AEAT authentication (Raul).
- [ ] P-D10-02 Inspect filed declarations via `live filed list`.
- [ ] P-D10-03 `live filed capture` and capture-sources flow.
- [ ] P-D10-04 Apoderamiento / representation read-only checks.
- [ ] P-D10-05 Auth diagnostics: report observed Cl@ve app state.

## D11 - Output and filing handoff

- [x] P-D11-01 Export a modelo draft for external filing (Teresa).
- [ ] P-D11-02 Inspect the BOE fichero export byte-format for one
  modelo and judge whether it is AEAT-submittable.
- [ ] P-D11-03 Export the libros (IVA registers) in BOE format.
- [ ] P-D11-04 Produce the operator's filing checklist for a period.

## D12 - Lifecycle, recovery, hygiene

- [x] P-D12-01 Repair / diagnostics surfaces (Pablo).
- [x] P-D12-02 Adversarial error-probing (Ines).
- [ ] P-D12-03 Resume an interrupted `modelo work` run.
- [ ] P-D12-04 Recover from a corrupted / quarantined bucket.
- [ ] P-D12-05 Full year-round run: Q1 -> Q2 -> Q3 -> Q4 -> annual,
  one persona, continuity of carry-forward and prior filings.
- [ ] P-D12-06 Output-language: run the whole flow in English, then
  Spanish, and check locale consistency.

## Dispatch discipline

- Draw a batch (3-6) per loop iteration; vary domains so coverage
  broadens rather than deepening one corner.
- Re-run a `[x]` task after its area is fixed to confirm the fix from
  a user's seat (regression personas).
- Every new CLI-surface gap a persona finds is filed into the apex
  CLI ADR (`[[2026-05-12-cli-workflow-redesign-adr]]`) per its
  amendment convention, not fixed ad hoc.
- Extend this catalogue whenever a real tax-activity shape is not yet
  represented - it is meant to grow.
