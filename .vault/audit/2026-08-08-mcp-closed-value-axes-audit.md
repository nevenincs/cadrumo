---
tags:
  - '#audit'
  - '#mcp-closed-value-axes'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:1eee0388f3b2cdb6856fc568097f7e004a832da0529447db35407f6f5683e5b7'
related: []
---

# `mcp-closed-value-axes` audit: `Closed-value CLI axes reaching the MCP schema as bare strings`

## Scope


A census of every parameter on every MCP tool descriptor, looking for closed-value axes that reach the agent-facing JSON schema as a bare `string` instead of an `enum`. The surface is the whole `build_tool_descriptors()` output, not a sample: **308 tools, 1253 parameters, 190 already carrying an `enum`, 743 bare strings.**

The question is not "which parameters are bare strings" -- most legitimately are, because most are free-form (names, identifiers, paths, amounts, dates). The question is which bare-string parameters have a *closed* value set that a `StrEnum` in this tree already defines.

The governing decision is the `mcp-closed-value-axes` ADR; this document is the evidence behind it and the running record of what has been adjudicated.


## Findings

### An untyped CLI option degrades a surface its author never edited

The CLI rule says a Typer parameter over a closed set declares that set's enum. The rule reads as a CLI-ergonomics concern — click renders the accepted values on a parse failure — and that framing understates it.

The MCP input schema is **derived** from the click parameter type. An option annotated `str` produces `{"type": "string"}` with no `enum`, so the agent reading the tool schema is told nothing about the accepted set and must guess. Hand-parsing the token inside the handler does not repair this: the refusal arrives *after* the guess, and the schema — the only thing the agent reads before calling — stays silent. Every site found here had exactly that shape: a `str` annotation, plus a hand-rolled parser raising a localised "must be one of" error that the schema never surfaces.

The reusable point is that **the defect is invisible from the file being edited.** Nothing in the CLI module hints that a second consumer derives a contract from the annotation. `src/cadrumo/entrypoints/mcp/_input_schema.py:217` already knows this — its comment cites the architecture rule by name and unwraps Typer's `FuncParamType` to recover choices — but that knowledge lives in the schema builder, not where the annotations are written.

### Measuring it: match the description against real enum value sets

Grepping for `str`-typed options finds hundreds of legitimate free-form parameters. The discriminating signal was to collect every `StrEnum` in the package (421 of them) and flag a bare-string parameter whose **help text fully enumerates some enum's value set** — an author who lists the accepted values in prose is describing a closed axis. Over 743 bare strings this returned 7 candidates: precise enough to adjudicate by hand, and cheap because both halves are already in the process.

### Three of seven candidates were false positives, and the filter that catches them matters

Adjudication rejected three, and the rejections are the more instructive half.

**`config.profile.create --tax-id` and `config.profile.edit --tax-id`** matched `IdentityDocument` (NIF / CIF / NIE) because the help text explains which document kinds are accepted. But the parameter carries the identifier *value*, not the document *kind*. The description named an enum the parameter does not range over.

**`app.live.borrador.100.list --state`** matched `SnapshotLifecycleState` and is the substitutability trap. The option accepts `active`, `superseded`, `discarded` **and `all`** — the CLI axis is a strict superset of the enum. Promoting it would silently delete the `all` filter. This is the pre-filter the orchestration rule states: the replacement's constraint shape must be a superset of the current one, and here the relationship runs the wrong way.

A sweep that acted on its candidate list without adjudication would have shipped one broken filter and two nonsense annotations out of seven changes.

### Four confirmed sites

| command | parameter | enum | prior shape |
|---|---|---|---|
| `diagnostics.telemetry.status` | `--tier` | `TelemetryTier` | `str \| None` + `_parse_tier` |
| `diagnostics.telemetry.flush` | `--tier` | `TelemetryTier` | `str \| None` + `_parse_tier` |
| `registry.audit_oracles` | `--environment` | `OracleEnvironment` | `str`, **default already an enum member** |
| `modelo.filing_record.import` | `--evidence-kind` | `ExternalEvidenceKind` | `str` + inline `ExternalEvidenceKind(...)` |

`registry audit-oracles` is the clearest tell: the annotation said `str` while the default value was `_OracleEnvironment.PRODUCTION`. The declared type and the declared default disagreed, in one expression, and nothing failed.

### A `TYPE_CHECKING`-only import is a latent runtime break under Typer

`TelemetryTier` was imported only under `if TYPE_CHECKING:`, which is correct while the name appears solely in annotations under `from __future__ import annotations`. It stops being correct the moment Typer needs that annotation: Typer resolves parameter types at runtime via `get_type_hints()` to build the click type, so the guarded import must be promoted in the same change.

This class passes lint, passes `--collect-only`, and passes any import probe — the failure only appears when the command is actually constructed. Any retype of this shape must check whether the enum's import is real or guarded.

### Second instrument: parameter name against enum-typed model fields

The prose-matching sweep above is blind to any axis whose help text is terse. A complementary pass keys on structure instead: collect every pydantic model field in the package whose annotation is (or unions) a `StrEnum` — **315 such field names** — and flag bare-string MCP parameters sharing a name.

It has the opposite error profile: higher recall, much lower precision, because it matches on a *name* rather than a meaning. `kind` alone collides with 30 unrelated enums (`AttachmentKind`, `TransactionKind`, `VerbParamKind`, ...), and `reason`, `source`, `role` and `category` behave the same way. Those are name collisions, not findings. The two instruments are worth running together precisely because neither subsumes the other, and neither should be trusted without adjudication.

Two confirmed and fixed from this pass, both the now-familiar shape (enum default, `str` annotation, hand-parse downstream):

- **`review.queue --state`** — `ReviewState` exists, is documented as "Filter state for the review queue CLI", is already the type of the payload field, and was the option's own default via `.value`. The one place it was not used was the option annotation.
- **`app.live.borrador.100.list --state`** — the case iteration 3 deferred; see below.

### A latent mislabelling bug sitting behind the hand-parse

`_review.py` wrapped both the state parse **and** `project_review_queue(...)` in one `try`, with a single `except ValueError` raising "invalid state". Any `ValueError` raised anywhere inside the query would therefore be reported to the operator as an invalid `--state` value — naming a parameter that was in fact fine, and hiding the real fault.

Moving the parse to the Typer boundary let the whole `except ValueError` branch be deleted rather than narrowed. This is a recurring dividend of the retype: a hand-rolled parser tends to share a `try` with the work that follows it, so removing the parser removes an over-broad catch that nobody would otherwise have looked at.

### `--modelo`: 44 of 47 parameters are bare strings

The largest single gap the sweeps found, recorded here rather than actioned.

`Modelo` is the canonical identifier enum, and the registry-authority rule makes referencing modelos through it mandatory in production code. At the MCP boundary the picture inverts: **44 `--modelo` parameters expose no accepted set, and only 3 do** (`modelo.bindings.list`, `modelo.bindings.resolve`, `registry.diff_revisions`).

The three that work use an established in-tree pattern — a `click.Choice` over `[m.value for m in Modelo if m not in NON_REGISTRY_MODELOS]`, with a comment explaining that help and parse-time refusals must render even while a peer's registry authoring slice is invalid. So the technique is settled; it simply was not propagated.

**Why this was not swept mechanically.** There is no shared option alias — `--modelo` is declared inline across fifteen-plus modules — and, more importantly, the accepted set is not obviously the same for every command. A live-portal command, a calculation command and a Google-Sheets export command may each legitimately accept a different subset, and `NON_REGISTRY_MODELOS` proves the full enum is already wrong for at least some of them. Applying one Choice everywhere would be the exact failure the substitutability pre-filter exists to prevent, at 44x scale. Each site needs its accepted set adjudicated before it is pinned.

### The substitutability pre-filter has a second edge: a deliberately-open axis

This one was caught by a test run rather than by adjudication, after it had already shipped into the queued diff. It is the most useful finding in this document because the reasoning that produced it looked complete.

The pre-filter as applied so far asked: is the enum's value set a superset of what the CLI accepts? For `--modelo` on registry-resolving verbs the answer was yes — every code those verbs can act on has a registry definition — and the batch was pinned on that basis.

The answer was right about the **success** path and wrong about the **refusal** path. Two CLI guards deliberately accept codes outside the taxonomy in order to refuse them *well*:

- `guard_ceded_autonomic_modelo` (5 discovery verbs) — ITP-AJD (`600`/`620`) and ISD (`650`/`660`) are ceded autonomic taxes managed by each Comunidad Autónoma, not AEAT registry modelos. The guard raises an instructive redirect naming the ceded tax and its regional filing route.
- `guard_unsupported_work_modelo` (`modelo work create`) — the same refusal on the verb an operator actually reaches with an unhandled modelo.

A `click.Choice` refuses **before the command body runs**. Pinning replaced a legally-grounded answer telling a taxpayer which regional authority handles their tax with `'650' is not one of '036', '038', ...`. Seven tests caught it; nothing about the option declarations did.

**So the pre-filter needs both directions.** Ask not only "can the value set shrink safely" but "does anything downstream depend on receiving a value outside the set". An out-of-set value that reaches an instructive refusal is a *feature*, and it is invisible at the declaration site — the guard lives in the command body, often several call frames away.

The standing architecture rule already anticipates this: a late refusal is acceptable where it lists the accepted set, and these refusals do considerably more than list it. The error was reading "prefer the enum at the boundary" as unconditional.

**Process note.** Iteration five reported the `modelo work` surface as complete and green; its test selection (`-k "modelo_work or work_lifecycle or ..."`) never matched `test_modelo_unsupported_work_refusal.py`, so the regression sat in the queued diff for a full iteration. A `-k` filter chosen from the *names of the files being changed* systematically misses the tests named after the *behaviour* being broken. Where a change alters a parse boundary, run the owning directory rather than a name-filtered slice.

### Re-audit of every pinned axis: clean, and a third edge found in the axes NOT yet pinned

After the ceded-autonomic regression, every axis retyped across this campaign was re-checked against the failure mode, on two questions: did the deleted refusal say anything a generic "not one of" does not, and does any command body depend on receiving an out-of-set value.

**All five deleted refusal messages were purely generic.** Recovered verbatim from HEAD: `'--operation-type must be one of: {valid}'`, `'--tier must be one of: {accepted}; got {value!r}.'`, `'--evidence-kind must be one of {canonical}; got {kind}.'`, `'Invalid review state: {state}'`, `'--state must be one of: active, superseded, discarded, all.'`. Click's replacement is equal or better in every case; `Invalid review state` did not even name the accepted set, so that retype strictly improved the refusal.

**No command body guards any of these axes.** Nothing resembling `guard_ceded_autonomic_modelo` exists for operation-type, tier, environment, evidence-kind, review state or snapshot state.

**Verified empirically, not by inspection alone.** The entire `entrypoints/cli/tests` directory was run — 3007 passed, 49 failed — and then re-run with all sixteen changed source modules **and the four locale catalogues** reverted to HEAD. Reverting the catalogues matters: HEAD's code still looks up the keys this campaign deleted, so a baseline that kept the trimmed catalogues would have manufactured failures and hidden real ones. The two failure sets are **byte-identical** — 49 failures, same tests, no member on either side. Zero regressions across iterations two through six.

### The third edge: input normalisation the enum choice silently drops

Adjudicating `--ccaa` (a singleton carried since the field-name sweep) turned up a trap that is neither of the first two edges.

`CCAA` has fifteen members and **excludes País Vasco and Navarra**. Those are the foral territories, which run their own Haciendas Forales. `parse_tax_region("pais-vasco")` raises `ForalRegimeError` — *"is a foral regime outside the scope of this profile"* — a domain fact, not a typo message. That alone makes `--ccaa` a second-edge case.

But it also **normalises input**: `parse_tax_region("comunidad-valenciana")` resolves to `CCAA.COMUNIDAD_VALENCIANA` whose value is `comunidad_valenciana`. The option's own help advertises the hyphenated form. A `click.Choice` over enum values accepts only the underscored spelling, so pinning would refuse the exact example the help gives.

The same check applied backwards to this campaign's own work: three retypes dropped normalisation their hand-parsers performed — `--operation-type` lost `.upper()`, and `--tier` and `review --state` lost `.strip().lower()`. No test or shipped document depends on the looser forms, and the enum values are lowercase so ordinary typing still matches, but **only the first was disclosed when it happened**. Recorded here because a silent narrowing of accepted input is the same class of defect as a silent narrowing of accepted values, and `click.Choice(case_sensitive=False)` would restore it wherever that is wanted.

### The pre-filter, restated with all three edges

Before replacing a hand-parsed string axis with its enum, confirm all three:

1. **Value containment** — the enum's set covers every value the CLI accepts on the success path.
2. **No instructive out-of-set refusal** — nothing downstream depends on receiving a value outside the set in order to answer well. Grep the command body and what it calls for a guard; it will not be visible at the declaration site.
3. **No input normalisation** — the removed parser did not case-fold, strip, or rewrite separators. If it did, either keep that behaviour (`click.Choice(case_sensitive=False)`, or a `click_type` over the accepted spellings) or disclose the narrowing.

Edge one is a property of the type. Edges two and three are properties of the *code being deleted*, which is why reading only the annotation is not enough.

### A third instructive-refusal site, and the shape is now clearly systematic

Working the gate's `unadjudicated` list turned up the pattern a third time, in a domain nobody would have connected to the first two.

`--valuation-method` on `ledger inventory create` passes its raw token to the inventory service, which accepts values outside `ValuationMethod` in order to refuse one of them **by name and with a legal citation**: *"LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1."* Pinning the option would answer `--valuation-method lifo` with `'lifo' is not one of 'fifo', 'pmp', 'coste_medio'` — the same set, none of the reason, and no citation.

That is now three independent instances — ceded autonomic modelos (ITP-AJD, ISD), foral CCAA (País Vasco, Navarra), and LIFO inventory valuation. They share a shape: **the enum is the set the application handles, and the CLI accepts a wider set so it can explain what it does not handle and why.** In a regulated domain that is not an accident; the excluded values are precisely the ones a taxpayer is most likely to try, because they are real tax concepts that some *other* authority or regime governs.

The practical consequence: on this codebase, an enum-shaped CLI axis should be assumed to have an instructive refusal behind it until the command body has been read. The base rate is high enough that the burden of proof runs that way round.

### A drift gate caught a defect three iterations after it was introduced

`python -m dev.locales scaffold --check` reported `cli.app.modelo.formulas.modelo_help` as **extra** — present in all four catalogues, referenced by no code. The cause was in the iteration that reverted the ceded-modelo pin: the revert was applied by a regex that stripped `click_type=` from a group of `typer.Argument(...)` declarations and then restored their `help=tr(...)` keys from a list in document order. Only some of the declarations had been patched, so the restore ran off by one and the *formulas* command silently inherited the *bindings* command's help key.

Nothing else caught it. Ruff passed, the file compiled, every CLI test passed, and the MCP schema was unaffected because help text is not part of the closed value set. The only surface that could see it was the locale catalogue's own key-parity check, and only because an orphaned key is exactly what it exists to find.

**What follows.** A regex edit that consumes and re-emits a *positional* list of tokens is not a safe refactoring primitive — it silently reorders when the match set and the restore set differ. Prefer a per-site replacement keyed on the site's own surrounding text. And run the locale drift gate after any change that touches `tr()` call sites, including changes that only *move* them: it is the only check in the tree that can see a help key pointing at the wrong string.


### Applying the decision mechanically: two more pinned, one collision confirmed

With the ADR accepted, the remaining gate entries reduce to running its three checks.

**`--role` on `config provision pull|verify` — pinned.** `_resolve_role_model` did `ModelRole(role_value)` with no surrounding catch, so an unrecognised role raised a bare `ValueError` on its way to the error boundary rather than a clean refusal. Pinning is therefore a *repair*, not merely a typing change: the operator now gets the three accepted roles listed at parse time, and the resolver's signature carries the member instead of re-parsing a token it was handed.

**`--phone-state` — pinned** (recorded with the ADR as its worked example).

**`--iva-rate` (9 sites) — confirmed name-collision.** The help text settles it: *"IVA rate as a decimal, for example 0.21"*. The parameter carries a numeric rate; `IvaRate` is a rate-band taxonomy and was never the accepted input set. The name match was pure coincidence, which is exactly the false-positive class the second instrument was expected to produce.

### An inconsistency the sweep surfaced without looking for it

Reading the nine `--iva-rate` help strings side by side exposed a unit disagreement that no gate covers. Eight of them describe a **decimal fraction** — "as a decimal fraction", "as a decimal, for example 0.21". One, `ledger inventory movement add`, describes a **percentage**: *"IVA rate as a percentage"*.

Either the operator passes `0.21` to eight verbs and `21` to the ninth, or one of the ten help strings is wrong. Both readings are bad, and the second is worse in the quiet way this codebase cares about: a value entered under the wrong convention is off by a factor of a hundred, arithmetically valid, and lands in an inventory movement that feeds downstream aggregation.

Not fixed here — establishing which convention the movement path actually applies is a ledger-semantics question, not a CLI-typing one, and answering it by reading the help text would repeat the mistake this document keeps recording. Filed as a finding for whoever owns the inventory surface, with the note that the fix is either the parser or the prose, and only the code can say which.


### The `--iva-rate` unit split: two conventions, one option name, and only one of them enforced

Investigated properly rather than resolved from the help text, and the answer is neither of the two the earlier note anticipated.

**Both conventions are real, and each surface is internally correct.**

- `ledger inventory movement add` and the asset ledger take a **percentage**. The field is `Field(default=DEFAULT_IVA_GENERAL_RATE_PCT, ge=0, le=100)`, the value object computes `taxable_base * iva_rate / 100`, the docstring says "IVA rate percentage (0-100)", and the help says "in percent". Nothing here is wrong, and the default is literally `21.00`.
- `ledger add|classify|update`, the evidence verbs and the invoice verbs take a **fraction**. Help: "as a decimal, for example 0.21". The stored value is used as-is.

So the ninth help string was not the bug. The bug is that **the fraction side was unbounded**: `Transaction.iva_rate` was `Decimal | None = None` with no constraint, and no application-layer check either. `21` -- the spelling a sibling command asks for by default -- was accepted as a **2100% rate**.

**The direction matters.** An under-declaration eventually contradicts a filing and something downstream notices. A hundredfold *over*-statement produces a valid-looking return the taxpayer simply overpays, and this codebase's gates are built almost entirely against under-declaration. That is the asymmetry recorded elsewhere as "nothing watches over-payment", showing up in a concrete place.

**Fixed** with a field validator refusing a fraction above 1, and the message names the *unit* rather than the bound: `iva_rate is a decimal fraction, not a percentage: got 21. Express 21% IVA as 0.21.` A bound-shaped message ("must be <= 1") is a true statement that leaves the operator to rediscover the convention that caused the mistake.

The bound is the unit boundary of a fraction, not a rate. The highest Spanish IVA rate is 21% (LIVA arts. 90-91), so no legitimate filing approaches it and the guard never needs to move when a rate does -- which is why it stays a local constant rather than a registry lookup that would drift by filing year.

**Coverage.** The positive control runs on the rates that actually exist -- 0.21, 0.10, 0.04, 0.05, 0 -- rather than one convenient value, because a bound placed a decimal place out would still refuse `21` while quietly rejecting the superreducido band, and a refusal test alone cannot tell those apart. A boundary test pins 0.999 accepted / 1.001 refused, so widening the guard to `> 100` cannot pass unnoticed. A third test asserts the message names the unit, so the obvious later simplification to a plain `le=1` constraint cannot silently delete the explaining part. Mutation-proved by patching the constant to 100 from outside the repo: the three refusal tests red, the positive controls stay green.

**Not fixed, and deliberately.** The two conventions still share the name `--iva-rate`. Reconciling them is a ledger-semantics decision with an operator-facing rename on one side of it, and it is not this campaign's to make. The guard closes the dangerous direction on the unenforced side; the percentage side was already bounded `0..100` and cannot silently take a fraction without producing an obviously tiny cuota.


### Closing the gate list surfaced four wrong help strings, none of which any gate could see

Adjudicating the last entries pinned `--category` (both ratios verbs), `--kind` on inventory movement and on `modelo work amend`, and confirmed the third `--kind` site as a genuine collision -- `registry.manuals.rules` filters on a plain `str` with no closed set behind it, so there is nothing to declare.

The unplanned result was that **four operator-facing help strings turned out to be wrong**, and pinning fixed three of them structurally by making click render the real set:

- `--category` advertised `USAGE_RATIO_VEHICLE`. That value does not exist in any casing; the real names are `vehiculo_combustible`, `vehiculo_mantenimiento` and forty others. An operator following the example got a refusal that did not list valid values either.
- `--kind` on inventory movement advertised `(purchase, sale, adjustment)`. `MovementKind` is `opening, purchase, cogs, count` -- two advertised values do not exist and two real ones were undocumented.
- `--kind` on `modelo work amend` advertised `complementaria or sustitutiva`. The CLI parses into `CalculationRevisionAmendmentKind`, which also admits **`rectificativa`** -- a legally distinct amendment the operator was never told they could file.
- The fourth, `cli.app.modelo.formulas.modelo_help`, was this campaign's own regression, recorded earlier.

Each help string was corrected in all four catalogues as well, since the prose ships alongside the rendered choices.

**Why nothing caught these.** Every gate in this area checks *structure*: key parity, placeholder residue, envelope shape, schema enums. A help string that is well-formed, translated four ways, and simply names values that do not exist passes all of them. The only reliable check is reading the enum next to the prose, which is precisely what the three-edge adjudication forces you to do.

So the sweep's most durable output may not be the pinned axes at all. **Declaring the enum makes the accepted set derived rather than restated**, and a derived set cannot drift from the code the way a sentence can. Three of these four had been wrong for long enough to be translated into Catalan and Hungarian.

The amendment case is the one worth remembering: the omission was not cosmetic. `rectificativa` is a distinct legal instrument under LGT art. 122, the engine supports it, and the operator-facing surface said it did not exist.


### The gate list closed at zero, and `--provider` closed by *not* being pinned

Both `--provider` families are correctly bare, for different reasons, and neither ranges over the `LLMProvider` enum whose name they matched.

The `diagnostics.*` verbs filter recorded run rows by a **free-form runner label** -- the help's own examples are `claude, antigravity, codex`, none of which are `LLMProvider` members (`ANTHROPIC, OPENAI, GEMINI, LOCAL`). The set is whatever has actually run, so there is nothing closed to declare.

`config.auth.*` resolves against a **backend catalogue** that distinguishes implemented providers from reserved ones. A static `Choice` would misstate it in both directions: admitting reserved providers as valid, or hiding them from an operator who needs to know they exist but are unavailable. This is the dynamic-data exception the architecture rules already carve out.

So the axis sweep ends with every entry adjudicated: pinned where the three checks pass, exempt where they do not, and nothing left labelled "nobody has looked".

### The help-prose gate: what it took to make it not lie

The sequel gate reads help prose and checks it against the enum. Three drafts were needed, and each failure is worth recording because each would have shipped a gate that produced work rather than caught defects.

**Draft one matched any member-shaped token in the prose. Every hit was a false positive** -- English words like "non-resident" share a stem with `non_resident_irnr` without claiming to be a value. Prose is not a claim.

**Draft two read parentheticals**, distinguishing `(a, b, c)` from `(e.g. a)` and `(a, b, ...)`. That is the right discrimination, but the token pattern rejected hyphens, so `part2-deducciones-autonomicas` and `latest-draft` were silently dropped from every list and reported as omissions. Six flags, all manufactured by the detector.

**Draft three had a subtler bug and it is the one worth remembering.** The illustrative-marker pattern ended in `\b` after a literal period. Spanish and Catalan markers are `p. ej.` and `p. ex.` -- a period followed by a space -- and `\b` after a period only matches when a word character follows immediately. So every Spanish and Catalan example list was classified as an exhaustive enumeration. The gate reported four translations as defective. **They were correct; the gate was wrong.** Reading the actual catalogue strings before "fixing" them is what caught it.

The general lesson: a gate that reads *prose* inherits every quirk of the languages that prose is written in, and a regex tuned on English will mis-parse the others confidently. The corpus is four languages; the detector has to be checked against all four.

### Two real defects the gate found once it was honest

Both in Spanish, both invisible to the English-only probe used earlier:

- `--part` advertised `part2-deducciones-**autonómicas**`, accented. The real value has no accent, so an operator following the Spanish help gets a refusal -- in this application's primary language.
- `--classification` listed three values in Spanish and Catalan where English and Hungarian marked the list partial with an ellipsis. The enum has eight; the other five are system-assigned and refused by hand with their own instructive message, so listing three is right -- but only if the list says it is partial.

A fifth, found earlier in the same pass: `--manual` advertised `renta, iva, sociedades` while only `renta` and `iva` exist in the manuals tree.

**The gate reads the active locale**, which under the test runner is Spanish. That is the right single locale to check if only one is checked -- it is the language of the tax authority -- but it means an English-only defect could pass. Extending it to render all four catalogues is the obvious next step and is not done.


### Generalising the IVA-rate defect: `Invoice.retention_rate` has the same shape

The campaign's highest-severity find was an unbounded fractional field on a persisted model. That suggests a class rather than an incident, so the pivot swept every `Decimal` field whose name reads as a rate, ratio, percentage, coefficient or share, and checked which carry an upper bound.

**The instrument under-reports and it matters.** It reads `Field` metadata, so the `iva_rate` guard this campaign added -- a `field_validator` rather than a constraint -- shows as UNBOUNDED. Every hit therefore needs adjudicating rather than counting; `Transaction.business_pct` came back unbounded and turns out to be guarded by `_enforce_business_pct`.

**`Invoice.retention_rate` is the real one.** No `Field` bound, no validator on the model. What exists is a guard on *one entry path*: `application/invoices/_wizard.py` validates `0 <= value <= 1` and says why in its own docstring -- *"The upper bound catches a percentage written into this fractional field."* The author understood the failure precisely.

But the wizard is one of seven writers. `_creation.py`, `_lifecycle.py`, `_evidence_draft.py`, `review/_edit.py`, the business-invoice CLI and direct model construction all reach the field without passing through it.

So the shape is the `iva_rate` shape exactly, and slightly worse: there the guard was missing everywhere, here it exists, is correct, is commented, and five paths route around it. The value is the RIRPF art. 95 retencion rate -- `0.15` for the general 15%, `0.07` in the inicio-de-actividad window -- so `15` written where `0.15` belongs is a hundredfold error in tax withheld, on a regulated figure that reaches a filing.

**Not fixed this iteration** -- it arrived at the end of the budget, and a persisted-model constraint deserves the same treatment `iva_rate` got: a validator naming the unit rather than the bound, a positive control over the rates that actually exist (0.15 and 0.07, not one convenient value), a boundary case, and a mutation proof. The pattern is proven; only the execution is outstanding.

**A guard on one writer is not a guard.** That is the transferable form, and it is worth checking wherever a validation comment explains a unit confusion: the comment marks a place someone already understood the risk, which makes the *other* writers the interesting question.


## Recommendations

**Actioned.** All four sites now declare their enum; two hand-rolled parsers and their four-locale error keys are deleted; the `TelemetryTier` import is promoted to module scope. A parametrized gate in `entrypoints/mcp/tests/test_tools_and_dispatch.py` asserts each axis reaches the MCP schema as an `enum`, reading the expected set **from the enum itself** so adding a member cannot leave the gate asserting a stale list. Mutation-proved: all four cases red against the pre-fix source.

**Not actioned, deliberately.** `--state` on the borrador list stays a bare string. Making it honest needs a four-member type (the lifecycle states plus `all`) or a `click.Choice`, which is a design decision about whether "all" belongs in the lifecycle enum — not a mechanical retype. Recorded rather than forced.

**The generalisable procedure**, which cost minutes and is worth re-running whenever a CLI option is added:

- Enumerate the real population from `build_tool_descriptors()` rather than grepping annotations. The schema is the artefact that ships to the agent, so measure the artefact.
- Generate candidates by matching help prose against actual enum value sets. Cheap, high-precision, and it finds axes whose parameter name matches no enum name.
- **Adjudicate every candidate before touching it.** Apply the substitutability pre-filter explicitly: confirm the enum is a superset of the CLI axis, never merely overlapping.
- Check whether the enum's import is `TYPE_CHECKING`-guarded before relying on the annotation at runtime.

The residual 743-minus-4 bare strings are **not cleared** — they are unexamined by this instrument, which only sees axes whose help text happens to enumerate its values. An axis with terse help and a closed set is invisible to it. A complementary pass keying on parameter *name* against enum *field* declarations in the domain models would cover a different slice.

### Adjudicated: `all` does not join the lifecycle enum

Iteration 3 deferred `--state` on the borrador list as a design call. Resolved: **`ALL` must not become a member of `SnapshotLifecycleState`**, and the option takes a purpose-built filter enum instead.

The reasoning is about what the type means, not about convenience. `SnapshotLifecycleState` describes the state a persisted snapshot **is in**. No snapshot is ever in an "all" state. Admitting `ALL` would let a stored record claim a value meaning "no filter", and would give every exhaustive `match` over the lifecycle — there are several — a branch that cannot occur but must still be written. The filter is a different axis that happens to range over the same tokens plus one.

This is not a novel judgement: `ReviewState` in `application/review/_enums.py` is documented as "Filter state for the review queue CLI" and already carries `ALL` as a *filter* separate from the reviewed records' own state. The precedent existed; the new `SnapshotStateFilter` follows it and says so.

Because it was not ADR-worthy — an established in-tree pattern applied to a second case, not a new decision — it was implemented directly, with the rationale carried in the enum's own docstring where the next reader will meet it.

**The cost of the separation, and the gate that pays it.** Two enums over overlapping tokens can drift: adding a lifecycle state would leave no filter for it, silently making those snapshots unreachable from the CLI. A gate in `application/live/tests/test_snapshot_base.py` asserts the correspondence is **total** — every lifecycle state has a filter member, and `as_lifecycle_state()` round-trips every member — keyed on the property rather than a member count, so adding a lifecycle state reds the gate instead of quietly narrowing the operator's reach.

### Next: adjudicate `--modelo` per command

The 44 bare `--modelo` parameters are the highest-value remaining item and the one most likely to be got wrong in bulk. The work is not the retype; it is deciding, per command, which modelo subset that command actually accepts. Do it in batches by owning surface (live, modelo work, Google sync, registry), pin each batch's accepted set with the existing `click.Choice` idiom, and extend the MCP enum gate as each batch lands.

### `--modelo` batch one: the `modelo work` surface, and why the subsets really do differ

The adjudication iteration 4 called for produced a hard answer before any code changed. `Modelo`'s own docstring says non-registry members are "real codes with implementation support (lifecycle routing, **portal entries**)", and the tree bears that out: `domain/portals/_entries/portal_m037_censal_simplificada.py` ships a portal entry for the suppressed Modelo 037, which is **not** in the registry-eligible set.

So a single accepted set across all 44 sites would have been wrong, and wrong in the silent direction — `portals list --modelo 037` would have started refusing a code the application deliberately supports. The two families need different sets:

- **registry-resolving surfaces** (`modelo work`, registry introspection, calculation, export): the core taxonomy minus `NON_REGISTRY_MODELOS`, 73 codes.
- **surfaces that address retired codes** (portals, and plausibly the filed/justificante live reads): the full taxonomy. Not yet adjudicated individually.

### What landed, and the leverage that made it cheap

The `modelo work` family declares `--modelo` through one shared `Annotated` alias, `_ModeloOpt` in `_modelo_work_options.py`. Pinning that single alias fixed **19 commands at once**; `modelo.work.create` declares its own required option and was fixed alongside it, closing the surface at **23 of 47 sites carrying the accepted set, zero `modelo.work.*` left bare.**

The closure constraint the original idiom comment records is real and applies here: `work_create` is defined inside a registration function, `from __future__ import annotations` stringifies its `Annotated` metadata, and Typer re-evaluates that string in the **module's** globals. A module-level import of the shared constant satisfies it; a closure-local binding would not have been visible.

### The sweep removed a duplicate rather than creating a third

The `click.Choice` construction already existed **twice** — `_MODELO_CHOICE` in `_modelo_discovery_cli.py` and `_DIFF_MODELO_CHOICE` in `registry.py` — each with its own twenty-line rationale comment. Adding a third copy for the work family would have tripled a definition while nominally fixing an architecture defect.

Instead the constant now has one canonical home, `MODELO_CODE_CHOICE` in `_common.py`, and both prior copies import it. `rg` for the construction returns exactly one definition. The canonical comment additionally records the portal-037 carve-out, so the next author reaches for the full taxonomy where that is correct instead of discovering the exclusion by breaking a portal command.

`_common.py` documents a deliberate fast-path constraint — application-layer imports are deferred so `aeat --version` does not pull the registry parse. `Modelo` and `NON_REGISTRY_MODELOS` are core, not application, and sit beside the core imports that module already performs eagerly; the registry is not touched.

### Still open, at a clean boundary

**24 sites remain**, none of them in `modelo.work.*`: the `modelo.*` read/introspection verbs (`describe`, `casillas`, `formulas`, `compare`, `history`, `readiness`, `requires`, `aggregate`, `filing_record.*`), the four `config.google.sync.calc.*` verbs, `config.profile.preflight`, the four `app.live.*` verbs, `overview.*`, `quickfile`, and `review.queue`'s own modelo option.

The `app.live.*` four are the ones to adjudicate carefully rather than sweep: they are the most likely to legitimately need the full taxonomy, for the same reason portals do.

### The narrowing is repaired, not merely disclosed

The three retypes that dropped their parser's normalisation now carry `click_type=case_insensitive_choice(EnumClass)`, a single helper in `_common.py`. The probe that settled it is worth stating because the obvious objection turns out to be false: passing a `click_type` does **not** cost the enum annotation. The handler still receives a real member, `--tier CRASH_ONLY` and `--tier crash_only` both resolve to `TelemetryTier.CRASH_ONLY`, `bogus` is still refused, and the MCP schema still carries the closed value set — the input-schema builder's `FuncParamType` unwrap recovers the choices exactly as its own comment says it does.

So the narrowing was never a necessary cost of typing the axis; it was a side effect of reaching for the plainest form. Every previously-accepted spelling is accepted again, and nothing new is admitted — `case_sensitive=False` matches only the declared choices.

Applied to all four operation-type sites rather than only the three that regressed, because the evidence surface was already case-sensitive while the business-invoice surface was not; leaving that split would have preserved the asymmetry the original retype set out to remove.

### The portal filter takes the full taxonomy

`MODELO_CODE_CHOICE_ALL` now sits beside the registry-eligible constant and pins `app live portals list --modelo` to all 149 codes, including the suppressed `037` whose portal entry ships in the tree. It is a **second constant rather than a widening** of the first: the registry-resolving surfaces must keep refusing non-registry codes, so one constant cannot serve both, and the comment on each says which is which and why.

`justificante pull` and the `filed.*` reads stay bare. They fetch AEAT-side artefacts, so the full taxonomy is probably right, but whether a ceded code should get an instructive refusal there is a design question, and the last time this campaign answered a question like that under time pressure it shipped a regression.

### The standing gate

`entrypoints/mcp/tests/test_closed_value_axis_gate.py` detects the shape mechanically — a bare-string MCP parameter whose name matches a field some model types as a `StrEnum` — and requires every occurrence to be pinned or classified. **105 sites across 16 parameter names** currently match.

The design decisions worth recording:

- **It does not claim the tree is clean.** Most entries are `unadjudicated`, an explicit classification meaning "the shape matches and nobody has run the three checks". Labelling those `name-collision` would have been the comfortable lie; spot-checking three supposedly-obvious collisions found that `surface` hand-parses `VerifySurface(surface)` in the body and is a genuine unfixed axis. An allowlist whose entries are guesses is worse than no allowlist.
- **It gates on the property, never a tally.** Every matching site must have an entry; there is no "no more than N" ceiling to update and then stop reading.
- **Stale entries fail.** An exemption for an axis that has since been pinned reds the gate, so the list cannot only grow.
- **The collector has a positive control.** It reads `sys.modules` after the descriptors are built rather than walking every package — minutes faster, and under-collection can only miss a detection. A size assertion fails if the collector silently breaks, because a gate over an empty population passes every mutation.

Mutation-proved in both directions: removing the `surface` exemption reds with the two live sites named, and adding an exemption for an axis that is already pinned reds as stale.


### The multi-locale extension is not cheap, and the earlier estimate was wrong

The help-prose gate reads one locale, and extending it to four was recommended as an obvious cheap follow-up. Measuring it retracts that.

Three approaches were tried. **Re-rendering per locale** does not work in-process: help text is baked into the `Annotated` metadata when the module imports, so a locale switch afterwards changes nothing, and honouring it needs four subprocess builds of the whole CLI tree.

**Anchoring on the description to recover the locale key** is worse than slow, it is unstable: the same descriptor renders English under a plain interpreter and Spanish under the test runner, so the reverse index has to be built against whichever catalogue happens to be active. That instability is itself worth recording -- the existing single-locale gate's verdict depends on the runner.

**Comparing parentheticals across catalogues directly**, which needs no enum at all, produces **229 token mismatches**, and the sample is dominated by correct translations: `YYYY` becomes `AAAA`, `alpha-2` becomes `alfa-2`. A date placeholder and an enum value are both bare tokens inside a parenthetical, and only the second must survive translation untouched. Nothing in the string distinguishes them.

So the check needs the enum association after all, and getting it without importing four times means statically mapping each `tr("<key>")` back to the enum-typed option that uses it. That is a real piece of work, not a follow-up line item, and it is **not done**.

The hedge-marker half is separable and nearly clean: comparing only the presence of `...`/`etc` across catalogues gives **two** mismatches, both Hungarian carrying a hedge English lacks. That half would catch the `classification` defect this campaign fixed and could ship on its own.

### `collect_unhandled_source_diagnostics`: the deferral is resolved, and executing it would have been wrong

Carried since the campaign's first iteration as "same string-downgrade pattern, persisted field, wide ripple, needs a full iteration". Re-read at HEAD before planning the change, and the premise no longer holds.

**The collector is live.** It is called from `application/modelo/_calculation_source_staging.py`, which `_calculation_actions.py` imports -- the calculate path the aggregation rule requires it to run on. The "built but switched off" condition that made it a finding is gone.

**The typed field already exists.** `CalculationSourceDiagnostic` carries `binding_source: BindingSourceKind | None` beside `source_kind: str`, documented as "canonical binding source when `source_kind` names one; `None` for advisory categories".

And that documentation is the reason the originally-planned fix would have been a defect. **`source_kind` is deliberately a superset**: it holds binding source kinds *and* advisory category labels that are not `BindingSourceKind` members. Re-typing it to the enum would have refused the advisory rows the collector exists to emit -- the same substitutability failure that produced this campaign's one shipped regression, this time on a persisted field.

Closed as already-addressed. The lesson is the one the orchestration rules already state and this campaign keeps re-earning: **a finding's facts survive, its conclusion does not.** Fourteen iterations of drift separated the deferral from the plan, and the check that caught it cost one file read.


### The fractional-field thread is closed, and the reason is the instrument

Three iterations went into measuring this class. The outcome is one confirmed, fixed and shipped defect (`Transaction.iva_rate`, the 2100% rate) and one confidently wrong finding (`Invoice.retention_rate`, already guarded). The deciding factor for stopping is not the yield, it is that **no instrument built here could be validated.**

Three were tried. **Static `Field` metadata** cannot see a guard written as a validator, which is how the wrong finding happened -- and the blind spot was *documented* one iteration before it was walked into. **A name-based validator search** misses a guard that lives in a `model_validator` covering several fields, which is exactly where the real one lived. **A differential behavioural probe** -- construct with `0.15`, then `15`, and only credit a model that accepts the first -- cannot lie, and that is precisely why it reported inconclusive for 84 of 96 fields including all three cases whose answer is known.

Adding a recursive minimal-instance builder moved coverage to 36 of 96 and left the three controls **still inconclusive**: those models carry cross-field arithmetic validators, so no instance assembled from field types alone satisfies them. An instrument that cannot answer for the cases whose answer you know cannot be trusted for the cases you do not.

So the 32 fields it now calls unguarded stay **observations, not findings**. They cluster in patch, draft, command and suggestion models -- carriers that feed guarded domain records -- which is consistent with correct defence-in-depth placement, and asserting that without tracing each apply path is the same move that produced the wrong finding.

**What would actually settle it** is not a better detector but a different question: instead of asking each model whether it refuses, ask each *durable persistence boundary* whether a percentage survives a save-and-load round trip. That reuses the roundtrip fixtures the quality rules already mandate, which are built by hand and satisfy the cross-field validators the synthetic builder cannot. It is a larger piece of work and belongs to whoever owns those boundaries.

The transferable part is the stopping rule. **Three instruments, each honest about a different thing, none validatable against known ground truth -- that is the signal to stop measuring and pivot**, rather than the sense that one more variation might work.

