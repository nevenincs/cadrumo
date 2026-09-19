---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:701467a9eac8b2f12e07f2166d807c767e1b50783d7e2f392e75baa58193c9c0'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S41 locale leaves independent review`

## Scope

Independent review of `W05.P10.S41` only: the three configuration-check labels introduced in each supported output catalogue. The review verifies authored values rather than renderer humanisation and does not close the parent step.

## Findings

### native-locale-leaves | low | all twelve required locale leaves are authored

`cli.config.check.dependency_label`, `cli.config.check.capability_label`, and `cli.config.check.preflight_label` resolve through the non-humanising `lookup_translation` path for `en`, `es`, `ca`, and `hu`. Every lookup returned a nonempty scalar distinct from its key: Dependency, Capability, Preflight check; Dependencia, Capacidad, ComprobaciÃ³n previa; DependÃ¨ncia, Capacitat, ComprovaciÃ³ prÃ¨via; FÃ¼ggÅ‘sÃ©g, KÃ©pessÃ©g, ElÅ‘zetes ellenÅ‘rzÃ©s. The exact S41 leaf scope therefore has no runtime fallback, key echo, feature name, package prose, or English-only substitution.

## Recommendations

Retain `lookup_translation`-level assertions for each supported locale whenever a locale leaf is introduced. Keep `W05.P10.S41` open until the coordinating owner applies its own closure procedure; this audit records only the independently passed locale-leaf invariant.
