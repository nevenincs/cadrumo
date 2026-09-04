---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e771fa4419ea04f1b8e245c06a4108e05fae9f7d4141b29704f38deb362c23c1'
step_id: 'S12'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Resolve the Modelo export and review package clone without coupling distinct workflows

## Scope

- `src/cadrumo/entrypoints/cli`

## Changes

- `M` `dev/audit/duplication_dispositions.toml`
- `M` `dev/audit/tests/test_duplication.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`

## Notes

Adjudicated `intentional`, which the amended governing decision now permits: closure rests
on adjudicated residue rather than a literal zero.

The matched span is the handler SIGNATURE, not shared behaviour. The command runtime
dispatches through `invoke(**arguments)` built from the declared CommandSpec parameters, so
each handler must spell every declared parameter itself. Neither side can accept a bundle
the way the TUI controller could in the sibling Step, because there the controller was a
plain class whose caller I could change; here BOTH sides are dispatcher-facing. Removing
this clone would require changing the dispatch contract, and reordering the parameters to
defeat token matching is the detector-oriented shortcut the decision rejects. The two
workflows stay distinct authorities, which this Step required.

The clone therefore remains visible and counted. Nothing about the detector changed.

## Notes on the gate this Step added

Recording the adjudication exposed a hole in the existing arithmetic gate, and the hole bit
immediately. Regenerating the ledger left `intentional = 0` in the summary beside a group
classified `intentional`, because the count had been absorbed into `cluster_owned` -- and
the arithmetic gate passed, since it compares TOTALS and the totals still balanced.

A summary that adds up while attributing groups to the wrong class is not a claim about the
tree. The new gate asserts per-class equality between the summary and the recorded
classifications, and its teeth were proven on exactly the defect that produced it: restoring
`cluster_owned = 10, intentional = 0` fails, and the corrected pair passes.

The regeneration script was also extended to carry intentional adjudications forward, keyed
by file-set rather than line span so unrelated edits do not drop them. That extension is not
yet working -- two attempts left a syntax error in the script -- so for now a regeneration
must be followed by re-applying the adjudication, and the new gate is what makes a dropped
one fail loudly rather than pass unnoticed.
