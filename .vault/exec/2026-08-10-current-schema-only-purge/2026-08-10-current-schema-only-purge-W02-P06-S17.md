---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:da69d47d9cfb164883c0932e5f55991629a0cfd9fb7b3d64eef3d725e7b0ac8d'
step_id: 'S17'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Stamp current KDF markers during key mint and recovery

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`
- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_kdf_salt.py`
- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`

## Description

- Remove the KDF parameter record's `version` default so the field is required.
- Pass the current marker explicitly at both production writers, mint and recovery.
- Pass it at the three test construction sites, and match the two salt refusals on the
  salt field so their raise is provably about the length contract.
- Add a control that omits the marker and matches on it, so the other matches mean something.
- Repoint the minted-document assertion at the constant the writer stamps instead of at the
  model's own field default.

## Outcome

Delivered, verified at `388 passed`. The record's `version` is required and carries no default;
every writer states the marker it stamps.

**The row was twice the size its scope declared, and a precondition measurement is what found
that.** The row named the two production writers. There are **five** construction sites: mint,
recovery, and three in the record's own salt-validation tests, none of which passed the field.
Scope was widened before any edit rather than after.

**Two of those three would have passed for a new reason while keeping their names.** They assert
a *salt* refusal inside a bare expected-validation-error block. With the default gone they still
raise -- on the missing marker, before the salt validator is reached -- so two salt-validation
tests would have become version-validation tests with unchanged names, assertions, docstrings and
green. Nothing would have gone red to announce it. Both now supply the marker and match on the
salt field, and a new control omits the marker and matches on it: without that control, matching
at the other two sites is an untested precaution, since nothing would establish that omission
refuses at all.

**A sixth consumer existed and no audit of the change could have found it.** A directory-wide run
broke on an assertion in the file-fallback tests that reads the model's field default as an
oracle. It constructs nothing, so a census of construction sites could not see it; and a
line-class histogram of the change was clean and complete, because **a histogram describes the
lines that changed and this was a line that did not.** The census answered *who calls this model*
when the question was *who depends on this field's default* -- different sets, and only the second
is the blast radius. The sweep that finds it is a tree-wide search for reads of the model-fields
mapping: twenty hits, one of them this.

**That sixth site broke because it was tautological, which is the more useful half.** It compared
the written value against the thing that produced it, so a wrong default, a wrong marker, or the
Argon2 algorithm constant substituted for the parameter-shape constant would all have passed it.
A correct assertion against the constant would have been untouched by this change. **A tautological
assertion is not merely uninformative: it is coupled to the implementation detail it should be
independent of, so it breaks on a correct refactor and stays green on a real defect** -- wrong in
both directions at once. It now asserts against the constant, which is what it always claimed to
do.

## Notes

**A type-level duplicate authority was declined.** The tempting form was to pin `version` as a
literal type, refusing a foreign value at the type level. The sibling document model in the same
module does exactly that, so it reads as house style -- and its own comment names the price: the
literal is safe there **only because a lineage gate asserts it agrees with the named constant, so
the constant cannot drift from the constraint it describes.** The KDF parameter constant has no
such gate. Copying the idiom would have added an ungated second authority for a number, and then
satisfying the module's own convention would have required writing the drift gate to hold it: a
gate this row never asked for, protecting a duplication this row would itself have created. The
field is a plain required integer; the exactness check stays at the version gate, which already
owns it. **The sibling is not wrong -- it is paid for, and the payment is invisible at the call
site.**

**Provisioning was the blast radius and it is intact.** Both writers relied on the removed
default, so a mistake meant no new secret store could be minted and recovery could not complete.
Every minting, recovery, round-trip and tamper-refusal node passed. The one break was an assertion
about model metadata, never the write path -- which is precisely why a focused run over the four
scoped files would have been green and would have banked a false pass.

**One unrelated failure in the same directory is not this step's and is not a regression.** An
error-rendering test asserts an English category prefix while pinning no language. It passes at a
pre-session anchor and fails at HEAD, which reads as a committed regression -- and is not one.
The shipped default output language is Spanish and has been throughout: neither the language
resolver nor the settings default changed in the intervening range. What changed is that the
Spanish catalogue **gained the translation for that prefix**. Before, the lookup fell back to
English and the assertion held; now the translation exists and the renderer correctly returns it.
**The test was silently asserting the absence of a Spanish translation** -- it encoded a
translation gap as its contract and passed only while the gap existed. The remedy belongs to the
error-rendering surface, not here: pin the language the assertion is about, since the test's
subject is the category-prefix mechanism rather than which language a clean install renders.
