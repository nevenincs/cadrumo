---
tags:
  - '#plan'
  - '#settings-di'
date: '2026-05-14'
tier: L2
related:
  - "[[2026-05-14-settings-di-adr]]"
  - "[[2026-05-14-settings-di-research]]"
---

# `settings-di` plan

Lands the ContextVar-backed Settings override seam authorised by the
`settings-di` ADR, expands `Settings` with three Category-B fields,
migrates every Category-A and Category-B call site to read from
`get_settings()`, and converts the Category-E CLI flag write into an
override block. Test-suite mechanical migration of 223
`monkeypatch.setenv` sites is deferred to a follow-up sprint.

## Proposed Changes

Foundation first: extend `aeat.core.config` with the three new
`Settings` fields and the `override_settings` context manager.
Migrations follow per call-site, one focused commit each, with the
fail-closed branch verified by an explicit test on every Category-B
field. The CLI flag write migrates last so the upstream consumer is
already on `Settings`.

## Steps

### Phase `P01` - foundation: extend Settings and add override helper

Lands the new fields and the override context manager. No call sites
migrate yet; every existing test must continue to pass against the
unchanged `os.environ.get(...)` reads.

- [ ] `P01.S01` - add `aeat_log_dir`, `aeat_libreoffice_executable`, and `aeat_master_key_passphrase` to the Settings model; `src/aeat/core/config.py`.
- [ ] `P01.S02` - add `_settings_override` ContextVar and the `override_settings` context manager; `src/aeat/core/config.py`.
- [ ] `P01.S03` - extend `get_settings` to honour the ContextVar before falling back to the cached env-derived singleton; `src/aeat/core/config.py`.
- [ ] `P01.S04` - add focused unit tests for the override helper covering scalar override, nested override, restoration on exit, restoration on exception, and Pydantic-validation rejection of malformed override; `src/aeat/core/test_config_override.py`.

### Phase `P02` - migrate Category A call sites

Replace already-modelled env reads with `get_settings()` field reads.
No new Settings fields needed; per-site test verifies the override
helper is observed.

- [ ] `P02.S05` - migrate `AEAT_OUTPUT_LANGUAGE` read to `get_settings().aeat_output_language`; `src/aeat/core/i18n/_render.py`.
- [ ] `P02.S06` - migrate live-tests opt-in read at line 103 to `get_settings().aeat_live_tests_enabled`; `src/aeat/core/access_gate/__init__.py`.
- [ ] `P02.S07` - migrate diagnostic snapshot read at line 128 to `get_settings().aeat_live_tests_enabled`; `src/aeat/core/access_gate/__init__.py`.
- [ ] `P02.S08` - add focused tests proving each migrated site observes the override; `src/aeat/core/i18n/test_render_override.py` and `src/aeat/core/access_gate/test_override.py`.

### Phase `P03` - migrate Category B call sites with fail-closed verification

Each site swaps the env read for the new Settings field. Every commit
includes a test that asserts the fail-closed branch still raises on
`None`.

- [ ] `P03.S09` - migrate `AEAT_LOG_DIR` read to `get_settings().aeat_log_dir`; `src/aeat/core/logging.py`.
- [ ] `P03.S10` - migrate `_LIBREOFFICE_EXECUTABLE_ENV` reads (two sites) to `get_settings().aeat_libreoffice_executable`; `src/aeat/domain/calculations/registry/_workbook_parity.py`.
- [ ] `P03.S11` - migrate `PASSPHRASE_ENV_VAR` read to `get_settings().aeat_master_key_passphrase`; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `P03.S12` - add focused test that override of `aeat_master_key_passphrase` to `None` raises the same `MasterKeyError` as the current unset-env path; `src/aeat/adapters/persistence/storage/master_key/test_master_key_failclosed.py`.

### Phase `P04` - migrate Category E CLI flag write

Replace the `os.environ` write at the CLI root with an
`override_settings` block scoped to the command invocation. Requires
P02.S05 to have landed.

- [ ] `P04.S13` - wrap the command invocation in `override_settings(aeat_output_language=language)` and delete the env write; `src/aeat/entrypoints/cli/__init__.py`.
- [ ] `P04.S14` - add focused test proving the CLI flag value reaches the i18n renderer without any env-var manipulation in the test; `src/aeat/entrypoints/cli/test_language_flag_override.py`.

### Phase `P05` - audit and reviewer sign-off

Final pass before declaring the sprint complete.

- [ ] `P05.S15` - run `prek run --all-files` and confirm green (or only pre-existing other-agent WIP failures, documented inline); shell.
- [ ] `P05.S16` - run `pytest src/aeat/ -q` and confirm green; shell.
- [ ] `P05.S17` - run the `vaultspec-code-reviewer` agent against this branch and write the audit record; `.vault/audit/2026-05-14-settings-di-code-review-audit.md`.
- [ ] `P05.S18` - update task #77, #83, #84, #85, #88, #103 to reflect the unblock status that follows from this sprint; tasks.

## Parallelization

Phases are sequenced — P02 depends on P01 (the override helper must
exist before any migration uses it), P03 depends on P01, P04 depends
on P02.S05 (the i18n renderer must already read from Settings before
the CLI flag write can stop writing the env). Within a single Phase,
Steps may be batched into one commit when they share a single file;
otherwise one commit per Step.

## Verification

The plan is complete when:

1. Every Step is closed (`- [x]`).
2. `pytest src/aeat/ -q` is green.
3. `prek run --all-files` is green (or remaining failures are
   pre-existing other-agent WIP, documented per commit in the exec
   records).
4. Each Category-B migration's fail-closed test passes — overriding
   the field to `None` raises the same typed error as the current
   unset-env path.
5. The reviewer audit record concludes "no regressions on the
   live-write perimeter and no new mocks/fakes/stubs/skips".
6. The five downstream tasks (#83, #84, #85, #88, #103) carry an
   explicit unblock note in their description.
