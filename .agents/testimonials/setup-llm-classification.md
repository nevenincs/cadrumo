# Testimonial — Set up LLM classification providers

- **Doc path:** `docs/how-to/setup-llm-classification.md`
- **Persona:** A first-time user setting up an LLM provider so `aeat app ledger classify --llm` works.
- **Date:** 2026-06-18
- **Env note:** Provider CLIs `claude`/`antigravity`/`codex` ARE installed in this env but NOT logged in; only `ollama-vision` is unreachable. Passphrase pre-set by the harness; all commands run non-interactively (`</dev/null`).

## Walkthrough

### 1. `aeat app ledger classify <transaction-id> --llm claude` (first command on the page, "Supported providers")
- **Expected:** The page's opening example. As a naive reader I'd run it first to classify a transaction.
- **Actual:**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
- **Verdict:** DOC-ISSUE, MINOR. The very first command on the page assumes an active profile that the page never tells me to create. The refusal is in Spanish but is graceful and names the exact fix.

### 2. `aeat app ledger providers` ("Check what aeat can see")
- **Expected:** A list of provider CLIs visible on PATH; "only checks whether each provider executable is discoverable".
- **Actual:**
  ```
  claude	available	C:\Users\hello\.local\bin\claude.EXE
  antigravity	available	C:\Users\hello\AppData\Local\agy\bin\agy.EXE
  codex	available	C:\Users\hello\AppData\Roaming\npm\codex.CMD
  ollama-vision	unavailable	Ollama is not reachable at http://127.0.0.1	start Ollama (ollama serve) and ensure it listens on aeat_llm_ollama_chat_url
  ```
- **Verdict:** OK. Matches the page well. The `unavailable` row names the exact fix (start Ollama). Note: the page lists `claude`, `antigravity`, `codex` but the live output also surfaces `ollama-vision` — a small, harmless mismatch with the documented list.

### 3. `aeat config profile status` (smoke-test, step 1) — run BEFORE creating a profile
- **Expected:** Page implies you "use an existing low-risk transaction in a local test profile"; it does not say to create one.
- **Actual (no profile):**
  ```
  Sin perfil configurado. Ejecuta `aeat config profile create NAME` para empezar.
  next_action	aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>
  ```
- **Verdict:** DOC-ISSUE, MINOR. The smoke-test section never tells the reader to set up the profile and ledger it depends on. Refusal is graceful with a `next_action`.

### 4. `aeat app ledger list --filter classification=NOT_YET_PROCESSED` (smoke-test, step 2) — no profile
- **Actual:**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
- **Verdict:** OK (refusal) / DOC-ISSUE for the missing prerequisite. Same root cause as #3.

### 5. Recover by creating a profile (following the refusal hint)
- `aeat config profile create persona --tax-id 12345678Z --activity "consulting"` (literal hint form) →
  ```
  Refused. El asistente guiado necesita una terminal interactiva, y esta ejecución no la tiene.
  ...
  2. O créalo en un solo paso indicando los datos obligatorios como flags:
       aeat config profile create NAME --quiet --tax-id NIF/CIF/DNI/NIE
  ```
- Re-ran with `--quiet` → `estado creado`, `active_profile persona`.
- **Verdict:** OK for the app (the refusal teaches the `--quiet` non-interactive form). DOC-ISSUE for this page: it never links the profile-setup how-to a new user needs first.

### 6. Smoke-test re-run with profile present
- `aeat config profile status` → returns identity/activities/iva rows. OK.
- `aeat app ledger list --filter classification=NOT_YET_PROCESSED` → `MOVIMIENTOS DEL LIBRO CONTABLE` (empty). OK, but I had no transaction to classify — the page says "use an existing low-risk transaction" without saying how to get one.
- I added one manually: `aeat app ledger add --date 2026-01-15 --amount 42.50 --direction OUTGOING --description "Office supplies from Acme"` → ID returned.

### 7. `aeat app ledger classify <tx> --llm claude` (core smoke test) — provider installed, not logged in
- **Expected:** "previews a suggestion and leaves the ledger unchanged"; if installed but not authenticated, "can refuse with the provider's own error message. Complete that provider login and retry."
- **Actual:**
  ```
  Invalid value: La clasificacion por LLM fallo: claude CLI exited with 1:
  'Not logged in · Please run /login'
  ```
- **Verdict:** OK. This is exactly the documented "installed but not authenticated" path; the provider's own message (`Please run /login`) is surfaced verbatim. The page sets this expectation correctly.

### 8. `aeat app ledger classify <tx> --llm claude --apply`
- **Expected:** Page: only use `--apply` after verifying preview works.
- **Actual:** Same `Not logged in` refusal; no write happened.
- Verified with `aeat app ledger view <tx>`: `Clasificación NOT_YET_PROCESSED`, `Estado de revisión pending` — ledger unchanged.
- **Verdict:** OK. The app honors the "leaves the ledger unchanged" promise even on the apply path when the provider fails.

### 9. `aeat app ledger classify <tx> --llm bogusprovider` (negative test)
- **Actual:**
  ```
  Invalid value for '--llm': 'bogusprovider' is not one of 'claude', 'antigravity', 'codex'.
  ```
- **Verdict:** OK. Graceful Choice error listing accepted values.

### 10. `aeat config check` (persona-brief diagnostic; NOT on the page)
- **Actual (excerpt):**
  ```
  dependency	ollama-vision	ausente	start Ollama (ollama serve) ...
  dependency	llm-provider:claude	disponible
  dependency	llm-provider:antigravity	disponible
  dependency	llm-provider:codex	disponible
  ...
  problema	llm_vision is on but Ollama is not reachable at http://127.0.0.1 ...
  ```
- **Verdict:** DOC-ISSUE, MINOR. `aeat config check` is the richer, more diagnostic command (it reports each `llm-provider:*` status plus a "problema" with the fix) yet the page only ever points the reader at `aeat app ledger providers`. A setup page about getting a provider working should mention `config check`.

## Findings

1. **[MINOR][DOC]** The page's first runnable command (`classify ... --llm claude`) and the smoke-test commands all require an active profile (and the smoke test requires a populated ledger), but the page never tells the reader to create a profile or import/add a transaction first, nor links the profile-setup / import how-tos. Repro: run any page command with no profile → `Refused. No hay un perfil activo`. Fix: add a one-line prerequisite ("This assumes you already have an active profile and at least one transaction — see [Import bank statements] / profile setup") at the top, or in the smoke-test section.

2. **[MINOR][DOC]** The smoke test says "Use an existing low-risk transaction in a local test profile or a redacted ledger" but gives no command to obtain one; a fresh profile has an empty ledger. Repro: `ledger list` on a new profile returns only the header. Fix: link `import-bank-statements.md` or show `aeat app ledger add ...` as the way to get a test transaction.

3. **[MINOR][DOC]** The page never mentions `aeat config check`, which is the most informative provider-diagnostic surface (per-provider `disponible`/`ausente` plus a `problema` line with the fix). Fix: mention `aeat config check` alongside `aeat app ledger providers` in "Check what aeat can see".

4. **[NIT][DOC]** "Supported providers" lists `claude`, `antigravity`, `codex`; live `aeat app ledger providers` also returns an `ollama-vision` row. The page correctly says "for the current list, run `aeat app ledger providers`", so this is minor, but a reader comparing the two will notice the extra entry.

5. **[NIT][BOTH]** All refusals/diagnostics render in Spanish while the doc is English (e.g. `Refused. No hay un perfil activo`, `La clasificacion por LLM fallo`). The doc doesn't warn an English-only reader that CLI output is Spanish. The messages are still actionable, but the language switch is jarring.

## Testimonial

Following the page literally, my very first command bounced because I had no profile — nothing on the page warned me, so I only recovered by reading the (Spanish) refusal, which luckily told me the exact `create` command, then a second refusal taught me to add `--quiet`. Once I had a profile and hand-added a transaction, the core promise held up well: `classify --llm claude` surfaced the provider's own `Not logged in · Please run /login` message exactly as the page described, the bad-provider name gave a clean "not one of claude/antigravity/codex" error, and `--apply` left my ledger untouched when the provider failed. The provider machinery is graceful and instructive; the gap is the page's silence about the profile/transaction prerequisites and about the more useful `aeat config check` diagnostic.

## Scorecard

- **Doc clarity:** 3/5 (provider/privacy story is clear and accurate; loses points for unstated profile + transaction prerequisites and for not mentioning `config check`).
- **App capability:** 5/5 (refusals are graceful, name the exact fix, surface the provider's own error, and honor "ledger unchanged"; only `ollama` unavailable, which is expected).
- **Findings by severity:** BLOCKER 0, MAJOR 0, MINOR 3, NIT 2.
