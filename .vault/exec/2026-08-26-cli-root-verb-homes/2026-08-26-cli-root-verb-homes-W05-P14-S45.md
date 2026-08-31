---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:bcf8d03f51b9039c788bda5ae6c0a80b34423ca7d8392e8bdea2591362dd52ec'
step_id: 'S45'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rename `config google folder get` to `view`: a retired token on a locus-free read that the verb-grammar gate cannot see, sitting beside `credential-source view` in its own family

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_config/_google_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_folder.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_folder_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_config/tests/test_google_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_transport_verb_grammar.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `docs/_sequences/contracts/how-to/review-with-google-sheets/sheets-folder.seq`
- `M` `docs/_sequences/how-to/review-with-google-sheets/sheets-folder.json`
- `verify:` `python -c "...COMMAND_GRAPH..."` -> `294 leaves, 64 declarations, no leaf named get`
- `verify:` `pytest four campaign gates + test_google_command_specs.py` -> `25 passed`
- `verify:` `pytest test_documented_command_conformance.py -m integration` -> `349 passed`
- `verify:` `python -m dev.docs.sequences check --page how-to/review-with-google-sheets` -> `clean`
- `verify:` `python -m dev.locales scaffold --check` -> `missing=0`

## Notes

Found by reading the leaf-token census off the live graph, not by a gate. Within
one family, `credential-source` read with `view` while `folder` read with `get`
-- the same shape, two verbs, and `get` is on the contract's retired list.

The verb-grammar gate passed it correctly on its own terms: the gate only
refuses a retired token on a leaf that DECLARES a transport locus, and a
settings read declares none. That scoping is deliberate and still right, but it
leaves exactly this residue -- a retired token on a locus-free verb that is
nonetheless a synonym split. The gate's docstring now says so and names this
verb as the worked example, replacing the sentence that cited it as a
correct pass.

The rename also caught the recurring find-and-replace failure. Renaming the spec
key, help key, handler target and payload class all succeeded while the
positional token stayed `"get"`, because a bare `"get"` was not in the
replacement set. The graph still reported `config google folder get` afterwards.
Only a graph rebuild caught it; the string sweep looked complete.
