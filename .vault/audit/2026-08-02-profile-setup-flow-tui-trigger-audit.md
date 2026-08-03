---
tags:
  - '#audit'
  - '#profile-setup-flow'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:f0da5f97f8620bf1400a5390ed171afbd4a818bae65db6a20f67a85810cb66ce'
related:
  - "[[2026-07-23-profile-setup-flow-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-setup-flow` audit: `profile create TUI trigger`

## Scope

Audited the interactive routing contract for profile creation against the
accepted profile setup decision. The review covered the Typer parameter
construction, manager dispatch, capability predicate, and real CLI boundary
tests for both named and argumentless create invocations.

## Findings

### raw-routing-default | medium | An empty repeated-option default suppressed the manager

The dispatcher previously classified every non-`None` parsed value as an
explicit field. Typer supplies an empty list for an omitted repeated option,
so a bare interactive create was routed into the headless wizard even on a
full-screen host. `has_explicit_profile_fields` now treats empty collections
as parser defaults while retaining explicit false, zero, scalar, and
non-empty collection values. Covered by the routing test and direct route
reproduction; fixed in the current working tree.

### argumentless-create | medium | A required name prevented registration-screen dispatch

The create command required `profile_name` at parse time, so an argumentless
create could not reach the registration screen that already accepts an
optional suggested name. Create now makes the argument optional only at the
Typer boundary; the existing `_require_profile_name` refusal remains active
when dispatch falls through to the programmatic path. Covered by the CLI
boundary test; fixed in the current working tree.

### dispatch-context | high | The manager wrapper rejected Typer's vendored context

The manager wrapper needs the executing context to emit its closing envelope
after the TUI returns. The dynamically-built wizard callback now exposes that
injected parameter, but the first guard checked `typer.Context`, while Typer
actually injects its vendored `typer._click.core.Context` base. The guard
therefore still fell back to the wizard after the manager route had selected,
even on a full-screen-capable host. The dispatch now checks the actual
vendored context and casts only at the existing envelope seam, whose runtime
contract is structural. Covered by the runtime callback trace and focused
dispatch tests; fixed in the current working tree.

### windows-console-gate | high | Redirected streams must not be promoted to full-screen TUI

An experiment that treated valid `CONIN$` and `CONOUT$` handles as sufficient
was rolled back. Rebinding Python's standard streams to those devices lets
Textual enter alternate-screen and raw-console mode outside the stream the
operator launched, and an interruption can leave the terminal corrupted. The
canonical capability boundary is therefore strict: full-screen is selected
only when the process stdin and stdout are real TTYs; redirected or captured
hosts refuse safely and name the scripted flag form. The TUI entrypoint no
longer rewires standard streams. This preserves terminal safety while normal
Windows Terminal and PowerShell sessions remain eligible through their real
TTY streams.

## Recommendations

Keep raw parser-default classification at the routing seam, preserve the
distinction between interactive registration and headless validation, and
keep redirected-stream refusal fail-closed. The focused routing and
profile-create integration suites should remain part of the trigger
regression wall.
