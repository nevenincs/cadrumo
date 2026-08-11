---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:bbb05096912e3a7bed8c917421657058b6b693ae92578f72e33d174f5c330449'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-W04-P07-S49]]"
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

# `aeat-export-fragment-generator-authority` audit: `s49 differentiated deduction review`

## Scope

Reviewed S49 against the accepted M303 projection and prorrata ownership decisions. The audit covered arithmetic ownership, sector applicability, ledger identity, Bienes regularisation linkage, official endpoint geometry, failure behavior, caller migration, and the prohibition on duplicate persistence or aggregation.

## Findings

### s49-differentiated-deduction-review | high | Raw cuota was initially summed in projection

The first projector treated frozen observation cuota as already deductible. Architecture review established that application aggregation owns prorrata exactly once, including special-prorrata routing. Remediation added immutable apportioned contributions in that owner and made registry projection consume only those outputs.

### s49-differentiated-deduction-review | high | Sector applicability could silently route or disappear

Missing or unknown sectors could fall into common use and inactive or unresolved register entries could be filtered away. Remediation requires exact active sector authority and resolved percentages. Only explicit common-use classification may omit a sector identity.

### s49-differentiated-deduction-review | high | Duplicate ledger facts could be counted twice

The first contribution type discarded ledger identity. Remediation retains immutable source ledger identities and enforces exact-once consumption across all contribution categories before any sum.

### s49-differentiated-deduction-review | medium | Regularisation ownership was insufficiently constrained

Ordinary contributions could silently carry the Bienes-owned kind and a structural protocol admitted forged asset values. Remediation rejects wrong-owner observations and accepts the concrete canonical regularisation result with year, pending-state, asset-row, duplicate, sector, and casilla-43 parity validation.

### s49-differentiated-deduction-review | low | Final review found no residual defect

The final independent review passed with zero findings. All five revisions carry 36 fixed two-sector projection-only endpoints, arithmetic is applied once, and no unguarded caller or legacy surface remains.

## Recommendations

- Keep prorrata arithmetic in the canonical application aggregation service.
- Keep common use explicit and reject incomplete declared sector authority.
- Preserve ledger and asset identity through every future differentiated-deduction consumer.
