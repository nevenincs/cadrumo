---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:56189aaac30ce246addd52ddd916575b15ab2c52719e8c363af2907fc5463426'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-W05-P10-S89]]"
---
# `cli-action-envelope-hardening` audit: `S89 installed public-console action-envelope proof`

## Scope

Independent proof-only audit of the installed public `config provision pull` and `config provision verify` commands for `W05.P10.S89`. The audit used a pristine `HEAD` wheel with both required data companions, a fresh virtual environment, an empty working directory, and one isolated storage/database root per command, output format, and locale. It did not change product source, tests, plans, ledgers, execution records, profiles, sessions, or the shared checkout state.

## Findings

### s89-installed-public-console-proof | low | PASS: the public refusal preserves one canonical closed projection

All 16 rows passed: pull and verify, JSON and text, in `en`, `es`, `ca`, and `hu`, with the configured context requirement set to `1000000`. Each public command exited with code `2` before any model acquisition or readiness interaction, emitted `provisioning.selected_model.available`, and carried exactly one runtime observation whose values exactly equalled the result facts: `deployment_posture`, `eligible_candidate_count`, `required_context_tokens`, `role`, and `runtime`.

In every row the action was null and the no-recovery outcome was `operator_decision`; no locale-specific prose was parsed or used as authority. JSON rows additionally passed the installed command's registered schema JSON-validation path and round-tripped to the emitted result. Text rows reconstructed the action only from the machine field cells and matched the JSON result exactly for the corresponding command. No row surfaced `BadParameter`.

The isolated state had no active profile or session. The JSON envelope carried a null active-profile field in all eight JSON rows, establishing that these public provisioning refusals reach the selection boundary without borrowing the user's profile or session state.

## Recommendations

- Keep S89 open: this audit is an independent observation of the current public installed surface, not a closure decision.
- When the generated W06 action matrix is available, retain this context-unsatisfiable selection scenario as an installed-console row for both verbs and all supported output locales.
