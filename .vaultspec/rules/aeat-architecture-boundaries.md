---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

Place Python application code under `src/aeat/`. Do not add top-level Python packages, ad-hoc module roots, or hidden parallel implementations.

Expose validated boundary data through pydantic v2 models. Use strict config where practical. Do not expose bare `dict[str, Any]` for persisted records, wire payloads, configuration, CLI input, MCP messages, LLM responses, or fixtures.

Preserve the accepted hexagonal direction. Keep domain logic independent from adapters. Keep inbound, outbound, persistence, application, entrypoint, and core responsibilities separated.

Keep the CLI root surface to `config` and `app`. Do not add a third root command family.

Do not introduce shims, compatibility layers, deprecation paths, or duplicate legacy APIs. Move callers to the canonical path instead.

Land every symbol relocation in one atomic explicit-path commit. The canonical-site move, every consumer update, every fixture update, and every `__all__` baseline update share one git index and one commit. Run `uv run --no-sync pytest --collect-only -q` immediately before the commit and observe clean collection. Never split the canonical-site move from the consumer sweep across commits. Never reintroduce a re-export as a temporary bridge. One Step = one symbol = one atomic commit. Tag the commit subject with `relocation:<symbol>` so audits can grep history for the canonical-home decisions.

Type every constant-like axis. Closed value sets (period codes, output languages, lifecycle states, source kinds, auth providers, etc.) MUST be declared as StrEnum (or Literal where appropriate) in `core/` per the core-authority ADR. Production code and CLI handlers MUST accept and emit enum members, not raw strings. The registry TOML stays free-form per the registry-authority-flow rule; the loader hydrates the typed enum at boundary. Tests MUST assert against enum members.

Hint accepted values at the CLI boundary. Every Typer argument whose value is a closed enum MUST declare that enum as its type so click renders `Choice([...])` and surfaces the accepted-value set on parse failure. Late, registry-driven refusals (e.g. modelo-period-revision combinatorial checks) are acceptable for axes that depend on dynamic registry data, but the refusal MUST list the accepted set in the error message — never a bare "value invalid" without options. The CLI gate is the operator's first instructive surface. Never make it a silent black hole.
