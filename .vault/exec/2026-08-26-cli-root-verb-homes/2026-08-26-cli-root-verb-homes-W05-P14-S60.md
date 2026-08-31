---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1691c02192cb670d11ef7a2a96866788294e6c04ba39864a1f441a964917e654'
step_id: 'S60'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Judge the app-versus-config home of all 45 subjects the placement gate declines to rule on, and state the criterion that separates the two roots

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `python -c "...COMMAND_GRAPH unsignalled-subject enumeration..."` -> `45 subjects, 0 mis-homed`

## Notes

No code changed. This is the campaign's central question answered over the part
of the tree no gate can reach.

The placement gate is a refusal criterion: it fires only where a subject's own
`ExecutionPolicySpec` contradicts its mount, and its docstring is explicit that
roughly two thirds of subjects carry no signal either way and that a green run
is not evidence they are correctly placed. Those 45 subjects were the largest
remaining residue of this campaign. Every one has now been read.

**The criterion that separates the roots, stated positively:** `config` is where
the operator establishes WHO THEY ARE and WHAT THE TOOL MAY USE -- identity,
credentials, keys, storage, integrations, provisioning. `app` is where the
operator DOES TAX WORK, and observes the work being done.

All 45 conform. Every `config` subject is auth, certificates, apoderado, Google
integration, passphrase, profile facts, collaboration recipients, provisioning
or storage repair. Every `app` subject is ledger, live AEAT reads, modelo work,
overview, review, or diagnostics of those runs.

Three pairs sit either side of the line and demonstrate it rather than blur it.
`config collab recipient add` registers a trusted recipient's X25519 public key;
`app modelo review-package encrypt-for-recipient` seals a package to that
registered key. `config google folder set` records the Drive root; `app modelo
spreadsheet push` writes workbooks into it. `config provision` installs the
local models; `app diagnostics` reports on their runs. In each case config
establishes the capability and app spends it.

Two cases were considered and resolved rather than waved through.
`config profile descendiente` holds dependants, which are taxpayer facts feeding
IRPF calculations -- but they are facts about who the taxpayer is, which is what
`config profile` exists to hold, and it sits consistently beside `capabilities`
and `censo`. `app diagnostics` is neither configuration nor tax work, but with
only two roots permitted it is observation OF the work, and filing runtime
telemetry under setup would be worse.

The standing goal asked that every app-versus-config conflation be found and
tightened. On the evidence of this pass there are none left to find; what the
pass cannot claim is that the criterion above is enforced -- it is judgement
recorded in prose, not a gate, and a future subject could be mounted against it
without anything going red.
