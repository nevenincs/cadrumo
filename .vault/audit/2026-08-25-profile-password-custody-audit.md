---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e350a262d028717d44b85391160a1633f792ad5b61490884bb68e14688200cbd'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `s257-censal-operation-review`

## Scope

Reviewed S257 against ADR D9 and the accepted censal autofill decision: canonical operation routing, exact review projection, encrypted operand custody, baseline conflict behavior, restart without reread, sole-writer authority, frontend settlement honesty, and executable CLI/TUI/application evidence.

## Findings

### s257-censal-operation-review | high | Initial frontend foreclosure omitted the canonical review operation

The first candidate removed the direct apply path but did not supply the accepted submit, start, project, respond, and resume workflow. The final implementation routes both shipped frontend lanes through that workflow.

### s257-censal-operation-review | medium | Initial anti-redeclaration proof was lexical

The replacement parses production ASTs, rejects the retired writer declaration, inventories bare and qualified `apply_cotejo` calls, and pins the sole reviewed writer plus the distinct certificate-file door.

### s257-censal-operation-review | high | Terminal lifecycle alone was reported as successful apply

The frontend now requires `SUCCEEDED`, the exact declared effect, and a validated `CensalOperationResult` outcome; an injected failed continuation proves it raises instead of reporting success.

### s257-censal-operation-review | high | S257 test reaches and migration evidence initially left hygiene gates red

The real TUI proof moved to its owning entrypoint test package, the stale manager test-debt entry was removed, and form contracts remain defined exactly once in `components.forms`. Concurrent unrelated relocation work still leaves the whole-tree census transiently red and is recorded as peer provenance.

### s257-censal-operation-review | low | Final formal review approved the corrected Step

The final independent review found no remaining S257 critical, high, or medium findings. It verified terminal honesty, typed result validation, canonical writer ownership, exact routing, rollback, restart coverage, and structural anti-redeclaration evidence. A fresh five-test unit slice passed; a later integration rerun was obstructed before S257 execution by concurrent custody work, after the executor had already recorded the passing three-case integration result.

## Recommendations

- Keep frontend success rendering conditional on the full terminal condition, effect, and typed outcome triple.
- Keep `apply_cotejo` caller ownership and the absence of `apply_censal_read` enforced structurally.
- Complete and close the concurrent TUI relocation through its own owning Step before treating the whole-tree migration census as green.
