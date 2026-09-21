# INCOME-01 CLI baseline evidence

This directory preserves the sanitized synthetic evidence produced by the installed CLI run at source `8c3a40fecffcd98be5684dce4859c186e8a74d31` and authority generation `804b2c4f09b6c7d7292af3f77568f5c9772176dea5a49b2bd90c69615e4cd1fd`.

No credential, encrypted store, runtime log, or private taxpayer payload is retained here. The taxpayer and financial records in the receipts and XML are the versioned synthetic INCOME-01 scenario.

| File | SHA-256 |
| --- | --- |
| `journey-receipt.json` | `c93cc0f65c8e26c514f6ab809d85443d1635659b3591fc4eedac24d366ac89eb` |
| `controls-receipt.json` | `a8b6044807ed8081d57b1bc9a71f75d9d027889d84a814a4b029506fb672a5df` |
| `modelo-100-2025-0A.xml` | `6671b43e3ce297cccfee2e91dd6533f34f33e2c1980e0d1d8e5194c652b180f7` |
| `modelo-100-official-xsd-validation.json` | `323515a1dba93d810957d1f8047a085b28f8f7b9c81c4754c4978d81a31324f6` |

## XSD validation qualification

- Official source: AEAT `Renta2025.xsd`.
- Original byte identity: SHA-256 `df94cc5160e8ad8244e6fc5fb0f257280b4c8c3f70107f0c2acc99d395f678c2`, 812099 bytes.
- Normalization: remove the backslash from each of the 16 literal `\·` regex sequences that XML Schema does not admit, leaving each middle dot as `·`. No other schema bytes change.
- Effective validation-schema identity: SHA-256 `ec8e7c405c7fc8c0f5a9205f178636185eeb86a5014be5f776945375a693141f`, 812083 bytes.
- Result: the retained Modelo 100 XML produced zero validation errors. This is local structural validation; it is neither AEAT submission nor evidence of AEAT acceptance.

The receipts retain their original temporary run paths as historical execution metadata. These copied files are the durable handoff artifacts.
