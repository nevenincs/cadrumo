---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:cba216460f8f6ec4d2fd0a71cf3a797534c31b52eb4957063a0609328230a8f4'
step_id: 'S332'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Decouple the flows area from its application back-reference and convert its entry surface into a mountable screen -- the dearest of the three conversions, and therefore last: the flow entry is an application, its two page surfaces are screens constructed with the application instance itself as a constructor argument, and the module carries dozens of back-references to that instance, so the pages are not host-agnostic. Decouple the back-reference FIRST -- the pages must depend on a narrow protocol or on injected state, not on the concrete application -- because converting first would merely move the coupling. Rehost every driving test in the same change. THREE TRAPS THE EARLIER CONVERSIONS PAID FOR: (1) a screen subclass's `CSS` attribute is IGNORED by Textual, only `DEFAULT_CSS` applies, so a naive rename silently drops the stylesheet -- and note honestly that this trap is currently UNGUARDED: a mutation blanking a converted screen's stylesheet did NOT fail its suite, because the shared host carries base styling that keeps layout plausible, so do not rely on a test to catch it. (2) An async method on the converted class can COLLIDE WITH TEXTUAL'S OWN PRIVATE WIDGET API -- a wholesale-redraw method named `_render` shadowed the widget's visual accessor, harmless on an application which has no such method and fatal on a screen, because every paint then receives a coroutine. The symptom misleads: it surfaces as no-matching-widget errors on widgets plainly present in compose, which sends you hunting a mount-timing bug. Before converting, compare each screen's own attributes against the base screen class and rename every collision, rather than waiting for a paint failure. (3) The extra screen layer widens existing races, so rehosted tests must wait on a real postcondition rather than a longer sleep

## Scope

- `the flows area's entry application`
- `its page screens`
- `the application back-references throughout the module`
- `and every test that drives them`

## Changes

- `M` `src/cadrumo/entrypoints/tui/flows/app.py`
- `M` `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_flow_tui_app.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_frontend_parity.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_visual_verification.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/modelo_work_wizard.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_flow_tui_app.py -m unit -n0` -> `fail`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_visual_verification.py -m integration -n0 -k question` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/flows src/cadrumo/entrypoints/tui/tests/test_flow_tui_app.py src/cadrumo/entrypoints/tui/tests/test_frontend_parity.py --collect-only -q` -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format` / `ty check` on the tui package -> `pass`

## Notes

**Order kept: the back-reference went first.** The two page surfaces took the
concrete application as a constructor argument and reached back into it 57
times across 16 distinct members. Those members are now a narrow protocol the
pages depend on -- engine state to render and the closed intent set to route,
with no Textual concept in it -- and the pages hold the protocol, never a
host. `push_screen` was the one reach that did NOT belong in it: it is a
Textual host concern, so the pages take it from their own `app` handle
instead, which keeps the protocol to what a flow driver must actually
provide. Converting first would have carried all 57 reaches into the new
shape unchanged.

**Then the entry surface became a mountable screen.** `DEFAULT_CSS` with
`SCOPED_CSS = False`, per the trap the secret conversion paid for; the
stylesheet is unscoped because these rules address the page screens the
surface opens, which are siblings on the screen stack rather than descendants
of its own DOM. App-only calls became host calls, `exit()` became a dismissal,
and the standalone runner mounts the screen in the shared host instead of
being an application itself.

**One real regression, found by a test rather than by reading.** The
appearance toggle stopped working. The binding had been declared on the entry
surface, which as an application was always in the key-routing path; as a
screen it sits BENEATH the pages it opens, is never the active screen, and its
bindings never resolve. The binding now lives on the two page surfaces, from a
single shared declaration. Fixing that exposed a second layer: both pages
rebuild their binding map wholesale at mount to localise the descriptions, so
a class-level entry alone was discarded and the toggle stayed dead. The shared
binding is listed in both localised maps, with a comment saying why, because
the failure mode is silent.

**A structural consequence worth naming rather than hiding.** The converted
surface opens its pages as siblings on the screen stack, so it renders nothing
itself and is never the active screen -- it is a controller wearing a screen's
shape. That satisfies the Step (a root shell can navigate to it, and the pages
no longer hold their host) but it is not a surface in the sense the other
converted areas are. Making the pages content owned by the entry surface, so
its own DOM and bindings participate, is a larger redesign than this row
covers and is left as a known shape rather than quietly accepted as finished.

**The widened race was real and was fixed by waiting on a postcondition.** One
rehosted test asserted the engine cursor on the line after a click; the extra
screen layer meant it read the pre-click cursor. The wait pumps the message
queue until the cursor reaches the expected page and then returns the ACTUAL
cursor, so a transition that never happens still fails the caller assertion
with the true value rather than on a timeout message. No sleep was lengthened.

**Two failures in the flow test module are pre-existing, and this was PROVEN
rather than reasoned.** Both locale tests fail identically when the committed
pre-change module is loaded at runtime in place of the working copy, so they
were failing before this Step. That technique was also used to clear the
operation modal lifecycle hang seen in the same lane: it hangs identically
against the pre-change modal, so it is not attributable to the earlier
action-row work either.

**Other failures in adjacent modules belong to work in flight elsewhere.** The
visual-verification module reports failures on the registration, login, status
and profile-manager surfaces, all raising that a screen has no application
test driver -- the conversion of those areas, owned elsewhere. The flow
surface's own fixture in that module was hosted here and its gates pass. A
transactions facade in the working tree also exports a symbol its defining
module does not yet declare, which breaks collection for unrelated suites; it
is a half-landed change owned elsewhere and untouched here.

**Provenance.** This work was committed by another agent's broad commit before
its author reached the commit step; content was verified intact at HEAD across
all nine paths, with the converted symbol absent and the new one present.
History was not rewritten. A peer subsequently refined the postcondition
helper in the working tree; that edit was left in place rather than reverted.

**Production reachability.** Direct. The converted surface is the one the
flow runner mounts and the one the development harness registers, and the
pages under it are the surfaces an operator answers every flow through. The
proofs drive the real screen through the real host at real terminal sizes,
against the real flow engine.
