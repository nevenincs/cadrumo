---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:94836e03b0931e17c838fb3b37505407409b2e643bbb3967a74a85c1a0fdcc5f'
step_id: 'S168'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Relocate the verify contract, filing validation and fixture provenance onto public modules, repointing the module-object attribute access the AST scan cannot see

## Scope

- `src/cadrumo/`

## Changes

- `A` `src/cadrumo/adapters/outbound/aeat/verify/contract.py` (15 symbols)
- `A` `src/cadrumo/application/filing/validation.py` (3 symbols)
- `A` `src/cadrumo/tests/fixtures/provenance.py` (7 symbols)
- `M` `src/cadrumo/adapters/outbound/aeat/verify/tests/test_verify.py`
- `M` three namespaces inert; 61 consumers repointed
- `verify:` `pytest aeat/verify -n 0 -m "not live"` -> 34 passed (the one failure is the live-test safety guard refusing without `CADRUMO_LIVE_TESTS_ENABLED`)
- `verify:` `--collect-only` -> 28987 collected, **0 errors**

## Notes

The tree now collects with ZERO errors, for the first time in this campaign
segment. The six that had stood all session were two peer-owned half-landed
relocations, and a peer resolved both while this batch was running. They were
correctly never chased.

### Module-object access, the fourth invisible consumer shape

Thirty-nine tests failed on `module 'cadrumo.adapters.outbound.aeat.verify' has
no attribute ...`. One test file binds the package as a module object --
`from ... import verify as verify_module` -- and then reaches through it for
private helpers.

That is an import an AST scan DOES see, but the coupling it creates is not in
the import: it is in every later `verify_module.X` attribute access. Repointing
the binding to the defining module fixed all thirty-nine at once.

Added to the list this campaign has accumulated of consumer shapes a static
import scan cannot fully resolve: string module paths in a lazy map, a separate
distribution's package root, source embedded in a string literal, and now a
module bound as an object. Each was found only by running tests after
`--collect-only` was already clean, which is the argument against treating
collection as sufficient proof for a relocation.

### A staged peer collision, handled differently this time

`application.filing` was `MM` -- staged plus modified -- and was relocated
before that was visible, exactly as `application.calculations` had been.

It was NOT reverted this time, and the difference is worth stating. The
calculations revert was necessary because that peer's staged map was WRONG: it
named modules that did not define the symbols, and restoring it reintroduced a
real defect affecting 240 collections. Here the staged change is a valid import
regrouping of a facade being retired, the tree collects clean with the
relocation in place, and every repointed consumer reads a defining module that
works whether or not the facade returns.

So the peer's commit can land without breaking anything; it will simply
reintroduce a namespace nothing routes through any more.
