# The filing journey: from bank records to a filed modelo

New to Cadrumo? This guide maps the whole journey - from your bank records to a
tax form you file yourself - and points you to the right guide at each stage.

Cadrumo prepares, checks, and exports Spanish tax forms as local files on your own
machine. It never submits anything to the Agencia Estatal de Administración
Tributaria (AEAT). You review each result, and you upload the final file yourself
through the official AEAT portal, signed with your own credentials. Everything the
tool does is local and human-gated: it builds the filing, you file it.

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
5. Check readiness, calculate, and verify.
6. Export and file at AEAT.

Each stage below says what it is and why it matters, then links to the guide that
walks the commands.

## Before you begin

Install `cadrumo` and confirm it runs. See
[Install Cadrumo](../workstation-setup.md) for installation.

Every command that touches your data needs your master-key passphrase, which
protects your encrypted local store. The tool prompts for it the first
time in a session.

The command help, prompts, and messages render in Spanish to match the official
AEAT forms, even though these guides are in English.

## Stage 1 - Set up your taxpayer profile

A profile holds the facts about one taxpayer - identity (NIF, CIF, DNI, or NIE),
activity, regime, and residence - that every later command reads. The profile
decides which forms apply and how each value is computed, so it is the foundation
of every filing.

Start here: [Set up your taxpayer profile](profile-setup.md).

## Stage 2 - Bring in your transactions

Your tax figures come from the income and expense records in your ledger. Import a
bank statement, or add rows by hand. Nothing is imported until you run an import
command.

Continue with: [Import and manage transactions](import-bank-statements.md).

## Stage 3 - Classify each transaction

An imported row has a date and an amount but no tax meaning yet. Classify each one
as business, personal, or mixed, and give business expenses a category, so the
calculation counts the right amounts.

Continue with: [Classify transactions](classify-transactions.md).

## Stage 4 - Find out which modelos apply

A modelo is a numbered AEAT form. Which ones you must file follows from your
profile facts, not from guesswork. Ask the tool for a verdict and its reasons
before you prepare anything.

Continue with: [Find out which modelos apply to you](choose-modelo.md).

## Stage 5 - Check readiness, calculate, and verify

Before you calculate, confirm the profile facts and transactions a form needs are
in place. Then calculate the form's values from your ledger, and verify the draft
against the registry rules. Verification is a local check; it does not contact
AEAT.

Continue with: [Check that a filing is ready](filing-readiness.md), then
[Verify a draft filing and act on the findings](verification-reports.md).

## Stage 6 - Export and file at AEAT

Export the verified draft to the `.boe` file the AEAT portal accepts. Upload it
yourself at the portal, signed with your own certificate or Cl@ve, then record the
filing locally and reconcile AEAT's receipt against your record.

Finish with: [Upload your exported modelo at the AEAT portal](file-at-aeat.md),
then [How to reconcile a filed modelo against its justificante](reconcile.md).

## Where to go next

- [How your records become tax figures](../explanation/from-records-to-figures.md) -
  understand the transaction-to-box pipeline behind the stages above.
- [Recording a filing and the boundary](../explanation/recording-a-filing-and-the-boundary.md) -
  why the tool never submits, and what "filed" means locally.
- [Plan your filing calendar](filing-calendar.md) - see what is due and when.
- [Diagnose and repair your local setup](troubleshooting.md) - if a command stops
  or the local state looks wrong.

Unfamiliar terms are defined in the {doc}`glossary </_generated/glossary>`. Before
you share command output to ask for help, remove personal tax identifiers such as
your NIF, CIF, DNI, NIE, or NII.
