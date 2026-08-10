---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:05b7c518971c235d37acb1117c676f8469dcea247e4baac3f01d91972e562925'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
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

# `aeat-export-fragment-generator-authority` audit: `s46 typed producer snapshot`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

Independent Luna review audited the S46 filing producer module, its public facade, real-behavior tests, and generated API scaffold against the accepted S44 canonical-home decision and the narrowed S46-before-S45 plan boundary. The review checked canonical ownership, immutable and strict typing, presenter separation, amendment evidence, account selection, unsupported M202 inventory, false-green resistance, and absence of semantic-vocabulary, renderer, composer, or raw-header integration work.

## Findings

### s46-canonical-profile-owners | resolved-high | Parallel M202 and M303 profile schemas redeclared canonical facts

The initial implementation introduced `Modelo202ProfileFacts` and `Modelo303ProfileFacts`, repeating five `TaxpayerProfile` corporate facts and seven `ModeloIVAProfile` census axes with divergent nullability. That violated the S44 single-home matrix and could let producer behavior drift from persisted typed profile authority.

The remediation deleted both duplicate classes and their public exports. M202 now composes the canonical `TaxpayerProfile` inside its producer view, and M303 accepts the canonical `ModeloIVAProfile` directly. Tests assert canonical runtime type identity and the absence of both legacy duplicate class names. Embedded profile accounts are removed before snapshot construction, while direct construction refuses them, so the disposition-selected account projection remains the only account carried by a snapshot.

The re-review passed with zero critical, high, medium, or low findings. Focused verification passed 12 tests; Ruff passed; strict BasedPyright reported zero errors, warnings, and notes; API scaffold conformance and exact cached diff checks passed. The tests enumerate every unsupported M202 producer ID rather than checking only a count and use distinct real IBANs to prove the unselected account is absent.

## Recommendations

Accept S46. Preserve `TaxpayerProfile` and `ModeloIVAProfile` as the canonical profile owners, keep the presenter explicit, and retain only the disposition-selected account in the snapshot. S45 may integrate this public substrate into vocabulary, maps, renderer, raw-header deletion, and composer flow, but must not restore duplicate profile records, scalarize M202 CNAE without an authoritative greatest-turnover fact, or introduce compatibility aliases, defaults, fillers, or plaintext account persistence.
