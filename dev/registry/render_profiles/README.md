# Render profiles

Hand-written answers to formatting questions that AEAT's official record
designs leave open, so that Cadrumo writes every field of an exported tax-return
file with the right characters.

## The problem

AEAT publishes a record design (*diseño de registro*) for each modelo: a
workbook that lists every field of the export file with its position, width and
type. The registry pipeline reads these designs and generates each modelo's
export layout from them.

The designs often say "17 positions, numeric" and stop there. That is not
enough to write the field correctly:

- **Decimals.** Does the field carry cents? With two implied decimals,
  1234.56 is written `00000000000123456`; without them it is
  `00000000000001235`. Guessing wrong makes an amount 100 times too large or too
  small.
- **Sign.** Can the value be negative, and if so is the minus written as a
  leading `N`, a blank, or not at all?
- **Meaning of a short number.** Is a four-digit field a year, a count or a
  code?
- **Fixed values.** A 303 *Tipo %* slot holding `00400` means 4.00 %, read at
  two decimal places.
- **Obsolete choices.** Older designs (156, 180, 181, 193) ask whether the file
  travels on cartridge (`C`), diskette (`D`) or telematically (`T`). Cadrumo's
  exports are always telematic, so the answer is `T`.

A wrong guess produces a file that looks valid but carries the wrong amounts,
so these answers are reviewed by a person and written down here instead of
being inferred.

## Who uses this folder

- **Developers authoring the registry** (adding a modelo or a new year's
  design) write and review these files.
- **The registry build pipeline** (`dev/registry/pipeline/render_profile.py`
  and the `render_profile_*` modules beside it) loads the folder for the modelo
  and design being built, checks it against the design, and uses the rules to
  set each field's width, decimals, padding and sign in the generated export
  layout. That layout is what the published registry, and therefore the
  installed application, uses.
- **The export verification checks** (`dev/registry/pipeline/render_check.py`,
  `dev/registry/filing_export_generated_verification.py`) confirm that the
  generated exports follow these rules.

The installed application never reads this folder. It is development input,
like the rest of `dev/registry/`.

## Layout

```
modelo_303/                              one folder per modelo
  2025/                                  one folder per design version ("design epoch")
    0001-numeric-representation.toml     one file per batch of related rules
    0002-literal-rates.toml
```

The design-version folder is named after the year the design took effect.
Where AEAT replaced a design within a year, a suffix tells the two apart
(`2024-early`, `2024-late`, `2026-late`).

Files are loaded in name order. The name is `NNNN-<topic>[-NNN].toml`:

- `NNNN` is the file's position in the folder (its load order).
- `<topic>` says what kind of rule the file holds (see the table below).
- the optional `-NNN` numbers several files of the same topic.

The `fragment_id` inside each file must equal its file name without `.toml`.

## What one file contains

```toml
[design_identity]
modelo = "111"
design_epoch = "2019"
source_ref = "aeat-dr-111-2019-v18"
source_sha256 = "5f65…"          # fingerprint of the exact AEAT design reviewed

[[singleton_rules]]
integer_digits = 8               # the answer: 8 digits,
decimal_digits = 0               # no decimals,
sign_policy = "unsigned"         # never negative

[singleton_rules.anchor]         # which field: sheet, row, cell, position
sheet = "dr M11101"
source_row = 17
ordinal = "12"

[singleton_rules.evidence]       # why
decision_id = "m111-2019-field-12-integer"
decision_statement = "The number of recipients is an unsigned integer."
justification = "The official description names a count of perceptores …"
```

Every rule therefore says **which field** it covers, **what the answer is** and
**why**, in words a reviewer can check against the official design.

`source_sha256` ties the file to one exact AEAT workbook. If the design file
changes, the fingerprint no longer matches and the build stops until someone
reviews the rules again.

## Topics

The topic vocabulary is closed. Using a new topic means adding it to this table
in the same change.

| Topic | What its rules answer |
| --- | --- |
| `numeric-representation` | General number formatting for one modelo and design: years, counts, amounts and codes. Used where no width-17 group applies. |
| `width17-num` | The 17-position amount fields of AEAT type `Num`. Many fields share one rule (for example 15 integer digits, 2 decimals, unsigned), so a rule lists all the fields it covers. |
| `width17-n` | The 17-position amount fields of AEAT type `N`, which write a negative value with a leading `N`. Kept apart from `width17-num` because the two groups have different sign rules. |
| `singletons` | Single numeric fields that belong to no group. |
| `signed-composite` | Amounts that the design writes as one sign character (blank or `N`) followed by the unsigned number. Each rule is checked against the design's own sign and layout wording. |
| `identifier-digits` | How many digits an identifier field holds (Modelo 210). |
| `literal-rates` | Fixed numbers printed in the design, such as the 303 *Tipo %* constants (`00400` = 4 %). These rules set how the number is written. They do not decide which tax rate applies. |
| `telematic-transport` | Selecting `T` (telematic transmission) where an old design still lists cartridge and diskette codes. The rule repeats the design's exact wording so that a changed design is noticed. |
| `alphanumeric-text` | The design's own rule for its alphanumeric and alphabetic fields, such as "en mayúsculas, sin caracteres especiales y sin vocales acentuadas". The rule repeats the design's sentence, the build checks that the design text contains it, and every record of the generated layout then declares it. At most one per design. |
| `source-complete` | The design states every formatting fact itself, so there is nothing to answer. The file holds no rules, only `empty_rule_assertion`, as a record that this was checked. |

One file, `modelo_200/2025/0129-width17-num-068-no-cumplimentar.toml`, adds a
description after the counter. Its comment explains why those six "no
cumplimentar" positions still need a width-17 rule.

## Which fields need a rule

A rule exists only to fill a gap in the design. For each design the pipeline
works out the set of fields whose formatting the design leaves open, and it
requires the profile to cover exactly that set:

- a field in the set with no rule is refused as **missing**;
- a rule for a field outside the set is refused as **unknown**.

Both errors name the field, so the message tells you which side is wrong.

For workbook designs the test is the field's content (*Contenido*) cell. If
the cell is blank, the design said nothing about formatting and the field needs
a rule here. If it holds any text, the pipeline takes the formatting from the
design and a rule here is refused.

**A footnote reference counts as text.** A content cell that reads only
`Nota 4.` puts the field outside this folder's reach, even when the note is
about whether the field applies rather than how it is written. If a rule you
expected to be accepted is refused as unknown, look at the field's content cell
first.

This has real effects. One amount field in a design currently in force is
written without decimals while five identical neighbouring fields carry cents,
because its content cell holds only a footnote reference. On 2026-09-02, 183
numeric fields across all designs were in that position. Almost all are still
written correctly, because the generator falls back on the design's type
column. Treat that number as a dated measurement, not a live count: no
maintained check recomputes it.
