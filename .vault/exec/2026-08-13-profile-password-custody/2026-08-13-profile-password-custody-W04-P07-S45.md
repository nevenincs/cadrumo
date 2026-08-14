---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:8c59428b285893af7b4795314e993680c94a80bfb64cb67c8d00e7295c70b6fa'
step_id: 'S45'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the module coverage gate judge a property rather than static reachability

## Scope

- `src/cadrumo/tests/test_every_module_has_test_coverage.py`

## Description

- Replace import reachability with a symbol-use judgement, so a module counts as
  proven only when an executing test can reach code it defines.
- Key exemptions by module identity with a stated retirement condition, never by
  line, and make both a vanished entry and a redundant entry fail.
- Land the honest result rather than absorbing it.

## Outcome

The gate now judges a property. An edge exists only where one module references
a name another DEFINES, resolved through import bindings and re-export chains,
and the load-bearing rule is that a re-export is not a use: a facade importing a
private module contributes no edge, because importing a facade executes only
module-level definitions and never calls the functions. That single edge, emitted
in bulk by the old gate, is why one import from any surviving test kept an entire
package reported as covered -- and therefore why fifteen deleted test modules
left their production modules unproven without the gate noticing.

Transitive use through production code is deliberately kept, because a test that
calls a function which calls a helper really does run the helper.

No count, ratio or ceiling appears anywhere. Each module is asked an individual
yes-or-no question whose answer flips exactly when the test reaching it
disappears.

Verified independently: one failed and five passed, which is the intended shape.
The five that pass are the controls -- the anti-tautology facade proof, the
transitive-closure positive control, the negative control, and both
exemption-staleness gates. The one that fails is the canonical gate, reporting
nine genuinely unproven modules.

## Notes

An honesty caveat matters more than the headline. Neutralising the sixteen
restored auth test modules surfaces only ONE module, not the twenty-two the
originating narrative implies, because twenty-one of them remain genuinely
EXECUTED through other call chains. Under a strict exercised reading the gate is
right and they are covered.

The twenty-two figure belongs to a STRONGER property -- that a test asserts a
module's behaviour -- which was measured separately at two hundred and
sixty-eight modules tree-wide with no test naming any symbol they define. That
set was deliberately not landed or absorbed. Adopting it is a standing decision
about what this repository means by covered, not a detail of this step, and
recording the distinction is what stops the weaker property being mistaken for
the stronger one later.

Nine exemptions the closure now reaches on its own were deleted, and one added
after direct verification that its only entry into execution is a spawned
process. The gate refuses an entry naming a vanished path and refuses one naming
an already-exercised module, so a standing waiver cannot silently absorb the loss
of real coverage.

Several unproven modules are separately significant rather than merely uncovered:
an export-completeness refusal with no callers cannot fire, and an entire
interactive flow for two operator verbs has no caller at all. Those are carried
as findings.
