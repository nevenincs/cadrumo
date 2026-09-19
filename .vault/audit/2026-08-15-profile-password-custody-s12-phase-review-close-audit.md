---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:6b8744b8d8d069cee24b94f70a90aaf89821112cdf62c454e921baa5af8b807d'
related: []
---

# `profile-password-custody` audit: `s12 phase review close`

## Scope

Third review of the login and session handover phase, by a fresh-context reviewer
told that a refusal with reasons was the better outcome if it were the true one.
The step had been closed once on false evidence and refused once on true
evidence. **Verdict: PASS. The step can close.**

The reviewer was given the dispatcher's figures explicitly flagged as second-hand
and told not to lean on them, and did not: the central property was proven by
mutation rather than accepted from the fix report.

## Findings

The cross-process resurrection defect is genuinely closed, and the proof is a
mutation rather than a passing suite. An out-of-repo probe spawning three
interpreters -- log in as one profile, log in as another, then measure the first
profile's recoverable key material -- was run twice: once at the current tree,
once with the child reinstating the exact pre-fix derivation. The current tree
refuses, returning no key material. The reinstated derivation returns a
thirty-two byte key and reproduces the second review's tell verbatim, including
the empty closed-profile field. The union is therefore load-bearing rather than
incidental.

The live in-process session is confirmed as ONE INPUT rather than the gate, and
the durable source is read inside the pointer transaction, so it names the retired
profile in any fresh process. The union fold is shared with the logout path
rather than mirrored, so the two owners cannot drift apart.

**The proof's topology was checked, not just its assertions** -- which is what the
first false closure turned on. The regression now spawns real separate processes,
asserts on RECOVERED MATERIAL rather than a file's absence, and asserts against
the correct artefact of the three that share the word. Injecting the pre-fix
derivation through an import hook that reaches every spawned child reds five of
seven cases, each on the retired profile's key still being recoverable, and
leaves green precisely the crash phase whose retirement had already completed.
That is the same four-of-five leak profile the second review measured, which
means the gate now fails on exactly the defect it previously could not see.

The keyring axis is exercised for real rather than mocked, with the child process
setting a failing backend in its own environment.

### s12-silent-clear-refusal | medium | A refused receipt clear is invisible to its caller

Outside this step's declared scope and carried forward. The helper that discards
a known receipt RETURNS whether the compare-and-clear succeeded, and the resume
path branches on that value. The revocation entry point -- the function the
handover's retirement authority calls -- invokes the same helper bare and returns
nothing. So a refused clear is silent: a login can report the prior profile as
closed while its acceleration receipt survives on disk.

Reachability is narrow, requiring the bytes to change under a held per-profile
lock, which is why it is medium rather than high. But it is this campaign's
signature shape once more -- an operation reporting success when its precondition
is false -- and the value that would report it already exists and is already
honoured one function away.

## Recommendations

Close the step.

Open a row to have the revocation entry point honour the clear outcome as its
sibling already does.

Take the crash-phase flake off the watch list. It did not reproduce across five
sequential runs, and the single red observed during review was a peer's
half-landed edit failing on an undefined name, since resolved. The mechanism the
second review identified is closed in source: the injection now exits on
observing the phase with no intervening filesystem write, and the terminal phase
uses no watcher at all.
