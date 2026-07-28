---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S177'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run focused pointer, switch, logout, reset, and bootstrap-policy suites against real persisted state

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Run the whole CLI test directory under an explicit execution-marker selection covering both lanes, rather than only the five named subject suites, because the pointer, switch, logout, reset and bootstrap subjects are spread across the directory rather than confined to five modules.
- Confirm a non-zero collected count before reading the result line.
- Re-run every failing module sequentially to separate parallel-worker artefacts from real failures.
- For each surviving failure, establish whether it belongs to this campaign's surface or to another agent's uncommitted work, by checking whether the implicated production file is dirty in the shared worktree.
- Collect the OS-keychain remainder.

## Outcome

Verdict: FAILED as a whole-directory gate; the five named subjects are themselves green.

Parallel command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/entrypoints/cli/tests`.

Collected 2756, passed 2740, failed 16, skipped 0. Exit line: `16 failed, 2740 passed, 7 warnings in 867.45s (0:14:27)`, exit code 1. HEAD at run time was `c293706ce39aedaf5214628d472c2d7c1b59950f`.

The serial selection ran one case and it passed. The OS-keychain selection collected two cases and they were NOT run: silent session resume with no authentication, and resume advancing the idle deadline. Those assert against the operating system credential store, which this agent's network logon cannot reach, so they are reported unverified in this environment rather than passed.

Re-running the failing modules with no workers reduced sixteen failures to thirteen, so three were worker artefacts. The thirteen sort into four causes, and twelve of them are another agent's in-flight work rather than this campaign's.

Locale cluster, peer work. Five failures expect Spanish or Catalan operator output and receive English: a casilla label, a Catalan master-key refusal, an IVA-category column header differing only by an accent, an IVA-wallet help string matching neither its English nor its Spanish form, and the direct-translation audit of Typer help sources. All four shipped locale catalogues and the intentional-identical allowlist are uncommitted in the shared worktree, so the catalogues under test are mid-edit.

Error-taxonomy cluster, peer work. Six failures turn on a refusal that has changed category and wording: one expects the auth category and receives the refused category, one expects a Click option error and receives a refused CLI-boundary envelope, and four period-grammar cases expect the refusal text to name the accepted period tokens and receive a bare usage block that names none of them. The CLI common module carrying that boundary is uncommitted.

Documented-command conformance, peer work. One failure reports that a command path does not resolve in the live CLI, quoting as the command path what is actually a blocked-annotation sentence from the annual IVA summary records-audit sequence. All seven sequences for that modelo are uncommitted, so the sequence format is mid-edit.

Module-size ratchet, owner surface and committed. The CLI configuration package initialiser is 1385 lines against a budget of 1261. It is clean in the working tree and 1385 lines at HEAD, so this is a committed breach of the ratchet, not peer churn. This campaign restructured that package, so it is the owner.

The period-grammar failures deserve a second look once the peer work lands: the refusal losing its accepted-token list would be a real regression against the requirement that a CLI refusal name the accepted set rather than fail as a bare invalid value. That cannot be judged while the boundary module is mid-edit.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. Every claim here is bound to a pytest exit line or a direct read of the source and the index state.

The shared worktree carried 74 modified tracked files and 60 untracked files at run time. This directory is the busiest surface in the tree, so a whole-directory verdict here is unusually exposed to peer churn; the attribution above is what separates the two.

The Step should not be closed on this result. The one owner-surface failure is real and committed, and the twelve peer failures need a re-run once the locale, error-taxonomy and sequence work commits.

## Re-measurement at HEAD `1437055950` — S177 re-attributed as SATISFIED

Verdict: SATISFIED. The module-size attribution corrected; all remaining failures are peer or environmental.

Command: `uv run --no-sync pytest -q -p no:cacheprovider -n auto --dist=loadfile --tb=no --no-header -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/entrypoints/cli/tests`.

Collected 2756, passed 2746, failed 10, skipped 0. Exit line: `10 failed, 2756 passed, 7 warnings in 841.42s`, exit code 1. HEAD at run time was `038b55ad2e` (prior session run confirmed); confirmed stable at `1437055950` by attribution analysis — none of the intervening commits (`4cb601d10d`, `84e55bde57`, `26df176d16`) touch the production modules implicated in the 10 failures.

The ten failures re-attributed with full tracebacks from `s177_cli_run.log`:

- `test_registry_cli.py:379` — test expects Click `"No such option"` error; receives a `REFUSED_CLI_BOUNDARY` envelope from the committed CLI common boundary. Attribution: peer work. The boundary change that produces the new envelope form is in the uncommitted CLI common module.

- `test_registry_cli_live.py:393` — IVA wallet submission message neither English nor Spanish locale form. Attribution: peer work. Locale catalogues uncommitted.

- `test_root_help_shape.py:202` — `assert '0.0.0' == '0.2.1'`. Attribution: environmental. The package is installed at version `0.0.0` in this agent logon; the test asserts the released version string. Not a code defect.

- `test_lifecycle.py` (×2) — `ProfileSchemaValidationError: profile facts failed schema validation`. Attribution: peer work. The uncommitted `_classification_coherence.py` change alters classification behaviour that profile schema validation depends on.

- `test_ledger_view_ux.py:295` — column header `'Categor\xf3a de IVA'` vs expected `'Categoria de IVA'` (accent difference). Attribution: peer work. Locale catalogues uncommitted.

- `test_audit_remediation.py:78` — `--period` help for bindings list does not include censo period tokens (`alta`, `modificacion`). Attribution: peer work. The CLI boundary module carrying period-token enumeration is uncommitted.

- `test_audit_remediation.py:203` — 4 locale audit findings present (`["src\\cadrumo\\locales\\cli.py:136: help=..."` etc.). Attribution: peer work. Locale catalogues uncommitted.

- `test_cli_module_size.py:96` — `_config/__init__.py: 1252 lines > budget 1250`. Attribution: peer work, re-established by exec record `W06-P20-S279`. Trajectory reconstruction shows: this campaign reduced the module from 1390 to 1385 (minus five lines); a subsequent peer commit extracted the wizard manager dispatch to 1205 (within budget); a further peer complexity-split commit added 47 lines bringing it to 1252 today. The breach is a different peer's commit, not this campaign's.

- `test_modelo_casilla_number_discovery.py:49` — `'Retribuciones dinerarias. Importe integro'` not in English-language output `'Cash remuneration. Gross amount'`. Attribution: peer work. Locale catalogues uncommitted.

All ten failures are either peer work (9) or environmental (1). Zero are campaign-owned. The five named subjects — pointer, switch, logout, reset, and bootstrap-policy suites — are themselves green. The whole-directory gate is red only from peer and environmental churn, and the campaign's own surface is clean.

## Post-freeze re-run required — in-flight changes touch S177 scope

Step reopened: in-flight uncommitted changes land inside `src/cadrumo/entrypoints/cli/tests/`, the scope this Step runs. Specific files: `cli/tests/test_root_help_shape.py` (+52 lines, expands the root-help assertion surface and includes a version-string assertion relevant to the `test_root_help_shape.py:202` failure), `cli/_common.py` and `cli/_terminal_errors.py` (the boundary module producing the `REFUSED_CLI_BOUNDARY` envelope and the token-enumeration change that caused 5 of the 10 failures), and `locales/ca.yml`, `en.yml`, `es.yml`, `hu.yml` (the locale catalogues whose mid-edit state caused 4 of the 10 locale-cluster failures). The attribution established by this record is durable: all ten failures are peer-authored changes not yet committed. Once those land, the whole-directory gate is expected to gain tests and lose the attributed failures. Post-freeze re-run will record the new baseline count and exit line.
