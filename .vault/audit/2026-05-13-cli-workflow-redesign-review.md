---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-W01-P001-exec]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `cli-workflow-redesign` Code Review

<!-- Persistent log of audit findings appended below. -->

<!-- Use: {TOPIC}-### | {LEVEL} | {Summary} \n {DESCRIPTION} format-->

W01-P001-001 | MEDIUM | Retired-surface contract omits ADR-mandated legacy roots
The accepted apex ADR requires legacy roots including `deadlines` and `browser` to be retired or folded under `config` and `app`, with explicit fold-under mappings to `app overview` and `config doctor connectivity`. The implementation in `src/aeat/application/operator_surface/_contract.py` omits both names from `RETIRED_OPERATOR_SURFACES`, and `retired_surface_suggestion("deadlines")` / `retired_surface_suggestion("browser")` currently return `None`. As a result, future CLI adapters using `require_accepted_root` will fall back to the generic `aeat --help` refusal instead of the backend-owned contract direction required by the ADR. The focused tests in `src/aeat/application/operator_surface/test_contract.py` only prove `setup` and `submit`, so this contract drift is not guarded.
