---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a4997c0b080d68aa56dd56a4b18ac6df9ca04dd07e12b9fa00bb066a8d4d8df1'
step_id: 'S47'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Tighten the two LLM-usage verbs by help text: `app diagnostics llm-usage` and `app ledger llm-diagnostics` read different stores but claimed the same question over the same window

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `python -m dev.locales scaffold --check` -> `ok in all four catalogues`
- `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py test_parity.py` -> `42 passed`
- `verify:` `pytest test_documented_command_conformance.py -m integration` -> `349 passed`

## Notes

Found by walking the unsignalled-subject residue the placement gate declines to
judge: 45 of 65 subjects carry no policy signal in either direction, and the
diagnostics families sit in that set.

The two verbs are NOT duplicates and were not merged. `app diagnostics
llm-usage` reads `local-storage` through `build_llm_usage_report` and measures
every application LLM run by provider and model; `app ledger llm-diagnostics`
reads `encrypted-facts` through `build_llm_diagnostics_report` and measures
ledger extraction cost and classification confidence. Different populations,
different stores.

What was wrong is that both help strings opened with "Report ... LLM usage ...",
both take `--since` and `--until`, and neither named the other -- so an operator
asking what the LLM has been doing had two answers and no way to choose. This is
the same shape as the registry-health pair, and it takes the same remedy S37
established: each verb states what it uniquely covers and names its sibling. The
split itself is principled and stays.

A third family, `config auth diagnostics`, was examined and left alone: it
answers why an AEAT login failed, which is not the same question.
