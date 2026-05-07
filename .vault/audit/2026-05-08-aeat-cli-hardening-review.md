---
tags:
  - '#audit'
  - '#aeat-cli-hardening'
date: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-hardening-inventory]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-cli-hardening` Code Review

<!-- Persistent log of audit findings appended below. -->

## Review Pass 1: `A23` And `A27` Help Copy Drift

Scope reviewed: `src/aeat/entrypoints/cli/_setup.py`,
`src/aeat/entrypoints/cli/test_user_cli_surface.py`, and the locale files for
Spanish, English, Catalan, and Hungarian.

No CRITICAL, HIGH, MEDIUM, or LOW findings were identified in this slice.

Review notes:

- `auth reset` no longer carries inline English command or option help.
- The reset scope validation message now uses the locale catalogue.
- Invoice import `--kind` help now names the actual accepted CLI values.
- Tests invoke the real Typer app help surface and can fail if the old wording
  returns.
- No business logic was added to CLI handlers; the change is restricted to
  existing command metadata and tests.
