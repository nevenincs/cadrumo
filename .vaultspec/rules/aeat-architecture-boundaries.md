# AEAT architecture boundaries

## Placement

Place Python application code under `src/cadrumo/`. Do not add top-level Python
packages, ad-hoc module roots, or hidden parallel implementations. Keep the
accepted hexagonal direction: domain logic independent from adapters, and
inbound, outbound, persistence, application, entrypoint and core
responsibilities separated. Keep the CLI root surface to `config` and `app` —
never a third root command family.

Every Python test file lives under a `tests/` directory at the narrowest owning
package. A naked `test_*.py` beside implementation modules pollutes the code
namespace and is forbidden.

## Typed boundaries

Expose validated boundary data through pydantic v2 models, with strict config
where practical. Do not expose bare `dict[str, Any]` for persisted records, wire
payloads, configuration, CLI input, MCP messages, LLM responses, or fixtures.

**Type every constant-like axis.** Closed value sets — period codes, output
languages, lifecycle states, source kinds, auth providers — MUST be a StrEnum
(or `Literal` where appropriate) in `core/`. Production code and CLI handlers
accept and emit enum members, not raw strings; registry TOML stays free-form and
the loader hydrates the typed enum at the boundary; tests assert against enum
members.

**Hint accepted values at the CLI boundary.** Every Typer argument whose value
is a closed enum declares that enum as its type, so click renders the accepted
set on parse failure. A late registry-driven refusal is acceptable for axes that
depend on dynamic registry data, but it MUST list the accepted set — never a bare
"value invalid".

## No shims

Do not introduce shims, compatibility layers, deprecation paths, or duplicate
legacy APIs. Move callers to the canonical path instead.

**A new service must delegate to an existing single-writer primitive rather than
re-implementing its write path.** The service emits its own surface-level event
in addition to the primitive's lifecycle event; the two are intentionally
distinct (lifecycle records the data change, surface records the operator's verb
invocation). Re-implementing re-introduces the torn-write risk the primitive
eliminates and creates shadow event emission.

## Relocations are atomic

Land every symbol relocation in ONE explicit-path commit: the canonical-site
move, every consumer update, every fixture update, and every `__all__` baseline
update share one git index and one commit. Run
`uv run --no-sync pytest --collect-only -q` immediately before and observe clean
collection. Never split the move from the consumer sweep across commits, and
never reintroduce a re-export as a temporary bridge. One Step = one symbol = one
atomic commit; tag the subject `relocation:<symbol>` so audits can grep history.

Companions: `service-imports-via-top-level-reexports`, `no-legacy-compatibility`,
`aeat-source-hygiene`.
