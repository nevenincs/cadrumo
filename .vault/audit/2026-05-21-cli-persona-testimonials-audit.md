---
tags:
  - '#audit'
  - '#cli-persona-testimonials'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-cli-persona-testimonials-plan]]"
---



# `cli-persona-testimonials` audit: `errorcode-message-key-translation-gap`

## Scope


## Findings


## Recommendations



## Context

## Scope

Task #522 — "aeat.locales scaffold/audit blind to ErrorCode
message_keys". Investigation outcome and the scope decision it forced.

## Finding

The `aeat.locales` AST scanner (`_ast_scanner.py`) collects
`message_key=` / `translated_message=` translation keys only from
callees whose name ends in `Error`/`Exception` or is `__init__`. The
error registry declares every `ErrorCode` with a
`message_key="errors.{category}.{code}"` literal, e.g.

```python
ErrorCode(
    code="REFUSED_TOPIC_NOT_FOUND",
    category=ErrorCategory.REFUSED,
    message_key="errors.refused.refused_topic_not_found",
    ...
)
```

The callee here is `ErrorCode` — it does not end in `Error`, so the
scanner never sees these keys. `resolve_error_message` falls back to
`tr(code.message_key)` when an error carries neither a literal message
nor a `translated_message`, so each declared `message_key` is a live
operator-facing fallback that needs a translation in every locale.

A one-line scanner generalisation (collect `message_key=` /
`translated_message=` dotted-literal kwargs callee-agnostically)
exposes the true gap: **~367 ErrorCode `message_key` fallbacks across
`errors.{auth,error,fail,integrity,internal,locked,refused}.*` have no
locale entry in any of es/en/ca/hu.** The `errors:` block in each
locale carries only a handful of hand-authored keys
(`errors.calc.*`, `errors.identity.*`, `errors.censo.*`,
`errors.refused.refused_cli_validation_boundary`, …). The bulk
registry fallback surface is untranslated.

A separate ~8 `wizard.setup.verifier.*` keys also surface as genuinely
missing real keys (distinct from the error-registry namespace).

## Scope decision

ErrorCode `message_key` values **are** a must-translate locale surface
— any error can be constructed bare and render its fallback. The
scanner generalisation is the correct fix. But it cannot land alone:
`test_codebase_to_locale_parity` hard-fails on any codebase key absent
from a locale, and the project rules forbid carving a tolerance into a
gate. The scanner extension must land **together with** the
translations (or a staged, namespace-by-namespace subset), never
before.

Translating ~367 error messages × 4 locales, grounded in each error's
semantics, is a dedicated remediation wave — it is not mechanical
(the `message_key` is an identifier, not a source string, so
`scaffold` cannot auto-fill content).

## Remediation

- The scanner generalisation (callee-agnostic `message_key=` /
  `translated_message=` collection) is designed and validated; hold it
  until the translations are ready, then land both together.
- New wave: author the `errors.*` registry-fallback translations,
  namespace by namespace (`errors.refused.*`, `errors.error.*`,
  `errors.fail.*`, `errors.auth.*`, `errors.integrity.*`,
  `errors.locked.*`, `errors.internal.*`). Each namespace batch lands
  with the scanner seeing that namespace, so the parity gate stays
  green per increment.
- Author the ~8 `wizard.setup.verifier.*` keys (smaller, independent).
- All locale edits via the `aeat.locales` CLI per project rule.

