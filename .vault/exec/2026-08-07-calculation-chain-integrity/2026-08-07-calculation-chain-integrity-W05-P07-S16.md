---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:50fb64fe5163842d28d387eda58037c9a18e9db75046303c87bcf90e8022b96f'
step_id: 'S16'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Classify each candidate-genuine suite failure as defect, environment artefact, or caused by this session's landings, with evidence

## Scope

- `src/cadrumo/`

## Description

- Checked out a pre-tonight baseline commit (`7fd2fa3034`, 2026-08-05 20:32, ~250 commits before the pinned full-suite SHA `8009be0181`) directly inside the disposable clone that produced the failing run, reusing its already-built venv, so the comparison environment matches the failing run exactly.
- Cleared `addopts` (`-o addopts=""`) on the baseline run after discovering the default marker filter silently deselected 44 of 71 requested node ids on the first attempt.
- Diffed the pinned-SHA failing set against the baseline failing set to separate pre-existing failures from failures caused by this session's landings.
- Read the exact assertion/traceback for every failure in the resulting genuinely-new set (21 items) plus the two clustered buckets (live-gated, installed-console), rather than classifying by filename pattern.

## Outcome

**Bucket 1 -- live-gated (34 tests), environment, confirmed by literal error text, not filename pattern**: every one fails with `Failed: selected live test requires CADRUMO_LIVE_TESTS_ENABLED=1` from `src/cadrumo/tests/live_gate.py:31`. This includes all 5 `test_renta_web_open_capture_replay.py` cases and `test_ledger_corpus_llm_classification.py`, both confirmed to hit the identical `requires_live_enabled()` call -- no sixth bucket exists.

**Bucket 2 -- installed-console (5 tests), genuine defect, caused by this session**: `test_root_help_shape.py`'s `--help` path constructs the full `Settings()` object (to resolve the locale-catalogue-cache path), which reaches `refuse_former_product_database` for a `tmp_path`-scoped synthetic legacy `aeat.db` the test deliberately plants, and (a) `--help` should never need database access, (b) the refusal leaks a raw Python traceback instead of the CLI's translated error boundary. Confirmed absent at the pre-tonight baseline.

**Pre-existing (confirmed identical at baseline)**: `test_codebase_size_budgets.py` (both), `test_docstring_core_struct_links.py` (both), `test_utf8_enrollment_inventory.py` (both), `test_cross_module_imports_resolve.py`, `test_inner_envelope_vacuity_invariants.py`, `test_inner_envelope_version_check_shape.py`, `test_storage_namespace_adoption.py`, `test_export_xml_dictionary_value_types.py`, `test_educational_docs_conformance.py`, plus one line-shift false positive corrected during triage (`test_every_text_writer_pins_its_terminator`'s `runner_queue_watchdog.py` finding moved line 282->301 by unrelated intervening edits, same call site, not a new violation).

**Genuinely new since baseline (21 items), individually confirmed via their real assertion text**:
- Trivial/mechanical (env-example doc entry, a stale exemption-list entry, four rationale-marker gaps across three AST gates, a missing `test_live_*` marker/banner, a registry/locale key-count ratchet, one shared `datetime.now(UTC)` site caught by two AST gates at once): `test_config.py`, `test_parsing_enrollment_inventory.py`, `test_cast_rationale_inventory.py`, `test_type_ignore_rationale_inventory.py`, `test_any_param_rationale_inventory.py`, `test_decimal_enrollment_inventory.py`, `test_no_broad_exception_raises.py`, `test_no_bare_wall_clock_reads_in_production` + `test_no_inline_datetime_now_utc` (one site, `application/invoices/_creation.py:443`), `test_filename_live_marker_lint.py`, `test_registry_locale_key_parity.py`.
- Self-caused, owned honestly: `test_no_fake_stub_or_dummy_definitions` flags `_FakePage` in this session's own `test_pre303_alert_modal_divergence.py:131` (the alert-modal collapse work) -- a banned-prefix naming violation on an otherwise real-behaviour-driven test double, missed during that work's own mutation-proof pass. `test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata` flags a second, different campaign-metadata comment (`test_source_resolver.py:1058`, "P01.S31") in a file this session already touched once for the same violation class.
- A real, undecided cross-cutting defect: `test_exception_base_hygiene.py` flags a new exception class not deriving from `CadrumoError` with no stated rationale -- a domain call, not made here.
- The headline finding: all 4 `test_ledger_evidence_extract_cli.py` failures share one root cause -- a pydantic `extra_forbidden` ValidationError on exactly four fields (`recargo_amount`, `lines`, `iva_breakdown`, `iva_category`) every time, reading as a real regression from this session's ledger-invoice-decomposition work (a model shape tightened; a caller or fixture still constructs the old flat shape). Not fixed here -- needs a read of the governing ADR or a domain call on which side changed.

## Verification

```
cd clean_clone/repo && git checkout 7fd2fa3034c48a07ce2dea621be521eae69927c7
.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider -o addopts= <71 pinned-failing node ids>
50 failed, 21 passed in 151.91s (0:02:31)
```
Diffed against the pinned run's `71 failed, 24354 passed` failure list (`comm -23`/`comm -12` on sorted node-id sets) to produce the genuinely-new 21-item set and the pre-existing set reported above.

## Notes

Not individually re-verified: whether each "pre-existing" test's inner assertion text is byte-identical between the two runs, only that the same test id still fails in both -- a small chance exists one of these changed shape without changing pass/fail status. Stated as a limit, not resolved as certainty.

Fixes NOT applied in this step: the trivial/mechanical items, the two self-caused items, the exception-hygiene base-class question, and the ledger-evidence-extract-cli regression are all reported to the plan owner rather than fixed here, since several need a domain call this step's scope did not authorise making unilaterally. Tracking/fixing them is not yet assigned to a specific plan row as of this record.
