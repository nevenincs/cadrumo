---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:77a6dc998bbb11e3cca6fda6a7b3516facbf562c4dc57c4fcd5db3eddcaf3894'
step_id: 'S52'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# apply the `W08.P12.S51` decision to every `SecureObjectNamespaceDefinition.object_key_grammar` declaration that currently diverges from it

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`

## Description

- Re-measure the S51 split at HEAD from the declarations rather than trusting the
  record: enumerate every `object_key_grammar` in the namespace registry and
  re-classify the identifier-bearing ones.
- Re-declare the calculation-observations grammar so its optional trailing member
  segment names the derivation, a digest of the member's canonical identity token,
  rather than the raw identifier.
- Re-declare the ledger confirmed-counterparty-facts grammar so it names the
  derivation instead of the resulting key. Declaration-only; the implementation
  already digested the canonical identifier.
- Change the member branch of the observation key builder to normalise through the
  one canonical identity token and fold the digest of that token into the key,
  matching every pre-hashed sibling.
- Correct the grammar drift gate's member-key assertion, which encoded the raw
  composition, and add a regression proving the identity contract the digest buys.
- Prove the regression bites by reverting the builder to the raw form at runtime
  from a throwaway script outside the repository.

## Outcome

### The S51 split re-verified at HEAD

Seventy-seven declared grammars, of which the identifier-bearing set matched S51's
measurement exactly: six already declared a digest, one folded the identifier
verbatim, and one was pre-hashed in substance while its token named the resulting
key rather than the derivation. The raw site was the calculation-observations
member segment, as recorded. Nothing had moved since the ruling.

### Two grammars changed, one key shape changed

The calculation-observations grammar now declares its optional trailing segment as
a digest of the member identifier. The confirmed-counterparty-facts grammar now
declares a digest of the canonical tax identifier in place of a token that merely
named the record key; that one is wording only, since the builder already produced
a full-width digest of the canonical identifier.

Only the first changes a rendered key, and within it only the member-widened
branch.

### The single-filer key is unchanged, bit for bit

Confirmed two ways. The edit is confined to the branch taken when a member
identifier is present; the early return for the absent case composes the same
three segments it always did, through an untouched helper. And the gate now
asserts directly that the member key builder with no member identifier returns
exactly what the single-filer key builder returns for the same modelo and period.
Every single-filer observation keeps its address.

### The defect this closes

The member segment was the declared value appended verbatim, and neither the key
builder nor the persisted payload normalised it. One member declared lower-cased
in one capture and space-padded in another therefore addressed two distinct rows,
so the cross-member fan-in the widening exists to serve counted that member twice.
The segment is now the digest of the trim-and-uppercase identity token every
sibling key already routes through, so the spellings converge on one address. A
blank identifier that is not an explicit absence is refused by the module's own
key error rather than silently keyed.

### The fate of already-persisted member rows

This is the material input to the discard-and-re-derive Step, and the answer is
sharper than "stranded".

The enumeration path the grupo fan-in reads through recomputes each row's natural
key from its decrypted payload and compares it with the key the row is filed
under, and a mismatch raises rather than being skipped. That is deliberate, so a
caller counting rows for a declaration is never handed a quietly shortened set. A
member row written under the old raw composition now rebuilds the digest form,
which does not equal the raw key it sits under.

So a profile that has ever persisted a member-widened calculation observation will
raise a row-identity refusal on the first full scan of that namespace, which is
the cross-period clean-state member fan-in. The rows are not lost and not silently
mis-read; they hard-refuse the scan until they are discarded and re-derived. That
makes the discard Step a real, required action for such a profile, and a genuine
no-op for a single-filer profile, whose keys are unchanged and whose rows continue
to re-verify identically.

### Proving the gate bites

The new regression and the corrected shape assertion were re-run with the key
builder reverted to the pre-fix raw append, rebound at runtime from a script
outside the repository. Both went red under the reverted builder and green again
on restore; no tracked file was edited to produce the proof. The digest the shape
assertion compares against is computed in the test from the standard library over
the canonical token, not read back from the production helper.

## Notes

The ruling was applied through the one canonical identity token in core rather
than by calling the aggregation package's normalise-then-hash convenience. That
helper's blank refusal raises an aggregation-domain error whose shipped message
names a perceptor, which is the wrong operator-facing diagnostic for a grupo
member and would have pulled a retenciones vocabulary into the calculations key
path. The module's own IVA wallet key builder already composes the identity token
and the digest locally for exactly this reason, so this follows the established
in-module shape. The canonicalisation authority is shared either way, which is
what the ruling binds on.

One adjacent defect is left open and belongs to the plan lead, because closing it
reaches beyond this row. The key now canonicalises, but the persisted payload's
member identifier field still carries no normalising validator, and the expected
member roster it is set-differenced against carries none either. So while two
spellings of one member now address one row, a payload spelling that differs from
the roster spelling still produces a spurious missing-and-unexpected member pair
in the clean-state verdict. Closing that means normalising at both model
boundaries, not at the key.

The full-tree picture around this row is red from several unrelated peer
campaigns, and none of the failures touch this surface. The dominant signature is
a tightened AEAT verification-code type refusing hyphenated synthetic codes still
present in a cross-period test support module; others include a catalogue schema
version bumped past its pin, a source-tree AST census tripping over a file being
edited, a translated refusal message compared against an interpolated value, and
missing-session refusals. The suites that do exercise the changed path, the
grammar drift gate, the observation header roundtrip, the grupo aggregation
continuity check and the informativa fidelity check, are green.

All identifiers used in the new coverage are obviously-synthetic placeholder
tokens no identifier authority would issue. No real or realistic identifier was
written to a log, a scratch file, or this record.
