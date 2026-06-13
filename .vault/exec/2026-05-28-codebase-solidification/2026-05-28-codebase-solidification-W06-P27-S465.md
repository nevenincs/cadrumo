---
step_id: S465
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P27.S465-S475

**Steps**: S465-S475 — P27 tr()-as-positional anti-pattern sweep across 11 operator-facing modules.

## Outcome

Closed all 11 Steps of P27 in a single-agent pass. Every `raise AeatError(tr("key"))` site
across the listed modules was migrated to deferred `translated_message="key"` with optional
`context={...}` kwarg, so locale resolution happens at render time rather than at raise time.

### S465 — wizard/_persistence.py
- WorkflowInputMismatchError bare English string at line 142 migrated to
  `translated_message="application.wizard.errors.persist_answers_edit_requires_supplied_question_ids"`.
- New locale key added across en/ca/es/hu via `python -m aeat.locales scaffold`.

### S466 — entrypoints/cli/_config/__init__.py
- ~40 `_CliRefusedBoundaryError(tr(...))` sites migrated. All now use `translated_message=` + `context=`.
- Removed no-longer-needed `tr` import calls where applicable.

### S467 — entrypoints/cli/_config/_google.py
- 4 `CliRefusedBoundaryError(tr(...))` sites migrated. The f-string at line 170 is intentional
  (bounded suffix table) and was left in place.

### S468 — entrypoints/cli/_config/_profile_census.py
- 2 `CliRefusedBoundaryError(tr(...))` sites migrated (replace_all).

### S469 — wizard/_prompter.py + wizard/_commands.py
- `_prompter.py`: 3 WizardUnsupportedConsoleError sites migrated.
- `_commands.py`: WizardMissingFlagError x3 + WizardEditUnsupportedConsoleError migrated.

### S470 — workflow/_models.py
- 2 NoActiveProfileError raises migrated + sibling LedgerNoActiveBucketError discovered and migrated.
- Removed unused `from ...core.i18n import tr` import.

### S471 — modelo/_actions.py
- WorkUnitNotFoundError x6, ExternalModeloImportError x2, WorkUnitMutationRefusedError x3,
  CalculationRevisionNotFoundError x2, ModeloRecordNotFoundError x2,
  VerificationReportNotFoundError x1, ModeloAggregationBindingError x1 all migrated.

### S472 — aggregation/_models.py
- 4 AggregationPeriodError raises migrated. `tr` import retained (still used at line 123
  with `message=tr(...)` — a correct non-antipattern site).

### S473 — user_profile/_orchestration.py
- ProfileNotFoundError x2 + ProfileAlreadyRegisteredError x1 migrated.
- Removed unused `from ...core.i18n import tr` import.

### S474 — filing/_runtime_repository.py
- 2 ModeloApplicationError raises migrated.
- Removed unused `from ...core.i18n import tr` import.

### S475 — inventory test
- New AST-based test at `src/aeat/test_locale_tr_positional_inventory.py` scans all 11 swept
  modules and asserts zero `raise AeatError(tr(...))` positional anti-pattern sites.
- Excludes `_bad` and `_google_refusal` factory functions (return non-AeatError types).
- Fixed 14 test assertions across test_resume.py, test_transaction_catalogue_resolution.py,
  test_import_flow.py, and test_prompter.py that matched against `str(error)` (now empty with
  deferred translation) — updated to assert `raised.value.translated_message == "key"` or use
  `resolve_error_message()`.

## Files

- `src/aeat/application/wizard/_persistence.py`
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/entrypoints/cli/_config/_profile_census.py`
- `src/aeat/application/wizard/_prompter.py`
- `src/aeat/application/wizard/_commands.py`
- `src/aeat/application/workflow/_models.py`
- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/aggregation/_models.py`
- `src/aeat/application/user_profile/_orchestration.py`
- `src/aeat/application/filing/_runtime_repository.py`
- `src/aeat/test_locale_tr_positional_inventory.py`
- `src/aeat/locales/en.yml`, `ca.yml`, `es.yml`, `hu.yml`
- `src/aeat/application/workflow/test_resume.py`
- `src/aeat/application/workflow/test_transaction_catalogue_resolution.py`
- `src/aeat/application/modelo/test_import_flow.py`
- `src/aeat/application/wizard/test_prompter.py`

## Commit

08910e058
