# Semgrep regression rules

Rules in `.semgrep/rules/` enforce the type-uniformity discipline established
in Wave 1 of the linkage-design epic. They prevent reintroduction of the
suppression patterns eradicated during Phases P03 through P10.

## Rules

| File | Defect class | Surface | Severity |
|------|--------------|---------|----------|
| `no-any-annotation.yml` | T-11 | `src/aeat/domain/`, `src/aeat/application/` | ERROR |
| `no-dict-str-any.yml` | T-01 | `src/aeat/domain/`, `src/aeat/application/` | ERROR |
| `no-cast-in-domain.yml` | T-11 | `src/aeat/domain/`, `src/aeat/application/` | ERROR |
| `justify-ty-ignore.yml` | T-11 | `src/aeat/` (excludes tests) | ERROR |

Defect-class references point at the Issue Taxonomy v1 reference document.

## CI invocation

`semgrep --config .semgrep/rules/ --error src/aeat/`

Failing rules are gating. Justified exceptions must use inline rule-id +
rationale comments (semgrep `# nosem:<rule-id> reason: <why>`).

## Local dev

`semgrep` requires the Unix `resource` module and does not run on Windows.
Windows contributors should use the suppression inventory tool as a faster
proxy: `uv run --no-sync python scratch/suppression_inventory.py`. The
inventory script reports any new sites in disallowed categories.

CI on Ubuntu/macOS runners executes the full semgrep rule set.

## Adding new rules

Each rule should:

1. Cite a defect class from the Issue Taxonomy v1 reference document in its
   `message` body.
2. Scope to the smallest applicable path set under `paths.include`.
3. Use `paths.exclude` for legitimate exemptions (tests, adapter boundaries
   bridging external untyped APIs).
4. Set `severity: ERROR` for gating rules; `WARNING` for advisory.
