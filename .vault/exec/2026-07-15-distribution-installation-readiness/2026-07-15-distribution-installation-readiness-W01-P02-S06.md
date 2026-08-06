---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:41a95be610a0c53e182a70aa830bd24232a43abf0db3502e4ffe4809034b6b70'
step_id: 'S06'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Execute the public CLI tax itinerary against isolated encrypted storage and assert the grounded Modelo 200 result

## Scope

- `dev/packaging/installed_tax_oracle.py`

## Description

- Drive profile creation, Modelo 200 work creation, calculation, and observation reload
  exclusively through the public installed `aeat` executable.
- Isolate product configuration and encrypted storage from inherited host state.
- Assert the externally grounded value, formula, legal and source provenance, persisted
  revision, active profile, and exact warning contract.
- Emit command transcripts and resolved executable identity as machine-readable evidence.

## Outcome

The probe installed a newly built root wheel with both real companion wheels and the
agent runtime into a fresh virtual environment. Its absolute `aeat` executable created
real encrypted state and calculated `DP200014:00562 == 23000.00` with formula
`modelo-200-cuota-integra`, persisted the revision, reloaded the public observations,
and retained the required legal and AEAT manual references.

## Notes

The first live run proved that `CADRUMO_DATABASE_URL` must not be forced before profile
creation because the product derives a profile-bound database route. The final probe
sets only the isolated storage root and secret passphrase. A second live run identified
the expected informational profile next-step notice; the gate now rejects warning
notices on setup commands while allowing non-fatal informational guidance.

The final clean artifact run completed successfully in 117 seconds including virtual
environment creation and dependency installation. Ruff, Ty, and bytecode compilation
passed.
