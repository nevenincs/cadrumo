# GROI response samples

Verbatim text fragments captured from live AEAT GROI servlet responses
(`https://www2.agenciatributaria.gob.es/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet`)
during cl@ve-movil authenticated probing on 2026-05-07.

The samples are the **authority** for the GROI verdict parser at
`src/cadrumo/adapters/outbound/aeat/sede/groi_check.py`. Each filename
encodes the expected verdict so the parametrized regression test
(`test_groi_response_samples_parse_to_expected_verdict`) reads the
file, runs the parser, and asserts the result matches the prefix.

| Filename                          | Expected verdict | Source                                                         |
|-----------------------------------|------------------|----------------------------------------------------------------|
| `valid_telefonica_a28015865.txt`  | `valid`          | NIF `A28015865` (Telefónica SA, public ROI-registered).        |
| `invalid_format_b00000001.txt`    | `invalid`        | NIF `B00000001` (syntactically invalid Spanish NIF).           |

If AEAT changes the response phrasing (e.g., drops the
`CONSTA UN OPERADOR INTRACOMUNITARIO` certification text or rephrases
the format-error message), this regression suite breaks immediately
— that is the whole point.

To add a new sample:

1. Capture the live response text via the project's BrowserSession
   (see `.tmp/probe_groi_response.py` for the script template).
2. Strip identifying chrome (the AEAT header / area-personal dropdown
   leaks the authenticated user's NIF; only keep the verdict-bearing
   block).
3. Save under this directory with a filename of the form
   `{verdict}_{descriptor}.txt` where `{verdict}` is one of
   `valid` / `invalid` / `unknown`.
4. The parametrized test discovers files automatically.
