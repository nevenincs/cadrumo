---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0b64d1cf7a7ee70104680cec0f9fb761bb863c7bbaf57b03ac956271f53b6980'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `s43 absence gate independent review`

## Scope

Adversarial review of the rebuilt hard-cutover absence gate, dispatched
because the gate's predecessor produced a false closure and the rebuild was
otherwise closing on its author's own evidence plus a dispatcher's reading of
a report. The reviewer was told explicitly not to treat that dispatcher's
endorsement as evidence anywhere it appeared. Verdict is REVISION REQUIRED
with three high findings, and the phase review it was meant to unblock stays
open.

## Findings

The central claim survives adversarial attack. The predecessor derived its
expected package set from its own scan root, so it agreed with itself at any
width. The rebuild anchors the coverage assertion to the layer directory
computed from the test file's own location, which the scan root cannot
influence. The reviewer attempted to construct a narrower root that still
passes and could not: every narrowing reds several assertions including the
scope proof, and both degenerate traversal shapes red as well. The original
defect is not reproduced one level up. Two of the bite probes were
reconstructed from first principles against real material rather than
replayed, and both do what they claim, including the one that exists solely to
prove another probe is not vacuous.

### s43-retiring-window-never-expires | high | The landing window becomes a permanent exemption

Each declaration carries an anchor set that must stay live and a second set
naming provider symbols accepted whether present or absent. The staleness
check compares only the anchor against the live findings. Nothing ever checks
the second set, so the window has no expiry.

Demonstrated by injection: the forbidden provider resolver added to the
forwarding port leaves the gate entirely green, while the same injection into
any sibling reds. The four names are live in the committed port today, so the
window is presently doing its stated job. The moment the in-flight edit
removing them lands, the one module at the centre of the original false
closure becomes the one module where the exact symbol the phase review names
is accepted permanently, with nothing left to expire. The module's own
documentation calls this a landing window rather than a second exemption
channel; after the landing it is exactly a second exemption channel.

### s43-scope-proof-inverts-on-success | high | The gate cannot be green in the state it exists to produce

The scope evidence asserts that at least one declared violation lies outside
the package the predecessor scanned. Emptying the declaration set, which
simulates the cutover being finished, reds that assertion with its own
message.

So the proof is anchored to the population of live violations rather than to
anything durable, and completing the work destroys the evidence that the gate
looks widely enough. The standing pressure is to keep one violation declared
artificially so the proof survives. This is also why the phase review asked
for a tracked fixture anchor specifically rather than a probe: a fixture
module in a sibling package survives success, a census of real violations does
not.

### s43-module-net-misses-idiomatic-forms | high | The most natural way to write the reach is invisible

Importing the retired package by name from its parent is not detected. The
plain import statement runs its alias through the module matcher; the
from-import checks alias names only against the retired symbol list. A plain
asymmetry, and it hides the most idiomatic spelling of the very reach the net
exists to catch.

Also undetected: an aliased parent followed by attribute access, a dynamic
import whose target is passed by keyword rather than positionally, a relative
dynamic target with a separate package argument, targets built by formatting
or concatenation, the builtin import function, and the specification finder.
There are no production occurrences today, so these are latent rather than
live, but the module documentation claims no route into the retired package
remains, and that claim is false for these forms. Overstating a partial
matcher is the shape of the defect the rebuild was commissioned to repair.

Two lesser findings: the scope proof enumerates only direct children of the
layer, so restricting traversal to that depth takes sixteen modules dark while
everything stays green; and the root-exclusion prose names only the outbound
tax-authority adapters while a command-line readiness module and an outbound
identity-provider module also reach and are unnamed, the entrypoint layer
being precisely the other place a caller chooses a custody lifecycle.

The declared reach for the portable-export key derivation was examined and
found sound: it is the raw derivation primitive rather than a provider seam,
the reason is accurate, it names a destination, and it is declared rather than
excused.

## Recommendations

Red the gate when no name in a declaration's landing window is still live, so
the window expires with the work it describes.

Re-anchor the scope evidence to a tracked fixture module in a sibling package,
so the proof survives the completed cutover rather than being destroyed by it.

Route from-import alias names through the module matcher, read keyword
arguments when scanning dynamic import targets, and widen the recognised
dynamic import callables. Where residue remains, document it as known
uncovered rather than leaving the strong claim standing over a partial
matcher.

Do not read this gate's green as evidence the phase review's first finding is
closed. The gate's own declarations record that composition as live in three
application modules. Its green is a record that the finding is still open, and
reading it as closure would repeat the original error in a new register. Of
the three conditions the phase review set for re-closure, one is substantially
delivered with defects and two are untouched: the composition has not been
removed, and the forwarding port has gone from one thousand two hundred and
forty lines to one thousand two hundred and twenty-four.
