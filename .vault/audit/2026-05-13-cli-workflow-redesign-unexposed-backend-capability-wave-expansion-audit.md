---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace cli-workflow-redesign with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#cli-workflow-redesign'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-13'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-audit-research]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-workflow-redesign` audit: `unexposed-backend-capability-wave-expansion`

## Audit Scope

This audit covers the unexposed backend capability research, the corresponding
ADR, and waves W62 through W69 in the epic plan. The review checks the new
design slice against the apex root contract, command-collision and shadow-path
removal, strict typed backend contracts, secure bucket persistence, central
errors and logging, `_emit` output, and user-facing command vocabulary.

## Findings

- Finding: The new ADR correctly maps each unexposed backend cluster to an
  approved `aeat app` domain and rejects standalone roots. No new `aeat`
  third-root, topic root, sanitize root, LLM root, filing root, or submit-shaped
  command is approved.
- Finding: The initial LLM wording included an overbroad capability path. That
  wording was broader than the audited CLI epic and was removed. The accepted
  language now limits LLM access to approved OCR, extraction, and classification
  backend services.
- Finding: The initial plan wording used shortened command names without the
  binary root. The waves now use full operator-facing command paths such as
  `aeat app modelo verify`, `aeat app modelo file`,
  `aeat app ledger attach`, and `aeat app registry citations`.
- Finding: The first draft described typed services unevenly. Each new wave now
  carries explicit strict Pydantic backend contract language in its backend
  phase, with CLI handlers kept as argument parsing and `_emit` rendering only.
- Finding: The shadow and collision requirement is now explicit in each new
  removal phase. W62 through W69 each require command-collision and shadow-path
  cleanup before CLI exposure.
- Finding: Secure storage is represented across the new waves. Declaration,
  justificante, submission-status, sanitizer, LLM-derived evidence, export
  manifests, and attachment evidence all require active profile bucket
  persistence and bucket events where mutations occur.
- Finding: UX vocabulary now matches the apex: no wording authorizes live AEAT
  submission, remote write, sign, present, or pay. W65 and W68 explicitly test
  this absence.

## Result

The new ADR, research document, and W62 through W69 plan waves are coherent with
the apex style after the remediation edits. They do not preserve rejected support
surfaces, do not allocate business logic to the CLI layer, and do not introduce
ungrounded operator domains.

Residual vault-wide schema warnings remain outside this audit slice: several
older `cli-workflow-redesign` ADRs still lack research links. The new
unexposed-capability ADR is research-linked and passes the targeted structure
checks.
