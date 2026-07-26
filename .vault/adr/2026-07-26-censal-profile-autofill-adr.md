---
tags:
  - '#adr'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-censal-profile-autofill-repeatable-required-field-emission-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace censal-profile-autofill with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `censal-profile-autofill` adr: `repeatable required field emission and predicate access` | (**status:** `proposed`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

A required field declared on a repeatable profile section binds for no taxpayer.
Thirteen of the fifteen fields the schema marks required sit on repeatable
sections, and a section with no rows yields no rows to validate, so nothing is
emitted for any of them.

Two changes are needed and they cannot be decided separately. The emission
helper must produce a required path for a section that has no rows but applies to
this taxpayer; and whatever decides "applies to this taxpayer" must reach the
canonical economic-activity predicate from a flat value mapping. Deciding
emission alone licenses roughly a third of the change and leaves the surface that
would host the condition holding a predicate it cannot call. Both failures were
established by implementing the emission half and finding it inert, then
implementing the access half and finding it crashes; the measurements are in
`2026-07-26-censal-profile-autofill-repeatable-required-field-emission-audit`.

The defect appears a second time in a sibling section, which is why this record
treats it as a shape rather than as one field's problem. The attribution socios
section declares a member role required, and no form carries it and no code reads
it - the modelo's per-member field is residency, and the distinction that role
names sits at entity level. So one section declares something right that nothing
enforces, and its sibling declares something that nothing needs. Both are the
schema asserting what no consumer honours, and a fix shaped only around the first
would leave the second standing.

## Considerations

- Emitting unconditionally regresses the displayed-completeness defect verbatim;
  the per-section condition is load-bearing rather than tidiness (audit,
  blanket-emission).
- The required-field helper and the conditional-requirement helper serve
  different, overlapping consumer sets, and only the first reaches the operator's
  overview (audit, consumer-split).
- The policy for who owes an activity description is already settled and routes
  through a shipped, legally-grounded predicate rather than a new one.
- That predicate takes a domain aggregate; the helpers hold a flat mapping, and
  the one sanctioned coercion between them is strict (audit, predicate-access).
- A resolver's required set and the schema's required set are legitimately
  different: the resolver enforces what its row model consumes, the schema
  declares what the profile must hold. Making one derive from the other would
  force a resolver to enforce fields its modelo does not carry.
- The same section family holds a second instance of this record's own defect: a
  field declared required that no form carries and no code reads, so the
  declaration is a wall an operator must satisfy for nothing.
- The registry layer already solved the shape of "each family declares its own
  validator, dispatched by a closed kind" in
  `2026-06-14-bindings-interface-hardening-adr`.

## Considered options

**Extend the conditional-requirement helper.** Needs no new symbol and reaches
four consumers immediately. Rejected: it does not reach the overview, so the
enforcing surface would report what the displayed surface cannot, reopening the
drift a prior fix closed.

**Emit unconditionally from the row loop and suppress at each call site.**
Rejected twice over: the suppression would have to exist identically in two
consumers, so it must be shared and therefore named anyway, and until it is the
emission regresses every profile with no rows in any repeatable section.

**Read the income categories and entity type directly from the value mapping.**
Two lines, obviously correct, and rejected: it is a fourth statement of a concept
that already has three, and the concept is a policy about which taxpayer owes
something rather than a local detail, so every copy is a place the policy can
diverge without anything failing. The refusal must be stated explicitly in the
implementation, because the next reader will otherwise reach for it on exactly
the grounds that make it tempting.

**Build the taxpayer aggregate inside the helper via the existing coercion.**
Rejected on principle rather than circumstance: that coercion is strict and
raises on undeclared tokens, and a surface whose purpose is untrusted input
cannot depend on a strict projection of that input. The row loop is a worse host
than the validator was, because it also serves the display.

**Declare the condition in the schema.** Not rejected, deferred: the schema's key
set carries no conditional-requirement mechanism, so this is a loader and model
change as well as a data one, and it is larger than the problem in front of it.
It remains the right long-term home if a second section ever needs a condition.

## Constraints

The applicability question is open and cannot be closed by search: whether a
per-section applicability mechanism already exists elsewhere in the tree. Four
concepts in this campaign were found under names no sweep would reach, two of
them by reading a neighbouring decision rather than by searching. A mechanism of
that kind can be named anything, so a symbol sweep samples rather than proves.
**Answering it requires semantic discovery over the code corpus, and this record
must not be implemented until that has run.**

The nearest known adjacent statement is the setup wizard's per-question
visibility condition for this same taxpayer. Any implementation must reconcile
against it rather than adding a fourth statement beside it.

This record depends on the settled policy for who owes an activity description
and on the repeatable declaration staying, both of which are decided and stable.

## Implementation

The condition lives with the emission helper, because that is the only place both
the enforcing and the displayed surface observe, and keeping them on one helper
is the property a prior fix established.

A section-keyed applicability lookup holds one entry today. A section absent from
the lookup keeps its current behaviour exactly - silent when it has no rows -
so the three sections that are correctly silent stay silent by having no entry
rather than by a carve-out. This mirrors the registry layer's validator dispatch
keyed by a closed kind, where absence from the table is itself the declaration.

Access is resolved by giving the predicate a mapping-shaped entry point beside
its aggregate-shaped one, sharing one implementation, so the flat-mapping callers
reach the same legally-grounded logic without a coercion and without a
restatement. The strict coercion is not used and the implementation says why at
the site, so the closed door is legible where the temptation is.

Tests pair each "given the condition, the guard behaves" arm with a "given the
real upstream, the path actually arrives" arm. An anti-tautology arm alone proves
the guard would fire given input and cannot prove anything supplies it, which is
how the first attempt passed while being inert.

## Rationale

The knockout is the consumer split. Every alternative that avoids a new symbol
also avoids the overview, and a completeness rule the operator cannot see is the
defect this campaign already fixed once. Once the condition must reach both
surfaces, it must live in the shared helper, and once it lives there it needs a
name - so the naming is forced by the requirement rather than chosen for
convenience.

Against the direct read, the argument is not hypothetical and the instance is
this record's own history. The concept already has three statements: the setup
wizard's per-question visibility condition, the IVA-regime requirement predicate,
and the legally-grounded one carrying LIRPF art. 99 and RIRPF art. 109. **A
fourth was ruled and withdrawn this evening**, and only because the third was
found by sweeping alternative names - the ruling that would have created it named
the existing predicate in its own brief without connecting the two.

So the direct read is not a hazard the record is imagining. It is the exact route
by which the fourth statement would have entered, attempted in this file, hours
ago, by someone holding the pointer to the thing being duplicated.

The copy is also worse than an ordinary duplicate. The canonical predicate is
three-valued and legally grounded: undeclared income categories answer neither
yes nor no, and that answer fails closed by design. A direct read would have to
re-derive those semantics, and a later change to the legal basis would update the
predicate and leave the copy behind, answering differently for the taxpayer who
sits between them without anything failing.

This record deliberately does not argue that a resolver restating the schema is
itself the hazard. The neighbouring attribution resolver enforces four of the
schema's five required fields, and that is correct rather than drifted: it
enforces exactly what its row model consumes, and the fifth field is one the
modelo does not carry per member at all. A resolver's required set and the
schema's are legitimately different sets answering different questions - what
this declaration must be filed with, versus what this profile must hold. An
implementation that made either derive from the other would break the one that
is currently right.

## Consequences

Thirteen required fields become enforceable rather than decorative, and the
schema stops declaring what nothing checks.

The lookup is a new authority and will attract entries. Its one-entry shape is
deliberate: absence is the default and each addition is a decision, which is the
property that keeps the three correctly-silent sections silent for a stated
reason rather than by accident.

Giving the predicate a second entry point widens a domain surface for an
application-layer caller. The alternative was a fourth statement of the concept,
and this keeps one implementation.

The risk this record does not remove is the open applicability question. If a
mechanism does exist elsewhere, this creates the duplicate it was written to
avoid - which is why the constraint above is a precondition on implementing
rather than a caveat on the decision.
