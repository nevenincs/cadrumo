---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6517c2319953881e8b142f2fd5d3ab1c48a3a5a95a21d9ba474ce13cce20f0b9'
step_id: 'S76'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Record the Modelo 390 applicability ruling in its GOVERNING home, not only in this plan, and note what is currently blocking broad measurement. The ruling was implemented and verified under the sibling Steps, but a plan Step is an execution record and an ADR is where a decision lives; leaving it here only would have left the accepted 2026-07-01-modelo-303-regimen-simplificado-adr silently contradicted by the code implementing it. Appended as its 2026-08-28 amendment through the vault set-body verb so the modified stamp and body hash stay honest, previewed with --dry-run first. It is an AMENDMENT rather than a new record because it refines an accepted decision on the same scope: that ADR already owns the not-claimed-is-neutral vocabulary, and this enrols its LAST call site rather than establishing a competing rule -- authoring a sibling ADR would have started exactly the supersession-chain sprawl the pipeline forbids. The amendment states what S84 left unsettled (WHO the handoff is required of), grounds applicability in LIVA art. 122 Uno from the bundled corpus, records that the arrival-path invariant is unchanged and binds on a corrected antecedent, and explicitly carries forward the one question deliberately NOT folded in: whether a 390 may require a filed 303 4T at all wherever the family applies is a separate decision needing its own owner. BROAD RE-MEASUREMENT IS BLOCKED, and not by anything in this campaign. A peer is mid-relocation making src/cadrumo/adapters/persistence/storage/__init__.py inert by removing its re-exports, which is the correct end state under the inert-namespace rule, but consumers including src/cadrumo/tests/master_key.py still import KEY_SIZE and SecretStoreError from that namespace, so every broad pytest run dies at conftest import. The same campaign broke and self-healed twice within minutes -- once here, once on domain/iva DEDUCTIBLE_INPUT_FLOW_DIRECTIONS, and once leaving a literal IndentationError from an insert landing inside an indented block. Their files were deliberately NOT touched: this is uncommitted WIP in a shared worktree, relocations become atomic at commit, and editing a peer's half-landed sweep is how two agents start fighting over one index. The measurement is retried instead, and the honest status is that the suite is intermittently un-runnable for reasons outside this lane

## Scope

- `.vault/adr/2026-07-01-modelo-303-regimen-simplificado-adr.md`

## Changes

- `M` `.vault/adr/2026-07-01-modelo-303-regimen-simplificado-adr.md`

## Notes

- ADR-lifecycle provenance only: `a232800b14d15bc65427d81dc12c261ad57cbef4` appended the accepted 2026-08-28 amendment to the governing ADR and updated this plan row. The amendment keeps the decision single-homed: taxpayer applicability governs the annual-summary handoff, while the general filed-303-4T prerequisite remains a separate question.
- S75 implementation in `94187f454c55ddd1df6265d7f66601c0df4fdfe2` is downstream relation only. This record does not borrow its historical plan test statement or claim a source action.
- The plan's broad-suite block is historical context, not a current green or red receipt. No literal historic test or CLI transcript is recoverable. Current annual-summary and calculation-actions files are `MM` shared WIP, so no fresh current-code or pytest claim is made.
