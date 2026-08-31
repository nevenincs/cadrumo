---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:d6970576a15eda80e14cdcc6c5e16603237de10940172cfe445f3d9fe5128496'
step_id: 'S352'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Sweep the module-local strict-frozen configurations that W05.P23.S307 never reached, and land the detector only after. S307 IS NOT REOPENED and stays closed: what it claims on the shared constant was delivered and is load-bearing, and reopening a genuinely-delivered row would misrepresent it while orphaning its execution record. What escaped is the population that row's own text names as the thing it exists to avoid patching one at a time. TWO FIGURES, BOTH WITH THEIR FILTERS, because a number without its filter gets quoted back wrongly: of 269 inline ConfigDict calls in production modules, 62 declare strict AND frozen AND extra=forbid while omitting validate_default and adding no key -- a strict subset of the canonical with a guarantee silently removed -- and 182 declare strict OR frozen while omitting validate_default and adding no key. A further 40 add a genuine key and are the sanctioned divergences, but 39 OF THOSE 40 ALSO OMIT validate_default, so even the legitimate population is unprotected. The union is 221. An earlier report of 103 was wrong twice, counting test modules alongside production and using the narrow filter under the broad filter's description; do not carry 103 forward. Concentration means the top seven files cover roughly a third: application/live/remote_state_models.py 19, registry/query_reports.py 15, registry/record_design_schema.py 12, llm/models.py 10, registry/binding_selector_utils.py 7, llm/column_role_mapping.py 7, application/registry/diff.py 6. Repoint at the canonical by NAME at every use site -- assigning it to the old private constant would be a forwarding alias the rules prohibit outright, and the tell that a repoint is complete is that the module stops importing ConfigDict. Keep a local constant only where the module needs a DIFFERENT config, which the canonical docstring sanctions, and record the reason inline: a weaker config nobody chose is a defect, one somebody chose for a stated reason is a decision. Treat any default that then fails as a latent defect to report, per S307's own instruction. THE GATE LANDS LAST, in the same row and after the sweep -- an AST census refusing a module-local configuration whose keys are a strict subset of the canonical, admitting one only where it adds a key or carries a documented reason. Landing it first reds up to 221 sites and the cheapest route to green becomes weakening the detector, which is the third time that trap has appeared in this campaign. The three TUI operations modules are already repointed and are not in the remaining set

## Scope

- `the production modules holding a local strict-frozen configuration`
- `src/cadrumo/core/_models.py as read-only reference`
- `and a new subset-refusing census gate landed after the sweep`

## Changes

- `M` 60 production modules repointed to the canonical `STRICT_FROZEN_CONFIG`
- `verify:` `AST census before` -> `269 production ConfigDict calls; 222 in the sweep union`
- `verify:` `AST census after` -> `26 strict-subset sites remain across 24 files; 40 genuine-key admitted`
- `verify:` `ruff check` over every touched file -> `All checks passed`
- `verify:` `grep ConfigDict` over every touched file -> `0` (the row's own completion tell)

## Notes

PARTIAL: 170 of ~222 sites. The census gate is NOT landed and the row stays
open, per the row's own sequencing -- landing it first reds up to 221 sites and
makes weakening the detector the cheapest route to green.

RE-MEASURED FIRST, as the row demands. An independent AST census found 269
production calls, 66 / 183 / 40 across the row's three filters and a union of
222 against its stated 221 -- within tree drift, so the row's figures hold and
the discarded figure of 103 stays discarded.

NOT SWEPT, deliberately: `src/cadrumo/core/**` and any file a peer had touched
within the preceding 25 minutes. That is where the remaining 26 sites live. A
peer relocation was landing across core/ throughout (47 files in six minutes at
one point), and a 222-site sweep colliding with it would be unmergeable.

TWO DIVERGENCES KEPT, each with its reason recorded inline, per the row's rule
that a weaker config nobody chose is a defect while one somebody chose for a
stated reason is a decision:
- `PromptDefinition` keeps `arbitrary_types_allowed` -- it carries a compiled
  template object pydantic cannot describe.
- `PromptRegistry` keeps `strict=True` alone. It exposes a `register` mutator,
  so declaring it frozen would advertise an immutability the class lacks. Note
  the trap: pydantic's `frozen` blocks attribute assignment but NOT in-place
  mutation of the `definitions` dict, so freezing it would have PASSED the
  tests while making the model lie about itself.

THREE DEFECTS THE LINT PASS CAUGHT THAT PARSING DID NOT. Two modules import the
canonical aliased as `_STRICT_FROZEN`; the mechanical replacement wrote the
unaliased name at one site each, producing an undefined name that `ast.parse`
accepts. One module's pydantic import is parenthesised, so a single-line regex
left `ConfigDict` imported but unused -- a false "repoint complete" by the
row's own tell. Repointing by regex REQUIRES a lint pass; parse-clean is not
the bar.

VERIFICATION IS INCOMPLETE AND MUST NOT BE READ AS GREEN. The package run
reported `13 failed, 6452 passed`, an internally consistent footer -- and the
lost-test reporter contradicted it: 307 of 6773 collected tests never reported
an outcome after a worker died. Two of the 13 were investigated to root cause
and neither is config-related: modelo 200 declares NO export-layout fragments
at this HEAD (so `export_layouts` is legitimately empty), and modelo 390
declares no 2026 revision while the test requests one. Both are registry
coverage state, the same class as the modelo 303 2021 failures seen earlier.
The remaining eleven are unattributed.

## Notes (continued)

UPDATE 2026-08-31: THE SUBSET TEST IS NOT A PROMOTABILITY TEST, AND ACTING AS IF
IT WERE BROKE THE TREE.

The sweep's selector was "this config's keys are a strict subset of the
canonical's", which reads as "weaker, therefore safely strengthened". It is not.
Pydantic REFUSES `extra` on a `RootModel` outright -- `PydanticUserError:
RootModel does not support setting model_config['extra']` -- and the canonical
carries `extra="forbid"`. On a root model the canonical is not stronger, it is
INVALID, so those sites were never promotable.

Repointing `core/logging.py`'s `LogExtra` stopped that module importing, and
because `core.logging` sits under most of the tree it took four unrelated
modules with it. Parse passed, lint passed, and the earlier spot-checks passed;
only importing the modules surfaced it. A model-config change is validated at
class-construction time, so static checks cannot see it -- which is the reason
the 95-file batch needed an import sweep it did not get at the time.

Restored, each with its reason recorded inline, which is what turns an
apparently-weak config into a declared decision:
`core/logging.py`, `application/diagnostics_run_health.py`,
`application/diagnostics_telemetry.py`, `application/ledger/llm_diagnostics.py`
and `adapters/outbound/llm/_run_telemetry.py`.

Swept the whole tree for the same shape rather than assuming those were all:
exactly ONE other `RootModel` carries a strict-frozen config,
`core/json_contract.py:344`, and it uses a purpose-named `_STRICT_ROOT_CONFIG`
-- a correct pre-existing divergence, not a sweep casualty.

A SECOND POPULATION THE CENSUS WRONGLY COUNTED: roughly thirteen remaining
"subset" sites are `TypeAdapter(..., config=ConfigDict(strict=True))`, not model
configs at all. `frozen` and `extra` are model concepts; applying the canonical
to a TypeAdapter over `dict[str, object]` would be meaningless. They are
excluded, and the census that counts them is measuring the wrong population.

- `verify:` `import every one of the 70 touched modules` -> `70 of 70`
- `verify:` `tree-wide RootModel + strict-frozen config sweep` -> `1, pre-existing and correct`

### A SECOND non-promotable class, and it reached HEAD before it was caught

`llm/providers/local.py` parses THIRD-PARTY Ollama response envelopes. The
canonical config forbids extra fields; the runtime sends `message.role`, which
the model does not declare. Repointing it rejected valid responses and failed 27
tests. A peer's 00:05 "land the in-flight state" commit swept the change into
HEAD before the failure was found, so the regression was briefly live.

This is a DIFFERENT class from the RootModel one, and neither is visible to the
selector this sweep used:

- RootModel: the canonical is structurally INVALID -- pydantic refuses `extra`.
- Third-party payload boundary: the canonical is semantically WRONG -- forbidding
  unknown keys rejects valid input from a system this codebase does not control.

Both pass parse and lint. The first surfaces at class construction, the second
only at parse time with a real payload, so only running the tests finds it.
"Keys are a subset of the canonical" means the config is NARROWER; it does not
mean the canonical is CORRECT for that model. Any continuation of this sweep
must check the model's base class and whether it parses foreign input before
repointing.

Restored with the reason inline: tolerating unknown keys is the contract at a
boundary we do not own, and strictness belongs on the fields we DO declare.

- `verify:` `pytest src/cadrumo/llm` -> `2 failed, 497 passed` (57 before)
- `verify:` the 2 remaining -> `modelo 390 declares no 2026 revision`, the
  pre-existing registry-coverage failure, unrelated to configuration
- `verify:` `pytest llm/tests/test_evidence_draft_vision.py` -> `47 passed`
- `verify:` `pytest llm/tests/test_column_role_mapping.py` -> `23 passed`
