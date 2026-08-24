---
tags:
  - '#audit'
  - '#release-readiness-drive'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fcd57c79467c9b7a9a46b6141cf95b6ab0a9642f949f476142794004f2eefddc'
related: []
---

# `release-readiness-drive` audit: `release readiness drive: the cohort chain and the unsatisfiable platform floors`

## Scope

Driving `dev.release.readiness` to all-PASS. Final measured state: 4 PASS
(project-names-canonical, version-surfaces-agree at 0.2.2, changelog-ready,
no-open-release-blockers), 2 BLOCK, 1 WARN. Both BLOCKs are one missing
artefact, `var/release-cohort`.

## Delivered

- The readiness gate crashed before running: `ArtifactKind.PYTHON_WHEELHOUSE`
  was surfaced by no download channel, which the descriptor contract requires.
  Added `python-wheelhouse` to the `python` channel.
- `_export_names` did not strip the editable marker, so the workspace member
  `cadrumo-harness` resolved as missing and failed the cohort export check.
- A wheelhouse assertion tested whether the product extends a host
  application, which stopped being true once both host-extension channels
  shipped. Repinned to the owning channel tier.
- Restored `capture_owned_server_launch` and `_initialize_server_name` with
  their imports; three modules still imported the deleted symbol.
- Restored the cohort fixture's harness-wheel and `mcpb` real-zip branches.
  `REQUIRED_ARTIFACT_KINDS` still carries `cadrumo-harness-wheel`,
  `claude-plugin`, `mcpb` and `claude-marketplace`, so the fixture was stale
  against its own authority.

Preflight moved from 33 failed / 351 passed / 1 error to 25 failed / 365
passed / 0 errors, with no regressions.

## Open: the platform floors are unsatisfiable

`plan_runtime_wheelhouse` cannot select a wheel for four packages on Linux and
two on macOS. Measured minima: `argon2-cffi-bindings` 2.26, `greenlet` 2.24,
`pikepdf` 2.26/2.27, `pillow` 2.27; `pikepdf` macOS 14.0, `pypdfium2` 13.0.
The minimal satisfiable pair is glibc 2.27 with macOS 14.0. The declared
floors are glibc 2.17 and macOS 11.0, so the gate has never been satisfiable
on three of four targets since it was authored.

Narrowing the runtime closure is NOT available: `pikepdf`, `pillow` and
`pypdfium2` are declared direct core runtime dependencies, and pillow was
deliberately promoted from transitive to direct.

`TargetPlatform.floor` is decorative for selection — `_platform_rank`
hardcodes the tuples and never reads it. Editing only the declarations changes
nothing; editing only the constants ships a wheelhouse that attests a floor it
does not honour. Any fix must derive the tuples from the declared floor, and
must move the three sites asserting the manifest floors by exact-dict equality
in the same change.

Raising the Linux floor drops only already-EOL distros. Raising the macOS
floor drops Big Sur, Monterey and Ventura, which is a product support-policy
decision and is escalated, not decided here.

## Open: two channels claimed without an evidence path

The shipped descriptor claims `claude-plugin` and `mcpb`, but the publish
workflow declares only `packaging_run_id`, `scoop_run_id` and
`homebrew_run_id`. One commit retired those lanes and a later one restored the
channels without restoring their inputs. Wiring them or withdrawing the claim
is a pipeline decision.

## Open: a cohort-bound emitter with no cohort at the call site

`materialise_plugin` and `materialise_marketplace` gained a required `cohort`;
the distribution-identity verifier calls both without one. It accepts no
cohort parameter and the protocol requires real built wheels, so this needs a
design decision rather than a patch.

## Note on method

The first attribution asserted every preflight failure belonged to one
campaign. An adversarial verifier refuted it: twelve did not, one cause was
undercounted, and a nine-failure cause in a test fixture was missed entirely.
Seven failures were shared-worktree collateral — the fixture builds from a
pristine HEAD extract while the installed CLI reflects uncommitted work, so
any peer's dirty file reds them. A floor ruling was likewise verified
adversarially before any edit; the verifier refuted the closure-narrowing
alternative and confirmed the direction.

A closing caution from that verifier, worth keeping: a floor that always
equals the resolver's output is a readout, not a floor. Nothing stops the next
dependency bump from forcing another rise. The disciplined shape is a declared
policy floor that fails the build when a bump would breach it.
