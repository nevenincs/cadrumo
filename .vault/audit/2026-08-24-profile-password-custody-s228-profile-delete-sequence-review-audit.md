---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:65f39a49312dc111be70e1437ad04a0f5993d5bf7cb5f59c788caa799234c34b'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-password-custody` audit: `S228 profile delete sequence review`

## Scope

Audit the S228 guide and sequence contract against the real logout and
single-profile deletion boundaries, the hermetic sequence runner, and the
CLI-owned golden-record gate.

## Findings

### s228-profile-delete-sequence-review | high | logout cannot reach the login-gated delete verb

The real page refresh executes `config logout` successfully, then the root CLI
refuses `config profile delete docs-sequence-sandbox --yes` with exit 2 and
`REFUSED_CLI_BOUNDARY`: the operator is no longer logged in. This is consistent
with the explicit negative admission in `LOGIN_GATED_VERB_PATHS`, but conflicts
with the lifecycle test that claims deletion succeeds from a no-session state.
The sequence runner therefore cannot generate the required golden record, and
the requested logout-then-delete journey is not a live product behaviour.

### s228-profile-delete-sequence-review | high | executed sequence has no CLI-owned golden

The corrected contract uses one visible logout frame and one terminal delete
result whose success payload must report `deleted == true`. Because the terminal
verb is refused, the CLI refresh writes no `profile-setup-delete` golden. An
executed documentation sequence cannot be merged or closed without that
generated ownership record.

## Recommendations

- Reconcile whether irreversible profile deletion is intentionally login-gated
  or intentionally reachable after strong-close logout; implement and test one
  boundary consistently before closing S228.
- Once the real subprocess journey succeeds, refresh through the sequence CLI,
  commit its generated golden, rerun page coherence and nitpicky documentation
  gates, and request a fresh formal review.
