# Render profiles — authored numeric-representation review

One TOML fragment set per (modelo, design epoch), consumed by
`dev.registry.pipeline._render_profile`. Every file is AUTHORED evidence, not
generator output: each rule carries a hand-written `[.evidence]` block with its
decision id and justification.

## File schema

`NNNN-<topic>[-<NNN>].toml` — `NNNN` is the global ordinal in the directory
(the load order); the optional `NNN` is the per-topic counter; `fragment_id`
inside the file matches the filename stem.

## Topic vocabulary (closed)

- `numeric-representation` — reviewed numeric-representation policy for fields
  without a width-17 rule family (formerly spelled `reviewed-numerics`,
  `blank-numeric`, `unstated-numerics`).
- `singletons` — singleton-field numeric rules (formerly `singleton-numerics`).
- `width17-num` — width-17 rules for `Num`-type fields.
- `width17-n` — width-17 rules for `N`-type fields (n-prefix negative sign
  policy). Deliberately distinct from `width17-num`: the two populations carry
  different sign policies and are never the same topic.
- `identifier-digits` — identifier digit-width policy (modelo 210).

A new topic stem is a change to this vocabulary: add it here in the same
change as its first use.
