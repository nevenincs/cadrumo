---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:b925a8b3b4e35418e6e20b4f8a83b73e91e2b4082006c2a0a7c01fc11c03e2ae'
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
