---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:e6d7ca7d79f4dd60638b68cf30c8e38d765cf10d6e564922e3422b97523a6842'
step_id: 'S466'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Call the click exceptions own renderer in the plain-text funnel, since it looked up an attribute named view that no click exception has so every parse refusal fell through to a bare message write and lost its prefix usage block hint and the parameter name, leaving the localised show reimplementation dead code in the text path

## Scope

- `src/cadrumo/entrypoints/cli/_terminal_errors.py`
- `src/cadrumo/entrypoints/cli/tests/test_localised_parser_errors.py`

## Changes

`test_invalid_language_value_is_refused_with_accepted_set` now passes. It was
the last failing gate in `dev/locales` outside the two blocked on decisions.

ONE WORD. `_render_click_exception_text` read
`getattr(exc, "view", None)` -- and no click exception has a `view`. The lookup
returned None on every refusal, so the funnel always fell through to its
fallback, `sys.stderr.write(str(exc))`. The function's own docstring says it
falls back to "plain `exc.show()`", so the intent was never in doubt.

What that cost is much larger than the missing prefix the gate named. The
refusal an operator actually saw was:

    'xx' is not one of 'es', 'en', 'ca', 'hu'.

with no statement of WHICH option had rejected the value. Passing several
options, there was nothing in the output to say which one was wrong. What the
renderer produces once it is reached:

    Usage: aeat [OPTIONS] COMMAND [ARGS]...

    Error: Invalid value for '--language' / '--lang': 'xx' is not one of 'es', 'en', 'ca', 'hu'.

Both option spellings, the usage line, and the localised `Error:` prefix.

AND IT MADE DEAD CODE OF A WHOLE SUBSYSTEM. `_framework_localisation` rebinds
`ClickException.show` and `UsageError.show` with from-scratch localised
reimplementations -- the `Error:` prefix, the usage block, the "Try ... for
help" hint, each routed through `tr`. In the plain-text path nothing ever
called them. The localisation was installed and unreachable.

The failure was silent by construction: `getattr` with a default returns None
rather than raising, and the fallback prints something that reads like a
plausible error. Nothing anywhere reported that the renderer had been skipped.

Teeth: restoring `"view"` -- the defect verbatim -- fails both the new funnel
gate and the target gate. Restored by copy. The new gate hands the funnel an
exception whose renderer records that it ran, because asserting on rendered
text would pass just as well against the fallback.

## Notes

VERIFIED PRE-EXISTING, NOT CAUSED BY THIS FIX. Five failures in
`test_json_error_contract.py` and one in
`test_parse_error_envelope_names_its_command.py`
(`config.profile` where `config.profile.preflight` is expected) fail
identically with the defect restored. Both were baselined that way rather than
assumed.

They are worth a later firing: the envelope one is adjacent to this fix, and
now that the text path reaches the real renderer, the JSON path's spine
documents are the obvious next thing to read.

TARGET STATE. Of the six named targets, (1) translation honesty, (3) language
override sites, (4) badge-key scanner visibility and (6) `remove-batch` are all
GREEN, and (5) `test_no_tui_module_names_the_create_action` lives at
`src/cadrumo/entrypoints/tui/modelo/tests/test_create_deferred.py` and passes.

Target (2) parity is the only one left, and it is BLOCKED on three operator
decisions, all evidenced from live authorities rather than from absence: the
125 `cli.*` extras the command-spec registry does not declare, the 5
`application.*` the error registry does not declare, and the
`tui.ledger.reconciliation.direction` spelling the shadow gate rejects.
