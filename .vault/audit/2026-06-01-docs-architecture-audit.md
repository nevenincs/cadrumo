---
tags:
  - '#audit'
  - '#docs-architecture'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---



# `docs-architecture` audit: campaign-close honesty review

## Scope

A fresh-context honesty review of the documentation epic, run before declaring
structural completion, as the campaign-close honesty-review gate requires. The
reviewer inherited the epic with no prior context and verified each claim
against the live repository rather than the closure narrative. The epic spans
five waves: tooling foundation, the conformance harness, full-tree
cross-reference remediation, the user-doc rewrite, and the editorial workflow
plus gate flip.

## Findings

### Conformance harness is committed and structurally sound

The module-to-stub correspondence check reports zero drift, the
correspondence test passes, the CLI reference generator and its drift and
conformance tests pass, the vendored intersphinx inventories resolve offline,
and the no-metadata convention holds with zero leaks across the README, the
guides, the Sphinx configuration, and all generated stubs. The user-doc
surface is complete and accurate: the README, getting-started, and architecture
pages exist, are wired into the documentation index, link only to pages that
exist, and every command and class name was verified against the code.

### The nitpicky build is not yet at zero - remediation is incomplete

The headline gate, the nitpicky warnings-as-errors Sphinx build, still emits
unresolved cross-references, so the committed build-gate test fails. The
residual is genuine content: public functions referenced in docstrings that
carry no docstring of their own and so are not documented, plus a small set of
docstring-role bugs that reference parameter names, builtins, or literals as
cross-references. These are real conformance findings; suppressing them with
broad ignores would hollow out the gate. The flip-gates-to-blocking work cannot
honestly land until this residual reaches zero.

### Enforcement tools are configured but not all wired into a lane

The docstring-presence ruleset and its coverage floor run in the lint and docs
lanes. The docstring-signature accuracy checker is configured but its findings
are not yet zero, so it is not yet wired into a blocking lane. The coverage
floor is a floor, not a full-documentation hard cut.

### The docs lane is not yet a standing blocking gate

The documentation tests are excluded from the default unit lane and are not
invoked by any standing automated trigger. Making them blocking depends on the
build reaching zero first.

## Recommendations

1. Finish the cross-reference remediation: document the public functions that
   are referenced but undocumented, and correct the docstring-role bugs, until
   the nitpicky build exits clean. Track each as a remediation step with the
   build as its verification gate.
2. Once the build is clean, wire the docs tests into a standing blocking gate
   and add the signature-accuracy checker to the docs lane after its findings
   reach zero.
3. Keep the coverage floor honest about being a floor; raise it as remediation
   progresses rather than treating the current pass as full coverage.

The single most important item before the epic can honestly be called complete:
the nitpicky build must reach zero unresolved cross-references. Everything that
depends on a green gate is blocked behind it.

## Resolution

The single blocking item is now closed. The remaining unresolved cross-references
were remediated as content, not suppressed: forty-five docstrings were corrected
across the adapters, application, core, and domain layers, and the final
stragglers were a parameter named as an exception type in a Raises section and a
PEP 695 type parameter. The nitpicky warnings-as-errors build now exits clean
with zero unresolved cross-references, zero import failures, and zero duplicate
descriptions.

With the build green, the docs lane was promoted from advisory to a standing
blocking gate in the push workflow, running the nitpicky build, the
module-to-stub correspondence check, the CLI reference drift and conformance
tests, the reStructuredText formatter, and the docstring-coverage floor. During
remediation a peer removed a source module; the correspondence check caught the
resulting orphan stub immediately, which is the drift protection the gate exists
to provide.

Two items from the recommendations remain open as follow-on hardening rather
than blockers: wiring the docstring-signature accuracy checker into the docs
lane once its findings reach zero, and raising the coverage floor as further
docstrings land. Both are improvements on top of a now-green gate.

