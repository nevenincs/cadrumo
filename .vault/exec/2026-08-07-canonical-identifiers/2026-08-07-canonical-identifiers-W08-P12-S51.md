---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1ec482cf9e1a47a5341359f9ff9cc76876c5a088bfa719312ea72724e5a3f7f2'
step_id: 'S51'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# decide, and record the reason, whether every PII-shaped fold-in in `object_key_grammar` (`{member_nif}`, `{perceptor_nif}`, `{perceptor_tax_id}`) is pre-hashed uniformly or intentionally left raw beneath the outer `HashedLookup` HMAC, given the column is deterministically hashed either way

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`

## Description

This is a decision-only Step. No production code was modified.

- Enumerate all 74 `SecureObjectNamespaceDefinition` declarations in
  `_namespace_registry.py` and extract every `object_key_grammar` mechanically rather
  than by eye.
- Read `HashedLookup` in
  `src/cadrumo/adapters/persistence/storage/crypto/_encrypted_columns.py` and the
  `object_key` column declaration in
  `src/cadrumo/adapters/persistence/storage/sql/_orm.py` to test the Step row's premise
  directly instead of inferring it from the class name.
- Trace every identifier-bearing key builder to its implementation:
  `member_observation_key` and `iva_wallet_decision_key` in
  `src/cadrumo/application/calculations/_observations_repository.py`,
  `retencion_observation_key` in
  `src/cadrumo/application/aggregation/_retencion_observations_repository.py`,
  `percepcion_observation_key` in
  `src/cadrumo/application/aggregation/_percepciones_observations_repository.py`, and
  the counterparty key in `src/cadrumo/application/ledger/_counterparty_establishment.py`.
- Follow the composed natural key outward to every surface that could render it: the
  remote mirror name builder, the mirror manifest digest, the namespace-registry
  refusal messages, and the logical-path diagnostic marker.
- Probe the two key builders as pure functions with a synthetic token to confirm the
  canonicalisation divergence empirically rather than by reading alone.

## Outcome

### The measured inventory

Seventy-four namespace definitions are declared. The Step row named three PII-shaped
placeholders; the measured set of grammars that fold a natural or legal person's tax
identifier into the key is seven, and the row's classification of two of them was
inverted.

Pre-hashed, and the grammar says so — six:

- retencion observations, folding the perceptor identifier through a declared digest.
- withholding observations, folding the perceptor identifier through a declared digest.
- IVA wallet reconciliation decisions, folding the taxpayer identifier with the target
  year and period.
- IVA wallet reconciliation decision events, folding the decision identity and payload,
  which carries the taxpayer identifier transitively.
- AEAT IVA wallet observations, folding the taxpayer identifier with target year,
  period and capture instant.
- Ledger confirmed counterparty facts, whose key is a full-width hex digest of the
  canonical identifier. The grammar token names the key rather than the derivation, so
  this one is pre-hashed in substance but silent about it in the declaration.

Raw — one:

- Calculation observations, whose grammar carries an optional trailing member
  identifier segment appended verbatim to the single-filer key.

The row listed the two perceptor placeholders as if they sat on the raw side. They do
not: both are already declared inside a digest, and their builders route through the
shared canonical hashing helper. The genuine divergence is a single site, not three.

Adjacent but deliberately excluded from the PII set after checking the derivation: the
profile-scoped grammars key on a bucket identifier that is a UUID, not an
identifier-derived value; the Google surfaces key on an operator-chosen profile name;
the justificante grammar keys on the AEAT verification code, which identifies a filing
rather than a person.

### The premise holds, with one qualification

The row's premise is that the column is deterministically hashed either way. Confirmed
at the implementation. The `object_key` column is declared as the keyed-lookup type,
whose bind path derives a sub-key from the active data encryption key via HKDF under a
stable context and returns an HMAC-SHA256 over the UTF-8 natural key. The plaintext is
not recoverable from the stored digest. So at rest, a key that folded a raw identifier
and a key that folded a digest of one are indistinguishable: both are 32 bytes of
keyed MAC under a key the operator holds.

The qualification is that the bind path also accepts already-computed 32-byte input and
passes it through without hashing. That pass-through is exercised only by read paths
operating on digests already loaded from rows; no production write path hands it a
natural key as bytes. So the premise holds for every write in the tree today, but it
holds by caller discipline at one point rather than by construction.

The premise was also tested outward, not just at the column. The off-host mirror names
objects from a digest over the namespace and the already-hashed key bytes, and the
operator-visible remote filename label is derived from the namespace, never from the
key. The namespace refusal that embeds the offending key in its message fires only on
the singleton branch, where no identifier-bearing grammar exists. The logical-path
diagnostic marker does build a path from the natural key, and it is exported publicly,
but both of its call sites pass a singleton default key. So no path in the tree today
renders a raw identifier outside the hashing path.

### The security argument is a wash; the correctness argument is not

Stated honestly: given the outer keyed MAC, pre-hashing the identifier first adds no
cryptographic protection at rest. An attacker holding the encrypted store without the
key learns nothing either way; an attacker holding the key can recompute candidate
digests against a guessed identifier under either scheme, because both are
deterministic over a low-entropy value drawn from a small national identifier space.
The pre-hash does not defend against a partially compromised key in any meaningful
sense, and there is no live log, error or export channel through which a composed key
leaks today. Anyone claiming a real confidentiality gain from the pre-hash would be
overstating it.

What the pre-hash does buy is blast-radius containment for a class of future edit. It
removes the identifier from the entire in-process natural-key surface by construction,
so a later diagnostic string, refusal context or marker that echoes an object key
cannot leak an identifier no matter who writes it. The declared-refusal machinery
already propagates a nested reason into a validation error context, so that channel is
one edit away from existing rather than hypothetical. That is a hygiene and
defence-in-depth argument, not a cryptographic one, and it is recorded here as such.

The decisive argument is elsewhere, and it is correctness rather than confidentiality.
Every pre-hashed sibling routes its identifier through the shared canonical identity
token before digesting, so a padded or lower-case declaration and its canonical form
address the same row; the retencion and percepcion suites assert exactly that
equivalence. The raw member path does not. Its builder validates the token's shape and
returns it unchanged, and the persisted observation model carries no normalising
validator on that field, so the declared value reaches both the payload and the key
verbatim. A probe over the builder as a pure function confirms it: a case-variant
rendering of one synthetic member token produces a different storage key from its
canonical rendering, so one grupo member declared inconsistently across two captures
persists as two rows. That is a silent duplication in the cross-member fan-in the key
widening exists to serve — the same class of defect the identity-token helper documents
as its own reason for existing.

### Ruling

The canonical form is uniform pre-hashing: every PII-shaped fold-in routes its value
through the canonical identity token and is folded into the key as a digest, never
verbatim, and the grammar declares the derivation rather than naming the resulting key.

The ruling is grounded on identity canonicalisation and blast-radius containment, not
on an at-rest confidentiality gain, because there is none. Uniformity is worth having
on its own terms as well: with one site diverging, a reader cannot tell whether a raw
fold-in is a considered exception or an oversight, and the divergent site is the one
that is also wrong on canonicalisation — which is the usual relationship between the
two.

The counterparty grammar is brought into the same shape by declaring its derivation.
That is a wording correction to an already-correct implementation.

### Blast radius for the follow-on Step

The registry text and the key behaviour are separable, and the follow-on Step should
treat them as two changes with very different consequences.

Changing a grammar string on a templated namespace has no runtime effect at all. The
namespace contract enforces the declared literal only for singleton namespaces; for a
templated one it checks whitespace and traversal safety and treats the placeholder
grammar as documentation. So re-declaring the two diverging grammars — the member
segment and the counterparty key — strands nothing. It does couple to the grammar
drift gate, which derives match shapes from the declared string and asserts live keys
satisfy them, so a grammar edit without the matching builder edit reds that gate.

The behavioural change is confined to one key builder, and within that builder to one
branch. Only rows carrying a member identifier re-key. The single-filer branch returns
the unwidened key unchanged and is unaffected, which was confirmed directly. So:

- Namespaces whose declared grammar changes: two.
- Namespaces whose rendered keys change: one.
- Rows whose keys change within that namespace: only grupo member observations. Every
  single-filer calculation observation keeps its key bit-for-bit.

Whether any live encrypted record is actually stranded is therefore a narrow question:
it depends solely on whether an operator profile has ever persisted a member-widened
observation. The writing paths are live in production code — the cross-period
clean-state assembler and the amendment baseline carry both pass a member identifier
through — and the surface is reachable from the work-verification CLI via a grupo
roster, so the capability is not dormant. No operator store was inspected to answer the
data question; that determination belongs to the operator and was deliberately left to
them rather than answered by reading their encrypted database.

Because the affected population is grupo member observations only, the discard and
re-derive Step is very likely a no-op for a single-filer profile, and the operator
re-authentication Step should be scoped accordingly rather than assumed necessary.

## Notes

No production code was modified; this Step produces a ruling only. Applying it, discarding
and re-deriving affected profile databases, and recording the operator re-authentication
action are held by the plan lead as separate rows.

The Step row's own enumeration of PII-shaped placeholders was short by four and
misclassified two, which is why the set was re-measured from the declarations rather
than taken from the row.

One finding is worth the plan lead's attention before the follow-on Step lands, because
it changes what that Step is for. The raw fold-in is not only a hygiene divergence; it
is a live identity-canonicalisation defect that lets one grupo member persist as two
rows when the identifier is declared in different casing across captures. That makes
the follow-on Step a defect fix with a key change attached, rather than a cosmetic
uniformity sweep, and it argues for proceeding rather than deferring. It also means the
fix is incomplete if it only digests the value: the digest must be taken over the
canonical identity token, exactly as the pre-hashed siblings do, or the duplicate-row
defect survives the change in hashed form.

All identifier values used while probing were synthetic placeholder tokens. No real or
realistic identifier was written to a log, a scratch file, or this record.
