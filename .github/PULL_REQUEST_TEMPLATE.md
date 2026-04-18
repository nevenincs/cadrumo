<!-- Every PR must answer the Kent question. -->

## What Kent can now do that he couldn't before

<!-- One sentence, Kent-observable. If this PR is pure infrastructure, cite the Kent capability it unblocks. -->

## Closes

<!-- GitHub issue numbers, e.g. Closes #216 -->

## Acceptance criteria met

<!-- Copy the Kent-observable acceptance bullets from the issue and tick each one. -->

- [ ] ...

## Charter compliance

- [ ] No new default-enabled AEAT write paths ([#197](https://github.com/wgergely/aeat/issues/197), [#116](https://github.com/wgergely/aeat/issues/116))
- [ ] CI regression-prevention checks pass ([#205](https://github.com/wgergely/aeat/issues/205))
- [ ] `aeat submission submit` / `aeat live-submit` still absent from default `--help`

## Regression prevention

- [ ] If this PR closes a Kent wall, a test exists that prevents its reintroduction
- [ ] Kent journey audits referenced as needed (`.vault/audit/2026-04-17-kent-*.md`)

## Coverage matrices

- [ ] `docs/coverage/modelos.md` updated if this PR changes per-modelo state
- [ ] `docs/coverage/kent-capabilities.md` updated if this PR changes capability state
- [ ] `docs/coverage/pipeline.md` updated if this PR changes T1–T6 pipeline state

## Other

- [ ] Conventional commit on every commit
- [ ] Docs / README / ROADMAP updated if user-facing
- [ ] Trilingual contract honoured for user-facing strings (es/en/hu)
- [ ] No absolute `aeat.*` imports added inside `src/aeat/` (#162)

## Test plan

<!-- What did you run locally? just test-cov, just lint, etc. -->
