---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S09'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---




# DONE as reviewed instructions, nothing pushed to either repository. Reference authored covering both developer CLIs, grounded in structured API reads of the live repositories on 2026-07-25 and attributing every fact to what it was read from. The consequential finding is that the derived matrix does NOT select the managed installers for these two, because their users can be assumed to hold the toolchain, so vaultspec-core's existing in-repository bucket is RETIRED rather than migrated into the shared repository, which is the opposite of the dashboard instruction and easy to get backwards. vaultspec-rag needs only the standalone-executable tier it currently lacks. Neither product declares a tag trigger, verified

## Scope

- `.vault/reference/2026-07-25-account-distribution-standard-vaultspec-cli-migration-reference.md`

## Description

- Read both repositories' layouts, workflows, bucket contents, and release assets through structured queries.
- Evaluate the derived matrix for both products.
- Author the migration reference, attributing every fact to what it was read from.
- Record what could not be verified from public data as unverified rather than omitting it.

## Outcome

Reviewed instructions exist for both developer CLIs. Nothing was pushed to either repository; each adopts these under its own review.

The consequential finding is a reversal that is easy to get backwards. The derived matrix does NOT select the managed installers for these two products, because their users can be assumed to hold the language toolchain, so `vaultspec-core`'s existing in-repository bucket is RETIRED rather than migrated into the shared repository. That is the opposite instruction from the dashboard's, and the two products differ on exactly one property.

`vaultspec-rag` has the simpler gap: it ships to the registry alone and needs only the standalone-executable tier.

## Notes

`vaultspec-core`'s committed bucket manifest is a self-labelled placeholder skeleton whose own comment block states the hash is deliberately absent because the assets did not exist when it was committed. It currently pins a version whose assets do exist. Whether its bump step has ever run to completion cannot be decided from the committed file alone, and the reference says so.

A related asset gap is recorded rather than smoothed over: only the two most recent `vaultspec-core` releases carry binaries, and every release back through several versions carries none. The executable channel must not be documented as available for versions whose assets do not exist.

Both products' publication workflows were read and neither declares a tag trigger.

Semantic search was degraded throughout, so every fact here comes from a structured API read, each attributed in the reference to the query that produced it.
