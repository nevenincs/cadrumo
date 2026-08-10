---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:251ebabe60e52a9e245a4fb0e840b3cd3657a3fd953580e9ab6f0d72c4f597d7'
step_id: 'S33'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Establish how long the lane-reachability gate has been red and whether anything shipped past it

## Scope

- `src/cadrumo/tests/test_lane_reachability.py`
- the commit history of its reported paths

## Description

- Date the first appearance of every module the gate reports, rather than reasoning from the directory's age.
- Date the gate itself, so the red window is bounded by whichever came later.
- Count what landed inside that window.
- Identify the source of the reported modules, because the answer changes what the finding means.

## Outcome

The gate has been red for about five hours, not months, and the answer inverts the concern that opened this row.

Every one of the twelve modules the gate reports first appears **today**. The earliest landed at 07:21:28 and the rest followed through the morning. Before 07:21 the directory held no reachable-or-otherwise test modules for the gate to report, so the gate was green. It went red this morning and has been red since.

So this is not a guard everyone learned to route around over weeks. It is a guard that went red at 07:21 and that nobody noticed for five hours, which is a **monitoring-latency** finding rather than a decay one. That is a materially different defect with a materially different remedy, and stating it as decay would have been the more dramatic and less true reading.

Did anything ship past it: yes. One hundred and fifty-six commits landed after the gate went red, out of one hundred and seventy-eight today. Every one of those landed against a repository where a hard gate with no allowlist was failing. None of them can be said to have been *blocked* by it, because nothing was blocking.

The source is the sharper half. The twelve modules were landed by an active registry campaign, across at least six distinct commits, several of them working-tree preservation sweeps. So the hole is not accruing historic rot at some slow background rate: a live campaign is adding test modules to a directory no lane reaches, today, at roughly twelve in a day. Every one of them reads as coverage to its author and executes nowhere.

## Notes

This strengthens the enrolment row rather than merely dating it. An unreachable directory that stopped growing is a cleanup task, and an unreachable directory a live campaign is actively filling is a leak. The enrolment closes the leak, and the sooner it lands the fewer modules arrive believing they are covered.

It also sharpens the cadence row from a different direction. Five hours is not a long time in absolute terms, but nothing in the tree surfaced the transition from green to red — it was found because a separate investigation went looking. A gate that nine lanes reach and that fails in twenty-eight seconds is not a discoverability problem in principle, so the five hours is about who runs which lane and when, which is exactly what the cadence row exists to decide.

One thing this record deliberately does not claim. It does not assert that the campaign authoring those modules did anything wrong. The directory's unreachability is invisible from inside it: the modules are well-formed, correctly marked, and sit beside an `__init__.py` in a `tests/` package, and nothing at the authoring site says the lane list omits it. Blaming the authors would be blaming them for not reading a path list in a justfile, which is precisely the knowledge the gate exists to supply and the reason it must be green to be useful.

No tests, gates or linters were run for this record. Every figure here comes from commit metadata.
