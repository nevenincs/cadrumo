---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S15'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Sever the environment source for cadrumo_active_profile so the field is populated only by --profile and override_settings, retarget the logout override refusal to the per-invocation --profile case, and sweep every string or doc naming CADRUMO_ACTIVE_PROFILE as an operating mechanism, verified by a settings test proving the env var no longer selects a profile and the existing override-refusal tests retargeted green

## Scope

- `src/cadrumo/core/config.py`
- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/application/user_profile/_orchestration.py`

## Description

- Sever both environment sources for the active-profile field by replacing them with filtering subclasses, so neither the process environment nor the dotenv file can populate it, while leaving the init source untouched as the channel the profile flag and the test override helper write through.
- Exclude severed names from the model's environment-variable inventory, so the generated environment reference and the shipped environment template both stop advertising a control that does nothing.
- Key the reference generator and its drift gate on that inventory rather than on the raw field list, which otherwise demanded the dead knob back.
- Retarget the five profile-health next-step strings that told operators to unset the variable; the override can now only arrive from the per-invocation flag.
- Remove the metadata-isolation scope's pin of the variable, which became dead code, after confirming the help and version invocations behave identically without it.
- Correct the precedence prose in the pointer resolver, the bucket-scan resolver, the CLI root callback, and the label-resolution test module, each of which described a rung that no longer exists.
- Add the absolute session-cap entry to the shipped environment template, which the earlier settings step had left undocumented and which was reddening the alignment gate.
- Author a dedicated verification module rather than folding a line into an existing sweep.

## Outcome

- Landed as commit `e75322d8cc` across thirteen files.
- The verification module proves both halves: the process environment, the dotenv file, and the documented inventory each fail to select a profile, while the two surviving channels each still do. It carries an anti-tautology case asserting a neighbouring field still reads its own environment variable, without which a filter that dropped every variable would pass every other assertion.
- Gates green: the new module and both environment-alignment gates pass, and 504 cases across the core, config, workflow, and affected CLI modules pass with no failures.
- Tests were reconciled rather than deleted. The label-resolution module already drove the in-process channel and only its prose was stale, so its coverage stands. The custody precedence case was inverted to prove the variable is now inert: it is still exported through every invocation and the pointer still wins.

## Notes

- Blast radius was assessed before landing, as the change alters profile resolution for every process in this shared worktree. The variable is set nowhere -- not in any live shell, not in the operator dotenv -- so no concurrently running agent loses a selection mid-task.
- One consumer looked like it would be stranded and was not. The metadata-isolation scope pinned the variable to keep help and version invocations off an operator's real state root. Both invocations were confirmed to behave identically without the pin, because the scope already redirects to a temporary root where no profile exists, so resolution yields nothing naturally. The pin was removed as dead code rather than replaced.
- Two files carrying this step's docstring corrections were deliberately excluded from the commit: a peer campaign's in-flight verb-rename edits had landed in the same files between the working-tree check and the edit, so they are left for that campaign's commit rather than swept into this one. The excluded content is prose only and no part of the severance depends on it.
- One operator-facing string remains stale and is handed off: the logout override refusal still names the environment variable alongside the profile flag. Its catalogue belongs to a concurrent campaign under the locale-CLI authority rule, which forbids hand-editing the files, so it must be corrected through the locale CLI by that owner. The refusal's CODE semantics are already correct -- it guards on the field, which only the flag can now set.
