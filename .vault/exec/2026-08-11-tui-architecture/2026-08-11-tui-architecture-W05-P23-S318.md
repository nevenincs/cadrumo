---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:e10e6d8eca6a190967415ce4d638a64eb44e8b79c10481ee124005d9e6f3e370'
step_id: 'S318'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Let the credential-free journal check admit a field whose SHAPE proves it carries no secret, instead of refusing it on a substring of its name: `_validate_credential_free_schema` (`application/operations/registry.py:902`) splits each field name on underscores and refuses any part in `_FORBIDDEN_CREDENTIAL_FREE_FIELD_PARTS`, which contains `key`, so the detail-row address field `natural_key` -- a pure addressing concept carrying no credential -- is refused on its name alone, and this is why `detail_row_intents` still cannot be carried on the `modelo.edit.apply` submission after S312 mirrored all six row kinds; S310 already established the precedent and its limit, admitting `digest`-named fields only when Hex64-shaped, so generalise that carve-out into a shape test the gate applies to every forbidden part rather than accumulating one hand-written exemption per field name. The gate exists to stop a credential reaching an unencrypted journal and MUST keep refusing anything secret-capable: prove with a four-direction conformance test that a legitimately-shaped natural_key passes, that a genuinely secret-capable field of the same name still refuses, and the same pair for one other forbidden part; never widen by deleting a member from the forbidden set

## Scope

- `the operations registry credential-free check`
- `its tests`
- `and the modelo edit-apply submission type that S312 left unable to carry detail_row_intents`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_detail_row_wire_mirror.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_detail_row_wire_mirror.py -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync pytest --collect-only -q` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo` -> `pass`

## Notes

### The gate was not changed, and no exemption was spent

The Step was framed as widening the credential-free journal check with a shape
test. That framing does not survive contact with the field it was meant to
admit.

The detail-row address carries a natural key whose schema is a string bounded
between one and 256 characters. That is exactly the shape a passphrase field
has. The legitimate field and a secret-capable field of the same name are
schema-identical, so no predicate can separate them, and the four-direction
proof the Step asked for was not satisfiable as posed. An earlier carve-out
worked only because a 64-character fixed hex pattern is genuinely distinctive;
a free-form bounded string is not.

The option of admitting any field whose schema declares a pattern was
considered and rejected: a pattern matching any character satisfies it, and
regex permissiveness cannot be judged soundly, so a secret-capable field would
have been admitted under a rule that looked principled.

What shipped instead spends nothing. The joined key is a derived convenience
rather than information: every one of its components is one of the row's own
declared identity fields, already carried in the clear by the row mirrors in
the same payload and already admitted by the same check. So the components
cross the wire and the translation derives the key. The credential-free check
is byte-for-byte unchanged and still refuses a bounded free-form field named
for a forbidden token, which a test asserts directly.

### Why this is not the rename that was refused earlier

A rename leaves identical information crossing the wire under a different
label, which clears the matcher and changes nothing real. That was refused when
it was available as a thirty-second fix, and it would have been just as wrong
here.

This changes what crosses. The components were always the real content; the
joined string was a projection of them. Carrying the projection was the
accidental part.

It is also strictly less ambiguous. A joined key cannot distinguish a separator
inside a component from a component boundary, and one of the six kinds keys on
a free-form source identifier that may contain one. The components keep that
distinction, and a test asserts the two cases are different on the wire while
producing the same domain key.

### One separator, not two

The domain derivation joined on a literal separator. Mirroring that literal
into the wire form would have created two definitions free to drift into
addressing different rows - the same defect the row hydration in the preceding
Step was shaped to avoid. The separator is now declared once beside the domain
derivation and imported by the wire form, so there is one definition rather
than two that agree today.

### Mutation proof

Three deliberate breakages, each confirmed to red exactly the assertions it
should, all applied by runtime monkeypatch from a plugin outside the
repository:

- deriving with the wrong separator reds the key-equality assertions across
  every row kind;
- dropping a component from the derivation reds the same set;
- translating an intent without resolving its address reds the removal
  assertion specifically.

The suite also asserts the direction that a widening would have broken: a
bounded free-form field named for a forbidden token is still refused by the
real check. Without that, every assertion here would pass just as happily
against a gate that had been quietly loosened.

### What this closes

The wire submission now carries the detail-row family, and the registered
request type is admitted by the real gate with it present. The preceding Step
delivered six row mirrors that nothing could submit; that is no longer the
case.

The reachability statement from that Step still stands unchanged and should not
be read as closed by this one: no caller anywhere submits this operation, so
what exists is capability rather than reach.
