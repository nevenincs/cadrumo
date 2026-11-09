"""Reviewed exact Spanish dictionary gaps used by the locale spelling audit."""

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
REVIEWED_SPANISH_SPELLINGS: frozenset[str] = frozenset(
    {
        # Month abbreviations of the Spanish CLDR medium date format, which
        # the application writes dates in.
        "feb",
        "abr",
        "may",
        "jun",
        "jul",
        "ago",
        "sept",
        "oct",
        "nov",
        "dic",
        # Exact Spanish legal-note forms, never English fallback vocabulary.
        # DLE lemmas attest the listed forms or their regular gender,
        # plural, participle and -mente inflections:
        # https://dle.rae.es/cauci%C3%B3n
        # https://dle.rae.es/tautol%C3%B3gico
        # https://dle.rae.es/enrutado
        # https://dle.rae.es/autoritativo
        # https://dle.rae.es/exoneraci%C3%B3n
        # https://dle.rae.es/improcedente
        # https://dle.rae.es/reinvertir
        # https://dle.rae.es/enchufable
        # https://dle.rae.es/indisponible
        "caución",
        "tautológica",
        "enrutado",
        "autoritativo",
        "exoneraciones",
        "improcedentemente",
        "reinvertida",
        "enchufables",
        "indisponible",
        # Exact fiscal usage (domain attestation, not a DLE claim):
        # https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/criterio.aspx?id=00%2F04628%2F2009%2F00%2F0%2F1
        "autorrepercusión",
        # Exact native Spanish administrative usage, not a participle claim:
        # https://sede.mscbs.gob.es/ciudadanos/procAdministrativos.do?cod=3125710&tipo=detallar
        "cofinanciadoras",
        # Fiscal and technical prose attested by the tax-administration
        # association, the RAE, Python's glossary, and the software vendor.
        # https://www.ciat.org/Biblioteca/ConferenciasTecnicas/2010/Espanol/e-book_conferencia_paris_2010.pdf
        # https://dle.rae.es/heur%C3%ADstico
        # https://dle.rae.es/discrepante
        # https://docs.python.org/es/3/glossary.html
        # https://docs.python.org/es/3/c-api/init_config.html
        # https://tesiunamdocumentos.dgb.unam.mx/pd2001/299962/299962_A1.pdf
        # https://www.aistryx.com/es/legal/transparencia
        "diferimiento",
        "sublímite",
        "heurística",
        "discrepante",
        "Discrepante",
        "manejador",
        "inicialización",
        "recompilación",
        "derivable",
        "multicomponente",
        "notarizada",
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
        # The provider sign-in guide names these AI clients by product name.
        "Codex",
        "Antigravity",
        # The same guide names the Git version-control system.
        "Git",
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
        "Simplifícala",
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
        # Ordinary desktop terms in the document viewer, the asset categories and setup:
        "zoom",
        "Zoom",
        "Hardware",
        "proxy",
        # The log viewer's own words for its source and its level:
        "logger",
        "Info",
        # RAE Ortografía: an enclitic pronoun joins the imperative of acortar
        # (acorta + lo), which takes a written accent:
        # https://www.rae.es/ortografia/tilde-en-formas-verbales-con-pronombres-encliticos
        "acórtalo",
        # The name of the invoicing-system verification regime of Real
        # Decreto 1007/2023 (written VERI*FACTU in the regulation):
        # https://www.boe.es/buscar/act.php?id=BOE-A-2023-24840
        "Verifactu",
        # Proper names: the exit of the United Kingdom from the EU, which
        # titles the AEAT instructions cited for Modelo 349 country
        # prefixes, the scripting language and Apple's computer line:
        # https://es.wikipedia.org/wiki/Brexit
        # https://developer.mozilla.org/es/docs/Web/JavaScript
        # https://www.apple.com/es/mac/
        "Brexit",
        "JavaScript",
        "Mac",
        # The Spanish public administration's electronic signature
        # service, whose name the AEAT signature inbox reuses:
        # https://administracionelectronica.gob.es/ctt/portafirmas
        "Portafirmas",
    }
)
