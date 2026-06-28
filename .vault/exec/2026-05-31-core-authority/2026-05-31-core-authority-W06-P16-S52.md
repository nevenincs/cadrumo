---
step_id: S52
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P16.S52

## Summary

Moved `AttachmentStoreProtocol` from `domain/attachments/_repository.py` to a new `domain/attachments/_protocols.py`. Updated `__init__.py` and `_service.py` to import from `_protocols.py`. The `_repository.py` was reduced to a stub docstring (the protocol was the only public symbol).

## Commit

`25f59f7c9` — feat(attachments): move AttachmentStoreProtocol from _repository.py to _protocols.py (MIGRATE-003 W06.P16.S52)
