---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c44e6a585f7b6963a52418bdf4aef9e7d8377dd13768956d95f803547ddb680e'
step_id: 'S172'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Guard the retirement sweep against creating cross-package private imports, and encode the three verified-broken exclusions so the sweep stops re-proposing them

## Scope

- `dev/quality/`

## Changes

- `M` retirement tool refuses to repoint an out-of-package consumer at a private defining module
- `M` retirement tool carries an exclusion table for the three namespaces verified to break
- `verify:` `storage.sql` and `core.identity` now refuse, naming the private module to publicise first
- `verify:` 0 files fail to parse; 0 unresolvable relative imports; private cross-package count held at 270 (no new debt added)

## Notes

"Stop retiring facades until the rename is ruled on" was too broad a reading of
this campaign's own finding. A facade whose definitions are already PUBLIC can
be retired with no new violation; only the private-definition case trades one
rule for another. The constraint belongs in the tool, not in the campaign's
pace.

The guard refuses when the defining module is private AND the consumer is
outside the owning package, naming the module to publicise first. On the first
sweep it caught `storage.sql` (`SecureObjectRow` in `._orm`) and `core.identity`
(`ContentDigest` in `._digest`) -- two retirements that would each have added
tens of consumers to the debt this campaign just measured.

### The exclusions are now guards, not memory

`core.resources`, `application.invoices` and `aeat.browser` were retired,
verified broken, and reverted for the THIRD time in this campaign. Each has a
real reason -- module-object attribute access, a gate asserting the opposite,
and an import the eager block does not carry -- and none of those reasons is
derivable by the sweep.

That is the property recorded under `P01.S170` and left unaddressed: a batch
sweep re-proposes anything whose exclusion lives in a human judgement rather
than in code. The parent-first case became a guard after ONE occurrence and
never returned; these three had no guard and cost three round trips each.

They now sit in an exclusion table carrying their reasons, so the sweep refuses
them with the reason rather than retiring them and waiting to be caught by a
test run.

### Tree state

Three collection errors, all in
`domain/calculations/registry/tests/test_modelo_100_registry_roles_*`. That
subtree carries 375 modified files and another session reports three of its
agents blocked there; none of the errors names anything retired here, and the
local damage scan is clean on both roots.
