---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-20-schema-hardening-plan]]'
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` Open Edge Closeout

EDGE-2026-05-26-001 | INFO | Bucket B remains a guarded foreign-campaign edge

The repair-integrity symbols carried in `_BASELINE_BROKEN_IMPORTS` remain
owned by the parallel repair-integrity/live IVA wallet campaign. The
schema-hardening action is to keep the import gate active and let its
silent-fix detector force baseline trimming when the owning campaign lands.

Verification: `test_cross_module_imports_resolve.py` passed with the current
baseline.

EDGE-2026-05-26-002 | INFO | Plan-format missing-semicolon gate belongs upstream

The missing-semicolon plan-row failure mode is a vaultspec-core parser and
doctor concern. The AEAT-side test attempt was reverted as scope overreach.
The remaining action is upstream coverage in vaultspec-core, not another local
tax-project test.

EDGE-2026-05-26-003 | WARN | Historical plan-format backlog remains in older plan

Closing S143 and S142 makes the 2026-05-20 schema-hardening plan 145 of 145
complete, but `vault plan check` still reports older convention errors in
historical W06, W07, W08, and W09 rows. Those diagnostics predate this closeout
and are not required to select the next registry slice, but they remain visible
and should be handled as a separate vault hygiene pass if this legacy plan must
be brought to full convention cleanliness.

EDGE-2026-05-26-004 | NEXT | M131 is the next registry fragmentation slice

The 2026-05-22 schema-hardening P06 closeout selected M131 as the next
registry fragmentation target. M131 has the largest remaining tracked TOML
file, four revision-file revisions, and no fragment-directory revisions. The
next registry slice should split M131 through the existing generic loader
contract.
