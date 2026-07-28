---
tags:
  - '#audit'
  - '#test-harness-honesty'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace test-harness-honesty with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `test-harness-honesty` audit: `The discovery service cannot start under fleet load, and reports the timeout as an identity failure`

## Scope

The semantic discovery service's startup path, measured on the operator
workstation on 2026-07-28 between 02:43 and 02:53 while three repositories ran
concurrent test fleets. The subject is the service's own start refusal, not the
index contents. This sits alongside the two open rows of the parent plan, which
cover a truncated index answering confidently and whether the code index can
converge while a committing fleet re-triggers its rebuild. This audit records a
third failure mode in the same family: under the same fleet load the service
does not merely index badly, it refuses to start, and it names the wrong cause
when it does.

The governing project rule refuses coding work whenever the discovery service is
unavailable, so this failure mode stops every agent in the fleet, not only the
one that observed it.

## Findings

### The service refuses to publish its own healthy child, and blames the child's identity

Five consecutive start attempts failed with `supervised Qdrant identity failed
final publication validation: witnessed managed child image is not Qdrant`. The
message asserts that the process the service just spawned is not the program it
is. That assertion is false. Each attempt logged a clean spawn from the
provisioned binary at the expected ports and storage path, and a clean shutdown
of that same child moments later.

### The real cause is a shared two-second budget against a three-second probe

The final publication check runs four sequential witness probes against one
shared deadline whose default is `inspection_timeout: float = 2.0` seconds. Each
probe draws from what the previous ones left. The third probe, the image check,
is implemented on Windows by shelling out to `tasklist` and testing whether the
string `qdrant` appears in its output; on a timeout it returns the same `False`
it returns for a genuinely wrong image, and the caller renders that `False` as
the identity message above.

Measured directly on the host while the fleet was running, `tasklist` took
**2794, 3421 and 3680 milliseconds** across three consecutive calls. A single
call therefore cannot complete inside the whole budget, let alone inside the
remainder after two earlier probes. The refusal is a timeout wearing an
identity failure's message.

### The load is real and is not this repository's

The host was concurrently running test processes out of three worktrees, this
one plus two others, alongside the standing runner lanes that share this box.
One of those peers is an active campaign in the discovery service's own
repository, running integration tests that take the machine-global singleton;
its transient child was observed and later confirmed gone, and the refusal
continued after it had exited. So peer contention is the load, but no single
peer process is the blocker, and killing one would not have helped.

### The failure is silent about what is actually wrong

An operator reading this message reasonably concludes the provisioned binary is
corrupt or that something is impersonating it, and goes looking at the wrong
layer. Nothing in the message, and nothing in the log line above it, mentions a
deadline. This is the same class of defect the parent plan's open rows already
describe: the service reports a state that reads as a definite negative when the
honest answer is that it could not tell in the time it allowed itself.

## Recommendations

These bind the discovery service's own repository, not this tree, and are
recorded here because this tree is where the cost lands.

- Distinguish a witness that says no from a witness that ran out of time. The
  image probe should return a third state, and the publication error should name
  the deadline it exceeded and the probe that exceeded it, so the message points
  at the load rather than at the binary.
- Do not implement a liveness probe as a process spawn on a machine the tool
  knows may be loaded, or give it a budget proportional to observed latency
  rather than a flat two seconds shared across four probes. A native process
  query does not pay the spawn cost that made this fail.
- Treat the shared budget as the defect it is. Four sequential probes drawing on
  one two-second deadline means the last probe is the first to be starved, and
  the last probe is the one whose failure is reported.

For this repository, the operational consequence is the honest one: while the
host carries a heavy fleet, the discovery service may be unstartable, and the
mandatory discovery rule then refuses all coding work. That refusal is correct
and should not be worked around by weakening the rule. The remedy is to let the
load drop, or for the operator to arbitrate machine contention.
