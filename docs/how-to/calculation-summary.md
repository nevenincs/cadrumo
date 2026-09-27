# Share and verify a calculation summary

This page covers the calculation summary: a PDF of a verified or filed
calculation that an accountant can read, that carries its own data, and that
anyone can check for changes. You write it with one command, hand it on, and
later confirm that a copy still matches what your encrypted store holds.

A summary is a local calculation, not AEAT evidence. The official proof of a
filing is the AEAT receipt (justificante), the filed-declarations lookup, or the
CSV check at the AEAT portal. The summary says so on its first page and in every
footer.

## Before you start

**Requirement:** a calculation that has passed verification or been filed. See
[Verify a filing](verification-reports.md).

Writing a summary needs the optional `pdf` extra. Checking one does not.

```text
pip install "cadrumo[pdf]"
```

Without the extra, the command refuses before it reads your data and names the
extra to install.

## Write a summary

Address the work unit the way `aeat app modelo work review` does, and choose the
`pdf` document format:

```text
aeat app modelo work report WORK_UNIT_ID --document-format pdf --output modelo-130-2026-1T.pdf
```

The summary is written in the language the command runs in; add
`--output-language en` (or `es`, `ca`, `hu`) to choose another. An existing file
is never overwritten unless you add `--replace`.

The result reports the file's SHA-256, the report's own SHA-256 and the
fingerprint of the key the summary is signed with. Writing the same calculation
again, at the same export instant, produces the same bytes.

## Read the summary

The first page states that the document is a local calculation and names the
software identity the filing file would carry. For the development identity
(program `0000`, developer NIF `00000000T`) it says that file cannot be
presented at AEAT. A table then shows the calculation's state, its verification,
whether a filing is recorded, the export instant, and your NIF and name.

Each registry section follows as a table of casilla, concept and amount. Three
states read differently:

- a figure, including a zero, is a calculated value;
- `— sin dato` (`— no data`) means the calculation recorded no value;
- `n/a · no aplicable` (`n/a · not applicable`) means the registry proves the
  casilla does not apply to the period.

Subtotals are set in bold and the result row is shaded. The last section,
Traceability and integrity, prints every identifier in full: the calculation
revision, work unit, verification report, filing record, registry snapshot and
authority generation, the report and CSV digests, and the signing key's
fingerprint.

## What travels inside the file

The PDF is archival (PDF/A-3) and tagged for assistive technology (PDF/UA-1). It
embeds four files, which any PDF viewer lists as attachments:

- `cadrumo-calculation-report.json`, the authoritative data the pages render;
- `cadrumo-calculation-report.csv`, the same table the CSV format writes;
- `cadrumo-report-certification.json`, the signed integrity statement;
- `cadrumo-report-certification.sig`, its 64-byte Ed25519 signature.

Your NIF and name appear on the pages and in the embedded JSON and CSV, because
the summary is your own document. They never appear in the document metadata,
which carries only identifiers, digests, codes and the signing public key. Third
parties, such as the perceptors behind a withholding, appear only as keyed
digests. The filing file and your evidence documents are not embedded.

## What the signature means

The summary is signed with your profile's key, the same key that signs your
review packages. A valid signature means that this key declared that, at the
export instant by this computer's clock, the named calculation, verification,
registry snapshot and authority produced exactly this report, CSV and pages.

It does not mean that AEAT accepted or received a filing, that the calculation
is legally correct, that the inputs were true, or that the key belongs to a
particular person. PDF viewers show no signature badge: the check is done with
Cadrumo or with OpenSSL as described below. A recipient trusts the key by
comparing its fingerprint, printed on the last page, with one received from you
through another channel.

## Verify a summary with Cadrumo

On the computer holding the profile that wrote it, check a summary against your
encrypted store:

```text
aeat app modelo work report-verify modelo-130-2026-1T.pdf
```

Cadrumo checks the signature, the embedded data, the metadata and the pages, then
rebuilds the report from the store and compares it. The outcome is one of:

- `verified`: the file is intact and still matches the store;
- `verified_with_later_changes`: it matches the store as it was at export, and
  the calculation has since moved on, for example it was filed;
- `valid_unpinned`: the file is internally consistent, but no key was trusted
  and the store was not consulted;
- `refused`: a check failed; each check row names its reason.

The command exits with status 1 when the outcome is `refused`.

To check only the document, without opening your store, add `--document-only`.
Anyone can forge a consistent document with their own key, so a document-only
check is `valid_unpinned` unless you also name the key you trust:

```text
aeat app modelo work report-verify summary.pdf --document-only --trusted-key PUBLIC_KEY_HEX
```

## Verify a summary without Cadrumo

A recipient with OpenSSL 3 can check the signature. First save the four embedded
files into one folder, from the attachments panel of a PDF viewer or with
poppler's `pdfdetach -saveall summary.pdf`. The signed digest is the SHA-256 of
the text `cadrumo/calculation-report-certification/v1`, one NUL byte, and the
statement file. The public key is the `public_key_hex` value inside the
statement; compare its SHA-256 with the fingerprint you were given before
trusting it. Replace `PUBLIC_KEY_HEX` below with that value.

On Linux or macOS:

```text
key=PUBLIC_KEY_HEX
{ printf 'cadrumo/calculation-report-certification/v1\0'; cat cadrumo-report-certification.json; } > signed.bin
openssl dgst -sha256 -binary -out digest.bin signed.bin
printf "$(printf '302a300506032b6570032100%s' "$key" | sed 's/../\\x&/g')" > public.der
openssl pkeyutl -verify -pubin -keyform DER -inkey public.der -rawin -in digest.bin -sigfile cadrumo-report-certification.sig
```

In PowerShell 7:

```text
$key = "PUBLIC_KEY_HEX"
$prefix = [Text.Encoding]::ASCII.GetBytes("cadrumo/calculation-report-certification/v1") + [byte]0
[IO.File]::WriteAllBytes("$PWD/signed.bin", $prefix + [IO.File]::ReadAllBytes("$PWD/cadrumo-report-certification.json"))
openssl dgst -sha256 -binary -out digest.bin signed.bin
[IO.File]::WriteAllBytes("$PWD/public.der", [Convert]::FromHexString("302a300506032b6570032100$key"))
openssl pkeyutl -verify -pubin -keyform DER -inkey public.der -rawin -in digest.bin -sigfile cadrumo-report-certification.sig
```

OpenSSL prints `Signature Verified Successfully` for an intact statement and
`Signature Verification Failure` otherwise. The statement also lists the SHA-256
of the embedded JSON and CSV as `report_sha256` and `csv_sha256`: compute the
digests of those two files (`sha256sum`, `shasum -a 256` on macOS, or
`Get-FileHash` in PowerShell, which prints capitals) and compare, to confirm the
data was not changed. Checking that the pages themselves match the statement
needs Cadrumo.
