---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:3b0c2b3ba514b40e4796d997e645a6d55644d2e459abc13c47ed184f113a7e93'
step_id: 'S471'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Drop the retired subprocess provider probe and the deleted remediation field from the sandbox external tool pin test, since both were removed with the cloud transport and the executable-text advice it carried, leaving the case uncollectable and its PATH and browser pins unchecked on every run

## Scope

- `dev/docs/sequences/tests/test_runner.py`

## Changes

`TestAmbientEnvNeutralisation` passes: 5 tests, where one could not be collected
and took the class's import with it.

TWO RETIRED SURFACES, BOTH STILL BEING ASSERTED.

* `probe_subprocess_providers` is a NAMED MEMBER of the deleted set that
  `core/tests/test_cloud_transport_fully_deleted.py` asserts stays gone -- the
  "provider axis: its enum, its PATH probes, its availability records" family,
  removed with the whole subprocess LLM transport. The import outlived the
  deletion.

  This is the mirror image of S470. There the public name was right and the
  private definition was the half left behind; here the deletion was right and
  the consumer was the half left behind. Both are `no-legacy-compatibility`
  failures -- a retired surface's consumers are updated in the same change --
  and only reading the deletion contract distinguishes them.

* `DependencyStatus.remediation` held the fix as executable text
  (`"playwright install chromium"`). The model's own docstring says
  `precondition_verdict` "closes every unavailable outcome without embedding
  presentation or executable text", so the field was deliberately dropped --
  the same replacement of free-text advice by a typed verdict as `suggestion`
  to `action` in S467. The assertion now reads the verdict.

Only the deleted halves went. What the case exists to prove is that the sandbox
pins `PATH` and `PLAYWRIGHT_BROWSERS_PATH` beneath its own workdir, and both
pins are still asserted against a probe that really runs.

MY FIRST TEETH ATTEMPT DID NOT BITE, which is worth recording because it passed
and could have been reported as proof. Making the browser pin fall back to
`os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ...)` left the test GREEN: the
variable is unset on this host, so the fallback returned the pin and the defect
was a no-op. Removing the pin outright fails the case. A defect that cannot
change the observed value proves nothing about the assertion.

The pin is genuinely load-bearing here: chromium IS available on this
workstation outside the sandbox, so the case is measuring the sandbox rather
than a machine that never had a browser.

Teeth: removing the `PLAYWRIGHT_BROWSERS_PATH` pin from the sandbox fails the
case. Restored by copy.

## Notes

MY EDIT SCRIPT'S OWN GUARD FIRED ON MY PROSE. It refused to write while any
line mentioned the retired probe, and the docstring I had just written names it
deliberately to say what was removed. Narrowed to executable references. The
refusal was the right behaviour -- it declined to half-apply -- but the check
was too blunt to tell a citation from a call.

REMAINING SWEEP FAILURES, unchanged: 23 of them are one parametrised case in
`dev/registry/tests/test_generated_export_trees.py` across ten modelos, and
`dev/audit/tests/test_unreachable_code.py::test_the_live_reference_walk_read_every_file`
is the other. Plus the three operator decisions -- the 125 `cli.*` extras, the
5 `application.*` extras, and the `direction` spelling.
