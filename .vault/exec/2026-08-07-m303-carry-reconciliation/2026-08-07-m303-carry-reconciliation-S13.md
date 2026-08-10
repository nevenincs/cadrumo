---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:194dacc7fc3a56ee65cec48641f41f614dc6592a0e415081795b3553bf1f3e4f'
step_id: 'S13'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# Recover the filed disposition from the printed declaracion render ONLY for a filing where no submitted_file artefact exists, and establish first whether that population is non-empty, because if the pull stores a submitted file for every filed modelo 303 this row has no subject and should be closed rather than built. Blocked on S12. Where the fichero is held the disposition is a direct read of the tipo de declaracion byte and no render parsing is warranted. IF the render path is taken, RECOVERY KEYS ON WHICH SLOT CARRIES A VALUE, NEVER ON A PRINTED LETTER. The C, I and D letters beside those sections are pre-printed form furniture present on all four bundled AEAT facsimiles including the two that elected ingreso, so a pattern matching the letter reports the same disposition for every filing while appearing to read the form. The pair needing separation is COMPENSACION versus DEVOLUCION, since the sign of casilla 71 already separates NEGATIVA from both through derive_result_disposition. Counts to state precisely rather than repeat: ResultDisposition declares TEN members, of which AEAT's modelo 303 diseño admits EIGHT, and the two the enum adds belong to other modelos. Unproven on evidence and not to be asserted otherwise: no bundled facsimile elected devolucion and none filed sin actividad, so box 73 and the sin-actividad flag have proven slots and unexercised values

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/`

## Description

- Trace the live Sede capture branches for submitted-file and declaration-PDF artefacts.
- Inspect the persisted `FiledDeclaracionObservation` model and its encrypted production reader.
- Run the read-only profile-status and storage-inventory commands without attempting login or credential access.
- Inspect the plan and relevant repository history to distinguish a production measurement from fixture-only evidence.
- After separately authorized profile unlock, enumerate the real encrypted observation store and emit only aggregate Modelo 303 artefact-kind counts.

## Outcome

The first read-only attempt was blocked because the profile was not unlocked.
After separately authorized profile unlock, the production reader
`FiledDeclaracionObservationStore.list_observations()` ran under its active
master-key provider. It returned zero Modelo 303 observations. Consequently,
the target count is zero: no observed Modelo 303 declaration has a
declaration-PDF artefact without a submitted-file artefact, because the current
active-profile corpus contains no Modelo 303 observations at all.

No declaration-render parser was added. This establishes the current
active-profile corpus measurement only, not a universal claim about all AEAT
filings. The independent review replayed the aggregate, approved the explicit
zero-target closure condition, and confirmed that no parser is warranted.

## Verification

`uvx --from vaultspec-rag vaultspec-rag search "filed M303 declaration submitted file artefact declaration render capture storage only:prod" --type code --max-results 8`

The production capture reads the submitted-file branch only when the live row
exposes its archive link and independently reads the declaration-PDF branch
only when the copy link is present.

`uv run --no-sync aeat config profile status --json`

`Refused. You are not logged in. Run aeat config login to unlock your profile.`

`uv run --no-sync aeat config storage list`

The safe inventory reports populated bucket database and keystore categories,
with the active-profile bucket redacted, but cannot enumerate decrypted filed
observation artefacts.

`uv run --no-sync python -`

The read-only aggregate over `FiledDeclaracionObservationStore.list_observations()`
reported `total_m303=0`, `m303_with_submitted_file=0`,
`m303_with_declaration_pdf=0`, and
`m303_declaration_pdf_without_submitted_file=0`. It inspected only `modelo` and
artefact `kind`, and emitted no identifiers, artefact bodies, values, paths, or
storage references.

## Notes

The original access blocker is resolved by the separately authorized profile
unlock. The measured zero target is caused by an empty Modelo 303 slice, so it
does not establish submitted-file coverage for any non-empty M303 corpus.
