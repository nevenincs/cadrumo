# Set up LLM classification providers

Use this when `aeat app ledger classify --llm` cannot find or run your LLM
provider. `aeat` does not store LLM credentials and does not have a separate
LLM account configuration command. It runs a provider CLI that is already installed and authenticated in your
system. `aeat` does not store or manage LLM credentials itself.

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md). The
  smoke test also needs at least one unclassified transaction in its ledger -
  see [Work with Transactions](import-bank-statements.md).
- Your master-key passphrase. Profile-scoped commands open the encrypted store,
  so they prompt for the passphrase (or read `AEAT_SECRET_PASSPHRASE` when set).

The runtime emits help, prompts, and messages in Spanish.

## Supported providers

The classification command accepts provider names such as `claude`,
`antigravity`, and `codex`. The `antigravity` provider uses Google's `agy`
CLI, the supported successor to the retired standalone `gemini` CLI. For the
current list, run `aeat app ledger providers`.

Use one of those names in the classification command:

```bash
aeat app ledger classify <transaction-id> --llm claude
```

## Check what aeat can see

List provider CLIs visible on `PATH`:

```bash
aeat app ledger providers
```

This command only checks whether each provider executable is discoverable. It
does not spawn the provider and does not verify account login. Each row reports
a provider, its status (`available` or `unavailable`), and a fix when something
is missing. The local vision reader appears here too: `ollama-vision` shows
`unavailable` with a fix (`start Ollama (ollama serve) ...`) until Ollama is
running.

For a wider check that also reports profile service capabilities, run:

```bash
aeat config check
```

It lists each external dependency - including every LLM provider as
`llm-provider:claude`, `llm-provider:antigravity`, and `llm-provider:codex` -
as `disponible` or `ausente`, and prints the fix for each problem.

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
aeat app ledger classify <transaction-id> --llm claude
```

A successful smoke test previews a suggestion and leaves the ledger unchanged.
If the provider CLI is installed but not authenticated, the classification
command refuses and relays the provider's own error. With the `claude` CLI
logged out, for example, it reports `La clasificacion por LLM fallo: claude CLI
exited with 1: 'Not logged in ...'`. Complete that provider login with its own
CLI and retry.

Only use `--apply` after you have verified that preview works and you have
reviewed the suggestion:

```bash
aeat app ledger classify <transaction-id> --llm claude --apply
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
