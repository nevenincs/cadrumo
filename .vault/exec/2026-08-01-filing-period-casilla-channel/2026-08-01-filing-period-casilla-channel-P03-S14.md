---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:268cce650f39ea51d88ec9b602bc4315ba0445393dcba1fd2d8e1518d3fabe73'
step_id: 'S14'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Prove the strict docs build and documented-command conformance gates green and report the publish unblocked

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

- Run the strict docs build gate and the documented-command conformance gate, reading each run rather than its exit status.
- Re-execute every recorded cli-sequence and attribute each remaining divergence to a page and an owner.
- Run the wider documentation suite and attribute every failure against the committed tree before claiming any of them are not ours.
- Fix the one full-scope build failure that traced back to this campaign, and re-measure.

## Outcome

Both gates named by this Step are green. The strict docs build passes at seventeen tests, and documented-command conformance at three hundred and fifty-four. The defect that previously aborted the strict build is gone.

The sequence gate passes for every page this campaign refreshed. Six divergences remain, on two pages this campaign never touched, all confined to a deadline-recovery legal reference from a concurrent change.

One failure first reported as not ours turned out to be ours, and the correction came from the coordinator rather than from this Step's own analysis. The check performed here asked whether any symbol referenced by this campaign's two commits appeared in the unresolved set, and none did, which was true but the wrong question. The alias reddening the full-scope build was introduced by this campaign's first phase as part of an adopted rider set, so it was this campaign's symbol without being referenced in its later commits. The narrower question produced a confident wrong answer.

The alias is a PEP 695 type alias, which Sphinx cannot document as a class, so it was enrolled in the curated nitpick baseline alongside the twenty-odd registry aliases of the same kind. It is named individually rather than folded into a pattern, so it cannot mask a future real class. The registry-alias entry that already exists is anchored to qualified paths and could never have matched, because the reference reaches the gate in its bare short-rendered form.

Measured after the fix: the alias no longer appears anywhere in the unresolved set.

## Notes

The publish is NOT unblocked, and this Step's action text should not be read as satisfied on that point. The two gates it names are green, and the defect this campaign owned is fixed and verified, but the full-scope nitpicky build remains red on two symbols belonging to others.

One is a type parameter in the retention surface with no active owner, last touched by a package-root rename. The other is a probe-result enum in an authentication campaign that is mid-landing, its declaring module still untracked. Because that second one is live work, the gate cannot go green until it lands, so fixing the ownerless one would not have delivered a green gate and was left alone rather than absorbed.

The wider documentation suite carries further failures in page translation catalogues and in missing stubs for four modules other campaigns have not yet scaffolded. None were absorbed: the stub generator is tree-wide and would have swept those four modules into this campaign's commit.

Timing was measured, not assumed: the full-scope build takes roughly twelve minutes per run, so each attribution costs a full cycle.
