---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:978a521c6e38b9db74998803c7685ef0d29b74e6d6413ad63370542ea1c5945a'
step_id: 'S14'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# enumerate every secure-object storage key derived from the CSV value, starting from `extract_identifier` in the justificante persistence adapter, informing (not gating, per the schema-rewrite authorisation) the key-composition redesign in `W08`

## Scope

- `src/cadrumo/adapters/persistence/profile/justificante.py`

## Description

Read-only enumeration. No production code changed.

Started at `extract_identifier` in the justificante persistence adapter, which
returns `payload.csv` unchanged, then followed the key upward into the shared
bound-repository base and outward across the whole namespace registry rather
than only the namespaces the receipt domain owns.

Enumerated all 74 `SecureObjectNamespaceDefinition` entries in the registry
mechanically rather than by reading for likely candidates, and read the key
grammar of each. For every namespace whose payload carries a CSV but whose
grammar does not name one, read the id-derivation function to confirm the CSV
does not enter the key indirectly through a hash. Three such derivations were
opened and cleared.

## Outcome

**Exactly one secure-object storage key is derived from the CSV value.**

| namespace | grammar, verbatim | where the CSV enters | pre-hashed or raw |
| --- | --- | --- | --- |
| `cadrumo.domain.justificante.metadata` | `{csv}` | `extract_identifier` returns `payload.csv`; the bound-repository base passes that return value straight through as `object_key` on save and compares it against the lookup key on load | **RAW** - no hash, no truncation, no prefix, no encoding step |

The key is the CSV itself. The base repository composes nothing around it: the
save path sets `object_key` to the extractor's return value, and the load path
re-derives the identifier from the loaded payload and refuses when the two
differ. The only transformation the value meets is a shape-safety guard that
rejects path separators, dot-prefixes and relative-path tokens, and that guard
deliberately declines to know any domain alphabet so one helper can serve every
governance repository. Nothing in the storage layer knows a CSV is a CSV.

The row asked for "every storage key derived from the CSV value", so the
complement is part of the answer. Four namespaces carry a CSV in the PAYLOAD but
do not key on it, and each was cleared by reading its id derivation rather than
its grammar string:

- The submission records namespace keys on `{submission_id}`, a truncated hash
  of draft id and attempt ordinal. Its payload carries `justificante_csv`. CSV
  absent from the key.
- The filing amendments namespace keys on `{amendment_id}`, a truncated content
  hash of submission id, amendment kind and the casilla delta. Its payload
  carries `original_csv`. CSV absent from the key.
- The live justificante capture snapshot namespace keys on bucket id plus a
  snapshot id content-hashed from modelo, filing year, period and the raw PDF's
  content address. The snapshot carries the captured CSV. CSV absent from the
  key, deliberately - the id is content-addressed on the PDF so a re-capture of
  the identical receipt is idempotent.
- The live verify observation namespace keys on bucket id plus an observation id
  hashed from surface, tax id, verdict and check time. CSV absent from the key.

Also cleared: the filed-declaration artefacts namespace keys on the artefact's
own byte digest. Its `source_url` carries the CSV as a query parameter, so a CSV
is recoverable from the payload, but the key is the content address of the
bytes.

**The finding `W08` most needs is not the table but an asymmetry the table
exposes.**

The write path stores under a NORMALISED key and the read path looks up under an
UNNORMALISED one.

On write, the key is `payload.csv`, and that field now carries the canonical
alias, whose before-validator strips and uppercases before any constraint runs.
Every key written from now on is stripped and uppercase.

On read, the two keyed lookups both pass an external evidence reference id
straight into `load`. That field is a plain constrained string - non-empty, at
most 128 characters, whitespace stripped - with no CSV shape and no case
normalisation. The external-import path's own pre-check strips the operator's
value and refuses it blank, and stops there; it does not uppercase. The value is
operator-supplied through a CLI option, so a lowercase or mixed-case reference id
composes a key that cannot match the uppercased key the write path stored.

The consequence was checked at both sites rather than assumed, and it is NOT a
silent wrong answer. Both turn the miss into a refusal: the external-import path
raises a justificante-missing error, and the cross-period clean-state gate
records a missing-evidence-record blocker. What the operator gets is an
ACCURATE-SOUNDING BUT WRONG diagnosis - "no such receipt" for a receipt that is
stored, under the same identifier in a different case. That is a better failure
than a wrong value and a worse one than a match, and it is unrecoverable from the
message alone.

The same module's receipt-matching helper compares the taxpayer identifier
case-insensitively and says so in its docstring. The identifier that addresses
the row did not get the same treatment.

Before the canonical retype the two sides agreed by accident: the retired alias
carried no pattern and no normalisation, so whatever case arrived was both
stored and looked up. The retype made the write side canonical and left the read
side where it was. The commit that landed the retype reasoned about this and
concluded the change moves no key and orphans nothing, which is true of data
already on disk - the namespace held zero stored objects across every bucket.
It is not true of the read path going forward.

This is offered as input to the key-composition decision, not as a finding this
row is authorised to fix. The row informs and does not gate.

## Notes

The commit that retired the receipt domain's CSV alias asserted in its message
that this namespace "has exactly one key-deriving consumer". Re-measured at
enumeration time that is not the shape of the surface: **four write sites and two
keyed-read sites across three modules**, plus three full-scan read sites that
enumerate every stored key without composing one.

The four write sites are three in the live justificante application module and
one in the filed-observation persistence module. The two keyed reads are in the
cross-period clean-state gate and the external-import actions module, and both
are the reads carrying the unnormalised reference id described above. The three
full-scan reads are in the overview evidence surface; they list rather than
address, so a key-composition change does not move them.

The correction does not overturn that commit's conclusion for data at rest, which
rested on the zero-stored-objects measurement rather than on the consumer count.
It does change the migration surface any future key-composition change has to
move, which is what this enumeration exists to supply.

The plan row scopes this enumeration to the persistence adapter file. That file
is the right starting point and the wrong boundary: the key it derives is
composed by a base class in the storage package, constrained by a guard in a
third module, and consumed by six call sites in three application modules. None
of that is visible from the scoped file alone.
