``aeat config`` — command reference
===================================

This page documents every leaf command under ``aeat config``. Help strings are rendered in English; the CLI respects the active output-language setting at runtime.

``aeat config auth apoderado check``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only live verification

**Command path:** ``aeat config auth apoderado check``

**Registry key:** ``config.auth.apoderado.check``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ApoderadoCheckResult``.

``aeat config auth apoderado clear``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retire the apoderado configuration

**Command path:** ``aeat config auth apoderado clear``

**Registry key:** ``config.auth.apoderado.clear``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ApoderadoClearResult``.

``aeat config auth apoderado configure``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Set active apoderado configuration

**Command path:** ``aeat config auth apoderado configure``

**Registry key:** ``config.auth.apoderado.configure``

**Parameters**

``--represented-nif``
   *Option, required.* NIF of the represented party

``--scope``
   *Option, required.* Scope tokens (can be repeated)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ApoderadoConfigureResult``.

``aeat config auth apoderado scopes list``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List accepted apoderado scopes

**Command path:** ``aeat config auth apoderado scopes list``

**Registry key:** ``config.auth.apoderado.scopes.list``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ApoderadoScopesListResult``.

``aeat config auth apoderado status``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show active apoderado configuration

**Command path:** ``aeat config auth apoderado status``

**Registry key:** ``config.auth.apoderado.status``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ApoderadoStatusResult``.

``aeat config auth clear``
~~~~~~~~~~~~~~~~~~~~~~~~~~
Clear local authentication metadata

**Command path:** ``aeat config auth clear``

**Registry key:** ``config.auth.clear``

**Parameters**

``--provider``
   *Option, optional.* No description.

``--all``
   *Option, optional.* Clear all configured auth providers

``--sessions``
   *Option, optional.* Clear persisted AEAT auth sessions

``--locks``
   *Option, optional.* Clear auth acquisition locks

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthClearResult``.

``aeat config auth configure``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Configure the active authentication provider

**Command path:** ``aeat config auth configure``

**Registry key:** ``config.auth.configure``

**Parameters**

``--provider``
   *Option, required.* Authentication provider id (e.g. certificado-electronico)

``--file``
   *Option, optional.* Path to the credential file (certificate or key)

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthConfigureResult``.

``aeat config auth diagnostics list``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List encrypted Cl@ve auth diagnostics.

**Command path:** ``aeat config auth diagnostics list``

**Registry key:** ``config.auth.diagnostics.list``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthDiagnosticsListResult``.

``aeat config auth diagnostics report``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Record the operator-observed Cl@ve app state for one auth diagnostic.

**Command path:** ``aeat config auth diagnostics report``

**Registry key:** ``config.auth.diagnostics.report``

**Parameters**

``diagnostic_id``
   *Argument, required.* Diagnostic id.

``--phone-state``
   *Option, required.* One of: app_prompted_and_accepted, app_prompted_not_accepted, app_did_not_prompt, operator_did_not_check.

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthDiagnosticsReportResult``.

``aeat config auth diagnostics show``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show one redacted encrypted auth diagnostic.

**Command path:** ``aeat config auth diagnostics show``

**Registry key:** ``config.auth.diagnostics.show``

**Parameters**

``diagnostic_id``
   *Argument, required.* Diagnostic id.

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthDiagnosticsShowResult``.

``aeat config auth login``
~~~~~~~~~~~~~~~~~~~~~~~~~~
Acquire or verify a live AEAT session

**Command path:** ``aeat config auth login``

**Registry key:** ``config.auth.login``

**Parameters**

``--provider``
   *Option, optional.* No description.

``--fresh``
   *Option, optional.* Force a new live authentication instead of reusing a saved AEAT session

``--reset-lock``
   *Option, optional.* Clear a stale auth acquisition lock before starting

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthLoginResult``.

``aeat config auth providers``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List supported authentication providers

**Command path:** ``aeat config auth providers``

**Registry key:** ``config.auth.providers``

**Parameters**

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthProvidersResult``.

``aeat config auth status``
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show configured authentication state

**Command path:** ``aeat config auth status``

**Registry key:** ``config.auth.status``

**Parameters**

``--provider``
   *Option, optional.* No description.

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthStatusResult``.

``aeat config auth test``
~~~~~~~~~~~~~~~~~~~~~~~~~
Check local authentication readiness

**Command path:** ``aeat config auth test``

**Registry key:** ``config.auth.test``

**Parameters**

``--provider``
   *Option, optional.* No description.

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.AuthTestResult``.

``aeat config bucket history``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the append-only event history for one bucket

**Command path:** ``aeat config bucket history``

**Registry key:** ``config.bucket.history``

**Parameters**

``bucket_id``
   *Argument, required.* Bucket identifier whose event history should be inspected

``--event-type``
   *Option, optional.* Filter the history to one or more event types (repeatable)

``--since``
   *Option, optional.* Filter the history to events at or after this ISO-8601 timestamp (e.g. 2026-04-01T00:00:00+00:00)

``--until``
   *Option, optional.* Filter the history to events at or before this ISO-8601 timestamp (e.g. 2026-04-30T23:59:59+00:00)

``--object-id``
   *Option, optional.* Filter the history to events targeting a specific object_id (exact match)

``--actor``
   *Option, optional.* Filter the history to events recorded by a specific actor (exact match)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.BucketHistoryResult``.

``aeat config google folder get``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the configured Google Drive root folder

**Command path:** ``aeat config google folder get``

**Registry key:** ``config.google.folder.get``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleFolderGetResult``.

``aeat config google folder set``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bind a Google Drive folder id to the active profile

**Command path:** ``aeat config google folder set``

**Registry key:** ``config.google.folder.set``

**Parameters**

``folder_id``
   *Argument, required.* Google Drive folder id

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleFolderSetResult``.

``aeat config google login``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Run the OAuth consent flow (or refresh an existing credential)

**Command path:** ``aeat config google login``

**Registry key:** ``config.google.login``

**Parameters**

``--refresh-only``
   *Option, optional.* Skip the consent screen and refresh an existing credential only

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleLoginResult``.

``aeat config google logout``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Clear the refresh token and metadata; preserve the registered client

**Command path:** ``aeat config google logout``

**Registry key:** ``config.google.logout``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleLogoutResult``.

``aeat config google register``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Register a Cloud Console Desktop OAuth client JSON for the active profile

**Command path:** ``aeat config google register``

**Registry key:** ``config.google.register``

**Parameters**

``--client-json``
   *Option, required.* Path to a Cloud Console Desktop OAuth client JSON file

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleRegisterResult``.

``aeat config google status``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the current Google OAuth session state for the active profile

**Command path:** ``aeat config google status``

**Registry key:** ``config.google.status``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleStatusResult``.

``aeat config google sync calc export``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Export the registry calculation surface for a modelo+period to a Google Sheets workbook in the operator's `aeat-vault/`

**Command path:** ``aeat config google sync calc export``

**Registry key:** ``config.google.sync.calc.export``

**Parameters**

``--modelo``
   *Option, required.* Modelo id to export (e.g. 130, 303, 100)

``--period``
   *Option, required.* Filing period code (e.g. 1T, 2T, 0A)

``--year``
   *Option, required.* Filing year (e.g. 2025)

``--prefill-relations``
   *Option, optional.* Prefill cross-revision relation values from the local observation store before exporting (annual roll-ups, prior-quarter carry-forward etc.)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncCalcExportResult``.

``aeat config google sync calc pull``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read operator-edited cells back from a calc-sheets workbook into typed records (after validating the workbook's registry-SHA stamp)

**Command path:** ``aeat config google sync calc pull``

**Registry key:** ``config.google.sync.calc.pull``

**Parameters**

``--modelo``
   *Option, required.* Modelo id to export (e.g. 130, 303, 100)

``--period``
   *Option, required.* Filing period code (e.g. 1T, 2T, 0A)

``--year``
   *Option, required.* Filing year (e.g. 2025)

``--spreadsheet-id``
   *Option, required.* Drive file id of the workbook to read operator edits from (must be app-owned and bound to the supplied snapshot)

``--compute``
   *Option, optional.* After pulling, run the local Decimal runtime against the pulled inputs and emit the computed casilla values

``--assemble-observations``
   *Option, optional.* After pulling, reassemble Detalle-tab row-set cells into typed observations (perceptors, foreign assets, related-party operations, atribución members, refund operations) and emit them in the payload alongside the raw row_set_edits

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncCalcPullResult``.

``aeat config google sync calc verify``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Three-way parity check of a modelo's calculation surface (AEAT oracle vs local Decimal runtime vs Sheets workbook)

**Command path:** ``aeat config google sync calc verify``

**Registry key:** ``config.google.sync.calc.verify``

**Parameters**

``--modelo``
   *Option, required.* Modelo id to export (e.g. 130, 303, 100)

``--period``
   *Option, required.* Filing period code (e.g. 1T, 2T, 0A)

``--year``
   *Option, required.* Filing year (e.g. 2025)

``--scenario``
   *Option, optional.* Path to a JSON scenario file with operator inputs and an optional AEAT-published expected-output map

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncCalcVerifyResult``.

``aeat config google sync probe``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Probe the configured Google Drive folder for read/write access

**Command path:** ``aeat config google sync probe``

**Registry key:** ``config.google.sync.probe``

**Parameters**

``--read-only``
   *Option, optional.* Probe Google Drive in read-only mode (no writes attempted)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncProbeResult``.

``aeat config google sync push``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Push the local data namespaces to the configured Google Drive folder

**Command path:** ``aeat config google sync push``

**Registry key:** ``config.google.sync.push``

**Parameters**

``--namespace``
   *Option, optional.* Namespace to push (repeatable; defaults to every namespace)

``--limit``
   *Option, optional.* Maximum number of files to push (defaults to no limit)

``--dry-run``
   *Option, optional.* Plan the push without uploading any files

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncPushResult``.

``aeat config profile census apply``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Overwrite the profile with census values reported by AEAT

**Command path:** ``aeat config profile census apply``

**Registry key:** ``config.profile.census.apply``

**Parameters**

``--snapshot-id``
   *Option, optional.* Specific snapshot id (prefixes accepted)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._profile_census_payloads.CensusApplyResult``.

``aeat config profile census compare``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Compare AEAT census and this profile field by field

**Command path:** ``aeat config profile census compare``

**Registry key:** ``config.profile.census.compare``

**Parameters**

``--snapshot-id``
   *Option, optional.* Specific snapshot id (prefixes accepted)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._profile_census_payloads.CensusCompareResult``.

``aeat config profile census refresh``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Download the latest census from AEAT and save a snapshot

**Command path:** ``aeat config profile census refresh``

**Registry key:** ``config.profile.census.refresh``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._profile_census_payloads.CensusRefreshResult``.

``aeat config profile census show``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the latest census AEAT reported for this profile

**Command path:** ``aeat config profile census show``

**Registry key:** ``config.profile.census.show``

**Parameters**

``--snapshot-id``
   *Option, optional.* Specific snapshot id (prefixes accepted)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config._profile_census_payloads.CensusShowResult``.

``aeat config profile create``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Initialize a new active profile and config bucket.

**Command path:** ``aeat config profile create``

**Registry key:** ``config.profile.create``

**Parameters**

``profile_name``
   *Argument, required.* Profile name to write the answers into

``--quiet``
   *Option, optional.* Run non-interactively using only the supplied flag values; required flags left unset cause an error. Sufficient on its own; combine with --accept-defaults to fill the rest from descriptor defaults.

``--accept-defaults``
   *Option, optional.* Fill every unsupplied flag from the descriptor defaults, without prompting. Use alongside --quiet, or on its own for an all-defaults create.

``--entity-type``
   *Option, optional.* Natural person, legal entity, or attribution entity

``--legal-entity-form``
   *Option, optional.* Recognised legal form when the entity type is a legal entity

``--irpf-income-categories``
   *Option, optional.* IRPF income category; pass --irpf-income-categories once per category

``--incn-prior-12-months``
   *Option, optional.* Net turnover (importe neto de la cifra de negocios) over the prior 12 months, in euros. Above 6,000,000 EUR Modelo 202 mandates the Art. 40.3 LIS modality; below it both modalities are available. Optional.

``--new-entity-first-two-profit-periods``
   *Option, optional.* Mark this when a newly-created legal entity is in one of its first two profit-making tax periods (LIS Art. 29) to opt into the 15 percent reduced rate. Optional; unset leaves the entity on its otherwise-applicable rate.

``--tax-id``
   *Option, optional.* Tax identifier (NIF/NIE) for the active profile

``--name``
   *Option, optional.* Display name shown in local reviews

``--surnames``
   *Option, optional.* Surnames or company name for export headers

``--activity``
   *Option, optional.* Business activity as plain text, or the IAE heading if you know it

``--address-postcode``
   *Option, optional.* Tax address postcode

``--activity-start-date``
   *Option, optional.* Census registration / start-of-activity date (YYYY-MM-DD). Optional; when set, obligations for periods before this date are not shown.

``--taxation-type``
   *Option, optional.* Income-tax return type: 1 = individual, 2 = joint (family unit).

``--output-language``
   *Option, optional.* CLI output language for this profile

``--taxpayer-sex``
   *Option, optional.* First taxpayer sex: H = male, M = female.

``--taxpayer-marital-status``
   *Option, optional.* First taxpayer marital status: 1 = single, 2 = married, 3 = widowed, 4 = separated or divorced.

``--situacion-familiar``
   *Option, optional.* Family situation under Art. 82 LIRPF: determines whether joint taxation is available and which family unit variant applies.

``--taxpayer-marriage-date``
   *Option, optional.* Start date of the current marriage (YYYY-MM-DD). Only when marital status = 2 (married). Derives casillas 0245/0246/0247 (matrimonio sobrevenido, Art. 82 LIRPF).

``--taxpayer-birth-date``
   *Option, optional.* First taxpayer birth date

``--taxpayer-disability-grade``
   *Option, optional.* First taxpayer disability grade: 1 = 33%-64%, 2 = 65% or higher, 3 = judicial incapacity, 4 = third-party assistance or reduced mobility.

``--taxpayer-death-date``
   *Option, optional.* First taxpayer death date

``--spouse-tax-id``
   *Option, optional.* Spouse NIF/NIE

``--spouse-name``
   *Option, optional.* Spouse given name

``--spouse-surnames``
   *Option, optional.* Spouse surnames

``--spouse-birth-date``
   *Option, optional.* Spouse birth date

``--spouse-sex``
   *Option, optional.* Spouse sex: H = male, M = female.

``--spouse-disability-grade``
   *Option, optional.* Spouse disability grade (if applicable): 1 = 33%-64%, 2 = 65% or higher, 3 = judicial incapacity, 4 = third-party assistance or reduced mobility.

``--spouse-non-resident-irpf``
   *Option, optional.* Spouse is non-resident IRPF

``--spouse-eu-eea-resident``
   *Option, optional.* Spouse is EU/EEA resident

``--spouse-eu-eea-country``
   *Option, optional.* Spouse EU/EEA country

``--family-descendants-eu-eea-deduction``
   *Option, optional.* EU/EEA descendants in family-unit deduction

``--family-minor-children-in-unit``
   *Option, optional.* Minor children in family unit

``--iva-regime``
   *Option, optional.* IVA regime

``--iva-roi-enrolled``
   *Option, optional.* Enrolled in ROI

``--iva-oss-enrolled``
   *Option, optional.* Enrolled in OSS

``--iva-sii-enrolled``
   *Option, optional.* Whether the taxpayer is enrolled in the SII

``--iva-redeme-enrolled``
   *Option, optional.* Whether the taxpayer is registered in REDEME

``--iva-intracommunity-operations-exceed-50000-eur``
   *Option, optional.* Intra-community operations exceed 50,000 EUR

``--enrollment-large-company``
   *Option, optional.* Large-company enrollment

``--enrollment-public-administration-budget-gt-6000000``
   *Option, optional.* Public administration budget over 6,000,000

``--has-employees``
   *Option, optional.* Has employees and pays salaries with retención

``--pays-professionals-with-retencion``
   *Option, optional.* Pays professionals with retención

``--professional-income-withholding-ge-70pct``
   *Option, optional.* At least 70% of professional income with prior retención

``--pays-rent-with-retencion``
   *Option, optional.* Pays local rent with retención

``--pays-capital-income-with-retencion``
   *Option, optional.* Pays capital income with retención

``--uses-objective-estimation-irpf``
   *Option, optional.* Files IRPF under objective estimation

``--irpf-estimation-regime``
   *Option, optional.* IRPF estimation regime for economic-activity income

``--irpf-special-regime``
   *Option, optional.* IRPF special regime. "general" for most taxpayers. "impatriado" for workers who relocated to Spain and elected the Beckham Law regime (Art. 93 LIRPF), available for the first 6 years after relocation.

``--irpf-special-regime-start-date``
   *Option, optional.* Date the worker elected the inpatriate regime (YYYY-MM-DD). Only when irpf-special-regime is "impatriado". RIRPF Art. 116. The regime expires at the end of the 6th calendar year.

``--does-intracomunitario``
   *Option, optional.* Conducts intracomunitario operations

``--third-party-transactions-above-347-threshold``
   *Option, optional.* Third-party transactions exceed Modelo 347 threshold

``--bienes-extranjero-above-threshold``
   *Option, optional.* Foreign-held assets above legal threshold

``--fiscal-residency``
   *Option, optional.* Fiscal residency category: resident_irpf (habitual resident in Spain) or non_resident_irnr (non-resident, IRNR taxation RDLeg 5/2004).

``--country-of-fiscal-residence``
   *Option, optional.* ISO 3166-1 alpha-2 code of the country of fiscal residence (e.g. GB, DE, FR). Required when fiscal-residency is non_resident_irnr.

``--representante-fiscal-nif``
   *Option, optional.* NIF/NIE of the fiscal representative in Spain. Required for non-EU/EEA non-residents (Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004).

``--representante-fiscal-nombre``
   *Option, optional.* Full name of the fiscal representative in Spain.

``--tax-residence-ccaa``
   *Option, optional.* Tax-residence autonomous community. One of: andalucia, aragon, asturias, baleares, canarias, cantabria, castilla_la_mancha, castilla_y_leon, cataluna, comunidad_valenciana, extremadura, galicia, la_rioja, madrid, murcia, pais_vasco, navarra.

``--notes``
   *Option, optional.* Notes for your own records (optional)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileCreateResult``.

``aeat config profile delete``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a profile and its on-disk state (--yes confirms)

**Command path:** ``aeat config profile delete``

**Registry key:** ``config.profile.delete``

**Parameters**

``name``
   *Argument, required.* Profile name to delete

``--yes``
   *Option, optional.* Explicitly confirm the delete operation

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileDeleteResult``.

``aeat config profile duplicate``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Copy a profile under a new id and display name

**Command path:** ``aeat config profile duplicate``

**Registry key:** ``config.profile.duplicate``

**Parameters**

``source``
   *Argument, required.* Source profile id to duplicate

``target``
   *Argument, required.* Target profile id for the duplicate

``--display-name``
   *Option, optional.* Display name for the new profile (defaults to the target id)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileDuplicateResult``.

``aeat config profile edit``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Re-run the wizard against an existing profile and update values in place

**Command path:** ``aeat config profile edit``

**Registry key:** ``config.profile.edit``

**Parameters**

``profile_name``
   *Argument, required.* Profile name to write the answers into

``--quiet``
   *Option, optional.* Run non-interactively using only the supplied flag values; required flags left unset cause an error. Sufficient on its own; combine with --accept-defaults to fill the rest from descriptor defaults.

``--accept-defaults``
   *Option, optional.* Fill every unsupplied flag from the descriptor defaults, without prompting. Use alongside --quiet, or on its own for an all-defaults create.

``--entity-type``
   *Option, optional.* Natural person, legal entity, or attribution entity

``--legal-entity-form``
   *Option, optional.* Recognised legal form when the entity type is a legal entity

``--irpf-income-categories``
   *Option, optional.* IRPF income category; pass --irpf-income-categories once per category

``--incn-prior-12-months``
   *Option, optional.* Net turnover (importe neto de la cifra de negocios) over the prior 12 months, in euros. Above 6,000,000 EUR Modelo 202 mandates the Art. 40.3 LIS modality; below it both modalities are available. Optional.

``--new-entity-first-two-profit-periods``
   *Option, optional.* Mark this when a newly-created legal entity is in one of its first two profit-making tax periods (LIS Art. 29) to opt into the 15 percent reduced rate. Optional; unset leaves the entity on its otherwise-applicable rate.

``--tax-id``
   *Option, optional.* Tax identifier (NIF/NIE) for the active profile

``--name``
   *Option, optional.* Display name shown in local reviews

``--surnames``
   *Option, optional.* Surnames or company name for export headers

``--activity``
   *Option, optional.* Business activity as plain text, or the IAE heading if you know it

``--address-postcode``
   *Option, optional.* Tax address postcode

``--activity-start-date``
   *Option, optional.* Census registration / start-of-activity date (YYYY-MM-DD). Optional; when set, obligations for periods before this date are not shown.

``--taxation-type``
   *Option, optional.* Income-tax return type: 1 = individual, 2 = joint (family unit).

``--output-language``
   *Option, optional.* CLI output language for this profile

``--taxpayer-sex``
   *Option, optional.* First taxpayer sex: H = male, M = female.

``--taxpayer-marital-status``
   *Option, optional.* First taxpayer marital status: 1 = single, 2 = married, 3 = widowed, 4 = separated or divorced.

``--situacion-familiar``
   *Option, optional.* Family situation under Art. 82 LIRPF: determines whether joint taxation is available and which family unit variant applies.

``--taxpayer-marriage-date``
   *Option, optional.* Start date of the current marriage (YYYY-MM-DD). Only when marital status = 2 (married). Derives casillas 0245/0246/0247 (matrimonio sobrevenido, Art. 82 LIRPF).

``--taxpayer-birth-date``
   *Option, optional.* First taxpayer birth date

``--taxpayer-disability-grade``
   *Option, optional.* First taxpayer disability grade: 1 = 33%-64%, 2 = 65% or higher, 3 = judicial incapacity, 4 = third-party assistance or reduced mobility.

``--taxpayer-death-date``
   *Option, optional.* First taxpayer death date

``--spouse-tax-id``
   *Option, optional.* Spouse NIF/NIE

``--spouse-name``
   *Option, optional.* Spouse given name

``--spouse-surnames``
   *Option, optional.* Spouse surnames

``--spouse-birth-date``
   *Option, optional.* Spouse birth date

``--spouse-sex``
   *Option, optional.* Spouse sex: H = male, M = female.

``--spouse-disability-grade``
   *Option, optional.* Spouse disability grade (if applicable): 1 = 33%-64%, 2 = 65% or higher, 3 = judicial incapacity, 4 = third-party assistance or reduced mobility.

``--spouse-non-resident-irpf``
   *Option, optional.* Spouse is non-resident IRPF

``--spouse-eu-eea-resident``
   *Option, optional.* Spouse is EU/EEA resident

``--spouse-eu-eea-country``
   *Option, optional.* Spouse EU/EEA country

``--family-descendants-eu-eea-deduction``
   *Option, optional.* EU/EEA descendants in family-unit deduction

``--family-minor-children-in-unit``
   *Option, optional.* Minor children in family unit

``--iva-regime``
   *Option, optional.* IVA regime

``--iva-roi-enrolled``
   *Option, optional.* Enrolled in ROI

``--iva-oss-enrolled``
   *Option, optional.* Enrolled in OSS

``--iva-sii-enrolled``
   *Option, optional.* Whether the taxpayer is enrolled in the SII

``--iva-redeme-enrolled``
   *Option, optional.* Whether the taxpayer is registered in REDEME

``--iva-intracommunity-operations-exceed-50000-eur``
   *Option, optional.* Intra-community operations exceed 50,000 EUR

``--enrollment-large-company``
   *Option, optional.* Large-company enrollment

``--enrollment-public-administration-budget-gt-6000000``
   *Option, optional.* Public administration budget over 6,000,000

``--has-employees``
   *Option, optional.* Has employees and pays salaries with retención

``--pays-professionals-with-retencion``
   *Option, optional.* Pays professionals with retención

``--professional-income-withholding-ge-70pct``
   *Option, optional.* At least 70% of professional income with prior retención

``--pays-rent-with-retencion``
   *Option, optional.* Pays local rent with retención

``--pays-capital-income-with-retencion``
   *Option, optional.* Pays capital income with retención

``--uses-objective-estimation-irpf``
   *Option, optional.* Files IRPF under objective estimation

``--irpf-estimation-regime``
   *Option, optional.* IRPF estimation regime for economic-activity income

``--irpf-special-regime``
   *Option, optional.* IRPF special regime. "general" for most taxpayers. "impatriado" for workers who relocated to Spain and elected the Beckham Law regime (Art. 93 LIRPF), available for the first 6 years after relocation.

``--irpf-special-regime-start-date``
   *Option, optional.* Date the worker elected the inpatriate regime (YYYY-MM-DD). Only when irpf-special-regime is "impatriado". RIRPF Art. 116. The regime expires at the end of the 6th calendar year.

``--does-intracomunitario``
   *Option, optional.* Conducts intracomunitario operations

``--third-party-transactions-above-347-threshold``
   *Option, optional.* Third-party transactions exceed Modelo 347 threshold

``--bienes-extranjero-above-threshold``
   *Option, optional.* Foreign-held assets above legal threshold

``--fiscal-residency``
   *Option, optional.* Fiscal residency category: resident_irpf (habitual resident in Spain) or non_resident_irnr (non-resident, IRNR taxation RDLeg 5/2004).

``--country-of-fiscal-residence``
   *Option, optional.* ISO 3166-1 alpha-2 code of the country of fiscal residence (e.g. GB, DE, FR). Required when fiscal-residency is non_resident_irnr.

``--representante-fiscal-nif``
   *Option, optional.* NIF/NIE of the fiscal representative in Spain. Required for non-EU/EEA non-residents (Art. 47 LGT + Art. 10 TRLIRNR RDLeg 5/2004).

``--representante-fiscal-nombre``
   *Option, optional.* Full name of the fiscal representative in Spain.

``--tax-residence-ccaa``
   *Option, optional.* Tax-residence autonomous community. One of: andalucia, aragon, asturias, baleares, canarias, cantabria, castilla_la_mancha, castilla_y_leon, cataluna, comunidad_valenciana, extremadura, galicia, la_rioja, madrid, murcia, pais_vasco, navarra.

``--notes``
   *Option, optional.* Notes for your own records (optional)

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileEditResult``.

``aeat config profile export``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Write a portable profile bundle to a JSON file

**Command path:** ``aeat config profile export``

**Registry key:** ``config.profile.export``

**Parameters**

``name``
   *Argument, optional.* Profile to export; defaults to the active profile

``--to``
   *Option, required.* Destination path for the JSON bundle

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileExportResult``.

``aeat config profile import``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Register a portable profile bundle from a JSON file

**Command path:** ``aeat config profile import``

**Registry key:** ``config.profile.import``

**Parameters**

``path``
   *Argument, required.* Path to the profile bundle JSON file

``--label``
   *Option, optional.* Display name for the imported profile; defaults to the name stored in the bundle. Use it to import a second copy under a fresh label.

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileImportResult``.

``aeat config profile list``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List every registered profile and mark the active one

**Command path:** ``aeat config profile list``

**Registry key:** ``config.profile.list``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigListResult``.

``aeat config profile logout``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sign out of the active profile by clearing the local pointer

**Command path:** ``aeat config profile logout``

**Registry key:** ``config.profile.logout``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileLogoutResult``.

``aeat config profile rename``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rename a profile in place; the active-profile pointer follows automatically

**Command path:** ``aeat config profile rename``

**Registry key:** ``config.profile.rename``

**Parameters**

``source``
   *Argument, required.* Existing profile name

``target``
   *Argument, required.* New profile name

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileRenameResult``.

``aeat config profile show``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the live values of a profile (defaults to the active profile)

**Command path:** ``aeat config profile show``

**Registry key:** ``config.profile.show``

**Parameters**

``name``
   *Argument, optional.* Profile id to show (defaults to the active profile)

``--output-language``, ``--language``
   *Option, optional.* Output language for the response text (es, en, ca, hu).

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileShowResult``.

``aeat config profile status``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the readiness of the current configuration profile

**Command path:** ``aeat config profile status``

**Registry key:** ``config.profile.status``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigStatusResult``.

``aeat config profile switch``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Switch the active profile

**Command path:** ``aeat config profile switch``

**Registry key:** ``config.profile.switch``

**Parameters**

``name``
   *Argument, required.* Profile name to activate

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigProfileSwitchResult``.

``aeat config repair connectivity``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Check browser and AEAT Sede connectivity

**Command path:** ``aeat config repair connectivity``

**Registry key:** ``config.repair.connectivity``

**Parameters**

``--target``
   *Option, optional.* Connectivity target to probe

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairConnectivityResult``.

``aeat config repair integrity objects``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Probe AES-256-GCM tag verification across one namespace (or all).

**Command path:** ``aeat config repair integrity objects``

**Registry key:** ``config.repair.integrity.objects``

**Parameters**

``--namespace``
   *Option, optional.* Restrict the integrity probe to one namespace.

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairIntegrityObjectsResult``.

``aeat config repair integrity registry``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Run full registry validation (the opt-in cross-domain integrity probe).

**Command path:** ``aeat config repair integrity registry``

**Registry key:** ``config.repair.integrity.registry``

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairIntegrityRegistryResult``.

``aeat config repair logs``
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Show the log file path and recent lines

**Command path:** ``aeat config repair logs``

**Registry key:** ``config.repair.logs``

**Parameters**

``--lines``
   *Option, optional.* Number of recent log lines to show

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairLogsResult``.

``aeat config repair profile``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Inspect and repair the active-profile pointer.

**Command path:** ``aeat config repair profile``

**Registry key:** ``config.repair.profile``

**Parameters**

``--profile``
   *Option, optional.* Inspect a specific registered profile bucket.

``--clear-active``
   *Option, optional.* Clear a pointer-file active profile only when it points at unreadable profile state.

``--repair-manifest-status``
   *Option, optional.* Backfill a legacy active bucket manifest status from the encrypted profile record.

``--yes``
   *Option, optional.* Confirm repair.

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairProfileResult``.

``aeat config repair quarantine``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Preview undecryptable rows; active quarantine is disabled by preserve-first repair policy

**Command path:** ``aeat config repair quarantine``

**Registry key:** ``config.repair.quarantine``

**Parameters**

``--yes``
   *Option, optional.* Explicitly confirm the quarantine operation

``--dry-run``
   *Option, optional.* Preview the rows that would be quarantined without moving anything

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairQuarantineResult``.

``aeat config repair reset-state``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Drop the unreadable workflow-state envelope (destructive; requires --yes)

**Command path:** ``aeat config repair reset-state``

**Registry key:** ``config.repair.reset_state``

**Parameters**

``--yes``
   *Option, optional.* Explicitly confirm the workflow-state reset

``--dry-run``
   *Option, optional.* Report the envelope fingerprint without deleting the row

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.RepairResetStateResult``.

``aeat config reset``
~~~~~~~~~~~~~~~~~~~~~
Reset operator-entered configuration scopes

**Command path:** ``aeat config reset``

**Registry key:** ``config.reset``

**Parameters**

``--scope``
   *Option, optional.* Scope to reset. profile: delete every profile bucket (manifests, DEKs, declarations, ledger and invoice reviews). auth: clear the persisted AEAT/SEDE auth session. data: quarantine unreadable secure-object rows across all namespaces. all: apply profile, auth, and data together.

``--yes``
   *Option, optional.* Explicitly confirm the reset operation

**Output schema**

This command emits a ``SchemaEnvelope`` whose ``result`` field is validated against ``aeat.entrypoints.cli._config_payloads.ConfigResetResult``.

