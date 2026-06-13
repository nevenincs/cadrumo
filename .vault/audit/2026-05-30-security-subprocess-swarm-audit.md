---
tags:
  - '#audit'
  - '#security-swarm-2026-05-30'
date: '2026-05-30'
modified: '2026-05-30'
related: []
---

# subprocess execution and command injection (security swarm axis 4)

## Scope

Audit of every subprocess execution surface in `src/aeat/` for shell
injection, argv-injection, PATH hijacking, missing timeouts, DLL side-loading,
unsafe environment passing, and unsafe URL launching. Read-only audit;
no source files modified. Covered sinks: `subprocess.run/Popen/check_output`,
`os.system/popen`, `shell=True`, `shutil.which`, `shlex.split`, LibreOffice /
soffice headless, Excel COM (`win32com.client.DispatchEx`), `webbrowser`,
`os.startfile`, and any f-string/`%` shell command construction.

Production subprocess sinks identified (4):

- `src/aeat/domain/calculations/registry/_workbook_parity.py:519, 670, 858` (LibreOffice headless + Excel COM)
- `src/aeat/domain/transactions/_llm.py:404, 423` (LLM CLI shell-out)
- `src/aeat/core/file_permissions.py:70` (Windows `icacls.exe`)
- `src/aeat/core/observability/_replay.py:87` (`shlex.split` of recorded entrypoint)

Test-only subprocess sinks (excluded from severity ranking): test harnesses
under `entrypoints/cli/test_*.py`, `tests/test_*.py`,
`adapters/persistence/storage/bucket/test_lockfile.py`,
`adapters/outbound/aeat/browser/test_live_evasion.py` (which spawns
`powershell -NoProfile -Command <script>` with a `driver_pid` int substituted
into a here-string — argv is list-form and the substituted value is the
integer PID of a process the test itself just started, not external input).

Findings

## Findings

### LOW — LibreOffice argv carries an attacker-controllable workbook path (no shell, list-form argv)

- File: `src/aeat/domain/calculations/registry/_workbook_parity.py:519-537` and `:670-688`
- Data path: `run_workbook_with_libreoffice(workbook_path, ...)` and the binary-XLS converter accept a caller-supplied `workbook_path`. The path is `.resolve()`d and passed as the final positional argv element to `subprocess.run([str(runner), "--headless", ..., str(working_copy)], ...)`.
- Exploit shape: argv is list-form, `shell=False`, so classical shell-metacharacter injection is impossible. The remaining surfaces are (a) a path that begins with `--` would be parsed by soffice as an option, but `Path.resolve()` always returns an absolute path so the first character is `/` (POSIX) or a drive letter (Windows); (b) the `-env:UserInstallation=<uri>` argument is built from `(tmp_path / "lo-profile").resolve().as_uri()` — `tmp_path` is from `TemporaryDirectory(prefix="aeat-workbook-")`, fully controlled, so no injection vector.
- The XLS-conversion path additionally constrains workbook_path to live under a registry-controlled `root` (`_binary_xls_conversion_context` raises `RegistryValidationError` if the path escapes root).
- Remediation: none required. Hygiene note: consider adding an explicit `--` separator before `str(working_copy)` to defeat any future soffice version that re-parses absolute paths as options. No active vulnerability.

### LOW — `_resolve_libreoffice_runner` accepts caller-supplied executable string, validated by basename allowlist

- File: `src/aeat/domain/calculations/registry/_workbook_parity.py:800-819`
- Data path: `executable` parameter is settings-driven (`Settings.aeat_libreoffice_executable: Path | None`) or `shutil.which("soffice"/"libreoffice")`. When provided explicitly, the code resolves to an absolute `Path`, calls `.is_file()`, and then enforces `candidate.name.lower() in {"soffice", "soffice.exe", "libreoffice", "libreoffice.exe"}`.
- Exploit shape: a malicious operator who can set `AEAT_LIBREOFFICE_EXECUTABLE` could point at a renamed binary, but only if it is literally named `soffice[.exe]` or `libreoffice[.exe]` AND already exists at that resolved path. Settings-supplied path is operator-authored config, not external input. No PATH-hijack: `shutil.which` is only called when no explicit path is configured, and a hijacked PATH affecting the operator is out of scope for this app.
- Remediation: low-priority hardening — also verify the resolved path is not inside a world-writable directory (e.g. reject if parent is `/tmp` or `%TEMP%`). Not currently exploitable.

### LOW — Excel COM `DispatchEx("Excel.Application")` opens caller-supplied workbook

- File: `src/aeat/domain/calculations/registry/_workbook_parity.py:854-876`
- Data path: `workbook = excel.Workbooks.Open(str(resolved), UpdateLinks=0, ReadOnly=True)` with `resolved = workbook_path.resolve()` and `.suffix.lower() == ".xlsx"` precondition.
- Exploit shape: not a subprocess-injection surface (no argv). The COM call passes `UpdateLinks=0`, `ReadOnly=True`, sets `excel.DisplayAlerts = False` and `excel.AskToUpdateLinks = False`, blocking auto-link refresh that is the classic Excel-COM RCE vector. Macros are not explicitly disabled (no `AutomationSecurity = msoAutomationSecurityForceDisable`), so a malicious `.xlsx` containing VBA + an `Auto_Open` macro on a host with macro execution permitted by Trust Center could still execute code.
- Remediation: set `excel.AutomationSecurity = 3` (`msoAutomationSecurityForceDisable`) before the `Workbooks.Open` call. Defence-in-depth — current callers feed registry-authored workbooks, so the practical risk is low, but registry workbook ingestion is the documented evidence pathway and should refuse to execute macros on the operator's machine.

### LOW — LLM classifier shells out to `claude`/`gemini`/`codex` with prompt over stdin or argv

- File: `src/aeat/domain/transactions/_llm.py:401-456`
- Data path: `SubprocessLLMClassifier.classify(transaction)` builds `argv = [resolved_binary, *self.command[1:]]`, optionally appends the prompt as the last positional argument when `prompt_via_argument=True` (Gemini); otherwise pipes the prompt to stdin. `self.command` is a frozen tuple constructed by `build_claude_classifier` / `build_gemini_classifier` / `build_codex_classifier` from internal model-tier resolution — no external string concatenation. `resolved_binary = shutil.which(self.command[0])` is checked for `None` and translated to `LLMClassifierError`.
- Exploit shape: list-form argv, `shell=False`, `timeout` enforced. The prompt is built from a `Transaction` (financial data) — passed as a single positional argument to Gemini, so even prompt content containing shell metacharacters cannot escape argv quoting. The only remaining concern is a hijacked `PATH` resolving `claude` to a malicious binary; same operator-trust model as the LibreOffice case.
- Remediation: none required for the call site. Consider documenting in `Settings` that operators on shared hosts should pin absolute paths for the LLM CLIs (analogous to `aeat_libreoffice_executable`).

### LOW — `icacls.exe` invocation for Windows file ACL hardening

- File: `src/aeat/core/file_permissions.py:60-88`
- Data path: argv is `[str(icacls_path), str(path), "/inheritance:r", "/grant:r", f"{candidate}:(F)"]`. `icacls_path` is built from `Path(os.environ.get("SYSTEMROOT", r"C:\\Windows")) / "System32" / "icacls.exe"`. `candidate` is `getpass.getuser()` and optionally `f"{userdomain}\\{username}"`. `path` is the auth-state file the caller is hardening.
- Exploit shape: list-form argv. The `candidate` string is local OS account info, not external input. `SYSTEMROOT` is a Windows-controlled env var; an attacker who can rewrite `SYSTEMROOT` already has interactive logon. **Missing `timeout=`** on the `subprocess.run` call — DoS-shaped concern: a `getpass.getuser()` or `icacls.exe` hang would block the auth-state writer forever. Severity LOW because the outer `try/except Exception` swallows hangs the same way it swallows errors, but the exception only fires after the subprocess returns; a wedged child blocks indefinitely.
- Remediation: add `timeout=10` to the `subprocess.run` call and translate `subprocess.TimeoutExpired` into the existing `_log.warning` path. Same hygiene class as the bug recently fixed elsewhere in the codebase.

### LOW — `shlex.split` of recorded `entrypoint` in replay

- File: `src/aeat/core/observability/_replay.py:87`
- Data path: `parts = shlex.split(entrypoint)` where `entrypoint` is a string field on `RunTrace`, persisted to disk by `run_context` and re-read by `load_trace(run_id)`. `replay_run` does not spawn a subprocess; it calls `invoke(argv)` which re-enters the in-process CLI runner.
- Exploit shape: `shlex.split` parses POSIX shell quoting rules over a string that an attacker with write access to the trace store could craft. Because the result is fed to `invoke(argv)` (Typer's `CliRunner.invoke` or similar in-process callable), not to `subprocess`, this is not a shell-injection sink. An attacker with write access to the trace store can already forge any CLI invocation directly; `shlex.split` does not increase the attack surface.
- Remediation: none required. Note: `replay_run` does mutate `os.environ[REPLAY_ACTIVE_ENV_VAR]` — already documented as an intentional exception.

### Observation — No `shell=True` anywhere in production source

`rg "shell\s*=\s*True"` returns zero hits in `src/aeat/`. The only matches in
the repository are in vault audit prose. This is a strong positive baseline.

### Observation — No `os.system`, `os.popen`, `webbrowser.open`, or `os.startfile` in production source

`rg "os\.(system|popen)\s*\("` and `rg "webbrowser\.|os\.startfile|Start-Process"`
return only `_oauth_flow.py:218` which is a *log message substring match*
(`"browser" in message`), not an actual `webbrowser.open` call. No URL or
file launcher is wired to external input.

### Observation — No subprocess command built from f-string or `%` formatting in production source

`rg "subprocess\.run\(\s*f[\"']"` returns zero hits in `src/aeat/`. All
subprocess invocations use list-form argv.

### Observation — DLL side-loading on Windows

The Excel COM path imports `win32com.client` and `pythoncom` at function
scope; the `icacls.exe` path is invoked with an absolute path derived from
`SYSTEMROOT`. LibreOffice executable resolution requires the basename to
match `soffice[.exe]` / `libreoffice[.exe]` and the path to exist. No
explicit DLL search-path manipulation (`SetDllDirectoryW`, `AddDllDirectory`)
is performed; the default Windows DLL search order applies. Documented as a
hygiene observation, not a finding — the binaries are operator-authored.

## Summary

- HIGH: 0
- MEDIUM: 0
- LOW: 6
- Observations: 4

Most concerning finding: Excel COM `Workbooks.Open` (`_workbook_parity.py:864`)
does not set `AutomationSecurity = msoAutomationSecurityForceDisable` before
opening caller-supplied XLSX workbooks. With macros enabled in the operator's
Excel Trust Center, a malicious `.xlsx` could execute VBA on workbook open.
Mitigated in practice by registry-authored workbook ingestion and by
`UpdateLinks=0` + `ReadOnly=True`, but defence-in-depth recommends an
explicit macro-disable assignment.

Overall posture is strong: zero `shell=True`, zero `os.system`, zero
f-string-built subprocess commands, list-form argv everywhere, basename
allowlisting for the LibreOffice runner, settings-driven executable
configuration, and explicit timeouts on every production subprocess except
the Windows `icacls` hardening helper.

## Recommendations

1. Set `excel.AutomationSecurity = 3` before `Workbooks.Open` in
   `_workbook_parity.run_workbook_with_excel_com` (defence-in-depth).
2. Add `timeout=10` to the `icacls.exe` `subprocess.run` in
   `core/file_permissions.py` to convert a wedged child from "blocks the
   auth flow forever" into a warning-logged best-effort failure.
3. Consider adding an explicit `--` separator before the workbook path
   argument in the two LibreOffice `subprocess.run` invocations to harden
   against a hypothetical future soffice version that re-parses absolute
   paths as options.
4. Document in operator-facing settings docs that
   `aeat_libreoffice_executable` pinning is the recommended posture on
   shared-PATH hosts; the same recommendation should apply to the LLM
   classifier CLIs (`claude`, `gemini`, `codex`).
