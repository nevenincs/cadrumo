---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:29c18eead5224c5de343af02ede92bdd537fc61d46818a9ab3d7de27c03cc3c3'
step_id: 'S41'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `AeatCertificadoId` as a new `IdentifierNamespace.AEAT_CERTIFICADO_ID` member and alias at the 13-digit-or-longer bound its docstring already states, and retype `RemoteNotification.certificado_id` onto it

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_notifications.py`

## Description

- Read the field, its class docstring, and its actual construction path
  before choosing a bound, rather than adopting the row's paraphrase of the
  docstring on trust — the same discipline this campaign has needed at
  every prior W05 row tonight. Found THREE different claims about one
  shape in the same file: the class docstring says "13-digit (or longer)";
  the field itself was `Field(min_length=8, max_length=32)`, no pattern;
  and the actual parse-time gate,
  `_CERT_RE = re.compile(r"^\d{10,16}$")`, is what every real value passes
  through BEFORE a `RemoteNotification` is ever constructed
  (`_row_from_cells` returns `None` on a `_CERT_RE` mismatch, never
  constructs the model with an unmatched value). The code comment beside
  the regex names the evidence directly: "13 digits. Captured:
  2699101808461 / 2596230606502."
- Used the parser's own gate as the bound, not the docstring's looser
  paraphrase: `AeatCertificadoId` is `min_length=10, max_length=16,
  pattern=r"^\d{10,16}$"` — digits-only, the deliberate 10-16 margin
  already chosen around the 13-digit observation (mirroring
  `AeatExpedienteId`'s own precedent: widen past a thin sample rather than
  pin to it). This is a genuine narrowing of the current field (which had
  no pattern and a wider 8-32 length window) and confirmed safe against
  every real construction site: the one production path is already gated
  by the identical regex, and all 21 test-fixture values across 6 test
  files are 13-digit literals or `f"{index:013d}"` zero-padded — every one
  already inside `10-16` digits.
- Declared `IdentifierNamespace.AEAT_CERTIFICADO_ID` and the
  `AeatCertificadoId` alias in `core/identity/_namespace.py`, re-exported
  through `core/identity/__init__.py`. Retyped
  `RemoteNotification.certificado_id` onto it, dropping the now-redundant
  inline `Field(min_length=8, max_length=32)`. Corrected the class
  docstring's "13-digit (or longer)" line to point at the alias rather than
  restate a bound that no longer matches the field.

## Outcome

COMPLETE. `ruff check`, `ruff format --check`, `basedpyright` clean on all
three touched files (`_namespace.py`, `core/identity/__init__.py` gated;
`_notifications.py` outside basedpyright's configured `include`). Real
tests green: 113 passed across `test_notifications.py` (both the sede
adapter and the application `live` suite), `test_calendar_post_filing_events.py`,
`test_calendar_notificacion_estado_servicio.py`,
`test_calendar_model_ownership.py`, `test_calendar.py`, and
`test_overview_calendar_verb.py` — every test file that constructs a
`RemoteNotification` directly.

## Notes

No incidents. The bound landed narrower and more precise than the row's
own "13-digit-or-longer" text asked for, because the row's text was itself
a paraphrase of a docstring that had already drifted from the code's real
enforced shape — recorded here so a future reader trusts the regex over
either piece of prose.
