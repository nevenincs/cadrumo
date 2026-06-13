---
step_id: W08.P35.S541
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W08.P35.S541–S549 batch exec

Delivered S541–S549 in one commit (`c1e2a51b4`).

## Sites narrowed

| Step | File | Old handler | New handler | Disposition |
|------|------|-------------|-------------|-------------|
| S541 | `_clave_movil.py:455` | `except Exception` | `except (OSError, AuthError)` | swallow + log (persist non-critical) |
| S542 | `_authenticator.py:862` | `except Exception` | `except (CertificateError, OSError)` + `except Exception → AuthValidationError` | expected absorbed; unexpected re-raised typed |
| S543 | `_workbook_parity.py:308` | `except Exception` | `except (InvalidFileException, BadZipFile, OSError)` + `except Exception → RegistryValidationError` | expected returns failed report; unexpected typed raise |
| S544 | `_workbook_parity.py:1076` | `except Exception` | `except TokenizerError` | regex fallback only on tokenizer failure |
| S545 | `_clave_movil.py:804` | `except Exception` | `except (ImportError, KeyError, AttributeError, UserProfileError)` | diagnostic context best-effort; non-domain errors propagate |
| S546 | `_site_health.py:100` | `raise TypeError(...)` | `raise ValueError(...)` | pydantic v2 validator contract compliance |
| S547 | `_pdfplumber_backend.py:95` | `except Exception` | `except (ImportError, OSError, ValueError, RuntimeError)` | pypdfium2 C-binding surface; unexpected propagates |
| S548 | `_clave_movil.py:1039` | `_invalidate_persisted` bare | nested `try/except` around cleanup call | preserves original exception if cleanup also fails |
| S549 | `src/aeat/test_w08_p35_exceptions.py` | — | 17 real-behaviour tests | all 17 pass |

## New imports added

- `_clave_movil.py`: `from .....domain.user_profile._errors import UserProfileError`
- `_authenticator.py`: `CertificateError` from `.certificate`
- `_workbook_parity.py`: `BadZipFile` from `zipfile`, `TokenizerError` from `openpyxl.formula.tokenizer`, `InvalidFileException` from `openpyxl.utils.exceptions`

## Test outcome

`pytest src/aeat/test_w08_p35_exceptions.py`: 17 passed, 0 failed.

Pre-existing failures in `test_clave_movil.py` (monkeypatch signature mismatch from commit `94370e252`) and `test_workbook_parity.py` (registry schema RegistryLoadError for modelo 100 revision 2020) are unrelated to this P35 work.

## Collision check

`git diff` on all 6 target files before edit: clean (no WIP from peer agents).

## Commit

`c1e2a51b4` — `solidification(W08.P35.S541-S549): narrow 7 broad except-Exception sites + aggregate test`
