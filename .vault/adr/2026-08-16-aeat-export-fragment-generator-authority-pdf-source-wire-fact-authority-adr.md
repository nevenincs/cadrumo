---
tags:
  - '#adr'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-16'
modified: '2026-09-14'
body_schema: 'body-v1'
body_hash: 'sha256:98dc0cbcca08716b1476ec819d9d1e80dbedb4370541f6680665d541202e6d89'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit]]"
---
# `aeat-export-fragment-generator-authority` adr: `PDF-sourced designs state wire facts in prose, so every numeric anchor is profile-eligible` | (**status:** `accepted`)

## Problem Statement

`2026-08-10-aeat-export-fragment-generator-authority-adr` is scoped to WORKBOOK
anchors by its own words, in three binding places: its problem statement ("when
the exact workbook field anchor carries no usable content"), its chosen option,
and its constraint naming the render profile "the sole reviewed authority for
wire facts absent at their exact workbook field anchors". Every modelo generated
under it -- 210, 232, 303 -- is workbook-sourced.

Three backlog modelos are PDF-sourced: 347, 193 and 296. A PDF design has no
Contenido column at all; the parser fills `content` with the field's descriptive
prose. `project_render_profile_eligibility` selects fields whose
`aeat_type in {"Num", "N"}` AND whose `content` is blank, so for a PDF design it
returns the empty set: the type is spelled `Numérico`, and the content is never
blank. **An empty render profile therefore satisfies the exhaustive-coverage
requirement completely, and the design generates with no declared numeric
format, sign policy or decimal placement.**

## Considerations

- Evidence is in
  `2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit`,
  which measures the four prose shapes that sit side by side in Modelo 347: a
  field stating sign and decimals in full, a field stating only width, a
  cross-reference stating nothing, and a purely semantic description.
- So neither available reading is correct. "Content non-blank means the fact is
  present" is false for three of those four; "PDF prose never states a wire
  fact" is false for the first.
- The parent ADR's principle is not in question and must hold: a profile may not
  override or conflict with a wire fact present in the official source.
- The corpus is 82 PDF designs against 134 workbooks, so this is not a corner.

## Considered options

- **Leave PDF sources out of scope (status quo).** Honest, and blocks 347, 193
  and 296 permanently.
- **Read PDF prose mechanically into wire facts.** Rejected on sight: parsing
  natural language into sign and decimal policy is exactly the inference the
  parent ADR forbids.
- **Make every numeric anchor of a PDF design profile-eligible, and require the
  reviewed rule to AGREE with any wire fact its prose does state (chosen).** The
  profile stays the sole reviewed authority; the source keeps its veto.

## Constraints

- Numeric-type selection must match on an accent- and spelling-insensitive stem,
  as `_naturaleza_or_none` already does for exactly this reason, so `Numérico`
  is recognised beside `Num` and `N`.
- `content` must stop being read as evidence that a wire fact is present, for
  PDF sources only; workbook behaviour is unchanged.
- Where the prose DOES state a fact, the reviewed rule must agree with it, and
  its evidence must record that the source stated it rather than claiming
  reviewed policy.

## Implementation

`project_render_profile_eligibility` gains the two numeric-anchor changes described
above. The reviewed signed-composite extension below is the only additional
eligibility and derivation change authorized here; it does not authorize automatic
interpretation of PDF prose.

Numeric selection normalises the AEAT type -- accents stripped, lower-cased --
and admits `num`, `n` and any `numeric` stem, so the parser's canonical
`Numérico` is recognised beside a workbook's `Num` and `N`. The parser already
canonicalises a PDF naturaleza before it reaches the intermediate, so this reads
one vocabulary rather than inventing a second.

The content test becomes conditional on the source shape, read from the field
itself rather than threaded in: a workbook field carries a `source_cell` and a
PDF field does not, which is exactly the distinction the anchor model already
documents. Where the cell exists, a non-blank `content` still means the design
stated the fact and the field stays ineligible. Where it does not, `content` is
descriptive prose rather than a structured wire-policy cell. Its presence does not
establish a render policy, so the numeric field is eligible and a reviewed rule
must supply one; any explicit source fact retains its veto over that rule.

Source-reserved slots stay ineligible on both paths, unchanged: a reserved run
has no wire fact beyond being filler.

**The workbook assumption runs through four layers, not one.** Three are in
`_render_profile.py` and are landed:

1. `project_render_profile_eligibility` selected on `{"Num", "N"}` and on a blank
   Contenido cell -- both above.
2. Singleton coverage matched `field.aeat_type != rule.aeat_type` by string, so a
   rule declaring `Num` could never cover a field spelled `Numérico`. A singleton
   rule pins `aeat_type = "Num"` and `sign_policy = "unsigned"` by construction,
   so its token carries no information beyond "numeric, unsigned"; the signed `N`
   form appears only in a width-17 membership rule, which keeps exact matching.
3. `RenderProfileAnchor.source_cell` had no default, so a PDF anchor could not be
   authored at all -- TOML cannot express an explicit null.
   :class:`SemanticMapAnchor` already defaults the same field for the same
   reason, and this now mirrors it.

The fourth is `_normalise_field` in `_export_tree.py` and is **not landed**. It
casefolds the AEAT type against `_TEXT_TYPES` and `_NUMERIC_TYPES` -- the
workbook tokens -- and refuses anything else as an unsupported type, so a
`Numérico` field never reaches a renderer at all. Its numeric branch then routes
on the same blank-content test: a non-blank `content` sends the field to
`_numeric_derivation`, which reads the wire fact out of the cell, instead of to
`_render_profile_numeric_derivation`. For a PDF design that would derive the
representation from descriptive prose and bypass the reviewed profile entirely.

So the renderer needs exactly the two changes eligibility received -- recognise
the canonical spellings, and route PDF fields to the profile rather than to
content derivation -- plus the text-type spellings (`Alfanumérico`,
`Alfabético`, `Blancos`) for the non-numeric anchors. That file is held by an
in-flight campaign, so it is named here rather than edited.

### Reviewed signed composites at unsplit PDF anchors

The scope established by `2026-08-10-aeat-export-fragment-generator-authority-adr`
is extended to reviewed, source-explicit signed monetary composites carried by
unsplit alphanumeric PDF anchors. Grounding and implementation boundaries are
recorded in `2026-09-14-registry-edition-authoring-signed-composite-export-reference`.
Automatic prose-to-policy inference remains rejected.

A dedicated typed render-profile rule, bound to the exact source reference,
SHA-256 and parser anchor, owns the reviewed interpretation. It declares one
leading sign slot, space for non-negative values and `N` for negative values,
followed by an unsigned magnitude with explicitly reviewed integer and fractional
widths. Admission is limited to the existing two-decimal monetary representation.
The raw alphanumeric source nature remains unchanged; neither the parser nor
semantic map relabels it as numeric.

Source-agreement validation may verify the rule but must never create, complete
or modify one. It must establish exactly one sign slot at the outer start, a
contiguous magnitude occupying the remaining span, and integer and decimal ranges
that partition that magnitude exactly. Coordinates, widths, digit counts, scale,
absence of embedded sign or decimal separator, and the complete sign convention
must agree with the reviewed rule and official source. Missing components,
duplicate or contradictory clauses, gaps, overlaps, unsupported scale, conflicting
rules, uncovered reviewed anchors, or source/anchor drift refuse the design. An
invalid or incomplete claimed composite cannot fall back to ordinary text.

The generated field represents one economic value through the existing monetary
codec and reserved blank-or-`N` sign position. It does not introduce separately
calculated sign and magnitude values, formatted-text producers, another codec,
or changed rounding or precision rules. Ordinary text, workbook eligibility,
literal and reserved-slot precedence remain unchanged. Already parsed split
leaves retain the policy established by
`2026-08-18-aeat-export-fragment-generator-authority-split-part-export-value-policy-adr`;
this extension does not authorize recomposing them into parent fields.

Publication requires exact-anchor coverage, distinct typed derivation provenance,
deterministic regeneration, and detector controls for every refusal above. Real
rendering must prove zero, positive and negative values, optional absence, the
maximum fitting magnitude and overflow, followed by complete target filing-output
proof. Generated declarations and provenance remain CLI-owned. This authorization
establishes no implementation or publication completion claim.

## Rationale

The measured evidence rules out both simpler readings. Modelo 347 carries, side
by side, a field whose prose states sign and decimals in full, one stating only
width, a bare cross-reference, and a purely semantic description. "Content
non-blank means the fact is present" is false for three of those four; "PDF prose
never states a wire fact" is false for the first. Only a per-field reviewed
judgement can tell them apart, which is precisely what the render profile is for.

Making every numeric PDF anchor eligible is therefore not a widening of the
profile's authority but a correction of its reach: the parent ADR already made it
the sole reviewed home for absent wire facts, and PDF designs were left out
because the mechanism was built against workbooks, not because their facts are
present.

The source keeps its veto. Where prose states a fact, the reviewed rule must
agree with it, and the rule's evidence must record that the source stated it
rather than claiming reviewed policy -- so the profile can still never override
the official design.

## Consequences

- Modelos 347, 193 and 296 become generatable through the sanctioned path. 347
  is ready immediately: its casillas are authored and its semantic map joins
  cleanly.
- Every PDF numeric anchor now demands a reviewed rule, so authoring a PDF design
  costs more than a workbook one. That cost is the point: it is the review that
  was silently skipped before.
- Workbook designs are untouched. The content test still applies wherever a
  `source_cell` exists, so 210, 232 and 303 keep their current eligibility sets
  exactly.
- The empty-profile false green closes: a PDF design can no longer satisfy
  exhaustive coverage by covering nothing.
