---
tags: ["#audit", "#schema-driven-wizard-ux"]
date: 2026-05-13
modified: '2026-05-13'
related:
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# wizard ux transcripts — 2026-05-13

verbatim capture-only artefact. every block below is the literal stdout +
stderr + exit code produced by driving the redesigned ``aeat`` cli on the
``chore/eliminate-shims`` branch through a sandboxed runner. no
evaluation, opinion, or recommendation is recorded here — the
orchestrator owns that.

## sandbox mechanism

the project has no single ``aeat_home`` override. every storage path is
declared on ``aeat.core.config.Settings`` as its own env var (see
``src/aeat/core/config.py``). the sandbox redirects every persistence
root to a fresh ``tempfile.mkdtemp()`` directory, sets
``aeat_secret_store_backend=unsecured`` + ``aeat_allow_unencrypted=1``
so no os keychain prompt is required, and pins
``aeat_database_url`` to a per-scenario sqlite file. on windows, the
unsecured backend is the only way to run without dpapi prompting.

each scenario uses its own sandbox tmpdir; the b-section transcript
includes the full env-var dump.

## host environment

- platform: windows 11 pro 10.0.26200, powershell + git-bash hybrid
- python: 3.13.11 (uv-managed)
- typer: shipped with the project (uses click ``CliRunner`` for capture)
- aeat branch: ``chore/eliminate-shims``
- interactive prompts: the ``QuestionaryPrompter`` backend wraps
  ``questionary`` + ``prompt_toolkit``. on a git-bash terminal the
  default prompt_toolkit output backend (``Win32Output``) raises
  ``NoConsoleScreenBufferError`` because the terminal reports
  ``xterm-256color`` rather than a real windows console. interactive
  scenarios that require it are recorded twice: once via the
  click ``CliRunner`` (capturing the failure mode) and once via
  ``prompt_toolkit.input.create_pipe_input`` + ``DummyOutput`` (which
  bypasses the win32 backend and exercises the prompter end-to-end).

## capture harness

``var/ux-captures/harness.py`` drives every non-interactive scenario via
``typer.testing.CliRunner``. ``var/ux-captures/harness_c.py`` walks the
descriptor question-by-question and drives each prompt through
``QuestionaryPrompter`` + ``create_pipe_input`` so the prompts can be
read verbatim. ``var/ux-captures/harness_d_pipe.py`` exercises the
ctrl+c / unknown-choice probes the same way.


## SCENARIO A — Cold-start surface discovery (es)

```text


# SCENARIO A — Cold-start surface discovery (es locale)

===============================================================================
### A1. `aeat` (no args)
$ aeat
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Asistente para preparar declaraciones tributarias españolas

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Mostrar la versión del paquete y el     │
│                                     resumen del registro                    │
│ --format                      TEXT  Formato de salida para los resultados   │
│                                     del comando                             │
│                                     [default: text]                         │
│ --quiet                             Mostrar solo errores en stderr          │
│ --verbose                           Mostrar logs internos informativos en   │
│                                     stderr                                  │
│ --debug                             Mostrar logs internos de depuración en  │
│                                     stderr                                  │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Gestionar configuración local y diagnósticos                        │
│ app     Espacio de trabajo fiscal para libros, facturas y declaraciones     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A2. `aeat --help`
$ aeat --help
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Asistente para preparar declaraciones tributarias españolas

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Mostrar la versión del paquete y el     │
│                                     resumen del registro                    │
│ --format                      TEXT  Formato de salida para los resultados   │
│                                     del comando                             │
│                                     [default: text]                         │
│ --quiet                             Mostrar solo errores en stderr          │
│ --verbose                           Mostrar logs internos informativos en   │
│                                     stderr                                  │
│ --debug                             Mostrar logs internos de depuración en  │
│                                     stderr                                  │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Gestionar configuración local y diagnósticos                        │
│ app     Espacio de trabajo fiscal para libros, facturas y declaraciones     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A3. `aeat --version`
$ aeat --version
--- stdout ---
aeat 0.1.0 (registry revisions 2003-y-siguientes, 2004-y-siguientes, 2008-y-siguientes, 2009-y-siguientes, 2010-y-siguientes, 2013-y-siguientes, 2015-y-siguientes, 2016-2017, 2018-y-siguientes, 2019-2022, 2019-2023, 2019-y-siguientes, 2020, 2020-y-siguientes, 2021, 2022, 2023, 2023-2024, 2023-y-siguientes, 2024, 2024-y-siguientes, 2025, 2025-y-siguientes, 2026, esquema-exterior, esquema-importacion, esquema-union; 25 modelos, 14952 casillas, 1039 formulas)
--- stderr ---

--- exit 0 ---

===============================================================================
### A4. `aeat -V`
$ aeat -V
--- stdout ---
aeat 0.1.0 (registry revisions 2003-y-siguientes, 2004-y-siguientes, 2008-y-siguientes, 2009-y-siguientes, 2010-y-siguientes, 2013-y-siguientes, 2015-y-siguientes, 2016-2017, 2018-y-siguientes, 2019-2022, 2019-2023, 2019-y-siguientes, 2020, 2020-y-siguientes, 2021, 2022, 2023, 2023-2024, 2023-y-siguientes, 2024, 2024-y-siguientes, 2025, 2025-y-siguientes, 2026, esquema-exterior, esquema-importacion, esquema-union; 25 modelos, 14952 casillas, 1039 formulas)
--- stderr ---

--- exit 0 ---

===============================================================================
### A5. `aeat config --help`
$ aeat config --help
--- stdout ---

 Usage: aeat config [OPTIONS] COMMAND [ARGS]...

 Gestionar configuración local y diagnósticos

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ list    Listar todas las claves de configuración y sus valores actuales     │
│ get     Mostrar el valor actual de una clave de configuración               │
│ set     Asignar un valor a una clave de configuración                       │
│ unset   Eliminar el valor asignado a una clave de configuración             │
│ setup   Ejecutar el asistente de configuración basado en esquema de forma   │
│         interactiva o usando banderas                                       │
│ status  Mostrar el estado del perfil de configuración activo                │
│ reset   Reiniciar ámbitos de configuración introducidos por el operador     │
│ auth    Configurar el proveedor de autenticación activo                     │
│ doctor  Diagnosticar configuración local, registro, perfil, autenticación y │
│         logs                                                                │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A6. `aeat app --help`
$ aeat app --help
--- stdout ---

 Usage: aeat app [OPTIONS] COMMAND [ARGS]...

 Espacio de trabajo fiscal para libros, facturas y declaraciones

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ overview     Revisar el estado actual del espacio de trabajo fiscal         │
│ ledger       Gestión de libros contables y registros de IVA                 │
│ invoice      Gestión y procesamiento de facturas                            │
│ declaration  Preparación y exportación local de declaraciones tributarias   │
│ modelo       Inspeccionar el catálogo de modelos tributarios AEAT en el     │
│              registro                                                       │
│ registry     Gestión del registro de modelos fiscales                       │
│ archive      Exportar e importar el archivo local cifrado como paquetes     │
│              JSON portables                                                 │
│ topic        Mostrar ayuda conceptual sobre regímenes, modelos y procesos   │
│              AEAT                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A7. `aeat config setup --help`
$ aeat config setup --help
--- stdout ---

 Usage: aeat config setup [OPTIONS]

 Ejecutar el asistente de configuración basado en esquema de forma interactiva
 o usando banderas

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --profile-name                           TEXT             Nombre del perfil │
│                                                           donde guardar las │
│                                                           respuestas        │
│                                                           [default:         │
│                                                           default]          │
│ --quiet                                                   Ejecutar el flujo │
│                                                           sin interacción   │
│                                                           usando solo los   │
│                                                           valores de las    │
│                                                           banderas          │
│ --accept-defaults                                         Aceptar los       │
│                                                           valores por       │
│                                                           defecto del       │
│                                                           descriptor sin    │
│                                                           preguntar         │
│ --tax-id                                 TEXT             Identificador     │
│                                                           fiscal (NIF/NIE)  │
│                                                           para              │
│                                                           declaraciones     │
│ --name                                   TEXT             Nombre visible    │
│                                                           mostrado en       │
│                                                           revisiones        │
│                                                           locales           │
│ --surnames                               TEXT             Apellidos o razón │
│                                                           social para       │
│                                                           cabeceras de      │
│                                                           exportación       │
│ --activity                               TEXT             Etiqueta de       │
│                                                           actividad o clave │
│                                                           controlada        │
│ --address-postco…                        TEXT             Código postal del │
│                                                           domicilio fiscal  │
│ --declaration-ty…                        TEXT             Código del tipo   │
│                                                           de declaración    │
│ --taxpayer-sex                           TEXT             Sexo del primer   │
│                                                           declarante        │
│ --taxpayer-marit…                        TEXT             Estado civil del  │
│                                                           primer declarante │
│ --taxpayer-birth…                        TEXT             Fecha de          │
│                                                           nacimiento del    │
│                                                           primer declarante │
│ --taxpayer-disab…                        TEXT             Clave de          │
│                                                           discapacidad del  │
│                                                           primer declarante │
│ --taxpayer-death…                        TEXT             Fecha de          │
│                                                           fallecimiento del │
│                                                           primer declarante │
│ --spouse-tax-id                          TEXT             NIF/NIE del       │
│                                                           cónyuge           │
│ --spouse-name                            TEXT             Nombre del        │
│                                                           cónyuge           │
│ --spouse-surnames                        TEXT             Apellidos del     │
│                                                           cónyuge           │
│ --spouse-birth-d…                        TEXT             Fecha de          │
│                                                           nacimiento del    │
│                                                           cónyuge           │
│ --spouse-sex                             TEXT             Sexo del cónyuge  │
│ --spouse-disabil…                        TEXT             Clave de          │
│                                                           discapacidad del  │
│                                                           cónyuge           │
│ --spouse-non-res…    --no-spouse-non…                     Cónyuge no        │
│                                                           residente IRPF    │
│ --spouse-eu-eea-…    --no-spouse-eu-…                     Cónyuge residente │
│                                                           UE/EEE            │
│ --spouse-eu-eea-…                        TEXT             País UE/EEE del   │
│                                                           cónyuge           │
│ --family-descend…    --no-family-des…                     Descendientes     │
│                                                           UE/EEE en         │
│                                                           deducción de      │
│                                                           unidad familiar   │
│ --family-minor-c…    --no-family-min…                     Hijos menores en  │
│                                                           unidad familiar   │
│ --iva-regime                             [GENERAL|SIMPLI  Régimen IVA       │
│                                          FICADO|RECARGO_                    │
│                                          EQUIVALENCIA|EX                    │
│                                          ENTO]                              │
│ --iva-roi-enroll…    --no-iva-roi-en…                     Alta en ROI       │
│ --iva-oss-enroll…    --no-iva-oss-en…                     Alta en OSS       │
│ --iva-intracommu…    --no-iva-intrac…                     Operaciones       │
│                                                           intracomunitarias │
│                                                           superan 50.000    │
│                                                           EUR               │
│ --enrollment-lar…    --no-enrollment…                     Empresa de gran   │
│                                                           volumen           │
│ --enrollment-pub…    --no-enrollment…                     Presupuesto       │
│                                                           administración    │
│                                                           pública superior  │
│                                                           a 6.000.000       │
│ --has-employees      --no-has-employ…                     Tiene empleados y │
│                                                           paga salarios con │
│                                                           retención         │
│ --pays-professio…    --no-pays-profe…                     Paga a            │
│                                                           profesionales con │
│                                                           retención         │
│ --professional-i…    --no-profession…                     Al menos 70% de   │
│                                                           los ingresos      │
│                                                           profesionales con │
│                                                           retención previa  │
│ --pays-rent-with…    --no-pays-rent-…                     Paga alquiler de  │
│                                                           local con         │
│                                                           retención         │
│ --pays-capital-i…    --no-pays-capit…                     Paga rentas de    │
│                                                           capital con       │
│                                                           retención         │
│ --uses-objective…    --no-uses-objec…                     Tributa IRPF en   │
│                                                           estimación        │
│                                                           objetiva          │
│ --does-intracomu…    --no-does-intra…                     Realiza           │
│                                                           operaciones       │
│                                                           intracomunitarias │
│ --third-party-tr…    --no-third-part…                     Operaciones con   │
│                                                           terceros superan  │
│                                                           el umbral del     │
│                                                           Modelo 347        │
│ --bienes-extranj…    --no-bienes-ext…                     Bienes en el      │
│                                                           extranjero        │
│                                                           superan el umbral │
│                                                           legal             │
│ --tax-residence-…                        [andalucia|arag  Comunidad         │
│                                          on|asturias|bal  autónoma de       │
│                                          eares|canarias|  residencia fiscal │
│                                          cantabria|casti                    │
│                                          lla_la_mancha|c                    │
│                                          astilla_y_leon|                    │
│                                          cataluna|comuni                    │
│                                          dad_valenciana|                    │
│                                          extremadura|gal                    │
│                                          icia|la_rioja|m                    │
│                                          adrid|murcia]                      │
│ --notes                                  TEXT             Notas del         │
│                                                           operador (no      │
│                                                           consumidas por el │
│                                                           motor)            │
│ --help                                                    Show this message │
│                                                           and exit.         │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A8. `aeat config status --help`
$ aeat config status --help
--- stdout ---

 Usage: aeat config status [OPTIONS]

 Mostrar el estado del perfil de configuración activo

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A9. `aeat config set --help`
$ aeat config set --help
--- stdout ---

 Usage: aeat config set [OPTIONS] KEY VALUE

 Asignar un valor a una clave de configuración

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│ *    key        TEXT  Clave a asignar (ej. iva.regime) [required]           │
│ *    value      TEXT  Valor a asignar (texto, true/false, importe segun la  │
│                       clave)                                                │
│                       [required]                                            │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A10. `aeat config auth --help`
$ aeat config auth --help
--- stdout ---

 Usage: aeat config auth [OPTIONS]

 Configurar el proveedor de autenticación activo

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ *  --provider        TEXT  Identificador del proveedor (p.ej.               │
│                            certificado-electronico)                         │
│                            [required]                                       │
│    --file            PATH  Ruta al archivo de credenciales (certificado o   │
│                            clave)                                           │
│    --help                  Show this message and exit.                      │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A11. `aeat config reset --help`
$ aeat config reset --help
--- stdout ---

 Usage: aeat config reset [OPTIONS]

 Reiniciar ámbitos de configuración introducidos por el operador

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --scope        TEXT  Ámbito a reiniciar (all, profile, auth) [default: all] │
│ --yes                Confirmar explícitamente la operación de reinicio      │
│ --help               Show this message and exit.                            │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A12. `aeat app archive --help`
$ aeat app archive --help
--- stdout ---

 Usage: aeat app archive [OPTIONS] COMMAND [ARGS]...

 Exportar e importar el archivo local cifrado como paquetes JSON portables

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ export  Escribir un paquete JSON portable del catálogo de objetos seguros   │
│ import  Restaurar un paquete de archivo en el catálogo cifrado de objetos   │
│         seguros                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A13. `aeat app topic --help`
$ aeat app topic --help
--- stdout ---

 Usage: aeat app topic [OPTIONS] [SLUG] COMMAND [ARGS]...

 Mostrar ayuda conceptual sobre regímenes, modelos y procesos AEAT

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│   slug      [SLUG]  Identificador del tema (kebab-case, ej. iva-regime)     │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### A14. `aeat app topic` (no slug)
$ aeat app topic
--- stdout ---
slug	authentication	Autenticación con la AEAT
slug	calendar	Calendario de obligaciones
slug	casilla	Casillas
slug	formats	Formatos de salida
slug	irpf-regime	Régimen IRPF
slug	iva-regime	Régimen IVA
slug	modelos	Modelos tributarios
slug	pago-fraccionado	Pago fraccionado IRPF
slug	profile	Perfil del contribuyente
slug	providers	Proveedores de autenticación
slug	recargo-extemporaneo	Recargo por presentación extemporánea
slug	regimens	Regímenes fiscales
slug	sii-verifactu	SII y Verifactu
--- stderr ---

--- exit 0 ---
```

## SCENARIO B — Quiet-mode setup happy path (es)

```text


# SCENARIO B — Quiet-mode setup happy path (es locale, fresh sandbox)

===============================================================================
### B0. sandbox env overrides
$ aeat
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Asistente para preparar declaraciones tributarias españolas

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Mostrar la versión del paquete y el     │
│                                     resumen del registro                    │
│ --format                      TEXT  Formato de salida para los resultados   │
│                                     del comando                             │
│                                     [default: text]                         │
│ --quiet                             Mostrar solo errores en stderr          │
│ --verbose                           Mostrar logs internos informativos en   │
│                                     stderr                                  │
│ --debug                             Mostrar logs internos de depuración en  │
│                                     stderr                                  │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Gestionar configuración local y diagnósticos                        │
│ app     Espacio de trabajo fiscal para libros, facturas y declaraciones     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

# sandbox tmp: C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1
# AEAT_OUTPUT_LANGUAGE=es
# AEAT_SECRET_STORE_BACKEND=unsecured
# AEAT_ALLOW_UNENCRYPTED=1
# AEAT_DATABASE_URL=sqlite:///C:/Users/hello/AppData/Local/Temp/aeat-ux-es-dh1_dww1/aeat.db
# AEAT_TOKEN_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\tokens
# AEAT_RUNS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\runs
# AEAT_FINANCIAL_TXS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\txs
# AEAT_INVOICES_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\invoices
# AEAT_DRAFTS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\drafts
# AEAT_SECRET_STORE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\secrets
# AEAT_BLOB_STORE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\blobs
# AEAT_AUDIT_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\audit
# AEAT_SUBMISSIONS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\submissions
# AEAT_INBOX_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\inbox
# AEAT_INBOX_PDF_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\inbox\pdfs
# AEAT_WORKFLOW_RUNS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\workflow-runs
# AEAT_STATUS_CACHE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\status-cache
# AEAT_FILING_HISTORY_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\filing-history
# AEAT_LEDGERS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\ledgers
# AEAT_ATTACHMENTS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\attachments
# AEAT_LLM_CACHE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\llm-cache
# AEAT_LLM_USAGE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\llm-usage
# AEAT_JUSTIFICANTES_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\justificantes
# AEAT_SUBMISSION_BROWSER_TRACE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\browser-traces
# AEAT_STATUS_BROWSER_TRACE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\browser-traces
# AEAT_STORAGE_BACKUP_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\backups
# AEAT_USAGE_RATIOS_PATH=C:\Users\hello\AppData\Local\Temp\aeat-ux-es-dh1_dww1\usage-ratios.json

===============================================================================
### B1. `aeat config status` (empty sandbox)
$ aeat config status
--- stdout ---
REFUSED: The command input failed validation.
  detail: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
  error_type: ValidationError
  original_exception: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
--- stderr ---
REFUSED: The command input failed validation.
  detail: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
  error_type: ValidationError
  original_exception: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
--- exit 2 ---

===============================================================================
### B2. `aeat config setup --quiet --tax-id 00000000T --name Carlos --activity design`
$ aeat config setup --quiet --tax-id 00000000T --name Carlos --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### B3. `aeat config status` (after setup)
$ aeat config status
--- stdout ---
profile	default
tax.id	00000000T
activity	design
iva.regime	GENERAL
tax.residence.ccaa	madrid
--- stderr ---

--- exit 0 ---

===============================================================================
### B4. `aeat config get tax.id`
$ aeat config get tax.id
--- stdout ---
tax.id	00000000T
--- stderr ---

--- exit 0 ---

===============================================================================
### B5. `aeat config get name`
$ aeat config get name
--- stdout ---
name	Carlos
--- stderr ---

--- exit 0 ---

===============================================================================
### B6. `aeat config get activity`
$ aeat config get activity
--- stdout ---
activity	design
--- stderr ---

--- exit 0 ---
```

## SCENARIO C — Interactive setup (es, pipe-driven)

```text
# sandbox tmp: C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_
# AEAT_OUTPUT_LANGUAGE=es
# AEAT_SECRET_STORE_BACKEND=unsecured
# AEAT_ALLOW_UNENCRYPTED=1
# AEAT_DATABASE_URL=sqlite:///C:/Users/hello/AppData/Local/Temp/aeat-ux-c-3i6ihc4_/aeat.db
# AEAT_TOKEN_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\tokens
# AEAT_RUNS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\runs
# AEAT_FINANCIAL_TXS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\txs
# AEAT_INVOICES_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\invoices
# AEAT_DRAFTS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\drafts
# AEAT_SECRET_STORE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\secrets
# AEAT_BLOB_STORE_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\blobs
# AEAT_AUDIT_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\audit
# AEAT_LEDGERS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\ledgers
# AEAT_ATTACHMENTS_DIR=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\attachments
# AEAT_USAGE_RATIOS_PATH=C:\Users\hello\AppData\Local\Temp\aeat-ux-c-3i6ihc4_\usage-ratios.json

### section: profile  (title: Identidad del perfil)
--- question: tax-id (widget=TEXT, profile_key='tax.id', required=True)
    prompt: 'Identificador fiscal (NIF/NIE) para declaraciones'
    default: None
    scripted_keystrokes: '00000000T\r'
    raw_response: '00000000T'
    validated: '00000000T'
--- question: name (widget=TEXT, profile_key='name', required=False)
    prompt: 'Nombre visible mostrado en revisiones locales'
    default: None
    scripted_keystrokes: 'Carlos\r'
    raw_response: 'Carlos'
    validated: 'Carlos'
--- question: surnames (widget=TEXT, profile_key='surnames', required=False)
    prompt: 'Apellidos o razón social para cabeceras de exportación'
    default: None
    scripted_keystrokes: 'Garcia Lopez\r'
    raw_response: 'Garcia Lopez'
    validated: 'Garcia Lopez'
--- question: activity (widget=TEXT, profile_key='activity', required=True)
    prompt: 'Etiqueta de actividad o clave controlada'
    default: None
    scripted_keystrokes: 'design\r'
    raw_response: 'design'
    validated: 'design'
--- question: address-postcode (widget=TEXT, profile_key='address.postcode', required=False)
    prompt: 'Código postal del domicilio fiscal'
    default: None
    scripted_keystrokes: '28013\r'
    raw_response: '28013'
    validated: '28013'
--- question: declaration-type (widget=TEXT, profile_key='declaration.type', required=False)
    prompt: 'Código del tipo de declaración'
    default: None
    scripted_keystrokes: '1\r'
    raw_response: '1'
    validated: '1'

### section: taxpayer  (title: Primer declarante)
--- question: taxpayer-sex (widget=TEXT, profile_key='taxpayer.sex', required=False)
    prompt: 'Sexo del primer declarante'
    default: None
    scripted_keystrokes: 'M\r'
    raw_response: 'M'
    validated: 'M'
--- question: taxpayer-marital-status (widget=TEXT, profile_key='taxpayer.marital_status', required=False)
    prompt: 'Estado civil del primer declarante'
    default: None
    scripted_keystrokes: 'S\r'
    raw_response: 'S'
    validated: 'S'
--- question: taxpayer-birth-date (widget=TEXT, profile_key='taxpayer.birth_date', required=False)
    prompt: 'Fecha de nacimiento del primer declarante'
    default: None
    scripted_keystrokes: '1980-01-01\r'
    raw_response: '1980-01-01'
    validated: '1980-01-01'
--- question: taxpayer-disability-grade (widget=TEXT, profile_key='taxpayer.disability_grade', required=False)
    prompt: 'Clave de discapacidad del primer declarante'
    default: None
    scripted_keystrokes: '\r'
    raw_response: ''
    validated: ''
--- question: taxpayer-death-date (widget=TEXT, profile_key='taxpayer.death_date', required=False)
    prompt: 'Fecha de fallecimiento del primer declarante'
    default: None
    scripted_keystrokes: '\r'
    raw_response: ''
    validated: ''

### section: spouse  (title: Cónyuge)
# SKIPPED (visible_when): spouse-tax-id (requires declaration-type=='2', got '1')
# SKIPPED (visible_when): spouse-name (requires declaration-type=='2', got '1')
# SKIPPED (visible_when): spouse-surnames (requires declaration-type=='2', got '1')
# SKIPPED (visible_when): spouse-birth-date (requires declaration-type=='2', got '1')
# SKIPPED (visible_when): spouse-sex (requires declaration-type=='2', got '1')
--- question: spouse-disability-grade (widget=TEXT, profile_key='spouse.disability_grade', required=False)
    prompt: 'Clave de discapacidad del cónyuge'
    default: None
    scripted_keystrokes: '\r'
    raw_response: ''
    validated: ''
--- question: spouse-non-resident-irpf (widget=CONFIRM, profile_key='spouse.non_resident_irpf', required=False)
    prompt: 'Cónyuge no residente IRPF'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
# SKIPPED (visible_when): spouse-eu-eea-resident (requires spouse-non-resident-irpf=='true', got 'false')
# SKIPPED (visible_when): spouse-eu-eea-country (requires spouse-eu-eea-resident=='true', got None)

### section: family  (title: Unidad familiar)
--- question: family-descendants-eu-eea-deduction (widget=CONFIRM, profile_key='family.descendants_eu_eea_deduction', required=False)
    prompt: 'Descendientes UE/EEE en deducción de unidad familiar'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: family-minor-children-in-unit (widget=CONFIRM, profile_key='family.minor_children_in_unit', required=False)
    prompt: 'Hijos menores en unidad familiar'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'

### section: iva  (title: IVA)
--- question: iva-regime (widget=SELECT, profile_key='iva.regime', required=False)
    prompt: 'Régimen IVA'
    default: 'GENERAL'
    choices: [('GENERAL', 'Régimen general'), ('SIMPLIFICADO', 'Régimen simplificado'), ('RECARGO_EQUIVALENCIA', 'Recargo de equivalencia'), ('EXENTO', 'Exento')]
    scripted_keystrokes: '\r'
    raw_response: 'GENERAL'
    validated: 'GENERAL'
--- question: iva-roi-enrolled (widget=CONFIRM, profile_key='iva.roi_enrolled', required=False)
    prompt: 'Alta en ROI'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: iva-oss-enrolled (widget=CONFIRM, profile_key='iva.oss_enrolled', required=False)
    prompt: 'Alta en OSS'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: iva-intracommunity-operations-exceed-50000-eur (widget=CONFIRM, profile_key='iva.intracommunity_operations_exceed_50000_eur', required=False)
    prompt: 'Operaciones intracomunitarias superan 50.000 EUR'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'

### section: enrollment  (title: Inscripción)
--- question: enrollment-large-company (widget=CONFIRM, profile_key='enrollment.large_company', required=False)
    prompt: 'Empresa de gran volumen'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: enrollment-public-administration-budget-gt-6000000 (widget=CONFIRM, profile_key='enrollment.public_administration_budget_gt_6000000', required=False)
    prompt: 'Presupuesto administración pública superior a 6.000.000'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'

### section: obligations  (title: Obligaciones)
--- question: has-employees (widget=CONFIRM, profile_key='has_employees', required=False)
    prompt: 'Tiene empleados y paga salarios con retención'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: pays-professionals-with-retencion (widget=CONFIRM, profile_key='pays_professionals_with_retencion', required=False)
    prompt: 'Paga a profesionales con retención'
    default: 'false'
    scripted_keystrokes: 'y\r'
    raw_response: 'true'
    validated: 'true'
--- question: professional-income-withholding-ge-70pct (widget=CONFIRM, profile_key='professional_income_withholding_ge_70pct', required=False)
    prompt: 'Al menos 70% de los ingresos profesionales con retención previa'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: pays-rent-with-retencion (widget=CONFIRM, profile_key='pays_rent_with_retencion', required=False)
    prompt: 'Paga alquiler de local con retención'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: pays-capital-income-with-retencion (widget=CONFIRM, profile_key='pays_capital_income_with_retencion', required=False)
    prompt: 'Paga rentas de capital con retención'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: uses-objective-estimation-irpf (widget=CONFIRM, profile_key='uses_objective_estimation_irpf', required=False)
    prompt: 'Tributa IRPF en estimación objetiva'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: does-intracomunitario (widget=CONFIRM, profile_key='does_intracomunitario', required=False)
    prompt: 'Realiza operaciones intracomunitarias'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: third-party-transactions-above-347-threshold (widget=CONFIRM, profile_key='third_party_transactions_above_347_threshold', required=False)
    prompt: 'Operaciones con terceros superan el umbral del Modelo 347'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'
--- question: bienes-extranjero-above-threshold (widget=CONFIRM, profile_key='bienes_extranjero_above_threshold', required=False)
    prompt: 'Bienes en el extranjero superan el umbral legal'
    default: 'false'
    scripted_keystrokes: 'n\r'
    raw_response: 'false'
    validated: 'false'

### section: residence  (title: Residencia fiscal)
--- question: tax-residence-ccaa (widget=SELECT, profile_key='tax.residence.ccaa', required=False)
    prompt: 'Comunidad autónoma de residencia fiscal'
    default: 'madrid'
    choices: [('andalucia', 'Andalucía'), ('aragon', 'Aragón'), ('asturias', 'Asturias'), ('baleares', 'Islas Baleares'), ('canarias', 'Islas Canarias'), ('cantabria', 'Cantabria'), ('castilla_la_mancha', 'Castilla-La Mancha'), ('castilla_y_leon', 'Castilla y León'), ('cataluna', 'Cataluña'), ('comunidad_valenciana', 'Comunidad Valenciana'), ('extremadura', 'Extremadura'), ('galicia', 'Galicia'), ('la_rioja', 'La Rioja'), ('madrid', 'Madrid'), ('murcia', 'Murcia')]
    scripted_keystrokes: '\r'
    raw_response: 'madrid'
    validated: 'madrid'

### section: notes  (title: Notas del operador)
--- question: notes (widget=TEXT, profile_key='notes', required=False)
    prompt: 'Notas del operador (no consumidas por el motor)'
    default: None
    scripted_keystrokes: '\r'
    raw_response: ''
    validated: ''

### final canonical answers:
    tax-id	00000000T
    name	Carlos
    surnames	Garcia Lopez
    activity	design
    address-postcode	28013
    declaration-type	1
    taxpayer-sex	M
    taxpayer-marital-status	S
    taxpayer-birth-date	1980-01-01
    taxpayer-disability-grade
    taxpayer-death-date
    spouse-disability-grade
    spouse-non-resident-irpf	false
    family-descendants-eu-eea-deduction	false
    family-minor-children-in-unit	false
    iva-regime	GENERAL
    iva-roi-enrolled	false
    iva-oss-enrolled	false
    iva-intracommunity-operations-exceed-50000-eur	false
    enrollment-large-company	false
    enrollment-public-administration-budget-gt-6000000	false
    has-employees	false
    pays-professionals-with-retencion	true
    professional-income-withholding-ge-70pct	false
    pays-rent-with-retencion	false
    pays-capital-income-with-retencion	false
    uses-objective-estimation-irpf	false
    does-intracomunitario	false
    third-party-transactions-above-347-threshold	false
    bienes-extranjero-above-threshold	false
    tax-residence-ccaa	madrid
    notes

### persisting via persist_answers
    OK

### C2. `aeat config status` after persistence (via CliRunner)
--- stdout ---
profile	default
tax.id	00000000T
activity	design
iva.regime	GENERAL
tax.residence.ccaa	madrid
--- stderr ---

--- exit 0 ---
```

## SCENARIO D — Validation rejections

```text
2026-05-13 09:23:49,375 [ERROR] aeat.entrypoints.cli._errors: command_error_boundary: unexpected exception in setup
Traceback (most recent call last):
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\entrypoints\cli\_errors.py", line 171, in _wrapped
    return callback(*args, **kwargs)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\entrypoints\cli\_config.py", line 268, in _wrapped
    _callable(*args, **kwargs)
    ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_commands.py", line 285, in _command
    answers = run_flow(flow, active, defaults=canonical)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_runner.py", line 62, in run_flow
    raw = prompter.ask(question, default=default)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_prompter.py", line 116, in ask
    return self._ask_text(prompt, default)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_prompter.py", line 131, in _ask_text
    result = questionary.text(
             ~~~~~~~~~~~~~~~~^
        prompt,
        ^^^^^^^
    ...<2 lines>...
        output=self._output,
        ^^^^^^^^^^^^^^^^^^^^
    ).ask()
    ^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\questionary\prompts\text.py", line 91, in text
    p: PromptSession = PromptSession(
                       ~~~~~~~~~~~~~^
        get_prompt_tokens,
        ^^^^^^^^^^^^^^^^^^
    ...<4 lines>...
        **kwargs,
        ^^^^^^^^^
    )
    ^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\shortcuts\prompt.py", line 483, in __init__
    self.app = self._create_application(editing_mode, erase_when_done)
               ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\shortcuts\prompt.py", line 744, in _create_application
    application: Application[_T] = Application(
                                   ~~~~~~~~~~~^
        layout=self.layout,
        ^^^^^^^^^^^^^^^^^^^
    ...<36 lines>...
        output=self._output,
        ^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\application\application.py", line 267, in __init__
    self.output = output or session.output
                            ^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\application\current.py", line 67, in output
    self._output = create_output()
                   ~~~~~~~~~~~~~^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\output\defaults.py", line 91, in create_output
    return Win32Output(stdout, default_color_depth=color_depth_from_env)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\output\win32.py", line 115, in __init__
    info = self.get_win32_screen_buffer_info()
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\output\win32.py", line 219, in get_win32_screen_buffer_info
    raise NoConsoleScreenBufferError
prompt_toolkit.output.win32.NoConsoleScreenBufferError: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.


# SCENARIO D — Validation rejections

===============================================================================
### D1. quiet setup with malformed NIF
$ aeat config setup --quiet --tax-id INVALID --name Carlos --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### D2. quiet setup with bogus iva-regime SELECT value
$ aeat config setup --quiet --tax-id 00000000T --name Carlos --activity design --iva-regime BOGUS
--- stdout ---
Usage: aeat config setup [OPTIONS]
Try 'aeat config setup --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value for '--iva-regime': 'BOGUS' is not one of 'GENERAL',          │
│ 'SIMPLIFICADO', 'RECARGO_EQUIVALENCIA', 'EXENTO'.                           │
└─────────────────────────────────────────────────────────────────────────────┘
--- stderr ---
Usage: aeat config setup [OPTIONS]
Try 'aeat config setup --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value for '--iva-regime': 'BOGUS' is not one of 'GENERAL',          │
│ 'SIMPLIFICADO', 'RECARGO_EQUIVALENCIA', 'EXENTO'.                           │
└─────────────────────────────────────────────────────────────────────────────┘
--- exit 2 ---

===============================================================================
### D3a. clean quiet setup (precondition for D3)
$ aeat config setup --quiet --tax-id 00000000T --name Carlos --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### D3. `aeat config set tax.id NOT_A_NIF`
$ aeat config set tax.id NOT_A_NIF
--- stdout ---
tax.id	NOT_A_NIF
--- stderr ---

--- exit 0 ---

===============================================================================
### D4. `aeat config set unknown.key any.value`
$ aeat config set unknown.key any.value
--- stdout ---
Usage: aeat config set [OPTIONS] KEY VALUE
Try 'aeat config set --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: Clave de configuración desconocida: unknown.key. Ejecuta     │
│ 'aeat config list' para ver las claves disponibles.                         │
└─────────────────────────────────────────────────────────────────────────────┘
--- stderr ---
Usage: aeat config set [OPTIONS] KEY VALUE
Try 'aeat config set --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: Clave de configuración desconocida: unknown.key. Ejecuta     │
│ 'aeat config list' para ver las claves disponibles.                         │
└─────────────────────────────────────────────────────────────────────────────┘
--- exit 2 ---

===============================================================================
### D5. `aeat config get unknown.key`
$ aeat config get unknown.key
--- stdout ---
Usage: aeat config get [OPTIONS] KEY
Try 'aeat config get --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: Clave de configuración desconocida: unknown.key. Ejecuta     │
│ 'aeat config list' para ver las claves disponibles.                         │
└─────────────────────────────────────────────────────────────────────────────┘
--- stderr ---
Usage: aeat config get [OPTIONS] KEY
Try 'aeat config get --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: Clave de configuración desconocida: unknown.key. Ejecuta     │
│ 'aeat config list' para ver las claves disponibles.                         │
└─────────────────────────────────────────────────────────────────────────────┘
--- exit 2 ---

===============================================================================
### D6. `aeat config setup --quiet` (no required flags)
$ aeat config setup --quiet
--- stdout ---
Usage: aeat config setup [OPTIONS]
Try 'aeat config setup --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: Faltan banderas obligatorias para el modo --quiet;           │
│ proporciona un valor para cada pregunta obligatoria.                        │
└─────────────────────────────────────────────────────────────────────────────┘
--- stderr ---
Usage: aeat config setup [OPTIONS]
Try 'aeat config setup --help' for help.
┌─ Error ─────────────────────────────────────────────────────────────────────┐
│ Invalid value: Faltan banderas obligatorias para el modo --quiet;           │
│ proporciona un valor para cada pregunta obligatoria.                        │
└─────────────────────────────────────────────────────────────────────────────┘
--- exit 2 ---

===============================================================================
### D7. interactive setup with empty stdin (EOF on first prompt)
$ aeat config setup
--- stdout ---
INTERNAL: The command failed due to an unexpected internal error.
  detail: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
  error_type: NoConsoleScreenBufferError
  original_exception: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
2026-05-13 09:23:51,126 [ERROR] aeat.entrypoints.cli._errors: command_error_boundary: unexpected exception in setup
Traceback (most recent call last):
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\entrypoints\cli\_errors.py", line 171, in _wrapped
    return callback(*args, **kwargs)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\entrypoints\cli\_config.py", line 268, in _wrapped
    _callable(*args, **kwargs)
    ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_commands.py", line 285, in _command
    answers = run_flow(flow, active, defaults=canonical)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_runner.py", line 62, in run_flow
    raw = prompter.ask(question, default=default)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_prompter.py", line 116, in ask
    return self._ask_text(prompt, default)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\src\aeat\application\wizard\_prompter.py", line 131, in _ask_text
    result = questionary.text(
             ~~~~~~~~~~~~~~~~^
        prompt,
        ^^^^^^^
    ...<2 lines>...
        output=self._output,
        ^^^^^^^^^^^^^^^^^^^^
    ).ask()
    ^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\questionary\prompts\text.py", line 91, in text
    p: PromptSession = PromptSession(
                       ~~~~~~~~~~~~~^
        get_prompt_tokens,
        ^^^^^^^^^^^^^^^^^^
    ...<4 lines>...
        **kwargs,
        ^^^^^^^^^
    )
    ^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\shortcuts\prompt.py", line 483, in __init__
    self.app = self._create_application(editing_mode, erase_when_done)
               ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\shortcuts\prompt.py", line 744, in _create_application
    application: Application[_T] = Application(
                                   ~~~~~~~~~~~^
        layout=self.layout,
        ^^^^^^^^^^^^^^^^^^^
    ...<36 lines>...
        output=self._output,
        ^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\application\application.py", line 267, in __init__
    self.output = output or session.output
                            ^^^^^^^^^^^^^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\application\current.py", line 67, in output
    self._output = create_output()
                   ~~~~~~~~~~~~~^^
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\output\defaults.py", line 91, in create_output
    return Win32Output(stdout, default_color_depth=color_depth_from_env)
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\output\win32.py", line 115, in __init__
    info = self.get_win32_screen_buffer_info()
  File "Y:\code\aeat-worktrees\chore-476-restructure-execution\.venv\Lib\site-packages\prompt_toolkit\output\win32.py", line 219, in get_win32_screen_buffer_info
    raise NoConsoleScreenBufferError
prompt_toolkit.output.win32.NoConsoleScreenBufferError: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
--- stderr ---
INTERNAL: The command failed due to an unexpected internal error.
  detail: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
  error_type: NoConsoleScreenBufferError
  original_exception: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
--- exit 6 ---

===============================================================================
### D8. interactive setup, BOGUS iva-regime
$ aeat config setup
--- stdout ---
INTERNAL: The command failed due to an unexpected internal error.
  detail: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
  error_type: NoConsoleScreenBufferError
  original_exception: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
--- stderr ---
INTERNAL: The command failed due to an unexpected internal error.
  detail: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
  error_type: NoConsoleScreenBufferError
  original_exception: Found xterm-256color, while expecting a Windows console. Maybe try to run this program using "winpty" or run it in cmd.exe instead. Or otherwise, in case of Cygwin, use the Python executable that is compiled for Cygwin.
--- exit 6 ---
```

## SCENARIO D (pipe addendum) — D7/D8 via pipe input

```text
### D7. send Ctrl+C (\x03) to first TEXT prompt tax-id

Cancelled by user

  result: ''

### D7b. send empty pipe text (EOF without bytes) to TEXT prompt
  [D7b] TIMEOUT after 4.0s — probe hung
  result: None

### D8a. SELECT iva-regime — press Enter immediately
  result: 'GENERAL'

### D8b. SELECT iva-regime — down-arrow then Enter
  result: 'SIMPLIFICADO'

### D8c. SELECT iva-regime — type 'BOGUS' then Enter (no movement)
  result: 'GENERAL'

### D8d. validate_widget_answer rejects 'BOGUS' as a raw SELECT canonical
  WizardValidationError: wizard.errors.select_unknown

### D8e. validate_widget_answer accepts 'GENERAL' as a raw SELECT canonical
  validated: 'GENERAL'
```

## SCENARIO E — Locale parity (en / es / ca / hu)

```text


# SCENARIO E — Locale parity (en / es / ca / hu)

===============================================================================
### E1.en `aeat --help`
$ aeat --help
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Spanish tax filing assistant

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Show package version and registry       │
│                                     summary                                 │
│ --format                      TEXT  Output format for command results       │
│                                     [default: text]                         │
│ --quiet                             Show only errors on stderr              │
│ --verbose                           Show internal informational logs on     │
│                                     stderr                                  │
│ --debug                             Show internal debug logs on stderr      │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Manage local configuration and diagnostics                          │
│ app     Tax workspaces for ledgers, invoices, and declarations              │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E2.en `aeat config --help`
$ aeat config --help
--- stdout ---

 Usage: aeat config [OPTIONS] COMMAND [ARGS]...

 Manage local configuration and diagnostics

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ list    List every configuration key with its current value                 │
│ get     Show the current value of one configuration key                     │
│ set     Assign a value to one configuration key                             │
│ unset   Clear the value of one configuration key                            │
│ setup   Run the schema-driven setup wizard interactively or via flag-driven │
│         quiet mode                                                          │
│ status  Show the readiness of the current configuration profile             │
│ reset   Reset operator-entered configuration scopes                         │
│ auth    Configure the active authentication provider                        │
│ doctor  Diagnose local configuration, registry, profile, auth, and logs     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E3.en `aeat config setup --help`
$ aeat config setup --help
--- stdout ---

 Usage: aeat config setup [OPTIONS]

 Run the schema-driven setup wizard interactively or via flag-driven quiet
 mode

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --profile-name                           TEXT             Profile name to   │
│                                                           write the answers │
│                                                           into              │
│                                                           [default:         │
│                                                           default]          │
│ --quiet                                                   Run the flow      │
│                                                           non-interactively │
│                                                           using only the    │
│                                                           supplied flag     │
│                                                           values            │
│ --accept-defaults                                         Accept the        │
│                                                           descriptor's      │
│                                                           defaults without  │
│                                                           prompting         │
│ --tax-id                                 TEXT             Tax identifier    │
│                                                           (NIF/NIE) for     │
│                                                           declarations      │
│ --name                                   TEXT             Display name      │
│                                                           shown in local    │
│                                                           reviews           │
│ --surnames                               TEXT             Surnames or       │
│                                                           company name for  │
│                                                           export headers    │
│ --activity                               TEXT             Business activity │
│                                                           label or          │
│                                                           controlled key    │
│ --address-postco…                        TEXT             Tax address       │
│                                                           postcode          │
│ --declaration-ty…                        TEXT             Declaration type  │
│                                                           code              │
│ --taxpayer-sex                           TEXT             First taxpayer    │
│                                                           sex code          │
│ --taxpayer-marit…                        TEXT             First taxpayer    │
│                                                           marital status    │
│ --taxpayer-birth…                        TEXT             First taxpayer    │
│                                                           birth date        │
│ --taxpayer-disab…                        TEXT             First taxpayer    │
│                                                           disability code   │
│ --taxpayer-death…                        TEXT             First taxpayer    │
│                                                           death date        │
│ --spouse-tax-id                          TEXT             Spouse NIF/NIE    │
│ --spouse-name                            TEXT             Spouse given name │
│ --spouse-surnames                        TEXT             Spouse surnames   │
│ --spouse-birth-d…                        TEXT             Spouse birth date │
│ --spouse-sex                             TEXT             Spouse sex code   │
│ --spouse-disabil…                        TEXT             Spouse disability │
│                                                           code              │
│ --spouse-non-res…    --no-spouse-non…                     Spouse is         │
│                                                           non-resident IRPF │
│ --spouse-eu-eea-…    --no-spouse-eu-…                     Spouse is EU/EEA  │
│                                                           resident          │
│ --spouse-eu-eea-…                        TEXT             Spouse EU/EEA     │
│                                                           country           │
│ --family-descend…    --no-family-des…                     EU/EEA            │
│                                                           descendants in    │
│                                                           family-unit       │
│                                                           deduction         │
│ --family-minor-c…    --no-family-min…                     Minor children in │
│                                                           family unit       │
│ --iva-regime                             [GENERAL|SIMPLI  IVA regime        │
│                                          FICADO|RECARGO_                    │
│                                          EQUIVALENCIA|EX                    │
│                                          ENTO]                              │
│ --iva-roi-enroll…    --no-iva-roi-en…                     Enrolled in ROI   │
│ --iva-oss-enroll…    --no-iva-oss-en…                     Enrolled in OSS   │
│ --iva-intracommu…    --no-iva-intrac…                     Intra-community   │
│                                                           operations exceed │
│                                                           50,000 EUR        │
│ --enrollment-lar…    --no-enrollment…                     Large-company     │
│                                                           enrollment        │
│ --enrollment-pub…    --no-enrollment…                     Public            │
│                                                           administration    │
│                                                           budget over       │
│                                                           6,000,000         │
│ --has-employees      --no-has-employ…                     Has employees and │
│                                                           pays salaries     │
│                                                           with retención    │
│ --pays-professio…    --no-pays-profe…                     Pays              │
│                                                           professionals     │
│                                                           with retención    │
│ --professional-i…    --no-profession…                     At least 70% of   │
│                                                           professional      │
│                                                           income with prior │
│                                                           retención         │
│ --pays-rent-with…    --no-pays-rent-…                     Pays local rent   │
│                                                           with retención    │
│ --pays-capital-i…    --no-pays-capit…                     Pays capital      │
│                                                           income with       │
│                                                           retención         │
│ --uses-objective…    --no-uses-objec…                     Files IRPF under  │
│                                                           objective         │
│                                                           estimation        │
│ --does-intracomu…    --no-does-intra…                     Conducts          │
│                                                           intracomunitario  │
│                                                           operations        │
│ --third-party-tr…    --no-third-part…                     Third-party       │
│                                                           transactions      │
│                                                           exceed Modelo 347 │
│                                                           threshold         │
│ --bienes-extranj…    --no-bienes-ext…                     Foreign-held      │
│                                                           assets above      │
│                                                           legal threshold   │
│ --tax-residence-…                        [andalucia|arag  Tax-residence     │
│                                          on|asturias|bal  autonomous        │
│                                          eares|canarias|  community         │
│                                          cantabria|casti                    │
│                                          lla_la_mancha|c                    │
│                                          astilla_y_leon|                    │
│                                          cataluna|comuni                    │
│                                          dad_valenciana|                    │
│                                          extremadura|gal                    │
│                                          icia|la_rioja|m                    │
│                                          adrid|murcia]                      │
│ --notes                                  TEXT             Operator notes    │
│                                                           (not consumed by  │
│                                                           the engine)       │
│ --help                                                    Show this message │
│                                                           and exit.         │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E4.en `aeat app archive --help`
$ aeat app archive --help
--- stdout ---

 Usage: aeat app archive [OPTIONS] COMMAND [ARGS]...

 Export and import the encrypted local archive as portable JSON bundles

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ export  Write a portable JSON bundle of the secure object catalogue         │
│ import  Restore an archive bundle into the encrypted secure object          │
│         catalogue                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E5.en `aeat app topic --help`
$ aeat app topic --help
--- stdout ---

 Usage: aeat app topic [OPTIONS] [SLUG] COMMAND [ARGS]...

 Show conceptual help about regimes, modelos, and AEAT processes

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│   slug      [SLUG]  Topic identifier (kebab-case, e.g. iva-regime)          │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E6.en `aeat config setup --quiet --tax-id 00000000T --name X --activity design`
$ aeat config setup --quiet --tax-id 00000000T --name X --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### E7.en `aeat config status` (after success)
$ aeat config status
--- stdout ---
profile	default
tax.id	00000000T
activity	design
iva.regime	GENERAL
tax.residence.ccaa	madrid
--- stderr ---

--- exit 0 ---

===============================================================================
### E1.es `aeat --help`
$ aeat --help
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Spanish tax filing assistant

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Show package version and registry       │
│                                     summary                                 │
│ --format                      TEXT  Output format for command results       │
│                                     [default: text]                         │
│ --quiet                             Show only errors on stderr              │
│ --verbose                           Show internal informational logs on     │
│                                     stderr                                  │
│ --debug                             Show internal debug logs on stderr      │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Manage local configuration and diagnostics                          │
│ app     Tax workspaces for ledgers, invoices, and declarations              │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E2.es `aeat config --help`
$ aeat config --help
--- stdout ---

 Usage: aeat config [OPTIONS] COMMAND [ARGS]...

 Manage local configuration and diagnostics

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ list    List every configuration key with its current value                 │
│ get     Show the current value of one configuration key                     │
│ set     Assign a value to one configuration key                             │
│ unset   Clear the value of one configuration key                            │
│ setup   Run the schema-driven setup wizard interactively or via flag-driven │
│         quiet mode                                                          │
│ status  Show the readiness of the current configuration profile             │
│ reset   Reset operator-entered configuration scopes                         │
│ auth    Configure the active authentication provider                        │
│ doctor  Diagnose local configuration, registry, profile, auth, and logs     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E3.es `aeat config setup --help`
$ aeat config setup --help
--- stdout ---

 Usage: aeat config setup [OPTIONS]

 Run the schema-driven setup wizard interactively or via flag-driven quiet
 mode

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --profile-name                           TEXT             Profile name to   │
│                                                           write the answers │
│                                                           into              │
│                                                           [default:         │
│                                                           default]          │
│ --quiet                                                   Run the flow      │
│                                                           non-interactively │
│                                                           using only the    │
│                                                           supplied flag     │
│                                                           values            │
│ --accept-defaults                                         Accept the        │
│                                                           descriptor's      │
│                                                           defaults without  │
│                                                           prompting         │
│ --tax-id                                 TEXT             Tax identifier    │
│                                                           (NIF/NIE) for     │
│                                                           declarations      │
│ --name                                   TEXT             Display name      │
│                                                           shown in local    │
│                                                           reviews           │
│ --surnames                               TEXT             Surnames or       │
│                                                           company name for  │
│                                                           export headers    │
│ --activity                               TEXT             Business activity │
│                                                           label or          │
│                                                           controlled key    │
│ --address-postco…                        TEXT             Tax address       │
│                                                           postcode          │
│ --declaration-ty…                        TEXT             Declaration type  │
│                                                           code              │
│ --taxpayer-sex                           TEXT             First taxpayer    │
│                                                           sex code          │
│ --taxpayer-marit…                        TEXT             First taxpayer    │
│                                                           marital status    │
│ --taxpayer-birth…                        TEXT             First taxpayer    │
│                                                           birth date        │
│ --taxpayer-disab…                        TEXT             First taxpayer    │
│                                                           disability code   │
│ --taxpayer-death…                        TEXT             First taxpayer    │
│                                                           death date        │
│ --spouse-tax-id                          TEXT             Spouse NIF/NIE    │
│ --spouse-name                            TEXT             Spouse given name │
│ --spouse-surnames                        TEXT             Spouse surnames   │
│ --spouse-birth-d…                        TEXT             Spouse birth date │
│ --spouse-sex                             TEXT             Spouse sex code   │
│ --spouse-disabil…                        TEXT             Spouse disability │
│                                                           code              │
│ --spouse-non-res…    --no-spouse-non…                     Spouse is         │
│                                                           non-resident IRPF │
│ --spouse-eu-eea-…    --no-spouse-eu-…                     Spouse is EU/EEA  │
│                                                           resident          │
│ --spouse-eu-eea-…                        TEXT             Spouse EU/EEA     │
│                                                           country           │
│ --family-descend…    --no-family-des…                     EU/EEA            │
│                                                           descendants in    │
│                                                           family-unit       │
│                                                           deduction         │
│ --family-minor-c…    --no-family-min…                     Minor children in │
│                                                           family unit       │
│ --iva-regime                             [GENERAL|SIMPLI  IVA regime        │
│                                          FICADO|RECARGO_                    │
│                                          EQUIVALENCIA|EX                    │
│                                          ENTO]                              │
│ --iva-roi-enroll…    --no-iva-roi-en…                     Enrolled in ROI   │
│ --iva-oss-enroll…    --no-iva-oss-en…                     Enrolled in OSS   │
│ --iva-intracommu…    --no-iva-intrac…                     Intra-community   │
│                                                           operations exceed │
│                                                           50,000 EUR        │
│ --enrollment-lar…    --no-enrollment…                     Large-company     │
│                                                           enrollment        │
│ --enrollment-pub…    --no-enrollment…                     Public            │
│                                                           administration    │
│                                                           budget over       │
│                                                           6,000,000         │
│ --has-employees      --no-has-employ…                     Has employees and │
│                                                           pays salaries     │
│                                                           with retención    │
│ --pays-professio…    --no-pays-profe…                     Pays              │
│                                                           professionals     │
│                                                           with retención    │
│ --professional-i…    --no-profession…                     At least 70% of   │
│                                                           professional      │
│                                                           income with prior │
│                                                           retención         │
│ --pays-rent-with…    --no-pays-rent-…                     Pays local rent   │
│                                                           with retención    │
│ --pays-capital-i…    --no-pays-capit…                     Pays capital      │
│                                                           income with       │
│                                                           retención         │
│ --uses-objective…    --no-uses-objec…                     Files IRPF under  │
│                                                           objective         │
│                                                           estimation        │
│ --does-intracomu…    --no-does-intra…                     Conducts          │
│                                                           intracomunitario  │
│                                                           operations        │
│ --third-party-tr…    --no-third-part…                     Third-party       │
│                                                           transactions      │
│                                                           exceed Modelo 347 │
│                                                           threshold         │
│ --bienes-extranj…    --no-bienes-ext…                     Foreign-held      │
│                                                           assets above      │
│                                                           legal threshold   │
│ --tax-residence-…                        [andalucia|arag  Tax-residence     │
│                                          on|asturias|bal  autonomous        │
│                                          eares|canarias|  community         │
│                                          cantabria|casti                    │
│                                          lla_la_mancha|c                    │
│                                          astilla_y_leon|                    │
│                                          cataluna|comuni                    │
│                                          dad_valenciana|                    │
│                                          extremadura|gal                    │
│                                          icia|la_rioja|m                    │
│                                          adrid|murcia]                      │
│ --notes                                  TEXT             Operator notes    │
│                                                           (not consumed by  │
│                                                           the engine)       │
│ --help                                                    Show this message │
│                                                           and exit.         │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E4.es `aeat app archive --help`
$ aeat app archive --help
--- stdout ---

 Usage: aeat app archive [OPTIONS] COMMAND [ARGS]...

 Export and import the encrypted local archive as portable JSON bundles

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ export  Write a portable JSON bundle of the secure object catalogue         │
│ import  Restore an archive bundle into the encrypted secure object          │
│         catalogue                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E5.es `aeat app topic --help`
$ aeat app topic --help
--- stdout ---

 Usage: aeat app topic [OPTIONS] [SLUG] COMMAND [ARGS]...

 Show conceptual help about regimes, modelos, and AEAT processes

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│   slug      [SLUG]  Topic identifier (kebab-case, e.g. iva-regime)          │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E6.es `aeat config setup --quiet --tax-id 00000000T --name X --activity design`
$ aeat config setup --quiet --tax-id 00000000T --name X --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### E7.es `aeat config status` (after success)
$ aeat config status
--- stdout ---
profile	default
tax.id	00000000T
activity	design
iva.regime	GENERAL
tax.residence.ccaa	madrid
--- stderr ---

--- exit 0 ---

===============================================================================
### E1.ca `aeat --help`
$ aeat --help
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Spanish tax filing assistant

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Show package version and registry       │
│                                     summary                                 │
│ --format                      TEXT  Output format for command results       │
│                                     [default: text]                         │
│ --quiet                             Show only errors on stderr              │
│ --verbose                           Show internal informational logs on     │
│                                     stderr                                  │
│ --debug                             Show internal debug logs on stderr      │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Manage local configuration and diagnostics                          │
│ app     Tax workspaces for ledgers, invoices, and declarations              │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E2.ca `aeat config --help`
$ aeat config --help
--- stdout ---

 Usage: aeat config [OPTIONS] COMMAND [ARGS]...

 Manage local configuration and diagnostics

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ list    List every configuration key with its current value                 │
│ get     Show the current value of one configuration key                     │
│ set     Assign a value to one configuration key                             │
│ unset   Clear the value of one configuration key                            │
│ setup   Run the schema-driven setup wizard interactively or via flag-driven │
│         quiet mode                                                          │
│ status  Show the readiness of the current configuration profile             │
│ reset   Reset operator-entered configuration scopes                         │
│ auth    Configure the active authentication provider                        │
│ doctor  Diagnose local configuration, registry, profile, auth, and logs     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E3.ca `aeat config setup --help`
$ aeat config setup --help
--- stdout ---

 Usage: aeat config setup [OPTIONS]

 Run the schema-driven setup wizard interactively or via flag-driven quiet
 mode

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --profile-name                           TEXT             Profile name to   │
│                                                           write the answers │
│                                                           into              │
│                                                           [default:         │
│                                                           default]          │
│ --quiet                                                   Run the flow      │
│                                                           non-interactively │
│                                                           using only the    │
│                                                           supplied flag     │
│                                                           values            │
│ --accept-defaults                                         Accept the        │
│                                                           descriptor's      │
│                                                           defaults without  │
│                                                           prompting         │
│ --tax-id                                 TEXT             Tax identifier    │
│                                                           (NIF/NIE) for     │
│                                                           declarations      │
│ --name                                   TEXT             Display name      │
│                                                           shown in local    │
│                                                           reviews           │
│ --surnames                               TEXT             Surnames or       │
│                                                           company name for  │
│                                                           export headers    │
│ --activity                               TEXT             Business activity │
│                                                           label or          │
│                                                           controlled key    │
│ --address-postco…                        TEXT             Tax address       │
│                                                           postcode          │
│ --declaration-ty…                        TEXT             Declaration type  │
│                                                           code              │
│ --taxpayer-sex                           TEXT             First taxpayer    │
│                                                           sex code          │
│ --taxpayer-marit…                        TEXT             First taxpayer    │
│                                                           marital status    │
│ --taxpayer-birth…                        TEXT             First taxpayer    │
│                                                           birth date        │
│ --taxpayer-disab…                        TEXT             First taxpayer    │
│                                                           disability code   │
│ --taxpayer-death…                        TEXT             First taxpayer    │
│                                                           death date        │
│ --spouse-tax-id                          TEXT             Spouse NIF/NIE    │
│ --spouse-name                            TEXT             Spouse given name │
│ --spouse-surnames                        TEXT             Spouse surnames   │
│ --spouse-birth-d…                        TEXT             Spouse birth date │
│ --spouse-sex                             TEXT             Spouse sex code   │
│ --spouse-disabil…                        TEXT             Spouse disability │
│                                                           code              │
│ --spouse-non-res…    --no-spouse-non…                     Spouse is         │
│                                                           non-resident IRPF │
│ --spouse-eu-eea-…    --no-spouse-eu-…                     Spouse is EU/EEA  │
│                                                           resident          │
│ --spouse-eu-eea-…                        TEXT             Spouse EU/EEA     │
│                                                           country           │
│ --family-descend…    --no-family-des…                     EU/EEA            │
│                                                           descendants in    │
│                                                           family-unit       │
│                                                           deduction         │
│ --family-minor-c…    --no-family-min…                     Minor children in │
│                                                           family unit       │
│ --iva-regime                             [GENERAL|SIMPLI  IVA regime        │
│                                          FICADO|RECARGO_                    │
│                                          EQUIVALENCIA|EX                    │
│                                          ENTO]                              │
│ --iva-roi-enroll…    --no-iva-roi-en…                     Enrolled in ROI   │
│ --iva-oss-enroll…    --no-iva-oss-en…                     Enrolled in OSS   │
│ --iva-intracommu…    --no-iva-intrac…                     Intra-community   │
│                                                           operations exceed │
│                                                           50,000 EUR        │
│ --enrollment-lar…    --no-enrollment…                     Large-company     │
│                                                           enrollment        │
│ --enrollment-pub…    --no-enrollment…                     Public            │
│                                                           administration    │
│                                                           budget over       │
│                                                           6,000,000         │
│ --has-employees      --no-has-employ…                     Has employees and │
│                                                           pays salaries     │
│                                                           with retención    │
│ --pays-professio…    --no-pays-profe…                     Pays              │
│                                                           professionals     │
│                                                           with retención    │
│ --professional-i…    --no-profession…                     At least 70% of   │
│                                                           professional      │
│                                                           income with prior │
│                                                           retención         │
│ --pays-rent-with…    --no-pays-rent-…                     Pays local rent   │
│                                                           with retención    │
│ --pays-capital-i…    --no-pays-capit…                     Pays capital      │
│                                                           income with       │
│                                                           retención         │
│ --uses-objective…    --no-uses-objec…                     Files IRPF under  │
│                                                           objective         │
│                                                           estimation        │
│ --does-intracomu…    --no-does-intra…                     Conducts          │
│                                                           intracomunitario  │
│                                                           operations        │
│ --third-party-tr…    --no-third-part…                     Third-party       │
│                                                           transactions      │
│                                                           exceed Modelo 347 │
│                                                           threshold         │
│ --bienes-extranj…    --no-bienes-ext…                     Foreign-held      │
│                                                           assets above      │
│                                                           legal threshold   │
│ --tax-residence-…                        [andalucia|arag  Tax-residence     │
│                                          on|asturias|bal  autonomous        │
│                                          eares|canarias|  community         │
│                                          cantabria|casti                    │
│                                          lla_la_mancha|c                    │
│                                          astilla_y_leon|                    │
│                                          cataluna|comuni                    │
│                                          dad_valenciana|                    │
│                                          extremadura|gal                    │
│                                          icia|la_rioja|m                    │
│                                          adrid|murcia]                      │
│ --notes                                  TEXT             Operator notes    │
│                                                           (not consumed by  │
│                                                           the engine)       │
│ --help                                                    Show this message │
│                                                           and exit.         │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E4.ca `aeat app archive --help`
$ aeat app archive --help
--- stdout ---

 Usage: aeat app archive [OPTIONS] COMMAND [ARGS]...

 Export and import the encrypted local archive as portable JSON bundles

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ export  Write a portable JSON bundle of the secure object catalogue         │
│ import  Restore an archive bundle into the encrypted secure object          │
│         catalogue                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E5.ca `aeat app topic --help`
$ aeat app topic --help
--- stdout ---

 Usage: aeat app topic [OPTIONS] [SLUG] COMMAND [ARGS]...

 Show conceptual help about regimes, modelos, and AEAT processes

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│   slug      [SLUG]  Topic identifier (kebab-case, e.g. iva-regime)          │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E6.ca `aeat config setup --quiet --tax-id 00000000T --name X --activity design`
$ aeat config setup --quiet --tax-id 00000000T --name X --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### E7.ca `aeat config status` (after success)
$ aeat config status
--- stdout ---
profile	default
tax.id	00000000T
activity	design
iva.regime	GENERAL
tax.residence.ccaa	madrid
--- stderr ---

--- exit 0 ---

===============================================================================
### E1.hu `aeat --help`
$ aeat --help
--- stdout ---

 Usage: aeat [OPTIONS] COMMAND [ARGS]...

 Spanish tax filing assistant

 Quickstart: aeat config setup --profile-name NAME --tax-id NIF

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -V            Show package version and registry       │
│                                     summary                                 │
│ --format                      TEXT  Output format for command results       │
│                                     [default: text]                         │
│ --quiet                             Show only errors on stderr              │
│ --verbose                           Show internal informational logs on     │
│                                     stderr                                  │
│ --debug                             Show internal debug logs on stderr      │
│ --install-completion                Install completion for the current      │
│                                     shell.                                  │
│ --show-completion                   Show completion for the current shell,  │
│                                     to copy it or customize the             │
│                                     installation.                           │
│ --help                              Show this message and exit.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ config  Manage local configuration and diagnostics                          │
│ app     Tax workspaces for ledgers, invoices, and declarations              │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E2.hu `aeat config --help`
$ aeat config --help
--- stdout ---

 Usage: aeat config [OPTIONS] COMMAND [ARGS]...

 Manage local configuration and diagnostics

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ list    List every configuration key with its current value                 │
│ get     Show the current value of one configuration key                     │
│ set     Assign a value to one configuration key                             │
│ unset   Clear the value of one configuration key                            │
│ setup   Run the schema-driven setup wizard interactively or via flag-driven │
│         quiet mode                                                          │
│ status  Show the readiness of the current configuration profile             │
│ reset   Reset operator-entered configuration scopes                         │
│ auth    Configure the active authentication provider                        │
│ doctor  Diagnose local configuration, registry, profile, auth, and logs     │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E3.hu `aeat config setup --help`
$ aeat config setup --help
--- stdout ---

 Usage: aeat config setup [OPTIONS]

 Run the schema-driven setup wizard interactively or via flag-driven quiet
 mode

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --profile-name                           TEXT             Profile name to   │
│                                                           write the answers │
│                                                           into              │
│                                                           [default:         │
│                                                           default]          │
│ --quiet                                                   Run the flow      │
│                                                           non-interactively │
│                                                           using only the    │
│                                                           supplied flag     │
│                                                           values            │
│ --accept-defaults                                         Accept the        │
│                                                           descriptor's      │
│                                                           defaults without  │
│                                                           prompting         │
│ --tax-id                                 TEXT             Tax identifier    │
│                                                           (NIF/NIE) for     │
│                                                           declarations      │
│ --name                                   TEXT             Display name      │
│                                                           shown in local    │
│                                                           reviews           │
│ --surnames                               TEXT             Surnames or       │
│                                                           company name for  │
│                                                           export headers    │
│ --activity                               TEXT             Business activity │
│                                                           label or          │
│                                                           controlled key    │
│ --address-postco…                        TEXT             Tax address       │
│                                                           postcode          │
│ --declaration-ty…                        TEXT             Declaration type  │
│                                                           code              │
│ --taxpayer-sex                           TEXT             First taxpayer    │
│                                                           sex code          │
│ --taxpayer-marit…                        TEXT             First taxpayer    │
│                                                           marital status    │
│ --taxpayer-birth…                        TEXT             First taxpayer    │
│                                                           birth date        │
│ --taxpayer-disab…                        TEXT             First taxpayer    │
│                                                           disability code   │
│ --taxpayer-death…                        TEXT             First taxpayer    │
│                                                           death date        │
│ --spouse-tax-id                          TEXT             Spouse NIF/NIE    │
│ --spouse-name                            TEXT             Spouse given name │
│ --spouse-surnames                        TEXT             Spouse surnames   │
│ --spouse-birth-d…                        TEXT             Spouse birth date │
│ --spouse-sex                             TEXT             Spouse sex code   │
│ --spouse-disabil…                        TEXT             Spouse disability │
│                                                           code              │
│ --spouse-non-res…    --no-spouse-non…                     Spouse is         │
│                                                           non-resident IRPF │
│ --spouse-eu-eea-…    --no-spouse-eu-…                     Spouse is EU/EEA  │
│                                                           resident          │
│ --spouse-eu-eea-…                        TEXT             Spouse EU/EEA     │
│                                                           country           │
│ --family-descend…    --no-family-des…                     EU/EEA            │
│                                                           descendants in    │
│                                                           family-unit       │
│                                                           deduction         │
│ --family-minor-c…    --no-family-min…                     Minor children in │
│                                                           family unit       │
│ --iva-regime                             [GENERAL|SIMPLI  IVA regime        │
│                                          FICADO|RECARGO_                    │
│                                          EQUIVALENCIA|EX                    │
│                                          ENTO]                              │
│ --iva-roi-enroll…    --no-iva-roi-en…                     Enrolled in ROI   │
│ --iva-oss-enroll…    --no-iva-oss-en…                     Enrolled in OSS   │
│ --iva-intracommu…    --no-iva-intrac…                     Intra-community   │
│                                                           operations exceed │
│                                                           50,000 EUR        │
│ --enrollment-lar…    --no-enrollment…                     Large-company     │
│                                                           enrollment        │
│ --enrollment-pub…    --no-enrollment…                     Public            │
│                                                           administration    │
│                                                           budget over       │
│                                                           6,000,000         │
│ --has-employees      --no-has-employ…                     Has employees and │
│                                                           pays salaries     │
│                                                           with retención    │
│ --pays-professio…    --no-pays-profe…                     Pays              │
│                                                           professionals     │
│                                                           with retención    │
│ --professional-i…    --no-profession…                     At least 70% of   │
│                                                           professional      │
│                                                           income with prior │
│                                                           retención         │
│ --pays-rent-with…    --no-pays-rent-…                     Pays local rent   │
│                                                           with retención    │
│ --pays-capital-i…    --no-pays-capit…                     Pays capital      │
│                                                           income with       │
│                                                           retención         │
│ --uses-objective…    --no-uses-objec…                     Files IRPF under  │
│                                                           objective         │
│                                                           estimation        │
│ --does-intracomu…    --no-does-intra…                     Conducts          │
│                                                           intracomunitario  │
│                                                           operations        │
│ --third-party-tr…    --no-third-part…                     Third-party       │
│                                                           transactions      │
│                                                           exceed Modelo 347 │
│                                                           threshold         │
│ --bienes-extranj…    --no-bienes-ext…                     Foreign-held      │
│                                                           assets above      │
│                                                           legal threshold   │
│ --tax-residence-…                        [andalucia|arag  Tax-residence     │
│                                          on|asturias|bal  autonomous        │
│                                          eares|canarias|  community         │
│                                          cantabria|casti                    │
│                                          lla_la_mancha|c                    │
│                                          astilla_y_leon|                    │
│                                          cataluna|comuni                    │
│                                          dad_valenciana|                    │
│                                          extremadura|gal                    │
│                                          icia|la_rioja|m                    │
│                                          adrid|murcia]                      │
│ --notes                                  TEXT             Operator notes    │
│                                                           (not consumed by  │
│                                                           the engine)       │
│ --help                                                    Show this message │
│                                                           and exit.         │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E4.hu `aeat app archive --help`
$ aeat app archive --help
--- stdout ---

 Usage: aeat app archive [OPTIONS] COMMAND [ARGS]...

 Export and import the encrypted local archive as portable JSON bundles

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ export  Write a portable JSON bundle of the secure object catalogue         │
│ import  Restore an archive bundle into the encrypted secure object          │
│         catalogue                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E5.hu `aeat app topic --help`
$ aeat app topic --help
--- stdout ---

 Usage: aeat app topic [OPTIONS] [SLUG] COMMAND [ARGS]...

 Show conceptual help about regimes, modelos, and AEAT processes

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│   slug      [SLUG]  Topic identifier (kebab-case, e.g. iva-regime)          │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---

===============================================================================
### E6.hu `aeat config setup --quiet --tax-id 00000000T --name X --activity design`
$ aeat config setup --quiet --tax-id 00000000T --name X --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### E7.hu `aeat config status` (after success)
$ aeat config status
--- stdout ---
profile	default
tax.id	00000000T
activity	design
iva.regime	GENERAL
tax.residence.ccaa	madrid
--- stderr ---

--- exit 0 ---
```

## SCENARIO F — Recovery and round-trip

```text


# SCENARIO F — Recovery and round-trip

===============================================================================
### F0. precondition quiet setup
$ aeat config setup --quiet --tax-id 00000000T --name Carlos --activity design
--- stdout ---

--- stderr ---

--- exit 0 ---

===============================================================================
### F1. `aeat config set tax.id 99999999R`
$ aeat config set tax.id 99999999R
--- stdout ---
tax.id	99999999R
--- stderr ---

--- exit 0 ---

===============================================================================
### F2. `aeat config get tax.id`
$ aeat config get tax.id
--- stdout ---
tax.id	99999999R
--- stderr ---

--- exit 0 ---

===============================================================================
### F3. `aeat config set TAX.ID 11111111H` (case-insensitive lookup)
$ aeat config set TAX.ID 11111111H
--- stdout ---
tax.id	11111111H
--- stderr ---

--- exit 0 ---

===============================================================================
### F4. `aeat config reset --scope PROFILE --yes`
$ aeat config reset --scope PROFILE --yes
--- stdout ---
scope	PROFILE
removed_profiles	1
removed_auth	False
--- stderr ---

--- exit 0 ---

===============================================================================
### F5. `aeat config status` (after reset)
$ aeat config status
--- stdout ---
REFUSED: The command input failed validation.
  detail: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
  error_type: ValidationError
  original_exception: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
--- stderr ---
REFUSED: The command input failed validation.
  detail: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
  error_type: ValidationError
  original_exception: 2 validation errors for SetupAnswers
tax_id
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
activity
  Field required [type=missing, input_value={'spouse_non_resident_irp...sidence_ccaa': 'madrid'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
--- exit 2 ---

===============================================================================
### F6. `aeat config reset --scope ALL --yes`
$ aeat config reset --scope ALL --yes
--- stdout ---
scope	ALL
removed_profiles	0
removed_auth	True
--- stderr ---

--- exit 0 ---
```

## SCENARIO G — Per-flag derived signature inspection

```text


# SCENARIO G — Per-flag derived signature inspection

### G1. inspect.signature(build_wizard_command(SETUP_FLOW)) parameters
profile_name: typing.Annotated[str, <typer.models.OptionInfo object at 0x000002150A9F1F90>]
quiet: typing.Annotated[bool, <typer.models.OptionInfo object at 0x000002150A9F20D0>]
accept_defaults: typing.Annotated[bool, <typer.models.OptionInfo object at 0x000002150A9F2210>]
tax_id: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF110>]
name: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF610>]
surnames: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF4D0>]
activity: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF890>]
address_postcode: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DED50>]
declaration_type: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DEE90>]
taxpayer_sex: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF390>]
taxpayer_marital_status: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DFB10>]
taxpayer_birth_date: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF750>]
taxpayer_disability_grade: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF9D0>]
taxpayer_death_date: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DEFD0>]
spouse_tax_id: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DF250>]
spouse_name: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DFC50>]
spouse_surnames: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DFD90>]
spouse_birth_date: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A8DFED0>]
spouse_sex: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A9F0050>]
spouse_disability_grade: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A9F0190>]
spouse_non_resident_irpf: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F02D0>]
spouse_eu_eea_resident: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0410>]
spouse_eu_eea_country: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A9F0550>]
family_descendants_eu_eea_deduction: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0690>]
family_minor_children_in_unit: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F07D0>]
iva_regime: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A9F0910>]
iva_roi_enrolled: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0A50>]
iva_oss_enrolled: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0B90>]
iva_intracommunity_operations_exceed_50000_eur: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0CD0>]
enrollment_large_company: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0E10>]
enrollment_public_administration_budget_gt_6000000: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F0F50>]
has_employees: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1090>]
pays_professionals_with_retencion: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F11D0>]
professional_income_withholding_ge_70pct: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1310>]
pays_rent_with_retencion: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1450>]
pays_capital_income_with_retencion: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1590>]
uses_objective_estimation_irpf: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F16D0>]
does_intracomunitario: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1810>]
third_party_transactions_above_347_threshold: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1950>]
bienes_extranjero_above_threshold: typing.Annotated[bool | None, <typer.models.OptionInfo object at 0x000002150A9F1A90>]
tax_residence_ccaa: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A9F1D10>]
notes: typing.Annotated[str | None, <typer.models.OptionInfo object at 0x000002150A9F1E50>]

===============================================================================
### G2. `aeat config setup --help` (es)
$ aeat config setup --help
--- stdout ---

 Usage: aeat config setup [OPTIONS]

 Ejecutar el asistente de configuración basado en esquema de forma interactiva
 o usando banderas

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --profile-name                           TEXT             Nombre del perfil │
│                                                           donde guardar las │
│                                                           respuestas        │
│                                                           [default:         │
│                                                           default]          │
│ --quiet                                                   Ejecutar el flujo │
│                                                           sin interacción   │
│                                                           usando solo los   │
│                                                           valores de las    │
│                                                           banderas          │
│ --accept-defaults                                         Aceptar los       │
│                                                           valores por       │
│                                                           defecto del       │
│                                                           descriptor sin    │
│                                                           preguntar         │
│ --tax-id                                 TEXT             Identificador     │
│                                                           fiscal (NIF/NIE)  │
│                                                           para              │
│                                                           declaraciones     │
│ --name                                   TEXT             Nombre visible    │
│                                                           mostrado en       │
│                                                           revisiones        │
│                                                           locales           │
│ --surnames                               TEXT             Apellidos o razón │
│                                                           social para       │
│                                                           cabeceras de      │
│                                                           exportación       │
│ --activity                               TEXT             Etiqueta de       │
│                                                           actividad o clave │
│                                                           controlada        │
│ --address-postco…                        TEXT             Código postal del │
│                                                           domicilio fiscal  │
│ --declaration-ty…                        TEXT             Código del tipo   │
│                                                           de declaración    │
│ --taxpayer-sex                           TEXT             Sexo del primer   │
│                                                           declarante        │
│ --taxpayer-marit…                        TEXT             Estado civil del  │
│                                                           primer declarante │
│ --taxpayer-birth…                        TEXT             Fecha de          │
│                                                           nacimiento del    │
│                                                           primer declarante │
│ --taxpayer-disab…                        TEXT             Clave de          │
│                                                           discapacidad del  │
│                                                           primer declarante │
│ --taxpayer-death…                        TEXT             Fecha de          │
│                                                           fallecimiento del │
│                                                           primer declarante │
│ --spouse-tax-id                          TEXT             NIF/NIE del       │
│                                                           cónyuge           │
│ --spouse-name                            TEXT             Nombre del        │
│                                                           cónyuge           │
│ --spouse-surnames                        TEXT             Apellidos del     │
│                                                           cónyuge           │
│ --spouse-birth-d…                        TEXT             Fecha de          │
│                                                           nacimiento del    │
│                                                           cónyuge           │
│ --spouse-sex                             TEXT             Sexo del cónyuge  │
│ --spouse-disabil…                        TEXT             Clave de          │
│                                                           discapacidad del  │
│                                                           cónyuge           │
│ --spouse-non-res…    --no-spouse-non…                     Cónyuge no        │
│                                                           residente IRPF    │
│ --spouse-eu-eea-…    --no-spouse-eu-…                     Cónyuge residente │
│                                                           UE/EEE            │
│ --spouse-eu-eea-…                        TEXT             País UE/EEE del   │
│                                                           cónyuge           │
│ --family-descend…    --no-family-des…                     Descendientes     │
│                                                           UE/EEE en         │
│                                                           deducción de      │
│                                                           unidad familiar   │
│ --family-minor-c…    --no-family-min…                     Hijos menores en  │
│                                                           unidad familiar   │
│ --iva-regime                             [GENERAL|SIMPLI  Régimen IVA       │
│                                          FICADO|RECARGO_                    │
│                                          EQUIVALENCIA|EX                    │
│                                          ENTO]                              │
│ --iva-roi-enroll…    --no-iva-roi-en…                     Alta en ROI       │
│ --iva-oss-enroll…    --no-iva-oss-en…                     Alta en OSS       │
│ --iva-intracommu…    --no-iva-intrac…                     Operaciones       │
│                                                           intracomunitarias │
│                                                           superan 50.000    │
│                                                           EUR               │
│ --enrollment-lar…    --no-enrollment…                     Empresa de gran   │
│                                                           volumen           │
│ --enrollment-pub…    --no-enrollment…                     Presupuesto       │
│                                                           administración    │
│                                                           pública superior  │
│                                                           a 6.000.000       │
│ --has-employees      --no-has-employ…                     Tiene empleados y │
│                                                           paga salarios con │
│                                                           retención         │
│ --pays-professio…    --no-pays-profe…                     Paga a            │
│                                                           profesionales con │
│                                                           retención         │
│ --professional-i…    --no-profession…                     Al menos 70% de   │
│                                                           los ingresos      │
│                                                           profesionales con │
│                                                           retención previa  │
│ --pays-rent-with…    --no-pays-rent-…                     Paga alquiler de  │
│                                                           local con         │
│                                                           retención         │
│ --pays-capital-i…    --no-pays-capit…                     Paga rentas de    │
│                                                           capital con       │
│                                                           retención         │
│ --uses-objective…    --no-uses-objec…                     Tributa IRPF en   │
│                                                           estimación        │
│                                                           objetiva          │
│ --does-intracomu…    --no-does-intra…                     Realiza           │
│                                                           operaciones       │
│                                                           intracomunitarias │
│ --third-party-tr…    --no-third-part…                     Operaciones con   │
│                                                           terceros superan  │
│                                                           el umbral del     │
│                                                           Modelo 347        │
│ --bienes-extranj…    --no-bienes-ext…                     Bienes en el      │
│                                                           extranjero        │
│                                                           superan el umbral │
│                                                           legal             │
│ --tax-residence-…                        [andalucia|arag  Comunidad         │
│                                          on|asturias|bal  autónoma de       │
│                                          eares|canarias|  residencia fiscal │
│                                          cantabria|casti                    │
│                                          lla_la_mancha|c                    │
│                                          astilla_y_leon|                    │
│                                          cataluna|comuni                    │
│                                          dad_valenciana|                    │
│                                          extremadura|gal                    │
│                                          icia|la_rioja|m                    │
│                                          adrid|murcia]                      │
│ --notes                                  TEXT             Notas del         │
│                                                           operador (no      │
│                                                           consumidas por el │
│                                                           motor)            │
│ --help                                                    Show this message │
│                                                           and exit.         │
└─────────────────────────────────────────────────────────────────────────────┘

--- stderr ---

--- exit 0 ---
```
