---
tags:
  - '#audit'
  - '#support-removal-fabricated-grounding'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:53ae8de6bfdceab67b1446e49fb31a000e97fbfa70dc24f360eaa6b66685a7cf'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
---

# `support-removal-fabricated-grounding` audit: `fabricated legal grounding in support-removal decisions`

## Scope

The `support_removal_decisions` registry mechanism (`SupportRemovalDecisionDefinition`,
one entry per `modelos/{id}/revisions/{rev}/support_removal_decisions/*.toml`) as it
existed on disk before this session deleted it, and its relationship to the accepted
`aeat-fichero-boe-export-adr`, which requires fichero-BOE fixed-width export support for
Modelo 130 and Modelo 303. Twenty entries were committed across ten modelos: 111, 115,
123 (two revisions), 130, 200, 202 (three revisions), 232 (two revisions), 303 (six
revisions), 390 (four revisions). This document records the finding retrospectively,
after the mechanism was deleted in this session; it is not an audit of code that still
exists.

## Findings

### fabricated legal grounding in support-removal decisions | critical | every removal decision cited real law it did not actually rest on, indistinguishable from a legitimate refusal

All twenty committed entries, without exception, declared the identical pair:
`decision = "remove_from_filing_grade"` and `reason = "unsupported_official_format"`.
The Modelo 390 2025 entry's own `evidence_note` gives away what was actually happening:
"This filing-grade fixed-width layout is withdrawn atomically because its official
record design contains producer fields that do not yet have canonical typed producer
authority; retaining a partial layout would permit silent under-declaration." That is a
description of unfinished application work — nobody had built typed producers for those
fields — dressed in the vocabulary of a regulatory decision. AEAT withdrew nothing. The
official format was never unsupported by AEAT; the application had not finished
supporting it.

The entry then attached real legal citations to that engineering gap. The Modelo 390
2025 `legal_refs` list named `ley-37-1992` (LIVA) articles 88, 90, 91, 92, 99, 115, 116,
122, 123 and 161, plus `orden-eha-3111-2009:art-1` and `rd-1624-1992:art-71` — twelve
real, resolvable provisions of Spanish VAT law and its implementing orders. Every other
committed entry followed the identical `reason`/citation pattern for its own modelo. Not
one of those provisions PROHIBITS Modelo 390 (or any of the other nine modelos) from
having a fixed-width export layout. They are the general LIVA framework articles the
modelo's calculations already cite elsewhere for unrelated reasons. Citing them here
supplied no falsifiable claim; it supplied the visual signature of a grounded decision —
`legal_refs`, `source_refs`, an `evidence_note` — to a record that was, in substance,
"we have not built this yet."

This is why it survived unnoticed: the registry's own validators (`_validate_constructs.py`'s
`validate_support_removal_decisions`, deleted alongside the mechanism this session) checked
only that the cited `legal_refs`/`source_refs` RESOLVED against the legal and source
catalogues and carried an accepted evidence tier. Nothing checked that the cited provisions
actually established the claimed removal. A reviewer or a downstream gate reading the
record — legal refs present, source refs present, evidence note present, decision typed —
had every structural signal of a grounded refusal and no way to tell it apart from an
unfalsifiable one without independently reading all twelve articles and confirming none
of them says what the record implies. Every gate that saw those `legal_refs` treated the
absence of an export layout as principled and moved on.

### fabricated legal grounding in support-removal decisions | critical | the Modelo 303 removal directly contradicted a standing accepted decision it never amended or superseded

`2026-04-22-aeat-fichero-boe-export-adr` is `accepted`, still is today, and its 2026-05-21
amendment restates the decision explicitly: "The decision in this ADR — that Modelo 130
and Modelo 303 fichero-BOE export support is required — is unchanged." Six committed
`support_removal_decisions` entries (Modelo 303 revisions 2009-y-siguientes, 2023,
2024-hasta-08-y-2t, 2024-desde-09-y-3t, 2025, 2026-y-siguientes) declared Modelo 303's
fichero-BOE layout `remove_from_filing_grade` under the same `unsupported_official_format`
reason, with no amendment to the ADR and no superseding decision record. The registry
therefore carried, simultaneously, an accepted decision requiring Modelo 303 fichero-BOE
export and a set of registry-data records asserting that capability was not required. The
`support_removal_decisions` mechanism does not consult ADR status at all — it has no
mechanism to — so this contradiction was invisible to every registry-build gate; only a
reader who separately knew the ADR's content and separately read the removal records could
see the two disagreeing.

## Recommendations

- A follow-on ADR should decide the grounding standard for any future "this capability
  cannot be built" declaration in the registry: a refusal grounded in law must name the
  provision that PROHIBITS the capability (or makes it inapplicable), not a provision that
  merely governs the general subject area, and the citation must be checked against the
  bundled corpus text for that specific claim rather than accepted because it resolves.
  "We have not built the typed producers yet" names no such provision by construction, so
  any mechanism that accepts a citation without that check will reproduce this defect
  under a different field name.
- Before any future registry-data record narrows or removes a capability that a standing
  accepted ADR requires (fichero-BOE export for Modelo 130/303 being the concrete case
  here), the ADR must be amended or superseded in the same change. A follow-on ADR or gate
  should decide whether registry build validation can detect this class of contradiction
  mechanically (e.g. cross-checking `remove_from_filing_grade` subjects against ADR-declared
  requirements) or whether it remains a reviewer discipline.
- The replacement mechanism landed this session — a hard registry-build refusal when a
  revision declares a calculation-completeness manifest but no fixed-width export layout,
  with no declaration able to excuse the absence — structurally removes this specific
  defect class by removing the escape hatch entirely rather than tightening its grounding
  standard. Confirm in that mechanism's own review that no equivalent "declared exemption"
  path is reintroduced later without meeting the falsifiability standard above.
