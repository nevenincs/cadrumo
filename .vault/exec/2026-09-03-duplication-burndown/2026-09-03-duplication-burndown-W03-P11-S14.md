---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:3f4184dc1b6c95b621048ff3d8e670259fed41c6ddeb850aa87063dc63f6f54d'
step_id: 'S14'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Adjudicate and resolve the GROI and NIF IVA check pair without merging distinct AEAT protocol authority

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede`

## Changes

- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/outbound/aeat/sede -k "groi or nif_iva or adapter_utils"` -> `pass`

## Notes

No code change. The adjudication is that this pair's shared check mechanics were already
centralised before this campaign, and the residual clone is not duplication.

`_adapter_utils.py` already owns every shared mechanic: landing assertions, marker verdict
extraction, the locate helper, playwright page handling, the NIF check operation tail, and
registry failure messages. `groi_check` imports nine of its symbols and `nif_iva_check`
ten. The distinct AEAT protocol authority of each check stays in its own module, which is
what this Step required be preserved.

The clone the detector reports is the ten-line import preamble naming those shared
symbols, and nothing else. It is an artifact of correct centralisation rather than a
defect: the more mechanics move to the shared module, the longer the identical import list
grows and the more the token matcher has to match on. Removing it would require either
un-centralising the mechanics or introducing a facade re-export layer, and a re-export
layer is forbidden outright by the architecture boundaries this project holds.

The group therefore stays recorded as `cluster-owned` and visible in the count. It is the
fourth structurally irreducible clone found in this campaign, after the Modelo export
handler signature, the auth/user-profile import preamble, and the deliberately diverging
atribucion member builders.
