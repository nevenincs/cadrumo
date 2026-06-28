---
tags:
  - "#exec"
  - "#dev-scaffolding"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-dev-scaffolding-plan]]"
  - "[[2026-04-12-dev-scaffolding-adr]]"
---

# dev-scaffolding phase-1 summary

Executed plan `[[2026-04-12-dev-scaffolding-plan]]` for issue wgergely/aeat#4
on branch `chore/4-dev-scaffolding`.

## outcomes

- **env layout**: `.env.example` moved to `env/.env.example` (`git mv`);
  `src/aeat/config.py` loads `PROJECT_ROOT / "env" / ".env"`;
  `tests/test_config.py` asserts the new path;
  `.gitignore` replaces blanket `env/` with `env/*` + `!env/.env.example`.
- **justfile dev loop**: recipes added — `default` (list), `bootstrap`
  (`uv sync` + `vaultspec-core install`), `install`, `sync`, `lint`, `fmt`,
  `typecheck` (ty), `test` (pytest), `hooks` (prek), `env-setup`. Dual
  `[unix]` / `[windows]` bodies where platform-specific.
- **gcloud-setup**: rewritten for both platforms. Unix: gcloud-update,
  else brew cask on Darwin, else `sdk.cloud.google.com` curl installer;
  Windows: gcloud update, else winget `Google.CloudSDK`, else manual URL.
  All branches return non-zero only on real failure.
- **env-setup**: copies `env/.env.example` → `env/.env` iff absent;
  otherwise no-op.

## verification

- `just env-setup` → creates `env/.env` from example.
- `just test` → 4 passed (pytest).
- `just lint` → ruff clean.
- `just typecheck` → ty clean.

## notes

- Unit/live pytest marker policy (CLAUDE.md) is pre-existing; not enforced
  on the existing config tests and out of scope for this issue.
- `tool.uv.dev-dependencies` deprecation warning is pre-existing and
  orthogonal to this change set.
