---
tags:
  - '#research'
  - '#cli-envelope-notice-standardisation'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-02-emit-envelope-schema-burndown-adr]]'
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-06-01-envelope-conformance-gate-adr]]'
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `cli-envelope-notice-standardisation` research: `CLI return-value, status, and notice standardisation`

## Question

The CLI `--json` contract migration (the `emit-envelope-schema-burndown`
feature) standardised the **success payload shape** but did not standardise
the **status, warning/failure modes, or the hints/lints/suggestions surface**.
Which operator-facing return surfaces are still non-uniform, what is the
complete blast radius, and what is the minimal contract change that makes
return commands, status, error reporting, and notices uniform across the whole
CLI?

## Findings

### F1. The success-envelope migration is already complete — that half is done

The `emit-envelope-schema-burndown` plan closed all 208 of 208 Steps. The
current CLI surface carries 231 `_emit_envelope` call sites and 209
`@register_schema` decorators, enforced by a **no-allowlist symmetric-diff
conformance gate** (`src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`,
`test_every_cli_leaf_has_a_registered_schema`): every CLI leaf must map to a
registered `OutputSchema`, and every registry key must map to a reachable leaf.
Only three documented `_emit` exemptions remain (help-prose, repair-report
passthrough). The prose in the original `json-output-contract` ADR and the
`aeat.core.json_contract` module docstring describing commands "still emitting
untyped payloads through bare `_emit`" is therefore **stale**: that migration
landed. The "comments/commands have not migrated" reading reflects the old
docstring, not the current tree.

### F2. The two envelopes are disjoint with no shared discriminator

Two unrelated shapes carry CLI results:

- **Success** (`SchemaEnvelope`, `src/aeat/core/json_contract.py`): fields
  `schema_version`, `command`, `result`, `warnings`. Emitted on stdout via
  `emit_json_success`.
- **Failure** (`ErrorEnvelope`, `src/aeat/core/errors/_registry.py`): fields
  `schema_version`, `code`, `category`, `message`, `suggestion`, `retryable`,
  `runbook_id`, `context`, `trace_id`. Emitted on stderr, wrapped under
  `{"error": {...}}`, via the error boundary in
  `src/aeat/entrypoints/cli/_errors.py` (`render_error_json`).

There is **no shared outer spine and no `status` field**. A machine consumer
cannot read one contract; it must branch on stdout-vs-stderr to learn whether a
command succeeded. The two `schema_version` fields are independent (both `"1"`)
with no coordinated versioning.

### F3. The success `warnings` channel is structurally dead

`SchemaEnvelope.warnings: list[str]` exists, but:

- `_emit_envelope(ctx, *, command, result, lines)` in
  `src/aeat/entrypoints/cli/_common.py` exposes **no `warnings` parameter** —
  the standard success helper cannot emit a warning at all.
- `emit_json_success` *does* accept `warnings=`, but a repository sweep finds
  **zero** call sites passing it. The channel is unreachable in practice.

"Warning mode" is consequently not a first-class envelope state. Non-fatal
diagnostics are instead smuggled inside individual `result` payloads (F4).

### F4. Advisories/warnings are modelled ad-hoc, per command, inside `result`

The domain already owns a severity-bearing diagnostic concept — `ModeloFinding`
with `WARNING` / `BLOCKING` severity, the `source_advisories` resolution
diagnostics, the RETMAR mandatory-filing warning, and the revision-stamp
advisory (`src/aeat/application/modelo/_verification*`,
`_calculation*`). The CLI projects these into **bespoke per-payload fields**
rather than a uniform channel:

- `authorization_advisory: str | None` and
  `source_advisories: tuple[SourceAdvisoryPayload, ...]` on the calculate
  result (`src/aeat/entrypoints/cli/_modelo_payloads.py:364-378`).
- `_work_calculate_source_advisory_output(...)` builds an advisory payload dict
  **and** a parallel set of text lines
  (`src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py:386-403`), so the
  same advisory is encoded twice in two shapes.
- The verify result carries `findings` inline; the obligation advisory is
  emitted as translated text lines
  (`_modelo_work_lifecycle_cli.py:343-355`).

Each command names its own advisory field, so there is no single place a
consumer reads "what non-blocking notices did this command raise".

### F5. Next-step hints/suggestions are non-uniform across success and error

- **Error side (structured, good):** `ErrorEnvelope.suggestion` (single
  copy-paste command), per-`ErrorCode` `default_suggestion`, and `runbook_id`.
  Command-resolution "did you mean" synonyms are a separate but structured
  surface (`src/aeat/entrypoints/cli/_command_suggestions.py`).
- **Success side (scattered):** next-step guidance is modelled as bespoke
  `next: str` payload fields (`src/aeat/entrypoints/cli/_config_payloads.py:499,509`),
  as workspace-state guidance text (`_overview.py` next-step helper), and as
  locale prose (`success.next_step`, `next_landing_command`,
  `next_modelo_work_command` in `src/aeat/locales/*.yml`). No typed channel
  unifies them.
- **No "lint" concept** exists on the success path at all; advisories (F4) are
  the closest analogue and are not surfaced uniformly.

### F6. A third, un-enveloped refusal shape still leaks

`_active_profile_or_exit` (`src/aeat/entrypoints/cli/_common.py:148-162`) emits
a raw `{"error": ..., "next": ...}` dict through the legacy `_emit` helper and
exits `2`, bypassing **both** `SchemaEnvelope` and `ErrorEnvelope`. It is not
caught by the bare-emit gate because `_common.py` is the module that defines
`_emit` (and is therefore excluded from the gate's file walk). This is a real
divergent operator-facing error surface with neither a `code`/`category` nor a
typed structure.

### F7. Exit codes are already centralised and uniform

`ExitCode` (`src/aeat/entrypoints/cli/_exit_codes.py`) and
`get_error_exit_code(category)` map one-to-one with `ErrorCategory`. The exit
vocabulary is sound and is **not** part of the gap — the new `status` field
should be derived from the same table so the JSON `status` and the shell exit
code never disagree.

## Blast-radius summary

| Surface | Count / location | State |
| --- | --- | --- |
| Success emit sites (`_emit_envelope`) | 231 across 54 CLI modules | migrated to `SchemaEnvelope`; will gain `status` + `notices` |
| Registered schemas (`@register_schema`) | 209 | complete |
| Dead `warnings` channel | `SchemaEnvelope.warnings`, 0 populators | to be replaced by typed `notices[]` + helper param |
| Ad-hoc advisory/hint fields in `result` | `source_advisories`, `authorization_advisory`, config `next:` (+ text-line twins) | to migrate onto `notices[]` |
| Error envelope | `ErrorEnvelope`, 1 boundary | to gain shared outer spine (`command`, `status`, `notices`) |
| Un-enveloped refusal | `_active_profile_or_exit` raw `{error,next}` | to route through the typed refusal path |
| Exit-code table | `ExitCode` + `get_error_exit_code` | sound; `status` derives from it |

## Recommendation

Standardise on a **shared outer spine** for both envelopes rather than
collapsing them:

- Both success and error documents carry `schema_version`, `command`,
  `status` (`success` | `warning` | `error`), and `notices: list[Notice]`.
- Success keeps `result`; error keeps `error: {code, category, message,
  suggestion, retryable, runbook_id, trace_id}`.
- Introduce one typed `Notice` model (`severity`, `code`, `message`,
  optional `suggestion`/`next`) as the single channel for warnings, advisories,
  and next-step hints, projected from the domain `ModeloFinding`/advisory types
  rather than re-modelled per command.
- `_emit_envelope` gains a `notices=` parameter and a derived `status`
  (`warning` when any notice is `WARNING`-severity, else `success`); the dead
  `SchemaEnvelope.warnings` list is removed.
- Extend the conformance gate to assert the outer spine and that no command
  re-introduces a bespoke advisory/next field outside the `notices` channel.
- Route `_active_profile_or_exit` through the typed refusal path so no
  un-enveloped error shape remains.

Migration follows the proven `emit-envelope-schema-burndown` pattern: one Step
per (payload-field removal + notice projection), text-mode output held
invariant per command, conformance gate green at each Step. This is the input
to the sibling ADR.
