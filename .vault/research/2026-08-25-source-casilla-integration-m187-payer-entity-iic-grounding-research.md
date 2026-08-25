---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7c889fad0828100cdddcadbc0173001a9165148655945320f084fee0f5a5be82'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `source-casilla-integration` research: `m187 payer entity iic grounding`

Modelo 187 has distinct type-1 filer/header and type-2 payer/entity/IIC facts. The official sources establish filing populations and record structure, but no current secure source owner supplies a non-lossy connected carrier; this record therefore authorizes no binding, resolver, export, or census promotion.

## Findings

### Article 42 RGAT is a separate obligated-person limb

Orden HAC/1417/2018 rewrites the Modelo 187 filer population to include the Article 42 RGAT obligated-person/entity limb in addition to the withholding payer population. The canonical legal catalogue records that separation at `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2021`; the official order is BOE-A-2018-17997. A single payer selector cannot represent both without collapsing distinct legal populations.

### Type-1 and type-2 records have non-substitutable grain

The Modelo manifest cites the authoritative AEAT procedure and BOE layout at `src/cadrumo/_data/registry/aeat/modelos/187/manifest.toml:2`. Type-1 owns declarant/header facts; type-2 carries payer/entity/IIC record facts. Existing manual/direct fields remain legitimate operator entry, but do not establish capture identity, source provenance, secure persistence, replay, review, or a live source owner.

### No connectable source route is present

The live source mesh has no Modelo 187 payer/entity/IIC resolver; its existing resolver families are source-kind-specific and must not be repurposed. Neither current registry declarations nor export structure prove a secure owner. Temporal applicability and an export layout are downstream schema facts, not evidence of source ownership. The evidence supports deferral pending a separately accepted non-lossy source carrier; it does not safely classify a new census entry before the S112 census lane.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2002`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2021`
- `src/cadrumo/_data/registry/aeat/modelos/187/manifest.toml:2`
- https://www.boe.es/buscar/doc.php?id=BOE-A-2018-17997

<!-- Lead: the question, why it matters to `source-casilla-integration`, and what was
     concluded - the evidence picture, not a decision. -->

## Findings

<!-- One ### subsection per line of inquiry. Claim first, evidence after.
     Anchor every non-obvious claim to a re-fetchable locator (URL,
     `file:line`, commit SHA, `package@version`, RFC number). Link, do not
     copy. Pin versions, dates, numbers. State each fact once: link what a
     related vault document already records; do not repeat what an earlier
     section establishes. Name alternatives and why kept or rejected. State
     what was not investigated. Cut anything that changes no decision. -->

## Sources

<!-- Each locator cited above, once: `path:line` backtick locators for code,
     bare URLs for external references. Flag unverified general-knowledge
     claims. -->
