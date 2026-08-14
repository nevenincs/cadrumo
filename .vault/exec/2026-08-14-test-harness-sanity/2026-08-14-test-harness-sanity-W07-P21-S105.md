---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:9eadf043b07269c1159ce69ed111bccc23a0964d3d59aca02c3958d6f1f72bf2'
step_id: 'S105'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Key the ownership manifest disposition on full constraint shape rather than repeated name

## Scope

- `dev/quality/fixture_census.py`
- `dev/quality/fixture_ownership.py`
- `dev/quality/tests/test_fixture_census.py`

## Description

- Establish which fixtures the census can and cannot see, by reading its data path rather than inferring from its output.
- Report the fixtures produced indirectly through a factory binding, which the decorator-only walk omits entirely.
- Require a resolved factory for membership so the reported population matches its name.
- State the unfollowable remainder as a bounded count rather than as thousands of false members.
- Make the import matcher scope-aware so a nested closure cannot receive an importable definition's consumers.

## Outcome

The census now reports the fixtures it previously omitted. A factory returning a decorated closure produces a real fixture through a plain module-level assignment, and that assignment carries no decorator, so the walk that fills the fixture population never saw it. Because the ownership manifest is built from that population alone, such a fixture received no row, no group and no disposition: the duplicate check did not examine and clear it, it never examined it. Ten fixtures in the current tree are bound that way.

The import matcher compared bare function names with no scope check, so two identically named fixture definitions in one file both received an external import's consumers and autouse reach. The record already carried the qualified name needed to distinguish an importable module-level definition from a nested closure; the matcher simply never read it. A closure is not a module attribute and can never be the target of an import, so it is now excluded.

## Notes

The correction that matters most here was to the reporting, not the detection. An earlier shape recorded every module-level call assignment as a fixture candidate: three thousand four hundred and fourteen members, of which ten were real and the remainder were date, decimal, regular-expression and frozen-set construction. That is this campaign's own subject reproduced in miniature, a category named for a property almost none of its members hold, and several thousand enumerated lines is not visibility but noise nobody reads. Membership now requires a resolved factory, so the name is true of every member, and the unfollowable remainder is a count carrying an explicit statement of what it bounds. Refusing to guess was right; naming the guess-free population after the thing it mostly is not was not.

Both corrections were proven by mutation. Disabling the new collection reds the factory assertion. Reverting the scope check reproduces the false attribution, with the nested closure inheriting the module-level definition's import binding, which is the exact false-clean reading that prompted the investigation.

Visible is not classified, and the difference is load-bearing. These bindings still take no manifest row, so the substitutable-duplicate rule remains blind to them and this plan's no-unclassified-record criterion is not yet satisfied for them. The gap is narrowed and stated rather than closed, and it should not be read as met.

The manifest module was committed here alongside its consumers because it had never been tracked while the tests importing it were, so committing either alone would have left the tree unable to import its own gate.
