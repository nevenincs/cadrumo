---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:6a2ca3679ac348487127dae4417c482c6cb4d691522b0f82948beeed9b23895d'
step_id: 'S191'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium re-root the supervisor declaration refusal onto the project error taxonomy and register it, since it was introduced rooting at a bare builtin while restoring guards that had failed open and is now the sole remaining violation of the unregistered-builtin-root gate, and an unregistered root escapes the registry that gives every refusal its code and its four-locale text

## Scope

- `src/cadrumo/application/operations/_execution_context.py and src/cadrumo/core/errors/registry/`

## Description

- Census every production `except` clause that could catch `OperationDeclarationError` before touching its base.
- Re-root the class onto the project error taxonomy, preserving `ValueError` ancestry.
- Register the class in the error-code registry, choosing an existing four-locale key where one is genuinely true, and reporting a new key otherwise.
- Prove the re-root bites from outside the tree: ancestry, registry resolution, and registry-withdrawal refusal.
- Re-run the exception-hygiene gate, the error-registry suites, and the operations package integration lane to confirm no regression.

## Outcome

**The catch-site census found no live trap, and `ValueError` was not load-bearing.** Only four files in the whole tree reference the symbol: the defining module, the package facade, and one test module, plus the two production catch sites in `_supervisor.py` (`start` and `_resume_from_checkpoint`). Both of those catch the class by its exact name (`except OperationDeclarationError: raise`) ahead of the blanket `except Exception` handler that settles ordinary executor failures — neither depends on it being a `ValueError`. No caller anywhere catches it via a bare `except ValueError`, `except Exception`, or a bare `except:`, and there is still no production consumer of `OperationSupervisor.start` to worry about. The census was therefore negative, but the negative still mattered: it cleared the way to change the base freely.

**Parent chosen: `CoreValidationError`.** The operations package carries no other exception class of its own, so there was no in-package sibling convention to follow. `CoreValidationError(CoreError, ValueError)` is the established cross-layer root for "this input or state violates an invariant" used throughout `application/`, `domain/`, and `adapters/` (dozens of sites, including the M303 and profile-custody classes re-rooted by the sibling row), and it fits this class's own meaning exactly: a declaration breach is a definition-contract invariant violated before any state mutation. Rooting there also preserves `ValueError` automatically through the MRO, so the change is `class OperationDeclarationError(ValueError):` to `class OperationDeclarationError(CoreValidationError):` plus one import, with no change to any raise site or catch site. Verified the resulting MRO directly: `OperationDeclarationError -> CoreValidationError -> CoreError -> CadrumoError -> ValueError -> Exception -> BaseException -> object`.

**Registration needed a new key.** Every `errors.internal.*`, `errors.error.*`, and `errors.refused.*` key already declared for a "not declared by its definition" / internal-contract-breach shape was searched (`declaracion`, `capabilit*`, `definition`, `contract`, `operation`, `internal_flow_validator_registry`, `internal_workflow_unhandled`, `cli_outbound_payload_boundary`, and others) and none was genuinely true of this condition: the closest generic internal-defect keys are each already one-to-one bound to a different specific class (workflow stage, guided-flow validator registry, CLI outbound payload), and reusing one would have made a wrong specific claim rather than a true general one. Registered against a new key instead of force-fitting: `code="INTERNAL_OPERATION_DECLARATION_BREACH"`, `category=ErrorCategory.INTERNAL`, `message_key="errors.internal.internal_operation_declaration_breach"`, `retryable=False`, `runbook_id=None`, added to `src/cadrumo/core/errors/registry/_application_part2.py`. The new key is reported to the campaign lead for locale coordination (see Notes) rather than hand-edited into any `.yml`, per ownership. Note that `resolve_error_message` prefers `error.args[0]` over the registry `message_key` whenever the exception carries a plain string message (which all four raise sites do), so the registered key's rendered text is a fallback for construction with no message, not the text an operator will usually see; it must still be genuinely true because the honesty gate and the fallback path both depend on it.

**Bite-proof, from outside the tree, four assertions:**
- Ancestry: `issubclass(OperationDeclarationError, CoreValidationError)` and `issubclass(OperationDeclarationError, ValueError)` both hold.
- Registration supplies the code: `get_registered_error_code(OperationDeclarationError).code == "INTERNAL_OPERATION_DECLARATION_BREACH"`.
- Withdrawal refuses: popping the class from the in-memory class-code cache and the declared-qualname mapping (monkeypatched on the live `core.errors._registry` module, restored in a `finally`) makes `get_registered_error_code` raise `ValueError` naming the missing declaration — proving the registration, not incidental class shape, is what supplies the code.
- Restoration is exact: resolving again after restoring the monkeypatch returns the identical `ErrorCode` as before withdrawal.

**The journal clause and the guard behaviour were verified through the production suite, not assumed.** The exact tests S175 wrote to pin this class's contract were re-run directly and all seven pass unchanged: the four-way parametrised `test_start_refuses_each_undeclared_executor_mutation_after_only_the_safe_started_transition` (undeclared phase, effect, resource family, interaction kind all still propagate `OperationDeclarationError` out of `start`), and the two `..._without_journal_mutation` tests in `test_executor_contract.py`, which assert byte-identical journal and lease state before and after the refusal. Re-rooting the base class changes nothing on the refusal path itself — the two `except OperationDeclarationError: raise` clauses match by exact type name regardless of ancestry, and no envelope is built anywhere on that path (envelope construction only happens at the CLI rendering boundary, never inside the supervisor's settle/journal-write path) — so no new write was introduced.

**Verification:**
- `src/cadrumo/core/errors/tests/test_exception_base_hygiene.py -m unit`: 7 passed. The unregistered-builtin-root violation list is now empty.
- `src/cadrumo/core/errors -m unit`: 54 passed.
- `src/cadrumo/application/operations -m integration -n0`: 56 passed, 0 failed (baseline maintained, no regression).
- The three declaration-guard tests named above, run directly: 7 passed (parametrised).
- Scoped Ruff check and Ruff format: both changed files clean. Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- The out-of-repo bite-proof script (ancestry, registration, withdrawal-refuses, restoration): all four assertions passed.

## Notes

**One new locale key needs coordination, reported here rather than hand-edited:** `errors.internal.internal_operation_declaration_breach`, four real values (not placeholders):

- en: `Internal error: an operation executor claimed a phase, effect, resource, or interaction its definition does not declare.`
- es: `Error interno: un ejecutor de operación reclamó una fase, un efecto, un recurso o una interacción que su definición no declara.`
- ca: `Error intern: un executor d'operació ha reclamat una fase, un efecte, un recurs o una interacció que la seva definició no declara.`
- hu: `Belső hiba: egy művelet-végrehajtó olyan fázist, hatást, erőforrást vagy interakciót igényelt, amelyet a definíciója nem deklarál.`

The `default_suggestion` / CLI-verb-recovery check named in the campaign brief does not apply here: `ErrorCode` has no suggestion field (it is a retired, test-enforced-forbidden field), and none of this class's four raise-site messages name a CLI verb.

No production code besides the two files in scope was touched. No commit, stage, stash, reset, or checkout was performed. The plan row was not checked, pending the locale key landing. The row can be marked complete once the four-locale key above is added by the locale-owning agent; the code and registry side of the row is done and independently verified.
