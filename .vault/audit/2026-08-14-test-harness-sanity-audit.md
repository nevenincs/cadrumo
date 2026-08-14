---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:93f71d4dda73d18de9f029d5dcdbd52a0a7b3467f7524d0557b1f0224219499c'
related:
  - "[[2026-06-05-test-topology-refactor-adr]]"
  - "[[2026-06-01-test-suite-performance-audit]]"
---

# `test-harness-sanity` audit: `test harness topology, fixtures, and performance`

## Scope

Holistic review of the `src/cadrumo` pytest harness, with particular attention
to the 138 test modules and shared support surface under `src/cadrumo/tests`.
The review covered directory and filename ownership, the boundary between
domain-local and package-global tests, root/package/module `conftest.py`
composition, fixture visibility and drift, policy-enforcement reach,
copy-paste duplication, subprocess and collection cost, and xdist worker
policy. Findings were checked against the accepted pytest-only,
test-topology-refactor, and worker-count decisions and against current focused
pytest/collection evidence. Production code, test code, and pytest
configuration were not changed.

The mechanical topology is healthy: all 2,915 `test_*.py` modules under
`src/cadrumo` currently live below a `tests/` directory, no `_test_*.py` or
`*_test.py` modules were found, and the two focused topology gates pass. The
findings below concern semantic ownership and harness behavior that those
mechanical gates do not prove.

## Findings

### fixture-drift | medium | LLM encrypted-storage fixture ownership is duplicated at two substitutable package scopes

`src/cadrumo/llm/conftest.py:12-28` and `src/cadrumo/adapters/outbound/llm/conftest.py:12-28` independently declare the same bucket id, autouse backend fixture, public `secure_object_test_profile` fixture, function scope, `tmp_path` constraint, and `isolated_runtime_profile` lifecycle; only the relative-import depth differs (`src/cadrumo/llm/conftest.py:10` versus `src/cadrumo/adapters/outbound/llm/conftest.py:10`). This is real duplication, not constraint-shape divergence: either fixture can substitute for the other for descendants in its pytest discovery subtree. Two authorities can now drift independently in bucket identity, scope, reset policy, or teardown while tests remain locally green.

### fixture-drift | high | Forbidden monkeypatch mutations are committed and the enforcing inventory gate is red

Four deterministic production-test modules mutate the module under test through pytest monkeypatch machinery: `src/cadrumo/adapters/inbound/financial/providers/tests/test_ofx.py:266-279`, `src/cadrumo/application/calculations/tests/test_previous_filing_absence_versus_malformed.py:148-181`, `src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py:652-683` and `src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py:694-727`, plus `src/cadrumo/domain/calculations/registry/tests/test_validate_previous_filing_year_coverage.py:49-77` and `src/cadrumo/domain/calculations/registry/tests/test_validate_previous_filing_year_coverage.py:84-105`. This directly violates the no-fake/mock/monkeypatch test policy and contradicts the static guard's asserted contract at `src/cadrumo/tests/test_monkeypatch_inventory.py:312-318`. The focused live gate `uv run pytest -q src/cadrumo/tests/test_monkeypatch_inventory.py::test_no_monkeypatch_fixture_or_context_usage` fails and reports all of those sites, so the harness currently advertises an enforced invariant that the checked-in suite does not satisfy.

### test-topology-config | low | Package conftest documentation still describes the retired naked-test topology

The package-wide fixture owner says `source_tree_ast` cannot move beneath the central tests harness because ratchets remain at `src/cadrumo/test_*.py` and elsewhere outside that subtree (`src/cadrumo/conftest.py:3-11`). The accepted topology has no such naked tests, and the executable topology gate at `src/cadrumo/tests/test_marker_integrity.py:1007-1025` now requires every test module to have a `tests` path segment. The current tree passes that gate (`test_test_modules_live_under_tests_directories_and_use_test_prefix`) and the mechanical inventory found all 2,915 `src/cadrumo` test modules under `tests/`. Keeping the obsolete rationale makes future fixture placement decisions depend on a topology that no longer exists; the fixture may still need package-root visibility, but that need must be justified against the actual distributed domain-local `tests/` subtrees.

### test-topology-config | high | The banned-import live-test guard reaches only the central tests subtree

The repo-root collection hook delegates only to the marker contract (`conftest.py:98-109`), while the banned-import scan is implemented exclusively by the child hook at `src/cadrumo/tests/conftest.py:139-164`. Pytest loads that child conftest only for tests in its own descendant subtree, yet live tests are deliberately domain-local outside it, including `src/cadrumo/application/live/tests/test_iva_wallet_live.py:35` and `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_live.py:31`; the current inventory finds 18 such `aeat_live` modules outside `src/cadrumo/tests/`. Consequently, those tests still receive the repo-root marker validation but bypass `_check_banned_live_imports`, so a prohibited fake/mock/network-interception import can be committed in a live AEAT test without the advertised collection-time hard exit. This is a harness safety-boundary gap, not a current banned-import hit.

### test-topology-config | medium | The central harness cohabits owner-specific tests with cross-cutting gates

`src/cadrumo/tests/__init__.py:1-16` declares that the package owns cross-cutting test plumbing, repo-meta tests, and fixture-bearing content, while behavior tests live beside their narrowest domain owner. The current contents do not consistently honor that boundary. `src/cadrumo/tests/test_cli.py:1-15` is named as a broad CLI test but imports and asserts only `core.i18n.DEFAULT_OUTPUT_LANGUAGE`, so both its filename and its `src/cadrumo/tests` placement obscure the actual `core.i18n` owner. `src/cadrumo/tests/test_output_language.py:1-76` explicitly exercises the application-profile/workflow stack and carries `hex_application`, yet it also remains in the package-global harness rather than the narrowest application-owned `tests/` subtree. These owner-specific modules cohabit with genuinely global inventory and collection gates, making the central folder an historical catch-all and weakening fixture visibility reasoning: a fixture placed there can appear globally authoritative merely because unrelated behavior tests accumulated beside it.

### test-runtime-performance | high | The implemented default worker cap contradicts the accepted worker-count decision

The accepted `2026-07-08-test-worker-count-policy-adr` explicitly chooses an operator-set native `PYTEST_XDIST_AUTO_NUM_WORKERS` cap and rejects any blanket repository default because the measured four-worker cap improved concurrent runs by about 10% but regressed a solo run by about 9%. Current code implements the rejected shape instead: `src/cadrumo/tests/_worker_count_hook.py` always returns `DEFAULT_WORKER_CAP = 6` when `CADRUMO_PYTEST_WORKERS` is absent or invalid, and states that this prevents pytest-xdist's native hook and `PYTEST_XDIST_AUTO_NUM_WORKERS` from participating. Repo-root `conftest.py` installs that hook for every `-n auto` invocation. No later worker-count ADR or supersession record was found by the exact search `rg -n -i "CADRUMO_PYTEST_WORKERS|project default|DEFAULT_WORKER_CAP|worker cap|test-worker-count" .vault -g "*.md"`; the only governing ADR remains accepted. The runtime policy may be defensible after later shared-host failures, but today it is an unrecorded reversal of a measured architecture decision, and direct CI pytest invocations silently inherit six workers unless they explicitly override `-n` or `CADRUMO_PYTEST_WORKERS`.

### test-runtime-performance | high | Unit meta-tests create nested xdist pools and dominate focused runtime

The default lane is itself xdist (`pyproject.toml` uses `-n auto --dist=loadfile`), but `src/cadrumo/tests/test_worker_count_hook.py` contains four unit tests that each boot another real pytest process with `-n auto` or an explicit count. A bounded sequential outer run, `uv run --no-sync pytest -q -n0 -o addopts='' --durations=10 src/cadrumo/tests/test_worker_count_hook.py src/cadrumo/tests/test_serial_marker_enforcement.py`, passed 18 tests in 59.70 seconds; the four worker-resolution subprocess cases consumed 35.57, 7.17, 7.09, and 6.32 seconds, while the two serial-marker subprocess controls consumed 1.54 and 0.72 seconds. The slowest case starts the project-default six-worker pool to execute one probe, and the explicit-override case starts eight workers (`DEFAULT_WORKER_CAP + 2`) to execute one probe. Under the normal outer six-worker lane those inner pools coexist with the outer workers and any sibling invocations, recreating the multiplicative process-pressure class the cap is intended to prevent. The real-hook proof is valuable, but enrolling all four fresh-process width probes as ordinary `unit` work makes harness self-verification a material runtime and host-contention cost.

### test-runtime-performance | medium | A unit meta-test recursively recollects the full repository test corpus

`src/cadrumo/tests/test_every_test_module_is_collectable.py::test_every_test_module_in_the_tree_is_collectable` is selected by the default unit lane and starts a child `pytest --collect-only -n0 --continue-on-collection-errors` across every discovered first-party test root. The child deliberately disables xdist, so the outer worker blocks while a second pytest process imports and collects the entire corpus serially. Current independent full-tree evidence in `2026-08-12-casilla-schema-s41-full-tree-collection-gate-review-audit` measured 32,280 collected tests in 74.78 seconds; this audit avoided duplicating that disruptive sweep. A bounded collection of the four harness modules, `uv run --no-sync pytest --collect-only -q -n0 -o addopts='' src/cadrumo/tests/test_worker_count_hook.py src/cadrumo/tests/test_serial_marker_enforcement.py src/cadrumo/tests/test_every_test_module_is_collectable.py src/cadrumo/tests/test_deselection_hook.py`, found 27 meta-tests in 0.20 seconds and confirmed this recursive collector remains a normal unit item. Collection integrity needs end-to-end proof, but paying a full second collection inside every unit campaign duplicates import-time setup and prevents the main pytest session's already-complete collection result from being reused.

### test-runtime-performance | low | Marker enforcement walks collected items twice for the central harness subtree

Repo-root `conftest.py` and `src/cadrumo/tests/conftest.py` both install `pytest_collection_modifyitems` delegates to `src/cadrumo/tests/_marker_hook.py::apply`; the helper documents that affected items may pass through twice and calls that safe. Safety does not make the work free: each pass walks every received item, materialises its inherited marker set, validates execution and hex markers, and checks serial status. The central child hook is still needed for its live-import scan, but re-running the repo-root taxonomy contract there has no distinct enforcement outcome. This is smaller than nested subprocess cost, yet it is deterministic collection overhead on a corpus independently measured at 32,280 items and an unnecessary second authority surface for ordering-sensitive collection behavior.

## Recommendations

- For `fixture-drift | medium`, nominate one conftest-visible canonical owner for the LLM encrypted-storage fixture and remove the duplicate definition. Preserve the existing function scope and real `isolated_runtime_profile` lifecycle; add a collection/fixture-visibility test covering both descendant trees so consolidation cannot silently leave either subtree without isolation.
- For `fixture-drift | high`, replace every module mutation with an explicit production seam or a real input/state variation that drives the same branch without replacing production symbols. Keep the existing inventory assertion fail-closed, rerun its positive controls, and require the focused inventory gate to pass before claiming the no-monkeypatch contract restored.
- For `test-topology-config | low`, rewrite `src/cadrumo/conftest.py`'s placement rationale to describe the real requirement: package-root visibility across distributed domain-local `tests/` subtrees. Add a small fixture-reachability assertion if package-root ownership remains necessary, so the reason is executable rather than tied to retired naked-test paths.
- For `test-topology-config | high`, move the banned-live-import enforcement to the repo-root collection surface (or delegate both root and child hooks to one idempotent shared enforcement function), then add a real subprocess collection test whose temporary topology contains an `aeat_live` module outside `src/cadrumo/tests/` with a banned import and proves collection exits non-zero. Also retain a clean domain-local live module control proving legitimate live tests still collect.
- For `test-topology-config | medium`, inventory every module under `src/cadrumo/tests` against the package's declared cross-cutting/meta/fixture boundary, move owner-specific behavior tests to the narrowest domain-local `tests/` subtree, and rename vague files such as `test_cli.py` to the behavior they prove. Keep genuinely cross-domain structural gates central. Add a static ownership gate based on declared hex owner plus imports only after the migration has established rules that can distinguish a cross-cutting gate from a misplaced behavior test without a hardcoded file allowlist.
- For `test-runtime-performance | high` (worker policy), author a follow-on ADR that explicitly chooses between the accepted operator-only native cap and the implemented project-default `CADRUMO_PYTEST_WORKERS` hook using fresh solo, CI, and concurrent-agent measurements. Then make the ADR status/supersession graph and the code agree; do not leave two environment variables with conflicting authority.
- For `test-runtime-performance | high` (nested worker pools), retain at least one real subprocess integration proof of hook ordering, but redesign the acceptance shape so routine unit execution does not start four independent xdist pools of up to eight workers. The follow-up should decide whether these are a dedicated serial harness lane, a consolidated subprocess scenario, or a lower-width proof paired with direct pure-logic cases; it must continue to test the installed hook rather than replace it with a fake.
- For `test-runtime-performance | medium`, move the full-corpus recursive collectability proof out of the ordinary unit lane into one authoritative collection/CI lane, or expose the main session's collection failures and non-vacuity tally without starting a second pytest. Preserve the current real subprocess mutation controls for malformed temporary modules in a bounded target; do not weaken the clean-collection invariant.
- For `test-runtime-performance | low`, keep the repo-root marker contract as the single taxonomy owner and have the child hook perform only the additional live-import work that is genuinely subtree-specific. Add a hook-call-count or real collection control proving each item receives one taxonomy validation and all intended live items still receive the import guard.
