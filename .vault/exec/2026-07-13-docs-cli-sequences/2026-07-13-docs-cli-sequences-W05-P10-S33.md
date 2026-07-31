---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:02a191ef68c5705d32de540e879e398d535a42db4964e7ffa4b1affd0061053d'
step_id: 'S33'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Author the synthetic input fixtures and shared seed recipes for the first tutorials

## Scope

- `docs/_sequences/fixtures`

## Description

- Author the synthetic bank-statement fixture `docs/_sequences/fixtures/movimientos-2026-1t.csv`: a semicolon-delimited BBVA-shape statement with two invented first-quarter 2026 movements, one collected invoice (1210,00) and one office-supplies purchase (-605,00). All data synthetic.
- Author the shared seed recipe `docs/_sequences/seeds/autonomo-irpf-2026.seq`: three `@setup` frames that enrich the sandbox profile with a 2026-01-01 activity-start date and add two classified `BUSINESS` ledger rows (1000 base + 210 IVA income; 500 base + 105 IVA `material_oficina` expense).
- Ground both against the live engine with a throwaway probe before committing: the seed makes a fresh-sandbox Modelo 130 first-quarter verify grant, and a double run yields zero pre-mask differing paths.

## Outcome

Both synthetic inputs land and drive deterministic, granting runs. The seed's profile-edit approach was chosen after empirically proving that creating a fresh profile mints a random id that flaps every content-addressed identifier across runs (unusable for committed goldens); editing the pre-provisioned sandbox profile in place preserves the injected deterministic id while adding the activity-start date that scopes out the first-quarter cross-period dependency so verify grants.

## Notes

- The seed edits the profile by the engine's `SANDBOX_PROFILE_LABEL` (`docs-sequence-sandbox`); this is the only stable handle for the pre-provisioned active profile and is the deliberate cost of keeping the run deterministic. It renders inside the collapsed "Preparation" disclosure. The literal is defined as `SANDBOX_PROFILE_LABEL` in `dev/docs/sequences/_runner.py`; if that constant is renamed, the seed's edit target must move with it.
- Close-review polish (W05.P10): a discoverability comment pointing at that constant could NOT be added to the `.seq` file — the seed grammar (`parse_frame_lines` in `dev/docs/sequences/_parser.py`) refuses any non-frame line, so a leading `#` line is an "unrecognised line" parse fault that would red the check gate. The coupling note is recorded here instead. A `#`-comment grammar extension for seed recipes is a reasonable small ergonomics follow-up (a register item for the engine, out of W05 content scope) if the coupling proves a recurring readability snag.
- The fixture is consumed by the page's import sequence via `ledger import ... --provider csv`; import output carries no transaction ids, so import-then-classify by id was rejected as brittle in favour of an inline-classified seed for the filing sequence.
