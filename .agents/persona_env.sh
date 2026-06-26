# Persona test-isolation harness (NOT part of the documented user workflow).
# Usage:  source .agents/persona_env.sh /absolute/unique/base/dir
# Points every aeat var/* state directory under one private base so parallel
# documentation testers never collide on the active profile, master key,
# buckets, ledger, drafts, etc. Also supplies the master-key passphrase that an
# interactive user would type at the prompt.
B="$1"
if [ -z "$B" ]; then echo "persona_env.sh: missing base dir arg" >&2; return 1 2>/dev/null || exit 1; fi
mkdir -p "$B"
export AEAT_SECRET_PASSPHRASE="persona-harness-pass-123"
export AEAT_LOCAL_STORAGE_ROOT="$B/storage"
export AEAT_SECRET_STORE_DIR="$B/secrets"
export AEAT_BLOB_STORE_DIR="$B/blobs"
export AEAT_STORAGE_BACKUP_DIR="$B/backups"
export AEAT_AUDIT_DIR="$B/audit"
export AEAT_REGISTRY_PARITY_STORE_DIR="$B/audit/registry/parity"
export AEAT_FINANCIAL_TXS_DIR="$B/financial/transactions"
export AEAT_INVOICES_DIR="$B/financial/invoices"
export AEAT_ATTACHMENTS_DIR="$B/financial/attachments"
export AEAT_PURCHASE_INVOICE_EVIDENCE_DIR="$B/financial/purchase-invoice-evidence"
export AEAT_USAGE_RATIOS_PATH="$B/financial/usage-ratios.json"
export AEAT_LEDGERS_DIR="$B/financial/ledgers"
export AEAT_LLM_CACHE_DIR="$B/llm-cache"
export AEAT_LLM_USAGE_DIR="$B/llm-usage"
export AEAT_SUBMISSIONS_DIR="$B/submissions"
export AEAT_INBOX_DIR="$B/inbox"
export AEAT_INBOX_PDF_DIR="$B/inbox/pdfs"
export AEAT_WORKFLOW_RUNS_DIR="$B/workflow-runs"
export AEAT_DRAFTS_DIR="$B/drafts"
export AEAT_STATUS_CACHE_DIR="$B/status-cache"
export AEAT_RUNS_DIR="$B/runs"
export AEAT_JUSTIFICANTES_DIR="$B/justificantes"
export AEAT_FILING_HISTORY_DIR="$B/filing-history"
export AEAT_SUBMISSION_BROWSER_TRACE_DIR="$B/browser-traces"
export AEAT_STATUS_BROWSER_TRACE_DIR="$B/browser-traces"
echo "persona env ready under $B"
