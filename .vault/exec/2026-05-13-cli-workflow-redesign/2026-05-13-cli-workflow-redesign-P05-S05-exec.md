---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P05.S05'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P05.S05`

Flipped the shouty `REFUSED:` / `ERROR:` / … prefix on the human-
rendered stderr text to sentence-case `Refused.` / `Error.` / etc.
The structured JSON envelope, exit codes, and the
`ErrorCategory` enum values stay uppercase (grep-stable
programmatic identifiers). The transformation lives at the CLI
boundary so the core `render_error_text` helper still emits the
grep-stable prefix consumed by the contract test in
`src/aeat/entrypoints/cli/test_error_registry_contract.py`.

Implementation: introduced
`_SENTENCE_CASE_TEXT_PREFIX: dict[ErrorCategory, str]` and
`_rewrite_text_prefix_to_sentence_case` in
`src/aeat/entrypoints/cli/_errors.py`, applied in
`_emit_error_and_exit` before `write_stderr` when the active
callback has not opted into JSON output.

CliRunner integration tests that asserted the literal `"REFUSED"`
substring in captured output were retargeted to the new
`"Refused."` literal:

- `src/aeat/entrypoints/cli/test_error_boundary_integration.py`
- `src/aeat/entrypoints/cli/test_registry_cli.py`

The grep-stable prefix assertion in
`test_error_registry_contract.py::test_rendered_prefixes_are_grep_stable`
is intentionally unchanged because it exercises `render_error_text`
directly (not the boundary) and that helper still produces the
uppercase form.

- Modified: `src/aeat/entrypoints/cli/_errors.py`
- Modified: `src/aeat/entrypoints/cli/test_error_boundary_integration.py`
- Modified: `src/aeat/entrypoints/cli/test_registry_cli.py`

## Tests

Smoke-test of the rewriter:

```text
>>> _rewrite_text_prefix_to_sentence_case("REFUSED: The thing failed.\n", ErrorCategory.REFUSED)
'Refused. The thing failed.\n'
>>> _rewrite_text_prefix_to_sentence_case("ERROR: oops\n", ErrorCategory.ERROR)
'Error. oops\n'
```

Full pytest run is currently blocked by an unrelated
`AmendmentOverrideCasillaError` registry-binding failure introduced
by a sibling change under `src/aeat/application/modelo/_actions.py`;
the boundary tests themselves cannot collect until that lands a
registry row.
