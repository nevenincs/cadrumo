---
tags:
  - '#reference'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:88d50ba6dbc40b19c28d21f1eed6042a6765c676c3843e8802652673887da58d'
related:
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-06-10-cli-operator-surface-audit]]"
---

# `profile-requirement-grounding` reference: `profile requirement schema and its three consumer surfaces`

## Summary

The CLI already has a canonical schema linking a filing operation to its required taxpayer-profile fields (`ProfileSchemaDefinition`/`ProfileFieldDefinition`, with a `model_selectors` per-operation axis, `description`, and `legal_refs`), and it already backs three operator-facing surfaces. The defect is that the shared report-row model (`ProfilePreflightRequirement`) discards the `description`/`legal_refs` it has in scope, so every surface can only say WHAT path is missing, never WHY. A separate module (`_legal_zone.py`) already proves the fix (unioning schema + registry-binding grounding) is cheap, but its output has no render slot anywhere.

## Context

## Investigation summary

Five-iteration RAG-led code investigation (2026-08-08) into whether the CLI has a schema linking a tax operation to its required taxpayer-profile fields. Conclusion: the schema already exists and is already shared across three operator-facing consumers; the defect is narrower than "no schema" — the requirement row discards data it already has in scope.

## The canonical schema (already exists)

## Three consumers of the same requirement set

Rendered via the central error registry (`core/errors/registry/_application_part2.py:728-736`, code `REFUSED_MODELO_PROFILE_READINESS`) and locale template `application.modelo.errors.profile_readiness_missing` (`locales/en.yml:1048`): "Profile is incomplete for Modelo %{modelo} %{filing_year} %{period}; complete these profile facts first: %{missing}." — `%{missing}` is a raw comma-joined list of dotted schema paths. 2. **`aeat config profile preflight --modelo --filing-year --period [--revision-id]`** (`entrypoints/cli/_config/_profile_inspect.py`) — opt-in verb, same report, JSON payload `ProfilePreflightMissingPayload` (`entrypoints/cli/_config_payloads.py:544`) — same bare 3-field shape. 3. **`aeat app modelo readiness --modelo --revision-id --year --period`** (`entrypoints/cli/_modelo_readiness_cli.py`, via `state_projection.build_operator_state_projection`) — combines profile requirements (`ModeloReadinessMissingRequirementPayload`, `entrypoints/cli/_modelo_payloads.py:1097`, same bare 3 fields), calculation-binding requirements (`ModeloReadinessMissingBindingPayload`), and ledger issues as separate, un-unified sections.

## The reusable grounding-union source (already built, only used by the wizard)

`application/wizard/_legal_zone.py`'s `PageLegalZone` already unions this index's `legal_refs`/`source_refs` with the schema field's own `legal_refs`, for wizard setup-flow pages ONLY — and even there, its own docstring states the result has "no render slot today" in the flow substrate.

## Two other, disconnected profile-requirement mechanisms

- `ProfileKey` / `ProfileKeyRequirement` (`domain/contribuyente/_keys.py`) — flat, global REQUIRED/OPTIONAL (no per-operation axis) plus a conditional pair (`required_when_key`/`required_when_value`), human-labeled via `tr("profile.keys.*")`, compiled from `WIZARD_FLOWS` via `compile_profile_keys` (`application/wizard/_compiler.py`). **`ProfileSchemaDefinition` is loaded from an independently-authored bundled TOML, NOT compiled from `WIZARD_FLOWS`** — confirmed via `domain/user_profile/_loader.py`. These are two separately maintained sources describing overlapping facts (drift risk, not yet audited for actual divergence).
- `_DEADLINE_RELEVANT_FIELDS` (`application/overview/_explain.py:137`) — a private, ungoverned tuple of profile field names walked via `getattr`, single-purpose (deadline explanation), unrelated to either mechanism above.

## Prior related vault context

- `.vault/plan/2026-05-08-aeat-cli-hardening-plan.md` rows A12/A13/A15 (UX-006, unchecked `[ ]`) called for "per-modelo readiness matrix" and "completeness ratios" against the OLD `src/aeat/` package path (pre-`cadrumo` rename). The readiness verb and per-modelo behavior these rows wanted now exist in `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py` — but the rows remain unchecked with no exec record, so this reference does not claim them delivered; that reconciliation is out of this investigation's scope.
- `.vault/audit/2026-06-10-cli-operator-surface-audit.md` F8 (LOW) flagged the OLD `preflight --revision-id` as a required internal handle leaking to the operator — current `_profile_inspect.py` already makes `--revision-id` optional (resolves it when omitted), so this appears independently addressed; not verified further here.
- `.vault/adr/2026-07-23-profile-setup-flow-adr.md` — governs the paged wizard setup flow and profile-key bindings; relevant because `_legal_zone.py`'s unconsumed grounding computation lives in that flow's compile step.
