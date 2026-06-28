---
tags:
  - "#adr"
  - "#multilang-externalization"
date: 2026-05-04
modified: '2026-05-04'
related:
  - "[[2026-05-04-multilang-externalization-phase1-research]]"
---

# Architecture Decision Record: Multilang Externalization

## Status
Accepted

## Context
The previous trilingual i18n implementation (as defined in `2026-04-12-trilingual-i18n-adr`) introduced an inline kwargs pattern for translations (`t(es, en, ca, hu)`). This approach proved unmaintainable, coupling translations tightly to the codebase. We must adopt an externalized translation approach, supporting Spanish (es), Catalan (ca), English (en), and Hungarian (hu).

## Decisions

### 1. External Translation Framework
We will adopt **`python-i18n`** as our centralized localization backend.
*   *Rationale*: Provides a modern, key-based translation system using standard YAML configuration files.

### 2. Aggressive Pruning and Teardown
We will perform an aggressive, line-by-line teardown of all previous multilang implementations.
*   There will be **no backward compatibility** or incremental migration wrappers.
*   All `t(es, en, ca, hu)` structures, `Translatable` dictionaries, and `Language` enums will be completely excised from the codebase.
*   All tests attempting to verify the old multilang kwargs or fallback chains must be deleted.
*   Any class, module, or function attempting to implement its own multilang kwargs (e.g., `translate` functions accepting `en=`, `es=`) will be subjected to an extensive class-by-class audit and ripped out.

### 3. Translation Files (YAML)
We will store all translations in external YAML files (e.g., `locales/en.yml`, `locales/es.yml`, `locales/ca.yml`, `locales/hu.yml`).

### 4. Abstract Keys
All codebase strings will be replaced by strict **Abstract Keys** (e.g., `i18n.t('cli.auth.purpose')`). No language hints or source strings will remain in the Python files.

## Consequences
*   The immediate build will fail heavily until the teardown and replacement are complete across all CLI entrypoints and domain modules.
*   A strict line-by-line audit must be performed to ensure no remnants of the old system remain.
