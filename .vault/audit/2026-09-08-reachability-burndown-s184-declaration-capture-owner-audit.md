---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:663e45078044b417b00afc1dc5b13ed75811e0522610a6e1a84eb016094c7192'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace reachability-burndown with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `reachability-burndown` audit: `s184 declaration capture owner`

## Scope

S184 was audited against the reachability plan, the amended justificante identity decision and its call-graph remeasurement, the declaration-register capture implementation, its package surface and shipped registry declarations, and the focused declaration/PDF contract tests. The review checked that the normalized register session is the sole executable owner, that refusal occurs before browser mutation, that exact-row and canonical PDF validation remain in the owning paths, and that the tests can detect an incomplete consolidation.

## Findings

### stale-application-link-consumers | high | Shipped registry authority still names the deleted capture facade

Eighteen application-link records under the shipped Modelo registry still declare `cadrumo.adapters.outbound.aeat.sede.capture_filed_declaration_observation` as their portal consumer. S184 removes that symbol and does not publish `DeclaracionesRegisterSession` from the package facade, so those authority records now point at a consumer the product cannot resolve. The focused tests remain green because the PDF contract test uses a hand-maintained tuple of two implementation functions and no test resolves registry `consumer` values or asserts that the retired dotted target has disappeared from shipped declarations. This leaves the consolidation semantically incomplete and permits future facade deletion to strand registry claims undetected.

Disposition: resolved. All eighteen records now name `cadrumo.adapters.outbound.aeat.sede.declarations.DeclaracionesRegisterSession.capture_observation`. The aggregated `application_link_consumers` gate discovers every application-link whose id ends in `filed-declarations-observation`, resolves its `cadrumo.*` module and nested attribute chain, and fails on an unresolved target. Its hostile fixture proves a deleted attribute is reported, its positive fixture proves the nested session method resolves, and the live registry scan exits cleanly. Independent re-review ran both detector tests and the gate successfully; no open S184 findings remain.

## Recommendations

- Resolve `stale-application-link-consumers` before closing S184: migrate all eighteen application-link declarations to the canonical session capture owner using the registry's accepted dotted-target grammar, and add a detector-teeth test that fails when an application-link consumer names a removed module or attribute. Prove the detector with a fixture containing a stale dotted target, then rerun the affected registry validation and focused declaration/PDF tests.

Completed by the disposition recorded above.
