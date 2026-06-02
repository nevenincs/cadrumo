# Understanding the AEAT pipeline

## What this explanation covers

This page explains how the `aeat` tool is shaped and why it works the way it does. Read it to build a mental model of the pipeline before you use the tool. To set up a profile and run your first filing end to end, follow the [getting-started guide](../getting-started.md). For task-focused recipes - a specific import, a single modelo, a one-off repair - see the how-to guides.

`aeat` is a local-first assistant for Spanish autonomo tax work. It runs entirely on your machine. It builds, validates, and exports filings for you to file yourself with the AEAT. It never submits anything on your behalf. Live submission to the AEAT is permanently forbidden by design. The tool prepares the work; the human files outside the application. That boundary explains many of the choices that follow.

The surface divides into two top-level command families. The `config` family covers everything local to your setup: profile creation, authentication, diagnostics, and repair. The `app` family covers the actual tax work, grouped into areas:

- `overview` shows your workspace and filing calendar.
- `ledger` handles bank imports and transaction review.
- `modelo` holds the catalogue of AEAT tax forms and the work units built from them.
- `registry` holds the local AEAT reference data.
- `review` surfaces the items that need your attention.

A read-only `live` area observes AEAT data without ever writing to it. Two roots, each with one job: local setup versus operational work.

Underneath those commands runs a single conceptual flow. You set up a profile, import your bank data into the ledger, review and classify the transactions, open a tax-form work unit and calculate it, then check the result against your workspace status. That progression - profile, import, review, calculate, verify - is the pipeline this page sets out to explain. It is a way of thinking about the tool, not a fixed sequence of commands. The rest of this explanation walks through each stage and the reasoning behind it.

Across every stage, a few traits hold. Each operational command works locally and never contacts the AEAT, so exploring it has no effect on your tax account. Every command returns a structured result, and the JSON output is the precise machine contract when you want to feed results into other tools. The command line itself is a thin layer: it reads your input, calls the tax logic underneath, and renders the answer. The real work lives in the application core, which keeps the tax reasoning independent of how you happen to invoke it. If you want to look up the legal references behind a modelo while you work, the `app registry citations` surface inspects the local legal-norm corpus.

## How the pipeline works

The tool moves your tax data through one continuous chain: raw transactions become classified ledger entries, those entries become casilla values through a registry-driven calculation, and the calculation becomes a modelo you can validate, verify, and export. Every verb in this chain lives under `aeat app`. The chain ends at a local file. It never touches the AEAT portal.

### Transactions become classified ledger entries

The ledger is where your money movements enter the tool. Use `aeat app ledger add` to record a transaction, then `aeat app ledger classify` to assign it a tax category. Classification turns a bare amount into something a modelo can read: a categorized entry carries the meaning the calculation needs, not just a number and a date. Where a transaction mixes business and personal use, `aeat app ledger allocate` records the split that the calculation later applies.

Before any of this feeds a tax form, the ledger has to be ready. `aeat app ledger preflight` and `aeat app ledger check` inspect the entries for a period and report what's incomplete. This is the first half of validation, on the input side. It confirms the raw material is sound before the calculation runs.

### Ledger entries become casilla values

A modelo calculation anchors on a *work unit* - a record keyed by modelo, year, period, and revision. Create one with `aeat app modelo work create`. The key is the identity of the calculation: ask for the same four values twice and you get the same work unit back, so repeated requests never fork into duplicate drafts.

The registry is the authority behind the calculation. It defines each modelo's casillas (the numbered boxes on the official form), the bindings that say which ledger entries and profile facts feed each box, and the formulas that compute the rest. Read this authority directly with `aeat app modelo describe`, `aeat app modelo casillas`, `aeat app modelo bindings list`, and `aeat app modelo formulas`, which surfaces the legal and source references behind each value.

Running `aeat app modelo work calculate` against the work unit applies that registry definition. It pulls your classified ledger entries and profile facts through the bindings, evaluates the formulas, and produces a casilla value for every box on the form. The result is saved as a draft revision. The domain names this state `borrador` in Spanish, and each draft is identified by its own content hash. A draft is a candidate, not a finished filing. Each calculation persists a new draft, so recalculate as your inputs change and keep a history of what produced what.

### A draft becomes a verified modelo

`aeat app modelo work verify` is the formal validation gate. It checks a draft revision against the verified-complete contract: every required input present, every blocking condition cleared. If the draft passes, the tool promotes it to the state `VERIFICADO_COMPLETO` and records a structured verification report you can read with `aeat app modelo verification-report view`. If it doesn't pass, the draft stays exactly as it was, the report names the missing inputs or blocking findings, and the command exits with an error so an automated run can't mistake a refusal for success.

Verification joins the ledger-side readiness checks to the formal contract. The preflight confirmed the inputs; the verify gate confirms the assembled form. Only a revision that clears this gate is fit to leave the tool.

### A verified modelo becomes a local file

Optionally mark a verified revision as filed with `aeat app modelo work file`, which moves it to the state `PRESENTADO` and records a filing record. Filing is an internal state transition. It marks the revision as the one you intend to submit and nothing more. It does not contact AEAT and does not submit anything. Inspect the record later with `aeat app modelo filing-record view`.

The artefact you actually submit comes from `aeat app modelo export`. Export writes a verified or filed revision to a local fichero-BOE file - the official format AEAT expects - and records that the export happened. By default it picks the most recent filed (`PRESENTADO`) revision, or the most recent verified (`VERIFICADO_COMPLETO`) one if nothing is filed yet. A work unit with no verified revision can't be exported; the tool refuses and points you back to verify first. A raw draft never reaches this stage.

Every step along the chain reports through the same dual envelope: human-readable text lines for you to scan, and a typed payload for any program that consumes the output. That payload carries the casilla observations and their legal provenance, not just the flat numbers, so the *why* behind each value travels with it from the registry all the way to the export.

### Where the tool stops

The chain is build, validate, verify, and export, then it stops. The tool produces the file; it never uploads it. Live submission to AEAT is permanently outside its boundary by design. When the export is on disk, the final move is yours: you upload the fichero-BOE file to the AEAT portal yourself. Everything before that point is local, repeatable, and fully under your control.

## Why the app never files for you

The tool is built to stop short of the one action that matters most: it never submits anything to the AEAT. That is a deliberate design choice, enforced in code, not a configuration you happened to leave switched off. Understanding where that line sits, and what the tool does instead, explains most of how the pipeline behaves.

### The safety gate is permanent, not optional

Two boundaries separate the tool from the AEAT, and they behave differently.

Live writes to the AEAT are permanently refused. Any code path that would submit, mutate, or file remotely hits a single gate that always raises a typed refusal. There is no flag, environment variable, or setting that turns it on. This is the current, deliberate policy, grounded in the project's safety and legal rules; it would take a future, explicit decision to change it.

Live reads from the AEAT are also off by default, but they have a narrow opt-in. Until you set `AEAT_LIVE_TESTS_ENABLED` to `1`, the tool never contacts the AEAT, even to read. Reads stay off until you deliberately enable them. The write side has no such switch.

When live reads are enabled, the only paths that reach the AEAT are capture verbs under `aeat app live` - pulling filed declarations, notifications, expedientes, or wallet data. Every one is read-only and prints a safety preflight before it runs. No verb anywhere in the tool performs a filing or any other write to the AEAT.

### What `verify` does, and what it does not promise

`aeat app modelo work verify` checks a draft revision against the registry's verified-complete contract. On success, the revision moves to the `VERIFICADO_COMPLETO` state and the tool returns a structured report. On failure, the revision is left untouched, the report lists the missing casillas and blocking findings - each carrying its legal references and source references - and the command exits with a non-zero status.

The guarantee is narrow and worth stating plainly. `verify` confirms that the draft satisfies the registry's internal completeness contract. It does not contact the AEAT, does not file, and does not check the draft against any AEAT submission endpoint. A verified-complete revision means the tool's own rules are satisfied, not that the AEAT will accept the filing. Treat the green result as "this draft is internally consistent and complete," and nothing more.

One note to avoid confusion: `aeat app live verify` is a separate read-only audit log for NIF and VIES checks. The completeness check described here is `aeat app modelo work verify`, under the `work` subgroup.

### `file` is a local lifecycle state, not a submission

`aeat app modelo work file` reads as though it sends the return. It does not. The verb marks a verified revision as internally filed and says so in its own output, which appends a line stating that the action is internal only and does not submit to the AEAT. "Filed," in this tool, is a local lifecycle state, a record that you consider the revision final, and never a remote action.

### The hand-off boundary

Because the tool never submits, the real hand-off is an artefact you take elsewhere. `aeat app modelo export` writes a verified or filed revision to a local AEAT-compatible fichero-BOE file and records the operation, the output path, the byte size, and a SHA-256 of the file. It is local-only and never contacts the AEAT. That file is what you submit yourself, through the AEAT's own channels, outside this tool.

The closest the tool comes to confirming that the AEAT agreed with your figures is `aeat app modelo reconcile`, which compares a work unit against an AEAT justificante PDF you already obtained. It works on evidence you supply, not a live call, so reconciliation stays local. Together, export and reconcile frame the tool's role precisely: it builds, validates, and records the evidence; the filing itself stays in your hands.

## How every number cites its source

Trust in a tax calculation comes from one thing: the ability to trace every figure back to the law that produced it. The AEAT pipeline builds that traceability into every number it computes. When you calculate a draft revision, the tool does not hand you a bare amount. It hands you the amount together with the legal reference that grounds it.

That grounding travels as a three-part triple attached to each casilla:

- `legal_refs` - the BOE and AEAT legal references behind the value.
- `source_refs` - the registry provenance that records where the value came from.
- `formula_id` - the registry formula that computed the value.

These three fields originate in the modelo registry, not in the calculation code. The tool surfaces the grounding the registry declares; it never invents a legal reference. Tax semantics stay anchored to BOE and AEAT authority, never to operator preference.

Run `aeat app modelo work calculate <work_unit_id>` and the result returns in two parallel forms. A flat `casilla_values` map pairs each casilla with its value for quick human reading, led by a registry-declared result summary so the headline figure to pay or to refund sits above the full casilla dump. Modelo 100 alone carries roughly 2,235 casilla rows. Underneath the convenience view runs the contract: a typed `observations` list where each entry carries the casilla, its value, its `formula_id`, its operands, its `legal_refs`, and its `source_refs`. The flat view is for reading. The typed list is the proof.

Every casilla emits an observation, not only the computed ones. An input casilla and a bound casilla each carry `legal_refs` and `source_refs` pulled from the registry casilla definition. A casilla with no `formula_id` is not a number without provenance; it is a value whose grounding is the casilla definition rather than a formula. Nothing reaches the persisted revision stripped of its regulatory signal.

The same contract holds across the rest of the calculation surface:

- `aeat app modelo work revision <calculation_revision_id>` re-inspects a stored revision and returns the same provenance-bearing shape, so a stored revision returns the same provenance as a fresh calculation.
- `aeat app modelo formulas <modelo>` lists the registry formulas behind a modelo. The text output shows `formula_id`, target, and inputs by default, and adds the `legal_refs` and `source_refs` columns when you pass `--explain`.
- `aeat app modelo work verify <calculation_revision_id>` produces a verification report whose findings each carry `legal_refs` and `source_refs`. Even a completeness or parity refusal cites the law, rather than returning a bare error string.
- `aeat app modelo compare --year <A> --year <B> --modelo <code>` attaches `formula_id`, `legal_refs`, and `source_refs` to each year-over-year delta, drawn from the latest revision's typed observations.
- `aeat app modelo project` projects a year-end Modelo 100 from quarterly Modelo 130 filings and emits typed casilla observations carrying the same triple alongside the flat projection figures.

The maritime-exemption preview shows the contract at full strength. Its result pairs a flat projection with typed observations, and its warning surfaces the RETMAR statutory citation - Ley 47/2015, BOE-A-2015-11346 - so the operator sees the exact law behind the adjustment.

Text mode gates some of this grounding for readability: `formulas` hides the reference columns until you pass `--explain`, and `verify` prints reference lines only for findings that carry them. The JSON envelope behind `--json` does not gate anything. The typed observation list, with its `legal_refs` and `source_refs`, is always present there. The JSON is the complete contract; the text and flat views are the human-readable convenience laid over it.

This is why the operator can defend the output. Any figure traces back through its `formula_id` to a registry formula, and through its `legal_refs` to a BOE or AEAT reference. The tool builds, calculates, verifies, and exports - it never files anything with AEAT - and every number it produces returns the evidence that grounds it.

## The two-surface mental model: config and app

The `aeat` tool organizes everything you do into two top-level surfaces, and that split is the first thing worth understanding. Type `aeat config` for setup and local state. Type `aeat app` for tax work. There is no third surface, and that is a deliberate architectural rule, not an accident of the current version.

The two surfaces answer two different questions. `aeat config` answers "is this machine ready?" - it owns profile setup, authentication, the buckets that hold your local data, diagnostics, and repair. `aeat app` answers "what's my tax situation?" - it owns your overview, your ledger, the modelos you file, the registry that grounds those filings, and the review step before anything leaves your hands. You configure once and rarely; you work in the app continually. Keeping the two apart means the commands you reach for every day aren't tangled with the commands you ran once during onboarding.

Run `aeat` with no subcommand and the tool shows a landing card instead of an error. The card lists the surfaces - `config` plus the app areas (overview, ledger, modelo, review, registry) - under "Main sections," states its purpose - a local-first Spanish tax workflow for autonomos - and points you at `aeat --help`, `aeat config --help`, and `aeat app --help` for the next level of detail. The landing card is the map; the two `--help` views are the two territories.

### Why the surfaces are thin

Neither surface contains tax logic. Every command is a thin transport: it gathers your input, hands it to the application behind the tool, and renders what comes back. Validation, calculation, schema decisions, and persistence all live behind that boundary, expressed as typed records rather than loose values. This matters for how you read the rest of these docs. When a command refuses an input or revises a number, the command didn't decide that - the application did, on regulatory grounds, and the command is reporting the decision. The two surfaces are entry points into that backend, not the backend itself.

### Why the CLI speaks your language but these docs are English

The tool talks to you in the language you configure. Help text, prompts, the landing card, and error messages are all localized. Four output languages ship today: Spanish, English, Catalan, and Hungarian. A clean install with no profile and no override speaks Spanish, because the audience is Spanish autonomos and their advisors. To override the language for a single session, pass `--language` before the subcommand - for example, `aeat --language en app overview status`. An invalid value lists the accepted set.

These Explanation docs, by contrast, are written and maintained in English. The localized CLI serves the operator at the keyboard in their own language; the English docs serve a narrower, more technical reader who wants the conceptual picture and is comfortable in English.

One detail reinforces the split. The localized text is output only, and not everything the tool prints is output for a human. Run `aeat --version` and you get a bare machine line like `aeat 1.2.3`. It is left untranslated because tooling and continuous integration (CI) read it, not people. The tool draws a clean line between prose meant for you and data meant for a machine, and that same instinct separates the localized CLI from these English docs.

## How the pieces fit together

The `aeat` tool has exactly two top-level command roots, and knowing which one you're in explains almost everything about what a command does.

- `aeat config` manages local state: profiles, authentication, Google sync, and repair or diagnostics.
- `aeat app` does the operational tax work, grouped into six subgroups: overview, ledger, live, modelo, registry, and review.

Every `aeat app` command operates on the active profile bucket. Create and activate a profile before any app work, or most app verbs refuse with a message explaining that no active profile resolves. Profile creation, profile import, and `aeat config repair` are the exceptions: they run without an active profile so you can bootstrap a fresh setup.

### The pipeline, end to end

The tool follows a linear path from a blank profile to a filing artefact you submit yourself.

1. **Set up.** Create a profile with `aeat config profile create`, then configure and sign in to AEAT with `aeat config auth configure` and `aeat config auth login`. This step establishes the local state every later command reads.
2. **Work the daily ledger.** Bring transactions in with `aeat app ledger import`, then shape them with `aeat app ledger classify`, `aeat app ledger allocate`, and `aeat app ledger attach`. Check your progress with `aeat app ledger review` and `aeat app ledger status`.
3. **Run the modelo lifecycle.** Each tax form moves through a strict state progression: `aeat app modelo work create` opens a work unit for a given modelo, year, period, and revision; `aeat app modelo work calculate` persists a draft revision; `aeat app modelo work verify` checks that draft against the verified-complete contract; `aeat app modelo work file` marks the verified revision as internally filed; and `aeat app modelo export` writes a local AEAT-compatible fichero-BOE file.
4. **Read the cross-cutting views.** `aeat app overview status` shows where you stand, `aeat app review queue` surfaces what needs attention, and `aeat app registry inspect` shows the regulatory definitions behind a modelo.

### Where the tool stops

The tool builds, validates, verifies, and exports. It never submits to AEAT.

`aeat app modelo work file` only records an internal filed state - its own help says it "Does NOT submit to AEAT." `aeat app modelo export` writes a fichero-BOE file to local disk and "never contacts AEAT." You perform the actual submission outside the tool, using the exported file. This boundary is deliberate and enforced by the project's safety rules.

The one place the tool reaches out to AEAT is the `aeat app live` subgroup, and that path is read-only. Commands such as `aeat app live filed capture` read observations from AEAT into your local profile. They never file, mutate, or submit anything remotely.

### Understanding why a modelo applies

When you want to know why the tool thinks a form applies to you, run `aeat app overview explain MODELO`. It decomposes a modelo's applicability against the active profile, surfacing the applicable flag, the registry-backed rationale, and the profile facts the decision depends on. Like the rest of the overview group, it's local-only and never contacts AEAT.

### Where to go next

This section explains how the pieces relate. Two other documents take you further:

- To run the pipeline end to end, follow the [getting-started guide](../getting-started.md).
- To look up any single command - its flags, output schema, and exit codes - read the [generated CLI reference](../cli/index.rst). That reference is machine-generated from the live command tree: regenerate it when the commands change, and never hand-edit it.

Help text renders in English in the reference. The running tool honors `--language` (es, en, ca, or hu), so your terminal output can differ from the documented examples.
