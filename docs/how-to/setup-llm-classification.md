# Set up LLM classification providers

Use this when `aeat app ledger classify --llm` cannot find or run your LLM
provider. `aeat` does not store LLM credentials and does not have a separate
LLM account configuration command. It runs a provider CLI that is already installed and authenticated in your
system. `aeat` does not store or manage LLM credentials itself.

## Supported providers

The classification command accepts provider names such as `claude`,
`antigravity`, and `codex`. The `antigravity` provider uses Google's `agy`
CLI, the supported successor to the retired standalone `gemini` CLI. For the
current list, run `aeat app ledger providers`.

Use one of those names in the classification command:

```bash
aeat app ledger classify --id <transaction-id> --llm claude
```

## Check what aeat can see

List provider CLIs visible on `PATH`:

```bash
aeat app ledger providers
```

This command only checks whether each provider executable is discoverable. It
does not spawn the provider and does not verify account login.

## Configure the provider outside aeat

Install the provider CLI you want to use, make sure its executable is on
`PATH`, and authenticate with that provider's own CLI or account flow. The
exact login command and data-retention settings belong to the provider, not to
`aeat`.

After changing PATH or signing in, run:

```bash
aeat app ledger providers
```

If the provider still is not listed as available, fix the CLI installation or
PATH before using `--llm`.

## Smoke-test classification

Use an existing low-risk transaction in a local test profile or a redacted
ledger:

```bash
aeat config profile status
aeat app ledger list --filter classification=NOT_YET_PROCESSED
aeat app ledger classify --id <transaction-id> --llm claude
```

A successful smoke test previews a suggestion and leaves the ledger unchanged.
If the provider CLI is installed but not authenticated, the classification
command can refuse with the provider's own error message. Complete that
provider login and retry.

Only use `--apply` after you have verified that preview works and you have
reviewed the suggestion:

```bash
aeat app ledger classify --id <transaction-id> --llm claude --apply
```

## Privacy boundary

LLM classification does not contact AEAT. It calls the selected provider CLI on
your machine. That CLI may send prompt data to the provider's cloud service,
depending on how that provider works and how your account is configured.

Treat transaction descriptions, counterparties, amounts, categories, and any
profile context in the prompt as taxpayer data. Do not use production data with
an LLM provider unless your provider setup and privacy policy permit it.

## Next steps

- [Classify transactions with an LLM](classify-with-llm.md)
- [Classify transactions](classify-transactions.md)
- [Work with Transactions](import-bank-statements.md)
