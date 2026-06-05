# Classify a transaction with an LLM

Classifying transactions is the heaviest part of preparing a return. An LLM can
suggest the classification for you, which you then review and accept, override,
or reject. Nothing is saved until you explicitly apply a suggestion, and a
manual decision always wins.

You need an active profile, an imported ledger (see
[Import and classify a bank statement](import-bank-statements.md)), and a local
LLM command-line tool on your `PATH` — one of `claude`, `gemini`, or `codex`.
Everything here is local; the LLM runs on your machine and the tool never
contacts the Agencia Estatal de Administración Tributaria (AEAT).

## What the LLM decides — and what it doesn't

The LLM suggests only the non-tax dimensions: the business/personal
classification (BUSINESS, PERSONAL, or MIXED) and, where it can, an expense
category. It does **not** set the regulated tax figures — the taxable base, the
IVA rate or amount, the IVA category, or the IRPF category. You still enter
those yourself (see the `--taxable-base`, `--iva-rate`, `--iva-category`, and
`--irpf-category` options on `aeat app ledger classify`).

## Check which providers are available

The LLM runs through a local provider CLI. List the ones found on your `PATH`:

```
aeat app ledger providers
```

This lists providers whose CLI is found on your `PATH`. The provider must also
be **logged in**: `providers` checks installation, not authentication. If a
provider's CLI isn't signed in, `classify --llm` refuses and shows the
provider's own message (for example, `claude CLI exited with 1: 'Not logged in
· Please run /login'`) — log in to that CLI and retry. If your provider isn't
listed at all, install its CLI or pick one that is.

## Ask the LLM for a suggestion

Run `classify` with `--llm` and a provider. This **previews** the suggestion -
the classification, the suggested category, a confidence, and the reason - and
saves nothing:

```
aeat app ledger classify --id <transaction-id> --llm claude
```

Find the transaction id with `aeat app ledger list`. Read the suggestion and
decide what to do next.

## Accept the suggestion

If the suggestion is right, apply it. This persists it with `llm:` provenance,
so the audit trail records that the decision came from a model:

```
aeat app ledger classify --id <transaction-id> --llm claude --apply
```

## Override or reject

- **Reject:** simply don't pass `--apply`. The transaction is left unchanged.
- **Override:** classify it yourself instead. A manual decision overwrites any
  prior value and stamps manual provenance:

  ```
  aeat app ledger classify --id <transaction-id> --classification BUSINESS
  ```

  Re-running `classify` at any time replaces the previous classification, so you
  can correct an applied LLM suggestion the same way.

## Where next

- [Import and classify a bank statement](import-bank-statements.md) - load the
  ledger and classify by hand or in bulk.
- [Common filing recipes](index.md) - the modelo lifecycle these classifications
  feed.
- [CLI reference](../cli/index.rst) - every classify option and exit code.
- [Diagnose and repair your local setup](troubleshooting.md) - fix local setup
  or readiness problems.
