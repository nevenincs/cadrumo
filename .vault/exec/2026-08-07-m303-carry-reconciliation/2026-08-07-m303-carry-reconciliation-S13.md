---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:02fba40de2135579bef547553a8f3847586a8c8b2f2c70815e50d278e1099a73'
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

## Outcome

The required population was not measurable in this environment. The production
reader is `FiledDeclaracionObservationStore.list_observations()`, which decrypts
active-profile records; the shell has no unlocked active profile. The CLI
refused the read-only status probe with `reason: absent`. Storage inventory
shows a bucket database and keystore exist, but it does not expose decrypted
observation artefact kinds.

No declaration-render parser was added. The data model permits an observation
to hold a declaration PDF without a submitted file, but the capture branches
do not establish that such a Modelo 303 population exists. S13 remains open.

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

## Notes

The external blocker is authorization to unlock the existing local profile
bucket. This record does not request a login, passphrase, or credential access;
without that authorization the count of Modelo 303 observations with a
declaration PDF and no submitted file is unknown rather than zero.
