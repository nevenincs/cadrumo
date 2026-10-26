//! Browser-process observations contain only closed labels and numeric telemetry.
use serde::Serialize;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProcessKind {
    BrowserProcessExited,
    RenderProcessExited,
    RenderProcessUnresponsive,
    FrameRenderProcessExited,
    UtilityProcessExited,
    SandboxHelperProcessExited,
    GpuProcessExited,
    PpapiPluginProcessExited,
    PpapiBrokerProcessExited,
    UnknownProcessExited,
    Unrecognized,
}
impl ProcessKind {
    pub const fn from_code(code: i32) -> Self {
        match code {
            0 => Self::BrowserProcessExited,
            1 => Self::RenderProcessExited,
            2 => Self::RenderProcessUnresponsive,
            3 => Self::FrameRenderProcessExited,
            4 => Self::UtilityProcessExited,
            5 => Self::SandboxHelperProcessExited,
            6 => Self::GpuProcessExited,
            7 => Self::PpapiPluginProcessExited,
            8 => Self::PpapiBrokerProcessExited,
            9 => Self::UnknownProcessExited,
            _ => Self::Unrecognized,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FailureReason {
    Unexpected,
    Unresponsive,
    Terminated,
    Crashed,
    LaunchFailed,
    OutOfMemory,
    ProfileDeleted,
    Unrecognized,
}
impl FailureReason {
    pub const fn from_code(code: i32) -> Self {
        match code {
            0 => Self::Unexpected,
            1 => Self::Unresponsive,
            2 => Self::Terminated,
            3 => Self::Crashed,
            4 => Self::LaunchFailed,
            5 => Self::OutOfMemory,
            6 => Self::ProfileDeleted,
            _ => Self::Unrecognized,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadFailures {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments_hresult: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kind_hresult: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details_hresult: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason_hresult: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exit_code_hresult: Option<i32>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MonitorOperation {
    Dispatch,
    CoreWebview,
    Register,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(
    tag = "event",
    rename_all = "snake_case",
    rename_all_fields = "camelCase"
)]
pub enum WebviewFailure {
    ProcessFailed {
        kind: Option<ProcessKind>,
        kind_code: Option<i32>,
        reason: Option<FailureReason>,
        reason_code: Option<i32>,
        // For an unresponsive renderer this is STILL_ACTIVE, not a confirmed exit.
        exit_code: Option<i32>,
        read_failures: ReadFailures,
    },
    MonitorUnavailable {
        operation: MonitorOperation,
        hresult: Option<i32>,
    },
}
impl WebviewFailure {
    pub fn process(
        kind_code: Option<i32>,
        reason_code: Option<i32>,
        exit_code: Option<i32>,
        read_failures: ReadFailures,
    ) -> Self {
        Self::ProcessFailed {
            kind: kind_code.map(ProcessKind::from_code),
            kind_code,
            reason: reason_code.map(FailureReason::from_code),
            reason_code,
            exit_code,
            read_failures,
        }
    }
}
