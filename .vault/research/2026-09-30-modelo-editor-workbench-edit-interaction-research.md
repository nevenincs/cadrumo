---
tags:
  - '#research'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:b15109d0de58b538ccadf9e00df73c00926a5d0ae60fcee30163ba20142689ae'
related:
  - "[[2026-09-30-modelo-editor-workbench-reference]]"
---

# `modelo-editor-workbench` research: `Editing, typed values and the staged session`

How does a person edit casilla values end to end, and how does that map onto the accepted edit contract? The evidence shows the current path loses work (memoryless carry-forward, Calculate wipes manual values, 303 edits fail, several data types unreachable) and favours a typed application parser, a persisted operator layer and a staged session with mandatory review. Measured on 2026-09-30 against the live tree and the published authority; probe scripts ran in session scratch and were not retained, so every figure names the code or data it was measured from.

## Findings

Investigator: lens C. Date: 2026-09-30. Worktree: `Y:\code\cadrumo-worktrees\tui` (read-only).
Scratch evidence: `(session scratch, not retained)`
(scripts `census.py`, `surface.py`, `rowtmpl.py`, `repro_edit.py`, `proto_parser.py`, `proto_edit_ui.py`; outputs `census.out`,
`repro_130.out`, `proto_parser.out`; screenshots `shots/*.svg`).

How I measured: the scripts ran against the published authority at the repo-root `.authority` directory
(`CADRUMO_AUTHORITY_ROOT` pointed there, read-only). The reproduction runs the real admission, wire translation and executor
(`admit_modelo_edit_baseline` -> `ModeloEditApplySubmissionV1.from_submission(...).to_submission()` -> `apply_modelo_edit`)
over real encrypted storage under the scratch directory (`isolated_runtime_profile` plus `profile_adapter_composition`, with the
same complete synthetic profile as the former source file). All values are synthetic.
Semantic code search (vaultspec-rag) was not used. I located code with targeted grep and full reads.

---

#### 1. Findings (with evidence)

##### 1.1 What the user can do today

- The TUI has one edit surface. For every writable surface entry it composes a bare `Input` whose placeholder is `Box {casilla}` or
  `Declared input {binding}`. The input shows no label, current value, origin, type, unit or help
  (the former source file, catalogue `src/cadrumo/locales/en/common.yml:1943-1946`).
- Apply sends every non-empty box as `SET_TYPED_VALUE`, with the raw string as the value (`overview.py:355-370`,
  `src/cadrumo/entrypoints/tui/modelo/lifecycle.py:129-169`). The door builds no `CLEAR_DECLARED_VALUE` and no `REMOVE_OVERRIDE`
  intent, so a user can neither clear a value nor restore a source value.
- The boxes start empty. They are never pre-filled with the current value.
- After a successful apply, the page dismisses itself (`overview.py:621-628`). A failed or refused apply leaves the typed strings in
  place. The door, however, holds a single baseline admitted at composition (`lifecycle.py:79`, `lifecycle.py:136`), so a stale
  baseline stays stale for the whole life of that screen (see 1.4).
- The size of the edit surface is unbounded in the UI. The measured admitted surfaces are:

  | Modelo (revision) | Writable manual casillas | Writable `manual_input` bindings | Inputs composed |
  |---|---|---|---|
  | 115 (2019-y-siguientes) | 1 | 0 | 1 |
  | 130 (2019-y-siguientes) | 5 | 0 | 5 |
  | 111 (2019-y-siguientes) | 19 | 0 | 19 |
  | 303 (2025) | 71 (57 money, 14 ratio) | 0 | 71 |
  | 390 (2025) | 241 | 173 (none bound to a casilla) | 414 |
  | 714 (2025) | ~111 casillas, 971 bindings | 971 | ~1,080 |
  | 100 (2025) | 1,979 | 2 | 1,981 |

  Source: `surface.py` and `rowtmpl.py` output; the surface projection is `src/cadrumo/application/modelo/edit_admission.py:134-189`.
  Modelo 369 has 825 `manual_input` bindings for 6 casillas.

##### 1.2 Data types, constraints and what the engine can actually accept

Census of MANUAL casillas in hydrated published revisions (146 revisions, `census.py` -> `census.out`):

| data_type | manual rows | required | declared constraints (rows) | engine channel (`_registry_helpers.py:67,82`, `schema_scalars.py:434-471`) | TUI executor routes to (`_edit_execution.py:86,128-133`) | Works today? |
|---|---|---|---|---|---|---|
| money | 19,856 | 157 | non_negative 422; non_negative+max 4; none 19,430 | Decimal | Decimal | yes (see lexical bugs) |
| text | 3,692 | 109 | enum 42 (sizes 1-4); length 58; none 3,632 | text | text | yes |
| boolean | 813 | 2 | none | Decimal, encoded 0/1 | **text** | **no, raw exception** |
| nif | 799 | 31 | length 8 | text (checksum-validated) | text | yes |
| ratio | 751 | 6 | 0..100 (30+8); 0..1 (210); none 713 | Decimal | Decimal | only with 2 decimals or fewer (bug 4.4) |
| decimal | 735 | 2 | sign 35 | Decimal | Decimal | only with 2 decimals or fewer |
| integer | 449 | 114 | max 12 (months), 0..1 indicators, 1..9 | Decimal | Decimal | yes |
| date | 224 | 16 | none | **none**: not text-family, not in numeric set | text | **no, raw exception** |
| name | 183 | 16 | none | text | text | yes |
| year | 136 | 10 | none | **none**: `year` is absent from the application numeric set | Decimal | **no, raw exception** |
| province_code | 55 | 14 | none | text | text | yes |
| country_code | 50 | 3 | none | text | text | yes |
| postal_code | 37 | 2 | none | text | text | yes |
| iban | 23 | 0 | none | text | text | yes |
| municipality_code | 10 | 0 | none | text | text | yes |
| ccaa_code | 10 | 0 | none | text | text | yes |
| nif_iva | 9 | 1 | none | text | text | yes |
| period_code | 6 | 1 | none | text | text | yes |
| bic | 3 | 0 | none | text | text | yes |

Consequences for the design:

- About 97% of manual casillas declare no constraint. "Absent constraints" is the normal case, not an edge case.
- Enums exist on only 42 text casillas. Their tokens are raw (for example `adeudo_en_cuenta`, `efectivo`,
  `domiciliacion_bancaria` for 136 `forma-pago`; `1`, `2` or `I`, `O` for 280). They have no display-label keys.
- `ratio` has no unit authority. The enum documents a ratio as "a proportion or rate expressed as a fraction"
  (`src/cadrumo/domain/calculations/registry/schema_base.py:699-700`). Yet 303 ratio casillas 89, 90, 91, 92 and 107 are
  constrained to 0..100 (percent), 210 `porcentaje_convenio` is constrained to 0..1, and 303 casillas 02, 05, 08 and 23 (manual rates)
  have no constraint at all. The editor cannot know whether `21` means 21% or 2,100%.
- 478 manual casillas are row-field templates. They are admitted as writable scalars, but the calculation refuses them
  (`rowtmpl.py`: 180, 184, 190, 193, 347, 349; refusal in `calculation_actions.py:542-544`).
- `required` sits on the casilla definition (`schema_surfaces.py:344`) and is not in the permitted surface. No required-missing
  signal exists at edit time.

##### 1.3 How an edit reaches persistence

The path is: door `lifecycle.py:129` -> wire `operation_definitions.py:2196-2305` -> operation executor
`operation_definitions.py:2351-2394` -> `apply_modelo_edit` `_edit_execution.py:380-449` ->
`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` `calculation_actions.py:1431` ->
`persist_calculation_revision` (`calculation_actions.py:604-646`).

- **The calculation is memoryless, and a revision does not record who authored an input.** The persisted
  `input_values_by_casilla_id` is the merged map of declaration-period values, backend (ledger or source) values, bound values and
  the caller's own values (`calculation_resolution.py:254-281`, persisted at `calculation_actions.py:618`). `binding_overrides` is
  likewise the merged profile, backend, borrador and caller binding channel (`calculation_resolution.py:170-185`,
  `calculation_resolution.py:335-342`). No field marks which entries the operator typed.
  Measured: 130 with no edits already records input `06='0'` (a backend value), and the operator's `06=100` is stored under the
  same key (`repro_130.out`, "rev0 inputs" and "rev1 full inputs").
- **The executor passes only the submitted intents.** It builds `casilla_inputs`, `text_casilla_inputs` and `binding_values` from
  this submission alone (`_edit_execution.py:102-134`, `_edit_execution.py:238-270`) and re-supplies only the current revision's
  detail rows (`_edit_execution.py:359-377`). This contradicts contract D4 ("absence means UNCHANGED").
- **Clear does not do what its name says.** `CLEAR_DECLARED_VALUE` only appends to `cleared_casilla_ids` (`_edit_execution.py:125-127`).
  That list feeds the revision id and nothing else: no verification, review or export consumer reads it (grep over
  `src/cadrumo/domain` and `src/cadrumo/application`). Clearing a casilla that a source also supplies leaves the source value in
  the inputs, so the revision says "cleared" and "0" for the same casilla (`repro_130.out`, "edit 3b").
- **`REMOVE_OVERRIDE` is refused.** `_edit_execution.py:249-253` returns `remove_override_not_yet_wired` (measured on 714,
  `repro_edit.py` output). `SET_OVERRIDE_VALUE` does execute, yet the enum still carries `SET_OVERRIDE_VALUE_NOT_YET_WIRED`
  (`edit_models.py:598`), and the module docstring still says every binding intent refuses (`_edit_execution.py:17-21`).
- **The eligibility rule for binding overrides differs between the contract and the code.** The accepted amendment says every
  binding whose source is not in `BUCKET_AGGREGATION_LOCK_SOURCES` is writable, date-channel bindings excluded. The code admits only
  `source is MANUAL_INPUT` and does not exclude date-channel bindings (`edit_admission.py:161-178`).
- **No parser and no preflight exist.** `ModeloEditParsedValueV1` and `ModeloEditParseResultV1` are declared
  (`edit_models.py:504-512`, `edit_models.py:648-651`), but nothing produces them. There is no `ModeloEditParseRequestV1` and no
  preflight service, even though the `edit_services.py` docstring claims both (`edit_services.py:1-7`). The executor coerces with
  `Decimal(str(value))` (`_edit_execution.py:131`) and `str(value)` (`_edit_execution.py:133`).
- **The wire bound is a money rule applied to every type.** `ModeloEditApplySubmissionV1` checks every scalar intent that parses as
  a Decimal against the manual-override operand: EUR, scale 2, ±999,999,999,999.99 (`operation_definitions.py:1656-1673`,
  `operation_definitions.py:1859-1872`, `operation_definitions.py:2236-2253`). A ratio of `0.125`, a decimal of `1.5775` or a text
  value such as `NaN` or `12.345` is refused with a pydantic `ValidationError` raised inside the TUI door. Binding intents are not
  checked at all.
- **Refusal detail is dropped at the operation boundary.** Only the refusal family travels (`action_errors.py:503-518`), so the
  settled operation cannot say which casilla or coordinate failed. Address-level feedback therefore has to come from an in-process
  parse and preflight before submission.
- **The edit apply blocks the event loop.** `ModeloEditApplyExecutor.execute` calls `apply_modelo_edit` synchronously inside
  `async def` (`operation_definitions.py:2377`). The calculate executor wraps the same work in `asyncio.to_thread`
  (`operation_definitions.py:427-434`).

##### 1.4 Baseline lifetime and staleness

- The baseline lives 5 minutes (`edit_admission.py:57`). It is admitted when the lifecycle door is built
  (`launcher.py:1035-1041`). Doors are built eagerly, one per declaration, while the declarations workbench is composed
  (the former source file, called from `launcher.py:970`). Any apply more than 5 minutes
  after the declarations screen was built is therefore refused as `stale_edit_baseline` with coordinate `baseline_expiry`
  (reproduced: `repro_130.out`, "expired baseline").
- The coordinates are whole-bucket digests. `work_catalogue_revision` and `calculation_catalogue_revision` hash the entire bucket
  catalogues (`edit_admission.py:245-246`, rechecked at `edit_services.py:55-58`). Calculating or editing any other declaration in the
  profile stales every open edit session. Reproduced for the same work unit: "baseline admitted before a concurrent edit" reports
  all three coordinates.
- An admission refusal becomes `edit_baseline=None` silently (`launcher.py:1083`), so no edit surface appears and no reason is
  given.
- Admission requests the default `filing`-grade snapshot (`edit_admission.py:222-226`). For a calculation-grade or
  applicability-grade revision it raises `RegistryValidationError` instead of refusing. Reproduced for 136 (calculation grade) and
  182 (applicability grade). Because doors are built eagerly (above), one such declaration may break composition of the whole
  workbench. This is inferred from reading and was not reproduced in the TUI.
- The user-facing stale message says "La declaración ha cambiado desde que se abrió ... Vuelva a abrirla y edítela de nuevo"
  (`src/cadrumo/locales/es/errors.yml:934-935`). It is wrong when the cause is expiry alone, and "reopen" throws away the user's typing.

##### 1.5 Recalculation and what changed

- A before/after diff is feasible from two `CalculationRevision`s. `casilla_values` of the previous and new head differ exactly on
  the affected casillas. Measured on 130 after setting 06=100 and then only 08=50:
  `{'06': 100.00 -> 0, '07': -100.00 -> 0.00, '08': 0 -> 50.00, '09': 0.00 -> 1.00, '11': 0.00 -> 1.00, '12': 0.00 -> 1.00}`
  (`repro_130.out`). This one diff also exposes the carry-forward loss (06 went back to 0 although the user only touched 08).
- `casilla_values` materialises `0` for manual casillas that were never supplied (rev0 lists `08: '0'` with no input). Absent, cleared
  and zero states must therefore come from `input_values_by_casilla_id` and `cleared_casilla_ids`, never from `casilla_values`.
- Resubmitting identical values returns `ModeloEditExecutionUpdatedV1` while the head does not change (duplicate content-addressed
  revision; `repro_130.out`, "identical resubmit").
- The TUI "Calculate" button submits `ModeloWorkCalculateRequest(work_unit_id, actor)` only (`lifecycle.py:86-108`). Its executor
  calls the same memoryless boundary with no caller inputs and no `detail_rows` (`operation_definitions.py:427-434`). A TUI
  recalculation therefore discards every manual value, binding override and detail row stored on the current revision. This is
  inferred from the code path and matches the measured behaviour of an empty submission.

---

#### 2. Proposed design

##### 2.1 Principles

1. **One parser, owned by the application.** Every frontend and the executor use it. A value that passes the parser passes the
   engine, because the parser calls the same validators the engine calls (`validate_registry_text_scalar`,
   `CasillaConstraints.violates` and `violates_text`, `validate_spanish_tax_id`).
2. **Locale is an entry grammar only (ADR D3/D4).** Staged values are typed and locale-free. The display re-renders them in the
   current locale. An unparsed lexeme exists only inside the focused widget.
3. **Absence means unchanged, end to end.** The next calculation always starts from the previous revision's operator layer (2.6).
4. **Never guess, never round.** Ambiguous separators, extra decimals and undeclared units are refused or flagged with a plain
   fix-it sentence.
5. **Nothing is saved until Apply.** Staged edits live in memory only (ADR D4). Apply always passes through the review.

##### 2.2 Per-type control table

"Inline" means edit in the casilla row: Enter or typing starts it, Enter stages the value, Esc reverts. "Modal" means the casilla
detail editor, which uses the same parser and adds help, origin and warnings. Every inline type can also open the modal with `e`.

| data_type | Control | Entry grammar (es/ca · hu · en) | Constraints used | Readback shown | Absent-constraint display |
|---|---|---|---|---|---|
| money | inline right-aligned field, `€` suffix | `1.234,56`, `1234,56` · `1 234,56` · `1,234.56`, `1234.56`; the other locale's mark is accepted when unambiguous; `-` allowed unless the sign rule forbids it | sign, min, max; operand ±999,999,999,999.99; scale 2 | `= 1.234,56 €` | "Importe en euros, 2 decimales" |
| decimal | inline | same grammar, no suffix, scale from registry or unbounded | sign, min, max | `= 1,5775` | "Número decimal" |
| ratio | inline, unit suffix `%` or `×` | same grammar; a `%` suffix is accepted in percent mode | min, max; unit (from lens A; inferred max 100 = percent, max 1 = fraction) | `= 21 %` or `= 0,21 (21 %)` | unit undeclared: an amber "unidad no declarada: escriba el valor tal como figura en el impreso" |
| integer | inline, digits only (`restrict`); `+`/`-` step when a max is declared | `3`; `3,0` normalises to 3; `2,5` is refused | sign, min, max (for example months 0..12) | `= 3` | "Número entero" |
| year | inline, 4 digits | `2025` | `FILING_YEAR_MIN..MAX` | `= 2025` | read-only "no editable todavía" until the engine channel exists (bug 4.3) |
| boolean | inline toggle: `Sí` / `No` / `— sin declarar`; Space cycles | `sí/no`, `yes/no`, `igen/nem`, `1/0` | — | the glyph `☑ Sí` / `☐ No` | always three states; "sin declarar" is not "No" |
| date | modal with a masked field | `dd/mm/aaaa` (es, ca), `aaaa.mm.dd` (hu), `yyyy-mm-dd` (en); ISO accepted everywhere | real calendar date | `= 31 de marzo de 2025` | read-only until a channel exists (bug 4.3) |
| text | inline; modal when `max_length` > 60 or a pattern exists | free text, trimmed | min/max length (with a counter `12/24`), pattern (hint only, never the regex) | — | "Texto libre" |
| text + enum | inline Select (radio list for 4 options or fewer) | pick from the list; typing filters | enum tokens with label keys (lens A) | label | — |
| nif | inline, upper-cased as typed | separators stripped (`B-1234567-4` -> `B12345674`) | `validate_spanish_tax_id` with `runtime_tax_id_format` | canonical NIF plus kind (NIF/NIE/CIF) | — |
| nif_iva | inline, upper-cased | `ES` + body, separators stripped | `_validate_nif_iva_string` | canonical | — |
| name | inline | 1..200 characters | — | — | "Nombre o razón social" |
| iban | modal | spaces and hyphens allowed | shape + mod-97 (`core/iban.py`) | `ES91 2100 0418 4502 0005 1332` grouped | — |
| bic | inline | 8 or 11 characters, upper-cased | ISO 9362 | — | — |
| country_code | inline autocomplete (ISO alpha-2 plus name) | `ES`; lower case is upper-cased visibly in the field | shape; enum if declared | `ES · España` | — |
| province_code | inline Select `28 · Madrid` | 2 digits or type the name | 01..52 | label | — |
| postal_code | inline, 5 digits | `28001` | shape with province prefix | `28001 (Madrid)` | — |
| municipality_code | inline, 5 digits | INE code | shape | — | — |
| ccaa_code | Select when an enum is declared, otherwise an inline 2-digit field with a note that numbering is modelo-specific (`schema_scalars.py:289-300`) | `13` | shape 01..19 | label if known | amber "código según el modelo" |
| period_code | Select limited to the modelo's periodicity | `1T`, `01`, `0A`, … | `_validate_period_code` | label "1.er trimestre" | — |

Common control rules:

- Do not use Textual `Input(type="number")`, because it hard-codes the dot. Use `restrict` with a per-locale character class,
  and parse on every change for live readback.
- Lexical errors appear on the line under the field. Focus stays in the field, the row gets a `✗` glyph, and the session bar counts
  "1 valor con error". Esc restores the last staged or committed value.
- All label, help and hint `Static`s use `markup=False`. The prototype showed `[r]` being swallowed as markup (`shots/edit-valid-120x36.svg`).
- In the modal, only the two primary actions are buttons (Cancelar, Guardar en cambios). Vaciar and Restaurar are key hints, because
  four buttons do not fit at 80 columns (`shots/edit-ambiguous-80x24.svg` truncates "Guardar en cambios").

##### 2.3 Parser API (application layer)

The public, semantically named modules, following the architecture boundaries rule (no facade, no re-export), are:

- `src/cadrumo/application/modelo/edit_value_grammar.py` defines the value-free grammar that admission projects per writable address.
- `src/cadrumo/application/modelo/edit_parsing.py` defines the parse request, the result and the pure parse function.

```python
class ModeloEditValueFamily(StrEnum):
    DECIMAL = "decimal"; INTEGER = "integer"; BOOLEAN = "boolean"; DATE = "date"; TEXT = "text"

class ModeloEditValueChannel(StrEnum):      # where the engine can take it
    DECIMAL = "decimal"; TEXT = "text"; UNAVAILABLE = "unavailable"   # year and date today

class ModeloEditRatioUnit(StrEnum):
    PERCENT = "percent"; FRACTION = "fraction"; UNDECLARED = "undeclared"

class ModeloEditChoiceV1(EditModel):
    token: str                               # stored value, never translated
    label_key: str | None                    # catalogue key when one exists (lens A)

class ModeloEditValueGrammarV1(EditModel):   # value-free: safe inside the baseline
    data_type: CasillaDataTypeValue
    family: ModeloEditValueFamily
    channel: ModeloEditValueChannel
    max_fraction_digits: int | None          # money 2; others from registry or None
    sign: CasillaSignConstraint
    minimum: Decimal | None; maximum: Decimal | None
    choices: tuple[ModeloEditChoiceV1, ...] | None
    min_length: int | None; max_length: int | None; has_pattern: bool
    ratio_unit: ModeloEditRatioUnit | None
    required: bool
    constraints_declared: bool               # drives the "sin restricciones declaradas" display

# The writable entries gain `grammar: ModeloEditValueGrammarV1`. An entry whose channel is
# UNAVAILABLE, or that is a row-field template, is projected NON-writable with a new reason
# (VALUE_CHANNEL_UNAVAILABLE, ROW_FIELD_TEMPLATE).

class ModeloEditParseRequestV1(EditModel):
    address: ModeloEditScalarAddressV1 | ModeloEditBindingAddressV1
    entry_locale: OutputLanguage
    lexeme: TransientLexeme                  # repr and serialisation redacted; excluded from model_dump

class ModeloEditParseReason(StrEnum):
    EMPTY = "empty"; NOT_A_NUMBER = "not_a_number"; AMBIGUOUS_SEPARATOR = "ambiguous_separator"
    BAD_GROUPING = "bad_grouping"; SCIENTIFIC_NOTATION = "scientific_notation"; NON_FINITE = "non_finite"
    EXPLICIT_PLUS = "explicit_plus"; TOO_MANY_DECIMALS = "too_many_decimals"; NOT_AN_INTEGER = "not_an_integer"
    NEGATIVE_NOT_ALLOWED = "negative_not_allowed"; POSITIVE_NOT_ALLOWED = "positive_not_allowed"
    BELOW_MINIMUM = "below_minimum"; ABOVE_MAXIMUM = "above_maximum"; OUT_OF_OPERAND_RANGE = "out_of_operand_range"
    NOT_A_BOOLEAN = "not_a_boolean"; NOT_A_DATE = "not_a_date"; NOT_IN_CHOICES = "not_in_choices"
    TOO_SHORT = "too_short"; TOO_LONG = "too_long"; PATTERN_MISMATCH = "pattern_mismatch"
    NIF_LENGTH = "nif_length"; NIF_LEADER = "nif_leader"; NIF_CHECKSUM = "nif_checksum"
    IBAN_SHAPE = "iban_shape"; IBAN_CHECKSUM = "iban_checksum"; INVALID_CODE = "invalid_code"
    CHANNEL_UNAVAILABLE = "channel_unavailable"

class ModeloEditParseRefusalV1(EditModel):   # joins the closed ModeloEditRefusalV1 union
    kind: Literal["parse"] = "parse"
    address: ModeloEditScalarAddressV1 | ModeloEditBindingAddressV1
    reason: ModeloEditParseReason
    message_arguments: tuple[str, ...]       # min, max, scale, choice count: never the lexeme

class ModeloEditNormalisation(StrEnum):
    FOREIGN_DECIMAL_MARK_READ = "foreign_decimal_mark_read"   # e.g. es user typed 1234.56
    SEPARATORS_REMOVED = "separators_removed"; UPPER_CASED = "upper_cased"; TRIMMED = "trimmed"

# ModeloEditParsedValueV1 (edit_models.py:504) gains `normalisations: tuple[ModeloEditNormalisation, ...]`.

def parse_modelo_edit_lexeme(
    request: ModeloEditParseRequestV1, *, baseline: ModeloEditBaselineV1, tax_id_format: SpanishTaxIdFormat,
) -> ModeloEditParseResultV1: ...
```

Reuse of existing core code:

- Numbers. A small locale lexer maps the locale's group and decimal marks to canonical form. Then
  `try_parse_canonical_decimal` (`core/decimal/grammar.py:68`) does the final parse. It already refuses scientific notation, a
  leading `+`, NaN and Infinity. The ambiguity rule is `european_thousands_reading_is_ambiguous` (`grammar.py:149`) and its
  mirror for English `1,234`. The doubly-marked logic in `coerce_finite_european_decimal` (`core/decimal/coercion.py:129-181`) shows
  how grouping is validated. Do not call the extraction contract directly: it returns `None` and cannot say why.
- Text families. Use `validate_registry_text_scalar` (`schema_scalars.py:482`), then `CasillaConstraints.violates_text`
  (`schema_surfaces.py:232`). This is exactly what the engine runs (`formula_text_inputs.py:100-111`). Map `RegistryValidationError`
  to `INVALID_CODE` and similar reasons by data type, never by message text.
- NIF. Use `validate_spanish_tax_id` (`core/identity/tax_id.py:102`) with `runtime_tax_id_format`
  (`registry/tax_id_format.py:159`). Map `IdentityError.translated_message` (`errors.identity.tax_id_invalid_length`,
  `tax_id_unrecognised_leader`, `nif_invalid_shape`, checksum) to the `NIF_*` reasons.
- IBAN. Use `normalise_iban`, `IBAN_SHAPE_RE` and `iban_mod_97` (`core/iban.py`).
- Numeric rules. Use `CasillaConstraints.violates` (`schema_surfaces.py:214`), plus the operand bound for money only.

The prototype grammar (`proto_parser.py` -> `proto_parser.out`) shows the intended behaviour:
`es '1.234,56' -> 1234.56`; `es '1.234' -> AMBIGUOUS_SEPARATOR`; `en '1,234' -> AMBIGUOUS_SEPARATOR`;
`en '1234.567' -> TOO_MANY_DECIMALS (2)`; `es '1e3' -> SCIENTIFIC_NOTATION`; `hu '12 345,00' -> 12345.00`;
`es 'sí' -> 1`; `es '31/03/2025' -> date`; the IBAN checksum is refused. The prototype refused `es '1234.56'` as bad grouping.
The spec instead accepts it with `FOREIGN_DECIMAL_MARK_READ`, because a dot followed by 2 digits cannot be a thousands group,
and the readback shows how it was read.

The executor changes, in the application layer. `_reachable_scalar_inputs` stops coercing. Instead it re-runs
`parse_modelo_edit_lexeme`'s typed half on the intent value (typed validation, no lexing), routes by `grammar.channel` (boolean to
Decimal 0/1), and returns a typed `ModeloEditExecutionNoEffectV1(ModeloEditParseRefusalV1)` instead of raising. The wire bound
(`operation_definitions.py:2236-2253`) applies only to `money` addresses, or it moves into the parser as `OUT_OF_OPERAND_RANGE`.

A preflight is also needed: `preflight_modelo_edit(submission, *, ports) -> ModeloEditPreflightResultV1` in
`edit_preflight.py`. It re-parses, re-checks the permitted surface and a baseline renewal (2.5), flags required casillas left
empty, flags overrides of source values, and flags an invalid combination (for example CLEAR on a source-fed casilla). It runs
in process, before the operation, so it can name addresses. The operation refusal cannot (`action_errors.py:503-518`).

##### 2.4 Staged session: state, dirty tracking and state machine

TUI-local, memory only. The location is the former source file.

```python
@dataclass(frozen=True)
class StagedChange:
    address_key: tuple[str, str]           # ("scalar", casilla_id) | ("binding", binding_id)
    kind: Literal["set", "clear", "restore"]  # -> SET_TYPED_VALUE | CLEAR_DECLARED_VALUE | REMOVE_OVERRIDE
    value: ModeloScalar | None             # typed, locale-free; None unless set
    before: ValueView                      # value + origin as displayed when staged (manual | source kind | computed | empty | cleared)
    displaces: Literal["none", "source", "computed", "operator"]  # drives override warnings

@dataclass
class ModeloEditSession:
    read_coordinates: ...                  # workspace consistency identity (ADR D3)
    baseline: ModeloEditBaselineV1 | None  # lazily admitted; renewed (2.5)
    changes: dict[tuple[str, str], StagedChange]
    invalid: set[tuple[str, str]]          # a widget holds an unparsed lexeme (the lexeme itself stays in the widget)
    state: SessionState
```

User-facing states simplify ADR D4. VALIDATING and READY are internal sub-steps of Review:

| State | Bar text (es) | Entered by | Leaves to |
|---|---|---|---|
| CLEAN | "Sin cambios" | open; discard all; apply settled | EDITING on first staged change |
| EDITING (D4 DIRTY) | "3 cambios sin aplicar · 1 con error" | stage, revert one | REVIEW (`R`); CLEAN when the last change is reverted |
| REVIEW (D4 VALIDATING→READY) | "Revisando 3 cambios" | `R`; blocked while `invalid` is non-empty | APPLYING (confirm); EDITING (Esc or jump to a row); STALE (renewal found a real change) |
| APPLYING (D4 SUBMITTING) | "Aplicando y recalculando…" | confirm in review | APPLIED; EDITING (typed refusal, changes kept); STALE; UNKNOWN |
| APPLIED (D4 SETTLED) | "Aplicado · revisión nueva" | UPDATED effect plus fresh read | CLEAN after the diff screen is closed |
| STALE (D4 STALE_CONFLICT) | "La declaración cambió · sus cambios siguen aquí" | renewal found different coordinates; stale refusal | REVIEW against the new base (after the user confirms each changed "Antes"); CLEAN (discard) |
| UNKNOWN | "No sabemos si se aplicó" | failed or unknown effect | CLEAN after a forced reload; staged values are shown read-only for copying by eye |

Rules:

- Dirty tracking is keyed by semantic address, never by widget id or position (ADR D2).
- Re-staging a value equal to the committed value removes the change, so it does not count as dirty.
- **Revert one**: `u` on a row, or the per-row control in the review.
- **Discard all**: `Shift+U`, with a confirmation that lists the count.
- **Unsaved-change guard**: leaving with changes (Esc, `q`, switching declaration or page) opens
  `ConfirmScreen` "Tiene 3 cambios sin aplicar" with the choices [Seguir editando] (default focus), [Revisar y aplicar] and
  [Descartar y salir] (`components/dialogs.py:28`). There is no background save (ADR D4).
- **"Changed but not applied" rows** show the staged value in place with a `✎` glyph, plus a second muted line
  "antes: 0,00 € (libro)". The row keeps its state glyph from lens B (for example missing), so both are visible.
- **Locale switch**: staged typed values re-render. A widget with an unparsed lexeme keeps it, tagged `[es]`, and blocks the
  review (ADR D4).

##### 2.5 Baseline handling (corrected)

Where each fix belongs:

| Change | Layer | Location |
|---|---|---|
| Admit lazily when the session starts (first staged change), not when the workbench is composed | TUI composition | `launcher.py:1004-1087` (door takes an `admit` callable, not a baseline); `installed_workspace.py:131-135` builds nothing eager |
| **Renewal** at review open and again just before submit: re-admit; if every coordinate except `issued_at`, `expires_at` and `baseline_id` is equal, adopt it silently. This is not a rebase, because nothing changed. | application | new `renew_modelo_edit_baseline(baseline, …) -> Renewed \| Stale(coordinates)` in `edit_admission.py` |
| Narrow the coordinates to the edited work unit: that work unit's record digest and the head it points to, instead of whole-bucket catalogue hashes | application; **amends contract D2** | `edit_admission.py:245-246`, `edit_services.py:55-60` |
| Admission refuses, and does not raise, for a sub-filing-grade revision. Request the calculation grade, as `calculate_input.py:883-893` does. | application | `edit_admission.py:222-226` |
| Admission refusal reason reaches the UI | TUI | `launcher.py:1083` keeps the refusal; the edit area shows it in plain words |

With renewal, the 5-minute lifetime stops being user-visible. The only stale case left is a real concurrent change to this
declaration. For that case, V1 of the workspace ADR allows only "review pending edits and explicit abandon-and-reload". I propose,
as a D6 amendment, **user-confirmed re-basing**: the review re-opens against the new head, and each row whose "Antes" changed is
marked `⟳ cambió mientras editaba: 0,00 € → 12,00 €`. Apply stays disabled until the user acknowledges those rows. This is not
silent and not automatic, and it keeps the user's work.

##### 2.6 Mutation semantics (corrected): carry the operator layer forward

The fix is an application-layer change that needs its own decision, because the revision schema changes.

1. `CalculationRevision` gains an **operator layer**, recorded next to the merged maps and part of the content address:
   `operator_casilla_inputs`, `operator_text_casilla_inputs` and `operator_binding_overrides` (typed, canonical strings), plus
   the existing `cleared_casilla_ids`. `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` already receives the
   caller layer separately (`calculation_actions.py:1436-1442`); it only needs to persist it
   (`calculation_actions.py:604-646`, `revision_persistence.py`). The persisted `input_values_by_casilla_id` and
   `binding_overrides` are merged across all tiers (1.3, and lens D's independent finding), so they **cannot** be replayed as the
   caller layer. Replaying them would freeze ledger, profile and borrador values as caller overrides, which outrank every source,
   and new ledger data would never show up again.
   The replayable "caller context" is wider than values. The head already stores these caller-supplied, non-source fields, and the
   next calculation must receive them again: `detail_rows` (the executor already replays these), `filing_instance_evidence` (see
   4.15), `m210_official_tipo_renta_code`, `m210_gross_income_source_mode` and `borrador_snapshot_id`, plus caller relation
   overrides once they are separated from the merged map. A single application helper, `caller_context_of(revision)`, owns this
   list, so edit and Calculate cannot drift apart.
2. `apply_modelo_edit` computes the next caller layer as the previous revision's operator layer with the intents applied:
   - SET replaces the value, and removes the address from the cleared set.
   - CLEAR removes the address from the operator layer. It adds the address to `cleared_casilla_ids` **only when no source feeds
     the casilla**. When a source feeds it, preflight refuses with "este valor procede del libro; use Restaurar", or the intent
     becomes REMOVE, as decided in open question Q2.
   - REMOVE_OVERRIDE removes the binding or casilla from the operator layer, so the profile, backend or borrador tiers win again.
     This is the entire implementation of the currently refused intent (`_edit_execution.py:249-253`).
   - An address not in the submission stays as it was, which honours contract D4.
3. The **Calculate** operation (`operation_definitions.py:427-434`) replays the current head's operator layer and `detail_rows`, so
   a TUI recalculation after new ledger data keeps the user's manual values. The CLI `modelo work calculate` keeps its
   explicit-full-specification semantics unless decided otherwise (Q3).
4. Legacy revisions have no operator layer. Load them as `operator_layer = unknown`. The first edit on such a revision shows a
   one-time notice in the review: "Las revisiones anteriores no distinguen los valores que usted escribió; revise las casillas
   manuales". Do not reconstruct the layer by guessing (no-silent-under-declaration).

The executor must also return typed refusals instead of raising `decimal.InvalidOperation` or `RegistryValidationError`, and run in
`asyncio.to_thread` (bug 4.10).

##### 2.7 Clear vs set to zero vs remove override

| User intent | How the user expresses it | Staged row shows | After apply shows | Contract intent | Available for |
|---|---|---|---|---|---|
| Set to zero | type `0` (or `0,00`), Enter | `✎ 0,00 €` · "antes: 120,00 €" | `0,00 €` with a "manual" origin tag | SET_TYPED_VALUE 0 | any writable numeric |
| Clear (remove my declared value; nothing replaces it) | `Supr` on the row, or empty the field and press Enter (the modal hint says "Vaciar") | `✎ — vaciar` with the old value struck through | `— sin valor` with a "vaciado por usted" tag (from `cleared_casilla_ids`, **not** `casilla_values`, which says 0) | CLEAR_DECLARED_VALUE | manual casillas no source feeds |
| Restore origin (stop overriding the ledger, profile, import or formula value) | `r` on the row, or "Restaurar del libro" in the modal | `✎ ↺ restaurar` · "volverá al valor del libro tras recalcular" | the recalculated source value with its source tag, highlighted in the diff | REMOVE_OVERRIDE (binding), or removal from the operator layer (casilla) | any address carrying an operator value that displaces a source or formula |
| Leave unchanged | do nothing, or `u` to undo a staged change | normal row | unchanged, **including after later edits and recalculations** | (absence) | all |

An empty field is never a silent zero. An empty boolean is "sin declarar", which is distinct from "No". The review lists clears
and restores as their own verbs, never as "0".

##### 2.8 Review screen (mandatory before apply)

Contents: every staged change with casilla number, label, before (value and origin), after, and effect in words. Override warnings
list every row that displaces a source or computed value. Preflight findings sit inline on their rows, and a global banner shows
counts. There are three actions. Apply is the primary action, but default focus is on the table so that Enter cannot fire it by accident.

120x36:

```
 Revisar cambios · Modelo 130 · 1T 2026 · Pago fraccionado IRPF                                    3 errores: 0 · avisos: 1
 5 cambios sin aplicar. Nada se guarda hasta que pulse «Aplicar y recalcular».
 ┌───────┬──────────────────────────────────────────────┬────────────────────┬──────────────────┬──────────────────────────────┐
 │Casilla│Concepto                                      │Antes               │Después           │Efecto                        │
 ├───────┼──────────────────────────────────────────────┼────────────────────┼──────────────────┼──────────────────────────────┤
 │▶06    │Retenciones e ingresos a cuenta               │0,00 € · libro      │1.234,56 €        │⚠ sustituye el valor del libro│
 │ 08    │Volumen de ingresos trimestral                │— sin valor         │50,00 €           │nuevo valor                   │
 │ 16    │Deducción adquisición vivienda habitual       │120,00 € · manual   │0,00 €            │cero declarado                │
 │ 18    │Resultados de autoliquidaciones anteriores    │35,00 € · manual    │— vaciar          │quedará sin valor             │
 │ 10    │Retenciones e ingresos a cuenta (sección II)  │10,00 € · manual    │↺ restaurar       │volverá al valor de origen    │
 └───────┴──────────────────────────────────────────────┴────────────────────┴──────────────────┴──────────────────────────────┘
 ⚠ 1 cambio sustituye un valor calculado a partir de su libro (casilla 06). Si después importa más
   facturas, su valor manual seguirá mandando hasta que pulse «Restaurar» (r).
 ℹ Tras aplicar, el modelo se recalcula y verá qué casillas cambian.

                                            [ Volver a editar ]  [ Descartar todo ]  [ Aplicar y recalcular ]
 ↑↓ mover  u deshacer este  Intro ir a la casilla  a aplicar  Esc volver  U descartar todo
```

80x24. The 5-column table does not fit (the prototype `shots/review-80x24.svg` clips at "Despu"), so this width uses a stacked
two-line record form (ADR D8 narrow layout):

```
 Revisar cambios · 130 · 1T 2026                  5 cambios · 1 aviso
 Nada se guarda hasta que pulse «Aplicar».
 ────────────────────────────────────────────────────────────────────────
▶06 Retenciones e ingresos a cuenta
     0,00 € (libro)  →  1.234,56 €                ⚠ sustituye el libro
 08 Volumen de ingresos trimestral
     — sin valor     →  50,00 €                     nuevo valor
 16 Deducción adquisición vivienda habitual
     120,00 € (manual) → 0,00 €                     cero declarado
 18 Resultados autoliquidaciones anteriores
     35,00 € (manual)  → — vaciar                   quedará sin valor
 10 Retenciones e ingresos a cuenta (sec. II)
     10,00 € (manual)  → ↺ restaurar                vuelve al origen
 ────────────────────────────────────────────────────────────────────────
 ⚠ 06 sustituye un valor calculado desde el libro.
 [Volver]  [Descartar]  [Aplicar y recalcular]
 u deshacer · Intro ir · a aplicar · Esc volver
```

The detail editor at 80x24 (prototype `shots/edit-ambiguous-80x24.svg`), trimmed to two buttons:

```
 ┌ Casilla 06 · Retenciones e ingresos a cuenta ─────────────────────┐
 │ Actual: 0,00 € · del libro (retenciones soportadas 1T 2026)      │
 │ ╭──────────────────────────────────────────────────────────╮ €   │
 │ │1.234                                                     │     │
 │ ╰──────────────────────────────────────────────────────────╯     │
 │ ✗ «1.234» puede ser mil doscientos treinta y cuatro o uno con     │
 │   234. Escriba 1234 o 1.234,00.                                   │
 │ ⚠ Sustituirá el valor calculado desde el libro.                   │
 │ Qué es: retenciones soportadas en el trimestre.                   │
 │ Dónde: certificados de retenciones de sus clientes.               │
 │ Formato: euros, 2 decimales. Sin límites declarados.              │
 │                              [ Cancelar ] [ Guardar en cambios ]  │
 │ Intro guardar · Esc cancelar · Supr vaciar · r restaurar · F1 ayuda│
 └───────────────────────────────────────────────────────────────────┘
```

##### 2.9 Apply, recalculation diff, refusal and stale flows in plain language

Flow: Review, then **Aplicar y recalcular**, then the operation modal (the existing `_start_lifecycle_action`, with no second
confirm), then the result.

Outcomes, with suggested text (es / en) and behaviour:

| Outcome (source) | Text | Behaviour |
|---|---|---|
| UPDATED, new head | "Aplicado. El modelo se ha recalculado." / "Applied. The return was recalculated." | open the **diff screen**, then CLEAN; stay on the same casilla afterwards (do not dismiss the page as `overview.py:628` does) |
| UPDATED, same head | "No había nada que cambiar: el cálculo ya tenía estos valores." | CLEAN, no diff |
| Parse or preflight refusal (in process, before submit) | on the row: "✗ Un importe admite como máximo 2 decimales. No se redondea." | EDITING, focus on the first failing row |
| Stale, expiry only | never shown (renewal) | — |
| Stale, real change | "Mientras editaba, esta declaración se recalculó (por usted en otra ventana o por un importe nuevo). Sus 5 cambios siguen aquí. Revise los valores marcados ⟳ y vuelva a aplicar." | STALE, then the re-based review |
| Unsupported intent | "Todavía no se puede restaurar esta casilla desde aquí. Quite ese cambio (u) para aplicar los demás." | EDITING, row marked |
| Refused, domain | "No se ha cambiado nada: {motivo por casilla del preflight}" | EDITING |
| Failed or unknown effect | "No sabemos si el cambio se guardó. Vamos a recargar la declaración; sus cambios se muestran abajo para que pueda comprobarlos." | UNKNOWN, then a forced fresh read |

Diff screen (feasible from the two revisions; demonstrated in 1.5). Rows come from casillas whose `casilla_values`, input maps or
cleared state differ, grouped as:

1. "Sus cambios" (the addresses in the submission).
2. "Recalculadas" (formula targets), each with its formula reference from provenance (lens B/D).
3. "Cambiaron por datos nuevos" (bound or source casillas whose value changed although the user did not touch them). Detect these
   by comparing `source_provenance` and `source_transaction_ids` between the revisions. If any exist, the screen says so explicitly,
   so the user does not attribute ledger changes to their edit.

The headline is the modelo's result casilla, taken from the registry's result or semantic role (for example 130 casilla 19):
"Resultado: 0,00 € → 1.160,23 € a ingresar". Prototype: `shots/diff-120x36.svg`. The application needs a query
`diff_calculation_revisions(before_id, after_id, *, submitted_addresses)`, which returns typed rows and the three causes. The TUI
keeps `before_id` (`lifecycle.calculation_revision_id`) and takes `after_id` from `ModeloEditApplyPublicResultV1.calculation_revision_id`.

##### 2.10 Keyboard map

Workbench casilla list (the editing surface; lens B row widget):

| Key | Action |
|---|---|
| ↑ ↓, PgUp PgDn, Home End | move between casillas |
| Enter, or start typing | inline edit (types marked inline); opens the Select or modal for the others |
| e / F2 | open the detail editor (modal) |
| Space | cycle a boolean: Sí → No → sin declarar |
| Supr / Delete | stage CLEAR |
| r | stage RESTORE ORIGIN (only on overridden rows) |
| u | undo the staged change on this row |
| Shift+U | discard all (confirm) |
| n / N | next / previous staged change |
| m | next required-missing casilla |
| x | next row with an error |
| R | open the review |
| / | search casillas |
| F1 or ? | toggle the help panel for the focused casilla |
| Esc / q | leave (guard if dirty) |
| F3 | appearance (existing) |

Inline edit: Enter stages and stays on the row. Tab stages and moves to the next editable row, Shift+Tab to the previous. Esc
reverts the field. Ctrl+Z inside the field is the Textual input undo.

Modal: Enter saves to changes, Esc cancels, Supr clears, r restores, F1 expands help.

Review: ↑ ↓ move, u undoes the selected change, Enter jumps to that casilla in the workbench (focus return by semantic address,
ADR D8), `a` or Ctrl+S applies, Esc returns to editing, Shift+U discards all.

Diff: ↑ ↓ move, Enter shows the casilla provenance, Esc closes and returns to the same casilla.

These keys do not collide with the current overview bindings (`q`, `escape`, `f3`; `overview.py:157-161`) or the profile manager
(`/`, `q`; `profile/overview.py:526-535`).

---

#### 3. Suggestions ranked by user value against effort

| # | Suggestion | User value | Effort | Layer |
|---|---|---|---|---|
| 1 | Carry the operator layer and caller context forward in edit **and** Calculate (2.6); return typed refusals; run in a thread | Critical: today a second edit or a Calculate silently resets earlier manual values and detail rows, and every 303 edit fails (4.15) | M-L (revision schema plus a decision) | application |
| 2 | Lazy admission plus baseline renewal plus work-unit-scoped coordinates (2.5) | Critical: today every apply more than 5 minutes after opening the workbench fails | S-M | application + launcher |
| 3 | Typed parser with locale grammar and fix-it messages (2.3); fix the executor channel routing (boolean, year, date) | High: Spanish users type `1.234,56`, which today makes the operation fail | M | application |
| 4 | Staged session, review screen and unsaved guard (2.4, 2.8) replacing raw inputs | High | M | TUI |
| 5 | Wire bound applied per data type (money only) | High for ratio and decimal users (14 of 71 writable 303 casillas are ratios) | S | application |
| 6 | Diff screen after recalculation (2.9) | High: answers "what did my change do?" | M | application query + TUI |
| 7 | Admission marks row-field templates and unreachable channels non-writable with reasons | Medium: removes 478 plus 360 traps (year + date) | S | application |
| 8 | REMOVE_OVERRIDE / Restore (falls out of item 1) | Medium | S after item 1 | application |
| 9 | Admission refusal visible; sub-filing grade handled | Medium | S | application + launcher |
| 10 | Ratio unit and enum label keys in the registry (lens A) | Medium | M (registry authoring) | registry |
| 11 | Preview result before apply (dry-run calculation without persistence) | Medium-high, but costly | L | application |
| 12 | Plain-language refusal catalogue (2.9) replacing "vuelva a abrirla" | Medium | S | locales |

---

#### 4. Bugs noted (not fixed)

Output lines are from `agent-c\repro_130.out` or from `repro_edit.py 714 2025 0A` unless stated otherwise.

4.1 **A second edit resets the first manual value** (contract D4 violated). 130: edit 1 `06=100` gives rev1 inputs `{'06':'100'}`.
Edit 2 `08=50` only gives rev2 inputs `{'06':'0','08':'50'}` and `casilla_values['06'] 100.00 -> 0`. Code: `_edit_execution.py:102-134`,
`calculation_actions.py:1431-1456` (memoryless), merged persistence `calculation_resolution.py:254-281`. The first value is replaced
by the backend's `0`, which the revision stores exactly as if the user had typed 0.

4.2 **TUI Calculate discards manual values, binding overrides and detail rows.** `lifecycle.py:86-108` sends no inputs;
`operation_definitions.py:427-434` calls the boundary with none and with `detail_rows=()`. Established from the code path; consistent
with 4.1 (an empty submission reproduces the reset).

4.3 **boolean, date and year manual casillas cannot be edited.** They raise a raw exception.
- 714 `declaracion-negativa='1'` raises `RegistryValidationError: text_input supplied for non-text casilla ids`.
- `identificacion.fecha-nacimiento='2025-03-31'` fails the same way.
- `identificacion.fecha-declaracion-anio='2025'` raises `RegistryValidationError` with context `data_types: year`.

Causes: the executor routes non-numeric types to text (`_edit_execution.py:86,128-133`); `year` is missing from the application
numeric set (`_registry_helpers.py:67`, check at `:334-352`); `date` has no channel. This affects 813 + 224 + 136 hydrated manual rows.

4.4 **Lexical defects on the value path.**
- `'1.234,56'` and `'1234,56'` escape as raw `decimal.InvalidOperation` from `_edit_execution.py:131`, so the operation fails
  instead of returning a typed refusal.
- `'1e3'` is accepted as 1000, which the CLI canonical grammar refuses (`calculate_input.py:670-689`).
- `'0.125'` and `'NaN'` are refused by a pydantic `ValidationError` raised by the wire model in the TUI door
  (`operation_definitions.py:2236-2253`). In the TUI this shows only "failed" (`overview.py:527-535`).
- The scale-2 bound applies to ratio, decimal and even numeric-looking text (`operation_definitions.py:1859-1872`).

4.5 **The baseline is admitted once, at workbench composition, and never renewed.** `launcher.py:1035-1041`,
`installed_workspace.py:131-135`. Expiry is reproduced ("expired baseline" gives `mismatching_coordinates: ['baseline_expiry']`).
Once stale, the same screen's Apply can never succeed (the door is frozen: `lifecycle.py:79,136`), and the message tells the user to
reopen, which loses their typing (`errors.yml:934-935`).

4.6 **Whole-bucket staleness.** `edit_admission.py:245-246` and `edit_services.py:55-58` hash the entire catalogues. Any calculation
of another declaration stales every edit session. Reproduced for the same work unit (all three coordinates mismatch). The
cross-declaration case is inferred from the hash inputs.

4.7 **Clear is recorded but has no effect when a source feeds the casilla.** 130 `CLEAR 06` gives `cleared=('06',)` while inputs
still hold `06='0'` ("edit 3b"). `cleared_casilla_ids` has no consumer besides identity. Clear markers are also not carried: after
3b, `08` is no longer in `cleared_casilla_ids`.

4.8 **Admission over-admits.** 478 row-field-template casillas are writable (`rowtmpl.py`) but refused by
`reject_row_field_template_scalar_inputs` (`calculation_actions.py:542-544`). Year and date types are admitted but unreachable (4.3).
Binding eligibility differs from the accepted amendment (`edit_admission.py:161-178`).

4.9 **Admission raises for calculation-grade or applicability-grade revisions.** 136 and 182 raise `RegistryValidationError ... cannot
satisfy the requested 'filing' snapshot authority` at `edit_admission.py:222-226`. Doors are built eagerly, so this is a probable
workbench composition failure (not reproduced in the TUI).

4.10 **The edit apply blocks the Textual event loop.** Synchronous `apply_modelo_edit` in `async execute` (`operation_definitions.py:2377`).

4.11 **The overview composes one `Input` per surface entry.** 1,981 for 100 (2025) and about 1,080 for 714
(`overview.py:184-196`, counts from `surface.py` and `small.py`). This is a performance and usability risk; I did not time it.

4.12 **Stale contract surface.** The enum carries `SET_OVERRIDE_VALUE_NOT_YET_WIRED` although SET is wired (`edit_models.py:598`,
`_edit_execution.py:238-270`). Module docstrings claim behaviour that does not exist (`_edit_execution.py:17-21`,
`edit_services.py:1-7`) or cite old module names (`_edit_services`, `_edit_models`, `_calculation_actions`).

4.13 **An identical resubmission reports UPDATED.** The head does not change; it is reproduced as "identical resubmit ... head changed
on identical resubmit: False". The UI would say "applied" for a no-op.

4.14 **Silent admission refusal.** `launcher.py:1083` maps a refusal to `edit_baseline=None`, so the edit controls just vanish.

4.15 **Every Modelo 303 edit apply fails: the M303 filing evidence is never passed.** `_execute_modelo_edit` calls the calculate
boundary without `filing_instance_evidence` (`_edit_execution.py:339-351`). For 303, the evidence validator raises
`M303FilingEvidenceError("missing")` when it is `None` (`src/cadrumo/application/modelo/m303_filing_evidence.py:74-88`). This is
established by reading and was independently reported by lens D. My end-to-end attempt (`repro_edit.py 303 2025 1T` ->
`repro_303.out`) stopped earlier, at another precondition: `ModeloIvaWalletReconciliationBlockedError`
(`iva_wallet_gate.py:253`, `no_usable_authority`, because the synthetic profile has no prior period). That also escapes as a raw
exception rather than a typed no-effect refusal. Fix: replay the head's evidence as part of the caller context (2.6). A pre-submit
preflight should surface workflow preconditions such as the IVA wallet gate as plain-language findings before the user commits to
an apply.

---

#### 5. Risks and open questions

- **Q1. Operator layer, a costly decision.** Adding persisted operator-authored maps to `CalculationRevision` changes the
  content-address inputs and a persisted schema. It needs an ADR, which could live in the new editor-workbench ADR or amend
  contract D4/D6. It also needs a forward migration story for legacy revisions ("operator layer unknown"). The alternative, deriving
  the layer by re-running sources without caller inputs and diffing, is fragile and breaks no-silent-under-declaration. I recommend
  against it.
- **Q2. What should CLEAR mean on a source-fed manual casilla (like 130 06)?** Options: (a) refuse, and tell the user to use
  Restore; (b) CLEAR also suppresses the source value, which needs an engine suppression axis and is legally risky
  (under-declaration); (c) treat it as REMOVE. I recommend (a). This needs lens A's data on which manual casillas are also source-fed.
- **Q3. Should CLI `modelo work calculate` also replay the operator layer?** That changes CLI semantics and the generated reference.
  Possibly add an opt-out flag. Out of this lens's scope; flag it for lens E.
- **Q4. User-confirmed re-basing (2.5)** amends workspace ADR D6 (V1 allows only abandon-and-reload).
- **Q5. Wire custody of values.** The 2026-09-24 proposed ADR (operand custody) may change how scalar values travel. The parser and
  session design are independent of it, but the wire bound (4.4) should be retired with it.
- **Q6. Ratio unit.** Until the registry declares a unit, percent versus fraction is inferred from `max` (100 or 1) where present.
  713 of 751 ratio casillas have no hint. There is a risk of a hundredfold error, so show the amber "unidad no declarada" note and
  the formula context.
- **Q7. Date and year channels.** Making them writable needs an engine decision on how date and year casilla inputs are represented;
  today `ddmmaaaa` would parse as a Decimal on the CLI path, which is a trap. Until then they stay non-writable with a reason.
- **Q8. Enum labels.** The 42 enum casillas carry raw tokens and no label keys. Showing tokens is honest but cold; lens A should
  propose catalogue keys per enum token.
- **Q9. Required-missing at apply time.** Should apply be blocked while required casillas are empty? I recommend a warning, not a
  block. Calculation is a draft step and verification is the gate.
- **Risk: sensitive values.** Staged values, lexemes and the diff rows are financial data. They stay in process memory and never in
  routes, notices, logs, snapshots or goldens (contract D7). The review and diff screens must use synthetic data in visual fixtures.
- **Risk: large surfaces.** Staging performance needs virtualised rows (lens B), not one widget per casilla.

---

#### 6. Overlap notes

- **Lens A (form model and editability).** I need per-address `ModeloEditValueGrammarV1` (2.3) from admission, which covers
  `required`, constraints, ratio unit, enum label keys and channel availability. A new non-writable reason is needed for row-field
  templates and unavailable channels. A "source-fed manual" flag is needed per casilla (see Q2 and 130 casilla 06, which is manual in
  the registry but fed by a backend value). Registry facts: 97% unconstrained, 42 enums, and ratio unit contradictions (1.2).
- **Lens B (row widget and states).** I add staged-state glyphs to the row vocabulary:
  - `✎` staged set
  - `✎ —` staged clear
  - `✎ ↺` staged restore
  - `✗` invalid lexeme
  - `⚠` displaces a source value
  - `⟳` base changed while editing (stale)
  - `●` changed by the last recalculation (diff highlight)

  Staged rows show value plus "antes". Absent, cleared and zero must come from input maps and cleared ids, never from
  `casilla_values` (1.5). At 80 columns, record-form rows are required.
- **Lens D (bindings and imports).** Restore origin equals REMOVE_OVERRIDE and depends on the operator layer (2.6). Binding eligibility
  differs from the accepted amendment (4.8). Displacing an imported or source value is always a review warning. The diff's third
  group ("cambiaron por datos nuevos") is where imports show up after a recalculation.
- **Lens E (whole flow).** Editing is always available in the workbench, and the session starts implicitly on the first staged change.
  Leaving is guarded. Calculate must replay the operator layer (4.2), or users will lose edits whenever they recalculate after
  importing. After apply, stay on the same declaration and casilla instead of dismissing the page (`overview.py:621-628`). Verify
  and file should refuse to start while the session is dirty.

## Sources

- `src/cadrumo/application/modelo/edit_admission.py:134-189`
- `src/cadrumo/application/modelo/edit_parsing.py`
- `src/cadrumo/application/modelo/edit_value_grammar.py`
- `src/cadrumo/application/modelo/m303_filing_evidence.py:74-88`
- `src/cadrumo/domain/calculations/registry/schema_base.py:699-700`

- `src/cadrumo/entrypoints/tui/modelo/lifecycle.py:129-169`

- `src/cadrumo/locales/en/common.yml:1943-1946`
- `src/cadrumo/locales/es/errors.yml:934-935`
