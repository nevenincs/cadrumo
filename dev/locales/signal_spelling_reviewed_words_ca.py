"""Reviewed exact Catalan dictionary gaps used by the locale spelling audit."""

from __future__ import annotations

REVIEWED_CATALAN_SPELLINGS: frozenset[str] = frozenset(
    {
        # The vendor uses this exact Catalan form for its macOS app:
        # https://teler.ai/ca/download
        "notaritzada",
        # Exact name of the recurring Spanish persona in the two lifecycle guides.
        "Ana",
        "García",
        # Native second-person verb forms, rather than the accented
        # adjective homographs, and the noun/adjective in the guides.
        # https://www.softcatala.org/conjugador-de-verbs/verb/publicar/
        # https://www.softcatala.org/conjugador-de-verbs/verb/especificar/
        # https://www.boe.es/boe_catalan/dias/2009/12/29/pdfs/BOE-A-2009-21050-C.pdf
        # https://catsalut.gencat.cat/web/.content/minisite/catsalut/coneix_catsalut/organitzacio/organs-direccio/Documentacio-aprovada-en-les-sessions-del-Consell-de-Direccio/2025/2025-01-27/CSMS-tarifes-per-particulars-2025.pdf
        # https://www20.gencat.cat/docs/gecopedia/Temes/Manuals%20dus%20GECO/FormesPresentacio/Arxius/OTGencat_GECO_IMMU_FPs_fil_Ariadna.pdf
        # https://www.bnc.cat/esl/content/download/617/5190/version/6/file/pcd_011_2024.pdf
        "publiques",
        "especifiques",
        "recapitulatiu",
        "recomprovació",
        "enllaçable",
        "inclusives",
        # Reference Hunspell accepts this present-tense form; spylls does not.
        # https://www.softcatala.org/conjugador-de-verbs/verb/calcular/
        "calcules",
        # Software package subdivisions, used by the Institut Obert de Catalunya:
        # https://ioc.xtec.cat/materials/FP/Recursos/fp_dam_m03_/web/fp_dam_m03_htmlindex/WebContent/u3/a1/continguts.html
        "subpaquet",
        "subpaquets",
        "Subpaquets",
        # Generalitat uses these exact forms in legal and form guidance:
        # https://repositori.justicia.gencat.cat/bitstream/handle/20.500.14226/576/llei_enjudiciament_civil_qdl88.pdf
        # https://canalempresa.gencat.cat/ca/ajuda/ajuda/ajuda-a-larea-privada/preferencies/dades/
        "declarable",
        "Preomple",
        # BOE's Catalan edition uses this exact plural for reportable items:
        # https://www.boe.es/boe_catalan/dias/2020/02/05/pdfs/BOE-A-2020-1653-C.pdf
        "declarables",
        # Exact native, technical and retained tax forms attested in
        # _data/terminology/concepts; no new casing or inflections implied.
        "autorepercuteix",
        # The unchanged surname names the impatriate regime in CLI help,
        # wizard choices and the Modelo 151 title; retain its exact case.
        "Beckham",
        "Sheets",
        "Windows",
        "macOS",
        "Homebrew",
        "Scoop",
        "PyPI",
        "Claude",
        # The provider sign-in guide names these AI clients by product name.
        "Codex",
        "Antigravity",
        # These lowercase provider IDs are shown in CLI provider-help
        # examples across current locales; preserve the canonical IDs.
        "claude",
        "antigravity",
        "codex",
        # AuthProviderKind.CERTIFICATE is an untranslated provider ID in
        # certificate-path diagnostics and authentication provider help.
        "certificate",
        "snapshot",
        "snapshots",
        "Snapshots",
        "bucket",
        "buckets",
        "OAuth",
        "DEHú",
        # These Catalan forms are used in current operator-facing locale
        # prose: impatriats in wizard.yml/profile.yml and modelo schemas;
        # reembolcallen and oblides in flows.yml; tipada/tipades in cli.yml,
        # application.yml and translated reference pages; bloquejants in
        # cli.yml/application.yml and verification-reports.po; Subclau in
        # profile.yml and modelo schemas. The pinned Catalan dictionary
        # rejects each exact form, so enroll only these observed spellings.
        "impatriats",
        "impatriat",
        "reembolcallen",
        "oblides",
        "tipada",
        "tipades",
        "bloquejants",
        "Subclau",
        # Current Catalan prose attests inclusiva in cli.yml, tipat in
        # application.yml, idempotència in application.yml, and
        # subcomandament/coteig/indiques in cli.yml and wizard.yml.
        # The documentation also uses tipats and subpaquets in
        # reference/registry-legal-api.po and architecture/index.po.
        # The Spanish Modelo 130 guide retains the tax label minoración.
        "minoración",
        "inclusiva",
        "tipat",
        "tipats",
        "idempotència",
        "subcomandament",
        "coteig",
        "indiques",
        # practiques is the second-person singular present of practicar,
        # used in cli.yml's Catalan guidance about withholding practice.
        # It is not the accented noun pràctiques.
        "practiques",
        # recapitulativa is standard Catalan terminology, attested by the
        # Modelo 349 catalogue and its translated operator documentation.
        "recapitulativa",
        # The CLI documents AEAT's literal census period values; preserve
        # these Spanish protocol spellings alongside Catalan explanation.
        "alta",
        "modificacion",
        "baja",
        "comunicacion",
        "variacion",
        # Catalan CLI help names the ledger subcommand in its command
        # examples and operator instructions; preserve that exact token.
        "ledger",
        # Runtime catalogue prose and command examples use these exact
        # technical tokens: `aeat`/`config`/`flags`/`status` in setup and
        # authentication instructions; `hash`/`payload` in storage errors;
        # `backend` and `runtime` in repository and storage diagnostics.
        # Keep the observed lowercase forms and language scope. These are
        # not spelling families or exceptions to ordinary Catalan prose.
        "aeat",
        "config",
        "flags",
        "status",
        "hash",
        "payload",
        "backend",
        "runtime",
        # The AEAT CLI namespace is written ``auth`` in command examples.
        "auth",
        # These exact Catalan forms are valid but absent from the pinned
        # dictionary: sublímit in a reduction warning, preomplert in
        # filing-record guidance, and reanomenament in work guidance.
        # reprenable describes a session that can be resumed.
        "sublímit",
        "preomplert",
        "reanomenament",
        "reprenable",
        # The key's label on a Spanish keyboard:
        "Supr",
        # The setup message's term for the network setting:
        "proxy",
        # The log viewer's own words for its source and its level:
        "logger",
        "Info",
        # The title of a Spanish ministerial order, as cited:
        "Orden",
        # The name of the invoicing-system verification regime of Real
        # Decreto 1007/2023 (written VERI*FACTU in the regulation):
        # https://www.boe.es/buscar/act.php?id=BOE-A-2023-24840
        "Verifactu",
    }
)
