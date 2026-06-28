# Testimonial — classify-with-llm-evidence.md

- **Doc path:** `docs/how-to/classify-with-llm-evidence.md`
- **Persona:** A naive first-time user trying to classify a transaction by having a
  model read its attached invoice. No local vision model installed, no cloud provider
  logged in, and the `cloud_evidence_upload` capability is off by default.
- **Date:** 2026-06-18
- **Env base:** `/tmp/persona-cllme-fg`

---

## Walkthrough

### Setup (not on the page — synthesized to reach a transaction)

The page builds on `classify-with-llm.md` and `ledger-evidence.md` and never shows how
to create a profile, import a transaction, or attach evidence. I had to synthesize all
of that to have a `<transaction-id>` to classify.

1. `aeat config profile create test-user --quiet --tax-id 12345678Z`
   - **Expected:** a profile so I can hold a ledger.
   - **Actual:** first attempt (`create test-user --tax-id ...`) refused because the
     guided wizard needs a TTY: *"Refused. El asistente guiado necesita una terminal
     interactiva..."* — but it printed the exact non-interactive form (`--quiet`). With
     `--quiet`: `estado creado`, `active_profile test-user`.
   - **Verdict:** OK (graceful, instructive refusal — but Spanish).

2. Imported a 1-row CSV: `aeat app ledger import "$BASE/stmt.csv" --provider csv`
   - **Actual:** `Entradas importadas 1`. Transaction id `d47b26b2`. (My CSV
     `direction=OUTGOING` column was ignored — `view` later showed `Sentido INCOMING`.)
   - **Verdict:** OK for setup; the ignored direction is out of this page's scope (NIT).

I could **not** attach real evidence bytes through any command on this page: `aeat app
ledger attach` takes only `--attachment-id` / `--purchase-invoice-evidence-id`, not a
file. Storing the bytes is delegated to `ledger-evidence.md`. So every `--read-evidence`
run below hit a transaction with **no readable evidence**.

### On-host image read (page §"Read a scanned or image invoice on-host")

3. `aeat app ledger classify d47b26b2 --read-evidence --saturate`
   - **Expected (per page):** the local vision model reads the image and previews a
     classification + IVA category; "you need no acknowledgement."
   - **Actual:**
     ```
     Error. classifying this transaction needs a cloud provider: pass --llm with claude,
     antigravity, or codex. (--read-evidence reads a scanned or image invoice on-host with
     no provider, but this transaction has no readable image evidence to route there.)
     ```
   - **Verdict:** OK (APP) — graceful, no crash, and the message explicitly explains the
     on-host-vs-cloud split. Could not exercise the real Ollama path (no image evidence,
     Ollama not installed), but the refusal is exemplary.

   I did **not** run `ollama pull qwen2.5vl:3b` — Ollama is external and not installed in
   this environment, which is expected. The page sets the on-host expectation clearly.

### Cloud text-layer PDF read (page §"Read a text-layer PDF through a cloud provider")

4. Without ack: `aeat app ledger classify d47b26b2 --llm claude --read-evidence --saturate`
   - **Expected (per page line 78-80):** *"Without the acknowledgement, the command
     refuses and explains that reading text-layer evidence sends it to a cloud model."*
   - **Actual:**
     ```
     Invalid value: La clasificacion por LLM fallo: claude CLI exited with 1:
     'Not logged in · Please run /login'
     ```
     The command went **straight to the provider** — it did NOT refuse on the missing
     acknowledgement / `AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED` gate.
   - **Verdict:** DOC-ISSUE (the page's promise didn't reproduce here) — but see Finding 1:
     the consent gate only fires when there is *actual text-layer evidence to upload*. With
     no evidence attached, `--read-evidence` is a no-op and nothing is uploaded, so the
     gate correctly stays silent. The page does not say "the refusal only happens when real
     text-layer evidence exists."

5. With ack and with `AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED=1`:
   `... --llm claude --read-evidence --evidence-acknowledged --saturate`
   - **Actual:** identical "Not logged in" provider error. Confirms the consent gate is
     bypassed when there's no evidence, regardless of the flags.
   - **Verdict:** OK (consistent) — cannot verify the actual upload-gate refusal text here.

6. Gestor-mode bar: `AEAT_EVIDENCE_GESTOR_MODE=1 AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED=1 ...
   --evidence-acknowledged`
   - **Actual:** same "Not logged in" — again, no evidence so the gestor bar never fires.
   - **Verdict:** Unverifiable here; the bar is real in code (see "Security posture"), but
     cannot be exercised without real text-layer evidence.

### Auto-split (page §"Split a multi-line invoice automatically")

7. `aeat app ledger classify d47b26b2 --read-evidence --auto-split`
   - **Actual:** same on-host "needs a cloud provider / no readable image evidence" refusal.
   - **Verdict:** OK refusal; the auto-split behaviour itself is unverifiable without a real
     multi-line invoice attached.

### Manual / derived override (page §"Review, approve, reject, or override")

8. Documented fallback as written: `aeat app ledger classify d47b26b2 --iva-category
   domestic_general_21 --saturate`
   - **Expected (page line 111-116):** *"If the model returns `unknown`... choose a
     category yourself and let `aeat` derive the rest."* — presented as self-contained.
   - **Actual:**
     ```
     Invalid value: IVA derivation applies only to a business transaction;
     classify it as BUSINESS or MIXED first, then derive the IVA substrate
     ```
   - **Verdict:** DOC-ISSUE (MINOR) — the command does **not** work standalone; the page
     omits the prerequisite that the transaction must already be BUSINESS/MIXED. The error
     is instructive, but a naive reader following the page literally hits a wall.

9. Prerequisite then retry: `classify ... --classification BUSINESS --category-id
   material_oficina`, then `classify ... --iva-category domestic_general_21 --saturate`
   - **First try** used `--category-id office_supplies` → refused: *"--category-id
     'office_supplies' no reconocido... Ejecuta `aeat app ledger categories`..."* (great
     pointer). Ran `categories`, found `material_oficina`.
   - **Then the derived override succeeded:**
     ```
     Categoria de IVA   domestic_general_21
     Base imponible     100.00
     Tipo de IVA        0.21
     Importe de IVA     21.00
     clasificado-por    derived:iva-category
     ```
   - **Verdict:** OK (APP delivers) — `aeat` derived base 100.00 + IVA 21.00 from the
     €121 amount; the model/user set no number. Provenance `derived:iva-category` matches
     the page's "Provenance you can audit" table exactly.

### Provenance commands (page §"Provenance you can audit")

10. `aeat app ledger view d47b26b2` and `aeat app ledger history d47b26b2`
    - **Actual:** `view` shows Clasificación BUSINESS, Categoría material_oficina, Base 100,
      IVA 21, Estado de revisión reviewed. `history` shows a 4-event audit trail (imported,
      classified, updated, classified) with content hashes.
    - **Verdict:** OK — both commands work and surface the audit trail the page promises.

---

## Security posture verification (the heart of this persona)

I confirmed against the source that the page's security claims are real, not aspirational:

- `cloud_evidence_read_permitted` (`src/aeat/application/ledger/_evidence_input.py:38`)
  gates an off-host read on `ServiceCapability.CLOUD_EVIDENCE_UPLOAD` **enabled AND
  acknowledged this invocation**; the acknowledgement is never sticky. Default-off.
- The docstring confirms the page's ordering: the gestor-mode bar is applied "first and
  absolutely" (`AEAT_EVIDENCE_GESTOR_MODE`), then the profile fact, then the global
  `AEAT_EVIDENCE_CLOUD_UPLOAD_PERMITTED` default-off flag; a capability can only NARROW,
  never widen.
- `EvidenceInput` holds decrypted FINANCIAL bytes "in memory only" and refuses
  serialization/persistence — matching the page's "never writes them to a temp file, a
  log, or a cache."

So the page **accurately** sets the expectation: on-host is the default and needs no
acknowledgement; cloud text-layer upload is off by default, gestor-barred, and requires a
per-run ack. What I could not do in this env is *trigger* the refusal text, because that
gate only fires when real text-layer evidence is present to upload — and no command on
this page lets me attach evidence bytes.

---

## Findings

1. **[MAJOR] [DOC]** — The page promises (line 78-80): "Without the acknowledgement, the
   command refuses and explains that reading text-layer evidence sends it to a cloud
   model." In practice, with `--llm claude --read-evidence` on a transaction that has no
   text-layer evidence, the command does **not** refuse on consent — it proceeds straight
   to the provider (failed here only on "Not logged in"). The consent gate is real but
   fires *only when there is actual text-layer evidence to upload*. The page should state
   this precondition, so a reader who tests the refusal on a no-evidence transaction
   isn't misled into thinking the gate is broken.
   - **Repro:** `aeat app ledger classify <id> --llm claude --read-evidence --saturate`
     on a transaction with no evidence → provider invoked, no consent refusal.
   - **Fix:** Add a sentence: "The refusal applies only when the transaction actually has
     a text-layer PDF to read; with no readable evidence the `--read-evidence` flag is a
     no-op and no upload occurs."

2. **[MINOR] [DOC]** — The "Override" fallback command (lines 114-116) is presented as a
   standalone fix for `unknown` IVA, but it fails on an unclassified transaction:
   *"IVA derivation applies only to a business transaction; classify it as BUSINESS or
   MIXED first."* The page never states the BUSINESS/MIXED prerequisite.
   - **Repro:** `aeat app ledger classify <fresh-id> --iva-category domestic_general_21
     --saturate` → refused.
   - **Fix:** Note that the transaction must already be classified BUSINESS or MIXED (with
     a category for expenses) before deriving the IVA substrate; or show the two-step form.

3. **[MINOR] [DOC]** — The page is unrunnable end-to-end on its own: it never shows how to
   attach evidence bytes, and the linked `attach` verb on this CLI takes only an
   `--attachment-id`/`--purchase-invoice-evidence-id`, not a file. A naive reader cannot
   get from "I have an invoice PDF" to a transaction `--read-evidence` can read using only
   this page. The link to `ledger-evidence.md` exists but the dependency is easy to miss.
   - **Fix:** Add an explicit "Before you start, attach the invoice (see Attach invoices
     and receipts)" prerequisite callout near the top.

4. **[MINOR] [DOC]** — No mention that the local vision path needs Ollama *running* (a
   server), not just `ollama pull`. A naive user who pulls the model but hasn't started
   the daemon will get a connection failure with no guidance from this page.
   - **Fix:** One line: "Ollama must be running (`ollama serve`) before classifying."

5. **[NIT] [DOC]** — The page never warns that a master-key passphrase is required. In an
   interactive shell the first `aeat` command would prompt; a non-interactive user would
   be blocked. (Harness pre-set it here, so it was invisible.) Minor for this page since
   classify isn't the first command a user runs, but worth a cross-link.

6. **[NIT] [BOTH]** — All CLI output and every refusal render in Spanish while the docs are
   English (e.g. `Estado de revisión`, `clasificado-por`, the consent error text). An
   English-only reader following an English page must mentally translate every result.
   Not specific to this page, but it adds friction throughout.

---

## Testimonial (first person)

I came in wanting the simplest thing — point the tool at my invoice and let a model read
it — and the page's framing of on-host-vs-off-host was genuinely clear and reassuring: I
understood immediately that scanned images stay on my machine and only text-layer PDFs
ever leave, off by default and behind a per-run acknowledgement. Where I tripped was that
I couldn't actually *get* an invoice onto a transaction using anything this page shows me,
so every `--read-evidence` command fell back to "no readable evidence" — graceful and
well-worded, never a crash, but I never reached the happy path. The one override command
the page hands me as a fallback didn't run until I'd done a setup step the page never
mentions. The good news: when I finally got there, the app delivered exactly the promise —
`aeat` derived base 100.00 and IVA 21.00 itself, stamped the result `derived:iva-category`,
and the security posture the page describes is real in the code. The page is honest and the
refusals are kind; it just over-promises the consent refusal and under-documents the
prerequisites.

---

## Scorecard

- **Doc clarity:** 3.5 / 5 (clear security framing and good structure; over-promises the
  consent refusal, omits the BUSINESS-first prerequisite and the attach dependency)
- **App capability:** 4.5 / 5 (every refusal graceful and instructive; derived amounts and
  provenance exactly as promised; consent/gestor gates real in code)
- **Findings:** BLOCKER 0 · MAJOR 1 · MINOR 4 · NIT 2
