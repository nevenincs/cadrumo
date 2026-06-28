# Testimonial — Carlos Vega, EMPLEADO + AUTÓNOMO (mixed income, Modelo 100)

**Slug:** `mixed-income-empleado-autonomo` · **Profile:** `carlos` ·
**NIF:** 11111111H · **Entity:** natural_person · **Birth:** 1985-06-15 ·
**Income categories:** `actividad_economica` + `trabajo` ·
**Activity:** "Consultoría informática", start 2024-01-01.
**Scenario:** a person who is BOTH employed under contract (salary + M111
employer withholding) AND an autónomo (actividad económica), filing the annual
Modelo 100 (Renta) that must combine both income streams.

## 1. Persona
I work a salaried job (≈€30.000, with IRPF withheld monthly by my employer via
Modelo 111) AND invoice on the side as an autónomo (≈€20.000 net, classified in
my ledger). My Renta has to add both together. I want the tool to combine my
nómina and my autónomo income and credit my withholdings and pagos fraccionados.

## 2. What worked
- **Mixed income categories accepted** at profile creation
  (`--irpf-income-categories actividad_economica --irpf-income-categories trabajo`);
  the CLI Choice hint correctly listed the accepted set when I guessed wrong
  (`rendimientos_trabajo` → it told me the value is `trabajo`).
- **Employment income flows through M100.** `--casilla 0003=30000` (rendimiento
  del trabajo dinerario) propagates: 0012/0017/0018/0022/0025=30000 → base
  general 0435/0500/0505=30000 → cuota íntegra 0545=3055.50 + 0546=2675.19 →
  0595=5730.69.
- **Employment retenciones credit folds** (casilla 0596=5000) via the
  `renta-2024-modelo-111-retenciones-periodicas` relation I supplied.
- **Birth-date date binding now resolves from the profile** (it is no longer in
  the missing-bindings list once the profile carries it) — confirming the
  correct channel for date facts is the profile, consistent with the F5 fix from
  the prior campaign.
- A working **DT-12ª pension-reduction advisory** fired (casilla 0011),
  educating about a possible 40% reduction with the exact flags to supply.

## 3. Friction / breakage
- **Autónomo income is DROPPED from M100 (see Finding 1).** casilla 0171
  ("Ingresos de explotación") stayed **0** despite €20.000 of classified
  actividad-económica income in the ledger; the base 0435=30000 reflected ONLY
  the employment salary, not employment + autónomo (~50.000).
- **M100 verify is blocked by the cross-period clean-state gate on M111** (12
  monthly periods need official AEAT evidence) — the employment retenciones
  credit cannot be verified/exported from a purely local chain (the same
  by-design safety invariant the prior campaign grounded for M130→M100).
- The profile-source bindings (declaration-type, descendientes, marriage,
  guardería, cotizaciones) are flagged missing for a single childless filer and
  must be supplied as zeros — minor known friction.

## 4. Input → Output reconciliation
| Input | Value | M100 casilla | Value | Match |
|---|---|---|---|---|
| Salary (manual 0003) | 30000 | 0003 / 0435 base general | 30000 / 30000 | ✅ |
| Employer withholding (M111) | 5000 | 0596 retenciones trabajo | 5000 | ✅ |
| **Autónomo net (ledger, classified)** | **20000** | **0171 ingresos explotación** | **0** | ❌ dropped |
| Combined base (expected ≈50000) | ~50000 | 0435 base general | 30000 | ❌ autónomo missing |

## 5. Final artefact
No `.boe` reached — M100 verify is blocked by the M111 cross-period clean-state
gate (no official monthly M111 evidence in a local-only chain). Consistent with
the prior campaign's grounded F4 safety invariant.

## 6. Findings (grounded)
1. **No mixed-income reconciliation path — autónomo ledger income does not flow
   into M100 — MEDIUM/HIGH (grounded).** RAG + registry grounding confirms M100
   2024 casilla 0171 (`registry/.../100/revisions/2024/casillas/0168-0171.toml`)
   is a **manual-input** casilla — no `formula`, no aggregation binding — so the
   work-unit `calculate` path never pulls the classified actividad-económica
   ledger income into the Renta. The only autónomo→renta bridge,
   `project_modelo_100_from_m130`, injects the M130 rendimiento into 0171 but
   **ignores employment income**. So neither path reconciles a mixed-income
   filer: `work calculate` drops the autónomo income (manual 0171), and `project`
   drops the salary. A real empleado+autónomo who classified their autónomo
   income would silently under-declare it in M100 unless they know to hand-enter
   0171 — relevant to `no-silent-under-declaration` (no advisory naming the
   unaggregated income was observed, though verify blocked on M111 first).
2. **Employment retenciones credit needs official M111 evidence — by design
   (grounded).** M100 verify blocks with `cross_period_dependency_unclean` on
   `renta-2024-rel-111-retenciones-mensuales` for all 12 months — the same
   external-evidence safety gate (`local-filed-observations-are-non-official-evidence`).
   Not a defect; a local-only mixed-income chain cannot self-evidence employer
   withholding.

## 7. Verdict
The individual pieces work — employment income propagates, the retenciones credit
and DT-12ª advisory are correct, and date facts resolve from the profile. But
there is **no end-to-end mixed-income (empleado + autónomo) reconciliation**: the
autónomo ledger income is silently dropped from M100 (manual 0171, no
aggregation), and the employment-withholding credit is gated behind official M111
evidence. A real mixed-income filer would **not** succeed unaided in producing a
correct combined Renta from local data.
