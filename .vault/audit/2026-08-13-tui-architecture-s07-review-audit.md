---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:00c1a1b004b299da45712f31b39bf480dbdb401a573df723e66b85d964eb2417'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---

# `tui-architecture` audit: `W01.P02.S07 independent review`

## Scope

Independent review of `W01.P02.S07`: the governing operation-envelope decision, narrow core facade promotion, operation identity/request/snapshot/receipt models, direct tests, and Step evidence. The review checked strict immutability, aliases, correlation and temporal invariants, refusal semantics, payload ownership, step boundaries, and import hygiene.

## Findings

### mutable-request-payload | high | A frozen request can retain a mutable submitted operand

`OperationRequest` accepts any `BaseModel` payload. `STRICT_FROZEN_CONFIG` freezes only the wrapper; it does not make the nested model immutable or require that payload model to be strict, frozen, and extra-forbidding. A caller can therefore submit an ordinary mutable Pydantic model and mutate its fields or nested containers after request validation, changing the authoritative operand without creating a new request identity or revision. The sole round-trip test uses a deliberately strict/frozen payload and therefore does not exercise or refuse this admitted form. This breaks the Step's immutable-request contract and weakens the later exact approval, idempotency, journal, and replay guarantees.

## Recommendations

- Make the operation request own an immutable validated snapshot of its typed operand, or enforce and mutation-test a payload protocol that guarantees deep immutability and strict validation. Do not move domain payload schemas into the generic platform.

The remaining reviewed surface is sound: `OperationId` reuses `Hex64Str`; definition and revision aliases are constrained; identity, request, revision, condition, effect, settlement time, and receipt correlation fail closed; UTC validation is canonical; terminal refusal/result meanings are separated; and no capability, event, interaction-token, journal, or transition behavior is pulled forward. The core facade change promotes only the nine S06 public axes. Focused Ruff, 10-test pytest, basedpyright, and private-import evidence are green, but none covers a mutable payload. No critical finding remains.

## Final re-review disposition

### mutable-request-payload | open-high | Admitted mapping proxies retain mutable backing state

The recursive validator correctly requires strict, frozen, extra-forbidding Pydantic models, rejects declared private attributes, walks model fields and immutable containers, and rejects ordinary lists, dictionaries, sets, unsupported objects, and direct model cycles. However, it explicitly admits `MappingProxyType`. A mapping proxy is a read-only view, not an immutable value: a retained reference to its backing dictionary can add, remove, or replace request payload facts after validation. A self-referential backing dictionary also defeats the current cycle guard because the proxy identity is never added to `visiting`; each descent instead wraps its items in a newly allocated tuple, so recursion does not fail closed through the declared cyclic-reference error.

The four new mutation cases prove non-strict model, non-frozen model, list, and dictionary refusal only. They do not prove nested-model admission, private-state refusal, cyclic model/container refusal, or safe handling of an admitted mapping proxy. Ruff, 14 tests, basedpyright, and private-import tests are green but do not close this escape. The generic type parameter is preserved and the validator does not mirror domain schemas, but the original exact-operand guarantee remains open. No critical finding remains.

## Final closure disposition

### mutable-request-payload | closed | Payload custody is recursively fail-closed

`MappingProxyType` admission is removed, so a borrowed read-only view over mutable backing state is rejected. Cycle tracking now begins at the common traversal boundary for every model, tuple, and frozenset before descent, producing a controlled path-specific refusal. Strict, frozen, extra-forbidding configuration is required for every nested model, private attributes are refused, mutable and unsupported containers remain rejected, and a nested strict-frozen model with tuple values is admitted without weakening generic payload typing or copying domain schema logic.

Real tests prove backing-dictionary mutation through a mapping proxy, controlled self-referential-model refusal, private-state refusal, valid nested-model admission, and the earlier list/dictionary/configuration cases. Final evidence records Ruff passed, 18 model tests passed, basedpyright reported no diagnostics, and the focused private-import gate passed. No critical, high, or medium findings remain.
