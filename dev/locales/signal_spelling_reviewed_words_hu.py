"""Reviewed exact Hungarian dictionary gaps used by the locale spelling audit."""

from __future__ import annotations

REVIEWED_HUNGARIAN_SPELLINGS: frozenset[str] = frozenset(
    {
        # Hungarian accounting and software terminology in primary sources:
        # https://www.allamkincstar.gov.hu/nem-lakossagi-ugyek/kozponti-koltsegvetes-vegrehajtasat-tamogato-rendszer-kkvtr--ifmis1/oktatasi-anyagok/3_kotelezettsegvallalas/3.3_bizonylatzaras-zaras-evvaltas/%24rppid0x1602400x13_pageNumber/numeral
        # https://www.nefmi.gov.hu/letolt/minisz/eves_beszamolo_2007/debreceni_egyetem.pdf
        # https://www.posta.hu/static/internet/download/PUSZ_Archiv_PUSZ_teljes_20160701_20160703.pdf
        # https://learn.microsoft.com/hu-hu/dotnet/standard/commandline/syntax
        # https://learn.microsoft.com/hu-hu/connectors/todoconsumer/
        "áthozata",
        "áthozatra",
        "áthozatokat",
        "alparancsok",
        "teendőlista",
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
        # Exact Hungarian case forms of the named product, people,
        # territories and retained AEAT terms in current guidance.
        # Hungarian spelling rules for proper names and final-vowel length:
        # https://www.helyesiras.mta.hu/helyesiras/default/akh12
        # Official territory names: https://www.ine.es/daco/daco42/codmun/cod_provincia.htm
        # https://www.euskadi.eus/what-is-basque-country/web01-ejeduki/en/
        "Cadrumóról",
        "Bizkaiának",
        "Gipuzkoának",
        "Navarrának",
        "Navarrában",
        "Anától",
        "Anának",
        "Anára",
        "Rentánál",
        "Rentára",
        "Rentához",
        "Tributariának",
        "Tributariával",
        "Tributariához",
        "Timbrével",
        "Macre",
        "prorratának",
        "prorratához",
        "prorratájára",
        "altával",
        "complementariát",
        "soportadót",
        # Exact native technical and domain terms in current guidance.
        # https://real-eod.mtak.hu/2328/134/2kotet_1.pdf
        # https://www.ksh.hu/statszemle_archive/2008/2008_04/2008_04_001.pdf
        # https://repo.lib.semmelweis.hu/bitstream/handle/123456789/6974/pulayattila.d_DOIs.pdf?sequence=1
        # https://www.sztnh.gov.hu/sw/static/file/202402-szemle.pdf
        # https://aol.mnl.gov.hu/adatbazis/urbaria-et-conscriptiones/adatlap/10275
        # https://eur-lex.europa.eu/legal-content/HU/TXT/PDF/?uri=CELEX%3A32003R1785
        # https://learn.microsoft.com/hu-hu/windows/win32/shell/scriptable-shell-objects-roadmap
        # https://learn.microsoft.com/hu-hu/fabric/extensibility-toolkit/setup-guide
        # https://hub.hellowp.io/hu/plugins/wp-all-import-pro/
        # https://support.microsoft.com/hu-hu/office/collab-files/office-document-cache-settings
        # https://mnbprogram.bme.hu/wp-content/uploads/2021/10/1_2_4_Tanulmany_AdversarialTamadasokAck.pdf
        "ellenaláírás",
        "imputáció",
        "imputációhoz",
        "bájtokból",
        "főrovat",
        "borostyánsárgára",
        "Szkriptelt",
        "szkriptelhető",
        "szkriptelheted",
        "gyorsítótárazza",
        "regularizációs",
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
        "factura",
        "simplificada",
        "simplificadához",
        "rectificativának",
        "rectificativát",
        "Borradort",
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
        # The key's label on a keyboard:
        "Delete",
        # The log viewer's own words for its source and its level:
        "logger",
        "Info",
        # Spanish legal names kept as cited: estimación objetiva por módulos, LIS art. 12.3 entities, an Orden:
        "módulos",
        "sociedades",
        "explotaciones",
        "asociativas",
        "Orden",
        # A formula's function name and a depreciation method's stored token, both shown as written:
        "max",
        "linear",
        # The name of the invoicing-system verification regime of Real
        # Decreto 1007/2023 (written VERI*FACTU in the regulation):
        # https://www.boe.es/buscar/act.php?id=BOE-A-2023-24840
        "Verifactu",
    }
)
