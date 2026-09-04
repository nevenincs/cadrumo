---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:e4bbe3a0d250ca0d83d2168e3f56756b3ea6ed246c321a98b47a0638934217b0'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P02-S07]]"
---

# `clitui-ledger` audit: `S07 TUI census review`

## Scope

Mandatory independent review of approved-plan step `W01.P02.S07`. The review
compared the S07 reference, execution record, plan state, and feature index with
all production Ledger TUI components, internal routes and messages, root app
dispatch, installed-session and launcher composition, application workspace
generation, installed search, CLI TUI metadata, and focused harnesses. No
production TUI or product code was changed.

Seven one-to-one internal routes name seven concrete area screens. The package
also has two shared screen bases and one typed refusal body. One controller,
one root factory, and one resolver own the graph. Production admits the outer
`workbench.ledger` destination when generation and admission agree; its factory
always resolves Overview. Exact production search finds declarations and
emitters but zero consumers of `LedgerRouteRequested`,
`LedgerReviewRequested`, `LedgerEvidenceReviewRequested`, and
`LedgerBackRequested`.

Installed composition injects exactly two read-action references,
`operator.ledger.review` and `operator.ledger.evidence.review.list`, and no
classification, import, or link mutation door. Synthetic component tests supply
those optional doors and cannot prove production enrollment. All 78 separate
CLI census entries remain `TuiCapability.NOT_IMPLEMENTED`. The secure
generation reader supplies the application-owned workspace projection to the
outer Ledger factory and installed search, proving a real read path without
proving mutation or internal navigation.

The dedicated three-file component harness has 38 test functions and collects
78 integration cases. The focused component plus installed-composition lane
passes 88 tests with 18 non-integration cases deselected. Ruff format/lint and
scoped `ty` pass. G0 remains OPEN and the TUI hold remains in force.

## Findings

### overview-installed-state | high | The sole reachable Ledger screen is misclassified as component-only

The reference correctly states that the installed `workbench.ledger` factory
constructs the internal Overview route and that Overview is the current
operator-reachable Ledger body. Its table nevertheless labels
`ledger.overview` `component_only` because it lacks an independently enrolled
message bridge. That contradicts the campaign's closed definition:
`INSTALLED` means operator-reachable through production composition, while
`COMPONENT_ONLY` means not installed. Production invokes
`ledger_screen_factory`, constructs the controller, resolves the Overview
target through `resolve_ledger_screen`, and returns `LedgerOverviewScreen`.
Independent root-level enrollment is not part of the predicate.

This is HIGH because installed reachability versus component construction is
the primary S07 deliverable. The current partition is one installed read-only
Overview route and six component-only routes. The absent consumers still prove
that no other route is reachable and Review/Evidence actions do not execute.
Calling all seven component-only silently discards the only positive installed
path and hands S08 a false supported-surface input.

### supported-surface-detector | high | The published digest has no committed projection or drift detector

The reference publishes
`sha256:c7402f5b7abf3ce30ce5b9e1452db1e894fe581d3e133e9f0c9f65af7476a0d1`
as an exact length-framed observation, but exact repository search finds it only
in the reference. No committed owner fixes the source list, schema, serializer,
or semantic census. Independent recovery reproduced the value by unsigned
eight-byte big-endian framing of sorted relative paths and bodies for eight
inferred files, but the prose omits four paths and the framing width/endianness.

A source hash also cannot establish the negative semantic claims by itself.
Adding a handler in a new production module, wiring a submitter through another
composition path, or adding a route outside the inferred files has no committed
check that fails. The green harnesses exercise known fixtures; none asserts the
exact production consumer/door absence. Under detector-teeth and
no-silent-under-declaration rules, this is not sufficient evidence for calling
the supported-surface stream exact and complete.

## Recommendations

- Reopen `W01.P02.S07`; mark `ledger.overview` installed/read-only and the other
  six routes component-only. Preserve the separate outer-installation,
  disconnected-navigation, and absent-mutation-door facts.
- Add a canonical supported-surface projection owner in
  `dev/quality/clitui_ledger_capability_matrix.py` with tests in its existing
  test module. Derive routes/screens, initial installed resolution, production
  actions and optional doors, and consumers of all four messages from a
  declared complete production scope. Pin the byte schema/source set and add
  defects for new/missing/duplicate routes, a new consumer, a mutation door,
  and a source outside the observed set. Refresh the reference, record,
  plan/index state, then obtain another independent review.

## Remediation review

Ruling: **NOT ACCEPTED**. The Overview classification HIGH is closed, but the
supported-surface detector HIGH remains open because its AST extraction does
not identify the semantics it publishes.

The corrected live projection reports `ledger.overview` as the sole installed
read-only internal route and exactly six routes as `component_only`. Zero
detected message consumers continues to bound the other routes' reachability.
The source selector contains 126 files: all production TUI Python modules
excluding tests/devtools, three dedicated Ledger harness files, three installed
composition harness files, four application workspace/search-generation files,
and all Ledger command-spec modules. It imports no product TUI while building
the census and does not introduce business authority.

Independent standard-library reconstruction confirms the NUL-terminated v1
domains, sorted repository-relative paths, unsigned eight-byte big-endian path
and body frames, canonical ASCII JSON, and framed payload. The source digest is
`sha256:e7337508a02ef2260e0b28205c31bb872b69f59aa51a18391ae209c21b8f9d57`
and the census digest is
`sha256:c136cfe1ae3f82a239476c00e805f8c9a29e010d502e74397963cea7e6f42371`.
The live semantic result contains seven routes, zero reported message
consumers, two read-action ids, zero mutation doors, and 78 CLI statuses all
equal to `not-implemented`. The governed harness scope has six files and 65
test functions; the narrower dedicated component harness remains three files,
38 functions, and 78 collected integration cases.

### supported-surface-ast-semantics | high | The detector confuses matching syntax with installed consumers, actions, and routes

The consumer extractor collects any function whose name matches Textual's
conventional handler spelling, regardless of whether it is a method on a
mounted message recipient. The committed mutation test appends a module-level
free function to `app.py`; the census calls that unreachable function an
installed `LedgerRouteRequested` consumer. Conversely, an independently
injected real `@on(LedgerRouteRequested)` method on `CadrumoTuiApp` with a
nonconventional method name remains classified as zero consumers. The extractor
also excludes the complete `ledger/controller.py` module, so a future real
consumer there cannot enter the semantic result.

The same syntax-only problem affects other fields. Adding an unused
`_LEDGER_UNUSED_ACTION = "operator.ledger.unused"` constant makes the census
report a third injected read action even though no composition consumes it.
Adding an unused helper that merely constructs
`LedgerRouteV1("ledger.shadow", ...)` makes the census report an eighth route,
although the constructor is not an entry in `LEDGER_ROUTES`. Installed-door
extraction similarly accepts keywords from every call named
`ledger_screen_factory` in `launcher.py`, without proving that the call is the
production-installed factory invocation.

All these mutations move the source digest, but the semantic projection is the
fact S07 publishes and S08 will ingest. Refreshing the baseline after an
ordinary source change would preserve a false positive or false negative. A
byte-drift alarm therefore does not repair the classifier. This remains HIGH
under detector-teeth and no-silent-under-declaration because the gate can
misstate whether a route, consumer, action, or mutation door is actually
installed.

The detector must bind AST facts to their owning constructs: route calls in the
`LEDGER_ROUTES` assignment; action constants actually passed into
`InstalledWorkbenchFactoryDependenciesV1`; mutation keywords on the returned
production `_ledger_generation_factory` call path; and both conventional and
decorator-based Textual handlers on classes that can receive the installed
messages. Add negative controls for dead free functions, unused constants,
unused factory calls, and unrelated route constructors, plus a positive
decorated-handler mutation. Then refresh S07 evidence and obtain another
independent review.

The ten focused census tests pass, the full matrix suite passes all 145 tests,
and Ruff, scoped `ty`, and basedpyright are clean. The final Vault check is
recorded in the review handoff. G0 remains OPEN, the TUI hold remains effective,
the record and plan/index state otherwise agree, and the remediation contains
no production TUI change.

## Semantic detector remediation review

Ruling: **NOT ACCEPTED**. The earlier syntax-classification defects are closed,
but one HIGH detector-teeth defect remains in the installed-screen dataflow.

Independent reconstruction again produced 126 selected sources, seven routes
with `ledger.overview` as the sole installed route, zero consumers, the two
published read-action ids, zero mutation doors, 78 CLI declarations all
`not-implemented`, and six governed harness files with 65 test functions. An
independent standard-library framing implementation reproduced source digest
`sha256:e7337508a02ef2260e0b28205c31bb872b69f59aa51a18391ae209c21b8f9d57`
and census digest
`sha256:c136cfe1ae3f82a239476c00e805f8c9a29e010d502e74397963cea7e6f42371`.

The remediated extractor correctly ignores a free convention-shaped handler,
an unused Ledger action constant, a dead `LedgerRouteV1` constructor, and a
dead same-name `ledger_screen_factory` call. It detects an `@on`-decorated
method on `CadrumoTuiApp`, a real `LEDGER_ROUTES` change, a changed factory
initial area, and an installed mutation keyword. Route facts are now confined
to the real `LEDGER_ROUTES` assignment; action facts are confined to the exact
`InstalledWorkbenchFactoryDependenciesV1` constructor; and recipient scanning
is confined to `CadrumoTuiApp`, the initial route screen, and their reachable
bases.

### installed-screen-return-dataflow | high | Unique matching calls are not proved to supply the returned installed screen

`_initial_route_area` applies `ast.walk` to all of `ledger_screen_factory` and
accepts the sole call named `resolve_ledger_screen`, but it does not prove that
the call is the value returned by the nested `create` closure. An independent
mutation changed the real return to `LedgerEntriesScreen(controller)` while
retaining the Overview resolver call in an unused assignment. The census still
reported `ledger.overview` as the sole installed route. This is a silent false
installed-reachability statement, not merely source drift.

The same defect exists one composition level above. `_installed_ledger_factory_call`
accepts the sole `ledger_screen_factory` call anywhere below
`_ledger_generation_factory`, without proving that its invocation supplies the
screen returned by the nested `create`. A mutation retained that call in an
unused `unused_factory` assignment and returned `Screen()` instead; the census
still reported the Ledger outer destination and Overview as installed. The
existing dead-call negative only appends a second call outside the owning
function and therefore does not exercise this boundary.

The owner must follow the exact returned value of `_ledger_generation_factory`
to its nested `create`, require that `create` returns the result of invoking the
one `ledger_screen_factory` value (directly or through explicitly modelled local
aliases), and then follow `ledger_screen_factory` to its returned `create` and
require that closure's returned expression to be the `resolve_ledger_screen`
call whose target determines the initial route. Unsupported, multiple, dead,
or alternate return shapes must fail closed. Durable mutations in
`dev/quality/tests/test_clitui_ledger_capability_matrix.py` must retain a dead
matching call while changing each real return and prove rejection or the
correct changed semantic result.

The focused S07 detector selection passes 16 tests with 135 deselected; the
full capability-matrix module passes all 151 tests. The installed/component TUI
lane passes 88 tests with 18 deselected. Ruff format/check, scoped `ty`, and
basedpyright are clean, and the feature Vault check passes. No production TUI
file changed in this remediation. G0 remains OPEN and the TUI hold remains in
force; the checked S07 record/plan state describes the delivered census but
cannot close this remaining quality-gate defect.

## Final return-dataflow remediation review

Ruling: **NOT ACCEPTED**. The two prior dead-return counterexamples are now
rejected and explicit simple alias chains are resolved, but the extractor still
silently accepts branch-dependent aliases. One HIGH therefore remains.

The live projection remains stable: 126 selected sources, seven routes with
`ledger.overview` as the sole installed route, zero message consumers, two
read-action ids, zero mutation doors, 78 CLI declarations all
`not-implemented`, and six governed harness files with 65 test functions.
Independent framing again reproduced source digest
`sha256:e7337508a02ef2260e0b28205c31bb872b69f59aa51a18391ae209c21b8f9d57`
and census digest
`sha256:c136cfe1ae3f82a239476c00e805f8c9a29e010d502e74397963cea7e6f42371`.
No production TUI file changed; G0 remains OPEN and the TUI hold remains in
force.

The return resolver now identifies the exact nested `create` returned from
both owning factories, resolves explicit local name aliases, rejects cycles,
unresolved expressions, multiple non-null returns, and the two prior mutations
that retained dead matching calls while returning an Entries or generic
screen. The earlier free-handler, decorated-handler, unused-constant,
dead-route, dead-factory, real-route, and real-initial-route adversaries also
behave as required.

### branch-dependent-return-alias | high | Conditional alias writes are ignored instead of failing closed

`_simple_assignments` records only direct statements in a function body. It
does not reject control-flow statements that write an alias later used by the
effective return. Consequently the detector treats the direct assignment as
the complete dataflow and ignores a conditional reassignment.

Two independent valid-shape mutations demonstrate the false result. In the
Ledger root `create`, assigning `target` to Overview, conditionally reassigning
it to Entries for the installed context, and returning
`resolve_ledger_screen(controller, target)` is accepted and still reports
Overview. In the installed launcher `create`, assigning `screen` from
`ledger_screen_factory(...)(context)`, conditionally replacing it with
`Screen()`, and returning `screen` is accepted and still reports
`workbench.ledger`/Overview as installed. In both cases the effective returned
screen is branch-dependent, exactly the unsupported shape demanded to fail
closed.

The correction must reject any assignment to a followed alias outside the one
supported direct, unconditional assignment, including writes inside `if`,
`match`, loops, `try`, `with`, comprehensions, or exception paths. It must also
reject duplicate assignments/deletions and alias reads before their defining
write. Durable tests in
`dev/quality/tests/test_clitui_ledger_capability_matrix.py` must cover at least
the conditional target and conditional screen mutations above, alongside the
existing cycle, multiple-return, unresolved, dead-call, and positive alias
controls.

The final focused S07 selection passes 20 tests with 135 deselected, and the
full matrix module passes all 155 tests. Ruff format/check, scoped `ty`,
basedpyright, and the feature Vault check pass. The record/reference/plan repeat
the unchanged live facts, but their completed S07 state cannot satisfy the
quality gate while this branch false-negative remains.
