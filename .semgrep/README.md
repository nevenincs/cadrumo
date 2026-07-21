# Semgrep regression rules

Rules in `.semgrep/rules/` enforce type-system and architectural discipline
across the codebase. They prevent reintroduction of patterns that bypass
the strict pydantic / typed-ID contracts established in `src/cadrumo/domain/`
and `src/cadrumo/application/`.

## Rules

| File | Surface | Severity |
|------|---------|----------|
| `no-any-annotation.yml` | `src/cadrumo/domain/`, `src/cadrumo/application/` | ERROR |
| `no-dict-str-any.yml` | `src/cadrumo/domain/`, `src/cadrumo/application/` | ERROR |
| `no-cast-in-domain.yml` | `src/cadrumo/domain/`, `src/cadrumo/application/` | ERROR |
| `no-mapping-str-decimal-on-registry.yml` | Registry-tier models | ERROR |
| `no-duplicate-ccaa-enum.yml` | Outside `domain/contribuyente/_ccaa.py` | ERROR |
| `no-duplicate-concept-models.yml` | `src/cadrumo/` (excludes tests) | WARNING |

## CI invocation

`semgrep --config .semgrep/rules/ --error src/cadrumo/`

Failing rules are gating. Justified exceptions must use inline rule-id +
rationale comments (semgrep `# nosem:<rule-id> reason: <why>`).
Type-ignore rationale is enforced once, repository-wide, by
`src/cadrumo/tests/test_type_ignore_rationale_inventory.py`; it is not
duplicated as a Semgrep rule.

## Local dev

`semgrep` requires the Unix `resource` module and does not run on Windows.
Windows contributors should use the suppression inventory tool as a faster
proxy: `uv run --no-sync python scratch/suppression_inventory.py`. The
inventory script reports any new sites in disallowed categories.

CI on Ubuntu/macOS runners executes the full semgrep rule set.

## Adding new rules

Each rule should:

1. Describe the violation pattern and its harm in self-contained prose in
   the `message` body. The rule should be readable as-is, without external
   project documents.
2. Scope to the smallest applicable path set under `paths.include`.
3. Use `paths.exclude` for legitimate exemptions (tests, adapter boundaries
   bridging external untyped APIs).
4. Set `severity: ERROR` for gating rules; `WARNING` for advisory.
