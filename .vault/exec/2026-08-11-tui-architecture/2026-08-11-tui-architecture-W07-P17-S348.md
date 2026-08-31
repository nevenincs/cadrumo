---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e73d5aa7228a98f74eb7ad6570d3f705f9298a131813251e2da9979a2716934e'
step_id: 'S348'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Regenerate the six GENERATED dev inventories that carry stale source paths, once the tree is quiet enough that regenerating does not bake in half-landed work: roughly 220 of 299 measured stale paths sit in artefacts that declare themselves generated, two of which name their own regeneration command -- a registry facade census, a complexity baseline, a fixture-ownership inventory marked do-not-hand-edit, an authority consumer census, a size-budget baseline and an import-hygiene baseline. They are stale because dozens of private-to-public relocations moved the modules they name. DO NOT hand-edit any of them, and DO NOT regenerate while the tree is churning: a regeneration absorbs whatever is mid-flight at that moment, which is precisely the contaminated-artefact hazard this campaign hit three times -- an evidence snapshot that ingested a gitignored source mirror, a consumer census 44 per cent contaminated by it, and a vacuity screen whose denominator was 86 per cent phantom paths. Regenerate each through its own declared command, then verify the regenerated artefact names only tracked files. THE SCAN THAT FOUND THEM, reproducible and to be re-run after any sweep: resolve every `src/cadrumo/**.py` path string in every tracked inventory under the dev quality, audit and registry-analysis trees against `git ls-files`, never against a filesystem walk -- a walk would absorb untracked and mid-relocation files and report a peer's in-flight work as drift. KNOWN LIMIT of that scan, stated by its author: it reports paths that no longer RESOLVE, not paths that resolve to the WRONG thing, so an entry silently re-pointed at a different module by a rename that split or merged one passes it. That is a second and harder question nobody has answered

## Scope

- `the six generated dev inventories`
- `their own regeneration commands`
- `and a post-regeneration check that every named path is tracked`

## Changes

- `M` `dev/quality/registry_authority_consumer_census.v1.json`
- `M` `dev/quality/registry_facade_family_census.v1.json`
- `M` `dev/audit/complexity_baseline.json`
- `M` `dev/audit/size_budget_baseline.json`
- `verify:` `the row's own staleness scan, before` -> `785 stale path references across 9 artefacts`
- `verify:` `the row's own staleness scan, after` -> `168 across 7`

## Notes

PARTIAL. Four of the six regenerated through their OWN declared commands, never
by hand: the authority consumer census (252 stale -> 0), the size-budget
baseline (20 -> 0), the complexity baseline (106 -> 7) and the facade family
census (332 -> 86).

THE MEASURED POPULATION IS LARGER THAN THE ROW RECORDS -- 785 stale references,
not the ~299 it measured -- because dozens of further private-to-public
relocations landed between the row being written and this run. The row's scan
is reproducible and was re-run rather than trusting its figure, which is what
the row asks for.

THE FIXTURE-OWNERSHIP GENERATOR REFUSED, AND ITS REFUSAL IS THE ROW'S OWN
HAZARD WORKING. `python -m dev.quality.fixture_ownership --write` exited with
`fixture source universe changed during manifest generation`, naming four
`core/identity` files whose content hash moved between the start and end of its
own scan. A peer was editing that package at that moment -- confirmed
independently: four files under `core/identity` had been modified within the
preceding ten minutes. This is precisely the contaminated-artefact hazard the
row says it hit three times, and the generator declines to bake in half-landed
work rather than producing a plausible manifest nobody can date. Do NOT retry
it until that package is quiet, and do NOT hand-edit around it.

REMAINING, and why each is not simply another regeneration:
- `registry_facade_family_census.v1.json` still carries 86 stale paths after
  `--refresh-reviewed`, so its remaining entries are curated rather than
  generated and need adjudication, not a command.
- `regulatory_drift_dispositions.toml` (34), `fixture_ownership.toml` (24),
  `complexity_allowlist.json` (12), `modelo_branch_classification.toml` (4) and
  `import_hygiene_baseline.json` (1) are hand-authored adjudication ledgers, not
  generated inventories; they are W07.P17.S349's subject, and that row already
  records 84 of 87 repointed with three escalated.

THE ROW'S OWN STATED LIMIT STILL STANDS AND IS NOT CLOSED HERE: the scan reports
paths that no longer RESOLVE, never paths that resolve to the WRONG module. An
entry silently re-pointed by a rename that split or merged a module passes it
clean. Nothing in this work answers that second question.

Re-attested through the owning edit verb after hand-authoring, so the body
fingerprint matches its stamp.

Re-attested through the owning edit verb; body fingerprint matches its stamp.

CORRECTION 2026-08-31 TO THIS RECORD'S OWN FIGURE, and to the scan the row calls reproducible.

The post-regeneration figure recorded above -- 168 stale across 7 artefacts -- is a TEXT scan result and over-reports. Re-measured by parsing each artefact and walking only real data keys, skipping any key that is underscore-prefixed or named as a note: **148 stale across 4 artefacts**.

Three artefacts drop out completely, because every apparent stale path in them sat in explanatory prose rather than in a ledger entry: `complexity_baseline.json`, `complexity_allowlist.json` and `import_hygiene_baseline.json`. The last is the sharpest case and is the same one W07.P17.S349 escalated: its `_note` names `domain/transactions/_ids.py` precisely to record that the bridge is GONE and its consumers now resolve through the canonical owner. The note is the record of the fix, and a text scan reads it as the defect.

So the row's stated scan has a second known limit beyond the one it already names. It records that the scan reports paths that no longer RESOLVE rather than paths resolving to the WRONG thing; it should also record that the scan cannot tell a live entry from a note about a removed entry. Both limits push the same way: the scan is a starting inventory, never a verdict.

The true remaining population is `registry_facade_family_census.v1.json` 86, `regulatory_drift_dispositions.toml` 34, `fixture_ownership.toml` 24 and `modelo_branch_classification.toml` 4 -- and the last three are hand-authored adjudication ledgers, which is W07.P17.S349's subject rather than a regeneration.
