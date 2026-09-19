---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:4801f9a91feab404eba8c5ff2b1b79e93c18eb33441ce416a666847106068136'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `registry facade family census`

## Scope

Audit the private-to-public registry module relocation recorded by `c94133f29516b12e3529f3d154c31592562f6198`, rather than replaying that already-delivered mechanical change. The fixed c941 rename delta supplies the 78-pair denominator. The reviewed source and consumer evidence is read exclusively from immutable clean Git object `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`; it is not derived from the current worktree. The archive includes authored source, tests, fixtures, manifests, receipts, tooling, and documentation while excluding generated registry data.

The checked matrix records one independent future disposition per pair. It is evidence and scheduling only: this audit implements no registry family disposition.

## Findings

### registry-facade-c941-denominator | medium | exact historical family requires individual disposition gates

The historic `git diff-tree -r -M` evidence names exactly 78 one-to-one renames beneath `src/cadrumo/domain/calculations/registry`. The checked matrix refuses a missing, extra, duplicate, unrelated, grouped, unresolved, or many-to-one pair. Every row records parent-facade exports, immutable source locators, categorized consumers, literal dynamic imports, unresolved nonliteral dynamic-import sites, a structured per-row owner locator census, competing in-family sites, substitutability rationale, terminal destinations, and a distinct canonical follow-on Step.

Relative `ImportFrom` targets are resolved to absolute modules. Once a resolved target matches a candidate, the consumer source path is placed in both the candidate's direct-module set and its operational category, even where the relative import contains neither candidate module string. The end-to-end regression anchors `src/cadrumo/adapters/inbound/declaracion/_parser.py` as a direct `production` consumer of `_authority.py`, not merely a transitive consumer. Legacy annotations and `ast.TypeAlias` nodes are included; package member attributes are attributed to one owning facade member rather than every row. The immutable measurement record is regenerated with the evidence commit, not a hard-coded test number, so source evolution cannot silently retain stale edge evidence.

`R01` through `R78` follow deterministic bytewise old/new-pair order. The Sol disposition packet is normalized by named module: `schema.py` is the hard-move special while `schema_verification.py` remains keep-public. The inventory is 54 `keep_public`, 9 `hard_move_complete`, 13 `privatize_external_elimination`, and 2 `delete`. The hard-move cases reserve the remote-authority move to `src/cadrumo/core/remote_authority.py`, `ENCODING_ALIAS_MAP` to `src/cadrumo/domain/calculations/registry/schema_exports.py`, and the `schema.py` local-definition cut with borrowed bindings routed to their existing owners.

### registry-facade-rag-owner-anchors | medium | semantic discovery is distinct from immutable AST evidence

The Sol HIGH remediation executed two `vaultspec-rag` production-code searches in the isolated remediation worktree and retained their actual request/result fields only on their reviewed rows. R01 queried `AEAT remote read host authority canonical hostname only:prod` under request `eec115fcf1ae4225b7e9209afc205b2b` and selected `src/cadrumo/domain/calculations/registry/aeat_hosts.py:19-51`; the complete module read and exact confirmation cover `canonical_remote_hostname` and `REMOTE_READ_SCHEME`. R55 queried `ENCODING_ALIAS_MAP registry schema export value policy only:prod` under request `f8cff429a3cd4d8fa1dc335774db9e47` and selected `src/cadrumo/domain/calculations/registry/schema_exports.py:1-41`; the complete module read and exact confirmation cover its `ENCODING_ALIAS_MAP` use and the current `record_spec` import pending the hard move.

Those structured RAG records carry query text, corpus/domain/preference, request ID, result ID, path, score, source, range, and returned structural fields. They are not immutable AST locators. The `semantic_evidence` owner-definition and competing-site locators remain a separately generated, machine-checked census from `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`; the schema rejects an AST-locator-shaped object in the RAG result field. The other 76 rows deliberately carry null RAG fields rather than claiming unperformed semantic searches.

A separate current-terminal report observes future S176--S254 work against the working tree. It accepts a removed public candidate or private relocation as a valid pending terminal state and never demands a shim, alias, forwarding module, or re-export. It is intentionally separate from the immutable S175 evidence check.

### registry-facade-independent-review | resolved | final Sol review passed and S175 is closed

Independent Sol review of frozen `976d47eb75` failed because its census was worktree-derived, did not fully resolve relative imports or `ast.TypeAlias`, dropped nonliteral dynamic imports, used imprecise package attribution, and had boilerplate semantic evidence that could not survive later H/P/D terminal changes. Its subsequent HIGH finding identified that a resolved relative import was only placed in the direct module graph, and that AST locators had been labelled as RAG results.

This remediation binds the regenerated schema-v2 matrix to `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`, records direct relative-import categories, retains the two genuine semantic-search anchors, keeps structured machine-anchored source evidence and terminal-state observation, and adds regressions for source measurements, TypeAlias, fixture ordering, dynamic imports, package attributes, dirty-worktree immunity, future terminal disappearance, direct relative consumers, and RAG-schema precision. Independent Sol review passed the remediated isolated commits `9f23e2c83fa15533745a95750b165826fae60878` and `9192817886bbda187d4827d585ec476a45c9494c` with no remaining severity finding.

Integrated-main follow-up found the reported `_schema_verification.py` drift in 28 externally dirty reviewed `semantic_owner` and `alternative_owner_evidence` rows, not in the immutable generator: the source files were byte-identical, fresh UV-managed checks passed from both worktrees under two hash seeds, and the checked matrix matched in the isolated review tree. The remediation nevertheless makes symbol maps, compact locators, definition-site maps, and the definition-site tie breaker total-order deterministic, and proves the semantic-evidence digest in fresh interpreters with different hash seeds and a foreign process CWD. The reviewed files were integrated through `019fc412c8a4a1808f8990246ff37aa72c2fe7d0`, `fefbc8ff46a91491b4f6ad4b8cccd8b6e8060cbc`, and `426fdf9e68c7bb2302238b6aab03203b830c9655`; competing output remains recoverable on `preserve/s175-shared-wip-20260826` and `preserve/s175-owner-evidence-wip-20260826`. Final integrated immutable and terminal checks passed, and focused serial pytest passed 17 tests in 166.92 seconds. S175 is closed; the 78 disposition Steps and final package gate remain open.

## Recommendations

Execute exactly one canonical plan Step for each matrix row. Preserve the row-specific terminal state and direct-import evidence; do not fold several registry families into one Step. Run the final inert-package fixed-point Step only after all 78 individual dispositions close. Do not use this audit or its matrix as evidence that a hard move, privatization, or deletion has already completed.

### registry-facade-census-evidence-root | corrected | the census reads the current worktree

The paragraphs above describe the reviewed census as derived from immutable Git object `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8` with dirty-worktree immunity. The generator that shipped does not bind to that object: it reads `RELOCATION_COMMIT` through Git for the rename delta only, and every row anchors `census_root: current_worktree`. Consequently the reviewed matrix is a current-tree fixed point and drifts whenever a peer edits a file the census covers; `--refresh-reviewed` re-derives it while preserving every reviewed adjudication field. The generator also excluded its own generated artifact from the evidence scan, without which no generation could reach a fixed point at all. The independent-review outcome recorded above stands; only its evidence-root wording is corrected here.
