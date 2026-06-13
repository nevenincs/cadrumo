---
tags:
  - '#reference'
  - '#core-authority-imports-v2'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# `core-authority-imports-v2` reference: AST import-layer audit

Mechanical AST-based full-codebase import audit of `src/aeat/`. Every `.py` file parsed via `ast.Import` / `ast.ImportFrom` nodes. Relative imports resolved to absolute `aeat.<...>` paths before classification. TYPE_CHECKING guards and local-scope imports counted separately. 1,655 files scanned.

**Delta vs first audit:** first audit reported 1 production violation / 164 test violations. This audit finds **278 production / 245 test**. The gap was caused by the first audit failing to resolve relative imports and missing local-scope and TYPE_CHECKING-guarded edges. The 1-violation number was an artifact of grep-only top-level analysis.

## 1. 5x5 Layer Matrix

Rows = importer layer. Columns = imported layer. All ctx modes included (normal + TYPE_CHECKING + local_scope).

| Importer \ Imported | core | domain | application | adapters | entrypoints |
|---|---|---|---|---|---|
| **core** | 342 | 36 | 13 | 4 | 0 |
| **domain** | 318 | 1472 | 7 | 119 | 5 |
| **application** | 456 | 640 | 1049 | 286 | 1 |
| **adapters** | 322 | 107 | 52 | 1002 | 0 |
| **entrypoints** | 139 | 151 | 300 | 100 | 187 |

Illegal directed pairs:

| Pair | Edge Count | Illegal |
|---|---|---|
| **core -> domain** | **36** | YES |
| **core -> application** | **13** | YES |
| **core -> adapters** | **4** | YES |
| **domain -> application** | **7** | YES |
| **domain -> adapters** | **119** | YES |
| **domain -> entrypoints** | **5** | YES |
| **application -> adapters** | **286** | YES |
| **application -> entrypoints** | **1** | YES |
| **adapters -> application** | **52** | YES |

## 2. Domain-Pair Matrix (cross-sub, top 60 by count)

| Count | From sub-domain | To sub-domain |
|---|---|---|
| 13 | calculations | iva |
| 13 | invoices | iva |
| 10 | iva | calculations |
| 10 | iva | invoices |
| 8 | fincas | calculations |
| 7 | calculations | deadlines |
| 6 | filing | calculations |
| 6 | usage_ratios | categories |
| 5 | calculations | user_profile |
| 5 | invoices | transactions |
| 4 | calculations | renta |
| 4 | modelos | calculations |
| 4 | renta | categories |
| 3 | modelos | profile |
| 3 | profile | _keys |
| 3 | renta | calculations |
| 3 | user_profile | calculations |
| 3 | user_profile | modelos |
| 2 | calculations | profile |
| 2 | deadlines | calculations |
| 2 | filing | modelos |
| 2 | iva | fincas |
| 2 | profile | errors |
| 1 | _identifiers | _errors |
| 1 | attachments | _enums |
| 1 | attachments | _errors |
| 1 | attachments | _models |
| 1 | attachments | _repository |
| 1 | buckets | profile |
| 1 | buckets | _errors |
| 1 | buckets | _event |
| 1 | buckets | _event_repository |
| 1 | calculations | registry |
| 1 | calculations | filing |
| 1 | calculations | modelos |
| 1 | calculations | categories |
| 1 | calculations | fincas |
| 1 | calculations | domain |
| 1 | categories | _corpus |
| 1 | categories | _profile |
| 1 | categories | _proportionality |
| 1 | categories | _registry |
| 1 | categories | _spending_category |
| 1 | currency | _errors |
| 1 | currency | _models |
| 1 | currency | _service |
| 1 | deadlines | profile |
| 1 | deadlines | _engine |
| 1 | deadlines | _errors |
| 1 | deadlines | _festivos |
| 1 | deadlines | _models |
| 1 | deadlines | _plazo |
| 1 | deadlines | _profiles |
| 1 | deadlines | _recargo |
| 1 | filing | submission |
| 1 | filing | _amendment |
| 1 | filing | _complementaria_repository |
| 1 | filing | _errors |
| 1 | filing | _protocols |
| 1 | filing | _repository |

## 3. Production Violation List (278 total)

Breakdown by reason:

- `application->adapters`: 143
- `domain->adapters`: 89
- `core->domain`: 25
- `adapters->application`: 17
- `domain->application`: 2
- `core->application`: 2

Breakdown by context:

- `normal`: 152
- `local_scope`: 109
- `type_checking`: 17

### 3.1 `application->adapters` (143 edges)

- `src\aeat\application\aggregation\_modelo_bindings.py:11` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\auth\_apoderado.py:28` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\auth\_apoderado.py:33` ctx:normal | `aeat.adapters.persistence.storage.envelope._secure_repository`
- `src\aeat\application\auth\_diagnostics.py:12` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\auth\_diagnostics.py:13` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\auth\_diagnostics.py:14` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\auth\_operator.py:30` ctx:type_checking | `aeat.adapters.outbound.aeat.auth.certificate`
- `src\aeat\application\auth\_operator.py:229` ctx:local_scope | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\auth\_operator.py:670` ctx:local_scope | `aeat.adapters.outbound.aeat.auth._clave_movil`
- `src\aeat\application\auth\_operator.py:807` ctx:local_scope | `aeat.adapters.outbound.aeat.auth.certificate`
- `src\aeat\application\auth\_operator.py:905` ctx:local_scope | `aeat.adapters.outbound.aeat.auth.certificate`
- `src\aeat\application\auth\_operator.py:932` ctx:local_scope | `aeat.adapters.outbound.aeat.auth._clave_movil`
- `src\aeat\application\auth\_sessions.py:15` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\auth\_sessions.py:30` ctx:type_checking | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\auth\_sessions.py:211` ctx:local_scope | `aeat.adapters.outbound.aeat.browser`
- `src\aeat\application\auth\_sessions.py:329` ctx:local_scope | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\auth\_sessions.py:466` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\auth\_sessions.py:546` ctx:local_scope | `aeat.adapters.outbound.aeat.browser`
- `src\aeat\application\calculations\_iva_compensation_history.py:13` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\calculations\_iva_compensation_history.py:14` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\calculations\_iva_compensation_history.py:19` ctx:normal | `aeat.adapters.persistence.storage.envelope._secure_repository`
- `src\aeat\application\calculations\_iva_wallet_reconciliation.py:18` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\calculations\_multi_year.py:37` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\calculations\_observations_repository.py:31` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\calculations\_observations_repository.py:39` ctx:normal | `aeat.adapters.persistence.storage.envelope._secure_repository`
- `src\aeat\application\calculations\_relation_prefill.py:34` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\config_reset.py:148` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\diagnostics.py:31` ctx:type_checking | `aeat.adapters.outbound.aeat.browser`
- `src\aeat\application\diagnostics.py:32` ctx:type_checking | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\diagnostics.py:199` ctx:local_scope | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\diagnostics.py:298` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\diagnostics.py:401` ctx:local_scope | `aeat.adapters.outbound.aeat.browser`
- `src\aeat\application\diagnostics.py:412` ctx:local_scope | `aeat.adapters.outbound.aeat.browser`
- `src\aeat\application\diagnostics.py:434` ctx:local_scope | `aeat.adapters.outbound.aeat.browser`
- `src\aeat\application\diagnostics.py:435` ctx:local_scope | `aeat.adapters.outbound.aeat.browser._site_health`
- `src\aeat\application\diagnostics.py:547` ctx:local_scope | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\diagnostics.py:550` ctx:local_scope | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\diagnostics.py:893` ctx:local_scope | `aeat.adapters.persistence.storage.master_key._active_session`
- `src\aeat\application\diagnostics.py:1036` ctx:local_scope | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\evidence\_service.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\evidence\_service.py:16` ctx:normal | `aeat.adapters.persistence.storage.envelope`
- `src\aeat\application\evidence\_service.py:17` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\filing\_export.py:36` ctx:normal | `aeat.adapters.inbound.pdf._utils`
- `src\aeat\application\filing\_history_repository.py:14` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\filing\_history_repository.py:18` ctx:normal | `aeat.adapters.persistence.storage.envelope._secure_repository`
- `src\aeat\application\filing\_history_repository.py:19` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\filing\_history_repository.py:20` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\filing\_import.py:24` ctx:normal | `aeat.adapters.inbound.justificante`
- `src\aeat\application\filing\_runtime_repository.py:5` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\filing\_runtime_repository.py:6` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\inventory\_service.py:11` ctx:normal | `aeat.adapters.persistence.profile.inventory`
- `src\aeat\application\inventory\_service.py:12` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\invoices\_source_resolver.py:8` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\ledger\_actions.py:21` ctx:normal | `aeat.adapters.inbound.financial.providers`
- `src\aeat\application\ledger\_actions.py:31` ctx:normal | `aeat.adapters.inbound.pdf._utils`
- `src\aeat\application\ledger\_actions.py:32` ctx:normal | `aeat.adapters.persistence.storage.attachment`
- `src\aeat\application\ledger\_rule_repository.py:7` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\ledger\_rule_repository.py:8` ctx:normal | `aeat.adapters.persistence.storage.envelope._secure_repository`
- `src\aeat\application\live\_borrador_100.py:22` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_borrador_100.py:25` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_borrador_100.py:28` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\live\_borrador_100.py:29` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\live\_borrador_100.py:30` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\live\_censo.py:27` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_censo.py:30` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_censo.py:33` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\live\_censo.py:34` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\live\_censo.py:35` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\live\_errors.py:8` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\live\_errors.py:13` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\live\_expedientes.py:32` ctx:normal | `aeat.adapters.outbound.aeat.sede._declarations`
- `src\aeat\application\live\_expedientes.py:33` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_expedientes.py:34` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\live\_notifications.py:42` ctx:normal | `aeat.adapters.outbound.aeat.sede._notifications`
- `src\aeat\application\live\_notifications.py:46` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_notifications.py:47` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\live\_snapshot_base.py:42` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_snapshot_base.py:43` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\live\_snapshot_base.py:44` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\live\_snapshot_base.py:45` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\live\_verify.py:33` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\_verify.py:34` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\live\_verify.py:35` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\live\_verify.py:37` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\modelo\_borrador_binding.py:22` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\modelo\_reconcile.py:162` ctx:local_scope | `aeat.adapters.inbound.justificante`
- `src\aeat\application\repair_integrity.py:41` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\repair_integrity.py:44` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\repair_integrity.py:49` ctx:normal | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\repair_integrity.py:218` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\repair_integrity.py:298` ctx:local_scope | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\repair_integrity.py:407` ctx:local_scope | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\review\conftest.py:11` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\state_projection.py:34` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\storage\calc_sheets\_parity_harness.py:325` ctx:local_scope | `aeat.adapters.outbound.google._calc_sheets_apply`
- `src\aeat\application\user_profile\_aggregate.py:25` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\user_profile\_censo_sync.py:202` ctx:local_scope | `aeat.adapters.outbound.aeat.sede._censo_live`
- `src\aeat\application\user_profile\_orchestration.py:22` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\user_profile\_orchestration.py:23` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\_orchestration.py:120` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_orchestration.py:121` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\user_profile\_orchestration.py:155` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_profile_repository.py:38` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_profile_repository.py:39` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\user_profile\_profile_repository.py:40` ctx:normal | `aeat.adapters.persistence.storage.bucket._keystore_paths`
- `src\aeat\application\user_profile\_profile_repository.py:41` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\user_profile\_profile_repository.py:42` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\user_profile\_profile_repository.py:48` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\user_profile\_profile_repository.py:49` ctx:normal | `aeat.adapters.persistence.storage.master_key._kdf_params`
- `src\aeat\application\user_profile\_profile_repository.py:50` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\_profile_repository.py:318` ctx:local_scope | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\user_profile\_repository.py:25` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_repository.py:28` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_repository.py:31` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_repository.py:34` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\user_profile\_repository.py:35` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\_repository.py:61` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\_testing.py:16` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\verification\_verify.py:11` ctx:normal | `aeat.adapters.inbound.declaracion`
- `src\aeat\application\workflow\_adapters.py:25` ctx:type_checking | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\workflow\_adapters.py:139` ctx:local_scope | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\workflow\_adapters.py:148` ctx:local_scope | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\workflow\_models.py:28` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\workflow\_models.py:38` ctx:type_checking | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\workflow\_models.py:343` ctx:normal | `aeat.adapters.outbound.aeat.browser._site_health`
- `src\aeat\application\workflow\_persistence.py:12` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\workflow\_persistence.py:15` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\workflow\_persistence.py:18` ctx:normal | `aeat.adapters.persistence.storage.envelope._envelope`
- `src\aeat\application\workflow\_persistence.py:19` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\workflow\_persistence.py:25` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\workflow\_persistence.py:29` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\workflow\_persistence.py:136` ctx:local_scope | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\workflow\_profile_bucket_scan.py:34` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\workflow\_profile_bucket_scan.py:35` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\workflow\_profile_bucket_scan.py:36` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\workflow\_profile_bucket_scan.py:37` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\workflow\_profile_bucket_scan.py:38` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\workflow\_profile_health.py:10` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\workflow\_profile_health.py:11` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\workflow\_profile_health.py:12` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\workflow\_profile_health.py:13` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\workflow\_profile_health.py:297` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\workflow\_protocols.py:25` ctx:normal | `aeat.adapters.outbound.aeat.export`

### 3.2 `domain->adapters` (89 edges)

- `src\aeat\domain\buckets\_event_repository.py:7` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\buckets\_event_repository.py:8` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\buckets\_event_repository.py:9` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\domain\buckets\_event_repository.py:10` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\filing\_complementaria_repository.py:15` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\filing\_complementaria_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\filing\_complementaria_repository.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\filing\_repository.py:14` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\filing\_repository.py:15` ctx:normal | `aeat.adapters.persistence.storage.envelope`
- `src\aeat\domain\filing\_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\filing\_repository.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\filing\_runtime_repository.py:5` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\domain\filing\_runtime_repository.py:6` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:33` ctx:type_checking | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:39` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:55` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:66` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:67` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:76` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:85` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:86` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:135` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:136` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:147` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:186` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:193` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:212` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:213` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:222` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:223` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:241` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:242` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:306` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:325` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:337` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:338` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:370` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:371` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:399` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:417` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:418` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:437` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:438` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:455` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:456` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:466` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:498` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:517` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:529` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:530` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\fincas\_repository.py:568` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\fincas\_repository.py:569` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\invoices\_repository.py:19` ctx:type_checking | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\invoices\_repository.py:31` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\domain\invoices\_repository.py:91` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\domain\invoices\_repository.py:107` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\invoices\_repository.py:114` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\invoices\_repository.py:132` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\domain\invoices\_repository.py:156` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\domain\invoices\_repository.py:157` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\justificante\_repository.py:23` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\justificante\_repository.py:24` ctx:normal | `aeat.adapters.persistence.storage.envelope`
- `src\aeat\domain\justificante\_repository.py:25` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\modelos\_calculation_repository.py:7` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\_calculation_repository.py:8` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\modelos\_calculation_repository.py:9` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\modelos\_filing_repository.py:7` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\_filing_repository.py:8` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\modelos\_filing_repository.py:9` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\modelos\_repository.py:15` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\modelos\_repository.py:20` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\modelos\_runtime_repository.py:5` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\domain\modelos\_runtime_repository.py:6` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\modelos\_verification_repository.py:7` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\_verification_repository.py:8` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\modelos\_verification_repository.py:9` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\submission\_engine.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\submission\_repository.py:14` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\submission\_repository.py:15` ctx:normal | `aeat.adapters.persistence.storage.envelope`
- `src\aeat\domain\submission\_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\transactions\_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.envelope._envelope`
- `src\aeat\domain\transactions\_repository.py:17` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\transactions\_repository.py:18` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\domain\transactions\_repository.py:34` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\domain\usage_ratios\_service.py:16` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\usage_ratios\_service.py:17` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\usage_ratios\_service.py:18` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\domain\usage_ratios\_service.py:19` ctx:normal | `aeat.adapters.persistence.storage.sql`

### 3.3 `core->domain` (25 edges)

- `src\aeat\core\resources\_repos\apoderamientos.py:15` ctx:local_scope | `aeat.domain.auth.apoderamientos`
- `src\aeat\core\resources\_repos\category_profiles.py:11` ctx:type_checking | `aeat.domain.categories`
- `src\aeat\core\resources\_repos\category_profiles.py:23` ctx:local_scope | `aeat.domain.categories`
- `src\aeat\core\resources\_repos\holiday_calendars.py:15` ctx:local_scope | `aeat.domain.deadlines`
- `src\aeat\core\resources\_repos\iva_catalogues.py:26` ctx:local_scope | `aeat.domain.iva._catalogue`
- `src\aeat\core\resources\_repos\iva_rate_tables.py:11` ctx:type_checking | `aeat.domain.iva`
- `src\aeat\core\resources\_repos\iva_rate_tables.py:25` ctx:local_scope | `aeat.domain.iva._rates`
- `src\aeat\core\resources\_repos\legal_parameters.py:11` ctx:type_checking | `aeat.domain.calculations.registry`
- `src\aeat\core\resources\_repos\legal_parameters.py:24` ctx:local_scope | `aeat.domain.calculations.registry`
- `src\aeat\core\resources\_repos\manuals.py:24` ctx:type_checking | `aeat.domain.manuals`
- `src\aeat\core\resources\_repos\manuals.py:67` ctx:local_scope | `aeat.domain.manuals`
- `src\aeat\core\resources\_repos\manuals.py:85` ctx:local_scope | `aeat.domain.manuals`
- `src\aeat\core\resources\_repos\manuals.py:98` ctx:local_scope | `aeat.domain.manuals`
- `src\aeat\core\resources\_repos\manuals.py:110` ctx:local_scope | `aeat.domain.manuals`
- `src\aeat\core\resources\_repos\modelos.py:20` ctx:type_checking | `aeat.domain.calculations.registry`
- `src\aeat\core\resources\_repos\modelos.py:21` ctx:type_checking | `aeat.domain.calculations.registry._schema`
- `src\aeat\core\resources\_repos\modelos.py:43` ctx:local_scope | `aeat.domain.calculations.registry`
- `src\aeat\core\resources\_repos\modelos.py:61` ctx:local_scope | `aeat.domain.calculations.registry`
- `src\aeat\core\resources\_repos\normatives.py:12` ctx:type_checking | `aeat.domain.normatives`
- `src\aeat\core\resources\_repos\normatives.py:13` ctx:type_checking | `aeat.domain.normatives._schema`
- `src\aeat\core\resources\_repos\normatives.py:36` ctx:local_scope | `aeat.domain.normatives`
- `src\aeat\core\resources\_repos\normatives.py:46` ctx:local_scope | `aeat.domain.normatives`
- `src\aeat\core\resources\_repos\normatives.py:52` ctx:local_scope | `aeat.domain.normatives`
- `src\aeat\core\resources\_repos\recargo_bands.py:15` ctx:local_scope | `aeat.domain.deadlines`
- `src\aeat\core\resources\_repos\user_profile.py:15` ctx:local_scope | `aeat.domain.user_profile`

### 3.4 `adapters->application` (17 edges)

- `src\aeat\adapters\outbound\aeat\auth\_authenticator.py:1146` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:746` ctx:local_scope | `aeat.application.user_profile._orchestration`
- `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:747` ctx:local_scope | `aeat.application.user_profile._projections`
- `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:748` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:749` ctx:local_scope | `aeat.application.workflow._profile_bucket_scan`
- `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:860` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\auth\_providers.py:15` ctx:normal | `aeat.application.auth`
- `src\aeat\adapters\outbound\aeat\browser\_factory.py:112` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\sede\_declarations.py:358` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\google\_calc_sheets_apply.py:43` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\adapters\outbound\google\_calc_sheets_pull.py:54` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\adapters\outbound\google\_calc_sheets_pull.py:55` ctx:normal | `aeat.application.storage.calc_sheets._engine`
- `src\aeat\adapters\outbound\google\_calc_sheets_pull.py:56` ctx:normal | `aeat.application.storage.calc_sheets._layout`
- `src\aeat\adapters\outbound\google\_calc_sheets_pull.py:57` ctx:normal | `aeat.application.storage.calc_sheets._records`
- `src\aeat\adapters\outbound\google\_oauth_flow.py:24` ctx:normal | `aeat.application.user_profile._orchestration`
- `src\aeat\adapters\outbound\google\_oauth_flow.py:75` ctx:local_scope | `aeat.application.workflow._profile_bucket_scan`
- `src\aeat\adapters\outbound\google\_profile_binding.py:21` ctx:normal | `aeat.application.workflow._models`

### 3.5 `domain->application` (2 edges)

- `src\aeat\domain\profile\_keys.py:137` ctx:local_scope | `aeat.application.wizard._compiler`
- `src\aeat\domain\profile\conftest.py:13` ctx:normal | `aeat.application.wizard`

### 3.6 `core->application` (2 edges)

- `src\aeat\core\resources\_repos\topics.py:10` ctx:type_checking | `aeat.application.topics`
- `src\aeat\core\resources\_repos\topics.py:20` ctx:local_scope | `aeat.application.topics`

## 4. Test Violation List (245 total)

Breakdown by reason:

- `application->adapters`: 143
- `adapters->application`: 35
- `domain->adapters`: 30
- `core->domain`: 11
- `core->application`: 11
- `domain->application`: 5
- `domain->entrypoints`: 5
- `core->adapters`: 4
- `application->entrypoints`: 1

### 4.1 `application->adapters` (143 edges)

- `src\aeat\application\aggregation\test_fx_conversion.py:49` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\aggregation\test_iva_ledger.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\aggregation\test_modelo_source_mesh_ledger.py:14` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\aggregation\test_renta_income_aggregation.py:22` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\aggregation\test_renta_ledger.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\aggregation\test_source_mesh.py:10` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\aggregation\test_source_mesh_profile_live.py:12` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\auth\test_diagnostics.py:11` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\auth\test_diagnostics.py:12` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\auth\test_ensure_session.py:13` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\auth\test_ensure_session.py:26` ctx:type_checking | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\auth\test_ensure_session.py:226` ctx:local_scope | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\auth\test_operator.py:12` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\auth\test_persisted_session_metadata.py:11` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\calculations\test_iva_compensation_history.py:11` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\calculations\test_iva_compensation_history.py:12` ctx:normal | `aeat.adapters.outbound.aeat.sede._schema`
- `src\aeat\application\calculations\test_iva_wallet_reconciliation.py:11` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\calculations\test_observations_repository.py:235` ctx:local_scope | `aeat.adapters.persistence.storage.envelope._envelope`
- `src\aeat\application\calculations\test_observations_repository_roundtrip.py:206` ctx:local_scope | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\application\calculations\test_observations_repository_roundtrip.py:207` ctx:local_scope | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\application\evidence\test_evidence.py:23` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\filing\reconciliation\test_reconcile.py:11` ctx:normal | `aeat.adapters.inbound.justificante`
- `src\aeat\application\filing\test_complementaria_repository.py:17` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\filing\test_complementaria_repository.py:18` ctx:normal | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\filing\test_complementaria_repository.py:141` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\filing\test_history_repository.py:15` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\filing\test_history_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\filing\test_history_repository.py:108` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\filing\test_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\filing\test_repository.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\filing\test_repository.py:143` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\inventory\test_inventory.py:12` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\inventory\test_inventory.py:13` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\ledger\test_actions.py:16` ctx:normal | `aeat.adapters.persistence.storage.attachment`
- `src\aeat\application\ledger\test_actions.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\ledger\test_actions.py:18` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\ledger\test_business_operation_invoice.py:11` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\ledger\test_evidence.py:10` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\ledger\test_merge.py:25` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\ledger\test_merge.py:26` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\ledger\test_preflight.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\ledger\test_preflight.py:13` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\ledger\test_split.py:30` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\ledger\test_split.py:31` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\live\test_borrador_100.py:12` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_borrador_100.py:15` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_borrador_100.py:19` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\live\test_borrador_100_roundtrip.py:23` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\live\test_borrador_100_roundtrip.py:174` ctx:local_scope | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\application\live\test_borrador_100_roundtrip.py:175` ctx:local_scope | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\application\live\test_census_snapshot.py:21` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_census_snapshot.py:446` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_expedientes.py:11` ctx:normal | `aeat.adapters.outbound.aeat.sede._declarations`
- `src\aeat\application\live\test_expedientes.py:12` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_filed_capture_calculation_history.py:14` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\live\test_iva_live_failure_taxonomy.py:7` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\live\test_iva_live_failure_taxonomy.py:8` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\live\test_iva_remote_state_acquisition.py:13` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\live\test_iva_remote_state_acquisition.py:14` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\live\test_iva_remote_state_acquisition.py:15` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_iva_remote_state_acquisition.py:16` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\live\test_iva_wallet_capture_backend.py:13` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\live\test_iva_wallet_live.py:12` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\live\test_iva_wallet_live.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_notifications.py:12` ctx:normal | `aeat.adapters.outbound.aeat.sede._notifications`
- `src\aeat\application\live\test_notifications.py:16` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_snapshot_base.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\live\test_snapshot_base.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\live\test_verify.py:11` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\modelo\test_bucket_aggregation_flow.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\modelo\test_export.py:21` ctx:normal | `aeat.adapters.persistence.storage.runtime`
- `src\aeat\application\modelo\test_export.py:22` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\modelo\test_iva_wallet_engine_integration.py:13` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\modelo\test_reconcile.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\modelo\test_source_mesh_calculation.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\setup\test_atomic_create_rollback.py:32` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\setup\test_atomic_create_rollback.py:33` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\setup\test_atomic_create_rollback.py:34` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\setup\test_atomic_create_roundtrip.py:26` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\setup\test_service_provisions_bucket.py:22` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\setup\test_service_provisions_bucket.py:23` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\setup\test_service_provisions_bucket.py:24` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\test_apex_workflow_verification.py:9` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\test_config_parity.py:27` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\test_config_reset.py:18` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\test_diagnostics.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\test_diagnostics.py:17` ctx:normal | `aeat.adapters.persistence.storage.master_key._active_session`
- `src\aeat\application\test_diagnostics.py:18` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\test_diagnostics.py:19` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\test_diagnostics.py:20` ctx:normal | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\test_diagnostics.py:185` ctx:local_scope | `aeat.adapters.outbound.aeat.browser._site_health`
- `src\aeat\application\test_repair_integrity.py:20` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\test_repair_integrity.py:25` ctx:normal | `aeat.adapters.persistence.storage.master_key._active_session`
- `src\aeat\application\test_repair_integrity.py:26` ctx:normal | `aeat.adapters.persistence.storage.runtime_repository`
- `src\aeat\application\test_repair_integrity.py:27` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\test_repair_integrity.py:28` ctx:normal | `aeat.adapters.persistence.storage.sql.secure_objects`
- `src\aeat\application\test_state_projection.py:30` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\test_state_projection.py:31` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\test_state_projection.py:36` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\test_state_projection.py:37` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\test_survivor_envelope_enrollment.py:60` ctx:local_scope | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\user_profile\test_aggregate.py:18` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\user_profile\test_aggregate.py:215` ctx:local_scope | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\user_profile\test_census_sync.py:15` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\test_corporate_tax_facts_roundtrip.py:42` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\test_irpf_special_regime_persistence_roundtrip.py:36` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\test_lifecycle.py:10` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\test_marriage_date_persistence_roundtrip.py:24` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\test_orchestration_pointer.py:19` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\test_profile_repository.py:27` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\user_profile\test_profile_repository.py:28` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\user_profile\test_profile_repository.py:29` ctx:normal | `aeat.adapters.persistence.storage.master_key._kdf_params`
- `src\aeat\application\user_profile\test_profile_repository.py:430` ctx:local_scope | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\user_profile\test_profile_repository.py:431` ctx:local_scope | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\user_profile\test_profile_repository.py:452` ctx:local_scope | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\user_profile\test_repository.py:10` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\test_repository.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\test_repository.py:16` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\test_repository.py:19` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\user_profile\test_repository_anti_tautology.py:28` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\test_repository_roundtrip.py:34` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\application\user_profile\test_taxpayer_axes_persistence_roundtrip.py:30` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\verification\test_verify.py:11` ctx:normal | `aeat.adapters.inbound.declaracion`
- `src\aeat\application\verification\test_verify.py:16` ctx:normal | `aeat.adapters.inbound.pdf._shared`
- `src\aeat\application\verification\test_verify_helpers.py:42` ctx:normal | `aeat.adapters.inbound.declaracion._schema`
- `src\aeat\application\verification\test_verify_helpers.py:46` ctx:normal | `aeat.adapters.inbound.pdf._shared`
- `src\aeat\application\wizard\test_commands.py:18` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\wizard\test_create_pointer_atomicity.py:27` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\wizard\test_status.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\application\workflow\test_engine.py:33` ctx:normal | `aeat.adapters.outbound.aeat.auth`
- `src\aeat\application\workflow\test_engine.py:34` ctx:normal | `aeat.adapters.outbound.aeat.browser._site_health`
- `src\aeat\application\workflow\test_engine.py:35` ctx:normal | `aeat.adapters.outbound.aeat.browser._site_health_parsers`
- `src\aeat\application\workflow\test_engine.py:36` ctx:normal | `aeat.adapters.outbound.aeat.export`
- `src\aeat\application\workflow\test_engine.py:40` ctx:normal | `aeat.adapters.outbound.aeat.sede`
- `src\aeat\application\workflow\test_models.py:17` ctx:normal | `aeat.adapters.outbound.aeat.browser._site_health`
- `src\aeat\application\workflow\test_persistence.py:132` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\workflow\test_profile_health.py:9` ctx:normal | `aeat.adapters.persistence.storage.bucket._layout`
- `src\aeat\application\workflow\test_profile_health.py:10` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest`
- `src\aeat\application\workflow\test_profile_health.py:11` ctx:normal | `aeat.adapters.persistence.storage.bucket._manifest_io`
- `src\aeat\application\workflow\test_run_persistence_roundtrip.py:123` ctx:local_scope | `aeat.adapters.persistence.storage`
- `src\aeat\application\workflow\test_runtime_defaults.py:9` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\application\workflow\test_runtime_defaults.py:10` ctx:normal | `aeat.adapters.persistence.storage.sql`
- `src\aeat\application\workflow\test_transaction_catalogue_resolution.py:12` ctx:normal | `aeat.adapters.persistence.storage.sql`

### 4.2 `adapters->application` (35 edges)

- `src\aeat\adapters\outbound\aeat\auth\test_authenticator.py:25` ctx:normal | `aeat.application.auth`
- `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py:27` ctx:normal | `aeat.application.user_profile._orchestration`
- `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py:28` ctx:normal | `aeat.application.user_profile._testing`
- `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py:29` ctx:normal | `aeat.application.workflow._persistence`
- `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py:907` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\auth\test_clave_movil_live.py:73` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\auth\test_providers.py:7` ctx:normal | `aeat.application.auth`
- `src\aeat\adapters\outbound\aeat\export\_formats\test_fichero_boe_roundtrip.py:406` ctx:local_scope | `aeat.application.filing`
- `src\aeat\adapters\outbound\aeat\export\_formats\test_fichero_boe_roundtrip.py:587` ctx:local_scope | `aeat.application.filing`
- `src\aeat\adapters\outbound\aeat\export\test_engine.py:17` ctx:normal | `aeat.application.auth`
- `src\aeat\adapters\outbound\aeat\export\test_preflight.py:11` ctx:normal | `aeat.application.auth`
- `src\aeat\adapters\outbound\aeat\sede\test_declarations.py:28` ctx:normal | `aeat.application.filing`
- `src\aeat\adapters\outbound\aeat\sede\test_declarations_live.py:36` ctx:local_scope | `aeat.application.auth`
- `src\aeat\adapters\outbound\aeat\sede\test_groi_check_live.py:26` ctx:normal | `aeat.application.workflow._models`
- `src\aeat\adapters\outbound\aeat\sede\test_iva_compensation_wallet_live.py:23` ctx:normal | `aeat.application.auth`
- `src\aeat\adapters\outbound\google\test_apply_adapter_helpers.py:25` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\adapters\outbound\google\test_calc_sheets_row_set_headers.py:14` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\adapters\outbound\google\test_compute_from_pull.py:46` ctx:local_scope | `aeat.application.storage.calc_sheets._engine`
- `src\aeat\adapters\outbound\google\test_grid_resize.py:19` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\adapters\outbound\google\test_pull_adapter_helpers.py:23` ctx:normal | `aeat.application.storage.calc_sheets._engine`
- `src\aeat\adapters\outbound\google\test_verify_pull_coverage.py:17` ctx:normal | `aeat.application.storage.calc_sheets._records`
- `src\aeat\adapters\outbound\google\test_worksheet_export_pull_roundtrip.py:25` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\adapters\outbound\google\test_worksheet_export_pull_roundtrip.py:30` ctx:normal | `aeat.application.storage.calc_sheets._engine`
- `src\aeat\adapters\outbound\google\test_worksheet_export_pull_roundtrip.py:31` ctx:normal | `aeat.application.storage.calc_sheets._records`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:41` ctx:normal | `aeat.application.auth._diagnostics`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:42` ctx:normal | `aeat.application.calculations._iva_compensation_history`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:46` ctx:normal | `aeat.application.calculations._observations_repository`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:47` ctx:normal | `aeat.application.diagnostics`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:48` ctx:normal | `aeat.application.filing`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:49` ctx:normal | `aeat.application.filing._history_repository`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:50` ctx:normal | `aeat.application.live._borrador_100`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:51` ctx:normal | `aeat.application.live._snapshot_base`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:52` ctx:normal | `aeat.application.repair_integrity`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:57` ctx:normal | `aeat.application.workflow`
- `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py:58` ctx:normal | `aeat.application.workflow._persistence`

### 4.3 `domain->adapters` (30 edges)

- `src\aeat\domain\attachments\test_repository.py:12` ctx:normal | `aeat.adapters.persistence.storage.attachment`
- `src\aeat\domain\buckets\test_event_history_roundtrip.py:133` ctx:local_scope | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\domain\buckets\test_event_history_roundtrip.py:134` ctx:local_scope | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\domain\calculations\registry\test_renta_web_open_oracle.py:90` ctx:local_scope | `aeat.adapters.outbound.aeat.sede._renta_web_open`
- `src\aeat\domain\filing\test_amendment_roundtrip.py:171` ctx:local_scope | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\domain\filing\test_amendment_roundtrip.py:172` ctx:local_scope | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\domain\filing\test_roundtrip_anti_tautology.py:34` ctx:normal | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\domain\filing\test_roundtrip_anti_tautology.py:35` ctx:normal | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\domain\fincas\test_aggregates.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\fincas\test_aggregates.py:16` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\domain\fincas\test_repository.py:13` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\fincas\test_repository.py:17` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\domain\fincas\test_roundtrip_anti_tautology.py:22` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\fincas\test_roundtrip_anti_tautology.py:25` ctx:normal | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\domain\fincas\test_roundtrip_anti_tautology.py:26` ctx:normal | `aeat.adapters.persistence.storage.sql.engine`
- `src\aeat\domain\invoices\test_secure_storage_roundtrip.py:121` ctx:local_scope | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\domain\invoices\test_secure_storage_roundtrip.py:122` ctx:local_scope | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\domain\justificante\test_repository.py:14` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\justificante\test_repository.py:18` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\modelos\test_calculation_repository_roundtrip.py:31` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\test_filing_record_repository_roundtrip.py:25` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\test_secure_storage_roundtrip.py:23` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\modelos\test_verification_report_roundtrip.py:19` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\submission\test_repository.py:11` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\submission\test_repository.py:15` ctx:normal | `aeat.adapters.persistence.storage.errors`
- `src\aeat\domain\submission\test_secure_storage_roundtrip.py:122` ctx:local_scope | `aeat.adapters.persistence.storage.sql._orm`
- `src\aeat\domain\submission\test_secure_storage_roundtrip.py:123` ctx:local_scope | `aeat.adapters.persistence.storage.sql.session`
- `src\aeat\domain\transactions\test_repository_roundtrip.py:23` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\usage_ratios\test_service.py:18` ctx:normal | `aeat.adapters.persistence.storage`
- `src\aeat\domain\usage_ratios\test_service.py:19` ctx:normal | `aeat.adapters.persistence.storage.errors`

### 4.4 `core->domain` (11 edges)

- `src\aeat\core\i18n\test_output_language.py:45` ctx:local_scope | `aeat.domain.user_profile`
- `src\aeat\core\resources\_repos\test_manuals.py:58` ctx:local_scope | `aeat.domain.manuals.errors`
- `src\aeat\core\resources\_repos\test_normatives.py:18` ctx:normal | `aeat.domain.normatives.errors`
- `src\aeat\core\resources\_repos\test_singletons.py:20` ctx:local_scope | `aeat.domain.auth.apoderamientos._catalogue`
- `src\aeat\core\resources\_repos\test_singletons.py:41` ctx:local_scope | `aeat.domain.user_profile._schema`
- `src\aeat\core\test_external_constants.py:336` ctx:local_scope | `aeat.domain.portals._categories`
- `src\aeat\core\test_external_constants.py:549` ctx:local_scope | `aeat.domain.currency._service`
- `src\aeat\core\test_logging.py:303` ctx:local_scope | `aeat.domain.calculations.registry._record_design`
- `src\aeat\core\test_profile.py:65` ctx:local_scope | `aeat.domain.deadlines._profiles`
- `src\aeat\core\test_profile.py:166` ctx:local_scope | `aeat.domain.deadlines._models`
- `src\aeat\core\test_profile.py:184` ctx:local_scope | `aeat.domain.deadlines._models`

### 4.5 `core->application` (11 edges)

- `src\aeat\core\i18n\test_output_language.py:10` ctx:normal | `aeat.application.user_profile._orchestration`
- `src\aeat\core\i18n\test_output_language.py:42` ctx:local_scope | `aeat.application.user_profile._orchestration`
- `src\aeat\core\i18n\test_output_language.py:43` ctx:local_scope | `aeat.application.user_profile._testing`
- `src\aeat\core\i18n\test_output_language.py:44` ctx:local_scope | `aeat.application.workflow._persistence`
- `src\aeat\core\i18n\test_output_language.py:58` ctx:local_scope | `aeat.application.workflow._persistence`
- `src\aeat\core\test_external_constants.py:527` ctx:local_scope | `aeat.application.ledger._models`
- `src\aeat\core\test_external_constants.py:532` ctx:local_scope | `aeat.application.ledger._models`
- `src\aeat\core\test_external_constants.py:561` ctx:local_scope | `aeat.application.aggregation._currency_predicates`
- `src\aeat\core\test_profile.py:49` ctx:local_scope | `aeat.application.wizard._catalogue`
- `src\aeat\core\test_profile_catalogue.py:43` ctx:local_scope | `aeat.application.wizard._catalogue`
- `src\aeat\core\test_profile_catalogue.py:55` ctx:local_scope | `aeat.application.wizard._catalogue`

### 4.6 `domain->application` (5 edges)

- `src\aeat\domain\calculations\registry\test_cross_boundary_roundtrip.py:439` ctx:local_scope | `aeat.application.workflow._models`
- `src\aeat\domain\calculations\registry\test_detail_record_modelo_coverage.py:18` ctx:normal | `aeat.application.storage.calc_sheets`
- `src\aeat\domain\calculations\registry\test_referential_integrity.py:792` ctx:local_scope | `aeat.application.diagnostics`
- `src\aeat\domain\invoices\test_reconciliation.py:12` ctx:normal | `aeat.application.invoices`
- `src\aeat\domain\modelos\test_work_unit.py:25` ctx:normal | `aeat.application.modelo`

### 4.7 `domain->entrypoints` (5 edges)

- `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:219` ctx:local_scope | `aeat.entrypoints.cli._modelo`
- `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:226` ctx:local_scope | `aeat.entrypoints.cli._modelo`
- `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:233` ctx:local_scope | `aeat.entrypoints.cli._modelo`
- `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:239` ctx:local_scope | `aeat.entrypoints.cli._modelo`
- `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:245` ctx:local_scope | `aeat.entrypoints.cli._modelo`

### 4.8 `core->adapters` (4 edges)

- `src\aeat\core\i18n\test_output_language.py:27` ctx:local_scope | `aeat.adapters.persistence.storage.sql`
- `src\aeat\core\test_external_constants.py:585` ctx:local_scope | `aeat.adapters.persistence.storage.blob_store._blob_store`
- `src\aeat\core\test_logging.py:302` ctx:local_scope | `aeat.adapters.inbound.pdf._pdfplumber`
- `src\aeat\core\test_logging.py:313` ctx:local_scope | `aeat.adapters.inbound.pdf._pdfplumber`

### 4.9 `application->entrypoints` (1 edges)

- `src\aeat\application\aggregation\test_renta_ledger.py:35` ctx:normal | `aeat.entrypoints.cli._common`

## 5. TYPE_CHECKING-Guarded Edges (117 total, 18 violations)

| File:Line | Importer Layer | Imported Layer | Imported Module | Violation |
|---|---|---|---|---|
| `src\aeat\adapters\outbound\aeat\auth\_certificate_backends\_base.py:15` | adapters | adapters | `aeat.adapters.outbound.aeat.auth.certificate` | no |
| `src\aeat\adapters\outbound\aeat\auth\_certificate_backends\_httpx_fallback.py:22` | adapters | adapters | `aeat.adapters.outbound.aeat.auth.certificate` | no |
| `src\aeat\adapters\outbound\aeat\auth\_certificate_backends\_playwright_context.py:28` | adapters | adapters | `aeat.adapters.outbound.aeat.auth.certificate` | no |
| `src\aeat\adapters\outbound\aeat\auth\_providers.py:32` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\auth\certificate.py:43` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._certificate_backends._base` | no |
| `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py:51` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\sede\_auth_state.py:12` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\sede\_censo_live.py:39` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\sede\_declarations.py:100` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\sede\_iva_compensation_wallet.py:41` | adapters | adapters | `aeat.adapters.outbound.aeat._playwright` | no |
| `src\aeat\adapters\outbound\aeat\sede\_iva_compensation_wallet.py:42` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\sede\_notifications.py:48` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\outbound\aeat\sede\_walker.py:46` | adapters | adapters | `aeat.adapters.outbound.aeat.auth._authenticator` | no |
| `src\aeat\adapters\persistence\storage\bucket\_lockfile.py:31` | adapters | adapters | `aeat.adapters.persistence.storage.bucket._layout` | no |
| `src\aeat\adapters\persistence\storage\master_key\_kdf_params.py:30` | adapters | adapters | `aeat.adapters.persistence.storage.bucket._manifest` | no |
| `src\aeat\adapters\persistence\storage\master_key\_master_key.py:63` | adapters | adapters | `aeat.adapters.persistence.storage.master_key._bucket_session` | no |
| `src\aeat\adapters\persistence\storage\runtime.py:31` | adapters | adapters | `aeat.adapters.persistence.storage.sql.secure_objects` | no |
| `src\aeat\adapters\outbound\aeat\auth\_authenticator.py:79` | adapters | core | `aeat.core.config` | no |
| `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:70` | adapters | core | `aeat.core.config` | no |
| `src\aeat\adapters\outbound\aeat\auth\test_authenticator.py:58` | adapters | core | `aeat.core.config` | no |
| `src\aeat\adapters\outbound\aeat\browser\_factory.py:40` | adapters | core | `aeat.core.config` | no |
| `src\aeat\adapters\persistence\storage\blob_store\_materialisation.py:41` | adapters | core | `aeat.core.config` | no |
| `src\aeat\adapters\persistence\storage\master_key\_master_key.py:62` | adapters | core | `aeat.core.config` | no |
| `src\aeat\adapters\outbound\aeat\export\test_preflight.py:23` | adapters | domain | `aeat.domain.submission._preflight` | no |
| `src\aeat\adapters\outbound\aeat\sede\_declarations.py:99` | adapters | domain | `aeat.domain.calculations.registry` | no |
| `src\aeat\adapters\outbound\aeat\auth\__init__.py:79` | adapters | other:config | `core.config` | no |
| `src\aeat\application\auth\_operator.py:30` | application | adapters | `aeat.adapters.outbound.aeat.auth.certificate` | **YES** |
| `src\aeat\application\auth\_sessions.py:30` | application | adapters | `aeat.adapters.outbound.aeat.auth` | **YES** |
| `src\aeat\application\auth\test_ensure_session.py:26` | application | adapters | `aeat.adapters.outbound.aeat.auth` | **YES** |
| `src\aeat\application\diagnostics.py:31` | application | adapters | `aeat.adapters.outbound.aeat.browser` | **YES** |
| `src\aeat\application\diagnostics.py:32` | application | adapters | `aeat.adapters.persistence.storage.sql.secure_objects` | **YES** |
| `src\aeat\application\workflow\_adapters.py:25` | application | adapters | `aeat.adapters.outbound.aeat.auth` | **YES** |
| `src\aeat\application\workflow\_models.py:38` | application | adapters | `aeat.adapters.persistence.storage.sql` | **YES** |
| `src\aeat\application\auth\_actions.py:11` | application | application | `aeat.application.workflow._models` | no |
| `src\aeat\application\auth\_operator.py:31` | application | application | `aeat.application.state_projection` | no |
| `src\aeat\application\auth\_operator.py:32` | application | application | `aeat.application.workflow._models` | no |
| `src\aeat\application\auth\_operator.py:33` | application | application | `aeat.application.workflow._persistence` | no |
| `src\aeat\application\auth\_sessions.py:36` | application | application | `aeat.application.auth` | no |
| `src\aeat\application\calculations\_iva_wallet_reconciliation.py:29` | application | application | `aeat.application.calculations._binding_prefill` | no |
| `src\aeat\application\diagnostics.py:33` | application | application | `aeat.application.wizard._status` | no |
| `src\aeat\application\diagnostics.py:34` | application | application | `aeat.application.workflow._models` | no |
| `src\aeat\application\diagnostics.py:35` | application | application | `aeat.application.workflow._profile_health` | no |
| `src\aeat\application\modelo\_actions.py:135` | application | application | `aeat.application.calculations._iva_wallet_reconciliation` | no |
| `src\aeat\application\modelo\_actions.py:138` | application | application | `aeat.application.calculations._observations_repository` | no |
| `src\aeat\application\user_profile\__init__.py:38` | application | application | `aeat.application._censo_errors` | no |
| `src\aeat\application\user_profile\__init__.py:44` | application | application | `aeat.application._censo_sync` | no |
| `src\aeat\application\user_profile\__init__.py:53` | application | application | `aeat.application._lifecycle` | no |
| `src\aeat\application\user_profile\__init__.py:54` | application | application | `aeat.application._preflight` | no |
| `src\aeat\application\user_profile\__init__.py:55` | application | application | `aeat.application._projections` | no |
| `src\aeat\application\user_profile\__init__.py:56` | application | application | `aeat.application._repository` | no |
| `src\aeat\application\user_profile\__init__.py:64` | application | application | `aeat.application._validation` | no |
| `src\aeat\application\user_profile\_profile_repository.py:71` | application | application | `aeat.application.user_profile._lifecycle` | no |
| `src\aeat\application\wizard\_prompter.py:76` | application | application | `aeat.application.wizard._models` | no |
| `src\aeat\application\workflow\_models.py:41` | application | application | `aeat.application.review._models` | no |
| `src\aeat\application\auth\_acquisition_lock.py:27` | application | core | `aeat.core.config` | no |
| `src\aeat\application\auth\_sessions.py:35` | application | core | `aeat.core.config` | no |
| `src\aeat\application\filing\_import.py:31` | application | domain | `aeat.domain.submission` | no |
| `src\aeat\application\filing\reconciliation\_reconcile.py:41` | application | domain | `aeat.domain.filing` | no |
| `src\aeat\application\filing\reconciliation\_reconcile.py:42` | application | domain | `aeat.domain.justificante` | no |
| `src\aeat\application\ledger\_actions.py:19` | application | domain | `aeat.domain.transactions._classification_rule` | no |
| `src\aeat\application\modelo\_actions.py:134` | application | domain | `aeat.domain.calculations.registry` | no |
| `src\aeat\application\user_profile\_bundle.py:28` | application | domain | `aeat.domain.user_profile` | no |
| `src\aeat\application\workflow\_models.py:39` | application | domain | `aeat.domain.transactions` | no |
| `src\aeat\application\workflow\_models.py:40` | application | domain | `aeat.domain.user_profile` | no |
| `src\aeat\application\auth\__init__.py:18` | application | other:config | `core.config` | no |
| `src\aeat\application\auth\__init__.py:12` | application | other:outbound | `adapters.outbound.aeat.auth` | no |
| `src\aeat\application\overview\__init__.py:107` | application | other:state_projection | `aeat.state_projection` | no |
| `src\aeat\application\overview\__init__.py:108` | application | other:workflow | `aeat.workflow` | no |
| `src\aeat\core\resources\_repos\topics.py:10` | core | application | `aeat.application.topics` | **YES** |
| `src\aeat\core\config.py:31` | core | core | `aeat.core.external_constants` | no |
| `src\aeat\core\errors\registry\__init__.py:14` | core | core | `aeat.core.errors._registry` | no |
| `src\aeat\core\logging.py:28` | core | core | `aeat.core.observability._context` | no |
| `src\aeat\core\observability\_redaction_rules.py:16` | core | core | `aeat.core.classification` | no |
| `src\aeat\core\resources\_repos\manuals.py:23` | core | core | `aeat.core.config` | no |
| `src\aeat\core\resources\_repos\normatives.py:11` | core | core | `aeat.core.config` | no |
| `src\aeat\core\resources\_repos\category_profiles.py:11` | core | domain | `aeat.domain.categories` | **YES** |
| `src\aeat\core\resources\_repos\iva_rate_tables.py:11` | core | domain | `aeat.domain.iva` | **YES** |
| `src\aeat\core\resources\_repos\legal_parameters.py:11` | core | domain | `aeat.domain.calculations.registry` | **YES** |
| `src\aeat\core\resources\_repos\manuals.py:24` | core | domain | `aeat.domain.manuals` | **YES** |
| `src\aeat\core\resources\_repos\modelos.py:20` | core | domain | `aeat.domain.calculations.registry` | **YES** |
| `src\aeat\core\resources\_repos\modelos.py:21` | core | domain | `aeat.domain.calculations.registry._schema` | **YES** |
| `src\aeat\core\resources\_repos\normatives.py:12` | core | domain | `aeat.domain.normatives` | **YES** |
| `src\aeat\core\resources\_repos\normatives.py:13` | core | domain | `aeat.domain.normatives._schema` | **YES** |
| `src\aeat\core\access_gate\__init__.py:37` | core | other:config | `aeat.config` | no |
| `src\aeat\domain\fincas\_repository.py:33` | domain | adapters | `aeat.adapters.persistence.storage.sql` | **YES** |
| `src\aeat\domain\invoices\_repository.py:19` | domain | adapters | `aeat.adapters.persistence.storage.sql` | **YES** |
| `src\aeat\domain\calculations\registry\_live_parity.py:48` | domain | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\domain\calculations\registry\_m232_row_bindings.py:24` | domain | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\domain\calculations\registry\_validate.py:33` | domain | domain | `aeat.domain.user_profile._schema` | no |
| `src\aeat\domain\calculations\registry\_validate_cross_domain_snapshot.py:8` | domain | domain | `aeat.domain.calculations.registry._snapshot` | no |
| `src\aeat\domain\calculations\registry\_validate_reference_checker.py:8` | domain | domain | `aeat.domain.calculations.registry._snapshot` | no |
| `src\aeat\domain\calculations\registry\_validate_reference_sections.py:10` | domain | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\domain\calculations\registry\_validate_references.py:32` | domain | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\domain\calculations\registry\_validate_references.py:33` | domain | domain | `aeat.domain.calculations.registry._snapshot` | no |
| `src\aeat\domain\invoices\_models.py:35` | domain | domain | `aeat.domain.iva._invoice_classification` | no |
| `src\aeat\domain\iva\_invoice_classification.py:60` | domain | domain | `aeat.domain.calculations.registry` | no |
| `src\aeat\domain\portals\__init__.py:32` | domain | domain | `aeat.domain._metadata` | no |
| `src\aeat\domain\portals\__init__.py:33` | domain | domain | `aeat.domain._registry` | no |
| `src\aeat\domain\profile\__init__.py:50` | domain | domain | `aeat.domain._keys` | no |
| `src\aeat\domain\transactions\__init__.py:80` | domain | domain | `aeat.domain._repository` | no |
| `src\aeat\domain\user_profile\_registry_contract.py:16` | domain | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\entrypoints\cli\_config\_google.py:37` | entrypoints | adapters | `aeat.adapters.outbound.google._calc_sheets_pull` | no |
| `src\aeat\entrypoints\cli\_app_live.py:27` | entrypoints | application | `aeat.application.auth` | no |
| `src\aeat\entrypoints\cli\_common.py:24` | entrypoints | application | `aeat.application.auth` | no |
| `src\aeat\entrypoints\cli\_common.py:25` | entrypoints | application | `aeat.application.workflow` | no |
| `src\aeat\entrypoints\cli\_modelo.py:79` | entrypoints | application | `aeat.application.modelo._reconcile` | no |
| `src\aeat\entrypoints\cli\_common.py:26` | entrypoints | domain | `aeat.domain.calculations.registry` | no |
| `src\aeat\entrypoints\cli\_common.py:27` | entrypoints | domain | `aeat.domain.deadlines` | no |
| `src\aeat\entrypoints\cli\_common.py:28` | entrypoints | domain | `aeat.domain.filing` | no |
| `src\aeat\entrypoints\cli\_common.py:29` | entrypoints | domain | `aeat.domain.invoices` | no |
| `src\aeat\entrypoints\cli\_common.py:30` | entrypoints | domain | `aeat.domain.profile` | no |
| `src\aeat\entrypoints\cli\_common.py:31` | entrypoints | domain | `aeat.domain.transactions` | no |
| `src\aeat\entrypoints\cli\_config\_google.py:38` | entrypoints | domain | `aeat.domain.calculations.registry._formula_runtime` | no |
| `src\aeat\entrypoints\cli\_config\_google.py:41` | entrypoints | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\entrypoints\cli\_modelo.py:80` | entrypoints | domain | `aeat.domain.calculations.registry._schema` | no |
| `src\aeat\entrypoints\cli\_modelo.py:81` | entrypoints | entrypoints | `aeat.entrypoints.cli._modelo_payloads` | no |
| `src\aeat\entrypoints\cli\_config\__init__.py:53` | entrypoints | other:buckets | `domain.buckets` | no |

## 6. Local-Scope Import Edges (1,696 total, 175 violations)

Only the 175 illegal local-scope imports. These evade top-level import analysis and were the primary reason the first audit missed violations.

| File:Line | Importer | Imported | Layer Pair |
|---|---|---|---|
| `src\aeat\adapters\outbound\aeat\auth\_authenticator.py:1146` | `aeat.adapters.outbound.aeat.auth._authenticator` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:746` | `aeat.adapters.outbound.aeat.auth._clave_movil` | `aeat.application.user_profile._orchestration` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:747` | `aeat.adapters.outbound.aeat.auth._clave_movil` | `aeat.application.user_profile._projections` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:748` | `aeat.adapters.outbound.aeat.auth._clave_movil` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:749` | `aeat.adapters.outbound.aeat.auth._clave_movil` | `aeat.application.workflow._profile_bucket_scan` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py:860` | `aeat.adapters.outbound.aeat.auth._clave_movil` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py:907` | `aeat.adapters.outbound.aeat.auth.test_clave_movil` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\auth\test_clave_movil_live.py:73` | `aeat.adapters.outbound.aeat.auth.test_clave_movil_live` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\browser\_factory.py:112` | `aeat.adapters.outbound.aeat.browser._factory` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\export\_formats\test_fichero_boe_roundtrip.py:406` | `aeat.adapters.outbound.aeat.export._formats.test_fichero_boe_roundtrip` | `aeat.application.filing` | adapters->application |
| `src\aeat\adapters\outbound\aeat\export\_formats\test_fichero_boe_roundtrip.py:587` | `aeat.adapters.outbound.aeat.export._formats.test_fichero_boe_roundtrip` | `aeat.application.filing` | adapters->application |
| `src\aeat\adapters\outbound\aeat\sede\_declarations.py:358` | `aeat.adapters.outbound.aeat.sede._declarations` | `aeat.application.workflow._models` | adapters->application |
| `src\aeat\adapters\outbound\aeat\sede\test_declarations_live.py:36` | `aeat.adapters.outbound.aeat.sede.test_declarations_live` | `aeat.application.auth` | adapters->application |
| `src\aeat\adapters\outbound\google\_oauth_flow.py:75` | `aeat.adapters.outbound.google._oauth_flow` | `aeat.application.workflow._profile_bucket_scan` | adapters->application |
| `src\aeat\adapters\outbound\google\test_compute_from_pull.py:46` | `aeat.adapters.outbound.google.test_compute_from_pull` | `aeat.application.storage.calc_sheets._engine` | adapters->application |
| `src\aeat\application\auth\_operator.py:229` | `aeat.application.auth._operator` | `aeat.adapters.persistence.storage.runtime_repository` | application->adapters |
| `src\aeat\application\auth\_operator.py:670` | `aeat.application.auth._operator` | `aeat.adapters.outbound.aeat.auth._clave_movil` | application->adapters |
| `src\aeat\application\auth\_operator.py:807` | `aeat.application.auth._operator` | `aeat.adapters.outbound.aeat.auth.certificate` | application->adapters |
| `src\aeat\application\auth\_operator.py:905` | `aeat.application.auth._operator` | `aeat.adapters.outbound.aeat.auth.certificate` | application->adapters |
| `src\aeat\application\auth\_operator.py:932` | `aeat.application.auth._operator` | `aeat.adapters.outbound.aeat.auth._clave_movil` | application->adapters |
| `src\aeat\application\auth\_sessions.py:211` | `aeat.application.auth._sessions` | `aeat.adapters.outbound.aeat.browser` | application->adapters |
| `src\aeat\application\auth\_sessions.py:329` | `aeat.application.auth._sessions` | `aeat.adapters.outbound.aeat.auth` | application->adapters |
| `src\aeat\application\auth\_sessions.py:466` | `aeat.application.auth._sessions` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\auth\_sessions.py:546` | `aeat.application.auth._sessions` | `aeat.adapters.outbound.aeat.browser` | application->adapters |
| `src\aeat\application\auth\test_ensure_session.py:226` | `aeat.application.auth.test_ensure_session` | `aeat.adapters.outbound.aeat.auth` | application->adapters |
| `src\aeat\application\calculations\test_observations_repository.py:235` | `aeat.application.calculations.test_observations_repository` | `aeat.adapters.persistence.storage.envelope._envelope` | application->adapters |
| `src\aeat\application\calculations\test_observations_repository_roundtrip.py:206` | `aeat.application.calculations.test_observations_repository_roundtrip` | `aeat.adapters.persistence.storage.sql._orm` | application->adapters |
| `src\aeat\application\calculations\test_observations_repository_roundtrip.py:207` | `aeat.application.calculations.test_observations_repository_roundtrip` | `aeat.adapters.persistence.storage.sql.session` | application->adapters |
| `src\aeat\application\config_reset.py:148` | `aeat.application.config_reset` | `aeat.adapters.persistence.storage.sql` | application->adapters |
| `src\aeat\application\diagnostics.py:199` | `aeat.application.diagnostics` | `aeat.adapters.persistence.storage.sql.secure_objects` | application->adapters |
| `src\aeat\application\diagnostics.py:298` | `aeat.application.diagnostics` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\diagnostics.py:401` | `aeat.application.diagnostics` | `aeat.adapters.outbound.aeat.browser` | application->adapters |
| `src\aeat\application\diagnostics.py:412` | `aeat.application.diagnostics` | `aeat.adapters.outbound.aeat.browser` | application->adapters |
| `src\aeat\application\diagnostics.py:434` | `aeat.application.diagnostics` | `aeat.adapters.outbound.aeat.browser` | application->adapters |
| `src\aeat\application\diagnostics.py:435` | `aeat.application.diagnostics` | `aeat.adapters.outbound.aeat.browser._site_health` | application->adapters |
| `src\aeat\application\diagnostics.py:547` | `aeat.application.diagnostics` | `aeat.adapters.persistence.storage.runtime_repository` | application->adapters |
| `src\aeat\application\diagnostics.py:550` | `aeat.application.diagnostics` | `aeat.adapters.persistence.storage.sql.secure_objects` | application->adapters |
| `src\aeat\application\diagnostics.py:893` | `aeat.application.diagnostics` | `aeat.adapters.persistence.storage.master_key._active_session` | application->adapters |
| `src\aeat\application\diagnostics.py:1036` | `aeat.application.diagnostics` | `aeat.adapters.persistence.storage.runtime_repository` | application->adapters |
| `src\aeat\application\filing\test_complementaria_repository.py:141` | `aeat.application.filing.test_complementaria_repository` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\filing\test_history_repository.py:108` | `aeat.application.filing.test_history_repository` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\filing\test_repository.py:143` | `aeat.application.filing.test_repository` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\live\test_borrador_100_roundtrip.py:174` | `aeat.application.live.test_borrador_100_roundtrip` | `aeat.adapters.persistence.storage.sql._orm` | application->adapters |
| `src\aeat\application\live\test_borrador_100_roundtrip.py:175` | `aeat.application.live.test_borrador_100_roundtrip` | `aeat.adapters.persistence.storage.sql.session` | application->adapters |
| `src\aeat\application\live\test_census_snapshot.py:446` | `aeat.application.live.test_census_snapshot` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\modelo\_reconcile.py:162` | `aeat.application.modelo._reconcile` | `aeat.adapters.inbound.justificante` | application->adapters |
| `src\aeat\application\repair_integrity.py:218` | `aeat.application.repair_integrity` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\repair_integrity.py:298` | `aeat.application.repair_integrity` | `aeat.adapters.persistence.storage.runtime_repository` | application->adapters |
| `src\aeat\application\repair_integrity.py:407` | `aeat.application.repair_integrity` | `aeat.adapters.persistence.storage.runtime_repository` | application->adapters |
| `src\aeat\application\storage\calc_sheets\_parity_harness.py:325` | `aeat.application.storage.calc_sheets._parity_harness` | `aeat.adapters.outbound.google._calc_sheets_apply` | application->adapters |
| `src\aeat\application\test_config_parity.py:27` | `aeat.application.test_config_parity` | `aeat.adapters.persistence.storage.sql` | application->adapters |
| `src\aeat\application\test_config_reset.py:18` | `aeat.application.test_config_reset` | `aeat.adapters.persistence.storage.sql` | application->adapters |
| `src\aeat\application\test_diagnostics.py:185` | `aeat.application.test_diagnostics` | `aeat.adapters.outbound.aeat.browser._site_health` | application->adapters |
| `src\aeat\application\test_survivor_envelope_enrollment.py:60` | `aeat.application.test_survivor_envelope_enrollment` | `aeat.adapters.persistence.storage.errors` | application->adapters |
| `src\aeat\application\user_profile\_censo_sync.py:202` | `aeat.application.user_profile._censo_sync` | `aeat.adapters.outbound.aeat.sede._censo_live` | application->adapters |
| `src\aeat\application\user_profile\_orchestration.py:120` | `aeat.application.user_profile._orchestration` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\user_profile\_orchestration.py:121` | `aeat.application.user_profile._orchestration` | `aeat.adapters.persistence.storage.errors` | application->adapters |
| `src\aeat\application\user_profile\_orchestration.py:155` | `aeat.application.user_profile._orchestration` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\user_profile\_profile_repository.py:318` | `aeat.application.user_profile._profile_repository` | `aeat.adapters.persistence.storage.sql.engine` | application->adapters |
| `src\aeat\application\user_profile\_repository.py:61` | `aeat.application.user_profile._repository` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\user_profile\test_aggregate.py:215` | `aeat.application.user_profile.test_aggregate` | `aeat.adapters.persistence.storage.bucket._manifest` | application->adapters |
| `src\aeat\application\user_profile\test_profile_repository.py:430` | `aeat.application.user_profile.test_profile_repository` | `aeat.adapters.persistence.storage.bucket._manifest` | application->adapters |
| `src\aeat\application\user_profile\test_profile_repository.py:431` | `aeat.application.user_profile.test_profile_repository` | `aeat.adapters.persistence.storage.bucket._manifest_io` | application->adapters |
| `src\aeat\application\user_profile\test_profile_repository.py:452` | `aeat.application.user_profile.test_profile_repository` | `aeat.adapters.persistence.storage.bucket._manifest` | application->adapters |
| `src\aeat\application\workflow\_adapters.py:139` | `aeat.application.workflow._adapters` | `aeat.adapters.outbound.aeat.sede` | application->adapters |
| `src\aeat\application\workflow\_adapters.py:148` | `aeat.application.workflow._adapters` | `aeat.adapters.outbound.aeat.sede` | application->adapters |
| `src\aeat\application\workflow\_persistence.py:136` | `aeat.application.workflow._persistence` | `aeat.adapters.persistence.storage.sql.secure_objects` | application->adapters |
| `src\aeat\application\workflow\_profile_health.py:297` | `aeat.application.workflow._profile_health` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\workflow\test_persistence.py:132` | `aeat.application.workflow.test_persistence` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\application\workflow\test_run_persistence_roundtrip.py:123` | `aeat.application.workflow.test_run_persistence_roundtrip` | `aeat.adapters.persistence.storage` | application->adapters |
| `src\aeat\core\i18n\test_output_language.py:27` | `aeat.core.i18n.test_output_language` | `aeat.adapters.persistence.storage.sql` | core->adapters |
| `src\aeat\core\i18n\test_output_language.py:42` | `aeat.core.i18n.test_output_language` | `aeat.application.user_profile._orchestration` | core->application |
| `src\aeat\core\i18n\test_output_language.py:43` | `aeat.core.i18n.test_output_language` | `aeat.application.user_profile._testing` | core->application |
| `src\aeat\core\i18n\test_output_language.py:44` | `aeat.core.i18n.test_output_language` | `aeat.application.workflow._persistence` | core->application |
| `src\aeat\core\i18n\test_output_language.py:45` | `aeat.core.i18n.test_output_language` | `aeat.domain.user_profile` | core->domain |
| `src\aeat\core\i18n\test_output_language.py:58` | `aeat.core.i18n.test_output_language` | `aeat.application.workflow._persistence` | core->application |
| `src\aeat\core\resources\_repos\apoderamientos.py:15` | `aeat.core.resources._repos.apoderamientos` | `aeat.domain.auth.apoderamientos` | core->domain |
| `src\aeat\core\resources\_repos\category_profiles.py:23` | `aeat.core.resources._repos.category_profiles` | `aeat.domain.categories` | core->domain |
| `src\aeat\core\resources\_repos\holiday_calendars.py:15` | `aeat.core.resources._repos.holiday_calendars` | `aeat.domain.deadlines` | core->domain |
| `src\aeat\core\resources\_repos\iva_catalogues.py:26` | `aeat.core.resources._repos.iva_catalogues` | `aeat.domain.iva._catalogue` | core->domain |
| `src\aeat\core\resources\_repos\iva_rate_tables.py:25` | `aeat.core.resources._repos.iva_rate_tables` | `aeat.domain.iva._rates` | core->domain |
| `src\aeat\core\resources\_repos\legal_parameters.py:24` | `aeat.core.resources._repos.legal_parameters` | `aeat.domain.calculations.registry` | core->domain |
| `src\aeat\core\resources\_repos\manuals.py:67` | `aeat.core.resources._repos.manuals` | `aeat.domain.manuals` | core->domain |
| `src\aeat\core\resources\_repos\manuals.py:85` | `aeat.core.resources._repos.manuals` | `aeat.domain.manuals` | core->domain |
| `src\aeat\core\resources\_repos\manuals.py:98` | `aeat.core.resources._repos.manuals` | `aeat.domain.manuals` | core->domain |
| `src\aeat\core\resources\_repos\manuals.py:110` | `aeat.core.resources._repos.manuals` | `aeat.domain.manuals` | core->domain |
| `src\aeat\core\resources\_repos\modelos.py:43` | `aeat.core.resources._repos.modelos` | `aeat.domain.calculations.registry` | core->domain |
| `src\aeat\core\resources\_repos\modelos.py:61` | `aeat.core.resources._repos.modelos` | `aeat.domain.calculations.registry` | core->domain |
| `src\aeat\core\resources\_repos\normatives.py:36` | `aeat.core.resources._repos.normatives` | `aeat.domain.normatives` | core->domain |
| `src\aeat\core\resources\_repos\normatives.py:46` | `aeat.core.resources._repos.normatives` | `aeat.domain.normatives` | core->domain |
| `src\aeat\core\resources\_repos\normatives.py:52` | `aeat.core.resources._repos.normatives` | `aeat.domain.normatives` | core->domain |
| `src\aeat\core\resources\_repos\recargo_bands.py:15` | `aeat.core.resources._repos.recargo_bands` | `aeat.domain.deadlines` | core->domain |
| `src\aeat\core\resources\_repos\test_manuals.py:58` | `aeat.core.resources._repos.test_manuals` | `aeat.domain.manuals.errors` | core->domain |
| `src\aeat\core\resources\_repos\test_singletons.py:20` | `aeat.core.resources._repos.test_singletons` | `aeat.domain.auth.apoderamientos._catalogue` | core->domain |
| `src\aeat\core\resources\_repos\test_singletons.py:41` | `aeat.core.resources._repos.test_singletons` | `aeat.domain.user_profile._schema` | core->domain |
| `src\aeat\core\resources\_repos\topics.py:20` | `aeat.core.resources._repos.topics` | `aeat.application.topics` | core->application |
| `src\aeat\core\resources\_repos\user_profile.py:15` | `aeat.core.resources._repos.user_profile` | `aeat.domain.user_profile` | core->domain |
| `src\aeat\core\test_external_constants.py:336` | `aeat.core.test_external_constants` | `aeat.domain.portals._categories` | core->domain |
| `src\aeat\core\test_external_constants.py:527` | `aeat.core.test_external_constants` | `aeat.application.ledger._models` | core->application |
| `src\aeat\core\test_external_constants.py:532` | `aeat.core.test_external_constants` | `aeat.application.ledger._models` | core->application |
| `src\aeat\core\test_external_constants.py:549` | `aeat.core.test_external_constants` | `aeat.domain.currency._service` | core->domain |
| `src\aeat\core\test_external_constants.py:561` | `aeat.core.test_external_constants` | `aeat.application.aggregation._currency_predicates` | core->application |
| `src\aeat\core\test_external_constants.py:585` | `aeat.core.test_external_constants` | `aeat.adapters.persistence.storage.blob_store._blob_store` | core->adapters |
| `src\aeat\core\test_logging.py:302` | `aeat.core.test_logging` | `aeat.adapters.inbound.pdf._pdfplumber` | core->adapters |
| `src\aeat\core\test_logging.py:303` | `aeat.core.test_logging` | `aeat.domain.calculations.registry._record_design` | core->domain |
| `src\aeat\core\test_logging.py:313` | `aeat.core.test_logging` | `aeat.adapters.inbound.pdf._pdfplumber` | core->adapters |
| `src\aeat\core\test_profile.py:49` | `aeat.core.test_profile` | `aeat.application.wizard._catalogue` | core->application |
| `src\aeat\core\test_profile.py:65` | `aeat.core.test_profile` | `aeat.domain.deadlines._profiles` | core->domain |
| `src\aeat\core\test_profile.py:166` | `aeat.core.test_profile` | `aeat.domain.deadlines._models` | core->domain |
| `src\aeat\core\test_profile.py:184` | `aeat.core.test_profile` | `aeat.domain.deadlines._models` | core->domain |
| `src\aeat\core\test_profile_catalogue.py:43` | `aeat.core.test_profile_catalogue` | `aeat.application.wizard._catalogue` | core->application |
| `src\aeat\core\test_profile_catalogue.py:55` | `aeat.core.test_profile_catalogue` | `aeat.application.wizard._catalogue` | core->application |
| `src\aeat\domain\buckets\test_event_history_roundtrip.py:133` | `aeat.domain.buckets.test_event_history_roundtrip` | `aeat.adapters.persistence.storage.sql._orm` | domain->adapters |
| `src\aeat\domain\buckets\test_event_history_roundtrip.py:134` | `aeat.domain.buckets.test_event_history_roundtrip` | `aeat.adapters.persistence.storage.sql.session` | domain->adapters |
| `src\aeat\domain\calculations\registry\test_cross_boundary_roundtrip.py:439` | `aeat.domain.calculations.registry.test_cross_boundary_roundtrip` | `aeat.application.workflow._models` | domain->application |
| `src\aeat\domain\calculations\registry\test_referential_integrity.py:792` | `aeat.domain.calculations.registry.test_referential_integrity` | `aeat.application.diagnostics` | domain->application |
| `src\aeat\domain\calculations\registry\test_renta_web_open_oracle.py:90` | `aeat.domain.calculations.registry.test_renta_web_open_oracle` | `aeat.adapters.outbound.aeat.sede._renta_web_open` | domain->adapters |
| `src\aeat\domain\filing\test_amendment_roundtrip.py:171` | `aeat.domain.filing.test_amendment_roundtrip` | `aeat.adapters.persistence.storage.sql._orm` | domain->adapters |
| `src\aeat\domain\filing\test_amendment_roundtrip.py:172` | `aeat.domain.filing.test_amendment_roundtrip` | `aeat.adapters.persistence.storage.sql.session` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:39` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:55` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:66` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:67` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:76` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:85` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:86` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:135` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:136` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:147` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:186` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:193` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:212` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:213` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:222` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:223` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:241` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:242` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:306` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:325` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:337` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:338` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:370` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:371` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:399` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:417` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:418` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:437` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:438` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:455` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:456` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:466` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:498` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:517` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:529` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:530` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:568` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\fincas\_repository.py:569` | `aeat.domain.fincas._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:31` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:91` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:107` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:114` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage.errors` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:132` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:156` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage` | domain->adapters |
| `src\aeat\domain\invoices\_repository.py:157` | `aeat.domain.invoices._repository` | `aeat.adapters.persistence.storage.sql` | domain->adapters |
| `src\aeat\domain\invoices\test_secure_storage_roundtrip.py:121` | `aeat.domain.invoices.test_secure_storage_roundtrip` | `aeat.adapters.persistence.storage.sql._orm` | domain->adapters |
| `src\aeat\domain\invoices\test_secure_storage_roundtrip.py:122` | `aeat.domain.invoices.test_secure_storage_roundtrip` | `aeat.adapters.persistence.storage.sql.session` | domain->adapters |
| `src\aeat\domain\profile\_keys.py:137` | `aeat.domain.profile._keys` | `aeat.application.wizard._compiler` | domain->application |
| `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:219` | `aeat.domain.profile.test_deduccion_maternidad_0611` | `aeat.entrypoints.cli._modelo` | domain->entrypoints |
| `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:226` | `aeat.domain.profile.test_deduccion_maternidad_0611` | `aeat.entrypoints.cli._modelo` | domain->entrypoints |
| `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:233` | `aeat.domain.profile.test_deduccion_maternidad_0611` | `aeat.entrypoints.cli._modelo` | domain->entrypoints |
| `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:239` | `aeat.domain.profile.test_deduccion_maternidad_0611` | `aeat.entrypoints.cli._modelo` | domain->entrypoints |
| `src\aeat\domain\profile\test_deduccion_maternidad_0611.py:245` | `aeat.domain.profile.test_deduccion_maternidad_0611` | `aeat.entrypoints.cli._modelo` | domain->entrypoints |
| `src\aeat\domain\submission\test_secure_storage_roundtrip.py:122` | `aeat.domain.submission.test_secure_storage_roundtrip` | `aeat.adapters.persistence.storage.sql._orm` | domain->adapters |
| `src\aeat\domain\submission\test_secure_storage_roundtrip.py:123` | `aeat.domain.submission.test_secure_storage_roundtrip` | `aeat.adapters.persistence.storage.sql.session` | domain->adapters |
| `src\aeat\domain\transactions\_repository.py:34` | `aeat.domain.transactions._repository` | `aeat.adapters.persistence.storage` | domain->adapters |

## 7. Per-File Violation Count (top 50 by density)

| Violations | File |
|---|---|
| 39 | `src\aeat\domain\fincas\_repository.py` |
| 12 | `src\aeat\application\diagnostics.py` |
| 11 | `src\aeat\adapters\persistence\storage\test_runtime_migrated_repositories.py` |
| 9 | `src\aeat\application\user_profile\_profile_repository.py` |
| 8 | `src\aeat\domain\invoices\_repository.py` |
| 7 | `src\aeat\core\i18n\test_output_language.py` |
| 7 | `src\aeat\application\workflow\_persistence.py` |
| 6 | `src\aeat\application\repair_integrity.py` |
| 6 | `src\aeat\application\test_diagnostics.py` |
| 6 | `src\aeat\core\test_external_constants.py` |
| 6 | `src\aeat\application\auth\_operator.py` |
| 6 | `src\aeat\application\auth\_sessions.py` |
| 6 | `src\aeat\application\user_profile\test_profile_repository.py` |
| 6 | `src\aeat\application\user_profile\_repository.py` |
| 5 | `src\aeat\application\test_repair_integrity.py` |
| 5 | `src\aeat\domain\profile\test_deduccion_maternidad_0611.py` |
| 5 | `src\aeat\core\resources\_repos\manuals.py` |
| 5 | `src\aeat\core\resources\_repos\normatives.py` |
| 5 | `src\aeat\application\live\_borrador_100.py` |
| 5 | `src\aeat\application\live\_censo.py` |
| 5 | `src\aeat\application\user_profile\_orchestration.py` |
| 5 | `src\aeat\application\workflow\test_engine.py` |
| 5 | `src\aeat\application\workflow\_profile_bucket_scan.py` |
| 5 | `src\aeat\application\workflow\_profile_health.py` |
| 5 | `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py` |
| 4 | `src\aeat\application\test_state_projection.py` |
| 4 | `src\aeat\core\test_profile.py` |
| 4 | `src\aeat\domain\buckets\_event_repository.py` |
| 4 | `src\aeat\domain\filing\_repository.py` |
| 4 | `src\aeat\domain\transactions\_repository.py` |
| 4 | `src\aeat\domain\usage_ratios\_service.py` |
| 4 | `src\aeat\core\resources\_repos\modelos.py` |
| 4 | `src\aeat\application\filing\_history_repository.py` |
| 4 | `src\aeat\application\live\test_iva_remote_state_acquisition.py` |
| 4 | `src\aeat\application\live\_snapshot_base.py` |
| 4 | `src\aeat\application\live\_verify.py` |
| 4 | `src\aeat\application\user_profile\test_repository.py` |
| 4 | `src\aeat\adapters\outbound\google\_calc_sheets_pull.py` |
| 4 | `src\aeat\adapters\outbound\aeat\auth\test_clave_movil.py` |
| 3 | `src\aeat\core\test_logging.py` |
| 3 | `src\aeat\domain\filing\_complementaria_repository.py` |
| 3 | `src\aeat\domain\fincas\test_roundtrip_anti_tautology.py` |
| 3 | `src\aeat\domain\justificante\_repository.py` |
| 3 | `src\aeat\domain\modelos\_calculation_repository.py` |
| 3 | `src\aeat\domain\modelos\_filing_repository.py` |
| 3 | `src\aeat\domain\modelos\_repository.py` |
| 3 | `src\aeat\domain\modelos\_verification_repository.py` |
| 3 | `src\aeat\domain\submission\_repository.py` |
| 3 | `src\aeat\application\auth\test_ensure_session.py` |
| 3 | `src\aeat\application\auth\_diagnostics.py` |

## 8. Allowed Registry Import Count

Total imports of `aeat.domain.calculations.registry.*` across all layers: **803**

This is the single explicitly allowed cross-domain target. Imports resolving to `aeat.domain.calculations.registry` or its children from outside `domain/calculations/` are exempt from the cross-domain rule.

## 9. Key Structural Patterns

**Pattern A: domain/_repository.py files import adapters directly.**
`domain/fincas/_repository.py` (39 violations, all local-scope), `domain/invoices/_repository.py` (8), `domain/modelos/_*_repository.py` (3 each), `domain/buckets/_event_repository.py` (4), `domain/filing/_repository.py` (4), `domain/usage_ratios/_service.py` (4), `domain/transactions/_repository.py` (4). These files act as persistence adapters but sit inside domain. The pattern is consistent: domain `_repository.py` and `_service.py` files import `aeat.adapters.persistence.storage.*` directly via local-scope imports to avoid circular startup errors.

**Pattern B: application importing adapters at module top-level.**
143 `application->adapters` edges (largest violation category). Hot files: `application/diagnostics.py` (12), `application/user_profile/_profile_repository.py` (9), `application/workflow/_persistence.py` (7), `application/live/_borrador_100.py` (5), `application/live/_censo.py` (5), `application/workflow/_profile_bucket_scan.py` (5), `application/workflow/_profile_health.py` (5). The storage adapter namespace (`aeat.adapters.persistence.storage`) is imported by at least 30 distinct application modules.

**Pattern C: adapters importing application (bi-directional cycle).**
17 `adapters->application` production edges. `adapters/outbound/aeat/auth/_clave_movil.py` (5 local-scope to `application.workflow.*` and `application.user_profile.*`), `adapters/outbound/aeat/auth/_providers.py` (1 normal to `application.auth`), `adapters/outbound/google/_calc_sheets_pull.py` (4 normal), `adapters/outbound/google/_oauth_flow.py` (2). This creates a hard bi-directional cycle between adapters and application layers.

**Pattern D: core importing domain (25 production edges).**
`core/resources/_repos/` cluster: `manuals.py` (5), `normatives.py` (5), `modelos.py` (4), `category_profiles.py` (2), `iva_rate_tables.py` (2), `legal_parameters.py` (2), `apoderamientos.py` (1), `holiday_calendars.py` (1), `iva_catalogues.py` (1), `recargo_bands.py` (1), `user_profile.py` (1). `core/resources/_repos/topics.py` also imports `application.topics` (2 edges: core->application). All are local-scope or TYPE_CHECKING-guarded, indicating deliberate lazy-load to break circular startup, but illegal under architecture rules.

**Pattern E: local-scope hiding is the dominant concealment mechanism.**
Of 278 production violations: 109 are local-scope (inside function bodies), 17 are TYPE_CHECKING-guarded, 152 are normal top-level. `domain/fincas/_repository.py` has 38 local-scope adapter imports. `application/diagnostics.py` has 9. This explains why the first audit found only 1 production violation: it used grep-based top-level analysis and missed everything inside function bodies.

**Pattern F: iva <-> calculations bidirectional coupling.**
`domain/iva` imports from `domain/calculations` (10 edges); `domain/calculations` imports from `domain/iva` (13 edges). This is a bidirectional cross-subdomain cycle. Similarly `domain/invoices` <-> `domain/iva` (13 + 10 edges). These are the highest-count cross-subdomain pairs after the allowed `domain/calculations/registry` exemption.
