---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S18'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace llm-evidence-classification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Fold Attachment.sha256 into the LLM cache build_key for multimodal evidence inputs

## Scope

- `src/aeat/adapters/outbound/llm/_cache.py`

## Description

- Add a frozen `MultimodalImageInput` model to `_models.py` carrying a 64-hex `content_sha256` content address plus the `repr`-suppressed `base64_data` payload, and an `images` tuple field on `LLMRequest`.
- Fold each image's `content_sha256` into `LLMCache.build_key`'s `args_payload` (`image_content_addresses`) so the content address — never the bytes — enters the cache key.
- Thread `LLMRequest.images` to `ProviderRequest.images` (mapping `.base64_data`) in `LLMClient.complete`.
- Re-export `MultimodalImageInput` from the package `__init__`.

## Outcome

- Two distinct evidence documents under one prompt now derive distinct cache keys; identical content addresses reproduce the same key. The base64 payload is hashed into the ephemeral request id but never persisted. Verified by the new collision test and the full cache suite.

## Notes

- The content address is folded (not the base64 bytes), keeping the cache key stable across re-encodings of the same source and honouring `sensitive-financial-data-secure-storage-only`.
