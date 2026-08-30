---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f72474c11194b8f8be56d162997cdb0275ac8723daf926bafc3daab6328b6dab'
step_id: 'S98'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Replace the 31 plan container identifiers in the Workspace projection module with the domain reason each stands for, including the only full W##.P##.S## address left anywhere in shipped production source. Do not delete the sentences and do not rename constants: each comment records a real design adjudication whose reasoning must survive without the identifier. BLOCKED ON PEER HANDOVER: the file currently carries another lane's uncommitted paginator generalisation, and the accepted 2026-07-08 ruling scopes exactly this case out as a peer-ownership constraint rather than an exemption, so the sweep timing belongs to that lane. The sibling modules were swept in commit 54778350d0

## Scope

- `src/cadrumo/application/modelo/workspace.py`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py`
- `verify:` `rg 'W[0-9]{2}\.P[0-9]{2}\.S[0-9]{2,3}' workspace.py` -> `0`
- `verify:` `bare S## container ids in workspace.py` -> `0`
- `verify:` `full W##.P##.S## addresses across production src/` -> `none`

## Notes

THE ROW'S OWN `BLOCKED ON PEER HANDOVER` TEXT IS STALE RELATIVE TO THE TREE.
The sweep landed regardless of the peer's paginator generalisation. The file
still shows as modified in the working tree, but that is the peer's edit and
not an unfinished half of this Step. Do not re-open this row on the strength
of the row's own prose; measure the file.

The last full `W##.P##.S##` address in shipped production source is gone --
verified across the whole production tree, not only this module. Its sibling
modules were swept earlier in `54778350d0`.
