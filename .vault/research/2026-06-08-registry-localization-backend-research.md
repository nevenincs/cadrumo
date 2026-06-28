---
tags:
  - '#research'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related: []
---



# `registry-localization-backend` research: `schema backend localization support`

Research on implementing localized support for Casilla labels, helper texts, and invariant translation values inside the model schema registry backend. This investigation is driven by the need to support localized UIs for operators in Catalan, Hungarian, and English, while keeping the core application locales clean and protecting CLI startup times from file bloat.

## Findings

### Registry Scale
Running `aeat app registry inspect` reveals that the registry contains 30 modelos, 46 revisions, and 15,291 casillas.
* Each Casilla has a `label` attribute representing the official Spanish text printed on forms.
* Loading all these strings into the core application `en.yml`/`es.yml`/`ca.yml`/`hu.yml` files (which are eagerly parsed on CLI startup) would add 61,164 leaf strings.
* This would increase YAML file size by several megabytes, introducing a major performance bottleneck during CLI bootstrap.

### Regulatory Invariant
* The physical and legal Spanish labels are regulatory constraints. To export conformance workbooks (like openpyxl offline sheets or Google Sheets layouts), the system must print the exact, legally binding Spanish labels regardless of the operator's locale.
* Therefore, the official Spanish label must remain in the registry TOMLs as a static structural invariant.

### Lazy-Loading Architecture
* Translatable help text and localized labels should reside in model-local translation extension files under the registry data directory (e.g., `src/aeat/_data/registry/aeat/modelos/<modelo>/locales/`).
* These files can be loaded lazily only when a specific modelo revision is requested, bypassing the core eager localization pipeline entirely.
* A fallback mechanism in the registry compiler will allow mapping translatable string notations to schema invariants.
