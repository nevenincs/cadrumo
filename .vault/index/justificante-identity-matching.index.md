---
generated: true
tags:
  - '#index'
  - '#justificante-identity-matching'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:597754b173a2721b7e0342a9b6e10725f6195cfd445905c969926ee061320ee8'
related:
  - '[[2026-08-07-justificante-identity-matching-adr]]'
  - '[[2026-08-07-justificante-identity-matching-plan]]'
  - '[[2026-08-07-justificante-identity-matching-reference]]'
---

# `justificante-identity-matching` feature index

Auto-generated index of all documents tagged with `#justificante-identity-matching`.

## Documents

### adr

- `2026-08-07-justificante-identity-matching-adr` - `justificante-identity-matching` adr: `Justificante presentation_id namespace correction` | (**status:** `accepted`)

### exec

- `2026-08-07-justificante-identity-matching-P01-S01` - Add a csv-equality check recovering the CSV from the justificante_pdf artefact source_url via extract_csv_from_url, fold a resolution failure into the existing swallowed-outcome shape, and drop the now-signature-invalid expediente_id argument in the same change
- `2026-08-07-justificante-identity-matching-P01-S02` - Drop the now-signature-invalid expediente_id argument now that register_capture_justificante_metadata's existing csv equality check already covers identity
- `2026-08-07-justificante-identity-matching-P01-S03` - Drop the now-signature-invalid expediente_id argument now that register_capture_as_filing_evidence's existing csv equality check already covers identity
- `2026-08-07-justificante-identity-matching-P01-S04` - Remove the presentation_id parameter entirely from matches_filing_target and its three now-dead pass-through wrapper parameters
- `2026-08-07-justificante-identity-matching-P01-S05` - Update the pinning test to the corrected signature and matching behavior, and remove the fixture's false expediente-as-presentation_id equivalence
- `2026-08-07-justificante-identity-matching-P01-S06` - Add a real-fixture regression proving the register-reconciliation path enrolls a committed M303 justificante via the new csv-equality check
- `2026-08-07-justificante-identity-matching-P01-S07` - Run the domain and application justificante test suites and confirm green
- `2026-08-07-justificante-identity-matching-P01-S11` - Confirm extract_csv_from_url already resolves through the sede package public facade before landing S01, promoting it only if a fresh HEAD read shows it missing
- `2026-08-07-justificante-identity-matching-P01-S12` - Add a mutation-proof test proving the new csv defense-in-depth check discriminates two same-period filings sharing modelo, ejercicio, period and tax_id, confirming a wrong-artefact-selection bug would be caught even though the row-scoped fetch is the primary binding
- `2026-08-07-justificante-identity-matching-P01-S13` - Harden the row-scoped locator to an exact expediente_id match instead of a substring filter, reusing the existing re import rather than a second selection idiom, with a test proving it cannot match a second row whose id merely contains the target as a substring
- `2026-08-07-justificante-identity-matching-P02-S08` - Distinguish all five swallowed outcomes (unreadable artefact, manifest mismatch, unparsable PDF, CSV-resolution failure, CSV mismatch) and return a typed reason instead of returning None uniformly
- `2026-08-07-justificante-identity-matching-P02-S09` - Emit a Notice through the shared envelope spine naming the unreached-evidence reason when an enrollment call finds an artefact but saves nothing
- `2026-08-07-justificante-identity-matching-P02-S10` - Add a mutation-proof test confirming the reason-distinguishing branch fires per swallowed case and confirm the CLI report surfaces the Notice
- `2026-08-07-justificante-identity-matching-P02-S14` - Narrow the application-layer relay test's name and docstring to what its assertions actually prove. It constructs the advisories onto the run model and reads them back off the same object, so it is a pydantic storage roundtrip that cannot fail when the CLI forwarding is deleted, while its name and docstring both claim to cover the relay. The fold itself is now covered at the transport boundary, so this is a truthfulness repair rather than a coverage gap. Gate: the renamed test still derives its expected set from the enum, and a reader can tell from the name alone that it proves the taxonomy has members and the model stores one advisory per member, not that anything reaches an operator

### plan

- `2026-08-07-justificante-identity-matching-plan` - `justificante-identity-matching` plan

### reference

- `2026-08-07-justificante-identity-matching-reference` - `justificante-identity-matching` reference: `Justificante identity matching: presentation_id namespace`
