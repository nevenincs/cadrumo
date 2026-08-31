---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1e33075c380e861a359430f50438a3f14ec6c83e3675dddf823b0391827c1cc2'
step_id: 'S349'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Sweep the four HAND-AUTHORED adjudication ledgers whose entries are keyed to source paths that no longer exist, with each owning area in the loop: roughly 79 of 299 measured stale paths sit in regulatory-drift dispositions, complexity acceptances, CLI action-census dispositions and modelo branch classifications. These are not generated artefacts and MUST NOT be regenerated or bulk-repointed -- each entry is a human judgement keyed to a path, so mechanically repointing risks re-keying a reviewed acceptance or a regulatory adjudication onto the WRONG successor wherever a rename split or merged a module. Confirm each entry's successor individually, and where the original judgement may not carry to the successor, say so rather than moving it. Several belong to owners who should see them before they change. Where an entry's subject genuinely no longer exists, retire it with a stated reason rather than deleting it silently -- a disposition that vanishes without explanation reads as an adjudication that was never made. Re-run the path scan afterwards to confirm the ledgers resolve, and note that the scan cannot detect an entry re-pointed at a wrong-but-existing module

## Scope

- `the regulatory-drift dispositions`
- `complexity acceptances`
- `CLI action-census dispositions and modelo branch classification ledgers`
- `with their owning areas consulted`

## Changes

- `M` `dev/quality/regulatory_drift_dispositions.toml`
- `M` `dev/audit/complexity_allowlist.json`
- `M` `dev/quality/cli_action_census_dispositions.toml`
- `M` `dev/quality/modelo_branch_classification.toml`
- `M` `dev/registry/analysis/modelo_branch_classification.toml`
- `verify:` `stale-path scan against git ls-files` -> `87 before, 3 after`
- `verify:` `tomllib/json parse of all six ledgers` -> `pass`

## Notes

PARTIAL: 84 of 87 repointed. Three entries remain, escalated to their owning
areas rather than repointed, and the row stays open until they are
adjudicated. They are named below.

84 repointed, 3 escalated, 0 guesses. Counts by ledger: regulatory-drift 49,
complexity acceptances 23, CLI action-census 5, modelo branch classification
4 + 3.

METHOD, and the two rejected approaches matter more than the result.
BASENAME MATCHING produced false positives LABELLED UNIQUE --
`registry/_queries.py` -> `application/invoices/_queries.py`,
`ledger/_confirmation_gate.py` -> `core/_confirmation_gate.py`,
`user_profile/_preflight.py` -> `domain/submission/_preflight.py`. Unrelated
files in unrelated packages sharing a filename, which would have moved
regulatory adjudications onto foreign modules. SAME-DIRECTORY UNDERSCORE-DROP
was safe but still a name-shape guess.

What was used: GIT'S OWN RENAME RECORD. `git log --diff-filter=R -M` over all
history yields 699 recorded renames; each stale path is chained through them
and the endpoint must be currently tracked. Git recorded those renames by
CONTENT similarity, so this is evidence rather than inference, and a FORK in
the chain -- a split or merge, exactly where a mechanical repoint picks the
wrong half -- refuses rather than guessing.

THE THREE ESCALATED, subject genuinely gone, each needing an adjudication
rather than a repoint:

- `registry/_handoff_paths.py` -- MERGED into another module by `e59e8a993b`.
  Whether the complexity acceptance carries to the absorbing module is a
  judgement about whether the accepted complexity is the same complexity.
  Registry owner.
- `domain/contribuyente/family.py` -- a SPLIT, by `ffccf6c4f8`. Domain owner.
- `domain/transactions/_ids.py` -- an import-hygiene RATCHET entry whose
  module was removed by `185f4f6e8b`. Route it as evidence that a removal
  landed WITHOUT its ratchet shrink, not as a stale path.

NOT FIXED: the `reason` prose in these ledgers embeds `path:line` locators,
which still rot on any edit above a cited site and are already stale at HEAD.
The locator is REDUNDANT with the entry's own `path` and `enclosing_symbol`
fields, so it carries no information the row lacks -- only a way to be wrong.
Drop it rather than teaching the gate to ignore part of its own data.

The bucket grew from 76 to 87 BETWEEN the measurement and the sweep, because
peers landed relocations in the interim. That is the argument for fixing the
census key first (see the S350 record).

UPDATE 2026-08-31: the third escalation is RESOLVED, and it was already resolved before it was escalated.

`domain/transactions/_ids.py` was routed as evidence that a removal landed without its ratchet shrink. Measured: the shrink DID land. `family2_shim_modules.paths` holds ZERO entries, and the module name appears nowhere in the baseline outside the explanatory `_note`, which records exactly why -- the last documented bridge is gone and its consumers resolve `TransactionId` through `cadrumo.core.identity`, the canonical owner.

The stale-path scan that flagged it matched the path inside that prose. A scan that reads a file as text cannot tell a live ledger entry from a note explaining why an entry was removed, and the note is the record of the fix. Parsing the JSON and walking only non-underscore keys distinguishes them; grepping the file cannot.

Two escalations remain and both are genuine ownership judgements, unchanged: `registry/_handoff_paths.py` merged by `e59e8a993b`, where whether the accepted complexity is the same complexity belongs to the registry owner; and `domain/contribuyente/family.py` split by `ffccf6c4f8`, which belongs to the domain owner.

Also measured in passing, and load-bearing elsewhere: `production_family1_cross_package_private_imports.sites` is at ZERO. The hard-zero baseline is real, which is why a TUI editor module importing `application/modelo/_edit_models.py` would have been the first violation rather than one among many.
