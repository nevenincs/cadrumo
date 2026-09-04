---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:765b378dd9587dfb1996c0637d77f7d83c35b0ba556a97116d2e493b9115a6c7'
step_id: 'S12'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
