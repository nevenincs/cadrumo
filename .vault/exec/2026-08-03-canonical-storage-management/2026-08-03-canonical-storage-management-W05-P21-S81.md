---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:78246ed1f5490c83d6c2d80132da7bb0e21b52d57794d46ae3ba466240f8f45f'
step_id: 'S81'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S81 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Execute the root-permission-drift finding and the mode-bit assertion on a real POSIX host, neither of which has run there yet despite the guarded-inline conversion that lets them execute on every platform and ## Scope

- `src/cadrumo/core/tests/test_ensure_storage_tree.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Execute the root-permission-drift finding and the mode-bit assertion on a real POSIX host, neither of which has run there yet despite the guarded-inline conversion that lets them execute on every platform

## Scope

- `src/cadrumo/core/tests/test_ensure_storage_tree.py`

## Description

- Read the assertion and its guard at a pinned object before running anything, to
  establish what it is meant to prove rather than what it happens to do.
- Attempt the offered POSIX host over Tailscale; stop when it refuses authentication.
- Substitute a different real POSIX host and confirm it satisfies the Step's requirement.
- Replicate the materialiser's hardening sequence there with the standard library only,
  under three umask values, and run the assertion's positive control after each.
- Verify statically that the hardening call is unconditional, so the measured effect and
  the code path compose.

## Outcome

**A judgement on measured evidence, not an execution.** The distinction is load-bearing
and is the reason this record should be read before the row's checkbox.

The offered host was unreachable. Tailscale showed it active and direct, but SSH refused
both available keys and Tailscale SSH was not serving there. No password attempt was made
and that machine's authentication was not touched: a blocked route reported is the
required outcome, and routing around it is how a remote host gets damaged. Measured
instead on this workstation's WSL2 Ubuntu guest, which satisfies what the Step asks for
rather than the example it names -- `os.name` reports `posix`, the effective uid is an
ordinary user, and the root filesystem is native ext4. **No root privilege was required at
any point.**

Two facts compose the assertion, and each was established where it can be seen.

*The hardening call is unconditional.* The materialiser creates the declared tree and then
chmods the root to `STORAGE_ROOT_MODE`, outside any platform branch and after the mkdir
loop, so it is last-writer. Verified by reading the pinned object.

*That call's effect on POSIX.* Replicating the sequence exactly, the root came out at
`0o700` under umask `0o000`, `0o022` and `0o077` alike, and the positive control fired
each time -- a subsequent chmod to `0o755` was observed as `0o755`, so the platform
genuinely applies mode changes and the first assertion is not vacuous.

**The umask sweep is what makes this evidence rather than a number that happened to be
right.** `chmod` is not umask-masked while `mkdir(mode=...)` is, so landing exactly `0o700`
under a hostile umask and a permissive one alike discriminates between the two mechanisms.
A single-umask run would have been consistent with either.

**What was not evaluated, stated so nobody relies on it.** The literal test function was
not executed on POSIX. Doing so requires the project's dependency set installed into the
operator's machine, and installing into their environment unasked is not warranted by a
plan row. The mechanism the Step exists to check is covered; the composition through the
test harness's fixtures is not. **A reader treating this as a full execution would be
relying on something explicitly not done.**

## Notes

**A finding raised from this work was overstated and is corrected here, because this row is
where the claim originated.** The hardening is best-effort: the chmod is wrapped in a
handler catching `OSError` and `NotImplementedError`, and its failure is recorded at debug
level. That was first reported as leaving a failed hardening effectively unannounced. It
does not. The resulting condition is detected by the storage-management service, which
compares the observed root mode against an expected value and raises a
root-permissions-drifted issue surfaced through the `config storage check` verb. Two
details make that better than a spot check: the expected value is bound to the
materialiser's own constant rather than restating the octal, so the check cannot keep
passing against a mode the materialiser no longer requests; and the comparison declares
itself unenforced on Windows and reports that fact in its payload rather than passing
vacuously where mode bits carry no meaning.

The accurate residual is narrow: **the failure is detectable on demand, not
self-announcing.** Nothing above debug fires when the chmod is refused and nothing
re-checks at write time, so an operator learns only by running the verb. Whether that
warrants a higher log level is a judgement for whoever owns the surface, and there is a
fair argument on both sides -- a verb built precisely to report the condition may be its
right home.

**Artefacts were left in place** on the POSIX guest, under its temporary directories, per
the standing prohibition on recursive deletion. Nothing was installed, configured, or
removed on any host.
