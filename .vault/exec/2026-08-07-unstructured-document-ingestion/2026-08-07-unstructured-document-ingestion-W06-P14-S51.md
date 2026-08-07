---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e8c64a43cbcedeba081272e03781f351d900f02a39f105b759ec4c1ac82f4b14'
step_id: 'S51'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

Add the `aeat config provision` verb family: report, model pull with progress and
a pre-load contention check, and readiness verification. No implicit pulls, no
daemon spawn.

## What landed

- `application/provisioning.py` — `PullProgress`, `PullOutcome`,
  `pull_runtime_model`, `ReadinessOutcome`, `verify_model_ready`.
- `_config/_provision_payloads.py` — four registered output schemas.
- `_config/_provision_cli.py` — the `report` / `pull` / `verify` subgroup.
- `_config/__init__.py` — registration.
- Locale keys: 8 keys × 4 catalogues = 32 real values, set through the locales
  CLI.
- `application/tests/test_provisioning_hardware_contention.py` — 5 cases
  appended to the existing loopback harness rather than a second one.

## The defect worth recording: a zero requirement is a fail-open

An unknown memory requirement was initially returned as `0`. That flows into the
contention assessment as "this model needs nothing", so the check reports
**admitted on evidence nobody has**. It is the same inversion the decision
forbids — unknown must never read as free headroom — and it looks harmless in a
diff, which is what makes it dangerous on a machine with under 4 GB free.

Measured on one injected profile, 1 GiB free against a 40 GiB requirement:

```
real requirement 40 GiB -> admitted=False  causes=['peer_process']
ZERO requirement, SAME machine -> admitted=True
```

The fix returns no pair at all, so the assessment is SKIPPED rather than faked;
the caller already treats a missing pair as "not assessed". A skipped assessment
says "we do not know" honestly, where a zero-requirement one says "you have room"
falsely.

The invented-settings correction is the same class in miniature.
`cadrumo_llm_pull_timeout_s` and `cadrumo_llm_readiness_timeout_s` do not exist;
referencing them would have pinned behaviour to fields nobody sets. Replaced with
module constants beside the shipped `_OLLAMA_PROBE_TIMEOUT_S`, following that
precedent. The values are deliberate and should not be "tidied": a pull gets
3600s because the 2s probe bound would abort every real multi-gigabyte download,
and readiness gets 120s because a cold load of a small vision model is tens of
seconds on this class of hardware.

## Admission ordering is the point of the action

`pull_runtime_model` consults `assess_model_load_contention` FIRST and returns
without issuing the fetch when not admitted. A download that completes and only
then discovers it cannot be loaded has spent the operator's bandwidth to arrive
at a refusal that was knowable at the start.

The refusal carries the whole snapshot, so the payload reports `causes` as a
typed list rather than a rendered sentence — a caller can act on
runtime-resident versus peer-process without parsing prose. The remediation
rendered is the snapshot's OWN, and no unload verb is named: naming a verb this
Step does not build would hand the operator a dead instruction.

## Verification

35 passed on the extended harness. 515 passed on documented-command and
JSON-schema conformance. All three MCP subtrees resolve with their real
arguments (`pull` and `verify` carry `model` and `role`; `report` is legitimately
argument-free), so the schema builder ships no argument-free verb.

**Two mutations, both proven to bite**, applied from outside the repo — the
ordering mutation as a pytest plugin loaded with `-p`, so no tracked file was
edited:

- **Fetch first, assess after.** `test_a_refused_pull_never_issues_the_fetch`
  reds; the other two pull cases still pass, so the mutation is targeted rather
  than breaking everything.
- **Zero requirement.** Flips a measured refusal into an admission on the same
  machine, as tabulated above.

The unreachable-runtime refusals are driven against a REAL closed loopback port
(127.0.0.1:1, reserved and never listening) rather than a patched client, so the
refusal is produced by an actual failed connection. Each refusal has a positive
control: an admitted pull DOES issue the fetch, and a readiness check DOES report
ready against a live stub — without those, a function that refused
unconditionally would satisfy every refusal assertion in the file.

## A corrected assertion

The ordering case first asserted the runtime received NO request at all. That was
wrong about the product, not about the code: attributing a shortfall requires
reading the resident set, so `/api/ps` is expected and is part of the CHECK
rather than part of the fetch. The assertion now names `/api/pull` specifically,
which is the claim that actually matters to an operator's bandwidth. The reason
is recorded in the test docstring so nobody restores the stricter, wrong form.

## Operational note

The locale catalogues are shared and this share loses concurrent writes: 3 of 32
values were lost to races on the first pass, with `atomic_write` reporting
standard-tier failures. A single pass silently leaves placeholders, and a
placeholder is refused by the shipped honesty gate — so the failure surfaces
later, in someone else's run, as an unexplained red. The retry re-set only keys
still holding placeholders, so it could not clobber a value that had landed.

The scaffold-then-set sequence unavoidably creates a local window where the
catalogues name verbs the command tree does not yet carry. The registration must
therefore land in the same commit as the catalogue change; a key promising a verb
that does not resolve is a dead operator instruction.

## Boundary held

Pull and inference logic were written and neither was executed. No model was
loaded, pulled, or queried; every test drives a loopback HTTP server, never a
real runtime.
