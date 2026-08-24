---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3af12a520870f37274c220b20897454f0a5e04d556be3fc03f9585a1591578b2'
step_id: 'S19'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Keep M210 tipo 28 event-shaped without a numeric offset until RD 1776/2004 article 14 is bundled and verified

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/210/`
- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Search the code and decision corpus semantically for alternate M210 tipo-28
  deadline or numeric-offset implementations, then confirm exact symbols with a
  targeted source sweep.
- Preserve the existing `EVENT-N` selector and the deliberate absence of a tipo-28
  deadline row and `rd-1776-2004:art-14` legal authority.
- Add an executable registry regression that fails if any revision loses the
  event selector, gains an ungrounded tipo-28 window, or claims the missing legal
  authority.
- Run the focused regression and Ruff against the changed test surface.

## Outcome

The S18 corpus already represented tipo 28 correctly, so no registry or legal data
was redeclared. The new biting test makes the missing authority a visible invariant:
tipo 28 remains event-shaped and cannot acquire a calendar window until the named
article is bundled through the legal catalogue.

## Notes

The focused regression passed. The broader Modelo 210 file was attempted but is
temporarily red because concurrent work removed the sole fragment from Modelo 322's
`2008-2022` deadline directory; every observed failure stopped at that unrelated
registry-load error. Ruff passed.
