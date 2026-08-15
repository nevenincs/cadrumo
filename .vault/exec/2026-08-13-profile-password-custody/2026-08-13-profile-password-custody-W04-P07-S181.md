---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d2b9923298b15e92d4c3bc2f46383baf7b943bdbe3d73855503260fc81df156c'
step_id: 'S181'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium switch the repair-policy coverage denominator from a hand-maintained module list to the live command tree, since a declared-but-unmounted command currently satisfies the check and the list had entries naming deleted files that raised from inside the coverage assertion as an error rather than a failure, and rule an owner domain and namespace policy for the four registered commands a live-tree denominator surfaces with no policy row

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py and src/cadrumo/application/repair_integrity.py`

## Description

- Read `test_repair_policy_coverage.py` to establish current state: the
  liveness direction (row cannot outlive its verb) was already live-tree
  based per `S47`; only the coverage direction (verb must have a row) still
  walked a hand-maintained thirteen-module AST list via `_POLICY_COMMAND_MODULES`.
- Switch `_policy_relevant_command_paths_from_sources()` to filter the same
  live click-tree walk (`_live_command_paths()`) already used by the liveness
  direction, instead of AST-parsing the hand-listed modules.
- Delete the now-dead hand-maintained module list, its `test_declared_policy_command_modules_all_exist`
  companion test, and the AST-walking helpers (`_command_paths_from_module`,
  `_typer_constructor_names`, `_collect_typer_mount`, `_collect_typer_commands`,
  `_command_name`, `_keyword_literal`) that existed only to serve it.
- Identify the four commands the live-tree denominator surfaces with no
  policy row, read each command's implementation to ground an owner-domain
  ruling, and add the four rows to `build_repair_policy_command_surface_catalog()`.
- Verify the declared-but-unimplemented surfaces
  (`config.profile.{subject_access_request,delete,rename,export,import}`)
  are unaffected by the denominator switch.

## Outcome

**The switch.** `_policy_relevant_command_paths_from_sources()` now reads
`{path for path in _live_command_paths() if _requires_policy_coverage(path)}`
— the identical live click-tree walk (`cadrumo_click_command()` plus
`list_commands`/`get_command` recursion) the liveness-direction test already
used. This makes the two failure modes the row names structurally impossible
rather than merely rare: a command that is declared in source but never
mounted cannot appear in the live tree, so it cannot be "coverage-visible but
not actually registered"; and a module simply missing from a hand list can no
longer under-report, because there is no longer a list to miss it from. Deleted
`_POLICY_COMMAND_MODULES` (the thirteen-module hand list), the AST-walking
helper functions that existed only to parse it, and
`test_declared_policy_command_modules_all_exist` (the companion test whose own
premise — a stale entry in that list raising `FileNotFoundError` from inside
the coverage assertion — no longer exists once the list is gone; `S47` had
already turned that raise into a readable failure, and this Step removes the
list itself).

**The four surfaced commands and their rulings, each read at its
implementation before ruling:**

- **`app ledger invoice import`** (`_ledger_business_invoice_cli.py::invoice_import`,
  mounted as `invoice_app` under `app ledger`) — bulk-creates catalogue
  invoices from an operator-supplied `--file`, one row at a time through the
  same sole write path `catalogue create` uses. Ledger-domain import of
  taxpayer financial records. Ruled: `owner_domains=("ledger",)`,
  `namespace_policies=(_LEDGER_POLICY,)` — identical policy shape to the
  sibling `app ledger import`/`app ledger export` rows already in the catalog,
  since this is the same ledger-artifact import/export policy class applied
  to the invoice sub-surface. Per `aeat-naming`'s documented exception, the
  operator-facing noun stays the English `invoice` (the internal taxonomy
  stays `payable_invoice`/`collectible_invoice`), so no rename is implied.
- **`app ledger restore`** (`_ledger_lifecycle_cli.py::ledger_restore`) —
  "Restore one stashed or archived ledger transaction to active," a
  confirmation-gated (`--yes`) mutation of ledger transaction state through
  `restore_manual_transaction`. Ledger-domain, matches the `restore` recovery
  leaf. Ruled: `owner_domains=("ledger",)`, `namespace_policies=(_LEDGER_POLICY,)`
  — same policy class as the ledger import/export siblings, since a restore is
  a recovery-facing mutation over the same ledger-transaction evidence class
  those rows already govern.
- **`app modelo m145 export`** (`_modelo_m145_cli.py::m145_export`, mounted as
  `m145_app` under `app modelo`) — "Export a persisted Modelo 145 local
  communication record" through `RegistryFixedWidthRecordRenderer`, i.e. an
  official filing-artifact export in the fixed-width AEAT record format.
  Ruled: `owner_domains=("modelo_filing",)`,
  `namespace_policies=(_MODEL_FILING_POLICY,)` — identical shape to the
  existing `app modelo export`/`app modelo filing-record import` rows, since
  m145 export is the same filing-artifact-preservation policy class applied
  to the M145 sub-surface.
- **`config google sync calc export`** (`_google_sync_calc.py::google_sync_calc_export`)
  — exports a modelo's registry calculation surface (casilla values and
  formulas) to a Google Sheets workbook, and records provenance of the sync
  run through `SyncRunRecordRepository`/`record_sync_run`. This is NOT a
  `modelo_filing` artifact (no official filing bytes leave the system; per
  `aeat-documentation`, Sheets is "a one-way export mirror, never an
  authority") and NOT `ledger`. Ruled a new coarse domain,
  `owner_domains=("google_sync",)`, distinct from the existing domains because
  neither an existing one accurately describes it nor should the policy
  fabricate coverage for the externally-mirrored calculation values
  themselves (which are non-authoritative by design and leave secure storage
  entirely). The namespace policy attaches to the one registered secure-object
  namespace this command actually writes to for durable provenance —
  `SYNC_RUN_RECORDS_NAMESPACE` (`cadrumo.storage.sync_run.records`, owner
  `cadrumo.application.storage`) — via the existing `_secure_object_policy()`
  helper, so the row's metadata is derived from the namespace registry rather
  than invented, per the module's own documented gate contract.

**Declared-unimplemented surfaces: no narrowing.** Checked
`DECLARED_UNIMPLEMENTED_SURFACES` in `_verb_input_schema.py:534` —
`config.profile.subject_access_request`, `.delete`, `.rename`, `.export`,
`.import` are schema-only declarations with no mounted click command by
design (the module's own docstring: "advertising a surface whose verb does
not exist hands an operator an instruction it cannot recover from... it must
not put a dead surface on the wire"). Verified empirically with a standalone
walk of the live click tree (`cadrumo_click_command()`, 282 leaves total):
zero matches for `config profile {export,import,delete,rename,subject...}`.
Cross-checked against the OLD hand-maintained module list: none of its
thirteen modules define a function implementing any of these five verbs
either (they are not backed by any source function at all). Coverage for
these five was therefore absent both before and after this Step's switch —
the switch is neutral here, not a narrowing, because neither denominator
could ever see an unmounted verb.

**Verification.** `pytest src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py -m "unit or integration" -n0`:
6 passed (was 7 before this Step; `test_declared_policy_command_modules_all_exist`
was deleted along with the list it tested). This includes
`test_policy_command_surface_catalog_covers_cli_repair_import_export_and_profile_history_commands`
(the exact-equality coverage direction, now green against the live-tree
denominator with the four new rows), `test_every_catalogued_command_path_resolves_in_the_live_cli`
(liveness direction, unaffected), `test_custody_family_prefixes_are_dormant_or_fully_catalogued`,
`test_the_live_command_walk_is_not_vacuous`,
`test_policy_command_surfaces_are_owned_and_namespace_policies_are_registered`
(confirms the four new rows' `owner_domains` are non-empty and their
namespace policies pass every registry cross-check, including the new
`SYNC_RUN_RECORDS_NAMESPACE` row), and
`test_repair_secure_object_surfaces_use_registry_metadata_instead_of_role_markers`
(pre-existing rows, unaffected).
`ruff check` and `ruff format --check` both clean on the two changed files.

**Bite-proof.** An external pytest plugin, loaded via `PYTHONPATH` + `-p`
from the scratchpad directory (no tracked file touched), monkeypatched
`repair_integrity.build_repair_policy_command_surface_catalog` to drop the
newly-added `app ledger restore` row before the test module's import bound
it. Re-ran the coverage test: it reds exactly as expected —
`AssertionError` naming `'app ledger restore'` as an extra item the live-tree
`discovered` set carries that `catalogued` does not. Removed the plugin file
afterward; the un-patched re-run (already captured above) is green.

## Notes

Edits landed via two separate peer broad-sweep commits rather than being
committed by this session: `repair_integrity.py` in `registry: continue
authority-grade sweep (round 66)` (`a9f14a3155`), and
`test_repair_policy_coverage.py` in `registry: continue authority-grade
sweep (round 67, custody path-identity and logout)` (`8407342720`),
consistent with the shared worktree's fast commit cadence during this Step.
Confirmed post-hoc against `git show`/`grep` on both landed files that the
content matches the intended edit exactly (four new catalog rows present with
correct owner domains; dead AST-walk machinery and its companion test gone).
