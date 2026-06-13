---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave13-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
---

# `secure-persistence-foundation` adr: wave-13 repository-id validator consolidation | (**status:** `accepted`)

## Problem Statement

Five repository modules across the `submission`, `filing`, and `justificante` domains carry byte-identical (modulo parameter name) "validate this id is safe to compose into a path" helpers. The duplication is benign today but each instance is its own potential drift point — a future hardening could land in one repository and silently miss the other four.

The upstream-reconciliation audit recorded this as a deferred code-quality refactor with no security impact. Per the user's "no deferring" directive it lands in this PR.

## Considerations

Surveyed in the wave-13 research artefact:

- **Five identical validators**: `_validate_submission_id`, `_validate_draft_id`, `_validate_amendment_id`, `_validate_csv` (justificante), `_validate_modelo` (filing-history).
- **Three checks per validator**: non-empty, no path separators (`/` or `\`), no dot-tokens (`.`, `..`, dot-prefix).
- **Existing test surface**: five tests catch `ValueError`. `PathContainmentError` inherits from `ValueError`, so the inheritance chain keeps every test passing without churn.
- **Substrate already houses path-safety helpers** at `aeat.adapters.persistence.storage._path_safety` (`safe_subpath`, `safe_record_path`). The new `safe_repository_id` is a natural sibling.
- **Domain-specific validators stay**: `_validate_run_id` (regex hex), `_validate_casilla_id`, `_validate_category_id`, `_validate_invoice_id_shape`, `_validate_optional_ids`. These have different semantics and are not consolidatable.

## Constraints

- **Pydantic v2 strict-frozen elsewhere**: this consolidation does not touch any pydantic record; it's a free-function helper.
- **No backwards-compatibility shims**: per the no-legacy directive, the five `_validate_*` functions are removed (not retained as deprecation wrappers). The call sites are updated in the same commit.
- **Error-message stability**: the helper's `context` parameter mirrors the current per-validator messages. Tests asserting on `match="path separator"` continue to match.
- **Typed error class**: the new helper raises `PathContainmentError`, the registered substrate-error class. Callers that previously raised raw `ValueError` now raise the typed class — non-breaking because of the multi-inheritance.

## Implementation

Three phases. All land in this PR.

### Phase 1 — Substrate: `safe_repository_id`

In `src/aeat/adapters/persistence/storage/_path_safety.py`:

```python
def safe_repository_id(token: str, *, context: str) -> str:
    """Reject repository-id tokens that would compose into an unsafe filename.

    Repositories store records as ``<store_dir>/<token>.envelope.json``.
    A token containing a path separator, a dot-prefix, or one of the
    relative-path tokens (``"."``, ``".."``) would either escape the
    store dir or shadow a hidden file. This helper performs the
    early-rejection layer; the substrate's path-resolution helpers
    enforce containment downstream.

    Args:
        token: The free-string id supplied by the repository caller.
        context: Stable label (e.g. ``"submission_id"``) embedded in
            the error message. Lets the failure-mode message remain
            byte-identical to the per-domain validators it replaces.

    Returns:
        ``token`` unchanged. Returning the validated value lets the
        helper appear inline (``record_id = safe_repository_id(...)``).

    Raises:
        PathContainmentError: When ``token`` is empty, contains a path
            separator, is a dot token, or starts with a dot.
    """
    if not token:
        raise PathContainmentError(f"{context} must be non-empty")
    if "/" in token or "\\" in token:
        raise PathContainmentError(
            f"{context} must not contain path separators: {token!r}",
        )
    if token in {".", ".."} or token.startswith("."):
        raise PathContainmentError(
            f"{context} must not be a relative-path token: {token!r}",
        )
    return token
```

Add to `__all__` of `_path_safety.py` and re-export through `aeat.adapters.persistence.storage.__init__.py` (alongside `safe_record_path`, `safe_subpath`).

### Phase 2 — Repositories: collapse the five validators

In each of the five repository modules:

- Delete the local `_validate_<token>` function definition.
- Replace the call sites (`_validate_<token>(token)`) with `safe_repository_id(token, context="<token>")`.

The 5 modules and their call counts:

| Module | Function deleted | Call sites |
| --- | --- | --- |
| `submission/_repository.py` | `_validate_submission_id` | 2 |
| `filing/_repository.py` | `_validate_draft_id` | 2 |
| `filing/_complementaria_repository.py` | `_validate_amendment_id` | 2 |
| `filing/_history_repository.py` | `_validate_modelo` | 4 |
| `justificante/_repository.py` | `_validate_csv` | 2 |

12 call sites in total updated.

### Phase 3 — Tests: substrate coverage + regression sweep

Substrate level (in `src/aeat/adapters/persistence/storage/_test_path_safety.py`, extending the existing tests):

- `test_safe_repository_id_returns_clean_token`: happy path.
- `test_safe_repository_id_rejects_empty`: empty string → `PathContainmentError`.
- `test_safe_repository_id_rejects_path_separator`: `"foo/bar"` and `"foo\\bar"` → `PathContainmentError`.
- `test_safe_repository_id_rejects_dot_token`: `"."`, `".."` → `PathContainmentError`.
- `test_safe_repository_id_rejects_dot_prefix`: `".hidden"` → `PathContainmentError`.
- `test_safe_repository_id_error_uses_context_label`: `match="submission_id must"` for `context="submission_id"`.
- `test_safe_repository_id_failure_inherits_value_error`: `assert issubclass(PathContainmentError, ValueError)` — explicit canary so future refactors cannot break the legacy `except ValueError` catchers.

Regression sweep: run the five domain test suites and confirm the existing `pytest.raises(ValueError)` tests continue to pass.

### Phase 4 — Code review request + audit gate

Per the standing "review requests are part of every wave" directive: after the wave-13 commit lands, request fresh `@gemini` + `@codex` reviews on PR #441, then write the wave-13 audit-gate report.

## Rationale

**Why a substrate helper, not a per-domain pattern.** The shared shape (non-empty + no path separators + no dot tokens) is a property of "anything composed into a filename", not a property of any single domain. The substrate's `_path_safety` module is the natural home — it already houses the two related path-containment helpers.

**Why `PathContainmentError` and not a fresh class.** The existing `PathContainmentError` is registered in the trilingual error registry as `INTEGRITY_STORAGE_PATH_CONTAINMENT`. The five validators were raising raw `ValueError` — strictly weaker; consolidation upgrades them to a typed, registry-coded error without any caller change because of the `ValueError` multi-inheritance.

**Why keep the `context` parameter.** Two reasons: (1) the per-domain error messages are observable in operator runbooks and existing test `match=` strings; preserving them is non-negotiable; (2) the alternative — generic `"id must not contain path separators"` — loses the field name that operators use to find the offending record.

**Why not move onto pydantic field validators.** Five repositories accept the id as a free-string parameter to public methods (`get(submission_id)`, `delete(draft_id)`, etc.). The validator runs at the method-call boundary, not the record-construction boundary. Fitting it onto a pydantic record would require constructing a wrapper for every call site — net code increase.

## Consequences

**Twenty-plus lines of duplicated code deleted**, replaced by one substrate helper + per-call-site `context=` keyword. Every future hardening (e.g. blocking control characters, length cap) lands in one place.

**Failure-class drift closed.** Five raw `ValueError`s become five typed `PathContainmentError`s, picking up the registered error code (`INTEGRITY_STORAGE_PATH_CONTAINMENT`) and trilingual message coverage that the rest of the substrate already enjoys.

**No operator-facing change.** Error messages are byte-identical (modulo the typed class). Test suite passes without modification (the inheritance chain keeps `pytest.raises(ValueError)` working).

**Pattern available for future repositories.** Wave-N repositories that compose `<store_dir>/<token>.envelope.json` paths now have a one-liner — `safe_repository_id(token, context="X")` — instead of copy-pasting five lines.
