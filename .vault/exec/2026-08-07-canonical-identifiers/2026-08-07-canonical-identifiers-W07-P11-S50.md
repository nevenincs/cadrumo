---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:627d539aa710759a2a7c27798fe12efc379f1bb24fbb3edf26d0d33b90a1ea70'
step_id: 'S50'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# triage the second-pass sweep's findings into the existing namespace set, a new namespace, or an explicit non-identifier exclusion, recording the disposition of each

## Scope

- `src/cadrumo/core/identity/_namespace.py`

## Description

- Triage the 101 records the noun sweep found and the suffix heuristic could not see.
- Assign each to the existing namespace set, a new namespace, or an explicit exclusion.
- Record which findings belong to a DIFFERENT rule rather than to this taxonomy.

## Outcome

**Method, stated because it bounds the claim.** The 101 records carry 62 distinct field
names. Disposition is assigned BY CLASS rather than by 101 individual lines, and the
classes are exhaustive and disjoint, so every record falls in exactly one. A per-record
list would be longer without being more decidable, because the disposition follows from
what the name denotes, not from the site.

**Already enrolled — the sweep re-found what the campaign had already caught.** The
verification-code fields and the liquidación-key field are both members of the landed
namespace enum with aliases declared. Their appearance here is the sweep validating
itself rather than a new obligation: these are exactly the two concepts the suffix
heuristic missed, and the campaign enrolled them anyway by reading the surfaces.

**Belongs to an EXISTING type, not to a new namespace member.** The tax-identity names
(taxpayer, member, canonical tax identifier, the Cl@ve document-number fields) are the
subject of the tax-identity split already decided and rowed. The content-address and
digest names carry the digest alias. No new namespace member is warranted for any of them.

**Deliberate exclusions, matching the three free-text sub-populations already documented
on the enum.** Provider and bank names, model names from language-model vendors, SKUs,
diagnostic and warning codes, actor and profile labels, and delegated-access scope lists.
Each is either a label rather than an identity, or an identifier belonging to an issuing
authority that is not AEAT.

**Named false positives, which the census discloses rather than hides.** The Spanish
authentication provider's name matches the *clave* vocabulary; language-model role-evidence
prose matches *identity* while describing an instruction ABOUT identity; an
encryption-algorithm field matches *identifier* incidentally. These are correct behaviour
for a prose-reading instrument and the reason its output is a candidate set.

## Notes

**THE FINDING WORTH MORE THAN THE TRIAGE: ten production model fields hold a modelo
identifier while annotated bare `str`, and they sit in a hole between two instruments
that each believe they cover it.**

A standing rule requires modelo identifiers to be carried by the core enum, and a standing
gate enforces it. That gate's predicate is bare modelo-code STRING LITERALS in identifier
positions — a comparison against a quoted code, a dict keyed by quoted codes, a call
passing one. Every one of its own parametrised cases is a literal. **A field declared as a
bare string, holding a modelo identifier, contains no literal at all, so the gate has
nothing to find and passes.**

The suffix census could not see them either, because the field name carries none of the
identifier suffixes it matched. So the population is invisible to the value gate for
lacking a value, and invisible to the name census for lacking a suffix. The prose sweep
finds them because their documentation calls them identifiers.

Four sibling fields in the same sweep ARE correctly typed, which is what makes this a gap
rather than an open design question: the canonical type exists and is already used at
sites that chose it.

**This is NOT enrolled into this taxonomy, and the reason is a rule rather than a
preference.** A modelo code is a closed published vocabulary, so it belongs in the core
enum, explicitly not as an identifier-namespace member — the same ruling the decision
record already makes for the other closed AEAT code sets. Enrolling it here would create
the second authority this campaign exists to remove.

**It is handed off rather than absorbed, and it needs an owner.** The correct home is the
modelo-enum rule and its gate, whose detector would need to grow an annotation predicate
alongside its literal one. That is a change to another campaign's gate, so this record
names the gap, the count, and the reason both existing instruments are silent about it,
and does not reach into it.
