---
tags:
  - '#adr'
  - '#broad-test-failure-repair'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:36857ab836272e4d59ffd8edff4afa47daa5298906c1ce72e70228c94a197fbe'
related:
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-07-02-arch-remediation-data-budget-adr]]"
  - '[[2026-10-07-broad-test-failure-repair-progress-audit]]'
---
# `broad-test-failure-repair` adr: `Restore corpus wheel distributability with a normative companion` | (**status:** `accepted`)

## Problem Statement

The strict companion-wheel size regression now fails: the official wheel is 105,862,342 bytes against the existing 100,000,000-byte cap. The manuals wheel is 96,673,670 bytes. Their sum exceeds two caps, so a two-package rebalance cannot preserve the complete corpus under the current build representation.

## Considerations

Measured real wheels come from `var/storage/development/.logs/test-runs/2026-10-07/20261007T173308.995450Z-pytest-17188-0098ae65/run.log` and its `cr_17188_8c6bdc/pytest/cadrumo-data-wheels0` scratch artifacts. The official archive contains compressed normative sources totaling 40,356,974 bytes, AEAT sources 64,387,091 bytes and EU sources 1,004,759 bytes. Recompressing every member with DEFLATE level 9 still yields official 105,547,177 bytes and manuals 96,036,982 bytes, excluding no content. The failure brief records this packaging case; this measurement updates its diagnosis.

## Considered options

- Add a normative-source companion: retain every source byte, use an existing corpus directory seam, and keep each package below the current cap. Chosen.
- Rebalance between the two existing companions or increase compression: insufficient measured combined capacity.
- Raise the cap, remove reviewed sources, or make a companion optional: rejected because each weakens an existing delivery constraint.

## Constraints

The cap, whole-tree budgets, exact-version dependency rule, disjoint exhaustive ownership, implicit namespace and offline resource paths remain unchanged. Derived surfaces remain in the root wheel. This proposal grants no upload, release or publication authority.

## Implementation

Add mandatory `cadrumo-data-normatives` owning only binary files under `corpus/normatives`; `cadrumo-data-official` retains `aeat_official` and `eu_official`, and `cadrumo-data-manuals` retains `manuals`. The root requires all three at its exact version. Update canonical product identity, build and install cohort manifests, artifact validation, release version synchronization, package-manager projections and clean-install proofs together. Incomplete old three-distribution cohorts must refuse current-cohort validation; no missing-companion fallback is permitted. Prove archive ownership, bytes, versions and all three size limits through actual builds and the joined installed namespace.

## Affected accepted wording

The approved amendment updates `2026-06-28-product-packaging-adr` to specify three data companions and four Python distributions, move BOE/normative binary ownership from official to normatives, and preserve every other cohort constraint. Amend `2026-07-02-arch-remediation-data-budget-adr` so the earlier decision to defer rebalancing is historical: its premise that both wheels fit is invalidated by the measured growth. Three mandatory companions replace two; all numeric ceilings and exhaustive ownership guarantees remain unchanged. These are scoped ownership/count refinements, not supersession of the immutable-cohort or budget decisions.

## Rationale

A third existing-directory partition restores distributability without losing legal evidence or moving runtime-derived data merely to evade its own budget. It supplies substantial official/normative headroom, while the manuals margin remains small and must continue to be measured.

## Consequences

Release tooling gains one mandatory wheel and sdist. Existing installations upgrade through the root's exact dependency pin. Reconsider if any actual package again reaches the unchanged cap. Acceptance records authority only; it does not claim completed migration or successful installation.

## Approval (2026-10-07)

The user explicitly approved the third mandatory companion while preserving all files, paths, exact-version pins and existing caps. This accepts the concrete proposal and its scoped amendments to the prior accepted decisions.
