---
tags:
  - '#adr'
  - '#recovery-mnemonic-surface'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1412465359b0ba9e3ba5e80849a6ae97adb89d61c125ca712079496c9de97c29'
related:
  - '[[2026-08-08-recovery-mnemonic-surface-reference]]'
  - '[[2026-07-25-auth-cert-recovery-custody-adr]]'
---

# `recovery-mnemonic-surface` adr: `The TUI may collect a mnemonic but must never display one` | (**status:** `accepted`)

## Problem Statement

Recovery-code create, rotate and verify, and the forgotten-passphrase recovery
path, exist in the application layer with working CLI verbs and no TUI surface
at all. A TUI-only operator who loses their recovery code, or who never enrolled
one, has no affordance: the capability is not refused, it is absent, which reads
as an omission rather than a boundary.

The governing custody record requires that the candidate words are displayed
once on the terminal device and fully retyped with echo suppressed before
anything commits. No decision rules on whether a rendered full-screen modal
satisfies "the terminal device", nor on what primitive could hold a show-once
value that must never round-trip back into a collected field. Building the
surface without answering those is how a show-once secret becomes a paintable
one.

## Considerations

- The show-once contract is enforced structurally today, not by convention. The
  candidate words are written to the **controlling terminal device**, explicitly
  not to stdout, the JSON envelope or a log; the write carries a real-console
  precondition and a stdin-identity precondition, and an echo-suppression
  failure is promoted to a typed refusal rather than degraded to a visible read.
  The words are shown exactly once and are unrecoverable afterwards.
- The mnemonic never leaves memory. It is passed once into the confirmation
  callback, is never returned on any result record, and is never serialized;
  the persisted envelope and even the failure-path error envelope are gated by
  tests asserting the words are absent.
- The TUI form model has **no display-only primitive**. Every unit of a form
  page is a collected, editable field, and the field kinds are text and choice
  only. The only display-only surfaces are raw framework labels composed inside
  specific screens, none of them parameterised as secret-bearing.
- Echo suppression exists in the TUI, but only for *collected* fields: a form
  field carries a secret flag that renders its input in password mode. Nothing
  in the TUI paints a secret, and the masked-field render gate asserts exactly
  that over every enrolled surface.
- That render gate HAD a stated blind spot — it could not see a secret collected
  inside a modal the base screen pushes only on a button press — and the blind
  spot is now closed. A companion gate expresses the property over every shipped
  manager action and every field its own form page declares secret, drives the
  dialog open, and asserts both that the edit input masks and that the committed
  summary-table cell masks, read off the table cell rather than sniffed out of a
  screenshot. Closing it caught two live leaks: the edit dialog was rebuilding
  the field and dropping the secret flag, and the summary table wrote raw values
  regardless. A secret collected in a modal is therefore covered.
- A full-screen framework application does not "display once". It composes a
  widget tree, holds the value in a renderable for the screen's lifetime,
  repaints it on every refresh, and can export the composited screen to an
  image. These are not incidental implementation details; they are the
  framework's contract.
- The recovery status panel in the TUI already renders the enrolled state, the
  non-secret fingerprint, and the literal CLI command strings for create, rotate
  and verify. Part of the boundary statement therefore already exists.

## Considered options

- **Build full recovery in the TUI, rendering the candidate words in a modal.**
  Rejected. A rendered modal cannot satisfy the show-once contract with any
  existing primitive: the value lives in the widget tree, survives repaints, and
  is reachable by screen export. At the time of the decision this was compounded
  by the only leak gate being blind to modals, so the failure would have shipped
  looking covered; that blind spot has since closed, and the rejection rests on
  the compositor argument alone, which is unaffected.
- **Specify a new show-once TUI primitive and build recovery on it.** Rejected
  on cost-versus-benefit, not on impossibility. Such a primitive would have to
  own the terminal device directly beneath the framework's compositor, bypass
  the widget tree entirely, and be proven against screen export, scrollback and
  repaint. That is a rendering-layer research project whose only consumer is one
  verb that already works correctly on the CLI.
- **Build nothing and say nothing.** Rejected. This is the status quo, and it is
  the actual defect: the operator cannot distinguish "not offered here" from
  "not supported".
- **Split by direction: the TUI may COLLECT a mnemonic, never DISPLAY one.**
  Chosen.

## Constraints

- The custody record's echo-suppression guarantee is enforced in the CLI secret
  helper, which carries a real-console precondition. A TUI field's password mode
  is a framework-level render choice with no equivalent precondition, so the two
  are not the same guarantee even though both hide the characters. A TUI
  collecting surface inherits masked rendering, proven by gate; it does not
  inherit the console precondition.

## Implementation

**The dividing line is direction of flow.** A secret the operator types may be
collected by the TUI; a secret the application generates must never be painted
by it.

Create and rotate are therefore **CLI-only, permanently**, because both must
display 24 generated words. Verify, and the forgotten-passphrase recovery path,
are TUI-expressible in principle, because both only ever *collect* a mnemonic
the operator already holds, and the existing secret form field is the primitive
for that. Status is already present and stays.

**The boundary is stated, not omitted.** Wherever the TUI presents recovery, the
create and rotate operations name the exact CLI verbs and say plainly that they
must be run on a terminal because the words are shown once and cannot be shown
again. An operator must never have to infer a capability boundary from a missing
menu row.

**The prohibition is enforced by a gate, not by convention.** A structural test
asserts that no TUI module composes a secret-bearing generated value into a
renderable: the recovery enrollment and rotation entry points are not reachable
from the TUI package, and no TUI module imports them. The gate is scoped to the
direction that matters — generation and display — so it does not fire on the
collecting path this record permits.

## Rationale

The knockout is that the show-once contract is a property of the *device*, and a
full-screen framework application is a compositor sitting between the
application and the device. Once a value enters the widget tree it is repainted,
retained and exportable; "shown once" becomes an assertion about operator
behaviour rather than about the system. The CLI path does not have this problem
because it writes past stdout to the controlling terminal and never retains the
value.

The second knockout was evidential, and it has since been retired by other
work: when this decision was taken, the only gate that would catch a painted
secret in the TUI was blind to modals — precisely where a recovery modal would
live — so building the surface would have created a leak path in the one region
the leak detector could not see, looking covered because the gate was green.
That blind spot is now closed. The decision does not move: the
compositor-retention argument above stands alone and is sufficient, and it is
the reason a rendered modal cannot satisfy a device-level show-once contract
however well instrumented it is. What changed is only that the collecting half
of this ruling is now backed by a gate rather than by a promise.

Choosing "CLI-only for display" over "no TUI recovery at all" matters because
the two failures are different. Being unable to *see* a new recovery code in the
TUI is a boundary the operator can act on with one named command. Being unable
to *verify* the code they already hold, or to recover a forgotten passphrase,
would be a genuine dead end — and neither of those requires displaying anything.

## Consequences

- A TUI-only operator can still verify a held recovery code and recover from a
  forgotten passphrase; only minting a new code sends them to a terminal, with
  the exact verb named.
- The show-once contract stays enforced where it is enforceable, and is not
  weakened by a second, softer implementation of the same guarantee.
- **Open gap: the TUI affordance text is not written.** The screens that would
  carry the boundary statement and the collecting verbs are under concurrent
  edit by another campaign at the time of this record, so this change does not
  touch them. What lands here is the ruling and its enforcement gate; the
  operator-facing prose and the verify/recover screens are a separate change on
  a quiet tree.
- The precondition on the collecting half is **met**. A mnemonic-collecting
  modal is now covered by a gate that drives navigation into pushed screens and
  checks the committed table cell as well as the edit input, so the verify and
  recover screens this record permits may be built without first extending it.
- Reversing the display prohibition requires a genuine show-once primitive that
  bypasses the compositor and is proven against screen export and repaint. This
  record does not forbid building one; it declines to build recovery on the
  primitives that exist.
