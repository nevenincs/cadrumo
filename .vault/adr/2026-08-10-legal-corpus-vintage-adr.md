---
tags:
  - '#adr'
  - '#legal-corpus-vintage'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d95ff2a8891b6daa91b3d95285d6b7f436595f0335f18aec1baffa3ea4baf650'
related:
  - "[[2026-08-10-legal-corpus-vintage-reference]]"
  - "[[2026-08-10-minimo-descendientes-eligibility-art-81-live-cross-check-audit]]"
---

# `legal-corpus-vintage` adr: `What a corpus excerpt gate must be able to say` | (**status:** `proposed`)

## Problem Statement

Every legal-catalogue entry carries a `required_text` gate: phrases that must
appear in the corpus document the entry cites. The gate exists so that a fetched
file which parses cleanly but is the wrong text still refuses.

Measured, it does not do that. Of 72 divergences between an excerpt and the
bundled current text, the gate catches 3. The grounding reference has the split.

The obvious reading is that the phrases are badly chosen and better ones would
fix it. That reading is wrong, and this record exists to say why before someone
spends a sweep on it.

## Considerations

- 606 catalogue entries, every one gated; 261 cite a per-article excerpt.
- Of the 104 excerpt-backed entries with a consolidated counterpart, 54 diverge
  from current text with the gate green, and 3 fire.
- 84 gates have every phrase in the excerpt-and-current intersection, so they
  cannot discriminate vintage by construction rather than by bad luck.
- `ley-37-1992:art-122` carries a superseded eligibility rule for the régimen
  simplificado, and one of its two phrases exists ONLY in the superseded text.
- `ley-35-2006:art-81` carries a repealed cotizaciones ceiling alongside
  post-2023 text -- sibling audit.
- The deliberately year-vintaged excerpts DO pin their vintage, so the mechanism
  is not uniformly broken and a blanket remedy would damage the cases that work.
- 157 excerpt-backed entries have no offline oracle at all.
- Reference, throughout.

## Considered options

1. **Give the gate a NEGATIVE clause: phrases that must be ABSENT, alongside the
   phrases that must be present (chosen).** A repealed clause becomes
   expressible. Costs a schema field and a per-entry authoring decision.
2. **Choose better `required_text` phrases.** The intuitive fix and the one this
   record exists to reject. **No choice of phrases that must be PRESENT can
   express "and this repealed clause must be absent"** -- art-81's defect is a
   surviving repealed ceiling and art-122's is a superseded eligibility rule
   whose own phrase is in the gate. A presence-only grammar cannot state either.
   Phrase-tuning yields a green gate over the same defect.
3. **Require every entry to cite a consolidated file and retire the excerpts.**
   Attractive, and rejected as over-broad: the vintaged excerpts exist because a
   prior filing year needs the text as it stood, and a consolidated file carries
   only the current version. This would delete the ability to ground a prior-year
   calculation.
4. **Re-fetch every excerpt and trust freshness instead of gating.** Rejected:
   freshness is a property of the moment of fetch, and the defect class is drift
   afterwards. It also leaves the 157 unmeasured entries unmeasured.
5. **Pin each entry to a redaction identifier and validate against that.** The
   strongest alternative and deferred rather than rejected: it needs the BOE
   article endpoint per entry, which the acquirer supports but which is a larger
   change than the negative clause and does not subsume it -- a redaction pin
   says which version, not which clauses must not be present in a fragment.

## Constraints

- No production code lands from this record.
- **A negative clause is a REFUSAL, so it states a control proving the legitimate
  population still passes and does not close on the refusal firing.** The
  vintaged excerpts are that control's most important members: they legitimately
  contain text current law does not.
- The remedy must not treat a vintaged excerpt as a defect. Divergence from
  current is CORRECT for a deliberately historical document, and those gates
  already pin their vintage.
- No entry's phrases may be authored by reading only the excerpt. That is the
  condition that produced the 10 entries whose every phrase exists only in their
  own excerpt.
- This record does not rule that any particular excerpt is stale. It rules on
  what the gate must be able to express.

## Implementation

The gate gains a second, optional clause: text that must NOT appear in the cited
document. An entry grounding current law names a repealed clause it must not
contain; an entry grounding a historical vintage names the LATER text it must not
contain, which is what pins it forward as well as backward.

Registry build evaluates both clauses. The failure message names which clause
fired, because "a required phrase is missing" and "a forbidden phrase is present"
diagnose opposite defects and a single message conflates them.

What this record does NOT do: it does not author a negative clause for any entry,
does not retire any excerpt, and does not rule on the 157 entries with no offline
oracle beyond noting that they remain unmeasured.

## Rationale

Option 1 wins because the defect is a **grammar** gap rather than an input
quality problem, and only option 1 changes the grammar.

The evidence is that the two worked cases fail in opposite directions. Art-81's
excerpt is missing five current clauses AND carrying one repealed one, so it can
over-claim and overpay depending on which clause a consumer reads. Art-122
carries a superseded eligibility set. In both, what a reader needs the gate to
say is *this clause must not be here* -- and no set of must-be-present phrases
says it. Option 2 would have produced a green gate over both, which is the
specific outcome this record is written to prevent.

The measurement also shows why the remedy must be additive rather than a
replacement. The vintaged excerpts already pin correctly through their present
phrases; a redesign that discarded the presence clause would break the cases that
work in order to fix the ones that do not.

## Consequences

**Gains.** A repealed clause surviving in a cited document becomes expressible
and therefore catchable. The failure message distinguishes two opposite defects.
And a historical excerpt can be pinned against forward drift, which nothing does
today.

**Difficulties.** Authoring a negative clause requires knowing what the document
must NOT contain, which is a tax review per entry against the redaction history
rather than a lookup. This closes slowly and cannot be swept.

**Pitfall guarded against.** The intuitive fix -- better phrases -- is recorded
as rejected WITH its reason, because it will otherwise be proposed again by
someone reading the 3-of-72 number without the grammar argument.

**Unmeasured, stated rather than buried.** 157 excerpt-backed entries have no
offline oracle and are neither clean nor dirty in this record's evidence. The
nine `art-163-*` entries are a triage candidate rather than a finding. And this
record's measurement cannot show any excerpt is CORRECT -- only that one disagrees
with the bundled current text.
