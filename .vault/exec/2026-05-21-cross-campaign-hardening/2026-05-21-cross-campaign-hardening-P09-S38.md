---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P09.S38'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
  - '[[2026-05-13-eliminate-shims-audit]]'
---

# `cross-campaign-hardening` `P09.S38`

Closed GEN-2 task 506.

- Modified: `src/aeat/entrypoints/cli/test_backend_boundary.py`
- Verified: `.vault/audit/2026-05-13-eliminate-shims-audit.md`

## Description

Triaged the May 13 discovery inventory against the current tree. The
production ignored-`path` shim rows identified for `load_usage_ratios`,
`save_usage_ratios`, `_load_transaction_catalogue`, and
`_read_transaction_catalogue` are already closed: the current signatures
take bucket ids and no longer delete an ignored path. The LLM provider
package also already keeps `_ProviderAdapter` and `_DeterministicAdapter`
outside `__all__`.

Added structural regression coverage for those dispositions in the CLI
backend-boundary suite so the inventory does not drift back into source.
Other May 13 rows were checked by existing gates or current source state:
the locale audit now passes, no `pytest.mark.xfail` or
`pytest.raises(Exception)` shortcut remains in `src/aeat`, and the
original strict-pydantic cluster no longer has `strict=False` or
`extra=ignore` matches in the audited high-risk paths.

No production behavior was changed for this row.

## Tests

`uv run ruff check src/aeat/entrypoints/cli/test_backend_boundary.py` passed.

`uv run pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_discovery_swarm_ignored_path_shims_stay_removed src/aeat/entrypoints/cli/test_backend_boundary.py::test_discovery_swarm_llm_provider_private_aliases_are_not_public src/aeat/entrypoints/cli/test_backend_boundary.py::test_removed_workflow_shim_modules_stay_absent src/aeat/entrypoints/cli/test_backend_boundary.py::test_cli_unit_tests_do_not_contain_process_state_or_xfail_language -q` passed with 4 tests in 2.23s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S38` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P09-S38.md src/aeat/entrypoints/cli/test_backend_boundary.py` passed.
