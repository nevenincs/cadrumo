//! Closed, payload-free monotonic timing facts for one sign-in helper attempt.
use crate::error::application::admit::{
    first_party_source as source, identifier, qualified, trace,
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum HelperKind {
    Read,
    Mutation,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum HelperOutcome {
    AdmissionRefused,
    SpawnFailed,
    ExecutionFailed,
    /// Native output was returned with a nonzero process exit code.
    NonzeroExit,
    /// Successful native exit; its CLI envelope has not been decoded here.
    Completed,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, Eq, PartialEq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct HelperTiming {
    pub helper_kind: HelperKind,
    pub outcome: HelperOutcome,
    pub admission_wait_ms: u64,
    pub spawn_ms: Option<u64>,
    /// Spawn returned through observed exit or the child wait refusal.
    pub execution_ms: Option<u64>,
    pub cleanup_ms: Option<u64>,
    /// Joins after child cleanup; pipe reading overlaps child execution.
    pub output_join_ms: Option<u64>,
    /// Whole native attempt through output assembly; excludes this summary's emission.
    pub total_ms: u64,
}

/// Caller-owned identity: never construct this from argv, profiles or provider ids.
#[derive(Clone, Copy)]
pub struct HelperIdentity {
    pub command: &'static str,
    pub executable: HelperExecutable,
}
#[derive(Clone, Copy, Debug, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum HelperExecutable {
    Cli,
    Runtime,
    AgentService,
}
#[derive(Clone, Copy, Debug, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum HelperDecode {
    Success,
    Refused,
    NativeRefused,
    Malformed,
    Unavailable,
}
/// A bounded projection of the envelope. Messages, arguments and other context
/// are deliberately absent, even when envelope decoding fails.
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HelperResult {
    pub command: &'static str,
    pub executable: HelperExecutable,
    pub envelope_decode: HelperDecode,
    pub stdout_bytes: u64,
    pub stderr_bytes: u64,
    pub code: Option<String>,
    pub reason: Option<String>,
    pub exception_type: Option<String>,
    pub raised_at: Option<String>,
    pub native_subject: Option<String>,
    /// Correlates this row with the helper's own diagnostic log record.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<String>,
}
impl HelperResult {
    pub fn unavailable(identity: HelperIdentity, stdout_bytes: u64, stderr_bytes: u64) -> Self {
        Self {
            command: identity.command,
            executable: identity.executable,
            envelope_decode: HelperDecode::Unavailable,
            stdout_bytes,
            stderr_bytes,
            code: None,
            reason: None,
            exception_type: None,
            raised_at: None,
            native_subject: None,
            trace_id: None,
        }
    }
    pub fn inspect(identity: HelperIdentity, success: bool, stdout: &[u8], stderr: &[u8]) -> Self {
        let mut fact = Self {
            command: identity.command,
            executable: identity.executable,
            envelope_decode: HelperDecode::Malformed,
            stdout_bytes: stdout.len() as u64,
            stderr_bytes: stderr.len() as u64,
            code: None,
            reason: None,
            exception_type: None,
            raised_at: None,
            native_subject: None,
            trace_id: None,
        };
        let bytes = if success { stdout } else { stderr };
        let parse = |bytes: &[u8]| serde_json::from_slice::<serde_json::Value>(bytes);
        let document = parse(bytes).ok().or_else(|| {
            if success {
                return None;
            }
            let mut lines = bytes
                .split(|b| *b == b'\n')
                .filter(|line| line.iter().any(|b| !b.is_ascii_whitespace()));
            let last = lines.next_back()?;
            let document = parse(last).ok()?;
            // Multiple envelopes are ambiguous; prose before the final envelope is ignored.
            if lines.any(|line| parse(line).is_ok_and(|v| v.get("schema_version").is_some())) {
                return None;
            }
            Some(document)
        });
        let Some(doc) = document else {
            return fact;
        };
        if !success
            && matches!(
                doc["native_refusal"].as_str(),
                Some("launch_value_missing" | "launch_value_malformed" | "invocation_undeclared")
            )
        {
            fact.envelope_decode = HelperDecode::NativeRefused;
            fact.code = doc["native_refusal"].as_str().map(str::to_owned);
            fact.native_subject = doc["subject"]
                .as_str()
                .filter(|value| {
                    (!value.is_empty()
                        && value.len() <= 160
                        && value.as_bytes()[0].is_ascii_uppercase()
                        && value
                            .bytes()
                            .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_'))
                        || matches!(
                            *value,
                            "cadrumo"
                                | "cadrumo-runtime"
                                | "cadrumo-agent-service"
                                | "cadrumo-agent"
                        )
                })
                .map(str::to_owned);
            return fact;
        }
        if doc["schema_version"] != "2" {
            return fact;
        }
        let named = doc["command"].as_str() == Some(identity.command);
        let unnamed = doc.get("command").is_none_or(serde_json::Value::is_null);
        if success
            && named
            && matches!(doc["status"].as_str(), Some("success" | "warning"))
            && doc.get("error").is_none_or(serde_json::Value::is_null)
            && doc.get("result").is_some_and(|v| !v.is_null())
        {
            fact.envelope_decode = HelperDecode::Success;
        } else if !success
            && (named || unnamed)
            && doc["status"] == "error"
            && doc.get("result").is_none_or(serde_json::Value::is_null)
        {
            let error = &doc["error"];
            let Some(code) = error["code"].as_str().filter(|v| identifier(v)) else {
                return fact;
            };
            fact.envelope_decode = HelperDecode::Refused;
            fact.code = Some(code.to_owned());
            let context = &error["context"];
            fact.reason = context["reason"]
                .as_str()
                .filter(|v| identifier(v))
                .map(str::to_owned);
            fact.exception_type = context["exception_type"]
                .as_str()
                .filter(|v| qualified(v))
                .map(str::to_owned);
            fact.raised_at = context["raised_at"]
                .as_str()
                .filter(|v| source(v))
                .map(str::to_owned);
            fact.trace_id = error["trace_id"]
                .as_str()
                .or_else(|| context["trace_id"].as_str())
                .filter(|v| trace(v))
                .map(str::to_owned);
        }
        fact
    }
}
