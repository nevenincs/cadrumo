---
tags:
  - '#adr'
  - '#application-distribution'
date: '2026-10-13'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:f2bc5f2ee674a56df3035ae64c9d7d2ddfb06d151aebe37520c97a7db261f608'
related:
  - "[[2026-10-04-application-distribution-adr]]"
  - '[[2026-08-06-llm-package-split-research]]'
  - '[[2026-08-07-unstructured-document-ingestion-provisioning-adr]]'
---

# `application-distribution` adr: `Native bundle installs the llm extra` | (**status:** `accepted`)

## Problem Statement

The native application package installs only the locked base closure of the `cadrumo` distribution. Every model-bearing surface sits behind `require_optional_extra(LLM_EXTRA)` (D8 of `2026-08-07-unstructured-document-ingestion-provisioning-adr`), so in the packaged app each of them refuses with `ERROR_OPTIONAL_EXTRA_MISSING` before it reaches a model. The packaged `ledger.classify.review` operation therefore cannot run, and with it the only review-gated operation that needs no remote service. A person who installs the desktop app has no supported way to add a Python extra to its private interpreter, so the refusal's `pip install cadrumo[llm]` guidance cannot be followed there.

## Considerations

- The `[llm]` boundary and its absent-extra behaviour are accepted at the wheel level (D8, D9 of `2026-08-07-unstructured-document-ingestion-provisioning-adr`); the `smoke_absent_llm` lane proves it on a core wheel install.
- The native package owns its locked Python closure privately (`2026-10-04-application-distribution-adr`); assembly refuses any installed distribution outside the selected closure (`dev/packaging/native/assemble.py:171`).
- Selection reads the locked closure through `active_requirements` (`dev/packaging/runtime_wheel_selection.py:168`) and `export_runtime_constraints` (`dev/packaging/uv_constraints.py`), which exports no extra today.
- The `[llm]` extra adds no model bytes; models are never package data.

## Considered options

- Keep the bundle core-only. Rejected: packaged model surfaces become permanently unreachable, because the app's interpreter is not operator-extensible.
- Install the extra into the bundle at first launch. Rejected: a networked, unpinned install inside a signed payload breaks the locked-closure and payload-integrity contracts.
- Select the locked `[llm]` closure at native assembly. Chosen.

## Constraints

- Applies to the native application package only. The wheel's default install stays core-only, and the absent-llm lane keeps proving the instructive refusal there; it is not loosened.
- The added distributions come from the same `uv.lock` resolution, version-pinned, wheel-only and target-selected, under the same assembly refusals as the base closure.
- Every other extra stays out of the bundle; this ruling named `llm` alone, and the 2026-10-18 amendment below adds `browser`.
- No model weights enter any artifact.

## Implementation

We will install the locked `[llm]` extra closure into the native application package's private site-packages. The selection that feeds wheel planning and assembly verification requests that extra for the native bundle, so the assembly closure check and the wheelhouse plan agree on one set. The bundled extras are declared once as `BUNDLED_EXTRAS` (`dev/packaging/native/product.py:31`) and passed only by native provisioning, assembly and the CMake build; the default constraint export still omits every extra.

Verification: the staged package contains the `[llm]` distributions (including `nvidia-ml-py`), and `ledger.classify.review` runs past `ledger.llm.acquire` against a model the person picked, reached through the agent service, on disposable data.

## Rationale

The packaged app is the operator's only installation, so a surface gated on an extra it can never install is an absent capability. Selecting the extra at assembly reuses the locked, verified closure path unchanged, while the wheel keeps the lean core D8 promised.

## Consequences

The bundle grows by the `[llm]` closure. Model surfaces in the packaged app now refuse for model or runtime reasons (no local runtime, model not pulled, hardware below floor) rather than for a missing extra. Reconsider if the extra gains a heavy native runtime or a licence the distribution cannot carry.

Authorization: the owner's ruling of 2026-10-13, "yes, we'll bundle the llm package set", given after the packaged review proof failed with `ERROR_OPTIONAL_EXTRA_MISSING` at `src/cadrumo/adapters/outbound/llm/text_classifier.py:76`.

### 2026-10-18 amendment: the browser extra ships too

The native application package also installs the locked `[browser]` extra closure: `playwright` with its platform wheel's bundled Node driver, `playwright-stealth`, and their locked dependencies (`pyee`, `greenlet`). `BUNDLED_EXTRAS` becomes `("llm", "browser")`, so wheel planning, provisioning, assembly verification and the CMake build select both extras through the same path as above. With them in the staged package, no AEAT browser surface refuses for a missing extra that the operator cannot install, the same dead end this decision removes for `llm`.

Every native target has a locked wheel for the added closure: `playwright` 1.64.0 ships `win_amd64`, `manylinux1_x86_64`, `manylinux_2_17_aarch64` and `macosx_11_0_arm64` wheels, and the other additions are pure-Python or already locked for each target.

The Chromium browser builds are not bundled. They are provisioned on demand into the installation-wide storage root (`components/playwright`) by the Rust component engine of `2026-10-24-rust-component-provisioning-adr`, so the packaged app's probe reports a browser that is not provisioned rather than an unavailable extra. The `[browser]` extra still ships, because Playwright's Python package and driver launch the browser at use time. No browser binary enters any artifact.

The other constraints stand: the wheel's default install stays core-only, the added distributions are locked, version-pinned, wheel-only and target-selected, and every remaining extra stays out of the bundle. The bundle grows by the `[browser]` closure, which is dominated by the per-platform Node driver.

Authorization: the owner's ruling of 2026-10-18, "Ship it", choosing to ship the `browser` extra alongside `llm` in the native application package with Chromium left to on-demand provisioning.

### Amendment 2026-10-25: local inference goes through the agent

Basis: the owner's first-hand rulings of 2026-10-25 in conversation, recorded in `2026-10-25-agent-owned-models-adr`: Cadrumo defines no AI model names, digests, sizes, licences, defaults, candidate lists or rankings; cadrumo-agent's provider catalogue is the sole source of providers and models, local ones included; every tax model call goes through the agent service.

- **Constraints and Implementation verification.** "No model weights enter any artifact" stands. The verification sentence "`ledger.classify.review` runs past `ledger.llm.acquire` against a locally provisioned model" reads: against a model the person selected and the Rust engine pulled, reached through the agent service. The `[llm]` closure no longer carries a Cadrumo-owned local inference adapter, because `LocalAdapter` is deleted.
