---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:be32118cdbbd5ee58fa71e968c6091c392f1158996ef7dd40a071b1295f04488'
step_id: 'S53'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Decide and document which channels may supply the secret-store passphrase, reconciling the undeclared CADRUMO_SECRET_PASSPHRASE environment channel that is consulted first against the exactly-two-channels claim the module docstring makes, as a follow-on ADR

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_io.py`

## Description

- Read the P04 door safety review finding, the entangled HIGH finding it depends on, and the four surfaces the contradiction spans: the custody command module's two-channel claim, the substrate's non-interactive resolver, the settings field backing the environment variable, and the two custody verbs that already bind an explicit fixed-value callback.
- Scaffold a follow-on ADR under this feature tag through `vault add adr`, related to the door safety review audit, this plan, and the feature's grounding ADR.
- Evaluate three postures: amend the docstring to declare three channels, have the enrollment callback consult the environment variable then fall back to a hardened prompt, or bind every custody verb to an explicit callback so the environment channel is unreachable from the door.
- Record the decision: bind every custody verb explicitly; retain the environment variable unchanged as the substrate's non-interactive unlock channel; scope the command module's claim to the verbs it registers.
- Land the docstring side of the decision alongside the HIGH-finding repair, since both turn on which callback the enrollment path resolves and the review asked for them to be settled together.

## Outcome

The decision is recorded as an accepted ADR, `2026-07-25-auth-cert-recovery-custody-adr`, carrying both this step's channel decision and the throttle decision of `S56`. A single record was correct here rather than two: both are posture questions raised by one review over one door, and the ADR filename convention allots one record per feature per date, so a second same-day record for the same feature had no distinct home.

The chosen posture makes the door's existing two-channel claim true as written rather than lowering the guarantee to match the code. Every custody operation now resolves the passphrase through an explicit callback. The interactive verbs bind the hardened no-echo prompt; passphrase change and flat recover continue to bind the operator's own prompted or stdin-supplied value; recovery verify never reaches passphrase resolution at all, because it unwraps under a mnemonic-derived key rather than the master key, and was bound to the non-interactive resolver regardless so the claim holds structurally rather than by coincidence of the current call graph.

`CADRUMO_SECRET_PASSPHRASE` is retained unchanged as the declared channel for the substrate's own non-interactive unlock resolver, which automated drivers depend on. It is simply not reachable from the custody verbs. The command module docstring now scopes its claim to the verbs it registers, names the environment channel as a legitimate substrate channel elsewhere, and states that no verb registered there consults it.

`_master_key_io.py`, the file this step's Scope names, was deliberately not modified. It is the site the finding pointed at, but it is not the site the decision changes: the environment channel it implements is affirmed as correct for its own non-interactive caller, and what changed is which callers reach it. The repair therefore landed in the two modules that resolve the callback.

## Notes

The application layer's default when called programmatically with no callback is a non-interactive resolver bound to the settings the operation already resolved. It reads the configured passphrase and refuses with a typed error when none is set, and is deliberately incapable of prompting. This is a narrowing: a programmatic driver that previously relied on the implicit environment read reaching enrollment now receives a typed refusal. That is the intended behaviour, but it is a behaviour change worth naming rather than discovering.

The ADR names the remaining pitfall honestly. The non-interactive default is a second resolution path alongside the explicit callback, constrained to refuse rather than prompt, and it is the surface a later pass over this module should scrutinise first.

The keyring custody path was not exercised at runtime. Agent sessions run over an SSH network logon where Windows keychain calls fail with `WinError 1312`; that is an environment artefact, not a defect, and this decision does not touch that backend, which refuses before any passphrase resolves. The console-only remainder is stated rather than implied away.
