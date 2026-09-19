---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:1e9143ae95c7acc23f72a4210f1c915853f921545821709b98d263a8189986c0'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `account factories review`

## Scope

Reviewed the S380 production account-factory composition and focused contracts for authority boundaries, deferred host effects, existing-screen reuse, locale ownership, and secret custody.

## Findings

### forwarding-and-deferred-effects | medium | Initial tests left optional door forwarding and most deferred effects unproven

The initial focused tests could not detect removal of optional Profile and Login door forwarding, or an eager persistence, authentication, password-assessment, or rotation call. The focused contract now supplies refusing doors, proves no eager invocation, and verifies each optional door reaches its existing screen owner before Step closure.

## Recommendations

- Retain the focused forwarding and deferred-effect assertions when account composition changes.
