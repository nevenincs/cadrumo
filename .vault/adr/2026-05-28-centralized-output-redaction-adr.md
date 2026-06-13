---
tags:
  - '#adr'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-centralized-output-redaction-research]]'
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
  - '[[2026-05-27-secure-storage-repair-profile-privacy-review-audit]]'
---

# `centralized-output-redaction` adr: `centralize CLI output redaction at the rendering boundary` | (**status:** `accepted`)

## Problem Statement

The project has central log, error, and observability redaction primitives, but CLI success output is not enrolled through a central redaction boundary. `_emit` and `_emit_envelope` route almost all operator-facing output through shared helpers, yet `render_command_output` only serializes payloads or joins text lines. Commands that emit profile ids, bucket ids, active-profile values, object-key hints, tax identifiers, URLs, tokens, certificates, session metadata, or passphrases must currently remember to redact locally.

That design is brittle. The `config repair profile` privacy defect proved that command-local redaction does not scale across the codebase.

## Considerations

The research found:

- 198 `_emit` call sites and 12 `_emit_envelope` call sites under production CLI/diagnostics code.
- 13 direct `typer.echo` call sites in production CLI/diagnostics code.
- Separate redaction mechanisms in `core.logging`, `core.errors._registry`, `core.redaction`, observability, auth diagnostics, and repair/profile commands.
- Centralized logging redaction is stronger than centralized CLI output redaction.

The architecture must preserve existing output contracts while making privacy the default:

- JSON output must remain valid JSON and maintain command schema shape.
- Text output must remain human-readable and localized where strings are user-facing.
- Diagnostic engineers may still need stable row/object correlation, but not raw secret or identity values.
- Commands that intentionally expose an operator-facing display label must distinguish that label from raw profile/bucket UUIDs.
- Tests must use real CLI behavior, not tautological helper-only assertions.

## Constraints

- The shared worktree is active; rollout must be stepwise and path-scoped.
- Some CLI outputs intentionally expose non-secret business data. The central policy must be configurable by output classification, not a blanket string replacement that destroys useful output.
- Error rendering and logging already have tests and public behavior; migration must preserve their semantics while removing duplicated sensitive-key logic.
- Direct `typer.echo` remains allowed only for explicitly audited non-sensitive paths or temporary diagnostics moved behind a plan row.

## Implementation

The accepted architecture is:

1. `src/aeat/core/redaction/__init__.py` owns the canonical redaction rule registry and structured redaction helpers.
2. `src/aeat/core/output_rendering.py` becomes the central success-output privacy boundary. It redacts JSON payloads and text lines before serialization or printing.
3. `src/aeat/entrypoints/cli/_common.py` routes `_emit` and `_emit_envelope` through the central output renderer. Any command bypassing `_emit` must have an explicit test-covered exception.
4. `src/aeat/core/errors/_registry.py` and `src/aeat/core/logging.py` stop carrying independent sensitive-key taxonomies. They compose shared redaction rules and keep only transport-specific formatting behavior.
5. Bespoke auth, repair, diagnostics, and profile redactors are deleted or reduced to domain-specific shaping helpers that call the central policy.
6. A mechanical inventory test guards production CLI output call sites so new `typer.echo`, direct writes, or unclassified `_emit` payloads cannot appear without an owning plan row.

The central output policy must include first-class handling for:

- profile id and bucket id values;
- active-profile values when they are raw ids rather than display labels;
- secure-object object keys and lookup-key hints;
- NIF, NIE, CIF, and profile tax identifiers;
- tokens, cookies, authorization headers, session secrets, passphrases, API keys, and certificate passwords;
- URL path/query redaction while retaining useful host-level diagnostics.

## Rationale

The rendering boundary is the right enforcement point because it is already the shared choke point for the majority of CLI success output. Enrolling `_emit`, `_emit_envelope`, and JSON-contract emission there avoids relying on every command author to remember privacy policy details. Keeping rule ownership in `core.redaction` prevents a fourth sensitive-key taxonomy and gives logging, error rendering, observability, and CLI output one vocabulary.

Command-local redaction is still permitted only for domain shaping that changes meaning before rendering, such as replacing a captured HTML body with a length-only diagnostic. It must not be used as the primary privacy boundary.

## Consequences

The migration has broad blast radius:

- Core output and redaction tests must change first.
- CLI JSON/text tests may need expectation updates where raw ids become placeholders or digests.
- Some repair and diagnostics tests must assert central redaction rather than command-local helper behavior.
- Direct diagnostics `typer.echo` surfaces must either move behind `_emit` or receive explicit exception coverage.
- API docs for redaction and output rendering must be updated after code lands.

The positive consequence is a simpler security model: operator output, JSON output, errors, logs, and observability all derive privacy behavior from one redaction subsystem, with transport-specific formatting at the edge.
