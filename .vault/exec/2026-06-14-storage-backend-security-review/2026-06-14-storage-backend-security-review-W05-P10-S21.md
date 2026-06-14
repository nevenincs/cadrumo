---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S21'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Route every domain and outbound secure-object namespace literal through its STORAGE_NAMESPACE_REGISTRY definition constant and ## Scope

- `src/aeat/domain/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route every domain and outbound secure-object namespace literal through its STORAGE_NAMESPACE_REGISTRY definition constant

## Scope

- `src/aeat/domain/`

## Description

- Route the `adapters/outbound/` secure-object namespace literals through their
  registry definitions: LLM cache/usage, Google OAuth client/token/metadata +
  Drive config, and the AEAT sede filed-declaration artefacts/observations + IVA
  wallet observations. Each local constant now derives from
  `<DEFINITION>.namespace`.

## Outcome

PARTIAL — outbound subtree only. Behaviour-preserving (every constant equals the
prior literal). 48 LLM tests green; outbound collect-only clean. Committed in
`1a06c2e47`. Step LEFT OPEN: the `domain/` namespace literals (submission, filing,
invoices, transactions, calculation_revisions, justificante, usage_ratios,
participation index, verification/filing/complementaria repos, bucket event repo)
remain to be routed through the registry.

## Notes

GATE BLOCKER for S22: extending the adoption gate to scan `adapters/outbound`
(and `domain`) is not clean as-is — the gate's third heuristic ("namespace
constant must come from storage registry") over-flags legitimate non-registry
`*_NAMESPACE` constants present in outbound (mirror-manifest sync-state keys,
`"_probe"` markers) and likely domain too. The gate needs refining (restrict the
check to constants actually passed as secure-object namespaces whose string
matches a registry namespace value) before the scope can widen without redding
the build. Tracked as part of S22.
