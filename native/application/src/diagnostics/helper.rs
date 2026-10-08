//! Closed, payload-free monotonic timing facts for one sign-in helper attempt.
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
    /// Native output was returned; its CLI envelope has not been decoded here.
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
