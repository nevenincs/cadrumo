---
tags:
  - '#audit'
  - '#schema-driven-wizard-ux'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-schema-driven-wizard-adr]]"
  - "[[2026-05-13-wizard-ux-transcripts-audit]]"
---

# schema-driven wizard ux audit

User-roleplay UX evaluation of the redesigned `aeat config setup`
wizard. The transcripts that ground this audit live in the related
`wizard-ux-transcripts` document and were captured against current
HEAD by a context-gathering pass with the wizard sandboxed under a
temp directory, the unsecured secret-store backend, and every storage
env var redirected. The evaluation here is first-person narration as
the autónomo operator the project's north-star targets — not the
context gatherer's; the agent only captured raw terminal output.

## persona

**Carlos García López.** Forty-two. Designer freelancer based in
Madrid, autónomo since 2015. Files Modelo 130 quarterly, Modelo 303
quarterly, Modelo 390 yearly. Comfortable with Spanish tax forms;
has done his own filings through the AEAT web portal for a decade.
Has used the command line maybe a dozen times — to copy a file, to
install a package — never to drive a serious tool. Native Spanish
speaker, intermediate English. Read about `aeat` from a colleague
and is trying it for the first time on a fresh Windows laptop with
VS Code installed; his terminal of choice is the integrated terminal
in VS Code (git-bash, xterm-emulating).

Carlos's expectation walking in: the tool will guide him through
setup the same way the AEAT web portal does — one question at a
time, in Spanish, with the next step always obvious. He has half an
hour before he has to pick up his daughter from school. If the tool
makes him read English error messages or hunt for documentation, he
will close the terminal and never open it again.

## cold start — Carlos types `aeat`

He has just installed `aeat` and types the bare command. Spanish help
text renders correctly:

> `Asistente para preparar declaraciones tributarias españolas`
> `Quickstart: aeat config setup --profile-name NAME --tax-id NIF`

The root surface lists exactly two command groups, `config` and `app`,
each with a one-line Spanish description. This part of the
redesign works — Carlos knows immediately that there are two distinct
spaces: configuration vs. fiscal workspace. He does not need to
remember that `aeat init` or `aeat setup` ever existed; the surface
introduces itself cleanly.

The Quickstart line, however, is misleading. It says `--profile-name
NAME --tax-id NIF` — implying both flags are required and giving them
equal weight. Carlos may reasonably believe he must pick a profile
name. In practice `--profile-name` defaults to `default` and is
optional, while several other required flags (`--activity`) are not
mentioned. Two-and-a-half lines into his cold start, the tool has
already shown him an incomplete and slightly wrong instruction.

`aeat --version` works and emits a comprehensive package summary
("25 modelos, 14952 casillas, 1039 formulas") — that's lovely if
Carlos cares about it, but it's three full lines of registry
metadata for a `--version` call. He doesn't care; he just wanted to
know it was installed. The summary belongs behind a `--detail` flag.

## discovery — what does `aeat config` offer

He follows the quickstart. `aeat config --help` shows ten verbs in
neatly translated Spanish:

> `list, get, set, unset, setup, status, reset, auth, doctor`

This is clean. The verb taxonomy reads naturally and Carlos can
guess what each does. The verb `setup` is described as
"Ejecutar el asistente de configuración basado en esquema de forma
interactiva o usando banderas" — accurate but jargon-heavy ("basado
en esquema"). A real autónomo doesn't care about schemas; he cares
that this is "the first-time setup". The Spanish text is technically
correct but talks down from architecture rather than up from the
operator's goal.

`aeat config setup --help` is where the tone changes. The help screen
lists **42 flags**. Many are truncated by Typer's column wrapping
into illegible stubs:

> `--address-postco…`
> `--declaration-ty…`
> `--taxpayer-marit…`
> `--spouse-non-res…    --no-spouse-non…`
> `--family-descend…    --no-family-des…`

Carlos cannot copy-paste any of these flag names from his terminal.
They are presented as ellipsised tokens — there is no way to discover
the full flag without reading the source. The descriptor-driven
derivation is structurally sound (every question becomes a flag, per
ADR §D) but the rendering surface — a single Typer help screen — is
the wrong delivery medium for 42 flags. Carlos closes this help
screen disoriented; if he wanted flag-mode setup he no longer knows
what to type.

The Spanish field labels themselves are mostly correct ("Identificador
fiscal (NIF/NIE) para declaraciones") but a handful are technical
beyond an autónomo's vocabulary: "Operaciones intracomunitarias
superan 50.000 EUR" assumes Carlos knows what intracomunitario means
and where 50.000 EUR comes from; "Recargo de equivalencia" is a
specialist regime; "Bienes en el extranjero superan el umbral legal"
gives Carlos no way to know what umbral applies to his case.

## the wizard journey — `aeat config setup` interactive

This is the headline experience. Carlos types `aeat config setup` and
the wizard should walk him through identity, IVA regime, obligations,
residence, and notes.

**It does not run.** On git-bash under VS Code's integrated terminal
on Windows, the wizard exits immediately with:

> `INTERNAL: The command failed due to an unexpected internal error.`
> `detail: Found xterm-256color, while expecting a Windows console.`
> `Maybe try to run this program using "winpty" or run it in cmd.exe`
> `instead.`

The exception is `prompt_toolkit.output.win32.NoConsoleScreenBufferError`.
Carlos's reaction: he has no idea what xterm-256color or winpty mean.
He does not know that cmd.exe is a different terminal. He sees an
internal Python error and concludes the tool is broken.

This is a HIGH-severity blocker for the project's north-star
audience. Spanish autónomos who try `aeat` on Windows will, by
default, hit this. VS Code is the most popular IDE worldwide and its
integrated terminal is git-bash on Windows by default. The wizard's
interactive surface is dead for that audience until the runtime
either gracefully detects the unsupported TTY shape or wraps
questionary in a fallback Python prompter that works under any TTY.

Assuming Carlos perseveres — switches to cmd.exe and starts again —
the interactive flow is well-shaped. The transcripts show:

- Sections render with clear titles ("Identidad del perfil", "Primer
  declarante", "Cónyuge", "Unidad familiar", "IVA", "Inscripción",
  "Obligaciones", "Residencia fiscal", "Notas del operador") — this
  is real, structured progression, not a flat question list.
- Conditional questions work: when Carlos declares `declaration-type
  == 1` (individual filing), the `spouse-*` and `family-*` sections
  are skipped. This is the descriptor's `visible_when` doing real
  work and the operator sees zero questions about a spouse that
  doesn't apply.
- Defaults are visible at SELECT and CONFIRM prompts: `iva-regime`
  defaults to `GENERAL`, `tax-residence-ccaa` to `madrid`, every
  CONFIRM defaults to `false`. Carlos can press Enter through every
  question that doesn't apply to him.
- The SELECT widget renders human-readable labels alongside canonical
  tokens: "Régimen general", "Régimen simplificado", "Recargo de
  equivalencia", "Exento". He can read what each option means.

This part of the redesign actually works. If the operator can reach
the wizard at all, the prompt-by-prompt experience is calibrated for
a Spanish autónomo. But there are sharp UX edges inside the flow:

- 32 questions in one sitting is a lot. The wizard doesn't show a
  progress indicator ("question 12 of 32" or "section IVA: 3 of 5
  questions"). Carlos can't pace himself or estimate when he'll be
  done.
- The notes section's prompt — "Notas del operador (no consumidas por
  el motor)" — is technical. The parenthetical is engineering
  language leaking through; the operator doesn't care about engines.
  Better: "Notas para tu propio recuerdo (opcional)".
- The Cónyuge section asks for a `spouse-disability-grade` field with
  the prompt "Clave de discapacidad del cónyuge". Carlos has no idea
  what "clave" means in this context. The AEAT codes for disability
  are a closed set (33%, 65%, etc.) but the prompt accepts free TEXT
  and gives no example.

## quiet mode — `aeat config setup --quiet --tax-id 00000000T --activity design`

Carlos's automation-fluent colleague tries to script the setup. With
the right four flags, the command succeeds — exit 0. But it emits
**nothing to stdout** and **nothing to stderr**. Silent success.

The operator's reasonable next move is `aeat config status` to
confirm. That works:

> `profile	default`
> `tax.id	00000000T`
> `activity	design`
> `iva.regime	GENERAL`
> `tax.residence.ccaa	madrid`

Two-column tab-separated, no headers, no formatting. Functional but
joyless. A real autónomo would expect at least a confirmation
sentence: "Perfil 'default' guardado. Próximo paso: `aeat app overview`."

The bigger problem is what happens **before** setup. If Carlos types
`aeat config status` against a fresh install (before running `setup`),
he gets:

```
REFUSED: The command input failed validation.
  detail: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
  error_type: ValidationError
  original_exception: 2 validation errors for SetupAnswers
...
```

This is a HIGH-severity defect. The very first thing a real operator
would do after install is `aeat config status` to verify the tool is
healthy. They see a Pydantic ValidationError traceback in English,
referencing internal type names (`SetupAnswers`), with the suggestion
to visit `errors.pydantic.dev`. Carlos has no idea what Pydantic is.
He concludes the tool is broken or unfinished and walks away.

The expected behaviour: `aeat config status` against an empty profile
should emit a clean "No hay perfil configurado. Ejecuta
`aeat config setup` para empezar." in the operator's locale.

The same defect surfaces in scenario F5: after
`aeat config reset --scope PROFILE --yes`, `aeat config status`
reproduces the same Pydantic traceback. The reset succeeds but
leaves the operator looking at an internal error.

## validation experience — does the tool catch mistakes

Mixed. Some validation paths are strong, others are silently broken.

**Strong: SELECT enforcement at the Typer layer.** `aeat config setup
--iva-regime BOGUS ...` fails cleanly with `Invalid value for
'--iva-regime': 'BOGUS' is not one of 'GENERAL', 'SIMPLIFICADO',
'RECARGO_EQUIVALENCIA', 'EXENTO'.` — exit 2. The error is in English
("Invalid value for") rather than Spanish, but the structure is clean
and shows the valid set.

**Strong: unknown-key rejection.** `aeat config set unknown.key
any.value` and `aeat config get unknown.key` both fail with a
translated Spanish message — "Clave de configuración desconocida:
unknown.key. Ejecuta 'aeat config list' para ver las claves
disponibles." — pointing the operator at the discovery command. This
is excellent UX.

**Strong: missing-required-flags in quiet mode.** `aeat config setup
--quiet` (no flags) fails with the translated "Faltan banderas
obligatorias para el modo --quiet". Clear and helpful.

**Broken: NIF format validation.** `aeat config setup --quiet
--tax-id INVALID --name Carlos --activity design` **succeeds**. The
profile is persisted with `tax.id = INVALID`. There is no NIF format
check at the descriptor layer. A real automation pipeline could write
garbage into the encrypted profile without any warning.

**Broken: post-setup `config set` validation.** `aeat config set
tax.id NOT_A_NIF` after a clean setup **succeeds**. The descriptor's
per-question validator either isn't wired to the `config set` path or
the validator doesn't enforce NIF shape. Same blast radius: garbage
persists silently.

This is structural: the descriptor's TEXT widget for `tax-id` has no
shape validator. Either the descriptor needs a NIF format constraint
(regex / checksum) or the post-validator chain through `SetupAnswers`
needs to fire on every `config set` write. Either way, the contract
the user expected — "the wizard knows my tax ID is malformed" — is
not being honoured.

**Broken: untranslated key leaks at SELECT validation.**
`validate_widget_answer(iva_q, "BOGUS")` raises `WizardValidationError`
with the **raw translation key `wizard.errors.select_unknown`** as the
message. There is no catalogue entry for that key in any locale yaml.
This is a closure-bypass: the R9 audit broadening did not catch this
key because it isn't referenced via `tr(...)` in the entrypoint
modules — it's emitted directly by the descriptor validator. The
audit's regex-extraction over entrypoint code doesn't reach
application-layer error keys. A real operator hitting an iva-regime
typo via SDK or programmatic path sees the raw token.

## recovery experience

Three observations.

**Round-trip works.** `aeat config set tax.id 99999999R` followed by
`aeat config get tax.id` returns `99999999R`. Case-insensitive lookup
works: `aeat config set TAX.ID 11111111H` resolves to the same
canonical `tax.id` slot. The R12-era `_normalise_key` symmetry holds.

**Reset works mechanically.** `aeat config reset --scope PROFILE
--yes` reports `removed_profiles: 1` and exits 0. The state is gone.

**Reset's after-state is broken.** `aeat config status` after the
reset reproduces the Pydantic ValidationError traceback. The
operator just performed the action they were told to perform; the
tool's immediate next response is an internal-error stack dump. The
two surfaces (reset, status) do not compose into a coherent user
journey.

The expected behaviour: `aeat config reset --scope PROFILE --yes`
should emit a follow-up hint — "Perfil eliminado. Ejecuta
`aeat config setup` para reconfigurar." — and `aeat config status`
should detect the empty profile and emit the same clean
"No hay perfil configurado" message it should emit on cold start.

## locale experience

The project ships four locale catalogues: `en`, `es`, `ca`, `hu`.
The closure plan's R9 added 33 `cli.config.*` keys, and the C2 plan
added 24 `cli.archive.*` and `cli.topic.*` keys — `audit_cli_
translations()` returns `()` over 524 keys.

**Spanish (`es`) is the strongest surface.** Every help screen and
every error renders in real Spanish. Tone is consistent, vocabulary
is mostly accessible (with the engineering-jargon exceptions noted
above). For Carlos, the primary persona, this is the locale he sees
and it serves him.

**English (`en`) is a real translation, not a fallback.** Help
strings, error messages, and prompt text are all real English (often
quite good — "Spanish tax filing assistant", "Manage local
configuration and diagnostics"). A non-Spanish operator using `aeat`
in English gets a coherent experience.

**Catalan (`ca`) and Hungarian (`hu`) fall back to English.** This
is a hidden defect. The locale YAML files exist; the audit gate
passes because the keys are present; but the values for the
root-help surface render in English under both `AEAT_OUTPUT_LANGUAGE=ca`
and `AEAT_OUTPUT_LANGUAGE=hu`. The translations are placeholder copies
of the English text. Compare under `ca`:

> `Spanish tax filing assistant`
> `config  Manage local configuration and diagnostics`
> `app     Tax workspaces for ledgers, invoices, and declarations`

Identical to `en`. A Catalan operator who sets `AEAT_OUTPUT_LANGUAGE=
ca` reasonably expects Catalan; they get English. The closure plan's
parity gate verifies key presence, not translation quality. The
locale audit needs a richer assertion: for each key, the value in
`ca`/`hu` must differ from the value in `en` (or carry an explicit
"intentionally identical" marker). The current state ships untrue
locale support.

## major findings ranked by severity

### HIGH

1. **The interactive wizard cannot start under git-bash on Windows.**
   `prompt_toolkit.output.win32.NoConsoleScreenBufferError` aborts
   `aeat config setup` with no user-recovery path other than
   switching to cmd.exe. VS Code's default integrated terminal on
   Windows is git-bash. The most common installation path for the
   north-star audience hits this on first run.

2. **`aeat config status` against an empty profile leaks a Pydantic
   ValidationError traceback.** The first command a new operator
   would type after install produces an internal English error with
   a link to `errors.pydantic.dev`. Reproduces post-reset too.

3. **`--quiet` setup with `--tax-id INVALID` silently succeeds.** No
   NIF format validation on the wizard's primary identity field.
   Automation pipelines persist garbage without warning.

4. **`config set tax.id NOT_A_NIF` silently succeeds.** Same root
   cause; same blast radius for post-setup mutations.

5. **`wizard.errors.select_unknown` leaks as a raw translation key.**
   No catalogue entry; the closure's locale audit doesn't reach
   descriptor-validator error keys. Operator hits this on any SELECT
   typo through the SDK / programmatic surface.

6. **`ca` and `hu` locales fall back to English at the root help
   surface (and likely elsewhere).** Real translations are missing;
   the audit gate passes only because keys are present. Operators
   selecting these locales get a false promise.

### MEDIUM

7. **`aeat config setup --help` truncates 39 of its 42 flag names.**
   Operators cannot read or copy the flag names from the help screen.
   `--address-postco…`, `--declaration-ty…`, `--taxpayer-marit…`, etc.

8. **No success acknowledgement after `--quiet` setup.** Exit 0,
   empty stdout, empty stderr. Operators have to run a second
   command (`aeat config status`) to confirm.

9. **No "next step" guidance from `aeat config status` after a
   successful setup.** Two-column TSV of values; no pointer to
   `aeat app overview` or the natural follow-up.

10. **No progress indicator during interactive setup.** 32 questions
    in eight sections; the operator cannot pace themselves or
    estimate completion.

11. **The Quickstart line under `aeat --help` is incomplete and
    slightly misleading.** Recommends `--profile-name NAME --tax-id
    NIF` but `--profile-name` is optional and `--activity` (required)
    is missing.

12. **Engineering jargon in prompt text.** "Notas del operador (no
    consumidas por el motor)" leaks engine vocabulary; "asistente
    de configuración basado en esquema" leaks schema vocabulary;
    `taxpayer-disability-grade` prompts "Clave de discapacidad"
    without explaining what "clave" expects.

13. **`aeat --version` emits three lines of registry metadata.**
    Useful but excessive for a `--version` call. Belongs behind a
    `--detail` flag.

### LOW

14. **The Cónyuge `spouse-disability-grade` field is free TEXT but
    AEAT's disability grades are a closed code set.** Should be a
    SELECT, or at minimum should accept a controlled-vocabulary value
    with an example in the prompt.

15. **Some SELECT prompts (e.g. `taxpayer-marital-status`) render as
    free TEXT in the help surface** instead of a `click.Choice`
    constraint, because the descriptor doesn't carry choices for
    those fields. The taxonomy is closed in AEAT's spec; the
    descriptor is loose where the regulation is tight.

16. **`taxpayer-marital-status` accepts `S` as a valid token without
    explaining the alphabet.** AEAT's codes (`S` soltero, `C`
    casado, `V` viudo, etc.) are not introduced anywhere the
    operator can see.

17. **The wizard does not preview the persisted answers before
    committing.** A "Review your answers" / "¿Confirmar?" screen
    before write would catch typos before they hit the encrypted
    profile.

## recommendations for the next slice

The wizard's structural redesign is sound — descriptor-driven flags
work, conditional sections work, locale parity gates work for what
they cover, the persistence round-trip is clean. The defects above
are surface defects, not architectural ones, and most are bounded.

In rough priority order for a UX-closure slice:

- Resolve the git-bash TTY blocker first. Detect the unsupported
  console shape and either fall back to a pure-Python prompter
  (no `prompt_toolkit` dependency for the basic flow) or print a
  clean operator-facing message that tells them, in Spanish, that
  the interactive wizard needs cmd.exe / Windows Terminal and
  points them at `--quiet` mode meanwhile.
- Catch the empty-profile case in `aeat config status` and `aeat
  config reset --scope PROFILE`'s after-state and emit a clean
  translated "Sin perfil configurado" message with the next-step
  command.
- Add NIF format validation to the descriptor's `tax-id` TEXT
  widget (regex + checksum). Wire it through both quiet-mode setup
  and `config set`. Apply the same pattern to other identity fields
  where a constrained shape exists (`address.postcode`,
  `taxpayer.birth_date`).
- Add the missing `wizard.errors.select_unknown` catalogue entry in
  all four locales, and extend the locale audit to walk
  application-layer error keys (not just entrypoint-module `tr(...)`
  call sites) so the next class of leak is caught at gate time.
- Translate the `ca` and `hu` locale catalogues for real. Add an
  audit assertion: `tr(key, locale='ca')` must differ from
  `tr(key, locale='en')` for every key, or carry an explicit "this
  locale shares the English wording" allow-list. The current state
  is dishonest about locale support.
- Trim the `aeat config setup --help` surface. Group flags by
  section in the help text (Typer's `rich_help_panel` mechanism)
  and shorten the longest names so the column wrapper doesn't
  ellipsis them. Or drop the per-question flags from `--help` and
  document them through `aeat config setup --list-flags`.
- Emit a success message from quiet-mode setup. Two sentences in
  Spanish: "Perfil 'default' guardado." plus a next-step pointer.
- Rewrite the prompt strings that leak engineering vocabulary.
  "Notas del operador" → "Notas para tu propio recuerdo".
  "Asistente de configuración basado en esquema" → "Configuración
  inicial guiada". Each docstring describing what the operator does,
  not what the runtime does.
- Add a progress indicator to the interactive flow: section title +
  "pregunta N de M" at the top of each section. The descriptor
  knows the count; the prompter just needs to surface it.

## out of scope

This audit does not cover:

- The `aeat app` surfaces (overview, ledger, invoice, declaration,
  modelo, registry, archive, topic). Those are the next operator
  journey after setup completes and deserve their own UX pass.
- The `aeat config auth` subgroup — the auth-provider setup flow
  was not exercised in the transcripts. Its UX is a separate
  evaluation.
- The cryptographic envelope, recovery key, master-key bootstrap.
  Those surfaces are present but the operator's first encounter
  with them is in `aeat config auth`, not `setup`.
- The `aeat app archive export` / `import` flow which the closure
  plan moved under `aeat app` — the surface is reachable but the
  experience of round-tripping an encrypted archive was not
  exercised here.
- The Linux / macOS terminal experience. The git-bash blocker is
  Windows-specific; the wizard may run cleanly on every Unix-like
  TTY.

A focused UX-closure plan should pick up the eighteen findings here
and sequence them against the surfaces this audit could not reach.
