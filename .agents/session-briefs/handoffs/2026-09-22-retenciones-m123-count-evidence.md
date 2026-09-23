# RETENCIONES-01: Modelo 123 count boundary (2026-09-22)

Status: authority question open; filing-grade Modelo 123 capture/calculation remains refused. This packet is research, not an approved counting rule.

Selected local target: Modelo 123 revision `2024-y-siguientes`, filing year 2025. The AEAT record-design catalogue identifies its 2024-and-later design as Orden EHA/3435/2007, revised by Orden HAC/56/2024. The 2024 form has separate `Número de rentas` fields for participation in equity and other relevant rents, plus a total (casillas 01, 02 and 03). Those are not the older `Número de perceptores` field.

Official sources checked:

- [AEAT record-design catalogue](https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html), entry 123, links the [2024-and-later XLS design](https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos_24/DR123e24.xls).
- [Orden HAC/56/2024](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-1772), annex I, replaces the Modelo 123 form; the published form identifies the three count boxes but does not define the count unit for instalments of one rent.
- [Orden EHA/3435/2007, consolidated](https://www.boe.es/buscar/act.php?id=BOE-A-2007-20485), article 1 and annex II, establishes the model and incorporates the 2024 modification. The consolidated text itself warns that the official amendment publication governs.
- [AEAT Modelo 123 procedure](https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GH04.shtml) links the 2024-and-later presentation and the record-design catalogue; it does not resolve the instalment count.

The inspected official material establishes the selected field and its two categories. It does **not** establish whether two payment instalments of one economic rent, one recognized taxable amount settled later, or two separate economic rents to one recipient contribute one or two to the appropriate quarterly count. Recognition timing and the annual Modelo 193 disclosure phases do not by themselves define this Modelo 123 count. A non-official explanation that equates the field with payments cannot settle the ambiguity.

Exact question for authoritative clarification: *For Modelo 123 revision 2024-y-siguientes, casillas 01/02 `Número de rentas`, when one identifiable income entitlement is paid in two instalments (including across quarters), is each instalment counted as a separate renta in the period of withholding, or is the economic income entitlement counted once? How does the answer differ when the income is recognized/exigible before later settlement, and which field or official example defines that treatment?*

Until an authoritative answer is obtained and boundary tests implement it through the typed binding, no inferred count may feed Modelo 123 verification or export. The existing public mutation refusal in `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py` remains required. This limitation is separate from the supported 111/115/180/190 installed campaign.

## Follow-up research — 2026-09-23

Result: no official AEAT, BOE or DGT text defines the 2024-revision "Número de rentas" unit or settles instalments. Filing-grade Modelo 123 stays refused, and the capability stays advisory.

Official material found, with the scope each item actually has:

- The pre-2024 field "N.º de perceptores" counted taxpayers. AEAT's printed instructions "Instrucciones para cumplimentar el modelo 123" (form M-123E-80/0.30, citing RD 439/2007 and RD 1777/2004) define casilla 01 as «el número total de contribuyentes o sujetos pasivos que hayan obtenido rentas o rendimientos del capital mobiliario». The copy read was on a third-party host (caisistemas.es/enlaces/instr_123.PDF); it is AEAT text, but that host is not an official locator. This definition applies only to the old field.
- Orden HAC/56/2024 (BOE-A-2024-1772) says its new annex I only adds a breakdown of dividends and other participation income («con la finalidad, exclusivamente, de incluir un desglose…»). It gives no definition of the relabelled "Número de rentas" count and has no instructions annex.
- The Modelo 111 instructions (AEAT sede, updated 09/06/2026) count persons for "Nº de perceptores". They say nothing on repeated payments to one person, and they cover a different modelo.
- Timing is settled by RIRPF art. 94.1 (RD 439/2007) and RIS art. 65.1 (RD 634/2015): the retention arises when the income becomes exigible, or when it is paid if payment comes first, and it is declared in that quarter under RIRPF art. 108.1. DGT V3165-21 applies the same rule to dividends. None of these define the count.
- DGT V1151-14 repeats the "contribuyentes" reading only as the consultant's own statement; it is not a DGT ruling on counting.

The authority still missing, and any one of these would settle the question: the casilla help inside the AEAT 2024 online form (OVME-COMN/123/E2024, which needs a login), an AEAT instruction or FAQ page for the 2024 revision, or a DGT consulta vinculante on how "número de rentas" is counted. Until one is obtained, Modelo 123 must keep a typed, visible advisory reason in both frontends. Today the CLI refusal is a hard-coded English `typer.BadParameter` in `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`. It is not localized, not typed, and does not name this missing authority. Replacing it with a typed refusal through the locale catalogue is an open implementation target, and it is blocked only by the shared `cli.yml`/`common.yml` catalogue slot.