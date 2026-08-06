---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-14'
body_hash: 'sha256:072f56509974a36bb459ae9e0748bbdb2b6270898458ceb057f32d03554d86fc'
step_id: 'S19'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Sweep docs, locales, error-registry suggestions, and the agent harness for every renamed variable

## Scope

- `renamed env-var prose surfaces`

## Description

- Checked for peer WIP in the four locale-catalogue files (clean) and in
  `docs/how-to/modelo-130.md` (an unrelated peer content edit; confirmed
  it references none of the 39 renamed fields, so no entanglement risk).
- Repo-wide grepped for all 39 old `AEAT_*` env-var literal names across
  `docs`, `src/cadrumo/locales`, `src/cadrumo/core/errors`, and
  `src/cadrumo/_data/agent`. Confirmed the S17 audit's finding held:
  zero hits in hand-written docs, error-registry `default_suggestion`
  fields, `next_action` builders, curated operator help, and the agent
  harness. The only hits were the 4 `AEAT_CLAVE_MOVIL_DNI_NIE` citations
  in each of the 4 locale catalogues (16 leaves total), plus a large set
  of stale hits confined to the gitignored, untracked
  `docs/_build/html/` Sphinx build output (regenerated on the next real
  build, not a source surface).
- Resolved the 4 dotted locale keys for the 16 leaves by loading each
  catalogue with the real YAML parser (`adapters.auth.clave_movil.errors.
  dni_nie_not_set`, `application.auth.operator.alignment.
  both_missing_detail`, `application.auth.operator.alignment.
  clave_identity_missing_detail`, `application.auth.sessions.errors.
  clave_identity_missing`), substituted only the `AEAT_CLAVE_MOVIL_DNI_NIE`
  token inside each existing translated string (preserving the
  surrounding Catalan/Spanish/Hungarian/English prose verbatim), and
  routed all 16 writes through `python -m cadrumo.locales set LOCALE KEY
  VALUE` -- never hand-edited the `.yml` files.
- A stale local-machine artefact (a real leftover `aeat.db` file on this
  dev machine's storage root, unrelated to this campaign) makes any bare
  `python -m cadrumo.locales ...` invocation in this shell trigger a
  legitimate `FormerProductStateError` refusal during eager `Settings()`
  construction. Worked around it non-destructively for these CLI
  invocations only by pointing `CADRUMO_LOCAL_STORAGE_ROOT` at a scratch
  directory for the duration of the command (never touching the real
  `aeat.db` or the machine's actual storage root).
- Ran the locale `scaffold --check` gate (clean on all four catalogues),
  the parity and translation-honesty test suites, the agent
  rule-surface conformance gate (`-m integration`, since it carries the
  `pytest.mark.integration` marker and is excluded from the default
  `-m unit` addopts), and the `application/auth` suite (the consumer of
  these exact locale keys).
- Ran a final repo-wide `rg`-equivalent sweep for all 39 old `AEAT_*`
  names across the ENTIRE tree (excluding `.git`, `.vault`, `__pycache__`,
  `_build`, `.venv`, `node_modules`): zero hits. Confirmed `.vault/`
  itself still carries 57 historical hits across pre-existing exec/
  audit/research/plan records that predate this rename -- correctly left
  untouched, since those documents record what was true when written.

## Outcome

Landed in one commit (`42a0aeae9f`, the four locale catalogue files).
Gates: locale `scaffold --check` clean; parity + translation-honesty
suites green (32 tests); agent rule-surface conformance gate green
(6 tests, `-m integration`); `application/auth` suite green (112 tests);
full-tree `pytest --collect-only -q` clean (12886 collected); zero live
`AEAT_*` hits repo-wide outside `.vault` history. The env-var rename
campaign (S17 to S19) is now structurally complete: every field is
renamed, every code consumer swept, every generated doc regenerated,
and the one confirmed user-facing prose citation routed through the
locales CLI.

## Review follow-up (wave-3)

The wave-3 review returned REVISION REQUIRED on this Phase: one MEDIUM
plus two LOW findings, closed in commit `71edd51918`.

- **MEDIUM** -- `src/cadrumo/application/preflight.py:198`
  (`_auth_error_remediation`, the `certificate` / `"unreadable"` branch)
  still cited the dead `AEAT_CERTIFICATE_PASSWORD` literal. This name was
  never one of the 39 fields the S17 table adjudicated -- it does not
  match any live Settings field (the real field is
  `cadrumo_certificate_password_secret`, env var
  `CADRUMO_CERTIFICATE_PASSWORD_SECRET`) -- so the S18/S19 field-literal
  sweeps correctly reported zero hits against their own worklist while
  missing this pre-existing, differently-spelled stale citation. Fixed
  by routing the hint to the live CLI verb
  (`` `aeat config auth certificate secret set` ``, confirmed against the
  live Typer tree: `auth_app` -> `certificate_app` -> `secret_app` ->
  `set`) rather than naming any env var, matching the sibling hints on
  the surrounding lines. Confirmed `preflight.py` carries no `tr()`
  calls, so no locale-key routing applied here. Re-ran the full
  `test_preflight.py` suite across all three modules (36 tests, green)
  and a final repo-wide `AEAT_CERTIFICATE_PASSWORD` sweep: remaining
  hits are exclusively pre-existing `.vault/` historical records (18
  files, left untouched per the same historical-record rationale as the
  main sweep), the two benign wizard-widget echo-string tests the
  reviewer already identified
  (`application/wizard/tests/test_questionary_smoke.py`,
  `application/wizard/tests/test_widgets.py` -- arbitrary password-input
  fixture strings, unrelated to the real field name), and
  `.agents/testimonials/authenticate-with-aeat.md`, a dated
  (2026-06-18) persona-testimonial record of what a past session found
  wrong in the docs at that time -- judged out of scope on the same
  historical-record basis as `.vault/`, since rewriting it would
  falsify what that session actually observed.
- **LOW 1** -- the S17 audit doc's
  `authority-referent-urls-and-templates` finding heading said "9 fields
  stay AEAT_" while its own body enumerated exactly 7 (the 10-KEEP total
  across all findings was correct). Fixed the heading to say "7 fields".
- **LOW 2** -- ran
  `vaultspec-core vault check annotations --feature
  data-output-standardization --fix`; reported clean (no scaffold
  annotation residue found in the S22 audit doc or any other feature
  document at the time this ran).

Commit `71edd51918` (`preflight.py` + the S17 audit doc heading fix; the
LOW-2 annotation check made no file changes).

## Notes

No incidents in this Step. Two points worth recording for future
reference:

1. The local-machine `aeat.db` refusal is a real, correct safety
   feature (`FormerProductStateError`) firing against a genuine leftover
   file on this dev machine, not a bug -- it is orthogonal to this
   campaign and was worked around only for the duration of the locales
   CLI invocations via a scratch storage-root override, never by
   touching the real file.
2. This Step's blast radius was much narrower than S18's, since the
   S17 audit had already correctly identified (and S18 re-confirmed)
   that error-registry, agent-harness, and hand-written docs carry zero
   citations of any renamed variable -- the only genuine prose-surface
   work was the 16 locale leaves.
