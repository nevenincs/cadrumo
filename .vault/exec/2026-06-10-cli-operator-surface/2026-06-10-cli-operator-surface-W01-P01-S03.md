---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
step_id: 'S03'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# narrow the doclink --source enum choice to the three members the handler accepts or widen the handler so the advertised set matches, satisfying the new gate

## Scope

- `src/aeat/domain/attachments/_enums.py`
- `src/aeat/domain/attachments/__init__.py`
- `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`
- `src/aeat/locales/{en,es,ca,hu}.yml`

## Description

Decision: NARROW the advertised set, not widen the handler. The doclink handler
maps only GMAIL / GOOGLE_DRIVE / URL to an `AttachmentKind`; `LOCAL_FILE` and
`INLINE` are byte-bearing captures, not document *link* sources, so accepting
them would invent behaviour the ADR forbids.

Added a dedicated `DocumentLinkSource` StrEnum (the three link sources) in
`domain/attachments/_enums.py`, re-exported it at the package top level, and
typed the `ledger doclink --source` option as it. The handler converts to
`AttachmentSource` via `to_attachment_source()` for the store call. The now-total
`kind_by_source` mapping replaced the unreachable app-level `bad_source` refusal:
the click Choice gate is now the instructive surface, listing the accepted set on
parse failure (per `aeat-architecture-boundaries`). Removed the orphaned
`cli.ledger.doclink.bad_source` locale key across all four catalogues.

## Outcome

`doclink --source` advertises exactly the three accepted link sources; the D5
enum-choice surface passes. `test_doclink_refuses_non_link_source` (LOCAL_FILE)
still passes (refusal moved to the click Choice gate, exit code 2). The
GOOGLE_DRIVE happy-path journey passes. `aeat.locales scaffold --check` clean
(no dangling `bad_source` reference). Docs unaffected (the guides cite
`--source GOOGLE_DRIVE`, still valid).

## Notes

`DocumentLinkSource` member values equal the matching `AttachmentSource` values,
so `to_attachment_source()` is a total mapping.

