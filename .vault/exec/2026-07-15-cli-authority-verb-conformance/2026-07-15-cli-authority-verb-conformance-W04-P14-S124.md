---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:c31e3fabfe3f18b6da0f1e3b335be3342773c22aed145614aa4ae42a03dd3db8'
step_id: 'S124'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert the accepted root grammar exactly and reject every removed path and option

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

Assert the accepted root grammar exactly, and reject every removed path and option,
in one omnibus invariant gate.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py` is the W04
keystone gate. It holds the accepted surface positively — `config reset` mounts
exactly start/status/resume (`:209`), `config recovery` mounts exactly
status/create/rotate/verify and refuses `show`/`mint`/`print`/`export` (`:141`),
`modelo audit` registers only the canonical three (`:86`), and `modelo audit export`
stays distinct from `modelo export` (`:44`) — and rejects the removed surface:
retired custody spellings (`:111`), the flat `config reset --scope` (`:226`), the
`config profile sandbox use` door (`:243`), bare-name profile selection (`:256`),
`ledger link --evidence-id` (`:201`), mnemonic argv options on the recovery verbs
(`:124`), and the bare `reconcile` / `audit` / `run` root aliases (`:28`, `:60`,
`:69`).

Two of its cases are broader than command registration and matter for the
hard-cut sweep. `test_retired_custody_spellings_absent_from_source_and_docs` (`:161`)
and `test_retired_reset_and_sandbox_spellings_absent_from_source_and_docs` (`:273`)
walk `src/cadrumo/**/*.py`, the four locale catalogues, the operator docs tree, and
the `docs/_sequences/**/*.seq` contracts, failing on any occurrence of a retired
spelling. Because the scan covers the whole Python source tree, it reaches the
surfaces the documented-command and JSON-schema conformance gates do not — the
runtime write-policy allowlist, the error-registry `default_suggestion` fields, the
cross-period `next_action` builders, `operator_surface/_help.py`, and the envelope
`command=` identifiers.

That automated reach is bounded by two explicit constants:
`_RETIRED_CUSTODY_SPELLINGS` (`:153`) covers `config rekey`, `config show-recovery`,
`config verify-recovery`, and `--recovery-key`; `_RETIRED_RESET_SANDBOX_SPELLINGS`
(`:266`) covers `config profile sandbox use`, `config reset --scope`, and
`reset --scope`. Spellings outside those two tuples — `config lock`,
`config auth clear`, the certificate `--backend` selector, and `modelo audit replay`
— are covered by targeted registration and schema probes but by no tree-wide scan,
and were swept by hand for this Wave (see Notes).

The gate exempts itself and `test_config_recovery_lifecycle.py` from the scan
(`:186`), correctly: those modules carry retired spellings as rejection probes, so
they are the enforcement rather than a dead citation.

The module passed in the coordinator's W04 gate run
(`uv run --no-sync pytest <14 W04 files> -m "integration and not os_keychain"` →
`1 failed, 154 passed`), the single failure being the unrelated S112 control.

## Notes

Hand-sweep for the four spellings outside the automated tuples, across the five
surfaces the conformance gates do not scan, all clean at this HEAD:
`storage_write_policy.py` carries no retired verb and still guards `app ledger link`
(`:113`) and the `config reset` prefix (`:186`); the error registry's only matching
`default_suggestion` is `aeat config auth apoderado configure --scope ALL`
(`registry/_domain_part1.py:621`), a retained verb; `operator_surface/_help.py` has
no retired citation; and the only `replay` envelope identifier is the distinct
retained `registry.parity.replay`. `ResetScope` has no residual declaration anywhere
in `src/cadrumo` or `docs`.

A candidate for the automated tuples in a later pass: `config lock`,
`config auth clear`, and the certificate `--backend` selector could be added to a
retired-spelling scan cheaply. `--evidence-id` deliberately could not — the retained
`app ledger evidence` family uses that option legitimately, so a tree-wide scan would
false-positive; its registration probe at `:201` is the right instrument.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
