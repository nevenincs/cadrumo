---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b03a649c594e5b913d3c59bdcd86457b385be80262367f3e817a9d8486ab4741'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
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

# `tui-architecture` audit: `s14 review`

## Scope

Independent review of `W02.P03.S14`, limited to operation-definition completeness, immutable registry and action-reference lookup, public facade, direct tests, and exact evidence.

## Findings

### definition-completeness | high | The canonical definition omits two D6 bindings

D6 requires the single registry definition to bind reconciliation policy and permitted frontend projections in addition to schemas, executor, phases, interactions, baseline/capabilities, effects, and replay semantics. `OperationDefinition` has no reconciliation-policy or permitted-projection field, and targeted search finds no alternate binding in the operation package. This leaves the purported complete definition unable to drive later recovery and projection conformance without adding facts out of band.

### executor-factory-binding | high | Factory output and request schema are not correlated or behaviorally proved

`OperationExecutorFactory` is a broad `Callable[[], OperationExecutor[BaseModel]]`, while `OperationDefinition` stores an unrelated `request_type`. Construction validates only that the value is callable: it does not invoke the factory, establish that its result implements the executor protocol, or bind the executor request payload to the registered request model. The direct suite never calls `executor_factory` or checks the produced protocol. A callable returning an arbitrary object can therefore be registered successfully, defeating the definition's executor-contract claim.

### registry-identity | low | Immutable lookup and optional action join remain narrow and fail closed

The registry freezes and canonically orders definitions, refuses duplicate definition IDs and duplicate joined action IDs, and raises for unknown definition/action lookups. It stores only canonical `ActionReference` identity and does not copy catalogue commands, arguments, presentation, or resolution policy.

### gates | low | Focused gates are green for the exercised surface

The execution record reports five focused tests passing plus clean Ruff and basedpyright. Public facade topology includes only the new registry owner. These gates are credible but do not cover the two HIGH omissions.

## Recommendations

- Complete the canonical definition with closed reconciliation and frontend-projection bindings required by D6, reusing established types if they exist or defining the narrow missing operation-owned axes here.
- Make the request/factory relationship type-safe and fail closed when factory output does not satisfy the public executor protocol; add direct valid and invalid factory tests using production contracts.
- Rerun exact registry/facade pytest, Ruff, and basedpyright gates after remediation.

## Final re-review

### definition-completeness-closure | low | Closed recovery and projection axes complete D6

`OperationDefinition` now requires a closed owner-loss reconciliation policy and a non-empty set of frontend-neutral projection identities. The registry imports no frontend package or implementation type, while the existing capabilities continue to own baseline, replay, and effect declarations. The original completeness HIGH is closed.

### executor-factory-binding-closure | low | Frozen descriptor binds request and validates structural output safely

The frozen factory descriptor declares the exact request model and executor class. Definition validation requires descriptor and definition request identity to match; descriptor construction refuses classes that do not structurally implement the public executor protocol without instantiating them. `create()` constructs but does not execute the executor and refuses undeclared or structurally invalid results. Direct tests prove accepted construction, request mismatch, and wrong output. The original factory HIGH is closed.

### final-gates | low | Exact remediated surface is green

The execution record reports seven focused registry/facade tests passing, Ruff clean, and basedpyright with zero errors, warnings, or notes. The public facade exports the new registry-owned axes and descriptor, and its exact import topology remains frontend-free.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.

## Reopened typed-resolver review

### concrete-two-pass-resolution | low | Resolver implementation hydrates only the registered concrete model

Both methods strictly parse a minimal definition-bearing header, perform fail-closed immutable registry lookup, then validate the unchanged JSON through `OperationRequest[request_type]` or `OperationSnapshot[request_type]`. The full second pass forbids extra or malformed outer/inner data and reuses snapshot definition/subject correlation. There is no mapping, `Any`, unparameterized `BaseModel`, or payload fallback.

### existential-return-annotation | low | BaseModel parameterization is a safe erased public view here

The runtime object is always the dynamically selected concrete generic model, while the public annotation intentionally exposes only the common `BaseModel` payload bound to callers that cannot statically know the registry-selected type. It does not cause runtime hydration through `BaseModel`, and consumers cannot infer a narrower payload. A new erased protocol or alias would add a second structural authority without improving safety.

### resolver-mutation-coverage | medium | Malformed JSON and subject-identity drift are not planted

The ten-test gate proves concrete request/snapshot round trips, byte input, observable payload mutation, unknown definitions on both routes, snapshot payload-model mismatch, and outer/request definition drift. It does not directly plant malformed JSON, a request-route payload mismatch, or snapshot identity/request `subject_ref` drift. Production validators appear to refuse all three, but the reopened acceptance proof is not mutation-sensitive to regressions in those exact branches.

Final verdict: FAIL. One MEDIUM finding remains; no CRITICAL or HIGH findings remain.

## Typed-resolver mutation closure

### resolver-mutation-coverage-closure | low | Both routes now carry exact refusal mutations

The focused suite now plants malformed JSON against request and snapshot resolution, a wrong concrete payload on the request route, and outer/inner subject drift in addition to the prior unknown-definition, snapshot wrong-model, and definition-drift cases. All are refused through production resolvers without fallback or mirrored parsing.

The execution record reports 11 focused tests passing, Ruff clean, and basedpyright with zero errors, warnings, or notes.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.
