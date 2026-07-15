---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S17'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Author the per-field ownership adjudication table for AEAT-prefixed app-owned settings

## Scope

- `.vault/audit`

## Description

- Read ADR ruling R6 (env-var prefix adjudication) and research findings F1.2
  (env-var prefix split) and F6.2 (unresolved ownership seams) as the
  grounding authority.
- Enumerated every `aeat_*`-prefixed `Settings` field: 32 in `core/config.py`,
  5 in `core/_config_runtime_fields.py`, 10 in `core/_config_timeouts.py` (47
  total), plus the `AEAT_IVA_CATALOGUE_ROOT` seam in
  `core/resources/_repos/iva_catalogues.py` (confirmed a constructor
  parameter, no separate literal to rename there).
- Read every field's declaration and docstring; classified each by referent
  per the `cadrumo-product-authority-names` doctrine (ownership/referent
  decides the prefix, not spelling) into three buckets: authority referent
  (stays `AEAT_*`), app-owned control (migrates to `CADRUMO_*`), and
  identity-adjacent (`aeat_certificate_*` / `aeat_clave_*_dni/nie/password`,
  adjudicated per-field since R6 withholds a blanket verdict for this
  bucket).
- Measured blast radius with a targeted `rg` sweep across `src/cadrumo` and
  `docs` per field group (browser controls, proxy/rate policy, auth
  timeouts/provider, corpus roots and policy flags, identity-adjacent
  certificate and Cl@ve fields, authority-referent URLs/templates).
- Confirmed `docs/reference/environment-overrides.md` is a generated file
  (`python -m dev.docs.env_reference`), so no hand-sweep is needed there; found
  the one required manual sweep obligation -- `AEAT_CLAVE_MOVIL_DNI_NIE` is
  quoted verbatim in all four locale catalogues (16 occurrences) and must
  route through `python -m aeat.locales set` when S19 executes the rename.
  Confirmed zero hits in `core/errors/registry/` and `_data/agent/` for any
  candidate env-var literal.
- Authored the audit document
  `.vault/audit/2026-07-13-data-output-standardization-env-var-ownership-audit.md`
  (the CLI's `vault add audit` scaffolds one audit per feature/date and has no
  `--topic` flag for the documented multi-audit narrative-infix convention;
  authored the file by hand to the exact template frontmatter/section shape
  since a second audit already exists for this feature's S04 step).
- Verdict summary: 10 of 47 fields KEEP `AEAT_*` (7 authority URLs/templates
  including the certificate verify URL, 2 verbatim bundled-corpus roots,
  1 domain-terminology language directive); 37 migrate to `CADRUMO_*` (all 11
  browser-automation fields, all 5 proxy/rate-policy fields, all 11
  auth-timeout/provider/Cl@ve-flag fields, 2 corpus-loading policy flags,
  `aeat_iva_catalogue_root`, 4 of 5 identity-adjacent certificate fields, and
  all 5 identity-adjacent Cl@ve DNI/NIE/password fields).

## Outcome

Audit document authored and committed. Ran `vaultspec-core vault check all`
to confirm the new document's frontmatter/tags/links are structurally clean
(no findings against the new file). No production code, tests, or docs were
touched by this Step -- it is a research/adjudication document only. This
Step gates S18 (execute the renames) and S19 (docs/locales/error-registry/
harness sweep), which the team lead holds pending the W01 executor's active
edits to `core/config.py` landing first. Committed at `f621c4362d` (audit),
plan-step check and this exec record follow in a second commit.

## Notes

No incidents. The recommendations section flags one open verification item
for S18's executor: re-confirm against the existing
`_LEGACY_PRODUCT_DOTENV_NAMES` rationale that none of the 37 migrating fields
were ever product-state-selecting before assuming zero new dotenv-exclusion
entries are needed (this audit's reading is that none of the 37 are storage/
identity-selecting state, only runtime policy/location knobs, but the
executor closest to the rename commit should re-verify against the live
exclusion set at that time).
