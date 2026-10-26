---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:554d55434366baf9c7cfdee1c55d0a00f079809979972b9041a4decde9b4d032'
related:
  - "[[2026-09-26-export-parity-audit]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
---

# `export-parity` adr: `development mock software identity for envelope exports` | (**status:** `accepted`)

## Problem Statement

Every layout whose envelope prefix reserves a program identifier and a developer NIF refuses export, because the product holds no AEAT software-developer registration and no entrypoint can supply a product software identity (`2026-09-26-export-parity-audit`). Modelo 303 is the first casualty: a verified-complete quarter produces no file on either surface, so no IVA periodic export can be exercised or reviewed. The operator stated on 2026-09-26 that the registration will not be obtained at this stage and directed the product to use a visibly mock development value instead.

## Considerations

- The accepted fragment-generator decision makes the program identifier and developer NIF one typed product authority that is never a presenter, taxpayer, default or guessed literal (`2026-08-10-aeat-export-fragment-generator-authority-adr`).
- The accepted destinations decision requires an export to say on the artefact and in the result what it could not establish (`2026-09-07-tuimodelo-export-destinations-adr`).
- The identity is a property of the installed product, not of one command; four entrypoints (CLI export, TUI operation, quickfile, review package) share one export-port composition root.
- The developer NIF is validated as a Spanish tax identifier; an all-zero DNI with check letter T is valid and cannot belong to a person.

## Considered options

- **Keep refusing.** Rejected by the operator: no IVA periodic export could exist until a certification that is not planned.
- **Operator-configured identity.** Deferred: it needs a real registration to be meaningful and adds a configuration surface nobody can populate yet.
- **One canonical all-zero development identity, supplied at the composition root and graded on every result.** Chosen.

## Constraints

- The mock must be impossible to present as a registration: its values and its evidence reference appear together and whole, and its grade is derived from the values rather than declared.
- No surface may present a mock-stamped file as presentable at AEAT.
- The taxpayer and presenter identities remain excluded from the developer header.

## Implementation

`src/cadrumo/domain/filing/software_identity.py` defines program identifier `0000`, developer NIF `00000000T`, an evidence reference naming the identity as not AEAT-certified, a derived `AeatSoftwareIdentityGrade`, and `development_mock_software_identity()`. `ModeloExportPorts` carries the identity and `build_modelo_export_ports` supplies the mock, so every entrypoint uses one value. The export service passes it only to layouts rendering an envelope prefix; the per-command field and the identity-unavailable refusal are deleted. `ModeloExportResult.software_identity_grade` reports the grade and the CLI adds the `modelo.export.development_software_identity` warning. A future registration replaces the value at the composition root.

## Rationale

The composition root is the only place a per-installation fact belongs, and it keeps CLI and TUI byte-identical by construction. Deriving the grade from the values closes the one way a mock could be relabelled. The warning and result grade satisfy the destinations decision's honesty requirement without blocking review of the file.

## Consequences

- Modelo 303, 390 and every other envelope-prefixed layout can export locally for review; AEAT will reject such a file if it is presented.
- The generator decision's refusal until explicit authority exists is satisfied by an explicit, graded mock rather than by refusal.
- Documentation and docs sequences state the mock and its consequence instead of a refusal.
- Replacing the mock with a registered identity later changes one composition-root call and the graded result.
