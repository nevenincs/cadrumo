---
tags:
  - "#adr"
  - "#multilang-externalization"
date: '2026-07-12'
related:
  - "[[2026-07-12-multilang-externalization-research]]"
supersedes:
modified: '2026-07-17'
body_hash: 'sha256:877e21a5e293636dfc3600970da5bddb281a1743a5c87a137697cd219969396d'
---

# `multilang-externalization` adr: `runtime localization authority and externalization boundary` | (**status:** `accepted`)

## Problem Statement

The 2026-05-04 phase-1 ADR correctly rejected inline multilingual value
payloads, but it also mandates deleting `core.i18n`, `Translatable`, and the
supported-language contract. Those latter instructions contradict the working
runtime: four YAML catalogues, the central renderer, and `Translatable` as the
typed abstract-key marker are the current authority. Treating the old
remediation list as live would remove the localization contract it was intended
to establish.

This ADR supersedes `2026-05-04-multilang-externalization-phase1-adr` in whole.
It preserves the valid externalization outcome while replacing its erroneous
teardown target with a precise runtime boundary.

## Considerations

- `src/cadrumo/locales/{es,en,ca,hu}.yml` is the canonical catalogue family.
- `tr` is the central runtime renderer. It resolves the active output language,
  loads YAML catalogues, and retains `python-i18n` initialization/fallback under
  the same boundary.
- `Translatable` is a strict string subtype that marks an abstract key; it is
  not an inline language-value dictionary or compatibility wrapper.
- The supported runtime languages are exactly Spanish, English, Catalan, and
  Hungarian. Their enum/constant is a live capability declaration, not a legacy
  multilingual payload.
- Documentation prose is not a runtime translation catalogue. It has its own
  authoring, review, and localization workflow.

## Considered options

1. **Delete the renderer and typed marker as phase 1 requires.** Rejected: it
   destroys the current externalized-key architecture and its coverage guards.
2. **Keep one YAML-backed runtime renderer and typed keys.** Accepted: runtime
   message ownership is central, inspectable, and compatible with all four
   supported output languages.
3. **Use runtime YAML keys to govern documentation prose.** Rejected: docs have
   different audience, lifecycle, and review requirements; coupling them to
   runtime message keys creates neither complete docs localization nor a clear
   runtime contract.

## Constraints

- Runtime translation values live only in the four YAML catalogues. A code path
  must not carry a language-indexed mapping, tuple, kwargs payload, or helper
  such as `t(es=..., en=..., ca=..., hu=...)` as its translation source.
- A runtime model, error payload, prompt descriptor, or CLI result that is
  intended for operator or taxpayer rendering carries a stable abstract key
  (`Translatable` where the type communicates that contract) and is rendered by
  `tr` at the presentation boundary.
- No locale-specific rendered user message is a domain/application authority or
  a persisted substitute for an abstract key. Interpolation values remain data,
  never embedded translations.
- Technical identifiers, source data, legal quotations, developer diagnostics,
  and non-user-facing log text are not translation payloads. They are outside
  this rule unless a caller projects them to an operator/taxpayer surface.
- A `tr` fallback may diagnose a missing key or keep a boundary readable; it
  must not become a second, inline locale catalogue or normal user-facing source
  of translated wording.
- Documentation changes remain outside the runtime catalogue boundary and must
  use the documentation workflow; prose in docs is not a locale-key exception
  or evidence of a runtime literal.

## Implementation

Runtime code stores and passes stable dotted keys. The YAML-first renderer
selects `es`, `en`, `ca`, or `hu` from the active output-language resolution,
interpolates data values, and uses the project-owned `python-i18n` backend only
through that central rendering boundary. `Translatable` remains the Pydantic
compatible marker for fields that intentionally carry such keys.

Locale scanners, catalogue coverage checks, placeholder-parity checks, and
typed-key contract tests govern the boundary. They must reject missing or
self-referential runtime translations and detect attempted reintroduction of
inline language-value payloads. A code owner adding an operator-facing runtime
message adds one key and all four YAML values through the locale authority; a
documentation owner follows the separate documentation lifecycle instead.

## Rationale

Externalization is about separating runtime message identity from language
values, not about eliminating the type that represents identity or the enum
that declares supported output languages. The central renderer and YAML
catalogues already deliver that separation. Narrowing the prohibition to inline
language payloads and local rendered user messages removes the actual
maintenance hazard without classifying working authority mechanisms as legacy.

## Consequences

- The phase-1 ADR's instructions to delete `core.i18n`, `Translatable`, and the
  language contract are retired; its 30 unchecked remediation rows are not safe
  implementation instructions.
- The four-catalogue runtime remains explicit and testable, but every new
  operator/taxpayer runtime message carries a catalogue-maintenance obligation.
- Documentation localization can evolve independently without weakening the
  runtime scanner or converting narrative prose into CLI/catalogue strings.
- Any additional output language or a different renderer requires a new ADR
  because it changes the runtime authority and coverage contract.
