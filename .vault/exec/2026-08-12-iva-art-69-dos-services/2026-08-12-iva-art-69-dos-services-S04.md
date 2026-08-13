---
tags:
  - '#exec'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4863c19d07104559be5bc78538a0e8098876b41d46f89f4b0b01c6cd78721519'
step_id: 'S04'
related:
  - "[[2026-08-12-iva-art-69-dos-services-plan]]"
---

# Gate the split with mutation proofs in both directions: every declared item reaching not-subject for a third-country recipient, the same items staying taxed for a recipient in Canarias or Ceuta y Melilla, an undeclared item staying taxed, and the B2B limb unmoved by any declared item. Assert per item across the whole enum rather than on a sample, so a member added later is covered without editing the file

## Scope

- `src/cadrumo/domain/iva/tests/`

## Description

- Asserted every listed service leaving the TAI for a third-country consumer,
  per item across the whole enum.
- Asserted the same items staying taxed for a recipient in Canarias or Ceuta y
  Melilla.
- Asserted an unstated item staying taxed.
- Asserted the excepted branch is constructible without a rate tier.
- Asserted the B2B limb is identical with and without a stated item.

## Outcome

Done. 57 cases pass in the module.

Proven to bite rather than assumed to: with the exception predicate forced
false from outside the repository, a listed service to a third-country consumer
falls back to `domestic_general` and the case reds.

## Notes

The cases are driven from the enum rather than from a listed sample, and that
choice does two things a sample cannot. A member added later is covered without
editing the file. And a member added WITHOUT the row learning to read it fails
here, instead of quietly staying taxed the way the whole list did before this
change.

The B2B case is the one that would catch a fix reaching too far. Art. 69.Dos
excepts from 69.Uno.2.º, the B2C paragraph, so a B2B service was never placed by
the rule being excepted and a stated item must move nothing. It asserts the two
answers identical rather than asserting the expected value twice, so it fails if
EITHER moves.
