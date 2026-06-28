---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
---

# `schema-hardening` audit: M100 reserva-inversiones cluster role assignment

## Scope

Sections `reserva_inversiones_canarias_res` (RIC — Reserva para Inversiones en Canarias, Ley 19/1994 art. 27) and `reserva_inversiones_baleares_res` (RIB — Reserva para Inversiones en las Illes Balears, DA 70a LIS) from M100 IRPF, all revisions 2020–2025.

Cluster JSON source: `.vault-scratch/m100-clusters/reserva-inversiones.json`.

- Total unique casilla ids in cluster: 38
- RIC-only ids: 26 (0733–0802, 0829, 1643, 1683)
- Shared RIC+RIB ids (shift by revision): 4 (1681, 1682, 1684, 1685)
- RIB-only ids: 8 (1689, 1780–1784, 1937–1943)

All roles are drawn verbatim from `_existing-roles.txt` where the concept matches. No new role names were minted: every concept in this cluster has a matching existing role.

---

## Role assignments

Each per-vintage slot (e.g., "RIC 2016: Importe de las dotaciones") is a structural AEAT table row; AEAT reuses the same physical casilla `id` to hold a different vintage row in different tax years (revisions). The role is assigned to the stable concept the casilla slot carries, not to the vintage year shown in any one revision's label. `revisions_present` lists the tax-year revisions (form years) in which this id appears.

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0733 | `irpf_anexo_a_ric_dotacion_importe` | RIC [2016/2018/2019/2020/2021]: Importe de las dotaciones | money(default) | 2020, 2022, 2023, 2024, 2025 | Per-vintage dotation amount slot; vintage shifts across form years |
| 0734 | `irpf_anexo_a_ric_dotacion_anio` | RIC [2016/2018/2019/2020/2021]: Año de la dotación | money(default) / text | 2020, 2022, 2023, 2024, 2025 | Data-type divergence: money(default) in 2020, text from 2022 onward — see §Data_type divergences |
| 0735 | `irpf_anexo_a_ric_dotacion_importe` | RIC [2017/2018/2020/2021/2022]: Importe de las dotaciones | money(default) | 2020, 2021, 2023, 2024, 2025 | Per-vintage dotation amount slot |
| 0736 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC [2017/2018/2020/2021/2022]: Inversiones previstas letras A, B, B.bis y D | money(default) | 2020, 2021, 2023, 2024, 2025 | Investment sub-type A,B,B.bis,D(1º) |
| 0737 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2017/2018/2020/2021/2022]: Inversiones previstas letras C y D (2º–6º) | money(default) | 2020, 2021, 2023, 2024, 2025 | Investment sub-type C,D(2º–6º) |
| 0738 | `irpf_anexo_a_ric_dotacion_importe` | RIC [2018/2019/2020/2022/2023]: Importe de las dotaciones | money(default) | 2020, 2021, 2022, 2024, 2025 | Per-vintage dotation amount slot |
| 0739 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC [2018/2019/2020/2022/2023]: Inversiones previstas letras A, B, B.bis | money(default) | 2020, 2021, 2022, 2024, 2025 | Investment sub-type A,B,B.bis,D(1º) |
| 0740 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2018/2019/2020/2022/2023]: Inversiones previstas letras C y D (2º–6º) | money(default) | 2020, 2021, 2022, 2024, 2025 | Investment sub-type C,D(2º–6º) |
| 0741 | `irpf_anexo_a_ric_pendiente_materializar` | RIC [2018/2019/2020/2022/2023]: Pendiente de materializar | money(default) | 2020, 2021, 2022, 2024, 2025 | Amount pending materialization |
| 0742 | `irpf_anexo_a_ric_dotacion_importe` | RIC [2019/2020/2021/2022/2024]: Importe de las dotaciones | money(default) | 2020, 2021, 2022, 2023, 2025 | Per-vintage dotation amount slot |
| 0743 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC [2019/2020/2021/2022/2024]: Inversiones previstas letras A, B, B.bis | money(default) | 2020, 2021, 2022, 2023, 2025 | Investment sub-type A,B,B.bis,D(1º) |
| 0744 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2019/2020/2021/2022/2024]: Inversiones previstas letras C y D (2º–6º) | money(default) | 2020, 2021, 2022, 2023, 2025 | Investment sub-type C,D(2º–6º) |
| 0745 | `irpf_anexo_a_ric_pendiente_materializar` | RIC [2019/2020/2021/2022/2024]: Pendiente de materializar | money(default) | 2020, 2021, 2022, 2023, 2025 | Amount pending materialization |
| 0746 | `irpf_anexo_a_ric_dotacion_importe` | RIC [2020/2021/2022/2023/2024]: Importe de las dotaciones | money(default) | 2020, 2021, 2022, 2023, 2024 | Per-vintage dotation amount slot |
| 0747 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC [2020/2021/2022/2023/2024]: Inversiones previstas letras A, B, B.bis | money(default) | 2020, 2021, 2022, 2023, 2024 | Investment sub-type A,B,B.bis,D(1º) |
| 0748 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2020/2021/2022/2023/2024]: Inversiones previstas letras C y D (2º–6º) | money(default) | 2020, 2021, 2022, 2023, 2024 | Investment sub-type C,D(2º–6º) |
| 0749 | `irpf_anexo_a_ric_pendiente_materializar` | RIC [2020/2021/2022/2023/2024]: Pendiente de materializar | money(default) | 2020, 2021, 2022, 2023, 2024 | Amount pending materialization |
| 0750 | `irpf_anexo_a_ric_inversion_tipo_abd` | Inversiones anticipadas futuras dotaciones RIC [2020–2024]: letras A, B, B.bis y D (1º) | money(default) | 2020, 2021, 2022, 2023, 2024 | Anticipated investment of future dotations; already roled in 2025 TOML |
| 0751 | `irpf_anexo_a_ric_inversion_tipo_cd` | Inversiones anticipadas futuras dotaciones RIC [2020–2024]: letras C y D (2º–6º) | money(default) | 2020, 2021, 2022, 2023, 2024 | Anticipated investment of future dotations; already roled in 2025 TOML |
| 0777 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2016: Importe de las dotaciones (rev 2020 only) | money(default) | 2020 | **Id-reuse hazard** — rev 2020 holds dotation amount; revs 2022–2025 shift to investment tipo_abd; see §Id-reuse hazards |
| 0777 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC [2018/2019/2020/2021]: Inversiones previstas letras A, B, B.bis | money(default) | 2022, 2023, 2024, 2025 | Second concept on same id post-restructure |
| 0778 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2016: Importe de las dotaciones (rev 2020 only) | money(default) | 2020 | **Id-reuse hazard** — rev 2020 holds dotation amount; revs 2022–2025 shift to investment tipo_cd |
| 0778 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2018/2019/2020/2021]: Inversiones previstas letras C y D (2º–6º) | money(default) | 2022, 2023, 2024, 2025 | Second concept on same id post-restructure |
| 0789 | `irpf_anexo_a_ric_dotacion_anio` | RIC [2017/2018/2020/2021/2022]: Año de la dotación | money(default) / text | 2020, 2021, 2023, 2024, 2025 | Data-type divergence: money(default) in 2020, text from 2021 onward |
| 0790 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2017/2018]: Inversiones previstas letras C y D (2º–6º) (revs 2020–2021) | money(default) | 2020, 2021 | **Id-reuse hazard** — revs 2020–2021 carry tipo_cd concept; revs 2023–2025 shift to pendiente_materializar |
| 0790 | `irpf_anexo_a_ric_pendiente_materializar` | RIC [2020/2021/2022]: Pendiente de materializar (revs 2023–2025) | money(default) | 2023, 2024, 2025 | Second concept on same id after form restructure |
| 0792 | `irpf_anexo_a_ric_dotacion_anio` | RIC [2018/2019/2020/2022/2023]: Año de la dotación | money(default) / text | 2020, 2021, 2022, 2024, 2025 | Data-type divergence; see §Data_type divergences |
| 0794 | `irpf_anexo_a_ric_dotacion_anio` | RIC [2019/2020/2021/2022/2024]: Año de la dotación | money(default) / text | 2020, 2021, 2022, 2023, 2025 | Data-type divergence |
| 0802 | `irpf_anexo_a_ric_dotacion_anio` | RIC [2020/2021/2022/2023/2024]: Año de la dotación | money(default) / text | 2020, 2021, 2022, 2023, 2024 | Data-type divergence |
| 0829 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2016/2018]: Inversiones previstas letras C y D (2º–6º) (revs 2020–2021) | money(default) | 2020, 2021 | **Id-reuse hazard** — revs 2020–2021 carry tipo_cd; revs 2022–2023 shift to pendiente_materializar |
| 0829 | `irpf_anexo_a_ric_pendiente_materializar` | RIC [2018/2019]: Pendiente de materializar (revs 2022–2023) | money(default) | 2022, 2023 | Second concept on same id |
| 1643 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2016(1): Importe de las dotaciones | money(default) | 2022 | Single-revision id; supplemental 2016 vintage slot |
| 1681 | `irpf_anexo_a_ric_dotacion_importe` | RIC [2016(1)/2017(1)/2019(1)]: Importe de las dotaciones (revs 2021–2022) | money(default) | 2021, 2022 | **Id-reuse / section shift** — revs 2021–2022 serve RIC section; revs 2024–2025 serve RIB section with RIB 2023 label |
| 1681 | `irpf_anexo_a_rib_dotacion_importe` | RIB 2023: Importe de las dotaciones (revs 2024–2025) | money(default) | 2024, 2025 | Section shifts from RIC to RIB |
| 1682 | `irpf_anexo_a_ric_dotacion_anio` | RIC [2016(1)/2017/2019(1)]: Año de la dotación (revs 2021–2022) | text | 2021, 2022 | **Id-reuse / section shift** — pure text across all revisions; revs 2024–2025 serve RIB 2023 |
| 1682 | `irpf_anexo_a_rib_dotacion_anio` | RIB 2023: Año de la dotación (revs 2024–2025) | text | 2024, 2025 | Section shifts from RIC to RIB |
| 1683 | `irpf_anexo_a_ric_dotacion_anio` | RIC 2016(1): Año de la dotación (rev 2021) | money(default) / text | 2021 | **Id-reuse hazard** — rev 2021 carries dotacion_anio (money+text); rev 2022 carries ric_inversion_tipo_cd (money only) |
| 1683 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC 2018(4): Inversiones previstas letras C y D (rev 2022) | money(default) | 2022 | Distinct concept in single revision |
| 1684 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2016(1): Importe de las dotaciones (rev 2021) | money(default) | 2021 | **Id-reuse / section shift** — rev 2021 carries RIC dotacion_importe; revs 2022 carries RIC inv_tipo_abd; revs 2024–2025 carry RIB inv_tipo_ab |
| 1684 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC [2017/2019]: Inversiones previstas letras A, B, B.bis (rev 2022) | money(default) | 2022 | Intermediate concept |
| 1684 | `irpf_anexo_a_rib_inversion_tipo_ab` | RIB 2023: Inversiones previstas letras A y B (revs 2024–2025) | money(default) | 2024, 2025 | Section shifts from RIC to RIB |
| 1685 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2016(1): Importe de las dotaciones (rev 2021) | money(default) | 2021 | **Id-reuse / section shift** — rev 2021 carries RIC dotacion_importe; rev 2022 carries RIC inv_tipo_cd; revs 2024–2025 carry RIB inv_tipo_c |
| 1685 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC [2017/2019]: Inversiones previstas letras C y D (rev 2022) | money(default) | 2022 | Intermediate concept |
| 1685 | `irpf_anexo_a_rib_inversion_tipo_c` | RIB 2023: Inversiones previstas letra C (revs 2024–2025) | money(default) | 2024, 2025 | Section shifts from RIC to RIB |
| 1689 | `irpf_anexo_a_rib_pendiente_materializar` | RIB 2023: Pendiente de materializar | money(default) | 2025 | Single-revision RIB id; already roled in 2025 TOML |
| 1780 | `irpf_anexo_a_rib_dotacion_importe` | RIB 2024: Importe de las dotaciones | money(default) | 2025 | Single-revision RIB id |
| 1781 | `irpf_anexo_a_rib_dotacion_anio` | RIB 2024: Año de la dotación | text | 2025 | Single-revision RIB id; pure text |
| 1782 | `irpf_anexo_a_rib_inversion_tipo_ab` | RIB 2024: Inversiones previstas letras A y B | money(default) | 2025 | Single-revision RIB id |
| 1783 | `irpf_anexo_a_rib_inversion_tipo_c` | RIB 2024: Inversiones previstas letra C | money(default) | 2025 | Single-revision RIB id |
| 1784 | `irpf_anexo_a_rib_pendiente_materializar` | RIB 2024: Pendiente de materializar | money(default) | 2025 | Single-revision RIB id |
| 1937 | `irpf_anexo_a_rib_dotacion_importe` | RIB [2023/2024]: Importe de las dotaciones | money(default) | 2023, 2024 | Per-vintage dotation amount; vintage label shifts 2023→2024 across form years |
| 1938 | `irpf_anexo_a_rib_dotacion_anio` | RIB [2023/2024]: Año de la dotación | text | 2023, 2024 | Pure text across both revisions |
| 1939 | `irpf_anexo_a_rib_inversion_tipo_ab` | RIB [2023/2024]: Inversiones previstas letras A y B | money(default) | 2023, 2024 | Investment sub-type A,B |
| 1940 | `irpf_anexo_a_rib_inversion_tipo_c` | RIB [2023/2024]: Inversiones previstas letra C | money(default) | 2023, 2024 | Investment sub-type C |
| 1941 | `irpf_anexo_a_rib_pendiente_materializar` | RIB [2023/2024]: Pendiente de materializar | money(default) | 2023, 2024 | Amount pending materialization |
| 1942 | `irpf_anexo_a_rib_inversion_tipo_ab` | Inversiones anticipadas futuras dotaciones RIB [2023/2024]: letras A y B | money(default) | 2023, 2024 | Anticipated investment; already roled in 2025 TOML |
| 1943 | `irpf_anexo_a_rib_inversion_tipo_c` | Inversiones anticipadas futuras dotaciones RIB [2023/2024]: letra C | money(default) | 2023, 2024 | Anticipated investment; already roled in 2025 TOML |

---

## Id-reuse hazards

AEAT reassigns the same physical casilla `id` to a different vintage row (and sometimes a different concept family) in later form revisions. Each hazard below requires split assignment — the `role` column in the table above already carries separate rows with non-overlapping `revisions_present` ranges.

### 0777 — dotacion_importe → inversion_tipo_abd (1 concept boundary)

- Rev 2020: label "RIC 2016: Importe de las dotaciones" → `irpf_anexo_a_ric_dotacion_importe`
- Revs 2022–2025: label "RIC [2018/2019/2020/2021]: Inversiones previstas letras A, B, B.bis" → `irpf_anexo_a_ric_inversion_tipo_abd`
- Trigger: 2022 form restructured which physical slot each vintage occupies.

### 0778 — dotacion_importe → inversion_tipo_cd (1 concept boundary)

- Rev 2020: label "RIC 2016: Importe de las dotaciones" → `irpf_anexo_a_ric_dotacion_importe`
- Revs 2022–2025: label "RIC [2018/2019/2020/2021]: Inversiones previstas letras C y D (2º–6º)" → `irpf_anexo_a_ric_inversion_tipo_cd`

### 0790 — inversion_tipo_cd → pendiente_materializar (1 concept boundary)

- Revs 2020–2021: label "RIC [2017/2018]: Inversiones previstas letras C y D (2º–6º)" → `irpf_anexo_a_ric_inversion_tipo_cd`
- Revs 2023–2025: label "RIC [2020/2021/2022]: Pendiente de materializar" → `irpf_anexo_a_ric_pendiente_materializar`
- Note: rev 2022 is absent from the id's `revs` list; the concept shift straddles a gap year.

### 0829 — inversion_tipo_cd → pendiente_materializar (1 concept boundary)

- Revs 2020–2021: label "RIC [2016/2018]: Inversiones previstas letras C y D (2º–6º)" → `irpf_anexo_a_ric_inversion_tipo_cd`
- Revs 2022–2023: label "RIC [2018/2019]: Pendiente de materializar" → `irpf_anexo_a_ric_pendiente_materializar`

### 1681 — ric_dotacion_importe → rib_dotacion_importe (section + registry shift)

- Revs 2021–2022: section `reserva_inversiones_canarias_res`, RIC vintage labels → `irpf_anexo_a_ric_dotacion_importe`
- Revs 2024–2025: section `reserva_inversiones_baleares_res`, RIB 2023 label → `irpf_anexo_a_rib_dotacion_importe`
- Trigger: form slot reassigned from RIC supplemental vintage rows to RIB first vintage when RIB block was introduced.

### 1682 — ric_dotacion_anio → rib_dotacion_anio (section + registry shift)

- Revs 2021–2022: RIC "Año de la dotación" (text) → `irpf_anexo_a_ric_dotacion_anio`
- Revs 2024–2025: RIB "Año de la dotación" (text) → `irpf_anexo_a_rib_dotacion_anio`

### 1683 — ric_dotacion_anio → ric_inversion_tipo_cd (2 distinct concepts in 2 revisions)

- Rev 2021: label "RIC 2016(1): Año de la dotación", data_type money(default)+text → `irpf_anexo_a_ric_dotacion_anio`
- Rev 2022: label "RIC 2018(4): Inversiones previstas letras C y D", data_type money(default) → `irpf_anexo_a_ric_inversion_tipo_cd`
- Highest-severity hazard in cluster: both concept and data_type change between adjacent revisions.

### 1684 — three-concept trajectory (ric_dotacion_importe → ric_inv_tipo_abd → rib_inv_tipo_ab)

- Rev 2021: RIC 2016(1) dotacion importe → `irpf_anexo_a_ric_dotacion_importe`
- Rev 2022: RIC [2017/2019] inv tipo abd → `irpf_anexo_a_ric_inversion_tipo_abd`
- Revs 2024–2025: RIB 2023 inv tipo ab → `irpf_anexo_a_rib_inversion_tipo_ab`

### 1685 — three-concept trajectory (ric_dotacion_importe → ric_inv_tipo_cd → rib_inv_tipo_c)

- Rev 2021: RIC 2016(1) dotacion importe → `irpf_anexo_a_ric_dotacion_importe`
- Rev 2022: RIC [2017/2019] inv tipo cd → `irpf_anexo_a_ric_inversion_tipo_cd`
- Revs 2024–2025: RIB 2023 inv tipo c → `irpf_anexo_a_rib_inversion_tipo_c`

---

## Data_type divergences

Several "Año de la dotación" ids carry `money(default)` in revision 2020 and `text` from revision 2021 or 2022 onward. This is a systematic AEAT form correction: the year field was initially mis-typed as a monetary field and corrected to `text` in subsequent revisions. Each affected id still maps to a single conceptual role (`irpf_anexo_a_ric_dotacion_anio`) because the underlying concept (the year of the dotation vintage) did not change — only the encoding type did.

| id | revisions with money(default) | revisions with text | role |
|----|-------------------------------|---------------------|------|
| 0734 | 2020 | 2022, 2023, 2024, 2025 | `irpf_anexo_a_ric_dotacion_anio` |
| 0789 | 2020 | 2021, 2023, 2024, 2025 | `irpf_anexo_a_ric_dotacion_anio` |
| 0792 | 2020 | 2021, 2022, 2024, 2025 | `irpf_anexo_a_ric_dotacion_anio` |
| 0794 | 2020 | 2021, 2022, 2023, 2025 | `irpf_anexo_a_ric_dotacion_anio` |
| 0802 | 2020 | 2021, 2022, 2023, 2024 | `irpf_anexo_a_ric_dotacion_anio` |
| 1683 | 2021 (also concept-hazard) | — | `irpf_anexo_a_ric_dotacion_anio` (rev 2021 only) |

**Remediation**: the schema constraint for `ric_dotacion_anio` should accept `text` as canonical and flag the 2020 `money(default)` instances as legacy encoding drift requiring migration or validator exemption scoped to rev ≤ 2020.

---

## Summary

- Total ids classified: 38
- Total role-assignment rows emitted: 53 (15 ids require split rows due to id-reuse)
- Existing roles reused: 10 (all drawn verbatim from `_existing-roles.txt`)
- New roles minted: 0
- Id-reuse hazards: 8 ids (0777, 0778, 0790, 0829, 1681, 1682, 1683, 1684, 1685)
- Data-type divergences: 5 ids carrying mixed `money(default)` / `text` on "Año de la dotación" field (0734, 0789, 0792, 0794, 0802) plus 1683 (also a concept hazard)
- Ids already roled in the 2025 TOML (confirmed match): 0750, 0751, 1689, 1942, 1943
