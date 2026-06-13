---
tags:
  - '#exec'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-closure-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# c3 excise transient-meta phrases from three source modules

## scope

C3 rewrites three docstrings / inline comments the second-loop
reviewer flagged for carrying transient-meta or process-state phrasing
(`historically`, `with the wizard rewrite`, `UX-015 closure.`). Each
rewrite preserves the original technical content but states the
structural invariant directly rather than narrating how the surface
got here.

## files owned

- `src/aeat/application/profile/_storage_namespaces.py` — module
  docstring describes the HKDF context binding's structural role
  (per-record encryption key derivation) and the on-disk shape
  invariant it pins, rather than referencing the wizard rewrite. The
  phrase "Only the Python module path moves with the wizard rewrite"
  is gone; the byte-identifier values remain documented as
  load-bearing
- `src/aeat/domain/deadlines/_profiles.py` — the inline comment on
  the IVA-regime canonicalisation states the SELECT-validator
  contract directly. The phrase "deadline-engine callers historically
  supplied mixed case" is gone; the normalisation invariant
  (canonical uppercase token, dashes mapped to underscores) survives
- `src/aeat/entrypoints/cli/_topic.py` — the `UX-015 closure.`
  marker line is removed from the module docstring. The remaining
  docstring describes the topic-rendering responsibility and its
  registry / i18n inputs

## acceptance gates run

- `grep -rn 'historically|legacy|previously|formerly|replaces|UX-[0-9]'
  <C3 files>` — returns nothing
- `ruff check <C3 files>` — passes
- `ty check <C3 files>` — passes
- `pytest src/aeat/application/profile/ src/aeat/domain/deadlines/`
  — 57 passed (no behaviour change, as expected)

## notes

The HKDF byte-string and namespace constants are now documented as
the on-disk ciphertext shape's load-bearing identifiers, not labels
for the Python module that owns them. The IVA-regime comment now
reads as a forward statement about the wizard's validator contract,
not a historical note about caller-side drift.
