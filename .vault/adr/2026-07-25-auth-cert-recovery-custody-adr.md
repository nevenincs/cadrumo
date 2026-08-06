---
tags:
  - '#adr'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:edebf18a76f2aed576288e3d1481e07ac7c6735364e55186bccd5caefa8a018a'
related:
  - "[[2026-07-25-auth-cert-recovery-custody-p04-door-safety-review-audit]]"
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
  - "[[2026-07-17-auth-cert-recovery-custody-adr]]"
---

# `auth-cert-recovery-custody` adr: `custody door secret channels and throttle posture` | (**status:** `accepted`)

## Problem Statement

The independent P04 door safety review left two of its six findings unresolvable by an implementer, because each asks which posture the door should hold rather than how to repair a defect.

The first is a contract contradiction. The custody command module states that secrets reach its verbs through exactly two channels and concludes that passphrases never appear in the process table, shell history, or logs. A `CADRUMO_SECRET_PASSPHRASE` environment variable is nevertheless consulted ahead of both, and refusal copy actively advertises it. The value itself is well handled and does not leak, so this is a contractual gap rather than a live exposure; but a reader hardening an adjacent surface will trust the absolute sentence, and an environment variable is readable by same-user processes and lands in shell history when set inline. The finding is entangled with the review's HIGH finding, since both turn on which callback the enrollment path resolves, so settling one without the other would leave the pair incoherent.

The second is an undeclared asymmetry. The failed-attempt backoff has exactly one production consumer, profile login. Passphrase change, recovery verify, and flat recover call none of it and all three are bootstrap-exempt, making passphrase change an unlimited passphrase-check oracle and recovery verify an unlimited mnemonic oracle. The review's own assessment is that this is very likely not exploitable, and the danger is precisely that: an unrecorded absence is indistinguishable from an oversight, and a future change that makes these verbs remotely or cross-user reachable would turn it into a real exposure with nothing flagging the regression.

Both are recorded here because the campaign cannot close honestly with either left as an implementer's judgement call.

## Considerations

The grounding is the P04 door safety review audit; its findings, reproduction probes, and clean-axis verdicts are cited rather than restated. Three forces bear on the choice.

Recovery enrollment is interactive by construction. The candidate words are displayed once on the terminal device and must be fully retyped with echo suppressed before anything commits, so no automated driver can enroll a recovery code however the passphrase is sourced. An environment channel therefore buys enrollment nothing it can use.

Two of the five custody verbs already bypass the environment channel. Passphrase change and flat recover bind an explicit fixed-value callback carrying the operator's own input, so the module already contains the shape that resolves the contradiction; the enrollment verbs were the outlier, not the rule.

The offline-equivalence argument for the throttle is a fact about the threat model, not a convenience. Any caller able to run these verbs already holds same-user read access to the wrapped key artefacts and can mount the identical Argon2id attack offline at the same cost, and the recovery mnemonic carries 256 bits of entropy. Its validity is contingent on same-user local reachability, which is what makes reachability the correct tripwire rather than a periodic re-review.

## Considered options

- **Amend the docstring to name the environment channel and its precedence.** Rejected: it makes the sentence accurate at the cost of widening the door's declared contract to three channels, one of which the interactive verbs cannot use and which no custody verb needs. Accuracy achieved by lowering the guarantee.
- **Have the enrollment callback consult the environment variable first and fall back to a hardened prompt.** Rejected: it keeps behaviour uniform across the substrate, but it preserves a channel enrollment can never exercise and diverges from the two custody verbs that already bind a fixed operator-supplied value. It would also leave the door's own contract stating three channels for no operator benefit.
- **Bind every custody verb to an explicit callback so the environment channel is unreachable from the door, and keep the environment channel for the substrate's non-interactive unlock path.** Chosen: it makes the existing two-channel claim true as written rather than merely softer, and it generalises the shape two of the five verbs already used.
- **Extend the failed-attempt backoff to the custody verbs.** Rejected: it defends against an attack the same-user offline path already permits at identical cost, so it adds a throttle-state surface and a lockout failure mode to a recovery path whose entire purpose is restoring access, in exchange for no reduction in attacker capability.
- **Leave the throttle absence unrecorded.** Rejected outright: this is the condition the finding exists to end.

## Constraints

No new technical dependency. The threading relies on the master-key provider factory already accepting a passphrase callback, which it does, so no substrate signature changes. The throttle decision is contingent on the custody verbs remaining same-user locally reachable; that contingency is the declared tripwire below rather than an open risk.

The keyring custody path could not be exercised at runtime during the review or this work: agent sessions run over an SSH network logon where Windows keychain calls fail with `WinError 1312`. That is an environment artefact, not a defect, and neither decision here touches that backend, which refuses before any passphrase resolves. The console-only remainder is stated rather than implied away.

## Implementation

**Decision one — the custody door's channels.** Every custody operation resolves the secret-store passphrase through an explicit callback rather than inheriting the substrate default. The interactive door supplies a guarded terminal prompt built on the hardened no-echo helper, which carries a real-console precondition, a stdin-identity precondition, and promotion of an echo-suppression failure to a typed refusal. Passphrase change and flat recover continue to bind the operator's own prompted or stdin-supplied value. Recovery verify never reaches passphrase resolution at all, because it unwraps the envelope under a mnemonic-derived key rather than the master key; it is bound to the non-interactive resolver regardless, so the claim holds structurally rather than by coincidence of the current call graph.

Where the application layer is called programmatically with no callback, the default is a non-interactive resolver bound to the settings the operation already resolved. It reads the configured passphrase and refuses with a typed error when none is set, and it is deliberately incapable of prompting, so a programmatic driver cannot silently acquire an interactive prompt it has no way to answer.

`CADRUMO_SECRET_PASSPHRASE` is retained, unchanged, as the declared channel for the substrate's own non-interactive unlock resolver, which automated drivers depend on. It is simply not reachable from the custody verbs. The command module's docstring is scoped explicitly to the verbs it registers, names the environment channel as a legitimate substrate channel elsewhere, and states that no verb registered there consults it.

**Decision two — no failed-attempt throttle on the custody verbs.** The absence is affirmed as deliberate and recorded in the custody module's own docstring in its own terms: the same-user offline-equivalence argument, the mnemonic entropy figure and its source, and the tripwire stated plainly — if these operations ever become remotely or cross-user reachable, the offline-equivalence argument collapses and the backoff must be extended to cover them. No throttle code is written.

## Rationale

The knockout for decision one is that the chosen option is the only one under which the door's existing claim becomes true rather than weakened. Both alternatives resolve the contradiction by lowering the guarantee to match the code; this one raises the code to match the guarantee, and it does so by generalising a shape already present in the module rather than inventing one. It also composes with the review's HIGH finding instead of merely coexisting with it: threading an explicit callback is the same edit that removes the unguarded terminal read the review reproduced as both an indefinite block and an echoing fallback, so one change settles the repair and the contract together, which is what the review asked for.

The knockout for decision two is that a throttle would reduce no attacker capability. The oracle it would close is already open, at identical cost, to anyone who can reach the verbs at all. Spending a lockout failure mode on the recovery path — the one surface whose purpose is restoring access to an operator who has already lost it — to defend a boundary that is not there is a net loss. Recording the position with an explicit reachability tripwire converts the honest low-exploitability assessment into a durable, checkable claim, which is the outcome the finding sought; the review states plainly that a formal deferral is acceptable here and that leaving it unrecorded is not.

## Consequences

The door's contract is now literally true, and the enrollment verbs no longer inherit an unguarded terminal read, so a console-less host refuses instead of blocking indefinitely and a rebound stdin refuses instead of echoing the passphrase. A programmatic caller that supplies no callback now receives a typed refusal where it previously received an environment lookup followed by a prompt; that is a deliberate narrowing and the intended behaviour, but it is a behaviour change for any driver that relied on the implicit environment read reaching enrollment.

The throttle decision leaves a documented, undefended surface. That is acceptable only while the reachability premise holds, and the premise is now written down next to the code that depends on it rather than living in a reviewer's head. The pathway this opens is a cheap future check: any change that makes the custody verbs remotely or cross-user reachable has a stated obligation attached to it.

The pitfall to name honestly is that the non-interactive default is a second resolution path alongside the explicit callback, and a future caller could reach it without noticing. It is constrained to refuse rather than prompt, which bounds the damage to a typed error, but it remains the surface a later pass over this module should scrutinise first.
