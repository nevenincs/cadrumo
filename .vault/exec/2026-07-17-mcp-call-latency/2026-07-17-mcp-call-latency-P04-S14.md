---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Hold the warm runtime's decrypted bucket-session state under the existing idle-lock custody rules and restart a crashed runtime cleanly with no torn persisted state and ## Scope

- `src/cadrumo/entrypoints/mcp/_server.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Hold the warm runtime's decrypted bucket-session state under the existing idle-lock custody rules and restart a crashed runtime cleanly with no torn persisted state

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`

## Description

- Relock after every in-process call: wrap the in-process worker's dispatch in a `finally` that evicts and zeroises any bucket session still bound in the worker context, so the warm runtime never retains decrypted key material between calls.
- Document the custody model on `_run_inprocess_tool`: the CLI opens and closes its own session within the call; the worker runs in its own thread context (a raw thread does not inherit the server's ContextVar state), so a bound session cannot leak into the long-lived server context; the finally relock is defence in depth covering an unexpected in-call fault and a timed-out worker that finishes in the background after its ceiling was reported.
- Document crash-restart cleanliness: a crashed server holds no decrypted state on disk, single-writer persistence is unchanged, the atexit hook zeroises any still-bound session on interpreter exit, and caches re-warm on restart.

## Outcome

The warm runtime honours idle-lock custody by construction - it holds no decrypted bucket-session key material past a single call - reinforced by an idempotent relock in the worker `finally`. The existing in-process and loop-responsiveness suites stay green (the relock is a no-op when no session is bound). The relock primitive is the storage facade's `close_active_bucket_session` (zeroises keys, evicts the active-session ContextVar, idempotent).

## Notes

The custody choice is to NOT hold keys warm: research shows crypto is not a bottleneck (Argon2id ~25 ms), so re-deriving per call is cheap and strictly safer than a long-lived held key. This is a stronger guarantee than the idle-lock rule requires. The idle-lock relock plus clean-crash-restart regression - which provisions a real encrypted bucket and asserts no session survives an in-process call - lands in S17 per the plan's division.
