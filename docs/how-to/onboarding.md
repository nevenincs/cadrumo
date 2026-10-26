# The filing journey: from bank records to a filed modelo

New to Cadrumo? This guide maps the whole journey, from your bank records to a
tax form you file yourself, and points you to the right guide at each stage.

Cadrumo prepares, checks, and exports Spanish tax forms as local files on your own
machine. It never submits anything to the Agencia Estatal de Administración
Tributaria (AEAT). You review each result, and you present the modelo yourself
through the official AEAT portal, signed with your own credentials. Preparation is
local and human-gated: the tool builds the filing, you file it.

Want the shortest concrete command path instead of the map? Follow the
[Quickstart](quickstart.md), which runs one complete example end to end. This page
is the orientation; the Quickstart and the linked guides are where the commands
live.

## The journey at a glance

A first filing moves through six stages:

1. Set up your taxpayer profile.
2. Bring in your transactions.
3. Classify each transaction.
4. Find out which modelos apply to you.
5. Confirm readiness, calculate, and check the draft.
6. Export and file at AEAT.

Each stage says what it is and why it matters, then links to the guide that
walks the commands.

## Before you begin

Install `cadrumo` and confirm it runs. See
[Install Cadrumo](../workstation-setup.md) for installation.

Every command that touches your data needs your passphrase, which protects
your encrypted local store. The tool prompts for it the first time in a
session.

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you
[choose another language](profile-setup.md#choose-the-output-language).

(stage-1---set-up-your-taxpayer-profile)=
## Stage 1: Set up your taxpayer profile

A profile holds the facts about one taxpayer that every later command reads:
identity (NIF or NIE), activity, regime, and residence. The profile decides which forms apply and how each value is computed, so it is the
foundation of every filing.

Start here: [Set up your taxpayer profile](profile-setup.md).

(stage-2---bring-in-your-transactions)=
## Stage 2: Bring in your transactions

Your tax figures come from your income and expense records. Import a bank
statement, or add rows by hand. Nothing is imported until you run an import
command.

Continue with: [Import and manage transactions](import-bank-statements.md).

(stage-3---classify-each-transaction)=
## Stage 3: Classify each transaction

An imported row has a date and an amount but no tax meaning yet. Classify each one
as business, personal, or mixed, and give business expenses a category, so the
calculation counts the right amounts.

Continue with: [Classify transactions](classify-transactions.md).

(stage-4---find-out-which-modelos-apply)=
## Stage 4: Find out which modelos apply

A modelo is a numbered AEAT form. Which ones you must file follows from your
profile facts, not from guesswork. Ask the tool for a verdict and its reasons
before you prepare anything.

Continue with: [Find out which modelos apply to you](choose-modelo.md).

(stage-5---check-readiness-calculate-and-verify)=
## Stage 5: Confirm readiness, calculate, and check the draft

Before you calculate, confirm the profile facts and transactions a form needs
are in place. Then calculate the form's values from your records, and check the
draft against the tax rules. The check is local; it does not contact AEAT.

Continue with: [Check that a filing is ready](filing-readiness.md), then [Check a draft declaration and act on the issues](verification-reports.md).

(stage-6---export-and-file-at-aeat)=
## Stage 6: Export and file at AEAT

Export the checked draft to a local file. Present the modelo yourself at the
AEAT portal, signed with your own certificate or Cl@ve. Cadrumo's Modelo 303
and Modelo 390 files carry a development software identity that AEAT won't accept, so
key the calculated box values into the portal form. For Modelo 130, import the
file if the portal offers a file import; otherwise key the values in too. Then record the filing in
Cadrumo and reconcile the AEAT receipt against your record.

Finish with: [File your modelo at the AEAT portal](file-at-aeat.md), then [Reconcile a filed modelo against its AEAT receipt](reconcile.md).

## Where to go next

- [How your records become tax figures](../explanation/from-records-to-figures.md):
  understand the transaction-to-box pipeline behind these stages.
- [Recording a filing, and why the tool never files for you](../explanation/recording-a-filing-and-the-boundary.md):
  why the tool never submits, and what "recorded as filed" means.
- [Plan your filing calendar](filing-calendar.md): see what is due and when.
- [Diagnose and repair your local setup](troubleshooting.md): if a command stops
  or the local state looks wrong.

Unfamiliar terms are defined in the {doc}`glossary </_generated/glossary>`. Before
you share command output to ask for help, remove personal tax identifiers such as
your NIF, NIE, or NII.
