---
tags:
  - '#audit'
  - '#workflow-cli-surface-swarm'
date: '2026-05-16'
modified: '2026-05-16'
related: []
---



# `workflow-cli-surface-swarm` audit: `Workflow and CLI surface data-loss audit`

## Scope

Audited the AEAT workflow engine (`src/aeat/application/workflow/`) and CLI emission surfaces (`src/aeat/entrypoints/cli/`) for data-loss risks across operator-facing transitions. Examined:

- Workflow state persistence and state transitions (LOADING_PROFILE → COMPUTING_DEADLINES → ... → DONE/ABORTED)
- WorkflowStep details field payload during state serialization
- Review record handling in WorkflowState (invoice_reviews, ledger_reviews)
- JSON envelope roundtrip boundaries via `emit_json_success` and `render_command_output`
- Type safety of CLI command payloads registered via `@register_schema`
- Workflow state load/save cycles through encrypted repository

## Findings

### 1. WorkflowState Accepts `dict[str, object]` in Review Record Fields — Data Loss on Serialization

**File**: `src/aeat/application/workflow/_models.py` lines 152–153  
**Issue**: The `WorkflowState` model declares `invoice_reviews` and `ledger_reviews` with union types that explicitly allow raw dicts:

```python
invoice_reviews: dict[str, InvoiceReviewRecord | dict[str, object]] = Field(default_factory=dict)
ledger_reviews: dict[str, LedgerReviewRecord | dict[str, object]] = Field(default_factory=dict)
```

**Data Loss Path**:
1. A raw `dict[str, object]` is stored in the state instead of the typed `InvoiceReviewRecord` or `LedgerReviewRecord`.
2. When `model_dump()` is called (line 103 in `_persistence.py`), the dict is passed through unchanged.
3. On reload, pydantic will attempt to coerce the dict back to the typed model, but any keys not in the model schema are lost under `extra="forbid"`.
4. If a dict contains extra fields beyond the typed model's schema, those fields are silently dropped on roundtrip.

**Evidence**: The `update_declaration_pointer` function (line 235) explicitly checks `if isinstance(current, dict)` and attempts recovery, signaling that this union pattern is known to occur in practice.

**Risk**: Unknown fields in persisted review records are lost; no audit trail of what was dropped.

---

### 2. WorkflowStep `details` Dict Keys Not Documented in WorkflowStepDetails Schema

**File**: `src/aeat/application/workflow/_engine.py` lines 525, 818, 855, 910–942  
**Issue**: WorkflowStep is constructed with details dicts containing keys that are not enumerated in the `WorkflowStepDetails` docstring:

- Line 525: `{"modelo", "period", "closes_on"}` when deadline check fails
- Line 818: `{"draft_id", "modelo", "period", "profile_tax_id", "schema_version"}` on draft mismatch
- Line 855: `{"error_count"}` on validation errors
- Lines 910–942: `{"provider_kind", "provider_operator_impact", "cert_not_after", "cert_severity", "cert_days_until_expiry"}` on certificate checks

**WorkflowStepDetails Schema** (`_models.py` lines 291–327) declares `extra="allow"` and implements `__getitem__`, `get`, and `items`, but the docstring (line 292–309) makes no mention of valid keys. The implementation is designed to accept arbitrary keys, but operators/tools consuming WorkflowResult have no documented contract for which keys may appear in which stages.

**Risk**: Tools reading WorkflowResult.steps cannot reliably parse or validate diagnostic details. Keys could be changed or dropped without detected breakage.

---

### 3. CLI Review Commands Emit Raw model_dump(mode="json") Without Registered Schema

**File**: `src/aeat/entrypoints/cli/_review.py` lines 33–36 and 51–63  
**Issue**: Both `review_queue` and `review_show` commands emit their payloads via:

```python
_emit(
    ctx,
    report.model_dump(mode="json"),  # <-- no @register_schema protection
    _queue_lines(report),
)
```

The `ReviewQueueReport` and `ReviewQueueRow` models are returned from application layer but are **not** registered with `@register_schema`. This means:

1. The JSON contract test suite cannot enumerate this command's schema.
2. Operators cannot rely on stable JSON output shape across releases.
3. A future change to the report shape (adding/removing/renaming fields) will be undetected.

**Evidence**: `src/aeat/entrypoints/cli/_modelo_payloads.py` shows 15+ registered schemas (lines 136+), but no equivalent in `_review.py`.

**Risk**: The review command's JSON output is opaque to downstream monitoring/audit tooling.

---

### 4. Plain Dict Emitted in _config/profile unset Command — No Type Validation

**File**: `src/aeat/entrypoints/cli/_config/__init__.py` line 392  
**Issue**: The `config profile unset` command emits a plain dict:

```python
_emit(ctx, {"key": key, "value": ""}, (f"{key}\t<unset>",))
```

This dict is not typed or registered. If the operator's parsing code expects a different shape (e.g., nested structure, different field names), the mismatch will cause silent failures in downstream tooling.

**Risk**: Low confidence in JSON shape; no validation against a schema.

---

### 5. WorkflowResult Serialization Does Not Round-Trip Tuples Through JSON Without Pydantic Re-Parse

**File**: `src/aeat/core/output_rendering.py` lines 73–88  
**Issue**: The `jsonable_output_payload` function converts tuples to lists (line 80):

```python
if isinstance(payload, list | tuple | set | frozenset):
    return [jsonable_output_payload(item) for item in payload]
```

When a CLI command calls `render_command_output` with JSON format, tuples are lost:

1. A command's OutputSchema may have tuple fields (e.g., `tuple[str, ...]` for operand_refs).
2. `jsonable_output_payload` converts them to lists for JSON.
3. The operator's tool receives JSON arrays where tuples are expected.
4. If the operator then reloads the JSON and expects a tuple field, pydantic coerces the list back, but the field is now a list in their local copy.

**Evidence**: The JSON envelope roundtrip test (`src/aeat/core/test_json_envelope_roundtrip.py` line 73–74) passes because pydantic `model_validate_json` automatically coerces lists back to tuples. However, tools that consume the raw JSON and reconstruct data without pydantic lose the tuple type.

**Risk**: Operators parsing raw JSON directly (not through pydantic) will receive lists instead of tuples; re-serializing those lists back to JSON and comparing with original will fail strict equality.

---

### 6. WorkflowStep.details Union Type Accepts dict[str, str] But Stores Non-String Values

**File**: `src/aeat/application/workflow/_models.py` line 348–351  
**Issue**: The WorkflowStep.details field is declared as:

```python
details: Annotated[
    WorkflowStepDetails | Mapping[str, str] | None,
    BeforeValidator(_coerce_workflow_step_details),
] = None
```

However, the engine constructs details dicts with non-string values:

- Line 855 in `_engine.py`: `{"error_count": str(len(error_findings))}` — explicitly stringified, OK
- Line 942 in `_engine.py`: `"cert_days_until_expiry": str(days_until_expiry)` — explicitly stringified, OK
- Line 818 in `_engine.py`: `"schema_version": ...` — conditionally stringified only if exception occurs

The union constraint `Mapping[str, str]` is documented but the WorkflowStepDetails model has `extra="allow"` and does not enforce string-only values. The `_coerce_workflow_step_details` validator (line 330–335) accepts dicts and converts them to WorkflowStepDetails via `model_validate(dict(value))`, which will accept non-string values because WorkflowStepDetails inherits from BaseModel and does not validate the value types.

**Risk**: Details may contain non-string values (Decimal, int, datetime) which serialize to JSON cleanly but fail re-validation if a strict schema is added later.

---

## Recommendations

1. **Replace `dict[str, object]` Unions in WorkflowState** — Promote `invoice_reviews` and `ledger_reviews` to accept only typed records or empty. If legacy data contains dicts, add an explicit migration function in the load path to coerce them to the proper type or reject with a clear error. This prevents silent field loss.

2. **Document WorkflowStepDetails Keys by Stage** — Add an enum or explicit dict of allowed keys keyed by `WorkflowStage`. Update the WorkflowStep validator to check `details` keys at construction time. This constrains the contract and makes tooling able to rely on known keys per stage.

3. **Register ReviewQueue Commands with @register_schema** — Create `ReviewQueueResult` and `ReviewItemResult` OutputSchema subclasses and decorate `review_queue` and `review_show` commands with `@register_schema`. Ensure the test suite enumerates the JSON contract.

4. **Replace Plain Dict in _config profile unset** — Define an explicit OutputSchema for the unset result (e.g., `ProfileUnsetResult`) and register it.

5. **Enforce `dict[str, str]` Constraint in WorkflowStepDetails** — Add a root validator to WorkflowStepDetails that asserts all values in `__pydantic_extra__` are strings. Reject construction if non-strings are passed.

6. **Audit All OutputSchema Fields** — Run the JSON envelope roundtrip test across all registered schemas to confirm tuple fields serialize and re-parse correctly under pydantic. Document any fields that are not round-tripped exactly (e.g., tuples → lists).
