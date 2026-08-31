---
name: aeat-cli-contract
trigger: always_on
---

# AEAT CLI contract

## Command surface

- The root command families are `config` and `app`. Commands extend the established subject hierarchy and do not create aliases or parallel spellings.
- The subject is positional where the hierarchy already makes it the command target. Options represent modifiers or explicit parameter loci; do not encode the same concept both positionally and as an option.
- Use stable transport tokens and machine-readable identifiers at the CLI boundary. Localized presentation text is output, never an input protocol.
- Local file ingestion uses the subject's `import --file` flow, for example `aeat config profile censo import --file ...`; do not revive retired `file` command families.

## Behavior

- Commands are deterministic and idempotent where they mutate local configuration. Refuse ambiguous state instead of guessing.
- User-facing notices go through the established notice/output channel. Do not mix diagnostics with structured output or write directly to arbitrary streams.
- Parse, validate, and normalize at the boundary, then call the same application service used by non-CLI entrypoints. The CLI must not carry a second business implementation.
- Help, completion, examples, and generated CLI reference derive from the live command tree. Do not maintain hand-copied inventories.

## Verification

Test the live parser and command registration, including success, refusal, idempotency, output channel, and machine-readable form. When changing a command, update its generated reference through the owning CLI generator rather than editing generated output.
