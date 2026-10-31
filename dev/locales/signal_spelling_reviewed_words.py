"""Reviewed exact dictionary gaps used by the locale spelling audit."""

from __future__ import annotations

# Exact Spanish dictionary gaps in the canonical legal references: IVA flow
# notes use enrutamiento, transmitente and registrales; IS uses deducibilidad
# and extracontables; IRPF uses autotaxis, subclaves, reinversión and aportante.
# Modelo 234/379 uses transfronterizos, Modelo 763 uses plurianuales, and Modelo
# 592 uses reutilizables. IRPF/Modelo 136 quoted wording uses autoliquidar.
# Enrutamiento is also attested in IGN's normalized ISO/TC211 glossary:
# https://www.ign.es/web/ide-glosario-panhispanico
# Keep this lexical subset separate from literal option IDs and casing aliases.
REVIEWED_SPANISH_LEGAL_SPELLINGS = frozenset(
    {
        "enrutamiento",
        "deducibilidad",
        "transmitente",
        "transfronterizos",
        "plurianuales",
        "autotaxis",
        "subclaves",
        "extracontables",
        "registrales",
        "reinversión",
        "aportante",
        "autoliquidar",
        "reutilizables",
    }
)
# These ordinary English technical/domain terms are absent from the pinned
# dictionary-en-gb data, but are attested in the canonical English catalogue:
# counterparty/withholdings in modelo/schema/347.yml and 220.yml,
# lifecycle/namespace/preflight in errors.yml and application.yml,
# cadastral in modelo/schema/714.yml, handoff in cli.yml, and OAuth in
# adapters.yml. Keep only the observed spellings and capitalisation.
REVIEWED_LOCALE_SPELLINGS: dict[str, frozenset[str]] = {
    "en": frozenset(
        {
            # Exact territory names used in the IVA geographic source notes:
            # https://www.gov.uk/government/publications/geographical-names-and-information
            # https://www.boe.es/biblioteca_juridica/abrir_pdf.php?id=PUB-PB-2025-386
            "Akrotiri",
            "Dhekelia",
            "Balears",
            # A redaction can also be an edited version of a text:
            # https://interparestrust.org/terminology/term/redaction
            "redaction",
            "redactions",
            # Exact technical forms used in storage and networking guidance:
            # https://docs.aws.amazon.com/sagemaker/latest/dg/sm-console-domain-resources-view.html
            # https://learn.microsoft.com/en-us/entra/architecture/recoverability-overview
            # https://docs.aws.amazon.com/vpc/latest/reachability/what-is-reachability-analyzer.html
            # https://docs.aws.amazon.com/kms/latest/APIReference/API_Decrypt.html
            "untagged",
            "recoverability",
            "reachability",
            "decrypts",
            # Exact forms attested in Microsoft documentation, the IRS and
            # European Commission tax guidance, and the cited dictionaries:
            # https://learn.microsoft.com/en-us/dynamics365/customer-insights/journeys/real-time-marketing-form-prefill
            # https://learn.microsoft.com/en-us/graph/api/approval-get?view=graph-rest-1.0
            # https://learn.microsoft.com/en-us/dotnet/api/java.time?view=net-android-36.0
            # https://learn.microsoft.com/en-us/purview/edisc-ref-partially-indexed-items
            # https://support.microsoft.com/en-us/onedrive/how-to-remove-an-account-in-onedrive
            # https://www.irs.gov/pub/irs-pdf/p1693_11.pdf
            # https://www.irs.gov/irm/part5/irm_05-009-013r
            # https://taxation-customs.ec.europa.eu/system/files/2021-06/taxation_trends_2021_country_chapter_luxembourg.pdf
            # https://files.ofsted.gov.uk/v1/file/1831493
            # https://dictionary.cambridge.org/dictionary/english/checkable
            # https://www.collinsdictionary.com/dictionary/english/unsupplied
            "approver",
            "checkable",
            "durations",
            "impatriate",
            "namespaces",
            "preadoptive",
            "prefill",
            "Prefill",
            "prefilled",
            "unassessed",
            "unindexed",
            "unlink",
            "unsupplied",
            "withholder",
            "withholders",
            # Exact native, technical and retained tax forms attested in
            # _data/terminology/concepts; no new casing or inflections implied.
            "embeddings",
            "artifacts",
            "normalized",
            "indexable",
            "preprocessor",
            "preprocessors",
            "materializes",
            "redemptions",
            "regularization",
            "capitalization",
            "integrations",
            "modelo",
            "Modelo",
            "Gmail",
            # Exact names in the English source: DEHú notification help and
            # Bizum payment entries; macOS/Homebrew/PyPI download/setup docs;
            # OpenSSL/PowerShell report-verification guidance and Pagefind
            # search terminology definitions.
            # These names are absent from the pinned English dictionary too.
            "DEHú",
            "macOS",
            "Homebrew",
            "PyPI",
            "OpenSSL",
            "PowerShell",
            "Pagefind",
            "counterparty",
            "Counterparty",
            "withholdings",
            "Withholdings",
            "lifecycle",
            "Lifecycle",
            # British spelling used by sector-based IVA apportionment errors.
            "sectorised",
            "namespace",
            "Namespace",
            "preflight",
            "Preflight",
            "cadastral",
            "Cadastral",
            "handoff",
            "Handoff",
            "OAuth",
            # These exact English forms occur in current operator catalogues:
            # counterparties/Counterparties and Depreciable in common.yml,
            # Recapitulative in Modelo 349's title, and deregistration in
            # common.yml, cli.yml and Modelo schemas. Retain observed case only.
            "counterparties",
            "Counterparties",
            "Recapitulative",
            "deregistration",
            "Deregistration",
            "Depreciable",
            # Genuine prose in adapters.yml (unparseable), application.yml
            # (idempotency, supersession, fileable), and cli.yml (reviewable,
            # resumable). reauthenticate also occurs as ordinary prose in
            # docs/how-to/authenticate-with-aeat.md, not only as a method name.
            "reauthenticate",
            "unparseable",
            "idempotency",
            "supersession",
            "reviewable",
            "fileable",
            "resumable",
            # Established CLI and application vocabulary, attested in the
            # English operator catalogues: provider names (claude,
            # antigravity), secure-storage and key terms (keychain,
            # unencrypted, keypair), and standard implementation concepts.
            # Preserve only the observed forms and casing.
            "claude",
            "antigravity",
            "keychain",
            "unencrypted",
            "keypair",
            "auditable",
            "backend",
            "Backend",
            "validator",
            "validators",
            "enum",
            "Enum",
            "datetime",
            "filesystem",
            "subcommand",
            "stdin",
            "json",
            "csv",
            "tsv",
            "xls",
            "xlsm",
            "xlsx",
            "loopback",
            # Authored documentation uses the valid US English spelling too.
            "behavior",
            # File format acronym and the documented adjective for a file
            # that can be uploaded; retain only these exact observed forms.
            # https://docs.python.org/3/library/zipfile.html
            # https://www.mediawiki.org/wiki/Extension:Page_Forms/Input_types
            "ZIPs",
            "uploadable",
            # Plural of the standard identifier acronym in runtime access help:
            # https://docs.python.org/3/library/uuid.html
            "UUIDs",
            # These exact source forms are accepted by the English (US) SCOWL
            # reference dictionary but absent from our pinned en-GB data.
            # Keep them finite: do not infer arbitrary -ize forms or casing.
            # https://wordlist.aspell.net/
            "Adapters",
            "afterward",
            "amortized",
            "authorizes",
            "capitalized",
            "categorized",
            "center",
            "color",
            "enrollments",
            "finalizes",
            "judgment",
            "memorize",
            "modeled",
            "notarized",
            "personalized",
            "recognizable",
            "serializes",
            "specialized",
            "specialty",
            "summarizes",
            # Existing English prose also uses these valid spelling variants:
            # advisor in disclaimer/filing guidance; adapter(s) in architecture
            # and service help; artifact in authority/API docs; amortization
            # and formalization/formalized in legal notes; and proration in
            # Modelo diagnostics. Keep only the observed lowercase forms.
            "advisor",
            "adapter",
            "adapters",
            "artifact",
            "amortization",
            "proration",
            "formalization",
            "formalized",
            # Exact software prose in current sources: Quickstart/quickstart
            # guide links, subpackages/docstrings in architecture and authoring
            # docs, plaintext/decrypting/decrypted in custody/export guidance,
            # and schemas/invariants in CLI docs and validation diagnostics.
            # Quickstart is also the setuptools guide's own heading:
            # https://setuptools.pypa.io/en/latest/userguide/quickstart.html
            "Quickstart",
            "quickstart",
            "subpackages",
            "docstrings",
            "plaintext",
            "decrypting",
            "decrypted",
            "schemas",
            "invariants",
            # Exact English legal/operator prose: Modelo 349 guidance uses
            # recapitulative, ledger help uses unestablished/linkable, and
            # legal references use unamended/citable/exigibility/intracommunity
            # and telematically. EU legislation uses intracommunity, and its
            # legislation directory uses exigibility; AEAT English guidance
            # likewise uses telematically. These are dictionary gaps, with no
            # permission to accept new inflections or arbitrary capitalization.
            "recapitulative",
            "unamended",
            "citable",
            "unestablished",
            "linkable",
            "exigibility",
            "intracommunity",
            "telematically",
            # The English catalogue and authored docs also use these exact US
            # forms, absent from the pinned British dictionary: common.yml's
            # window actions, application.yml's synchronization/finalization
            # prose, errors.yml's authorization diagnostics, wizard.yml's
            # enrollment prompts, and docs/how-to/censo-update.md. Preserve
            # only the spellings and capitalization observed by the audit.
            "Maximize",
            "Minimize",
            "Organize",
            "Initialize",
            "Summarize",
            "summarize",
            "finalized",
            "synchronization",
            "Synchronization",
            "synchronizing",
            "synchronize",
            "enrollment",
            "Enrollment",
            "enroll",
            "Enroll",
            "Unrecognized",
            "recognized",
            "authorized",
            "authorize",
            "authorization",
            "serialization",
            "localized",
            "localization",
            "normalization",
            # These exact lowercase names occur in translated operator
            # commands and English CLI diagnostics: ``aeat`` is the literal
            # command root, ``auth``/``config`` are command namespaces, and
            # Auth/Config are displayed diagnostic section labels.
            "aeat",
            "auth",
            "Auth",
            "config",
            "Config",
            # AEAT legal vocabulary is deliberately preserved in English
            # operator messages where the Spanish term names a filing
            # procedure, status, or tax concept. These exact forms occur in
            # adapters.yml, application.yml, common.yml, and cli.yml; keep
            # the enrollment narrow and language-scoped.
            "comparecencia",
            "Sede",
            "certificado",
            "autoliquidación",
            "rectificativa",
            "rectificación",
            "complementaria",
            "solicitud",
            "ejercicio",
            "cuota",
            "prorrata",
            "Reglamento",
            "apoderado",
            "foral",
            "Navarra",
            "Beckham",
            "impatriado",
            # The Spanish Modelo 130 adjustment term is retained verbatim in
            # translated operator guidance and official legal references.
            "minoración",
            "autoconsumo",
        }
    ),
    "es": frozenset(
        {
            # RAE native nouns used in statistical and typed-data documentation.
            # https://dle.rae.es/extrapolaci%C3%B3n
            # https://dle.rae.es/rehidrataci%C3%B3n
            "extrapolación",
            "rehidratación",
            # RAE records both this unit and its ordinary plural:
            # https://temporalraeweb.rae.es/dhle/megabyte
            "megabytes",
            # The Spanish technical and fiscal forms are attested by Microsoft
            # and AEAT, respectively; do not infer unobserved inflections.
            # https://learn.microsoft.com/es-es/azure/architecture/patterns/retry
            # https://learn.microsoft.com/es-es/azure/architecture/microservices/design/api-design
            # https://www3.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_Resto_Mod/archivos/dr995_2006.pdf
            "idempotencia",
            "reintentos",
            "sectorizado",
            "serialización",
            # NCI's Spanish dictionary uses this exact plural of heredable:
            # https://www.cancer.gov/espanol/publicaciones/diccionarios/diccionario-cancer/def/heredable
            "heredables",
            # Exact native, technical and retained tax forms attested in
            # _data/terminology/concepts; no new casing or inflections implied.
            "autorrepercute",
            "superreducido",
            "transfronterizas",
            "indexador",
            "preprocesador",
            "preprocesadores",
            "terminológica",
            *REVIEWED_SPANISH_LEGAL_SPELLINGS,
            # The unchanged surname names the impatriate regime in CLI help,
            # wizard choices and the Modelo 151 title; retain its exact case.
            "Beckham",
            # Singular taxpayer term in the same regime-help diagnostics.
            "impatriado",
            "Google",
            "Gmail",
            "Drive",
            "Python",
            "Enter",
            "Sheets",
            "Windows",
            "macOS",
            "Excel",
            "SQLite",
            "Homebrew",
            "Scoop",
            "PyPI",
            "Claude",
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
            # Initial word of the live borrador/expedientes/notifications help.
            "Snapshots",
            "bucket",
            "buckets",
            "OAuth",
            "DEHú",
            # Spanish CLI and runtime prose uses ``arts.`` as the legal
            # abbreviation for artículos (LIVA/RIS citations), ``hash`` for
            # content and storage-state digests, and ``backend`` for the
            # encrypted calculation/storage implementation. These are exact
            # technical terms used in src/cadrumo/locales/es/{cli,application,
            # common,adapters}.yml; do not infer other English terms.
            "arts",
            "hash",
            "backend",
            "desactualizado",
            "Desactualizado",
            # Current filing-calendar prose uses the plural form
            # desactualizados for stale census facts; enroll the observed
            # inflection without admitting a general suffix rule.
            "desactualizados",
            "recalcular",
            "Recalcular",
            "recálculo",
            "recalcula",
            "introdúcelo",
            "tributación",
            "contrafirmado",
            "intracomunitarias",
            "preadoptivo",
            "registral",
            "Confírmalo",
            "revísalo",
            "intracomunitaria",
            "recapitulativa",
            "minoración",
            "Minoración",
            # AEAT legal titles use the exact capitalized tax label
            # Minoración; the IVA and Spanish legal texts also use
            # autoconsumo as a standard tax-domain compound.
            "autoconsumo",
            "previsualiza",
            "sobrescritura",
            # The Spanish binding-resolution help and evidence reference use
            # sobrescrituras for user-supplied overrides.
            "sobrescrituras",
            "intracomunitario",
            "tipados",
            "autenticarte",
            "impatriados",
            "reintentar",
            # Exact operator prose in application.yml and cli.yml: informal
            # imperatives confírmalo/Combínalo, idempotente for repeated writes,
            # bloqueante/bloqueantes for findings, tipado/tipada for contracts,
            # and previsualizar for inspecting proposed values before writing.
            "confírmalo",
            "Combínalo",
            # Repeated operator instructions attest these Spanish forms in
            # runtime catalogues: Reintentar as a retry action, Reintenta and
            # Configúralo in Cl@ve guidance, Previsualiza for dry-run help,
            # sectorizada in IVA prorrata errors, and contrafirma in review
            # package help. Enroll only the exact observed spellings.
            "Reintentar",
            "Reintenta",
            "Configúralo",
            "Previsualiza",
            "sectorizada",
            "contrafirma",
            "idempotente",
            "bloqueante",
            "bloqueantes",
            "tipado",
            "tipada",
            "previsualizar",
            # AEAT census-form values exposed by CLI period help are exact
            # token spellings (alta, modificacion, baja), not running prose.
            "alta",
            "modificacion",
            "baja",
            # Current Spanish CLI help uses token/tokens for AEAT period and
            # scope values, app as the literal command namespace, and ledger
            # as the literal subcommand. Keep these runtime forms exact.
            "token",
            "tokens",
            "Token",
            "Tokens",
            "app",
            "ledger",
            # Exact Spanish operator-catalogue forms: resolutor names a
            # registered resolver; Intro is the terminal's displayed key;
            # flags and config name CLI options and command namespaces.
            "resolutor",
            "Intro",
            "flags",
            "config",
            # Lowercase ``aeat`` is the literal command root retained in
            # Spanish operator help and command examples.
            "aeat",
            # ``auth`` is retained as a command namespace in CLI guidance.
            "auth",
            # Current Modelo 390 help and workbench guidance use the exact
            # AEAT tax-domain term exoneración.
            "exoneración",
            # Repeated Spanish operator and tax-domain prose uses these exact
            # forms: operandos in calculation explanations, fiscalmente in tax
            # rules, direccionado/a in content-addressing docs, cotitular in
            # account labels, subclave/atribuyente in Modelo 184 fields, and
            # pymes in legal-form guidance. Keep each observed form exact.
            "operandos",
            "Operandos",
            "fiscalmente",
            "direccionado",
            "direccionados",
            "cotitular",
            "Cotitular",
            "subclave",
            "Subclave",
            "atribuyente",
            "pymes",
            "reintentarlo",
            "reintentado",
            # These exact informal imperatives and clitic forms recur in
            # operator instructions across the Spanish runtime and translated
            # how-to pages (application.yml, cli.yml, common.yml, and the
            # Spanish how-to catalogue). Enroll observed casing only; this
            # does not admit other clitic or imperative forms.
            "configurarlo",
            "Escríbelo",
            "escríbelo",
            "reintenta",
            "revísala",
            "Revísala",
            "escríbela",
            "Escríbela",
            "actívala",
            "regístrala",
            "Regístrala",
            "impórtalo",
            "Impórtalo",
            "confírmala",
        }
    ),
    "ca": frozenset(
        {
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
        }
    ),
    "hu": frozenset(
        {
            # The lifecycle guides retain the Spanish persona's original name.
            "Ana",
            "García",
            "López",
            # The payment name takes the assimilated Hungarian instrumental -val:
            # https://helyesiras.mta.hu/helyesiras/default/akh12
            "Bizummal",
            # All three forms are accepted by reference Hunspell with the pinned
            # original dictionary, but not by the pinned spylls implementation.
            "felülvizsgálati",
            "kisvállalati",
            "tartalmi",
            # These additional observed native forms were checked individually
            # with reference Hunspell against our exact vendored 1.8 dictionary.
            # spylls misses their compounds, inflections or initial capitals.
            # Do not accept arbitrary unaccented words or general suffixes.
            "Adatvédelmi",
            "Felülvizsgálati",
            "Késedelmi",
            "Nagyvállalati",
            "Pénzforgalmi",
            "adatbázisbájtjait",
            "adatvédelmi",
            "ellenőrzik",
            "ellenőrzöd",
            "ellenőrzöl",
            "előtakarékossági",
            "jövedelmi",
            "komponensbájtot",
            "nagyvállalati",
            "netót",
            "percentiliseit",
            "pozicionális",
            "pénzforgalmi",
            "áthozatot",
            "érintetti",
            "örökbefogadási",
            # Attested Hungarian byte forms, not a general suffix rule:
            # https://people.inf.elte.hu/szlavi/Magamnak/C%2B%2B/ansi_Cpp.pdf
            # https://fbenjih.web.elte.hu/Algoritmusok%20%C3%A9s%20adatszerkezetek%202/El%C5%91ad%C3%A1s%20%28%C3%81sv%C3%A1nyi%29/%C3%81sv%C3%A1nyi%20jegyzet.pdf
            # https://mek.oszk.hu/24200/24233/pdf/24233_1.pdf
            "bájtokkal",
            "bájtjait",
            "bájtnál",
            # Microsoft uses this exact Hungarian possessive byte-count form:
            # https://learn.microsoft.com/hu-hu/windows-hardware/drivers/debugger/using-poolmon-to-find-a-kernel-mode-memory-leak
            "bájtszámát",
            # Microsoft uses this Hungarian spelling of the storage unit:
            # https://learn.microsoft.com/hu-hu/powershell/scripting/lang-spec/chapter-02
            "megabájt",
            # Exact native, technical and retained tax forms attested in
            # _data/terminology/concepts; no new casing or inflections implied.
            "artefaktumokból",
            "artefaktumba",
            "artefaktumok",
            "szabadfoglalkozásúak",
            "prorratából",
            "prorratát",
            "rentát",
            "recargo",
            "autónomos",
            "presentado",
            "modelo",
            "Modelo",
            "Gmail",
            "Drive",
            "Sheets",
            "Windows",
            "macOS",
            "SQLite",
            "Homebrew",
            "Scoop",
            "PyPI",
            "Claude",
            # These lowercase provider IDs are shown in CLI provider-help
            # examples across current locales; preserve the canonical IDs.
            "claude",
            "antigravity",
            "codex",
            # AuthProviderKind.CERTIFICATE is an untranslated provider ID in
            # certificate-path diagnostics and authentication provider help.
            "certificate",
            "OAuth",
            "DEHú",
            # These exact Hungarian forms are attested in common.yml/errors.yml
            # and translated documentation: ellenőrzi/Ellenőrzi,
            # Intraközösségi (wizard.yml, profile.yml, cli.yml and common.yml),
            # szkriptelt (flows.yml and application.yml), Ugrás/ugrás,
            # szektorizált and munkajegység. Hungarian final vowel lengthening
            # is grammatical in Intraközösségi; enroll only the observed form.
            "Intraközösségi",
            "ellenőrzi",
            "Ellenőrzi",
            "szkriptelt",
            "Ugrás",
            "ugrás",
            "szektorizált",
            "munkajegység",
            # Hungarian ISO date masks use ÉÉÉÉ for the year component across
            # CLI, wizard, profile and ledger prompts. This exact notation is
            # not ordinary prose or a license for other repeated-letter forms.
            "ÉÉÉÉ",
            # Direct Hungarian inflections of the product name and the AEAT
            # term "modelo" lengthen final o to ó (AkH. 216(a)). These are
            # the exact forms attested by the locale audit; do not infer other
            # roots or suffixes. Sentence-final periods are retained by the
            # Hungarian tokenizer and are enrolled only where observed.
            "Cadrumóban",
            "Cadrumónak",
            "Cadrumón",
            "Cadrumóban.",
            "Cadrumót",
            "Cadrumóhoz",
            "Cadrumóhoz.",
            "Cadrumóba",
            "Cadrumót.",
            "Cadrumóval",
            "Cadrumóból",
            "Cadrumóba.",
            "Cadrumóra",
            "modeló",
            "modelók",
            "modelót",
            "modelóknál",
            "modelóhoz",
            "modelónál",
            "Modelókon",
            "modelódat",
            "modelóval",
            "modelónként",
            "modelókat",
            "modelókhoz",
            "modelóra",
            "modelónak",
            "modelóig",
            "Modelók",
            "modelótól",
            "modelóra.",
            # Ordinary Hungarian words absent from the pinned dictionary:
            # téged/őt in operator prose, bájtokat/bájtos in byte-handling
            # messages, and összegzése/összegzésével in summaries. Keep these
            # exact observed forms; do not enroll broader inflection patterns.
            "téged",
            "őt",
            "bájtokat",
            "bájtos",
            "összegzése",
            "összegzésével",
            # Additional exact ordinary forms attested in the current operator
            # catalogue: a confirmation prompt (Ellenőrzöd), byte descriptions
            # (bájtok/bájtban/bájtra/bájtként), and review/update prose.
            "Ellenőrzöd",
            "bájtok",
            "bájtban",
            "bájtra",
            "bájtként",
            "priorizálhatók",
            "megkísérléséhez",
            # Common Hungarian vocabulary attested in operator labels and
            # prose: summary/preset names, free-text reasons, byte references,
            # and the noun látás used in the LLM capability label.
            "Összegzés",
            "Előbeállítások",
            "Szabadszöveges",
            "bájtjaik",
            "bájtjainak",
            "bájtokhoz",
            "látás",
            # Modelo 130 documentation retains this Spanish tax label in
            # explanatory prose and legal citations.
            "minoración",
            # Spanish legal and jurisdiction names are retained in Hungarian
            # tax guidance: Navarra in common.yml/profile.yml/Modelo schemas,
            # Beckham in wizard.yml/profile.yml and the Modelo catalogue.
            # Keep the proper names exact and Hungarian-scoped.
            "Navarra",
            "Beckham",
            # The official Spanish AEAT name is retained in Hungarian docs;
            # the final Hungarian case ending is part of the observed token.
            "Agencia",
            "Estatal",
            "Administración",
            "Tributariánál",
            # Exact Hungarian terminology used in the current localized tax
            # catalogues: the compound stem hozzáadottérték, the adapted
            # prorrata inflections, HÉA's lowercase prose form, the common
            # intraközösségi adjective, and Baleár as part of Baleár-szigetek.
            # Keep these observed forms exact; they do not admit arbitrary
            # inflections or spelling variants.
            "hozzáadottérték",
            "Hozzáadottérték",
            "prorratája",
            "prorratájának",
            "héa",
            "intraközösségi",
            "Baleár",
            # Exact Hungarian catalogue forms that preserve the AEAT's
            # Spanish filing vocabulary (alta/modificacion, filing classes,
            # official document titles and tax-law terms). These spellings
            # are repeated across cli.yml, application.yml, errors.yml,
            # categories.yml and wizard.yml; retain the authored source form.
            "alta",
            "modificacion",
            "complementaria",
            "rectificativa",
            "Rectificativa",
            "cuota",
            "Reglamento",
            "Censal",
            "censal",
            "Certificado",
            "certificado",
            "Situación",
            "Sede",
            "sede",
            "retenciones",
            "Retenciones",
            "autoliquidación",
            "estimación",
            "compensación",
            # Project storage/ledger terminology occurs in Hungarian operator
            # text and CLI identifiers. Hungarian suffixes attach directly;
            # admit only the exact forms observed by this audit batch.
            "bucket",
            "bucket.",
            "bucketjéhez",
            "bucketet",
            "bucketje",
            "bucketjével",
            "bucketjével.",
            "buckethez",
            "bucketben",
            "bucketben.",
            "bucketnek",
            "bucketek",
            "ledger",
            "Ledger",
            "ledgerbe",
            "ledgerbe.",
            "ledgert",
            "ledgerben",
            "ledgerből.",
            "registry",
            "Registry",
            "registryben",
            "registryt",
            "registryjét",
            "registryje",
            "hash",
            "hashje",
            "sidecar",
            "sidecarja",
            "sidecarját.",
            "sidecarokat",
            "payload",
            "payloadját.",
            # ``atomikusan`` is an ordinary Hungarian adverb in local object
            # storage error prose; the pinned dictionary omits this valid form.
            "atomikusan",
            # Repeated Hungarian operator and calculation terms absent from
            # the pinned dictionary. Preserve only forms present in the
            # current audit; in particular, casilla remains the AEAT's
            # authority-named box term with attested Hungarian case endings.
            "alparancs",
            "többműszakos",
            "őrzésben",
            "őrzési",
            "profilőrzési",
            "imputációs",
            "casillához",
            "casillához.",
            "casillákat",
            "casillák",
            "casillát",
            "bájtjai",
            "kompozálódnak",
            # Exact Hungarian forms found in operator prose and the tax
            # catalogue. A manifest is called a manifeszt in Hungarian IT
            # usage; admit only the inflections actually present in source.
            "manifeszt",
            "manifesztjét",
            "manifesztjének",
            "manifesztje",
            "manifesztet",
            "manifesztjének.",
            "kisméretű",
            "forális",
            "Forális",
            "intrakomunitáris",
            "társaságiadó",
            "Társaságiadó",
            "gyorsparancs",
            # These are literal values or names in Hungarian CLI/help text:
            # option values and the command namespace stay untranslated.
            "aeat",
            "compensar",
            "devolver",
            "ingreso",
            "domiciliación",
            "config",
            # ``auth`` is a literal runtime command namespace in help text.
            "auth",
            "relation",
            "notifications",
            "LongPathsEnabled",
            "Decimal",
        }
    ),
}
