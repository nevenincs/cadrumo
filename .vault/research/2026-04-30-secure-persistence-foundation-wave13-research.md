---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-audit]]"
---

# `secure-persistence-foundation` research: wave-13 repository-id validator consolidation

Research foundation for the wave-13 ADR. Catalogues five byte-identical (modulo parameter name) repository-id validators across the per-domain repositories, evaluates whether to consolidate them, and frames the substrate-level helper that closes the duplication.

## Background

The upstream-reconciliation audit recorded as a deferred item:

> `_validate_*_id` consolidation. Each repository has its own near-identical id validator. Pure code-quality refactor; no security impact.

A cross-codebase grep against the wave-12 HEAD reveals the precise consolidation surface:

| File | Function | Param |
| --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/export/_repository.py` | `_validate_submission_id` | `submission_id` |
| `src/aeat/application/filing/_repository.py` | `_validate_draft_id` | `draft_id` |
| `src/aeat/application/filing/_complementaria_repository.py` | `_validate_amendment_id` | `amendment_id` |
| `src/aeat/domain/justificante/_repository.py` | `_validate_csv` | `csv` |
| `src/aeat/application/filing/_history_repository.py` | `_validate_modelo` | `modelo` |

All five share the identical body (the parameter name and the `_id` suffix in error messages are the only differences):

```python
def _validate_<token>(<token>: str) -> None:
    if not <token>:
        raise ValueError("<token> must be non-empty")
    if "/" in <token> or "\\" in <token>:
        raise ValueError(f"<token> must not contain path separators: {<token>!r}")
    if <token> in {".", ".."} or <token>.startswith("."):
        raise ValueError(f"<token> must not be a relative-path token: {<token>!r}")
```

Catalogued **out of scope** (different rules, not consolidatable):

- `_validate_run_id` (observability) — regex `^[0-9a-f]{16}$` for run-trace ids.
- `_validate_casilla_id` (×2 in schema) — domain-specific casilla format.
- `_validate_category_id` (×2 in financial/{transactions,invoices}) — domain-specific category-id format.
- `_validate_invoice_id_shape` — domain-specific invoice id shape.
- `_validate_optional_ids` — multi-id batch validator.
- `_validate_modelo` in `schema/_models.py:425` — different shape (model-name field validator), happens to share the function name.

## Investigation findings

### F1 — The five callers all compose `<store_dir>/<token>.envelope.json`

All five validators are called immediately before composing a path of the form `<store_dir>/<token>.envelope.json` (or similar). The validation prevents:

- Empty tokens that would compose to `<store_dir>/.envelope.json` (a hidden file shadowing).
- Path-separator tokens (`/`, `\`) that would escape `<store_dir>`.
- Dot-tokens (`.`, `..`) that would resolve to the store dir or its parent.
- Dot-prefix tokens that would create hidden files (`.foo.envelope.json`).

This is **belt-and-braces** validation: the substrate's `safe_record_path` (and `aeat.core.paths.resolve_record_json_path`) already enforce path containment downstream. The repository-level validator is an early-rejection layer so the failure mode is a clean `ValueError` at the API boundary rather than a deeper path-resolution exception.

### F2 — Consolidation target: `aeat.adapters.persistence.storage._path_safety`

The substrate already houses two path-safety helpers in `_path_safety.py`:

- `safe_subpath(root, relative_path, *, context)` — wraps `resolve_relative_subpath`.
- `safe_record_path(root, record_id, *, context)` — wraps `resolve_record_json_path`.

A natural sibling: `safe_repository_id(token, *, context)` — performs the early-rejection checks the five validators duplicate, raising `PathContainmentError` with a stable message. The `context` parameter labels the field name in the error message ("submission_id", "draft_id", etc.).

`PathContainmentError` already inherits from `ValueError`, so existing test surface that catches `ValueError` keeps working without churn:

```python
class PathContainmentError(PersistenceError, ValueError):
    """Raised when a computed path escapes its configured root directory.

    Inherits from :class:`ValueError` as well as :class:`PersistenceError` so
    legacy call-sites that catch ``ValueError`` from the path helpers in
    :mod:`aeat.core.paths` continue to work; new code should catch the
    typed :class:`PathContainmentError` instead.
    """
```

### F3 — Existing tests catch `ValueError` (not the typed class)

A grep across the five domain test files reveals 5 tests that exercise the validators directly with `pytest.raises(ValueError)`. These all pass through the `ValueError`-inheritance chain and require **no change** to keep working:

- `src/aeat/application/filing/_test_repository.py:200` (draft_id)
- `src/aeat/application/filing/_test_history_repository.py:163` (modelo)
- `src/aeat/application/filing/_test_complementaria_repository.py:182` (amendment_id)
- `src/aeat/adapters/outbound/aeat/export/_test_repository.py:192` (submission_id)
- `src/aeat/domain/justificante/_test_repository.py:168` (csv)

Total existing-test surface preserved; consolidation is non-breaking.

### F4 — Consolidation does not introduce a coupling regression

The five repositories already import from `aeat.adapters.persistence.storage` (the substrate's public surface). Adding `safe_repository_id` to `aeat.adapters.persistence.storage`'s `__all__` and importing it from each repository reuses the existing dependency edge. No new cross-module dependency edge is introduced.

The `aeat.core.observability._validate_run_id` and `aeat.domain.schema._validate_casilla_id` validators are kept domain-local because their rules are not the simple path-token shape — they would over-fit `safe_repository_id` if folded in.

### F5 — Error message stability vs. the new `context` parameter

Current messages:

```
submission_id must not contain path separators: 'foo/bar'
submission_id must not be a relative-path token: '..'
submission_id must be non-empty
```

After consolidation, the helper produces:

```
{context} must not contain path separators: 'foo/bar'
{context} must not be a relative-path token: '..'
{context} must be non-empty
```

The five callers pass `context="submission_id"`, `context="draft_id"`, etc., so the messages are byte-identical to the current state (modulo the typed-error class). Test surface that asserts on `match="path separator"` continues to match.

### F6 — Alternative shapes considered

**Inline lambda / partial.** Replace each validator with a `partial(safe_repository_id, context="...")`. Rejected — adds a level of indirection without removing the call-site duplication; the per-call `context=` is already minimal.

**Field validator on a pydantic record.** Move the shape check onto the record models' fields. Rejected — five repositories pass the id as a free-string parameter to public methods (`get(submission_id)`, `delete(draft_id)`, etc.). The validator runs at the **method-call boundary**, not the record-construction boundary. Fitting it onto a pydantic record would require constructing a wrapper for every call site.

**Regex-based allow-list.** Replace the three checks with a single regex like `^[A-Za-z0-9_\-]+$`. Rejected — the current callers' tokens have different alphabets (e.g. AEAT CSV is alphanumeric 4-64 chars; submission_id can be UUIDs with hyphens; modelo is short numeric like `100`/`130`/`303`). Centralising onto a single regex would over-constrain.

The existing three-check shape (non-empty + no path separators + no dot tokens) is the right semantic: it's the **smallest set that prevents path-containment escape** without claiming knowledge of the domain-specific id alphabet.

## Recommendation

Author the wave-13 ADR with the **substrate-helper** shape (F2). One `safe_repository_id` function in `aeat.adapters.persistence.storage._path_safety`, exported through the `aeat.adapters.persistence.storage` public surface, called from all five repositories, raising the existing `PathContainmentError` (which already inherits from `ValueError`).

Five lines of body × 5 callers = 25 lines deleted, replaced by one helper + 5 single-line call sites. Pure code-quality refactor with zero security regression and zero existing-test surface churn.
