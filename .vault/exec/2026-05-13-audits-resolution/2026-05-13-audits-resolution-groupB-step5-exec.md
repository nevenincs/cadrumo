---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-b step-5

## scope

Plan row B5: fill the locale catalogues for every key the broadened
scanner now discovers.

## changes

Each of `src/aeat/locales/{es,en,ca,hu}.yml` gains new entries under:

- `cli.registry.metrics:` — 45 metric labels matching every
  `_emit_metric(name, ...)` call site in
  `src/aeat/entrypoints/cli/registry.py`. The es / en values carry
  the metric identifier as the label so the rendered line stays
  machine-parseable.
- `cli.review:` — `app_help`, `errors.invalid_state`, the
  `labels` block (`id`, `kind`, `next`, `severity`), the `queue`
  block (`empty`, `help`, `kind_help`, `modelo_help`,
  `state_help`), and the `show` block (`help`, `id_help`).
- `cli.config.auth.reserved_provider` — operator-facing message for
  the reserved provider slots.
- `cli.filing.import.año_help` — the Unicode help key
  the regex scanner picks up at line 541 of
  `src/aeat/entrypoints/cli/filing/__init__.py`.

es and en carry real translations; ca and hu carry English text for
now. B6 captures the intentional-identical state in the honesty
allowlist.

## verification

`audit_cli_translations()` returns `()`.
`audit_wizard_translations()` returns `()`.

The locale parity test still flags many extra-key warnings (YAML
keys the static scanner cannot resolve to call sites — e.g., domain
error messages keyed but emitted indirectly); these were
already present pre-B5 and grow as the broadened scanner discovers
more dotted prefixes than it can validate by lookup. The
audit-functions are the authoritative gate per the plan.
