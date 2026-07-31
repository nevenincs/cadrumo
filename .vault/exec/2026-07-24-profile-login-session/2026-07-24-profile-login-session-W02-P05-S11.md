---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:e5b7624a5ebccbd28aa0c0376e37900e3a9ff4a06ed24094e6d05c700e3c614a'
step_id: 'S11'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Register aeat config login (bootstrap-exempt, optional NAME argument, --secrets-stdin strict-JSON passphrase channel) and aeat config logout with envelope identifiers config.login and config.logout and the uniform result payloads, verified by documented-command and JSON-schema conformance plus direct invocation tests

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py`
- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

- Register `login` and `logout` on the config root through the custody registrar, both already enrolled bootstrap-exempt.
- Delegate profile selection wholly to the application login service's UUID-or-exact-label resolver rather than adding a second CLI selector authority.
- Read the optional passphrase from the shared bounded strict-JSON stdin channel the custody verbs already use, so it is never an argv value.
- Add typed result payloads registered under the envelope identifiers `config.login` and `config.logout`.
- Land help and notice locale keys in all four catalogues through the locales CLI.

## Outcome

Both verbs resolve and render. Locale parity, translation honesty, JSON-schema conformance, and documented-command conformance are green at 46 passed. Ruff and ty are clean on both touched modules.

## Notes

The passphrase resolver is a nested function rather than a lambda so it carries a docstring and avoids a lint suppression. The emitted profile identifier is redacted to the standard placeholder by the envelope funnel, which the lifecycle suite asserts.
