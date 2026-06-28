---
tags:
  - "#research"
  - "#cli-workflow-redesign"
date: 2026-05-12
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# Research: config-init-shape

Feature tag: `#cli-workflow-redesign`
Date: 2026-05-12

## Question

Define the first-run shape for `aeat config init` and decide whether the
existing `SetupWizard` remains part of the command path.

## Current State

The live CLI has three conflicting setup surfaces:

- `aeat init` is mounted at root as an onboarding alias for `aeat setup init`.
  It accepts `--name`, `--tax-id`, `--activity`, `--iva-regime`, and `--quiet`.
  It writes profile-like values through `workflow_state_repository().update(...)`.
- `aeat setup init` is mounted under `setup`. It creates and activates a
  workflow profile, then directs the user toward `aeat setup auth configure ...`.
- `aeat config init` is not mounted. The current `config` surface contains flat
  `list`, `get`, `set`, `unset`, and `doctor` commands.

Root help currently exposes `version`, `init`, `setup`, `config`, `archive`,
`topic`, `help`, and `app`. This violates the strict root contract for the CLI
workflow redesign, where the root command space is exactly `aeat config` and
`aeat app`.

## Persistence Findings

The live first-run path does not use `SetupWizard`. Root `aeat init` and
`aeat setup init` write workflow profile state through
`workflow_state_repository()`.

`SetupWizard` exists as a typed setup engine with interactive and
non-interactive execution, strict `SetupAnswers`, `SetupResult`, verifier
execution, optional first-run runner, and prompter abstraction. However, its
side effects target legacy setup surfaces:

- `.env` through `write_env_file`
- secure `AutonomoProfile` envelope through `write_profile_file`

Those writes do not update the current workflow profile record consumed by
`aeat init` and `aeat setup init`.

Current workflow state is stored under secure object namespace `aeat.workflow`
and object key `state`. `WorkflowState` tracks profiles, active profile,
declarations, invoice reviews, and ledger reviews, but has no `bucket_id` and
no bucket event collection.

Profile actions can create, select, set, and clear profiles, but they do not
create buckets or emit events.

## Required Target Shape

The canonical first-run command is:

```text
aeat config init [--profile NAME]
                 --tax-id NIF
                 --activity TEXT
                 --iva-regime REGIME
                 [--tax-residence CCAA]
                 [--auth-provider certificate|clave_movil|none]
                 [--certificate-path PATH]
                 [--certificate-password-env VAR]
                 [--output-language LANG]
                 [--drafts-dir PATH]
                 [--submissions-dir PATH]
                 [--manuals-root PATH]
                 [--from PATH]
                 [--non-interactive]
                 [--dry-run]
                 [--format json|text]
```

Interactive mode prompts for omitted fields directly from `aeat config init`.
There is no `wizard` subcommand.

Non-interactive mode requires all required values to be supplied by flags or
`--from PATH`.

The command creates a config bucket and profile atomically, selects the active
profile and bucket, runs readiness validation, and performs internal migration
from old setup-mounted state without exposing old CLI routes.

All output is rendered through `_emit`, including `--format json`.

## Event Requirements

Every persisted mutation is bucket-scoped and emits a bucket event.

Required event names:

- `bucket.created`
- `profile.created`
- `profile.activated`
- `profile.updated`
- `auth.provider.configured`
- `config.env.updated`, only if env-file persistence survives
- `setup.state.migrated`, for backend-only migration from legacy setup state

## SetupWizard Disposition

Do not expose `aeat config init wizard`.

Retire `SetupWizard` as a command backend unless it is refactored to call the
new bucket/profile init service. Its reusable pieces are limited to typed
answers, the prompter abstraction, and verifier checks.

The current `SetupWizard` side effects conflict with the target persistence
model because they write `.env` and the legacy setup profile envelope instead
of bucket-scoped profile state with bucket events.

## Rejected Surfaces

Reject all setup and compatibility surfaces:

- root `aeat init`
- root `aeat setup`
- `setup init`
- `setup status`
- `setup reset`
- `setup auth`
- `setup profile`
- root `aeat archive`
- aliases, compatibility shims, deprecation routes, and support-only routes
- `aeat config init wizard`
- `aeat config setup`

Root `topic` and root `help` also remain outside the strict root contract unless
another ADR explicitly rehomes them.

## Cross-References

This research supports the apex CLI workflow redesign ADR and should be linked
from it as the locked decision for config initialization.

It depends on the bucket ADR for atomic bucket/profile creation and bucket-owned
profile storage.

It depends on the bucket-event ADR for append-only bucket event semantics.

It aligns with the config-profile ADR by keeping profile lifecycle under
`aeat config profile ...` and rejecting any `aeat setup` compatibility alias.
