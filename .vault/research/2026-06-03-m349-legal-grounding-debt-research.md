---
tags:
  - '#research'
  - '#m349-legal-grounding-debt'
date: '2026-06-03'
modified: '2026-06-29'
related:
  - "[[2026-06-03-m349-payable-invoice-authoring-research]]"
---

# `m349-legal-grounding-debt` research: M349 substantive Ley 37/1992 grounding debt - closed

## Current State - 2026-06-29

The original research finding is closed in the current registry.

Executable registry inventory over Modelo 349 `2020-y-siguientes` reports:

- invoice bindings: 34 total;
- `collectible_invoice` bindings: 17;
- `payable_invoice` bindings: 17;
- missing actionable LIVA refs on collectible bindings: 0;
- missing actionable LIVA refs on payable bindings: 0;
- missing current broad M349 LIVA/RIVA ref set on invoice bindings: 0;
- completeness manifest present and carrying the current broad M349 legal-ref
  set;
- `modelo-349-informative` construct present and carrying the current broad
  M349 legal-ref set.

The current invoice binding files are:

- `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0007-bindings.toml`
  for the 17 `collectible_invoice` bindings.
- `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0008-payable-bindings.toml`
  for the 17 `payable_invoice` mirror bindings.

Both binding sets carry the substantive M349 ref set:

```
ley-37-1992:art-9-bis
ley-37-1992:art-13
ley-37-1992:art-15
ley-37-1992:art-25
ley-37-1992:art-26
ley-37-1992:art-27
ley-37-1992:art-69
ley-37-1992:art-70
ley-37-1992:art-80
ley-37-1992:art-84
ley-37-1992:art-86
rd-1624-1992:art-79
rd-1624-1992:art-80
```

The originally actionable refs from this note were `ley-37-1992:art-15`,
`ley-37-1992:art-25`, and `ley-37-1992:art-26`; all are now present on all
34 invoice bindings, the completeness manifest, and the construct.

Do not add `ley-37-1992:art-141` for M349 triangulation. The bundled
consolidated LIVA text identifies article 141 as "Régimen especial de las
agencias de viajes". M349 triangulation is grounded through article 26 LIVA and
article 79 RIVA in the current registry.

## Historical Finding

The 2026-06-03 audit found the M349 binding set fully grounded
procedurally through the form-publication order and the general
information-supply duty, but missing substantive Ley 37/1992 references for
the intracommunity operations it described.

At that point, only 17 `collectible_invoice` bindings were in scope and their
uniform `legal_refs` were:

```
orden-eha-769-2010:art-1
ley-58-2003:art-93
```

That historical state is no longer current.

## Current Legal Catalogue

The current legal catalogue resolves every substantive ref named above. The
core articles from the original action item resolve to bundled corpus files:

- `ley-37-1992:art-15` ->
  `corpus/normatives/html/ley-37-1992-art-15.html#a15`
- `ley-37-1992:art-25` ->
  `corpus/normatives/html/ley-37-1992-art-25.html#a25`
- `ley-37-1992:art-26` ->
  `corpus/normatives/html/ley-37-1992-art-26.html#a26`

The broader current M349 ref set also resolves through bundled legal entries,
including `rd-1624-1992:art-79` and `rd-1624-1992:art-80`.

## Closure Verification

Verification command, read-only:

```
uv run python -
```

The script loaded the bundled registry with `load_registry_tree`, selected
Modelo 349 revision `2020-y-siguientes`, counted `binding.source` values, and
checked the required legal-ref subsets across all invoice bindings, the
completeness manifest, and the legal catalogue.

Focused registry test coverage for the same current state lives in
`src/aeat/domain/calculations/registry/tests/test_modelo_349_registry.py`,
including assertions that the revision has 17 `collectible_invoice` and
17 `payable_invoice` invoice bindings.

## Per-Binding Historical Inventory

The original 17 collectible binding ids remain, now substantively grounded:

- `iva-349-declarante-numero-operadores`
- `iva-349-declarante-importe-operaciones`
- `iva-349-declarante-numero-rectificaciones`
- `iva-349-declarante-importe-rectificaciones`
- `iva-349-operador-row-codigo-pais`
- `iva-349-operador-row-nif`
- `iva-349-operador-row-apellidos`
- `iva-349-operador-row-clave`
- `iva-349-operador-row-base`
- `iva-349-rectificacion-row-codigo-pais`
- `iva-349-rectificacion-row-nif`
- `iva-349-rectificacion-row-apellidos`
- `iva-349-rectificacion-row-clave`
- `iva-349-rectificacion-row-ejercicio`
- `iva-349-rectificacion-row-periodo`
- `iva-349-rectificacion-row-base-rectificada`
- `iva-349-rectificacion-row-base-anterior`

The current payable mirror ids add `-adquisicion` to the corresponding public
binding concepts and use `claves = ["A", "I", "T"]`.
