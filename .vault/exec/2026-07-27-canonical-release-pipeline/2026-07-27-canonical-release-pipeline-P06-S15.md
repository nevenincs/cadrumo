---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S15'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Codify the release runbook with the bump-first release-please step, the docs consequence, the distribution-complete tripwire, and the 0.1.0 first-version expectation, sweeping user docs where they describe the release flow, gate: uv run --no-sync pytest dev/docs/tests -m docs -q and the documented-command conformance test pass

## Scope

- `docs/`
- `dev/docs/tests/`

## Description

- State in the runbook that the bump is the first act of a release cycle.
- Record that the version is computed from commit history rather than chosen.
- Name the two guards that refuse a stale version, and what each costs.
- Add the distribution-complete tripwire to the post-publication stage.

## Outcome

Landed under the commit subject `docs(release): make the bump the first act and
the docs publish a named tripwire`.

A cohort is stamped with whatever version the declarations hold when it is
built, so building before bumping mints a cohort under the previous release
number. That is unrecoverable once anything ships, because a package index
upload is permanent and the number is burned whether or not the upload was
intended.

The runbook now says so at the top of the first stage, names the seal-time and
publication-time guards, and explains what each costs: the first refuses when
the price is one re-run, the second immediately before the first write.

The post-publication stage gains the tripwire. Publication attaches the download
payload and the documentation site reads it at its next publish, so until that
runs the page still describes the previous release. That is deliberate and
bounded rather than a defect, and the runbook now names the act that closes it
and the operator decision that will automate it.

## Notes

The documented-command conformance suite has one pre-existing failure unrelated
to this Step: a modelo audit sequence cites a command the live surface does not
provide. That file is untouched by this campaign, was last changed by an
operator bulk commit, and resolving it needs a domain decision about which audit
verbs should exist. It is reported rather than absorbed, and this Step does not
claim that suite green.
