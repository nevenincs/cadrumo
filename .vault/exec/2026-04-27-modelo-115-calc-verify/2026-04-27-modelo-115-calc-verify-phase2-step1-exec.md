---
tags:
  - '#exec'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-plan]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
---

# Step record — extractor sibling classes (2024 + 2026)

Plan reference:
`2026-04-27-modelo-115-calc-verify-plan` §2.1..§2.2.

## Files changed

- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_115_v2025.py` — added
  `Modelo115V2024Extractor` and `Modelo115V2026Extractor` sibling
  subclasses. Each pins only its own `template_revision`
  ClassVar; the extraction logic is inherited verbatim via
  `Modelo115V2025Extractor` (which is itself a thin subclass of
  `GenericDeclaracionExtractor`). Module docstring updated to
  document the three-year layout invariance per the rule-delta
  manifest. `__all__` updated.
- `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py` — extended the
  import statement and registered both new classes in
  `_REGISTERED_CLASSES`.

## Verification

- Smoke test in Python REPL:
  ```python
  from aeat.adapters.inbound.declaracion._extractors import get_extractor
  from aeat.adapters.inbound.declaracion._schema import TemplateRevision
  for año in (2024, 2025, 2026):
      tr = TemplateRevision(modelo='115', año=año, revision=f'{año}.01')
      cls = type(get_extractor(tr))
      print(año, cls.__name__)
  ```
  → resolves to `Modelo115V2024Extractor`,
  `Modelo115V2025Extractor`, `Modelo115V2026Extractor`
  respectively.

## Notes

This step closes the same registry gap that issue `#321`'s
PR-440 review surfaced for Modelo 130 — without sibling
classes, a 2024 or 2026 PDF of M115 would raise
`NoExtractorRegisteredError` at the
`detect_template_revision → get_extractor` boundary.
