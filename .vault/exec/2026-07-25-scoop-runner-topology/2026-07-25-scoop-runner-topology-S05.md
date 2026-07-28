---
tags:
  - '#exec'
  - '#scoop-runner-topology'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S05'
related:
  - "[[2026-07-25-scoop-runner-topology-plan]]"
  - "[[2026-07-22-scoop-runner-topology-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace scoop-runner-topology with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-25-scoop-runner-topology-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Adapt the Scoop acquisition lane to the ADR-ruled native execution, replacing the docker Windows-container preflight and the Container-mode harness invocation with a native Host-mode invocation pinned to the windows-scoop runner label, a preflight asserting AMD64 plus a resolvable Scoop in the lane user's profile, and a per-run Scoop profile reset that keeps acquisitions independent, and update the structural gate to pin the native shape and ## Scope

- `.github/workflows/packaging-scoop.yml`
- `dev/packaging/tests/test_scoop_workflow.py`
- `dev/packaging/smoke_scoop.ps1` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Adapt the Scoop acquisition lane to the ADR-ruled native execution, replacing the docker Windows-container preflight and the Container-mode harness invocation with a native Host-mode invocation pinned to the windows-scoop runner label, a preflight asserting AMD64 plus a resolvable Scoop in the lane user's profile, and a per-run Scoop profile reset that keeps acquisitions independent, and update the structural gate to pin the native shape

## Scope

- `.github/workflows/packaging-scoop.yml`
- `dev/packaging/tests/test_scoop_workflow.py`
- `dev/packaging/smoke_scoop.ps1`

## Description

- Retargeted the lane's preflight from the docker Windows-container check to the surface native execution depends on: AMD64, a Scoop profile complete with `apps`, `buckets`, and `shims` resolved the same way the harness resolves it, and a refusal on an elevated identity.
- Pinned the job to a fourth runner label so it schedules only onto the dedicated runner, and renamed the job to state that it is native.
- Replaced the `Container`-mode harness invocation with a `Host`-mode one, dropping the container image and the container-only timeout argument.
- Added an evidence-binding step between the smoke and the emitter, re-asserting the bindings the container orchestrator used to check.
- Staged `constraint_effect` alongside the other harness modules the smoke executes.
- Updated the structural gate to pin the native shape, added negative pins against the container invocation, and added a test that the binding check precedes the emitter.
- Corrected the release runbook's description of the lane.

## Outcome

The lane now expresses the accepted topology rather than the rejected one. It
ran against a preflight demanding a Windows-container Docker daemon while the
fleet's only daemon hosts the standing Linux runners and container modes are
exclusive per daemon, so the gate was unsatisfiable without tearing those
runners down on every run. Because Scoop installs user-scope with no admin, the
container supplied isolation and no evidentiary value, so the acquisition moves
into a dedicated non-admin runner user's own Scoop profile.

The preflight was retargeted rather than dropped. Its strictest new clause is
the non-elevation refusal: natively the privilege boundary *is* the
low-privilege runner user, so an elevated lane is a topology error and must
refuse rather than mint evidence from an administrator profile. Every refusal
names the operator action that clears it.

The profile reset the ruling asks for needed no new code. The host smoke
already refuses to start over a pre-existing app or persisted state, records
the profile's contents before it begins, and its cleanup removes every app,
bucket, and persist entry the run introduced and verifies their absence before
writing pass evidence. That is what keeps successive acquisitions independent
on a profile that is not disposable, so it was documented at the call site
rather than reimplemented.

What did need replacing was the orchestrator. In container mode the parent
verified the child's identity and source binding before returning; invoking the
smoke directly removes that parent. The lane now re-asserts those bindings
itself, ahead of the emitter: a passing native run, of this run's own generated
manifest, that cleaned up after itself, carrying a runtime identity and not
claiming a container identity it cannot have had.

Both new gates were proven to bite rather than merely pass. Five mutations of
the workflow (reverting to container mode, dropping the non-elevation refusal,
unstaging the harness module, defeating the manifest binding, unpinning the
runner label) were each applied to a temporary copy and each reddened the
structural gate. The binding check itself was executed against a synthetic
evidence shape: it accepts an honest native run, refuses each of seven
corruptions with a message naming the specific defect, and surfaces the smoke's
own failure reason when evidence is absent instead of a bare missing-file
error.

The row is not green and cannot be until the runner exists. What changed is
that provisioning it is now sufficient: before this step, the lane would have
refused at a retired gate no matter what the operator did.

## Notes

A latent break was found and fixed inside scope. The smoke asserts the
Scoop-installed venv landed on the manifest's pinned closure before the tax
oracle mints evidence on it, and the module that performs that assertion was
never copied into the token-free harness the lane executes from. The lane would
have died there with an import error the moment it got past the preflight, on
the operator's first native run. It never surfaced because the docker-mode
refusal fired earlier in every run the lane has ever had, which is the general
hazard of a gate that fails before the work it guards.

The harness script itself was left unmodified. Its `Container` mode remains a
supported path and the governing record retains a dedicated Windows-container
host as an explicit fallback should isolation requirements tighten, so the mode
is retained capacity rather than dead code. Only the lane's choice of mode
changed.

One unrelated red was observed and attributed rather than absorbed: a split
install sequence test times out in a real pip-install fixture on this loaded
workstation. It touches nothing this step changed. Every module that does cover
the changed surface passes.
