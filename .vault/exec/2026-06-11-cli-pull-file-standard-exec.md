---
tags:
  - '#exec'
  - '#cli-pull-file-standard'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S14'
related:
  - "[[2026-06-10-cli-pull-file-standard-plan]]"
  - "[[2026-06-10-cli-pull-file-standard-adr]]"
---

# cli pull file standard execution

## Description

Consolidated execution record for all fourteen Steps (S01-S14) of the
cli-pull-file-standard plan, landed across three commits.

- P01.S01-S03 (commit `579d6961b`): convert the reconcile surface into a Typer
  subgroup with `pull` (fetch from AEAT sede), `file --file PATH` (local
  artefact), and `history`; remove the four `--from-sede` / `--from-capture` /
  `--from-justificante` / `--from-declaration` flags and the
  reconcile-from-justificante sugar verb; move the reconcile help/error locale
  keys to the new group across all four catalogues; rewrite the reconcile CLI
  tests to drive `reconcile pull` and `reconcile file --file`.
- P02.S04-S09 (commit `1c85f0b43`): rename every live AEAT-fetch verb to the
  `pull` family - justificante `capture` to `pull`; expedientes `capture` /
  `capture-all` to `pull` / `pull-all`; notifications `capture` to `pull`; filed
  `capture` / `capture-all` / `capture-sources` to `pull` / `pull-all` /
  `pull-sources`; iva-wallet `capture-history` / `capture-remote-state` to
  `pull-history` / `pull-remote-state`. Move the live `capture*` help locale key
  family to the pull names across en/es/ca/hu via the `aeat.locales` CLI. Update
  the live verb tests and the live-read-subgroups test.
- P03.S10-S11 (commit `1c85f0b43`): rename `config profile censo refresh` to
  `pull`; rename `ledger import --source` to `--file` (keeping the internal
  `LedgerSourceImportCommand.source` keyword). Locale keys and tests updated.
- P04.S12-S14 (commits `1c85f0b43`, `d2fa3885f`): update the how-to guides to
  the renamed verbs and flags; regenerate the CLI reference and hold the
  documented-command conformance + reference-drift gates green; codify the
  `aeat-cli-pull-and-file-standard` project rule and sync it to all four provider
  rule directories.

## Outcome

Standardization complete: across every CLI interface, `pull` is the sole verb
that fetches from AEAT and `--file` is the sole single-file-input flag. The
`--from-*` flag family and the bespoke `capture` / `refresh` / `--source` names
are gone. All rename-specific surface tests pass (reconcile group, censo pull,
live `pull` family, iva-wallet `pull-history` / `pull-remote-state`, reconcile
`pull` / `file` natural-key help). Locale gates green: `aeat.locales scaffold
--check` clean for all four catalogues; `test_parity.py` and
`test_locale_translation_honesty.py` pass (21). Documentation gates green:
`test_cli_reference_drift.py` and `test_documented_command_conformance.py` pass
(43). The new rule is registered in `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`. All
fourteen plan Steps are closed.

## Notes

- The renamed live verbs preserve their read-only safety envelope unchanged
  (`require_live_read`, `AEAT_LIVE_TESTS_ENABLED`, the iva-wallet no-submit
  policy). A verb rename touched only names and help text, never a safety gate.
- Shared-worktree contention: during verification the working tree was bricked
  by two concurrent peer refactors mid-flight - a `StorageRouteKind` /
  storage-route classification move that dropped two noqa-guarded public
  re-exports from `core/config.py`, and a registry semantic-role module split
  that relocated `_validate_required_role_declarations` without repointing a
  stale importer. Both crashed every CLI import and all test collection
  worktree-wide. Three minimal, restorative (toward-HEAD) heals were applied to
  un-brick collection: re-add the two re-exports to `core/config.py`, and
  repoint the clean `_validate_registry_scope.py` importer to the new module.
  These heals were deliberately left uncommitted (peer-owned surfaces); they are
  not part of this feature and the owning peers will land coherent versions.
- Pre-existing / out-of-scope failures observed but not caused by the rename:
  `test_modelo_130_verify...refuses_without_clean_cross_period_state` fails at
  the calculate step (casilla `01` is now source-bound) - a registry/source-bind
  change; `test_config_auth_accepts_supported_provider_and_rejects_others`,
  `test_config_repair_is_config_scoped_not_root`,
  `test_read_only_status_commands_use_isolated_local_state`, and the
  bootstrap-safe-probe guard are storage-route-refactor collateral; the
  registry-inspect setup errors are a secret-store passphrase prompt
  (`EOFError`) in the non-interactive run, not a feature regression.
- A mandatory `vaultspec-code-reviewer` pass (commit `1b8e7767c` revision)
  surfaced one CRITICAL and four HIGH findings the initial rename missed: the
  verb-registration rename had not been swept through five out-of-band surfaces.
  CRITICAL - the runtime profile-bound write-guard allowlist in
  `storage_write_policy.py` still named the old `capture` / `refresh` verb paths,
  so the renamed live + censo write verbs fell through to fail-OPEN and bypassed
  the root-fallback write refusal; fixed by renaming the six entries and adding
  the live `pull` verbs to the guard-predicate regression set. HIGH - curated
  operator help advertised dead verbs (a RED gate), six error-registry
  `default_suggestion` fields and the cross-period `next_action` builders and two
  censo `LiveSnapshotError` suggestions instructed operators to run dead verbs;
  all updated to the `pull` family with their asserting tests. MEDIUM - ten
  `_emit_envelope(command=...)` identifiers had drifted from their already-renamed
  `@register_schema` keys; realigned. The rule's enforcement claim was softened to
  state the gates' real coverage and mandate the by-hand sweep surfaces a verb
  rename must touch. Post-revision gates green; the two residual failures in the
  affected-test run are the same peer `SecureObjectNamespaceIntegrity`
  secure-storage rebuild error, out of scope.
- One feature-internal test fix was required: the iva-wallet help test asserted
  the legacy Spanish phrase `No se envian opciones`; because translating the
  renamed `pull_history_help` key (which the honesty gate requires) makes the
  help resolve to the real es value instead of the English code default, the
  test's es fallback was updated to a stable substring of the current es
  translation, preserving the no-submit-policy assertion intent.
