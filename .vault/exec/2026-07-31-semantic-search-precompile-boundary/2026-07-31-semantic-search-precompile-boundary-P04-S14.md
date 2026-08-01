---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:bfc779c84a3c065109ffb75f1792c3292d7c38480f2ada9bfa75ac535decd8bc'
step_id: 'S14'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Run the fresh-context honesty review against the closure summary and persist it as a vault audit before declaring the campaign structurally complete and ## Scope

- `.vault/audit/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the fresh-context honesty review against the closure summary and persist it as a vault audit before declaring the campaign structurally complete

## Scope

- `.vault/audit/`

## Description

- Run the fresh-context honesty review adversarially, treating the campaign as inherited and asking what is missing, vague, or assumed-but-unverified.
- Re-measure every prior read-only inventory conclusion at current HEAD instead of inheriting it.
- Probe the deletion collateral: configuration, dead-code and type-check suppressions, generated stubs, locale catalogues, third-party notices, and the dependency lock.
- Probe the test surface for coverage that passes only by deselection or by being held out of a parallel lane.
- Probe the vault for any record still asserting a product-shipped semantic capability.
- Verify each of the plan's own Verification criteria against the mechanism it names, not against its conclusion.
- Persist the review as a vault audit and disposition every surfaced item.

## Outcome

The review ran and is persisted as the campaign's close honesty-review audit. It surfaced SEVEN items; all seven are closed with verification, and none is deferred.

Two items required a change and got one. The parent refoundation plan still advertised the runtime query embedder and the model2vec pins as delivered current architecture while its ADR and audit siblings both carried retirement annotations, so a reader could reach it without ever reaching the R3 amendment; a dated annotation was added to its Wave W06 prose, preserving every Step row untouched as a true record of what was built. The plan's own Verification section claimed the no-network property was proven "with sockets unavailable" when no socket-blocking mechanism exists or was ever built; the bullet was corrected in place with a dated note naming both the wrong mechanism and the real one, following the precedent ADR Update 1 set for the lockfile criterion.

One item was a code correction already landed under S11: the stale hybrid claim on the command-search index construction site.

Four items closed as verified without change: the ranking-golden gate is deselected by the default marker but is covered by the integration lane, recorded so a green routine run is not mistaken for discharge of the ranking criterion; the `LEXICAL_ONLY` member-name residue is deliberately left alone with the reasoning recorded to forestall a churn rename; both ADR Update 1 corrections were independently re-derived rather than trusted; and the deletion collateral is clean across every surface probed.

The campaign is structurally complete: the review ran BEFORE the declaration, which is the gate the discipline actually imposes, and every item it surfaced is dispositioned.

## Notes

Substantively, the campaign held up well under adversarial review. The product genuinely ships no semantic runtime: no shipped module imports a model loader, hub client, or vector maths, and the product dependency closure carries none of the three retired packages. Nothing was found that reopens the boundary ruling.

The honest pattern in the findings is worth stating plainly, because it is not flattering: the two medium findings that needed a change were both DOCUMENTATION claims that outran their evidence, not code defects. One criterion named a proof mechanism that did not exist, and one sibling document was left advertising a capability the campaign had just deleted. Both would have read to a later auditor as settled. The code was in better shape than the record of the code.

A related caution recorded for future sweep agents: the dev-side terminology pipeline legitimately describes embedding and hybrid retrieval, because it IS the build-time compilation oracle ruling R2 depends on. A vocabulary-matching sweep will hit those files and must leave them alone. That tree was additionally out of bounds here because a peer agent held uncommitted work in it.

No item was deferred, so no follow-up campaign reference is required. No skipped work, no scaffolds left in code.
