---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:29ef260d82d26f7dd8cecbf4ba7c11a537989041fb76d6dddade137d859dc818'
step_id: 'S29'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the statutory Python fact adapter with normalized scalar and decimal-mapping fragments carrying exact typed payloads, effective applicability, and official source evidence

## Scope

- `src/cadrumo/_data/registry/aeat/facts and dev/registry/compiler/fact_providers.py and dev/registry/compiler/statutory_constants.py and dev/registry/tests and dev/registry/analysis/facts_external_constants_retirement.toml`

## Changes

- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `M` `dev/registry/compiler/fact_providers.py`
- `D` `dev/registry/compiler/statutory_constants.py`
- `M` `dev/registry/tests/test_facts_wave2_provider_handoff.py`
- `A` `dev/registry/tests/test_statutory_authored_facts.py`
- `D` `dev/registry/tests/test_statutory_constants_provider.py`
- `M` `dev/registry/tests/test_wave2_fact_provider_handoff.py`
- `A` `src/cadrumo/_data/registry/aeat/facts/0030-m347-counterparty-declaration-threshold.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0031-m347-clave-c-beneficiary-declaration-threshold.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0032-iva-bien-inversion-escaso-valor-threshold.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0033-iae-cifra-negocios-exemption-threshold.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0034-lirpf-art-7p-exemption-cap.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0035-lirpf-multiple-pagadores-secondary-threshold.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0036-lirpf-work-income-general-declaration-limit.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0037-lis-art-40-3-incn-threshold.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0038-lirpf-art-20-trabajo-reduccion-rnt-ceiling.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0039-lirpf-art-52-individual-contribution-sublimit.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0040-rebeca-maritime-exemption-fraction.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0041-lirpf-art-81-maternity-monthly-amount.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0042-lirpf-art-81-maternity-annual-cap.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0043-lirpf-art-81-maternity-post-birth-enrollment-increment.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0045-lirpf-art-81-maternity-post-birth-enrollment-effective-year.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0046-lirpf-art-81-contribution-ceiling-retired-effective-year.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0047-lirpf-art-58-descendant-ordinary-maximum-age.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0048-lirpf-art-58-under-three-maximum-age.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0049-lirpf-art-61-shared-custody-proration-factor.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0050-lirpf-art-81-adoption-entry-window-years.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0051-madrid-birth-adoption-following-periods.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0052-lirpf-dt12-rescate-reduction-rate.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0053-lirpf-dt12-general-window-following-years.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0054-lirpf-dt12-transitional-contingency-first-year.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0055-lirpf-dt12-transitional-contingency-last-year.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0056-lirpf-dt12-transitional-window-following-years.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0057-lirpf-dt12-cliff-last-year.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0058-sal-special-reserve-allocation-rate.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0059-sal-special-reserve-capital-multiple.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0060-dehu-tacit-rejection-natural-days.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0061-lirpf-work-income-multiple-pagadores-reduced-limit.toml`
- `verify:` `uv run pytest -q -n 0 dev/registry/tests/test_statutory_authored_facts.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py dev/registry/tests/test_authored_mapping_fact_values.py` -> `pass`
