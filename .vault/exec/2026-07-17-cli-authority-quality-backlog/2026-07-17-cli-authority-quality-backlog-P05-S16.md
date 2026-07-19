---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S16'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Route classify --auto-split and split --llm through the typed review workflow with distinct invocation origins and remove CLI-owned review branching and application source-command defaults

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`

## Description

- Route the persisting ledger LLM decision terminals in `_ledger_llm_cli.py` through `execute_reviewed_decision`, each with its distinct `LlmReviewInvocationOrigin`: classify --llm --apply (CLASSIFY_LLM_APPLY), classify --llm --saturate --apply (CLASSIFY_LLM_SATURATE_APPLY), the classify/saturate/auto-split --reject terminals (CLASSIFY_LLM_REJECT), and the auto-split apply (CLASSIFY_AUTO_SPLIT).
- Route the `ledger split --llm` apply terminal in `_ledger_lifecycle_cli.py` through `execute_reviewed_decision` with the SPLIT_LLM origin.
- Delete the CLI-owned primitive dispatch and the CLI-passed `source_command` literal (`apply_llm_classification(..., source_command="aeat app ledger classify --llm --apply")`); the durable audit label now derives from the origin inside the workflow.
- Add an `origin` parameter to the shared `emit_llm_rejection` helper so each reject route names its origin.
- Promote the workflow symbols (`execute_reviewed_decision`, `LlmReviewInvocationOrigin`, `LlmReviewDecision`, `LlmReviewRequest`, `LlmReviewResult`, `ReviewedSuggestion`) through the `application.ledger` public facade so the entrypoints package imports them from the top-level `__all__`.
- Narrow each `execute_reviewed_decision` return through an `isinstance` assertion at the call site to keep ty and pyright green.

## Outcome

- Behaviour-preserving for the operator: the envelope shape, notices, text lines, and exit codes are identical. The only durable change is the non-operator-facing `source_command` audit label for the auto-split route (now `aeat app ledger classify --read-evidence --auto-split --apply`) and the split --llm route (now `aeat app ledger split --llm`), each corrected to its origin-derived spelling.
- Modified files: `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`, `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py`, `src/cadrumo/application/ledger/__init__.py`.
- Gates green: `just check-types` (ty + pyright), import-linter (layered contracts), ruff, JSON-schema/envelope conformance, CLI-surface and ledger-lifecycle-surface manifests, the operator rule-surface drift gate, documented-command conformance for the ledger surface, and the ledger LLM CLI behaviour tests (43 passed). Committed as `cca4371e33`.

## Notes

- Scope: the plan pins S16 to `_ledger_llm_cli.py` (and the `split --llm` sibling in `_ledger_lifecycle_cli.py`). "Remove application source-command defaults" was executed as removing the CLI's reliance on the source-command literal (the origin now derives it). The `source_command: str = "aeat app ..."` DEFAULT parameters on the four composed primitives in `_llm_classification.py` are out of this step's declared file scope and were deliberately left intact: they remain the canonical-API convenience for ~19 direct unit-test callers, and `execute_reviewed_decision` never reaches a default because it always passes the origin-derived spelling. Making them required is a mechanical, behaviour-neutral follow-up (touching 6 peer-owned test files) that a future step can take if the stricter reading is wanted.
- The no-split in-place apply (`apply_evidence_classification`) and the operator-iva derivation (`derive_operator_iva_substrate`) are NOT composed by `execute_reviewed_decision` (the workflow has no in-place-classify or operator-iva terminal), so those two CLI routes retain their direct primitive calls. This is not parallel decision logic — each is a single terminal the workflow does not own.
- Full-tree conformance had two RED gates that are owner-external (the operator's live config-door P04/all-profile-reset work, per the SAFETY header): documented-command conformance fails on `docs/_sequences/.../protect-data-access-rekey.seq` citing a removed `aeat config rekey`, and operator-surface-contract-drift fails on `config reset` sub-verbs. Neither touches the ledger surface; both trace to peer working-tree WIP in `_custody_secret.py` / `_config_payloads.py` and the all-profile-reset plan.
- The shared index held 7 foreign staged persona files at commit time; used an explicit-pathspec commit for the three authored files so the foreign staged work was neither swept nor disturbed.
