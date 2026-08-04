---
tags:
  - '#adr'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:8780a099f99550ae13b7f8ae66353526bd484d10360926793b9770e2b637c738'
related:
  - "[[2026-08-04-profile-derived-selectors-research]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-07-01-modelo-100-minimo-descendientes-engine-adr]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-research]]"
---

# `profile-derived-selectors` adr: `Declare derived profile paths as data and refuse operator writes to them` | (**status:** `accepted`)

## Problem Statement

Twenty profile schema fields declare a value the engine computes. Because the manager page
walks the schema, each renders as an editable row, and because the injectors decline to
overwrite a stored fact, a value typed into one suppresses the law computation with no
diagnostic. The declarations also grow by three per filing year without bound, which is
the symptom that prompted the investigation.

`2026-08-04-profile-derived-selectors-research` records the measurement, the four
disagreeing fact-index builders, the caller cost of the obvious alternative, and the two
standing rulings that block it. A decision is needed because the growth is unbounded by
construction and the override channel is an unaudited path around the calculation engine.

## Considerations

- The temporal axis is already carried twice — registry revision windows for the law,
  source facts for the taxpayer. A third would be driftable.
- The binding resolver implements no window ordering, so any design leaning on effective
  windows would have to build that first; the projection-side caller cost is a project-wide
  sweep, and two standing rulings govern it.
- Once any dated fact exists at a path, an undated write from an unmigrated door is
  permanently shadowed. Incremental adoption of windows fails silently.
- Path legitimacy and value admissibility are already separate judgments in this codebase,
  and the existing value authority expressly declines to judge absence.
- A refusal confined to the TUI leaves the CLI and programmatic doors open. A refusal at the
  write door leaves a lying row on screen until the declarations go.
- The engine's derivation is currently incomplete against Art. 58/61, and the override is
  today the only correction channel — see `2026-08-04-minimo-descendientes-eligibility-adr`.

## Considered options

**Declare the derived paths as a year-parameterised pattern namespace in the profile
schema, refuse operator writes to them, and let the injectors own the computation.**
Removes the rows structurally, closes the override at a boundary every door consults, and
reduces a new filing year to registry work. Chosen.

**Collapse each family to one year-less declaration and move the year onto the fact's
effective window.** The original hypothesis. Rejected: a derived value has no window of its
own, the value would remain stored and writable so the override survives, the consuming
resolver implements no window ordering, and the prerequisite is blocked behind an accepted
but dormant snapshot ruling.

**Group or collapse the rows in the TUI.** Rejected by the operator, and it leaves both the
growth and the override untouched.

**Declare a per-field derived attribute rather than a pattern namespace.** Rejected: it
keeps one declaration per year, so the growth survives the fix.

**Route the refusal through the existing value-refusal authority.** Rejected on structure —
see Rationale.

## Constraints

- Hard ordering: the write refusal must not land before the eligibility predicate is
  complete, or a correctable under-declaration becomes uncorrectable. That record owns the
  predicate, this one owns the refusal.
- The registry contract validator raises on any binding selector that resolves to nothing,
  and that validation is wired into per-modelo registry build. Any commit that leaves a
  selector unresolvable stops the registry loading and kills suite collection. The pattern
  namespace must therefore land additively while the declarations still stand.
- The namespace declaration is not divisible. The loader hydrates the schema model from two
  hand-picked top-level keys, so a new array declared in TOML alone is parsed and silently
  dropped, while passing the key through before the model declares the field raises at every
  schema load because the model forbids extra keys. TOML, model and loader are one commit.
- The filing-year placeholder must compile to a four-digit, terminally anchored fragment.
  Two of the five patterns are prefixes of one another, so a permissive placeholder lets the
  shorter swallow the longer, which both makes the anti-rot gate unable to detect the longer
  pattern's deletion and makes the derived-path test over-broad.
- The refusal must be evaluated before the field-index lookup, not merely before the
  unknown-path arm. While the declarations stand the lookup succeeds and that arm never
  fires, so a check placed after it would accept the write.
- Locale catalogues are maintained only through the locales CLI, per `aeat-locales-cli`.
- The two consumers of the value-refusal kind enum branch exhaustively with deliberate
  no-fallback arms, one of them pinned by a test. The derived-path helper is a sibling of
  that authority and now shares its module, so co-location must not become conflation.
- The pattern namespace is a declaration of engine ownership, never a resolution route for
  values. It must not be extended to the schedule-predicate, deadline, cross-reference or
  export-header consumers, which read disjoint namespaces, nor to the binding resolver's own
  fact index, where it would make a declared but uninjected path look resolvable.
- Registry binding files are not swept: they keep their canonical selectors, and the
  pattern namespace supplies the resolution route.

## Implementation

A top-level derived-selector array is added to the profile schema authoring tree, hydrated
by the existing loader into a typed model. Each entry declares a path pattern carrying a
filing-year placeholder, the source paths the value derives from, the operator surface that
edits those sources, and the governing legal references. Five entries replace twenty field
declarations. The registry contract validator resolves a binding selector against the
declared field paths, the model selectors, and now the patterns; an anti-rot gate requires
every declared pattern to match at least one live binding, so a pattern nothing consumes
fails loudly.

The refusal is a path-legitimacy judgment and lands beside the existing one rather than
inside the value authority. A single domain-level helper answers whether a path is derived,
and the profile validation service consumes it as a blocking issue ordered before the
unknown-path check, with a message naming the surface that edits the real source facts.
Because every write door already converges on that validator, the CLI, wizard, cotejo and
bundle-import paths are covered by the one refusal.

That convergence carries a consequence the refusal cannot be shipped without. The validator
judges an incoming batch as a whole, and the descendant projection every descendant-writing
door uses emits one derived aggregate alongside the per-descendant source facts it also
writes. A refusal landing while that emission stands would refuse every legitimate
childcare save — the precise surface the refusal message directs the operator to, for the
precise scenario the aggregate exists to compute. Retiring the emission alone is equally
unsafe, because a formula-consumed casilla depends on the value. The emission's retirement
and its replacement by calculate-time injection therefore ride in the same commit as the
refusal, not with the later deletion.

The overview projection skips derived paths from that same commit. This is not a
presentation-layer hide: the refusal lands with it, and the filter exists to close a window
in which a row would still render and the at-the-box value check would pronounce admissible
what the write door then refuses.

The declarations and their locale entries are then deleted in a single explicit-path
commit, after which the remaining injectors are hardened: the skip-if-present guards become
compute-always so a stray stored fact cannot win, the year-gating frozensets are replaced by
gating on registry content so a new filing year needs no code edit, and the parse failure
that silently under-counts a descendant becomes a raised refusal. A derived-scoped advisory
reports a selected derived binding that still resolves to nothing — narrow by construction,
so every fire is a structural gap rather than an optional fact's ordinary absence.

The dormant selector-level as-of channel is retired in its own commit rather than left as a
second unread temporal axis beside the pattern placeholder.

Two of the twenty-two fields are genuine operator input and keep their declarations and
their year suffix. Their year-less-key redesign belongs to the deferred windows campaign.

## Rationale

The decisive argument against effective-dating is that it does not solve the problem: the
value would remain stored and operator-writable, so the override channel — the actual
hazard — survives untouched, while the campaign would acquire a project-wide caller sweep
and a collision with two standing rulings. Declaring the paths as data removes the rows,
closes the channel, and stops the growth with no window semantics touched anywhere.

On placement of the refusal, the research establishes that this codebase already separates
path legitimacy from value admissibility, and that the existing value authority is scoped
to judging a value against a field declaration and expressly declines to judge absence. A
derived-path rule refuses every value including a clear, and after the declarations are
deleted there is no field declaration left to judge against — so routing through that
authority would force keeping the twenty declarations alive and defeat the change. The
sibling placement is not a second opinion on the same question: the two rules judge
disjoint questions over disjoint domains, so a contradictory answer is unconstructible
rather than merely discouraged. It also avoids extending an enum whose two consumers branch
exhaustively by deliberate design.

The growth argument settles the namespace shape. A per-field attribute would classify the
fields correctly and still add one declaration per year; only a pattern removes the year
from the declaration entirely.

## Consequences

The manager page loses roughly twenty rows immediately and gains none per filing year. A
new filing year becomes registry work alone — bindings and parameters — with no schema
field, no locale entry, no TUI row and no code constant.

The override channel closes. That is the point, and it is also why this record cannot land
before the eligibility predicate is complete; the two records must be sequenced, not merely
cross-referenced.

Compute-always removes any ability to hand-override the derived aggregate. Should a future
legal edge case genuinely require one, the sanctioned route is an explicit registry
mechanism with provenance, not a stored fact — recorded here so the door is not quietly
re-opened.

A one-stage window exists between the refusal and the deletion in which the declarations
still stand; the overview filter is what makes that window safe.

Deliberately not addressed: the general per-binding silent-skip class, on the grounds that a
blanket advisory would false-fire on legitimately absent optional facts and train operators
to ignore it. The narrow derived-scoped advisory covers the sub-class where every fire is
real. A related standing defect — a casilla that hard-fails because a declared operator
field has no entry surface — is left exactly as loud as it is today and needs its own
record, together with the entry-surface work for the eligibility inputs.
