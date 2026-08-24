---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:530fd3a6efb0986a21969c34b3cda48c0b7924a3c708129b27ccb0b4281a6498'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-operation-observation-research]]"
  - "[[2026-08-24-tui-operation-observation-adr]]"
---
# `tui-architecture` audit: `s121 current only purge`

## Scope

Audited the PRE_RELEASE operation-persistence cutover against the canonical plan and current-only ADR. Reviewed the lease and journal readers, acquisition and inspection paths, parser wiring, refusal fixtures, exact symbol census, and focused operation test results.

## Findings

### current-only-cutover | low | No S121 safety defects found

The v1 lease model, retired operation-keyed path helper, acquisition migration method and call, and private journal parser wrapper are deleted. The remaining canonical persistence readers hydrate only lease schema v2 and persisted snapshot schema v6. Superseded journal markers are rejected without rewrite, and the narrow retired-path guard refuses operation-keyed lease files under the canonical lock without reading or mutating their bytes.

The real historical operation-keyed v1 filename/payload witness now requires both `inspect` and `acquire` to raise, keeps the original bytes unchanged, and prevents creation of a current v2 path. A valid v2 file whose scope and operation identities collide is still parsed as current, observed ACTIVE, and returned as a conflict without mutation. No production operation compatibility reader, migrator, or retired fixture remains in the scoped packages.

Vaultspec RAG located the canonical lease/journal authorities and the focused tests; exact scoped searches found no deleted symbols or migration/retired compatibility vocabulary. The focused current-only lease/journal matrix passed 50/50 and scoped Ruff passed. The previously run aggregate operation lane recorded 306 passes and one unrelated concurrent persistence-facade export assertion, outside this remediation.

### independent-s121-attestation | low | Runtime and artifact census remain clean

A read-only workspace/runtime census found no affected nonterminal operation invocation or durable operation lease/journal artifact requiring migration. The unrelated terminal profile handover artifact remains untouched. The historical witness is created only under `tmp_path`, and the test proves no successor write and exact byte preservation.

### independent-s121-retired-path-rereview | low | Retired-path detector is fail-closed without becoming a reader

An independent re-review accepted the final retired-path detector. It only compares canonical and retired candidate paths then uses `os.path.lexists` under the shared lock; it never opens, parses, migrates, moves, or rewrites retired bytes. The equality guard retains the valid scope/operation-ID collision path, and the focused 50-test matrix, Ruff, and source type check passed.

## Recommendations

No S121 code changes remain in this remediation. Resolve the concurrent facade baseline independently before using the aggregate operation lane as a global green signal; the S121 plan row is closed through the Vault CLI.
