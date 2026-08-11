---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:486810b4a331d628889f303047f8e9e7414186f21fd4ea262e027daebfae5fb1'
step_id: 'S94'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Update LLM action-envelope consumers and typed failure boundaries without retaining prose recovery authority.

## Scope

- `src/cadrumo/llm/tests/test_anthropic_optional_extra_boundary.py`
- `src/cadrumo/llm/tests/test_missing_llm_extra_refuses_instructively.py`
- `src/cadrumo/llm/tests/test_llm_vision_classifier.py`
- `src/cadrumo/application/ledger/tests/_llm_vision_evidence_support.py`

## Description

- Replace optional-extra import interception with a fresh core-only installed-product cohort built from committed artifacts; child processes remove `PYTHONPATH` and import real production consumers.
- Preserve the AST-derived guard inventory and assert every actual exported `require_optional_extra(LLM_EXTRA)` boundary returns the registered typed `MissingOptionalExtraError` identity rather than prose.
- Exercise both the adapter builder and Anthropic SDK loader in the core-only product process, then run the corresponding available-extra control in its own installed cohort.
- Update the local-vision loopback service to serve Ollama's current measured resident-set `GET /api/ps` contract as well as `POST /api/chat` through the real HTTP harness.
- For the named, catalogued vision model, inject only a typed hardware measurement derived from the catalogue requirement and configured margin; leave resident discovery live so the production contention authority reads `/api/ps` and decides admission.

## Outcome

- Both Anthropic dependency boundaries expose the same unchanged `MissingOptionalExtraError` machine identity and registered extra facts in a genuinely absent installed core product.
- Every discovered LLM-extra guard is exercised with a real production consumer, with no import finder, `find_spec`, `sys.modules` mutation, fake, mock, stub, patch, monkeypatch, skip, xfail, or message-content assertion.
- The named local-vision override sends the declared model to `/api/chat`, reads a measured-empty resident set from `/api/ps`, and obtains the production admission decision from the contention authority instead of this host's transient GPU state.
- S94 remains open for independent re-review.

## Notes

- `uv run pytest -m integration -n0 src/cadrumo/llm/tests/test_anthropic_optional_extra_boundary.py` passed: 1 test in 195.06 seconds.
- `uv run pytest -m integration -n0 src/cadrumo/llm/tests/test_missing_llm_extra_refuses_instructively.py` passed: 2 tests in 318.98 seconds.
- `uv run pytest -m unit -n0 src/cadrumo/llm/tests/test_llm_vision_classifier.py src/cadrumo/llm/tests/test_dispatch_load_headroom.py src/cadrumo/application/tests/test_provisioning_hardware_contention.py` passed: 52 tests in 33.66 seconds.
- Ruff formatting and lint pass for the owned S94 files. The cross-slice campaign still has the independent quiet-profile creation failure in `test_profile_bound_command_populates_active_profile_label`; it is outside this LLM/test-integrity scope.
## Coordinated rehoming reconciliation

After three identical read-only boundaries separated by at least sixty seconds, the canonical S50 migration wrote one 238-row postimage. The isolated target delta was exactly eight removals, four additions, and thirty-eight preserved target identities. The additions were exactly three `PurchaseInvoiceEvidenceInputError` fingerprints owned by S38 and one `LLMContentionError` fingerprint owned by S94; thirty-one separately recorded locator-only refreshes were incidental metadata.

The resulting ledger SHA-256 is `9de39139862dd9c4a057c981a3f9d47de401f37675616ed1745d3f254b0ce1e5`. Direct validation passed with `E_REHOMING_VALIDATED:238`, and all four target error families matched the live fingerprint multisets and declared owners exactly. The immediate no-write byte replay returned `E_REHOMING_MIGRATION_CHECK_CONTENT` after concurrent source movement; no second locator chase or write was performed. The complete 74-test lane finished with 71 passes and three externally concurrent failures: new Modelo error-family multiset drift in two tests and a source parse failure in `_action_resolution.py` in the owner-scope test.

This step remains open for independent review.
