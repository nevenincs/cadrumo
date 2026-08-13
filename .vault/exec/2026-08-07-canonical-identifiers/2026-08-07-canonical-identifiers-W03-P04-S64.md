---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:bbfb0842793d9cb174c51731bb703a04d9bba445cbb225bae149bbb1467960be'
step_id: 'S64'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Decide whether resolve_identifier_namespace is enrolled or dropped, and record the outcome before S24 executes. Search production for a site holding an AEAT identifier value whose namespace is UNKNOWN at the point of use. A semantic sweep run for the 2026-08-10 ADR amendment found none, returning only the enum's own module, its own test and an in-flight census tool. The disconfirming observation that decides this row: a genuine consumer holds a value whose namespace cannot be read off its own field type. If every candidate turns out to hold a value whose namespace is already fixed by its field type, record that the resolver is DROPPED and retire IdentifierNamespace with it rather than leaving an exported concept nothing uses. Do not manufacture a caller to justify the symbol

## Scope

- `src/cadrumo/core/identity/`

## Description

- Run thirteen semantic sweeps for a production site holding an identifier whose
  namespace is unknown at the point of use.
- Confirm every candidate by targeted grep against its declaration, its call
  site, and the shape of the values it can receive.
- Enumerate every production classifier and every generically-named identifier
  parameter on the CLI surface, and adjudicate each against the deciding test.
- Measure separately whether the namespace taxonomy still earns its place.
- Record the ruling. No production code changed.

## Outcome

**Ruling: DROPPED.** No production site holds an identifier value whose
namespace both cannot be read off its own field type and could be answered by
shape. The two sibling enrollment rows close as adjudicated-no-implementation:
the resolver is not landed, and no unit coverage is authored for it.

The sweeps were run against the code index with these queries, verbatim:

- "resolve identifier namespace from a bare identifier string"
- "classify which kind of AEAT identifier an operator pasted, branch on whether
  it is a CSV or expediente or justificante number"
- "CLI argument accepting either a CSV or an expediente identifier, look up a
  document by whichever token the operator supplied"
- "try several identifier namespaces in turn until one matches, fall back to
  another lookup key"
- "error message telling the operator the value they supplied does not look like
  a valid identifier of the expected kind"
- "resolve a ledger transaction by an operator-supplied id prefix or full
  identifier"
- "MCP tool input accepting a document reference that could name several
  different record kinds"
- "read a token off an AEAT page whose kind is ambiguous, decide whether the
  scraped value is an expediente or a justificante number"
- "audit or census tool inventorying identifier fields across the codebase by
  namespace"
- "given an unqualified identifier string decide which record type it addresses
  and dispatch the lookup accordingly"
- "guess the kind of a value from its length and character shape, regex
  heuristics distinguishing identifier formats"
- "operator supplies a verification code to re-fetch a filed document from the
  AEAT public cotejo endpoint"
- "a stored identifier whose kind was not recorded, ambiguous provenance
  requiring the reader to work out which namespace it came from"

Each sweep was paired with a confirming grep: an enumeration of every
`classify_*`, `detect_*` and `infer_*` callable in production, an enumeration of
every generically-named identifier parameter on the CLI surface, and a
declaration-site read of every bare-`str` field named for one of the AEAT
namespaces.

### The decisive candidate

`src/cadrumo/application/ledger/_evidence_reference.py` is the one production
site that genuinely holds a namespace-ambiguous identifier. Its own module
docstring states that the transaction's purchase-invoice evidence reference
addresses two bucket-scoped id spaces, and the field's `str` type does not say
which. It passes the first half of the deciding test and fails the second.

It resolves by EXISTENCE against the actual record stores, which is strictly
stronger than shape and which it must do anyway, because it needs the record and
not merely the namespace. Neither of its two spaces is a member of the taxonomy,
so a resolver over the current members could not name the candidates it must
choose between. And three of its five outcomes turn on bucket ownership and
invoice kind, which shape cannot answer at all. Verdict: NOT a consumer, and the
most instructive near-miss in the sweep — the one genuinely ambiguous site in the
tree demonstrates why shape resolution is the wrong mechanism for the question it
asks.

### The remaining candidates

`src/cadrumo/application/workflow/_profile_bucket_scan.py` resolves a value that
may be a UUID bucket id or an operator display label, trying the UUID-direct
lookup first and falling back to a manifest scan. Structurally the closest
analogue to a namespace resolver on the whole surface. Neither space is a
taxonomy member, and like the evidence reference it resolves by existence rather
than shape. Verdict: NOT a consumer.

`src/cadrumo/adapters/outbound/google/_document_link_resolver.py` resolves a
document link reference that may be a Drive URL, a Drive file id, a Gmail link or
an arbitrary URL. It branches on the DECLARED source enum the operator supplies
alongside the value, never on the value's own shape, and its namespaces are the
non-AEAT issuing authorities the taxonomy already excludes by name in its own
exclusion comment. Verdict: NOT a consumer.

`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py` is the only
production callable that decides an identifier's kind from its shape. It
separates DNI from NIE, which are sub-kinds within the tax-identifier concept
rather than members of this taxonomy, and it is a validation gate rather than a
namespace question. Verdict: NOT a consumer.

`src/cadrumo/application/ledger/_id_resolution.py` resolves an operator-supplied
transaction id prefix to a full id. The ambiguity is prefix-versus-full within
ONE namespace, which is a completion problem and not a namespace problem.
Verdict: NOT a consumer.

`src/cadrumo/domain/user_profile/_schema.py` documents in its selector-path
lookup that its callers mix selector tokens with identifiers from other
namespaces and must be able to ask without knowing which they hold. The ask is
answered by membership in the profile schema's own declared token set; the other
namespaces are never enumerated or classified, and an unknown token returns
absence. Verdict: NOT a consumer.

Every generically-named CLI identifier parameter carries its namespace in its own
option or argument name and reaches exactly one typed downstream space: the
filed-capture expediente option, the capital-goods register identifier, the
evidence review reference, the consent re-derivation reference, the IVA wallet
evidence locator, the doclink reference, and the counterparty tax identifier.
Verdict: NOT consumers; namespace fixed by the parameter.

`dev/identity/identifier_noun_census.py` is the in-flight census the prior sweep
surfaced. It classifies FIELDS by their declared annotation through a static
walk, never VALUES by shape, it imports nothing from the taxonomy, and it is dev
harness rather than production. Verdict: NOT a consumer.

### The taxonomy is measured separately, and stands

The premise that the namespace enum has no role beyond feeding the resolver is
stale and was not acted on. The enum is not retired and was not touched.

All seven per-namespace pydantic aliases the enum indexes carry real production
consumers outside the identity package: the CSV alias in four files, the
expediente alias in five, the box-number alias in four, the certificado alias in
three, and the clave, registry-snapshot and presentation aliases in two, two and
one respectively. Every enum member's documentation names the alias that carries
its constraint shape, so the enum is the index over a consumed family rather than
a free-standing concept. It additionally carries the campaign's non-membership
exclusions as a code comment, carries the second-pass triage dispositions, and is
the vocabulary the still-open ratchet gate will assert against. The taxonomy
earns its place on grounds wholly independent of the resolver.

## Notes

The tree carries an explicit standing position against the mechanism this
resolver would have supplied. The ledger identity-roles model records that a
counterparty's country is never inferred from the identifier's own shape, and the
presentation-id alias records that every receipt-to-filing comparison in the app
runs on the CSV namespace precisely because a caller holding a register value
cannot supply a presentation id. Both are prior rulings that shape is not a
trustworthy source of namespace facts here, which is corroboration for the drop
rather than merely an absence of callers.

No production code, test or configuration was modified by this Step, so no gates
were run and none are owed.
