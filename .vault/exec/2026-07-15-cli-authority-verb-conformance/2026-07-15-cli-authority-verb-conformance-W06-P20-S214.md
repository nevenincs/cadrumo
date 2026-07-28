---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S214'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S214 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Confirm no removed CLI spelling survives in source, locales, tests, docs, schemas, MCP, or suggestions and ## Scope

- `.` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm no removed CLI spelling survives in source, locales, tests, docs, schemas, MCP, or suggestions

## Scope

- `.`

## Description

- Confirm the shipped surfaces carry no removed CLI spelling by running the enforcement gates at HEAD: the removed-grammar invariants (which unmount `config lock/unlock/rekey`, `show-recovery`, `verify-recovery`, `config profile sandbox use`, `config profile use`, `modelo audit replay`, flat `config reset --scope`, `ledger link --evidence-id`, and scan source, four locale catalogues, docs, and sequence contracts for the retired custody and reset/sandbox spellings), the self-referential CLI-string gate, the suggestion-command gate, and the removed-schema-key gate.
- Sweep the surfaces the gates do not cover by several shapes, excluding legitimate homonyms: bare-word `config lock/unlock/switch/rekey`, `sandbox use`, `modelo audit replay`, the retired file-input flags `--from-sede/--from-justificante/--from-capture/--from-file`, and the retired AEAT-read verbs `capture`/`refresh`, across production source, docs, locales, MCP, and suggestions.
- Verify by measurement that `config switch` is absent from the live tree (exit 2) and `config login` is the live selector (exit 0); the `switch`/`capture` occurrences in source are the domain concept (active-profile switch notices, `justificante capture`, `live capture`), not the removed verbs.
- Fix the one genuine survival the sweep found: three stale docstring/comment references presenting a removed `switch` verb as "the single accepted selector" — two test docstrings and one production comment — corrected to name `config login`, the real selector the same tests already invoke.

## Outcome

Verified at HEAD `6868f4f824e1e037753f98089499b3bbcaf527a3` (gates re-run there; earlier sweep at `279bd29bfc`).

Live tree materialises to 290 leaf paths with zero duplicates (measured independently by the coordinator; the naive `.commands` recursion returns one leaf and must be walked through the lazy materialiser with click's `list_commands`/`get_command`). The walk carries paths, not parameters, so option sets were read from live `--help`, not inferred from the walk.

Enforcement gates: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py` — `33 passed in 15.19s`; grammar invariants re-run after the docstring fix — `17 passed in 7.89s`; the removed-schema-key gate rides the full `test_json_schema_conformance.py` — `161 passed`.

Sweep corpus and classification. Production source (non-test), docs (`.md`), and the four locale catalogues carry zero removed-verb citations. Every `config lock/unlock/switch/rekey`, `sandbox use`, and `modelo audit replay` hit in the tree is in a rejection-probe test that deliberately carries the retired spelling to prove the CLI refuses it (the enforcement, not a citation) — `test_root_grammar_invariants`, `test_config_profile_sandbox`, `test_audit_verbs`, `test_profile_lifecycle_verbs`, `test_json_schema_conformance`. No `--from-*` file-input flag exists anywhere. `capture` survives only as the domain nouns `justificante capture` / `live capture`; the removed fetch verb is `pull` (locale `app_help`: "pull a filed receipt"). `switch` survives only as the profile-change concept (`config login` drives it), plus the three stale references now fixed.

## Notes

The method point that matters: a removed spelling does not always appear in the form searched for. `config switch` and `config lock` return nothing as command strings, but the concept survives as bare words with legitimate homonyms (file locks, acquisition locks, `.lock` files; active-profile "switch" notices). Every empty result was confirmed by re-running through the dedicated file-search tool and by measuring the live tree, not trusted as absence. The three fixed references were docstring/comment prose, not shipped operator or agent-harness strings, and the tests they annotate already invoke `config login`, so no behaviour changed. Five closed Steps in this plan still name a `switch` verb in their row text; that is stale plan prose, not a shipped surface, and is left to the plan-hygiene follow-up rather than rewritten here.
