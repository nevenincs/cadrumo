---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:014b251169c647c39ac2065a7314cd278f071c18363ea3bc654b911cdfb940dc'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-homepage-product-design-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
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

# `tui-architecture` audit: `w08 p26 s371 review`

## Scope

Independent review of `W08.P26.S371` in `src/cadrumo/entrypoints/tui/devtools/home_fixtures.py` and its focused tests against the exact plan row, approved Home product research, live `HomeProjectionV1` invariants, and architecture, naming, quality-gate and sensitive-data rules. The review covered all seven required scenarios, typed immutability, synthetic-data safety, deterministic fresh construction, availability truth, candidate-sizing utility, locale neutrality, I/O, and operator vocabulary.

The scenario enum and immutable builder mapping cover ready, locked, stale, never-captured, unavailable, empty and blocked exactly. Every builder returns a fresh, equal `HomeProjectionV1`; nested values use the real frozen Home, action, period and calendar models. Fixed time/date values and generic fixture labels are deterministic and synthetic. Non-available scenarios carry explicit reason codes and no false rows or counts, while available-empty carries proven zero Ledger and Messages values. Inspection found no repository, filesystem, network, secret, locale-catalogue or frontend execution dependency. The required internal `work_unit_id` field is used only to construct `HomeDeclarationResume`; the fixture authors no visible WorkUnit wording, and candidate product code must treat it solely as declaration identity.

## Findings

### measurement-corpus-density | high | Populated fixtures cannot exercise the candidate layouts they are meant to compare

Both populated scenarios contain exactly one next action, one declaration and one agenda entry. The approved Home research requires the prototype to render up to three next actions, three resumable declarations and an agenda, and S373 must measure clipping, scroll ownership, focus reach, restoration and task keystrokes at the four supported geometries. With one row per list, neither candidate can expose maximum preview density, a second/third row focus path, within-list arrow movement, identity restoration after selecting a non-first declaration, or the floor-height transition created by real stacked content. Short single-token reason codes and the short declaration label also provide no representative wrap pressure for four-locale rendering. This corpus can make both layouts appear to fit and navigate while the required populated shape remains untested, so it is not yet valid evidence for S372-S374.

### sensitive-purity-gate-teeth | medium | Current safe literals and pure imports are not protected by adversarial detectors

The fixture is non-sensitive and pure by inspection, but the security test examines only `ImportFrom` roots against six names. It misses direct `Import`, filesystem or repository imports under other names, and I/O calls. No test serializes every scenario and rejects representative NIF, IBAN, email, credential, filing-reference or secret-shaped content, so a protected literal inserted into profile/declaration labels or reason fields would remain green. The freshness test proves only top-level projection/account replacement and top-level frozen assignment; it does not assert fresh nested populated records or stable declaration identities across builds. These gaps weaken the security and isolation claims carried by the fixture module.

### final-density-disposition | low | Populated fixtures now exercise full preview density and varied typed states

Ready and blocked now each carry three uniquely ranked actions, three distinct declaration identities and three chronological agenda entries. The declarations vary lifecycle state and Modelo/period coordinates; agenda rows vary period, local-filing and AEAT-observation state. Direct inspection confirms the populated builders reconstruct these nested records on every call while preserving their semantic declaration identities. The corpus can now drive second/third-row arrows, non-first declaration focus restoration, maximum preview height and floor scrolling. `measurement-corpus-density` is closed.

### final-sensitive-purity-disposition | medium | Security and I/O detectors improved, but sensitive and nested-freshness teeth remain incomplete

The suite now serializes every scenario, constrains Hex64 values, checks several credential/email/IBAN/DNI patterns, and scans both import forms plus a wider call denylist. Current fixtures remain synthetic, deterministic, fresh and pure by inspection. The detector does not recognize NIE-shaped NIFs such as `X2482300W`, despite claiming PII coverage, and the I/O scan still permits paths such as `os.open` and arbitrary repository imports. The freshness test still asserts object replacement only for the projection and account, so caching populated action, declaration or agenda records would stay green; stable declaration identity across rebuilt projections is likewise unasserted. `sensitive-purity-gate-teeth` therefore remains open at medium severity even though no live sensitive literal, retention or I/O defect was found.

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### w08 p26 s371 review | {level} | {summary}

     followed by a paragraph carrying the detail. w08 p26 s371 review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

1. Expand at least one populated scenario to three application-ranked actions, three distinct declarations and three chronological agenda entries, with varied typed statuses and safely synthetic labels/reasons long enough to exercise wrapping. Keep semantic ordering owned by the projection, not the candidate.
2. Add behavioral probes for second/third-row focus and stable declaration identity, and prove every populated nested record is fresh across builds.
3. Serialize all scenarios and reject representative synthetic sensitive patterns and plaintext secret markers. Expand the no-I/O gate across `Import`, `ImportFrom` and relevant filesystem, repository, network and secret-access calls.
4. Keep `work_unit_id` as an internal application-contract field only. Candidate IDs, accessibility labels, copy and tests must call it declaration identity and must never render WorkUnit vocabulary.
5. Focused Pytest passed 15 tests; Ruff and ty passed; Basedpyright reported 0 errors, warnings or notes. No critical finding exists, but one high and one medium remain open. `W08.P26.S371` must not close.
6. Add an NIE/NIF probe, cover broad filesystem/repository entry points rather than a short denylist, and assert populated nested records are distinct objects across builds while their declaration identities remain equal.
7. Final focused Pytest passed 16 tests; Ruff and ty passed; Basedpyright reported 0 errors, warnings or notes. The high finding is closed, but one medium test-integrity finding remains open. `W08.P26.S371` must not close yet.

