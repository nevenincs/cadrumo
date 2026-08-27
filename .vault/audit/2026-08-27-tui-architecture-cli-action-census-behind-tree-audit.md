---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:50bf11038c62b203990298bc21556b5d29848a42aaf08b395bfca7376abbd111'
related: []
---

# `tui-architecture` audit: `the cli action census lost its modelo rows, so the s24 gate compares nothing`

## Scope

## Findings

## Recommendations

## Finding

`dev/quality/cli_action_census_dispositions.toml` carries 195 rows and NOT ONE
of them is under `src/cadrumo/application/modelo/`. The modelo rows were there
once and are gone.

The code they described is not. All 24 modules named by
`dev/tests/test_s24_precondition_campaign.py` still exist under that prefix,
with their symbols. So the ledger lost rows describing live code rather than
recording a campaign that finished.

## What that costs

`test_modelo_ledger_has_complete_s24_and_reserved_partition` filters the ledger
by the modelo prefix and compares the result against three declared partitions
-- 10 active groups, 33 retired-verification groups, 4 IVA-wallet groups. The
filter now yields nothing, so the assertion reads `set() == {...47 groups...}`.
The gate is not enforcing a partition; it is reporting that its corpus is
empty, and it would report exactly the same thing if the campaign had been
abandoned.

## It is not an isolated slip

`dev/tests/test_cli_action_census_dispositions.py`
::`test_current_tree_ledger_exactly_matches_the_mechanical_live_census` is red
for the reciprocal reason: the mechanical census finds current candidates the
committed ledger does not adjudicate, among them
`application/ledger/actions_classification.py::apply_classification_rules`,
`actions_import.py::import_ledger_transactions` and several
`actions_lifecycle.py` verbs. The ledger is behind the tree in both directions.

## Not remediated here

Each row in this file is an ADJUDICATION -- a decision recorded against one
action. Regenerating the file to make the gates green would manufacture
decisions nobody took, which is the failure the ledger exists to prevent. What
is needed is the owner reconciling the census against the tree and re-recording
the modelo dispositions, or retiring the S24 partitions if that campaign is
genuinely over.

## Status

Open. Both gates are red and honest about it; neither should be silenced.
