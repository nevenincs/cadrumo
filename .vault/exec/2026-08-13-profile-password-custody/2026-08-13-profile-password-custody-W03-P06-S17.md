---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e9ff978e5e27b4e10c81c237cb6c6662dd851f1efc2974c550bed47b0f57ead0'
step_id: 'S17'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh update root bootstrap, TUI login, locales, and status projection to remove old environment and provider channels

## Scope

- `src/cadrumo/entrypoints/`

## Description

- Enumerated every site in the entrypoints layer that reads the environment
  secret channel or reaches the retired provider sub-package, rather than
  assuming where they were.
- Repointed the one production provider reach onto the owning package's
  facade, matching what every sibling in the layer already does.
- Corrected two docstrings that cited the retired provider sub-package as the
  authority for a session the code reads through the facade.
- Established what the row's other three named surfaces actually are, and
  reported the two that do not exist rather than inventing a target.
- Stopped short of removing the environment secret channel, and states below
  why that is a ruling rather than a task.

## Outcome

**Two of the row's four named surfaces do not exist, one is delivered, and the
fourth is a ruling this row should not take alone.**

### The provider channel — delivered

Exactly ONE production module in the whole entrypoints layer reached into the
retired provider sub-package: the command-line profile-readiness check
imported its session predicate from the provider directly while every other
consumer in the layer — the root callback, the profile history verb, the
status frontend — imports the same symbol from the storage package facade.
That is both the row's "old provider channel" in this layer and a plain
ownership violation: the provider is a private sub-package of the storage
package, so a cross-package consumer must resolve to the storage facade. It is
repointed. The symbol is already exported there, so nothing had to be
promoted.

Two further citations were prose rather than imports. The status frontend's
docstrings named the provider's session class as the authority they read,
while the code beneath them reads the facade's accessor. The class is not on
the storage facade at all, so the citation could only ever have resolved
through the retired sub-package. Both now name what the code actually calls,
and one says explicitly that it does not reach the provider the facade owns —
so the next reader is not sent to the module this campaign is removing.

### The TUI login and the status projection — no such surface

There is no `entrypoints/tui/` package. The layer contains the CLI package, a
schema surface module and tests, and nothing else. The full-screen login page,
status page and manager the row means live INSIDE the CLI package as frontend
modules. Their login routing was changed by this row's sibling, which
generalised the routing condition so the new one-shot descriptor channel
suppresses the page exactly as the stdin object does; nothing further in them
reads the environment channel.

The status projection reads the live bucket session through the facade and
already degrades an absent or foreign session to absence rather than a
traceback. Its only defect was the two docstring citations corrected above.

### The environment channel — NOT removed, and this is the finding

`CADRUMO_SECRET_PASSPHRASE` is read at three places in this layer: the root
callback treats a configured value as a completed authentication and logs in
process-scoped without a session; the login verb lets it win over the
interactive prompt; and the login page routing treats it as the factor already
supplied. Removing it from the entrypoints layer is what this row names, and
this row deliberately did not do it, for a reason that is about consequence
rather than effort.

It is the ONLY channel by which a headless or CI host can reach any verb
without first running an interactive login. The replacement the sibling row
built — a one-shot descriptor on `config login` — supplies the factor to the
LOGIN VERB, but every subsequent verb in a different process then depends on
the persisted session surviving between processes, which needs the OS
keychain, which is exactly what a CI host does not have. So removing the
environment channel without first establishing that cross-process story does
not tighten a secret channel; it makes the tool unusable on the hosts that
have no other door, and it would do so silently, one red suite at a time.

The channel's own defence is also on record in the root callback and is not
obviously wrong: the passphrase IS the authentication factor, supplied
non-interactively rather than at a prompt, so it is not a provider fallback or
a shared-master-key route. What is genuinely wrong with it is what an
environment variable is — inherited by every child process, resident for the
whole process lifetime, and readable from a crash dump or a CI log — and that
is an argument for replacing it, not for deleting it before a replacement
reaches the verbs that need it.

The removal is also not containable within this row's scope. The setting is
declared in the core configuration, consumed by the preflight, the operator
scope resolver, the login session authority and the provider's own reader, and
set by a shared test fixture; an entrypoints-only removal would leave the
value live everywhere else while the operator-facing door disappeared, which
is the worst of both states.

**Escalated to the campaign lead with that consequence stated, rather than
executed or quietly dropped.** Recording it here beside what the row asked for
is the point: this row's standing goal is a tree with no environment secret
channel, and what was delivered excludes exactly that.

## Notes

**The row's scope line and the tree disagree, and the tree wins.** Two of four
named surfaces have no target. That is worth recording as a finding rather
than silently narrowing, because a later reader comparing the row text to the
diff would otherwise conclude the work was skipped.

**No bootstrap exemption was added or removed.** The sibling row's new
destructive verb stays login-gated, and the previously-cleared dead entries
were not reintroduced.

No commit was made and no plan checkbox was set. Every capture lives under the
session scratchpad directory, not the repository.
