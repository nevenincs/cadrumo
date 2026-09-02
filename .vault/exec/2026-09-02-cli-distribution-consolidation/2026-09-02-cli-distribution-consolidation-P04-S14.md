---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:935b5b0445f595722c735d8e82d5d5c7cd60afcee1feb33ce16090cbe486a3dc'
step_id: 'S14'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Rewrite the agent connection guide around the installed console script

## Scope

- `docs/how-to/connect-an-agent.md`

## Changes

M docs/how-to/connect-an-agent.md

## Notes

The configuration collapses from three keys, a package selector and an absolute
working directory to a single command name. The guide's checkout preparation section
goes with it: there is nothing to clone, because the server is on the reader's path
once the product is installed. The instruction not to use a normal install "until
public distribution is announced" is removed with the arrangement that made it true.
