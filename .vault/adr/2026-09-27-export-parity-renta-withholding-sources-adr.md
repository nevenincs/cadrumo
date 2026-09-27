---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:6e3ee192e4673a5d2487f48d70865265b3358825c9fc684c5ab8211696a84ad7'
related:
  - "[[2026-06-19-m100-dependent-modelo-applicability-adr]]"
  - "[[2026-09-27-export-parity-renta-withholding-sources-research]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-06-10-modelo-130-100-continuity-adr]]"
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]"
  - "[[2026-06-05-cross-period-filing-clean-state-adr]]"
  - "[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]"
  - "[[2026-06-01-calculation-test-oracle-discipline-adr]]"
  - "[[2026-06-12-live-pull-verification-sweep-adr]]"
---
# `export-parity` adr: `source Modelo 100 withholding credits from the perceptor side` | (**status:** `proposed`)

## Problem Statement

Modelo 100 subtracts the withholding, ingresos a cuenta and pagos fraccionados that the taxpayer bore (casillas 0592 to 0606, totalled in 0609) from the cuota. The live registry fills the two largest credit casillas from the declarant's own payer-side returns. Casilla 0596 sums the declarant's Modelo 111 in every revision, with the declarant's Modelo 190 added as an equivalent source in 2025. Casilla 0597 sums the declarant's Modelo 123, with the declarant's Modelo 193 added in 2024. Casilla 0599 is left unbound although the ledger already derives the professional withholding suffered on issued invoices and reports it as an unrouted quantity (`2026-09-27-export-parity-renta-withholding-sources-research`).

For a taxpayer who is an employee, an autonomo and a withholding agent in the same year, the product either credits tax withheld from other people or refuses the calculation as a conflict between equivalent bindings. In both cases it never reaches the correct figure. The accepted C3 decision (`2026-06-19-m100-dependent-modelo-applicability-adr`) deferred this as its Option 2. Its Update 3 kept the payer-side relations as the value source and only classified them `taxpayer_files_source = false`. This record decides the durable sourcing.

## Considerations

- In law, the credit belongs to the perceptor and is evidenced by the payer's certificate. Withholding the declarant practised is someone else's credit (LIRPF arts. 79.e, 99, 105; RIRPF arts. 76, 108.3; research, "Law" finding).
- The Renta designs from 2022 to 2025 number and describe these casillas identically, so the correction is one baseline change with no yearly divergence for 0596 to 0606 (research, "casillas" finding).
- AEAT's borrador and datos fiscales hold the payer-reported amounts, but in law they are informative, and the taxpayer stays responsible (research, "What AEAT prefills").
- The ledger can supply 0599 alone. Issued-invoice withholding is a typed quantity with derivation markers, and Modelo 130 casilla 06 already consumes it. Nothing in the ledger can supply 0596, 0597 or 0598 (research, "ledger" finding).
- There is no datos fiscales pull. The borrador PDF import stores `casilla.<id>` keys that the `--borrador` tier refuses. A higher-precedence value silently replaces a lower one (research, "Live pull" finding). That contradicts `no-silent-under-declaration` for filing-bound fields.
- The same conflation affects 1577 from the entity's Modelo 184 in 2025, and 0604 has unproven semantics for negative or complementaria Modelo 130 results. Both are adjacent but separately grounded (research, "Not investigated").

## Considered options

- Keep the payer-side relations and rely on operator overrides (the C3 Update 3 posture). Rejected. The override conflicts with the equivalent relation value and is refused, and when no override is given the payer's totals flow into the credit.
- Option A, per-casilla manual inputs only: remove the payer-side bindings and bind each credit casilla to `manual_input`. Kept as the fallback. It is minimal and correct in direction, but it has no per-payer evidence, cannot reconcile against a certificate or datos fiscales, and leaves the ledger's 0599 figure advisory.
- Option B, a typed suffered-withholding evidence family plus a ledger fold for 0599. An encrypted per-payer record ("retencion soportada") by income class feeds the credit casillas through one resolver. Casilla 0599 binds directly to the ledger's `withheld_amount_sum`. Certificates, borrador and datos fiscales enter as typed cross-checks with visible divergence. Chosen, subject to the operator decisions listed under Implementation.
- Option C, AEAT prefill as primary: import datos fiscales and fill the credits from them. Rejected as primary. The prefill is informative, no import exists, and a payer's omission would become a silent under-claim or over-claim. It is retained as a cross-check source.

## Constraints

- On acceptance this record supersedes `2026-06-19-m100-dependent-modelo-applicability-adr`. It realises that record's deferred Option 2 and reverses the Update 3 treatment of 111, 123, 190 and 193 as scoped-out dependencies that still supply values. What stays valid is carried forward here: 130 and 131 remain filing-grade dependencies conditional on economic activity, the gate reads registry classification and never the obligation schedule, and the first-filer self-carry remains a separate concern. The supersession is applied with `vaultspec-core vault adr supersede` only after this record is accepted.
- It proposes an amendment to `2026-06-10-calculation-aggregation-taxonomy-adr`. The precedence ladder (profile, backend mesh, borrador, caller) stays, but a higher tier replacing a different lower-tier value on a filing-bound binding must emit a structured divergence finding instead of overwriting silently. The amendment is presented separately for approval. The accepted text is unchanged until then.
- `2026-06-10-modelo-130-100-continuity-adr` stays as accepted: 0604 folds the declarant's own filed 130 and 131 through the relation channel.
- `2026-06-26-binding-source-kind-taxonomy-unification-adr`: any new provider kind is a member of the one canonical `BindingSourceKind`, with its validator in the dispatch table and its resolver at its own defining module.
- `2026-09-21-retenciones-workflow-observation-payment-contract-adr`: the payer-side withholding stores remain the source of 111, 115, 180, 190 and 193 only, and must not feed any Modelo 100 credit casilla.
- `2026-06-05-cross-period-filing-clean-state-adr`: removing the payer-side dependencies must not relax enforcement for dependencies the taxpayer does file.
- `2026-06-01-calculation-test-oracle-discipline-adr`: every numeric assertion uses an independent, hand-derived or official oracle.
- `2026-06-12-live-pull-verification-sweep-adr` and the project's live-write guard: any datos fiscales fetch is read-only and separately authorised. Local file import is the default ingestion path.
- Registry work follows the authority flow (source edit, candidate validation, publication, runtime adoption, each reported separately) and the delta-keyed standard (baseline plus genuine divergences). Taxpayer certificates and datos fiscales are private financial evidence and use the encrypted persistence boundary only.

## Implementation

Each Step is independently verifiable. Its tests run against the real compiler, resolver and calculation paths.

1. Remove payer-side sources from the credit casillas at the 2020 baseline, with removals inherited forward. Delete `renta-modelo-111-retenciones-periodicas`, `renta-modelo-123-retenciones-periodicas`, `renta-dep-111` and `renta-dep-123`. Delete the 2024 `renta-modelo-193-retenciones-anuales` alternate and `renta-dep-193`, and the 2025 `renta-modelo-190-retenciones-anuales` alternate and `renta-dep-190`, together with their construct references. Replace the live fold-in test that asserts filed Modelo 111 quarters reach 0596 with a test proving that filed 111, 115, 123, 180, 190 and 193 observations leave every credit casilla unchanged. Add a detector-teeth registry gate that fails when any casilla in the credit set is reachable from a binding whose source modelo is a payer-side return, including through alternates or formulas. The gate is proven with an isolated defective fixture.
2. Introduce the typed suffered-withholding family, chosen as Option B. It has a closed income-class vocabulary: trabajo, capital mobiliario, arrendamiento de inmueble urbano, actividad economica, ganancia patrimonial or premio, and the attribution and imputation classes. The class maps to casillas by `semantic_role`. Each encrypted per-payer record carries payer NIF, income class, gross amount, withholding, ingreso a cuenta and repercutido, period, evidence fingerprint and origin (payer certificate, datos fiscales import, or operator declaration). The provider, validator and resolver sit at one defining module and one application resolver, enrolled in the source mesh. Ingestion extends the existing `app` hierarchy through the subject's `import --file` flow; command naming is settled in the plan. The existing manual certificate binding is folded into this family at the baseline and deleted. Tests cover encrypted round trip, refusal of an unknown class, the distinction between absent, zero and missing, multi-payer aggregation to the right casilla, and the mixed persona.
3. Bind 0599 to the ledger directly as a bound casilla, not through a redirect, in the 2024 revision (inherited by 2025). The binding is a `ledger_renta_income_aggregation` with fact `withheld_amount_sum` over the Modelo 100 observations. Rows with a `REFUSED_ABOVE_SUPPORTED_RATE` or `NO_SUBSTRATE` marker surface as unresolved, never as zero. Whether inferred rows are filing-grade or advisory is an operator decision. Revisions 2020 to 2023 stay on the evidence family until their ledger income binding is grounded. Tests: a positive case with 15 and 7 per cent invoices, exclusion of employment and non-activity rows, marker propagation, silence of the unrouted-quantity screen for Modelo 100, and consistency with the fourth-quarter Modelo 130 casilla 06 over the same ledger.
4. Add a typed cross-source reconciliation. The registry declares, for each credit casilla, its cross-check sources: certificate records, the imported borrador or datos fiscales value, and for 0599 the filed fourth-quarter 130 casilla 06. The resolver emits a structured finding with modelo, revision, casilla, source family, both values and reason, and that finding reaches verify and the CLI handoff. The precedence overlay reports tier divergence under the proposed taxonomy amendment. Tests: agreement produces no finding, disagreement produces a visible finding, suppression is narrowly keyed, and a teeth test proves detection.
5. Correct the borrador path. Move `aeat_prefilled` to the suffered-withholding bindings. Make the borrador PDF import and the `--borrador` tier share one key contract, projecting through the registry's bound-casilla-to-binding mapping rather than free `casilla.<id>` keys. Extend the `borrador_pdf` profile to the credit casillas only against a verified render. Add terminal-origin classes for payer certificate and AEAT third-party data, so provenance is audited rather than left as `None`. Tests cover import-to-calculate round trip, refusal of unknown keys, and recorded provenance. A datos fiscales file import is a later, separately authorised Step.
6. Ground 0604 against the Modelo 130 instructions for negative quarters and complementarias. If summing casilla 19 does not equal the payments made, replace the operation with a typed aggregation, using official-example tests.
7. Prove the personas end to end with independent oracles:
   - (a) an employee only;
   - (b) an employee who is also an autonomo, with 15 and 7 per cent invoices and quarterly Modelo 130;
   - (c) persona (b) also filing 111, 115, 180 and 190.

   Assert 0596 equals the certificates, 0599 the invoice withholding, 0604 the 130 payments, 0609 their sum, and that payer-side totals are absent from 0592 to 0606. Extend the income-tax acceptance journey to assert 0599.
8. Clean up. Remove the authored 0599 comment and correct the verification-predicate comments that say the value cannot arrive from AEAT. Record follow-ups for 1577 per-member attribution and for 0598 activity-rental withholding.

Operator decisions required before a plan executes:

- the filing-grade authority for 0599 (ledger with certificate cross-check, or certificate with ledger cross-check);
- whether inferred ledger withholding may be filing-grade;
- the disagreement policy (advisory, blocking until resolved, or refusal);
- whether and when to build a datos fiscales import;
- the temporal rule for invoices whose payment year differs from their accrual year, which needs DGT grounding first.

## Rationale

Option B is the only option that follows the legal evidence chain (payer certificate, payer informative return, perceptor credit), uses data Cadrumo already holds (the ledger's issued-invoice withholding), and keeps every disagreement visible, all through one typed binding family and one aggregation mechanism (`2026-09-27-export-parity-renta-withholding-sources-research`). Option A is safe but blind: it cannot reconcile or explain a figure. Option C makes an informative prefill authoritative. Keeping the relations fails on the product's own conflict rule. The designs do not diverge across years, so the change is a baseline correction with inherited removals, which the delta-keyed standard favours.

## Consequences

- Gains: a mixed employee, autonomo and payer reaches a correct Modelo 100. Withholding practised on others can no longer be credited. 0599 stops being a silent manual box. Borrador and datos fiscales become honest cross-checks.
- Costs: a new source kind, encrypted store, resolver, CLI import flow and reconciliation findings, and a registry rewrite across six revisions with publication and runtime adoption reported separately.
- Pitfalls: persisted calculation revisions that name deleted binding identities must stay replayable under their pinned authority generation, which needs a migration check. Until the operator settles the 0599 authority and the temporal rule, 0599 stays advisory. Operators who relied on overrides of the 111 binding must re-enter values through the new family.
- Opens: the same family can carry 0597, 0598, 0603 and the attribution classes as certificates arrive, and it gives a place to reconcile a future datos fiscales import.
