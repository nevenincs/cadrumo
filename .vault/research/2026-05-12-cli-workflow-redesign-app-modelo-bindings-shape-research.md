---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `app modelo bindings shape`

## Topic

Design the `aeat app modelo bindings` surface for binding readiness discovery,
temporary override preview, and calculation binding overrides.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §4.3 and §6, the
app-modelo-shape ADR, modelo lifecycle ADRs, current modelo and declaration
binding code, registry binding queries, UX-012 supplier-flag closure, and the
phantom `data require/readiness` family.

## Rewrite Scope

This research supports a child ADR that locks app modelo bindings grammar,
supplier flag closure, missing/readiness behavior, the relationship between
`bindings preview` and `calculate --binding`, error-message fix pointers,
output/event behavior, rejected shapes, and the no-shim rule.

## Findings

The locked grammar should be:

```text
aeat app modelo bindings list --modelo M --year YYYY --period P [--missing]
aeat app modelo bindings preview --modelo M --year YYYY --period P [--binding KEY=VALUE]
aeat app modelo calculate WORK_UNIT_ID | --modelo M --year YYYY --period P [--binding KEY=VALUE]
```

Current `_modelo.py` has a registry introspection command named `bindings`, but
it does not provide the target app modelo `bindings list` and `bindings preview`
subcommands.

The apex phantom `data require/readiness` command should become:

```text
aeat app modelo bindings list --modelo X --year YYYY --period P --missing
```

`bindings list` reports required and available keys. `--missing` filters
unresolved required keys.

`bindings preview` resolves temporary `--binding` overrides without mutation.
Overrides should preserve scalar, list, and mapping values.

Current declaration `--binding` parsing only accepts `KEY=Decimal` and injects
into inputs before `build_draft`. `build_draft` separates casilla inputs,
calculation binding inputs, and persisted filing binding values.

Registry binding queries have static metadata but not readiness state.

UX-012 supplier flag closure is currently modeled as declaration calculate
`--binding` with direct Decimal input. In the redesigned app modelo flow,
supplier flag closure should be an explicit binding override shared by
`bindings preview` and `calculate`.

Source-derived readiness still requires backend aggregation or preflight
support. A known gap is that aggregate filing inputs returns `{}` except for
Modelo 100.

Missing binding raw errors should become domain-language readiness output using
these categories:

```text
bucket
ledger source
profile fact
prior filed revision
live observation
casilla
waiver
blocking finding
```

Error fix pointers A25/A26 for missing and unknown bindings remain follow-up
work.

Output goes through `_emit`.

No bucket events are needed for `bindings list` or `bindings preview` because
both are read-only. Calculate lifecycle events are covered by
calculate/revision ADRs. Filing records are covered by the filing-record ADR.

Rejected shapes are:

```text
inputs family
app declaration
root filing
submit/presentation/preflight
help support surface
mutating inventory under app modelo
```

No shims or aliases should be added.
