---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:0e182354d7bcc4a20fa650b0ccd35d55dc797b198f3455a2f57d885da2f76f4f'
step_id: 'S01'
related:
  - '[[2026-06-04-docs-sphinx-ux-plan]]'
---

# `docs-sphinx-ux` `W01.P01.S01`

Scope: `W01.P01.S01`.

## Description

Add the approved Sphinx UX extensions to the development dependency group.
Refresh the lockfile with the resolved extension packages.
Confirm the lockfile remains current after dependency resolution.

## Outcome

The dependency layer now includes copy buttons, design components, OpenGraph metadata, sitemap support, and not-found page support.
`uv lock --check` passed.

## Notes

The OpenGraph extension imports successfully but prints that Matplotlib is absent, so generated social preview cards remain out of scope for this wave.
