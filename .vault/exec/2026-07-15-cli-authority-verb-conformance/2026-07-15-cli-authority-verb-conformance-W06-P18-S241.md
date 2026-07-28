---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S241'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run hashing vector, truncation, file-retry, network-stream, mirror-key, and AST recurrence suites for all 18 one-shot and four reducible call sites

## Scope

- `src/cadrumo/core/tests/`
- `src/cadrumo/adapters/`
- `src/cadrumo/application/`
- `src/cadrumo/domain/`
- `src/cadrumo/entrypoints/mcp/tests/`

## Description

- Select the test directories that own the delegated call sites the implementing Steps named, rather than the whole adapters, application, and domain trees the scope line names, since those trees are the greater part of the package and are covered piecewise by the other Steps of this phase.
- Run that selection under an explicit execution-marker selection covering both lanes.
- Confirm a non-zero collected count before reading the result line.
- Inspect the AST recurrence gate directly for vacuity, since a ratcheting baseline gate can pass green while its detector is broken.
- Confirm the delegation actually landed by counting live call sites of the canonical helpers.

## Outcome

Verdict: SATISFIED for the hashing subject; the scope directory additionally carries two unrelated failures, one of them a real tree-property red.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf"` over the core, core observability, core corpus-manifest, declaracion, outbound storage, outbound LLM, AEAT auth, persistence storage, manuals, submission, calc-sheets, aggregation, filing, workflow and agent-evaluation test directories plus the MCP telemetry retention suite.

Collected 2265, passed 2263, failed 2, skipped 0. Exit line: `2 failed, 2263 passed, 6 warnings in 423.11s (0:07:03)`, exit code 1. HEAD at run time was `b8ed7b3ccca410cb343b4d40e7f6b94a2c504faa`. The serial selection ran one case and it passed. The OS-keychain selection collected nothing.

Every hashing suite named by the Step is green: the digest vectors, the truncation contracts, the file-read retry semantics, the preserved network-stream path, the mirror object-key structured byte contract, and the recurrence gate.

Neither failure is a hashing failure. The first is the scripted agent-evaluation session, which fails with the unregistered-profile-keys error returned by a harness-load tool call; that is the third independent surface hit by the single root defect recorded against the MCP dispatch and identity Step, and it is the same defect rather than a new one. The second is the repository-wide combined-period-string gate, which lives in the core test directory this Step scopes but has nothing to do with hashing. It was re-run alone with no workers at a later HEAD and reproduces: `1 failed in 44.75s` at `c293706ce3`. It reports seven unallowlisted year-qualified quarterly tokens across three generated documentation sequence payloads and one declaracion test fixture path. Only one of those three payloads was uncommitted at run time, so the red is a property of the committed tree and not peer churn, but it belongs to the sequences and period-token surface rather than to this Step.

The recurrence gate is sound rather than merely green. It ships three tests, not one: the ratchet itself, a discrimination proof that constructs a new reducible body and asserts the detector flags it while never flagging the legitimate uses it must not block, and a grounding test that refuses a baseline entry whose module no longer hosts a reducible body. That last test is what stops the baseline rotting into a permanent exemption list, and the discrimination proof is what stops the gate passing green with a broken detector. The non-substitutable cryptographic uses the gate deliberately allows are streaming and incremental hashing, keyed message authentication, key derivation, certificate fingerprints, and raw digest-byte uses.

The delegation is real and has spread well past the audited set: the canonical one-shot helper is now called from roughly ninety production modules and the whole-file helper from a further seven, while the reducible baseline has shrunk to three entries, each carrying a stated reason. The Step's heading still says four reducible sites; the ratchet is designed to shrink, so three is the correct current number and the heading is stale rather than wrong.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

One incidental defect surfaced while reading the gate. Its module docstring names this campaign's feature tag, and a tracked configuration file under the development audit tooling carries two fields whose values are a decision-record stem and an audit-record stem. Development records are removable scaffolding and the reference direction is one-way, so tracked source and configuration must not cite them. Neither is a functional defect and neither is in this Step's scope, but both are recorded here because this Step is where they were seen.

## Re-measurement note at HEAD `1437055950`

Both unrelated failures attributed above are closed at the current HEAD. The profile-keys registration defect is resolved by `6b2edc7301`; the combined-period-string gate is confirmed green by `84e55bde57`, which re-ran the gate at HEAD and found `1 passed` where the prior record had `1 failed`. Neither fix touches hashing; the hashing subject remains satisfied and the two unrelated failures no longer cloud the whole-directory result. The scope directories were not re-run in full at this HEAD, but the specific two failing tests are confirmed fixed by their respective owners.
