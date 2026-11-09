"""Reviewed exact English dictionary gaps used by the locale spelling audit."""

from __future__ import annotations

# These ordinary English technical/domain terms are absent from the pinned
# dictionary-en-gb data, but are attested in the canonical English catalogue:
# counterparty/withholdings in modelo/schema/347.yml and 220.yml,
# lifecycle/namespace/preflight in errors.yml and application.yml,
# cadastral in modelo/schema/714.yml, handoff in cli.yml, and OAuth in
# adapters.yml. Keep only the observed spellings and capitalisation.
REVIEWED_ENGLISH_SPELLINGS: frozenset[str] = frozenset(
    {
        # English legal and administrative usage, including real fostering
        # and signing roles in the operator interface:
        # https://www.merriam-webster.com/dictionary/declarant
        # https://assets.publishing.service.gov.uk/media/64ad6414269c83000c8f5e5a/EWCO_Amendment_Request_Form_v1.0_Published_12.07.2023.pdf
        # https://regs.maryland.gov/us/md/exec/comar/07.05.03.05
        "declarant",
        "Declarant",
        "declarants",
        "Declarants",
        "countersigner",
        "Preadoptive",
        # British Python usage, and AEAT's own English income manual:
        # https://bugs.python.org/msg275615
        # https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2023/ManualRenta2023_en_gb.pdf
        "deserialised",
        "Impatriate",
        # Technical forms in resource, security, import and model prose.
        # https://learn.microsoft.com/en-us/windows/win32/menurc/common-resource-attributes
        # https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/deletingundecryptablepasswordsenabled
        # https://learn.microsoft.com/en-us/visualstudio/debugger/debug-using-the-just-in-time-debugger
        # https://learn.microsoft.com/en-us/power-apps/maker/data-platform/data-platform-import-export
        # https://analysisfunction.civilservice.gov.uk/careers/role-profiles-and-career-pathways/role-profile-econometric-modeller/
        # https://www.gov.uk/government/publications/telecoms-supply-chain-diversification-report-and-recommendations
        # https://learn.microsoft.com/en-us/visualstudio/extensibility/visual-cpp-project-extensibility
        # https://learn.microsoft.com/en-gb/azure/communication-services/resources/troubleshooting/voice-video-calling/troubleshooting-codes
        "discardable",
        "undecryptable",
        "unhandled",
        "untrusted",
        "Unmapped",
        "computable",
        "Telecoms",
        "upgrader",
        "Subcode",
        "Sectorised",
        # https://www.euskadi.eus/contenidos/informacion/octe/es_def/adjuntos/072024_GMB_Basque_tax_and_financial_Glossary.pdf
        "Foral",
        # https://www.merriam-webster.com/dictionary/unremitted
        # https://www.merriam-webster.com/dictionary/domiciliation
        # https://www.merriam-webster.com/dictionary/ungrounded
        # https://www.merriam-webster.com/dictionary/regenerable
        "unremitted",
        "Unremitted",
        # https://dictionary.cambridge.org/dictionary/english/unbundle
        # https://dictionary.cambridge.org/dictionary/english/derogation
        "unbundled",
        "derogations",
        "domiciliation",
        "ungrounded",
        "regenerable",
        # Exact English legal-note dictionary gaps, independently attested:
        # https://www.merriam-webster.com/dictionary/transitorily
        # https://www.merriam-webster.com/dictionary/unseizable
        # https://www.merriam-webster.com/dictionary/registrable
        # https://www.merriam-webster.com/dictionary/uncollectible
        # https://www.merriam-webster.com/dictionary/unapplied
        # https://www.merriam-webster.com/legal/sublessee
        "transitorily",
        "unseizable",
        "registrable",
        "uncollectible",
        "unapplied",
        "sublessee",
        # Technical prose forms used in the project documentation and UI.
        # https://learn.microsoft.com/en-us/dynamics365/guidance/implementation-guide/extend-your-solution-guidance-product-fo
        # https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/data-entities/dual-write/dual-write-async-faq
        # https://learn.microsoft.com/en-us/previous-versions/windows/desktop/htmlhelp/creating-a-cascading-style-sheet
        # https://learn.microsoft.com/en-us/windows-server/storage/storage-migration-service/cutover
        # https://learn.microsoft.com/en-us/windows/win32/termserv/scriptable-virtual-channels
        # https://learn.microsoft.com/en-us/windows/win32/tapi/handoffs-ovr
        # https://learn.microsoft.com/en-us/ecdn/troubleshooting/troubleshoot-ecdn-performance-issues
        # https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-pacemaker-basics
        # https://learn.microsoft.com/en-us/uwp/api/windows.networking.connectivity.wwannetworkregistrationstate
        "updatable",
        "toolset",
        "cutover",
        "ungrouped",
        "stylesheet",
        "misconfigured",
        "unresolvable",
        "deregistered",
        "Deregistered",
        "scriptable",
        "unpromoted",
        "handoffs",
        # Exact territory names used in the IVA geographic source notes:
        # https://www.gov.uk/government/publications/geographical-names-and-information
        # https://www.boe.es/biblioteca_juridica/abrir_pdf.php?id=PUB-PB-2025-386
        "Akrotiri",
        "Dhekelia",
        "Balears",
        # AEAT's exact names for a declaration box and a Renta draft:
        # https://sede.agenciatributaria.gob.es/Sede/casilla.shtml
        "casilla",
        "borrador",
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
        # Exact forms used in the referenced technical documentation:
        # https://learn.microsoft.com/en-us/windows/win32/lwef/-search-2x-wds-fromcommandline
        # https://learn.microsoft.com/en-us/biztalk/core/orchestration-dehydration-and-rehydration
        # https://learn.microsoft.com/en-us/visualstudio/data-tools/typed-vs-untyped-datasets
        "rescans",
        "rehydration",
        "untyped",
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
        "Antigravity",
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
        "factura",
        "simplificada",
        "devengo",
        "rectificación",
        "complementaria",
        "solicitud",
        "Solicitud",
        "solicitudes",
        "solicitante",
        "representante",
        "Representante",
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
        # Plural of the file format, in the document import prompt:
        "PDFs",
        # The ledger's action that takes a row's mark off again:
        "Unmark",
        # AEAT's own names for the declaration kinds:
        "Complementaria",
        "Rectificativa",
        "Sustitutiva",
        # LIS art. 12.3 names these entities in Spanish:
        "sociedades",
        "laborales",
        "explotaciones",
        "asociativas",
        "prioritarias",
        # The recurring Spanish persona's name in the lifecycle guides:
        "García",
        "López",
        # The island named by the Modelo 100 territorial-deduction key
        # (Ley 35/2006, art. 68.4 and additional provision 57):
        # https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764
        "Palma",
        # The name of the invoicing-system verification regime of Real
        # Decreto 1007/2023 (written VERI*FACTU in the regulation):
        # https://www.boe.es/buscar/act.php?id=BOE-A-2023-24840
        "Verifactu",
    }
)
