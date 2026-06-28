---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S14
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P02.S14`

Every caller of `active_profile_bucket_id` / `active_profile_record`
now flows through the precedence chain by construction. No caller
signature changes; the resolver internalises `load_settings()` so
the cascade stays single-file.

- Verified: 24 caller files inventoried; zero signature changes
  required because the resolver hides settings access from the
  caller surface.

## Description

The audit surfaced 24 files calling these methods across CLI,
application services, and tests. The original plan expected a
24-file signature cascade. The cleaner alternative landed in S13:
delegate the method bodies to the resolver, keep their signatures
unchanged, and let the resolver call `load_settings()` internally.
Every caller now reads through the precedence chain without code
movement at the caller site.

## Tests

Covered by the 49-test pass in S13. The pre-existing test
`test_models.py::test_details_dict_str_str_accepted` failure is
unrelated (a `WorkflowStep.details` typed-model coverage gap on
a different surface).
