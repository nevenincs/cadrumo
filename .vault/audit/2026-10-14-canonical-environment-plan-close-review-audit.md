---
tags:
  - '#audit'
  - '#canonical-environment'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:e80c4ebcc9a6d84a0c4e0b237838592432e6b73efa844803e75a0cf321aa6885'
related:
  - "[[2026-10-13-canonical-environment-plan]]"
---

# `canonical-environment` audit: `plan close review`

## Scope

Plan-close review of the canonical-environment plan at HEAD `d2c52ff625`.

Verdict: PENDING. Findings and remaining items below are open.

The agent checkpoint lock was resynced in `0d0beb7cdf`. `bundle.environment-launch` and `bundle.environment-conformance` pass on a stage built from agent `1315871`. The working tree carries uncommitted fourth-amendment changes, described in `in-flight-amendment-unplanned`.

Remaining items:

- The POSIX `platform.invocation` is not compiled.
- The runtime-lifecycle view deadline, fixed by the ephemeral-operations work, awaits re-stage.

## Findings

### revision-rule-mismatch | medium | The store lifecycle's revision rule disagrees with the native invocation table and can leave the root blocked

`store_lifecycle.py:47` accepts `+` and 64 characters. `launch.rs:126-136` and `application_environment.py:50` accept `[A-Za-z0-9_.-]` up to 128. `_migrate` copies aside first, so exit 125 is classed FAILED, after which every start is refused as COPY_KEPT. Fix: derive one rule from the declaration and validate it before the copy. Map exit 125 to the native-refusal diagnostic.

### lifecycle-exceeds-start-bound | medium | Worst-case store lifecycle exceeds the frontend's agent start bound

`StoreLifecycleBounds` total about 145 s on the migrate path, while `AGENT_START_TIMEOUT_SECONDS = 120.0` (`frontend_client.py:88`). A slow migrate becomes an unknown outcome with the copy kept. Follow-on: phase the frontend bound or report preparing progress.

### root-slot-coverage | medium | Agent profiles take the storage root as a kind-only slot outside the accepted gateway slot list

`CADRUMO_LOCAL_STORAGE_ROOT` is a slot on `agent-gateway` and `agent-worker`, but committed constraint 11 lists only the hosted root, ports and relay, and constraint 8 says the root is resolved and pinned. Only the uncommitted fourth amendment adds it. Fix: commit the amendment with its approval basis, or pin the root.

### in-flight-amendment-unplanned | medium | Fourth-amendment work edits plan-owned files with no plan Step and currently breaks two gates

The working tree changes the ADR, the TOML, the composer, the probe, the conformance check and the contract docs. Conformance is red (`CADRUMO_AGENT_LOG_LEVEL`) and the spelling gate is red (`agent_host_fixture.py:90`, `test_agent_process_native.py:292`). Fix: add a P05 Step, then re-review on landing.

### agent-table-second-reader | low | The conformance check reads [agent] straight from the TOML

`environment_conformance.py:90` uses `tomllib`. Expose the validated table on `ApplicationEnvironment` instead.

### spelling-allowlist-scope | low | The spelling gate allows more files than constraint 20 names

`test_agent_prefix_spelling.py:83-105` allows package-side tests and runtime fixtures. Note the wider scope in the ADR, or narrow the allowlist.

## Recommendations

- `revision-rule-mismatch`: derive one revision rule from the declaration, validate before `_migrate` copies, and map exit 125 to the native-refusal diagnostic.
- `lifecycle-exceeds-start-bound`: phase the frontend start bound or report preparing progress.
- `root-slot-coverage`: commit the fourth amendment with its approval basis, or pin the root.
- `in-flight-amendment-unplanned`: add a P05 Step for the amendment work, restore both red gates, and re-review on landing.
- `agent-table-second-reader`: read the validated `[agent]` table from `ApplicationEnvironment`.
- `spelling-allowlist-scope`: record the wider allowlist in the ADR or narrow it to constraint 20.
- Close the remaining items (POSIX `platform.invocation`, runtime-lifecycle view deadline re-stage) before the verdict moves from PENDING.
