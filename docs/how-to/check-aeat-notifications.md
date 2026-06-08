# Check AEAT notifications and live observations

Use this guide to review and capture read-only live AEAT observations, DEHu notifications, filed declaration history, NIF verifications, and other live tax-authority states. 

All live commands in `aeat` are strictly read-only and local-first: they download and persist snapshots for local review and calculations. None of these commands submit filings, modify AEAT records, or register changes.

## Before you start

You need:
- an [active profile](profile-setup.md#what-the-active-profile-means)
- the taxpayer's fiscal ID (generalized as NIF, CIF, DNI, NIE, or NII) saved in that profile
- AEAT live-read authentication configured; see [Authenticate with AEAT](authenticate-with-aeat.md)

---

## 1. DEHu Notifications (`aeat app live notifications`)

Capture and inspect DEHu notifications.

### Capture a fresh snapshot
To live-fetch notifications and save them under the active profile's bucket:
```bash
aeat app live notifications capture
```
This runs the AEAT authentication preflight and downloads a snapshot containing certificate IDs, concepts, taxpayer names/identifiers, emission dates, read states, and source URLs.

### List and view snapshots
List saved snapshots:
```bash
aeat app live notifications list
```

View a specific snapshot by its ID or unambiguous prefix:
```bash
aeat app live notifications view <snapshot-id>
```

Show the most recent snapshot in the active bucket:
```bash
aeat app live notifications latest
```

---

## 2. AEAT Expedientes (`aeat app live expedientes`)

Walk the AEAT declaration register to query the status and presentation history of tax returns.

### Capture expedientes
To capture the expedientes for a specific modelo and year:
```bash
aeat app live expedientes capture --modelo 100 --year 2026
```

To capture expedientes for a range of years:
```bash
aeat app live expedientes capture-all --from-year 2020 --to-year 2026 --modelo 303
```
*(Omit `--modelo` to capture expedientes for all registered modelos).*

### List and view expedientes
List saved expedientes snapshots:
```bash
aeat app live expedientes list
```

View a specific snapshot's details (individual declarations, status, dates, and justificante links):
```bash
aeat app live expedientes view <snapshot-id>
```

Show the most recent expedientes snapshot:
```bash
aeat app live expedientes latest
```

---

## 3. Filed Declarations (`aeat app live filed`)

Inspect the detailed contents of previously filed declarations from the AEAT.

### List filed returns
List filed declarations without downloading full payloads:
```bash
aeat app live filed list --modelo 303 --from-year 2020 --to-year 2026
```

### Capture filed declaration data
Download and persist detailed observations from a filed return:
```bash
aeat app live filed capture --modelo 303 --year 2026 --period 1T
```

Capture all filed returns across a year range:
```bash
aeat app live filed capture-all --from-year 2020 --to-year 2026
```

Capture the required source declarations needed by a target filing's dependencies:
```bash
aeat app live filed capture-sources --modelo 303 --year 2026 --period 1T
```

---

## 4. NIF and Intra-community VAT Verification (`aeat app live verify`)

Query intra-community NIF-IVA registries and Spanish ROI/VIES (GROI) registrations.

### Live verification checks
Verify an intra-community VAT NIF via AEAT IXVI:
```bash
aeat app live verify nif-iva ESB12345678
```

Verify a Spanish NIF/NIE registration via ROI/VIES (GROI):
```bash
aeat app live verify tgvi 12345678A
```
*(Optional: Use `--expected valid|invalid|unknown` to verify against an expected verdict).*

### Audit log verification
List local verification logs:
```bash
aeat app live verify list --surface tgvi
```

View a specific verification audit entry:
```bash
aeat app live verify view <observation-id>
```

Show the latest verification observation for a NIF:
```bash
aeat app live verify latest --surface nif_iva --nif ESB12345678
```

---

## 5. AEAT Portals Catalogue (`aeat app live portals`)

Inspect the local database of official AEAT portal URLs and their required auth methods.

### List portals
```bash
aeat app live portals list --category sede_modelo --modelo 303
```

### View portal details
```bash
aeat app live portals view <portal-id>
```

---

## 6. Borrador Snapshots (`aeat app live borrador`)

Manage local snapshots of Modelo 100 draft (borrador) filings.

### List and view drafts
List saved drafts:
```bash
aeat app live borrador 100 list --state active
```

View a specific draft's details and casilla binding values:
```bash
aeat app live borrador 100 view <snapshot-id>
```

Show the latest active draft for a filing year:
```bash
aeat app live borrador 100 latest --filing-year 2026
```

---

## 7. IVA Compensation Wallet (`aeat app live iva-wallet`)

Manage the history and remote state of your IVA compensation wallet (saldos a compensar).

### Pull active wallet state
Download and persist the current IVA wallet state:
```bash
aeat app live iva-wallet pull --year 2026 --period 4T
```

### Remote history capture
Capture past Modelo 303 filings to reconstruct the local wallet history:
```bash
aeat app live iva-wallet capture-history --from-year 2020 --to-year 2026
```

Capture past returns and pull the current remote state in a single run:
```bash
aeat app live iva-wallet capture-remote-state --from-year 2020 --to-year 2026 --target-year 2026 --target-period 4T
```

### View local history
List persisted compensation balances and decisions:
```bash
aeat app live iva-wallet history --as-of-year 2026
```

---

## Next steps

- [Plan your filing calendar](filing-calendar.md)
- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Reconcile filing justificantes](reconcile.md)
