---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s93-authority-regression'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:e69c2cde35d7d35107c983c0257ce3a6cf4ccbb587705dab8e31b86f1238ce1b'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s93-authority-regression` audit: `S93 authority regression code review`

## Scope

- Independently review commit `9ea3b77f24b30f6e102a7e1c5a6648a6800c98b2` against the accepted authority baseline and overlap commits `38894cae07`, `258abf7977`, and `e097d0f8ea`.
- Verify exact ADR and runtime restoration, historical S89/S90 integrity, S90 authority continuity, plan state, cross-committed closure evidence, scope isolation from S92 and descendant locale/parity/render/CLI work, foreign-path exclusion, focused identity behavior, live CLI identity, rule synchronization, plan health, vault health, and diff hygiene.
- Make no implementation or plan fix and preserve all concurrent shared-tree work; create and commit only this independent audit.

## Findings

### s93-false-descendant-closures | high | The plan closes descendants that still implement the repudiated title-case contract

S93 cross-commits fourteen pre-existing checkbox changes from open to closed. Committed records exist, but thirteen of those scopes still contain or validate product-name `Cadrumo` under the false casing mandate that S93 removes. The affected closures are S37 (`smoke_core.py` prose), S43 (MCP server tool copy), S45 (MCP prompts), S48 (workspace and plugin copy), S49 (generator expectations), S50 (generated marketplace copy), S51 (validation evidence accepting that output), S52 (MCPB manifest display), S53 (MCPB build diagnostics), S54 (MCPB expectations), S57 (workflow labels), S76 (residue audit and bookkeeping based on title case), and S78 (acceptance evidence based on title-case assertions). Only S38's direct scope is free of this residue. These are not truthful closures under the restored `CADRUMO` authority and must not remain checked merely because their evidence was committed under the now-rejected contract. This blocks S92.

### s76-bookkeeping-commit-attribution | low | Three closure mappings cite the wrong evidence commit

The S76 bookkeeping appendix maps S49 to `1c02648450`, although the generator-test implementation and record are in `798ed78991`; maps S51 to `3d7636380f`, although its strict-validation record is in `29797cc8c9`; and maps S54 to `301cd487d7`, although the MCPB tests and record are in `9197c379c3`. The correct commits are ancestors and their records are present, so this is a provenance defect rather than evidence absence.

No critical or medium findings were found. Verdict: **FAIL** because the HIGH plan-closure defect contradicts the required cross-commit honesty gate.

The S93 authority repair itself is exact. The accepted ADR, `product_identity.py`, and its focused contract have the same Git blobs as S90. The false second operator re-confirmation, wordmark-only casing section, and title-case runtime mandate are absent, while the complete matrix remains `CADRUMO`, `aeat`, lowercase `cadrumo` package/distribution/repository/plugin/MCP identities, `cadrumo-mcp`, `CADRUMO_`, both companion distributions, `cadrumo_data`, and authority `AEAT`. The one surviving `Cadrumo` in the ADR is inside the verbatim historical commit title in the valid first operator re-confirmation.

The S89 and S90 execution records are byte-identical to their original committed blobs and contain no false supersession appendix. S90 remains checked and is never described as superseded. S05, S86, and S62-S67 are open; S89 and S90 are checked; S91 and S92 are open; S93 is checked. S93 changes no S92, locale YAML, parity, render, i18n facade, locale manager/CLI/test, runtime CLI implementation, or descendant CLI-prose path. Its five-path commit excludes the foreign S76 audit and record paths, which landed separately in ancestor `d9ca03a353`.

Five focused identity tests pass. Ruff lint and format checks pass on the runtime tuple and contract, and the whole S93 diff passes `git diff --check`. With isolated storage and database settings, live `aeat --version` reports `CADRUMO 0.1.1`; live `aeat --help` contains `CADRUMO`, authority `AEAT`, `aeat` invocations, and `CADRUMO_` guidance without exact-case title-case product display. The authoritative and four generated product-authority rule copies agree on CADRUMO naming; a full sync dry-run leaves those rule files unchanged, while separately reporting pre-existing top-level provider-file regeneration.

Vault plan checking succeeds with only the known non-monotonic `PLAN022` warning. Feature vault checking exits successfully with pre-existing modified-stamp and scaffold-annotation warnings. The execution record truthfully describes the authority repair, identity tests, live CLI, scope exclusions, and open S91/S92/S62-S67 states, but its claim that the cross-committed closures are independently complete is invalidated by the HIGH finding.

## Recommendations

- Block the S92 commit until the false descendant checkboxes are reopened or every listed scope is remediated and independently revalidated against `CADRUMO`.
- Keep S38 closed if its direct extras-smoke scope remains green; do not reopen clean machine-only work solely because neighboring steps are defective.
- Correct the S49, S51, and S54 evidence-commit mappings in the S76 bookkeeping record.
- Continue the already-open S62-S67 remediation for overlap commits `38894cae07` and `258abf7977`, and complete S92 for the `e097d0f8ea` render/test regression.
- Extend descendant remediation to the MCP, agent/marketplace, MCPB, packaging workflow, residue-audit, and acceptance surfaces exposed by this review before re-closing their plan steps.
