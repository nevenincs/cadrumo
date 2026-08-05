---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:ab8832a643657020d3db333060c2db4848166dbe8f38432598d58d3abf6961b5'
step_id: 'S34'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Retire the calculate-time maternidad flag so casilla 0611 has one authority, because the flag carries a free-form hijo id that no descendant record answers to and is today reconciled only by a mutual refusal, which contains the two-authority hazard without removing it, and the refusal is what currently blocks 0611 from becoming registry-computed like its 0613 sibling

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/cadrumo/locales/`

## Description

- Remove the calculate-time flag's Typer option, its type alias, and its `HIJO_ID=MESES` parser, including the parser's three refusal keys.
- Remove the parameter threaded through the input-bundle builder and the shortcut-application function, collapsing the two-authorities refusal entirely rather than leaving it as a vestige.
- Update the two direct callers that passed the parameter as a constant `None` so they no longer reference it at all.
- Retire the CLI-level tests that exercised the flag; add a retirement proof (the CLI itself now refuses the option) and a control test proving the profile-declared figure reaches the casilla unaided.
- Remove the two-authorities refusal's locale key and the parser's three refusal keys from all four locale catalogues through the locales CLI.
- Sweep both the literal flag name and every interpolated form (the parser's own function name, the Typer type alias name) rather than the literal alone.

## Outcome

Casilla 0611 now has exactly one authority: the active profile's declared descendant records. The calculate-time flag was retired outright rather than turned into an alias of the profile path, because aliasing it would have meant fabricating a descendant record — a birth date, a cohabitation answer, a rentas figure — for a bare `(hijo_id, meses)` pair that carries none of those facts to check eligibility against. The flag's own help text already scoped it to profiles declaring no descendants at all, which is a way around eligibility checking rather than a distinct legitimate use no descendant record could express, so there was no operator workflow to preserve.

Collapsing the two-authorities refusal was the correct shape rather than a narrower fix that kept it as a dead branch: with one channel remaining there is nothing left to reconcile, and a refusal guarding a conflict that can no longer occur reads as a live guard while defending nothing. Searching the interpolated forms rather than the literal flag string alone caught a real second site — the parser function's own name — that a literal-only sweep would have missed entirely.

## Notes

A concurrent write reintroduced two already-removed locale keys into the main commit. The `git diff --cached` check immediately before committing was clean, isolating the change against a HEAD-anchored scratch copy rather than filtering hunks out of the shared index. Between that check and the commit executing, the working tree for one locale file was touched again by an unrelated process, and a pathspec commit re-reads the working tree for its paths at write time rather than trusting what was staged — so the two retired keys, relocated and reformatted, rode back into the commit. This is the reason the standing instruction is to verify after committing rather than before: the pre-commit check cannot see a peer land in the same instant a commit executes. Caught by re-running the retired key names against the committed HEAD afterward, not by re-trusting the earlier staged-diff check. Fixed in one immediate follow-up commit touching only that file, then re-verified against HEAD for all four catalogues and against a fresh whole-tree search for every retired name.

Deliberately left untouched, and named as a decision rather than an omission: a tracked evaluation snapshot belonging to an unrelated documentation-search campaign that still names the retired option, because its own test suite injects the CLI surface it checks against rather than deriving it live, so it does not gate on this change and regenerates from its own pipeline; and an untracked build artefact that lists the retired option in a cached CLI-tree projection, which rebuilds on the next documentation build.
