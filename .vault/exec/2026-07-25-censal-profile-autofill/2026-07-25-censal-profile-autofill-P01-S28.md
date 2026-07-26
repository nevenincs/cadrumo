---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S28'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censal-profile-autofill with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-25-censal-profile-autofill-plan placeholders are machine-filled by
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
     The Reproduce whether a certificate provider paired with a cleared profile identity reaches any refusing guard at all, treating the composed two-agent report as unsettled until execution decides it either way, and naming what stops the read if anything does and ## Scope

- `src/cadrumo/application/auth/_sessions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Reproduce whether a certificate provider paired with a cleared profile identity reaches any refusing guard at all, treating the composed two-agent report as unsettled until execution decides it either way, and naming what stops the read if anything does

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Compose the two separately-proven halves into one in-process run, since each
  had been driven directly and the chain between them had only been read.
- Drive three paths against a foreign censal read: an active profile whose
  fiscal identity was cleared, a profile that never recorded one, and an intact
  profile reading its own taxpayer as a positive control.
- Name the refusing layer for each path rather than reporting a refusal.
- Establish whether the certificate session is an input to the ownership
  comparison at all.

## Outcome

The composition does not reproduce. Every route is refused, each by a named
layer, and the refusals come from the fixes rather than from anything
pre-existing.

An active profile whose identity was cleared is refused twice: at the session
entry, which will not bind a live session for an active profile carrying no
fiscal identity, and again at the read, which refuses a censal read it cannot
confirm belongs to this profile. A profile that never recorded an identity
proceeds through the session entry by deliberate exemption, since a profile
still in setup needs a session to finish setting up, and is then refused at the
read on the never-recorded branch. The control adopted three paths, which is
what proves the probe reaches the adoption rather than failing short of it.

The composed hazard is also weaker than the report that prompted this step
described, for a reason independent of the fixes. The ownership comparison reads
the fiscal identity carried in the returned document, never the session's: the
reconciliation takes no session parameter and the module consults no session
state. The session selects the SUBJECT of the read - the pull accepts no subject
parameter, so it fetches whoever is authenticated and cannot be redirected - and
it cannot influence whether the read is ACCEPTED. Both properties are
load-bearing and neither alone is the safety property.

Those two claims are separate and were briefly collapsed in reporting. That the
defence refuses is a fact about the fixes. That the certificate cannot be a
channel is a fact about the shape of the call, and would hold without them.

## Notes

The certificate was deliberately not minted, though the test support builds one
bearing an arbitrary subject. There is no input for it to change: a run would
not distinguish the guard holding from the session being irrelevant, and the
second answer was already established. Executing something shown unable to
matter produces a result nobody can interpret.

Two defects in the probe itself are recorded because both would have produced a
trustworthy-looking negative.

The first was a false refusal. An early run raised a missing-manifest error from
the harness rather than from any guard, printed in the same column as the real
refusals. A refusal at a layer that is defending nothing reads exactly like a
defence, so a refusal reported without naming its layer manufactures
reassurance.

The second is the reason the control exists. The result summariser assumed the
wrong return shape and would have raised on any success. Every refusing path
stopped before reaching it, so the probe looked healthy while being structurally
incapable of reporting a success at all. A probe whose only outcomes are
refusals cannot distinguish refused from cannot-proceed; an arm expected to
succeed is what separates them, and here it caught the defect.

The property this step establishes was afterwards found already pinned, by two
tests in one module that did not reference each other. No third test was added;
the two were annotated to name each other instead, since each is individually
green and the coupling is invisible at exactly the moment someone deletes one.
