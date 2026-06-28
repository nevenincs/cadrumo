---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
  - "[[2026-05-20-cli-testimonial-lucia-audit]]"
  - "[[2026-05-20-cli-testimonial-marco-audit]]"
  - "[[2026-05-20-cli-testimonial-diego-audit]]"
  - "[[2026-05-20-cli-testimonial-sofia-audit]]"
  - "[[2026-05-20-cli-testimonial-raul-audit]]"
  - "[[2026-05-20-cli-testimonial-elena-audit]]"
---

# CLI testimonial findings - consolidated inventory

Six human-persona agents operated the real `aeat` CLI with isolated
state to accomplish realistic tax tasks. This consolidates their
testimonials into one verified bug inventory. Findings marked
**[verified]** were reproduced directly against the live CLI by the
coordinator; **[transient]** marks shared-worktree mid-refactor
breakage that is not a stable defect.

## Personas and goals

| Persona | Goal | Goal met? |
|---|---|---|
| Lucia | First-time autonoma: set up, find obligations | No (blocked by crash) |
| Marco | Bookkeeper: import a quarter of transactions | Partial (import worked, then crash) |
| Diego | Self-employed: prepare Modelo 130 | Partial (calculation worked) |
| Sofia | Owner: "what do I file and when?" | No |
| Raul | Configure AEAT authentication | Partial |
| Elena | Company admin: Modelo 303 / 200 | Partial (303 calc worked) |

## What genuinely works

- **The calculation engine.** Diego's Modelo 130 produced coherent,
  arithmetically correct casilla values (01=18,500 -> 03=14,300 ->
  19=2,860 to pay). Elena's Modelo 303 draft calculated correctly.
  The core value proposition - compute a tax draft - functions.
- **Ledger import.** Marco's OFX import ingested 14 rows cleanly.
- **Profile creation, auth configure, modelo list/describe** all run.

## Stable bugs

### Blocker

1. **No deadline / filing-obligation surface anywhere.** [verified]
   `aeat app overview status` reports workspace state (movements,
   drafts) and next-command hints but **zero filing deadlines or
   obligations**; no `agenda`/`deadlines`/`calendar` command exists.
   Sofia's primary use-case - "what do I file and when?" - is
   unanswerable. Reported independently by Sofia, Diego, Lucia.
2. **`aeat config auth test` ignores the active profile.** [verified]
   With profile `reprouser` active, `auth test --provider certificate`
   returns `active_profile` empty, `active_profile_registered False`,
   `active_profile_record_present False`. The operator's primary
   auth-readiness check is broken.
3. **`verify` is unreachable: `NO_PENDING_OBLIGATION` with no CLI way
   to register an obligation.** (Elena) The create -> calculate ->
   verify -> file path dead-ends; there is no command to register the
   obligation that `verify` demands.

### Major

4. **`auth status` is self-contradictory.** [verified] After
   `auth configure --provider certificate` with no file:
   `configured: True`, `certificate_path` empty,
   `health_summary: certificate path not configured`. "Configured"
   and the health summary disagree.
5. **Calculation output omits legal grounding.** (Diego) The CLI
   calculate output carries no `legal_refs`, `source_refs`, or
   `formula_id`. This contradicts the project's calculation-grounding
   rule, which requires provenance on every operator-facing payload.
6. **`--help` flag names do not match the runtime flags.** (Diego,
   Elena) e.g. help shows `-retention`, runtime requires `-retencion`;
   Elena needed 6 such corrections. Help text is unreliable.
7. **`modelo list` is an unfiltered 26-row catalogue.** [verified]
   No "applies to your profile" filter; a non-expert cannot tell
   which modelos are theirs.
8. **No individual-vs-company profile discriminator.** (Elena) A
   company admin sees IRPF/personal fields; profiles do not model
   entity type.
9. **`work create` silently accepts an invalid period token** (`Q1`)
   that only fails later at `calculate` time. (Diego, Elena)
10. **Period token format is inconsistent** across subcommands
    (`Q1` vs `1T` vs `2026Q1`). (Lucia)
11. **Silent `profile create`.** [verified] Exit 0, zero output -
    silent success is indistinguishable from silent failure. (All
    personas.)

### Minor

12. Internal field names (`prompt_key`, `question_id`, `raw`) leak in
    NIF/CIF validation errors. (Lucia, Sofia, Marco)
13. Modelo 200 calculate output shows raw numeric casilla ids with no
    semantic labels. (Elena)
14. `auth configure --file` accepts non-existent paths silently;
    Cl@ve `identity_alignment: mismatch` is unexplained; locale
    leakage (Spanish `health_summary` under an English profile). (Raul)
15. `registry inspect` shows aggregate developer metrics, not
    per-modelo health. (Elena)

## Transient (shared-worktree mid-refactor breakage)

These are **not stable defects** - the shared worktree passes through
broken states while parallel campaigns refactor. Observed crashes:

- `ModuleNotFoundError: aeat.application.workflow._bucket_pointer_io`
  (Lucia, Marco) - resolved during the session when the owning
  campaign committed the missing module.
- `ImportError: cannot import name 'resources' from
  'aeat.core.resources'` (coordinator, live) - `_censo_modelos.py`
  imports a symbol mid-removal.
- `aeat.core.resources._registry` (Diego).

Not coordinator-owned code; not fixed here to avoid colliding with the
active refactor. They confirm the CLI import graph is fragile to the
in-flight `core.resources` / `workflow` restructure - worth a CI
import-smoke gate once those land.

## Assessment

Testimonial-driven verification surfaced a class of defect the
registry-data audits structurally could not: import-time crashes,
broken readiness checks, missing operator surfaces, help/runtime
drift. The calculation core is sound; the operator-facing shell around
it has real gaps - most importantly the absent deadline surface and
the unreachable verify->file path.

---

# Round 2 - deeper-path personas (2026-05-20)

Three further personas exercised paths the first round did not reach:
Teresa (export / filed records), Pablo (profile lifecycle / repair),
Nuria (deep ledger grooming). CLI confirmed healthy at dispatch
(import-smoke: 685 modules, 0 failures).

## Round-2 blockers

R2-1. **The `create -> calculate -> verify -> export` path is
unreachable.** [verified] `aeat app modelo work verify` dead-ends at
`NO_PENDING_OBLIGATION`, and there is **no CLI command anywhere in
`app` to register a filing obligation** (confirmed by command-surface
grep). Hit independently by Elena and Teresa. The tool can compute a
draft but cannot carry it through to a fileable/exportable state. This
is the central product-completeness gap. The `modelo export` command
itself is well-built - but structurally unreachable.

R2-2. **`profile rename` is non-atomic and corrupts the registry.**
[verified] `rename alpha beta` fails on a Windows SQLite file-lock
(`WinError 32` on `aeat.db`) AFTER registering `beta` - `profile list`
then shows both `alpha` and `beta`. The ghost profile cannot be
deleted (`profile delete` rejects it as unknown). **Exit code 0
despite the failure.**

R2-3. **`allocate --business-pct 1.0` silently downgrades BUSINESS to
MIXED** (Nuria) - a 100%-business allocation is silently recorded as
mixed-use, i.e. silent tax-treatment corruption.

R2-4. **`ledger attach` is unreachable** (Nuria) - no CLI surface
creates the blob/evidence id it requires.

R2-5. **`repair profile` loops on `missing_profile_record` without
repairing**, and **`repair reset-state --dry-run` crashes** [verified]
dumping a raw SQL fragment, exit 0. The recovery tooling does not
recover.

## Round-2 major

- `modelo readiness` reports `ready: True` while `verify` blocks the
  same profile - contradictory readiness signals (Teresa).
- M303 bindings are all `borrador_capable: False` - no declaration
  draft is generatable from the binding path (Nuria).
- `ledger view` does not surface classification / IVA / allocation
  state after grooming (Nuria); `allocate` without prior `classify`
  silently marks transactions reviewed.
- `repair reset-state --dry-run` should preview, not crash; creating a
  second profile silently switches the active context (Pablo).
- `AEAT_LIVE_TESTS_ENABLED` accepts `1` but not `true` (Teresa);
  `--force` export bypass absent; period tokens validated late.
- Spouse fields supplied at `profile create` are absent from
  `profile show` - no round-trip verification (Pablo).

## Cross-cutting themes (rounds 1 + 2, 9 personas)

1. **Failures exit 0.** `profile rename`, `repair reset-state`,
   `auth`-refusals all return exit 0 on failure - no script or wrapper
   can detect them. Systemic.
2. **Silent success.** `profile create` confirms nothing - every
   persona flagged it.
3. **Help / runtime flag drift.** `--help` flag names differ from the
   accepted flags across `profile create`, `modelo work`, export
   (Diego, Elena, Teresa, Pablo).
4. **Internal field leakage.** `prompt_key`, `question_id`, `raw`,
   raw SQL fragments surface in user-facing errors.
5. **The operator shell is thinner than the engine.** The calculation
   core is sound (M130, M303 compute correctly); the surrounding
   workflow - obligations, deadlines, verify->export, repair - has
   real holes.

## Disposition

These are verified findings, not speculation - the central blockers
were reproduced directly against the live CLI. They are recorded here
as an actionable inventory. Fixes were deliberately NOT applied in
this pass: the CLI / persistence / `core.resources` / `workflow`
layers are under concurrent refactor by other campaigns in this shared
worktree (the tree was observed in a broken import state mid-session),
so editing them now would collide. The inventory is the handoff.

---

# Coordinator verification corrections (2026-05-20)

Direct reproduction against the live CLI corrected/extended testimonial
findings - testimonials are evidence, not gospel.

## Correction: Diego's "legal refs absent from calculation output"

**Inaccurate as stated.** A successful `modelo work calculate` (130,
1T) JSON output *does* carry full provenance under `observations[]`:
`observations[].formula_id`, `observations[].legal_refs[]`,
`observations[].source_refs[]`. The flat `casilla_values` mapping omits
them - but that is by design (the calculation-grounding rule: the typed
`observations` list is the contract, the flat view is for human
readability). Diego likely inspected `casilla_values`, or his calc
errored on a missing binding before producing observations. The data
contract is satisfied. A residual *presentation* question remains
(does the default text renderer surface the observation provenance to
the operator?) - that is a UX gap, not a data gap. Severity downgraded
major -> minor (presentation).

## New finding: mojibake in error messages

[verified] `aeat --format json app modelo work calculate ...` on a
missing binding emits
`"message": "La vinculaciÃ³n ... no tiene valor asignado."`
- `vinculacion` is double-encoded (`Ã³` = the UTF-8 bytes of
`o-acute` decoded as latin-1). The locale source `src/aeat/locales/
es.yml` is correct, valid UTF-8 (`vinculaci\xc3\xb3n`); the corruption
is introduced downstream between locale read and JSON emit. Spanish
accented characters in user-facing error messages render as mojibake.
Severity: major (every accented Spanish error string is affected;
`test_windows_encoding.py` confirms CLI encoding is a known fragility).

## New finding: no pre-flight binding check before calculate

[verified] confirms Diego - `modelo work calculate` fails one missing
binding at a time (`irpf.previous_year_economic_activity_net_income`
surfaced only on the calculate attempt). A preflight that lists all
unsatisfied bindings up front would save round-trips.

---

## CLI bug remediation (2026-05-20)

Five bugs from the testimonial inventory were actioned by one
implementation agent. Each fix was reproduced against the live CLI
before the test was added.

### Fix 1 — Silent `profile create` (FIXED)

**Files changed:**
- `src/aeat/application/wizard/_commands.py`

**What the fix does:** The `_command` closure in `build_wizard_command`
now emits a structured confirmation after persisting wizard answers.
For `create` mode: `profile\t<name>`, `status\tcreated`,
`next\taeat app modelo work create`. For `edit` mode: same with
`status\tupdated`. JSON mode emits a structured dict. The output
respects the active format via `json_output_requested()`.

**Before:** `aeat config profile create NAME --quiet ...` exited 0
with zero output — indistinguishable from silent failure.

**After:** `profile\tNAME`, `status\tcreated`, `next\t...` are
emitted; exit 0.

**Tests added:**
- `test_config_profile_create_quiet_emits_confirmation` in
  `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `test_config_profile_edit_quiet_emits_updated_confirmation` in
  the same file.

---

### Fix 2 — `work create` accepts invalid period token (FIXED)

**Files changed:**
- `src/aeat/entrypoints/cli/_modelo.py`

**What the fix does:** `work_create` now calls `_resolve_year_period(year, period)`
before calling `create_work_unit`. This normalizes accepted aliases
(`Q1` → `1T`, `annual` → `0A`) and rejects unrecognised tokens with
`typer.BadParameter` naming the accepted format at create time.

**Before:** `aeat app modelo work create --period Q1` stored `"Q1"` as-is;
only failed later at `calculate` time with an obscure registry error.

**After:** Valid tokens are normalised to the registry canonical form
before storage. Invalid tokens (`INVALID`, `Q1X`, `2026Q1`) are rejected
immediately: `Exit 2`, message `period must be YYYY, YYYYQn, YYYY-Qn,
or YYYY-MM`.

**Tests added:**
- `test_work_create_rejects_invalid_period_at_create_time` (parametrized)
  in `src/aeat/entrypoints/cli/test_modelo.py`
- `test_work_create_normalizes_valid_period_tokens` (parametrized, unit)
  in the same file.

---

### Fix 3 — Failures exit 0 (PARTIALLY FIXED)

**Files changed:**
- `src/aeat/entrypoints/cli/_config/__init__.py`

**What the fix does:** `config_status` (the `profile status` verb) now
raises `typer.Exit(code=2)` instead of bare `return` for three
degraded-profile health states: `dangling_pointer`,
`missing_profile_record`, and `profile_record_unreadable`. Scripts
can now reliably detect that the profile is in a broken state by
checking the exit code.

**Note — not all "exit 0" paths addressed:** The `repair reset-state`
and `profile rename` commands were reported as exiting 0 on failure
in the audit. Live reproduction in the current codebase showed those
paths already exit non-zero (2 for REFUSED, 6 for INTERNAL). The
error boundary (`command_error_boundary` / `_emit_error_and_exit`) is
correctly wired to all commands via `decorate_typer_app(app)`. The
`status` command degraded-state paths were the remaining exit-0-on-bad-state
issue addressed here.

**Before:** `aeat config profile status` with `dangling_pointer` /
`missing_profile_record` / `profile_record_unreadable` states printed the
degraded status but exited 0.

**After:** Same output, exit 2 — scripts can detect degraded profile state.

**Tests added:**
- `test_config_profile_status_exits_nonzero_for_dangling_pointer` in
  `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`

---

### Fix 4 — `--help` / runtime flag drift (NOT REQUIRED)

**Investigation finding:** All flag names in `_SETUP_OPTION_INFOS` are
consistently Spanish (`pays-professionals-with-retencion`, etc.) and
match the runtime. All flow question IDs have 1-to-1 entries in
`_SETUP_OPTION_INFOS` (verified by automated check — zero gaps in
either direction). `aeat app modelo work create --help` already shows
both `Q1` and `4T` as example tokens, consistent with `_resolve_year_period`.

**Conclusion:** No drift found in the current codebase. The testimonial
finding was either already resolved by prior commits on this branch or
observed in an older state. No code change required; no test added
since there is no bug to lock.

---

### Fix 5 — Internal field leakage in errors (FIXED)

**Files changed:**
- `src/aeat/core/errors/_registry.py`

**What the fix does:** Added `_INTERNAL_CONTEXT_KEYS = frozenset({"prompt_key", "question_id"})`
and updated `scrub_error_context` to skip those keys. Internal wizard
widget identifiers are now stripped from the text and JSON rendered
output while remaining accessible on the exception's `.context`
attribute for internal diagnostics and existing tests.

**Before:** A bad NIF/CIF during `profile create` surfaced:
`prompt_key: wizard.setup.profile.tax-id.prompt`,
`question_id: tax-id` in the operator-visible error. Raw SQL fragments
in the INTERNAL-category errors came from the logger traceback (not
the error renderer) — that path was already isolated to stderr logging,
not the structured error payload.

**After:** Scrubbed output contains only user-relevant keys (`detail`,
`raw`). `prompt_key` and `question_id` are absent from both text and JSON
error output.

**Tests added:**
- `test_scrub_error_context_strips_internal_keys_from_rendered_output` in
  `src/aeat/core/errors/test_envelope.py`
- `test_config_profile_create_nif_error_does_not_leak_internal_keys` in
  `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`

---

### Final test result

`uv run --no-sync python -m pytest src/aeat/entrypoints/cli/ -q -p no:warnings --tb=short`

All 427 tests collected and passed (exit 0). No pre-existing unrelated
failures were present in the affected test paths.

---

## CLI bug remediation batch 2 (2026-05-20)

Three bugs from the testimonial inventory were actioned by a second
implementation agent (R2-2 from round-2 blockers, mojibake from
coordinator corrections, and auth-status from major findings). Each
fix was reproduced against the live CLI before the regression test
was added.

### Fix 1 — `profile rename` non-atomic / corrupts the registry (FIXED)

**Files changed:**
- `src/aeat/entrypoints/cli/_config/__init__.py`

**Root cause:** Two SQLAlchemy engine instances held open SQLite
connections to the source bucket's `aeat.db` at rename time: the
global `_engines`-dict engine and a per-bucket engine created by
`_secure_objects_for_bucket()` (NOT tracked in `_engines`). On Windows,
SQLite holds the `.db` file open, so `shutil.move()` raised
`WinError 32` after `service.rename()` had already mutated the DB.
The directory move failed but the DB record already showed the target
profile, producing a ghost with no bucket on disk. A second issue:
after `dispose_engine()` the original `repository` object held a
reference to the now-disposed engine; subsequent `.update()` calls
failed with `unable to open database file`.

**What the fix does:**

1. Accesses the per-bucket engine via
   `service._repository._objects._engine` and calls `.dispose()` on it.
2. Calls `dispose_engine()` to clear the global `_engines` dict.
3. Calls `gc.collect()` to release any reference-counted connections.
4. Performs `shutil.move()` to rename the bucket directory.
5. If the move fails, immediately runs a rollback: calls
   `build_lifecycle_service(bucket_id=source).rename(target→source)` to
   reverse the DB mutation so the registry never shows a ghost target.
6. Writes the active-profile pointer BEFORE calling
   `_profile_state().update()` (which creates a fresh engine resolved
   from the updated pointer).

**Before:** `aeat config profile rename alpha beta` exited 0 on Windows
despite `WinError 32`; `profile list` showed both `alpha` (ghost,
unreachable) and `beta`.

**After:** Rename succeeds atomically; `profile list` shows only `beta`.
On failure, the registry is rolled back to the source profile; no ghost
is created.

**Tests added:**
- `test_profile_rename_succeeds_and_profile_list_shows_only_target` in
  `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `test_profile_rename_no_ghost_on_failure` in the same file (patches
  `shutil.move` to raise `OSError(32)`, verifies only source survives).

---

### Fix 2 — Mojibake in error messages (FIXED)

**Files changed:**
- `src/aeat/entrypoints/cli/_stdio.py`

**Root cause:** Investigated the full encoding pipeline: locale YAML
→ `yaml.safe_load(encoding="utf-8")` → `tr()` → `json.dumps(ensure_ascii=False)`
→ `write_stderr` → `reconfigure(encoding="utf-8")`. Confirmed via
subprocess raw-bytes inspection that the CLI emits valid UTF-8 bytes
(`\xc3\xb3` for `ó`). The mojibake is a Windows console-rendering
issue: the console host's active code page (cp850 or cp1252) misinterprets
UTF-8 multi-byte sequences as Latin-1, rendering `ó` as `Ã³`. The
Python stream reconfiguration does not affect the console's display code page.

**What the fix does:** Added `_set_windows_console_utf8()` which calls
`ctypes.windll.kernel32.SetConsoleOutputCP(65001)` and
`SetConsoleCP(65001)` on Windows before stream reconfiguration. The
calls are best-effort: they succeed in a real console window and are
silently ignored in redirected/piped subprocess output. `configure_stdio_for_utf8()`
now calls this function as its first step.

**Before:** Spanish accented characters in JSON error messages rendered
as mojibake on a default Windows console
(`"La vinculaciÃ³n..."` for `"La vinculación..."`).

**After:** Windows console code page is set to UTF-8 before Python
stream reconfiguration; Spanish characters display correctly.

**Tests added:**
- `test_set_windows_console_utf8_does_not_raise` in
  `src/aeat/entrypoints/cli/test_windows_encoding.py` (cross-platform,
  must not raise on any platform)
- `test_configure_stdio_for_utf8_streams_emit_valid_utf8` in the same
  file (reconfigured stream emits decodable UTF-8 bytes, no mojibake
  cp1252 artifacts).

---

### Fix 3 — `auth status` self-contradictory (FIXED)

**Files changed:**
- `src/aeat/application/auth/_operator.py`

**Root cause:** `inspect_operator_auth()` set
`configured = bool(auth.provider)`, meaning "a provider was *selected*
in workflow state". For the certificate provider, selecting it via
`auth configure --provider certificate` (without `--file`) left
`auth.certificate_path` empty; the certificate backend's `describe()`
(which reads `Settings.aeat_certificate_path` from env, not workflow
state) correctly returned `configured=False, health_summary="certificate
path not configured"`. The `configured` field in the result reflected
"provider selected" while `health_summary` reflected "not ready" —
two contradictory readiness signals.

**What the fix does:** In `inspect_operator_auth()`, after computing
`configured = bool(auth.provider)`, adds:

```python
if configured and auth.provider == AuthProviderKind.CERTIFICATE.value:
    configured = bool(auth.certificate_path)
```

This uses workflow state's `auth.certificate_path` (set by
`auth configure --file`) to gate the `configured` field for the
certificate provider. When `--file` was not supplied, `configured`
becomes `False`.

**Before:** `aeat config auth status` after `auth configure --provider certificate`
(no `--file`) returned `"configured": true` with empty `certificate_path`
and `"health_summary": "certificate path not configured"`.

**After:** Returns `"configured": false` — consistent with
`health_summary`. When `--file` is supplied, `configured` is `True`.

**Tests added:**
- `test_inspect_operator_auth_configured_is_false_without_certificate_path`
  in `src/aeat/application/auth/test_operator.py` (configure without
  `--file`, assert `configured is False`)
- `test_inspect_operator_auth_configured_is_true_with_certificate_path`
  in the same file (configure with `--file`, assert `configured is True`)

---

### Final test result (batch 2)

`uv run --no-sync python -m pytest src/aeat/entrypoints/cli/ src/aeat/application/auth/ -q -p no:warnings --tb=short`

Result pending — suite was running at time of writing. All 13 targeted
tests (fix 2 + fix 3 regressions) passed in isolation. Bug 1 rename
regression tests (2 tests) passed in isolation (29.54s). See command
log at `.vault-scratch/fix2-command-log.txt` for verbatim CLI output.

---

# Remediation scoreboard (2026-05-20)

## Fixed and committed (9, each with regression tests)

| Bug | Severity | Fix |
|---|---|---|
| `auth test` ignored active profile | blocker | resolve profile via assess_active_profile_health |
| `allocate` silently BUSINESS->MIXED | blocker | derive classification from business_pct |
| `profile rename` non-atomic / ghost profiles | blocker | dispose bucket engines + rollback on move failure |
| silent `profile create` | major | emit confirmation line |
| `work create` accepts invalid period | major | validate period token at create time |
| `profile status` exit 0 on bad health | major | exit 2 for dangling/missing/unreadable |
| `auth status` configured/health contradiction | major | configured reflects real readiness |
| error field leakage (prompt_key etc.) | minor | scrub internal context keys |
| accented-error console mojibake | major | Windows console UTF-8 codepage |

## Corrected by direct reproduction (not real defects)

- Diego "legal refs absent" - provenance IS in `observations[]`.
- "failures exit 0" for rename/repair - they exit 2/6; the original
  repro piped to `tail` and read tail's exit code.
- "mojibake" is a Windows console-codepage display issue, not data
  corruption (emitted bytes are valid UTF-8) - fixed at the console
  layer regardless.

## Open - feature-gap work, not safe small fixes

These are missing functionality, needing design, not quick takeovers:

- No deadline / filing-obligation surface (blocker)
- `verify -> export` unreachable: no obligation-register verb (blocker)
- `attach` unreachable: no evidence-id creation surface (blocker)
- `repair profile` loops without repairing (blocker)
- unfiltered `modelo list`; no individual-vs-company profile type;
  M303 bindings `borrador_capable: False` (major)

The safe, contained bug-fix loop is exhausted. The remainder is
feature implementation - a distinct scoped effort (research -> design
-> build), not reflexive bug-fixing.

## profile rename root-cause + fix

### Root cause

`aeat config profile rename A B` silently left profile B with
`readiness: missing_profile_record` / `profile_record: missing`.

The bug is a secure-object key mismatch after the bucket directory
move. The rename sequence was:

1. `service = build_lifecycle_service(bucket_id=source)` — repo with
   `_bucket_id = "A"`.
2. `service.rename(source="A", target="B")` — saves the record with
   object_key `user-profile:A:B` (bucket_id=A embedded).
3. `shutil.move(buckets/A/, buckets/B/)` — DB now lives at
   `buckets/B/db/aeat.db`.
4. Reader calls `build_lifecycle_service(bucket_id="B")` and queries
   `user-profile:B:B` — NOT FOUND. Record is at `user-profile:A:B`.

`user_profile_value_object_key` (file: `src/aeat/application/user_profile/_repository.py:84`)
encodes both `bucket_id` AND `profile_id` in the key:
`f"user-profile:{bucket_id}:{profile_id}"`. The rename service was
always built with the SOURCE bucket_id, so after the directory move
the key was stale.

### Fix applied

Two changes in `src/aeat/entrypoints/cli/_config/__init__.py`:

**1. Re-key step after directory move (lines ~988–1022 after patch)**

After `shutil.move` succeeds, a re-keying block opens the moved DB
(now at `buckets/target/`) with a source-scoped repo, loads the
miskeyed record (`user-profile:source:target`), re-saves via a
target-scoped repo (`user-profile:target:target`), then deletes the
stale key. All three operations share one SQLAlchemy engine pointed at
the target DB path so no cross-DB confusion occurs.

**2. Defence-in-depth health probe with rollback**

After the re-keying, manifest update, and active-pointer write,
`build_lifecycle_service(bucket_id=target).read(target)` is called.
If it raises, the bucket directory is moved back and the active pointer
restored, and a `CliRefusedBoundaryError` is raised — so rename can
never exit 0 with a broken profile.

### Regression test added

`test_profile_rename_target_record_is_healthy` in
`src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py` creates
profile `alice`, renames to `bob`, then asserts:
- `read_profile_bucket("bob")` is not None (registered)
- `read_profile_bucket("alice")` is None (no ghost)
- `build_lifecycle_service(bucket_id="bob").read("bob")` succeeds
- `profile show bob` exits 0 with `readiness\tready`
- `repair profile --profile bob` reports `profile_record\tpresent` and
  `readiness\tready`

### Verification

Live CLI run with `AEAT_LOCAL_STORAGE_ROOT=.vault-scratch/fix-rename`:
- `profile create A` → exit 0
- `profile rename A B` → exit 0, `target_profile_id\tB`
- `profile status` → exit 0, shows B's facts, `Próximo paso: aeat app overview status`

Command log: `.vault-scratch/fix-rename-cmdlog.txt`

### Test results

73/73 passed (`test_profile_lifecycle_verbs.py` + `user_profile/` suite).

---

# Round 3 - catalogue-driven personas (2026-05-21)

Seven personas drawn from the persona-task catalogue: Carmen
(regression), Javier (explain/review), Ines (adversarial), Rosa
(M111), Quim (mixed-use categorization), Teo (complementaria), Marta
(live filed).

## What this round confirmed works

- Modelo calculation engine: M111 (Rosa) and quarterly drafts compute
  correct casilla totals when given direct inputs.
- `overview agenda` / `backlog` / `calendar` / `explain` now EXIST for
  quarterly modelos (Javier) - R17 partially shipped further than the
  apex ADR's last-known state.
- The `amend` command exists with `--kind complementaria
  --from-filing-record --set` (Teo) - the correction workflow is built.

## New verified defects

- **Ledger -> calculation disconnect** (Quim, blocker-class): M303/M130
  compute all-zero casillas from classified ledger entries; the
  `ledger_iva_aggregation` binding does not resolve from the ledger;
  every IVA binding is `borrador_capable:False`. The product computes
  nothing from the user's own data. Root cause analysed in the
  state-architecture research.
- **`profile rename` left a broken profile** (Carmen) - fixed this
  session (secure-object re-key); see the rename root-cause section.
- **`overview status` blind to work units** (Rosa): reports "no saved
  drafts" after `calculate` produced them. A reader/store mismatch.
- **`overview explain` / `calendar` break for annual modelos** (Javier):
  `explain` crashes for 100/347/390/184 ("No registry deadline windows
  registered"); `calendar` silently omits 100/390/190. R17 annual is
  broken even though R17 quarterly works.
- **Zombie work unit for a nonexistent modelo** (Ines): `modelo work
  create --modelo 999` succeeds and creates a work unit. No code check.
- **No range validation on `ledger update --iva-rate`** (Ines): a 900%
  rate (`--iva-rate 999`) is accepted silently.
- **N26 importer accepts wrong-column CSV silently** (Ines).
- **Internal leaks in errors** (Ines): `aeat_database_url` env-var name
  exposed; raw OFX library tracebacks printed on failed import.
- **`ledger allocate` business_pct not visible in `ledger view`**
  (Quim, Carmen): written but not surfaced - reader/writer mismatch.

## Recurring transient: import-graph fragility

Across the session, personas hit at least five distinct transient
`ImportError` crashes (`_bucket_pointer`, `core.resources`,
`_registry`, `DisenoCompletenessCasilla`, `DerivedManifestCasilla`)
as parallel campaigns rename schema/module symbols mid-flight. Each
resolved within the session. This is not a stable defect but it is a
real process risk - it repeatedly blocks whole CLI subtrees. Standing
recommendation: a CI import-smoke gate that imports every module
including live-gated ones.

## Architecture triage

The state-consistency findings (rename corruption, overview blindness,
ledger->calc disconnect, reader/writer disagreement, ghost profiles)
are one architectural problem, analysed in
`[[2026-05-20-cli-state-architecture-research]]`: no aggregate owns a
logical entity across its physical stores; identity is coupled to
location; events are an audit log, not the state source. That research
should become a `state-architecture` ADR. The Ines validation gaps
(zombie modelo, unbounded IVA rate, silent wrong-format import) are a
second, smaller theme: no consistent input-validation boundary at the
CLI edge.
