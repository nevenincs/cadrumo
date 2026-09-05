---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:61ef88b08885bbae57b97e3f3b60fff5ba09bdeeafb0573fbe7ef4b3deaf5b22'
step_id: 'S444'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Review the full-screen session's output-language override into the sanctioned inventory. The gate offers two verdicts, ctx-scoped or reviewed with a reason, and this site is neither shape it names: there is no Typer context to hang the override on, and the ExitStack it uses is the shape the gate warns can outlive a callback. Establish from the code whether anything renders after that stack unwinds, and record the answer as the reason rather than assuming either verdict.

## Scope

- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

The gate module is fully green: 8 passed. This was its last failure.

The gate offers two verdicts -- ctx-scoped, or reviewed into the inventory with
a reason -- and `run_requested_destination` is neither shape it describes. There
is no Typer context to hang the override on, because this is a full-screen
session subprocess entrypoint rather than a command callback, so the
ctx.with_resource requirement cannot apply to it. And it enters the override on
an ExitStack, which is precisely the shape the gate's own comment warns about:
"an ExitStack outliving the callback would silently become post-unwind
exposed".

So the question the gate asks is real here, and it has a determinate answer:
does anything RENDER after that stack unwinds? The stack closes at the end of
the function body, and the only work after it is
`request.outcome_file.write_text(render_outcome(outcome))`. `render_outcome` is
`json.dumps` over three fields. Its `detail` does carry localized prose, but
that prose was produced by the session callable, which runs INSIDE the stack.
Nothing translates after the override is gone.

That is the reason recorded beside the entry, and it is deliberately not either
of the two labels already in the file. Calling it ctx-scoped would be false --
there is no ctx. Filing it beside the wizard entry, which is annotated as the
surface the wrong-language bound was PROVEN against, would mark a safe site as a
known hazard. It is a third case: scope-closed before return, with nothing
rendering afterwards.

Teeth on the tripwire rather than on the entry, because the entry is data and
the tripwire is the behaviour: a new `override_settings(cadrumo_output_language=...)`
site added to entrypoints/tui/navigation.py failed the gate by name. Restored by
copy; 8 passed.

## Notes

The claim this entry rests on is about what runs after the ExitStack unwinds,
so it stops being true the moment a translated line is added after that block.
No gate asserts that -- this one checks the inventory, not the ordering -- and
the reason is written at the entry so the next reader sees what has to stay
true rather than only that the site was permitted.
