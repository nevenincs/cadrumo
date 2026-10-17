//! Safe application-boundary failures.
//!
//! An original cause stays local: its message, paths and payloads are never
//! serialized. What leaves the boundary is a closed fact per link of the cause
//! chain (an I/O kind, a JSON position, a nested catalogue code, a child
//! process's registered refusal) and a static reason naming which check of
//! several sharing one code failed.
use serde::{Deserialize, Serialize};
use std::{borrow::Cow, error::Error, fmt, sync::Arc};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidArguments,
    PackageUnavailable,
    EnvironmentFailed,
    TimedOut,
    OutputLimit,
    SpawnFailed,
    ChildFailed,
    ReadFailed,
    WriteFailed,
    ResizeFailed,
    CleanupFailed,
    SessionUnavailable,
    QueueFull,
    CliBusy,
    CliWaitTimedOut,
    LockPoisoned,
    LogUnavailable,
    DesktopUnavailable,
    WebviewFailed,
    WebviewProcessFailed,
    WebviewMonitorUnavailable,
    UnsupportedPlatform,
    InstanceLockForeign,
    ManagerUnavailable,
    ManagerDispatchFailed,
    InstallationUnavailable,
    InstallationRefused,
    InstallationCancelled,
    InstallationFailed,
    InstallationUnsettled,
    Panic,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    Launch,
    Package,
    Environment,
    Cli,
    Terminal,
    Logging,
    Webview,
    Shutdown,
    Manager,
    Installation,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApplicationError {
    pub code: ErrorCode,
    pub operation: Operation,
    pub message: &'static str,
    #[serde(
        serialize_with = "serialize_io_kind",
        skip_serializing_if = "Option::is_none"
    )]
    pub io_kind: Option<std::io::ErrorKind>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub os_code: Option<i32>,
    /// Which of the checks sharing this code failed; always a static identifier.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<Cow<'static, str>>,
    /// The cause chain, outermost first, as closed payload-free facts.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub causes: Vec<Cause>,
    #[serde(skip)]
    cause: Option<Arc<dyn Error + Send + Sync>>,
}

/// One link of a failure's cause chain, reduced to facts that carry no payload.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(
    tag = "kind",
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum Cause {
    Io {
        io_kind: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        os_code: Option<i32>,
    },
    Json {
        category: String,
        line: usize,
        column: usize,
    },
    Application {
        code: ErrorCode,
        operation: Operation,
        #[serde(skip_serializing_if = "Option::is_none")]
        reason: Option<String>,
    },
    Child(ChildRefusal),
    TimedOut,
    Disconnected,
    /// A cause of a type this boundary does not describe; its text stays local.
    Opaque,
}

impl Cause {
    fn of(error: &(dyn Error + 'static)) -> Self {
        if let Some(error) = error.downcast_ref::<std::io::Error>() {
            return Self::Io {
                io_kind: format!("{:?}", error.kind()),
                os_code: error.raw_os_error(),
            };
        }
        if let Some(error) = error.downcast_ref::<serde_json::Error>() {
            return Self::Json {
                category: format!("{:?}", error.classify()).to_ascii_lowercase(),
                line: error.line(),
                column: error.column(),
            };
        }
        if let Some(error) = error.downcast_ref::<ApplicationError>() {
            return Self::Application {
                code: error.code,
                operation: error.operation,
                reason: error.reason.as_deref().map(str::to_owned),
            };
        }
        if let Some(refusal) = error.downcast_ref::<ChildRefusal>() {
            return Self::Child(refusal.clone());
        }
        if let Some(error) = error.downcast_ref::<std::sync::mpsc::RecvTimeoutError>() {
            return match error {
                std::sync::mpsc::RecvTimeoutError::Timeout => Self::TimedOut,
                std::sync::mpsc::RecvTimeoutError::Disconnected => Self::Disconnected,
            };
        }
        if error.downcast_ref::<std::sync::mpsc::RecvError>().is_some() {
            return Self::Disconnected;
        }
        Self::Opaque
    }

    /// Whether a persisted fact still has the closed shape this boundary writes.
    pub fn admissible(&self) -> bool {
        match self {
            Self::Io { io_kind, .. } => admit::identifier(io_kind),
            Self::Json { category, .. } => admit::identifier(category),
            Self::Application { reason, .. } => reason.as_deref().is_none_or(admit::identifier),
            Self::Child(refusal) => refusal.admissible(),
            Self::TimedOut | Self::Disconnected | Self::Opaque => true,
        }
    }

    pub fn summary(&self) -> String {
        match self {
            Self::Io { io_kind, os_code } => match os_code {
                Some(code) => format!("io {io_kind} (os {code})"),
                None => format!("io {io_kind}"),
            },
            Self::Json {
                category,
                line,
                column,
            } => format!("json {category} at {line}:{column}"),
            Self::Application {
                code,
                operation,
                reason,
            } => {
                let mut text = format!("{} during {}", token(code), token(operation));
                if let Some(reason) = reason {
                    text.push_str(&format!(" ({reason})"));
                }
                text
            }
            Self::Child(refusal) => refusal.summary(),
            Self::TimedOut => "timed out".to_owned(),
            Self::Disconnected => "disconnected".to_owned(),
            Self::Opaque => "unclassified cause".to_owned(),
        }
    }
}

fn token(value: impl Serialize) -> String {
    serde_json::to_value(value)
        .ok()
        .and_then(|value| value.as_str().map(str::to_owned))
        .unwrap_or_default()
}

/// What a Cadrumo child process said about its own failure: its registered
/// code or refusal, the failing exception's type and first-party frame, and
/// the correlation id of the child's durable log record. Never its message.
#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ChildRefusal {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exception_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raised_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<String>,
}

impl ChildRefusal {
    /// The refusal a bridge child answered on its protocol channel, with the
    /// registered report the child sent on the same line, when it sent one.
    pub fn answered(document: &serde_json::Value) -> Self {
        Self {
            code: document["code"]
                .as_str()
                .filter(|v| admit::identifier(v))
                .map(str::to_owned),
            ..Self::default()
        }
        .with_report(Self::from_document(&document["report"]))
    }

    /// The registered error document a Cadrumo child wrote as the last JSON
    /// line of its standard error, when there is exactly one.
    pub fn reported(stderr: &[u8]) -> Option<Self> {
        let parse = |line: &[u8]| serde_json::from_slice::<serde_json::Value>(line).ok();
        let mut documents = stderr
            .split(|b| *b == b'\n')
            .filter_map(parse)
            .filter(|document| document.get("schema_version").is_some());
        let document = documents.next_back()?;
        if documents.next().is_some() {
            return None;
        }
        Self::from_document(&document)
    }

    /// The admitted identifiers of one registered error document.
    fn from_document(document: &serde_json::Value) -> Option<Self> {
        if document["status"] != "error" {
            return None;
        }
        let error = &document["error"];
        let context = &error["context"];
        let pick = |value: &serde_json::Value, admitted: fn(&str) -> bool| {
            value.as_str().filter(|v| admitted(v)).map(str::to_owned)
        };
        Some(Self {
            code: pick(&error["code"], admit::identifier),
            reason: pick(&context["reason"], admit::identifier),
            exception_type: pick(&context["exception_type"], admit::qualified),
            raised_at: pick(&context["raised_at"], admit::first_party_source),
            trace_id: pick(&error["trace_id"], admit::trace)
                .or_else(|| pick(&context["trace_id"], admit::trace)),
        })
    }

    /// Fills what the protocol answer lacks from the child's own report.
    pub fn with_report(mut self, report: Option<Self>) -> Self {
        if let Some(report) = report {
            self.reason = self.reason.or(report.reason).or(report.code);
            self.exception_type = self.exception_type.or(report.exception_type);
            self.raised_at = self.raised_at.or(report.raised_at);
            self.trace_id = self.trace_id.or(report.trace_id);
        }
        self
    }

    pub fn admissible(&self) -> bool {
        self.code.as_deref().is_none_or(admit::identifier)
            && self.reason.as_deref().is_none_or(admit::identifier)
            && self.exception_type.as_deref().is_none_or(admit::qualified)
            && self
                .raised_at
                .as_deref()
                .is_none_or(admit::first_party_source)
            && self.trace_id.as_deref().is_none_or(admit::trace)
    }

    fn summary(&self) -> String {
        let mut text = format!(
            "child refused {}",
            self.code.as_deref().unwrap_or("without a code")
        );
        for (label, value) in [
            ("reason", &self.reason),
            ("exception", &self.exception_type),
            ("at", &self.raised_at),
            ("trace", &self.trace_id),
        ] {
            if let Some(value) = value {
                text.push_str(&format!(" {label} {value}"));
            }
        }
        text
    }
}

impl fmt::Display for ChildRefusal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.summary())
    }
}

impl Error for ChildRefusal {}

/// Shape checks for the identifiers a cause fact may carry.
pub mod admit {
    pub fn identifier(value: &str) -> bool {
        !value.is_empty()
            && value.len() <= 160
            && value
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_')
    }
    pub fn qualified(value: &str) -> bool {
        !value.is_empty() && value.len() <= 240 && value.split('.').all(identifier)
    }
    pub fn trace(value: &str) -> bool {
        value.len() == 32 && value.bytes().all(|b| b.is_ascii_hexdigit())
    }
    /// A `module:function:line` frame inside Cadrumo's own packages.
    pub fn first_party_source(value: &str) -> bool {
        let parts: Vec<_> = value.split(':').collect();
        let first_party = [
            "cadrumo",
            "cadrumo_client",
            "cadrumo_runtime",
            "cadrumo_agent_service",
            "cadrumo_harness",
        ]
        .iter()
        .any(|root| {
            parts[0] == *root
                || parts[0]
                    .strip_prefix(root)
                    .is_some_and(|suffix| suffix.starts_with('.'))
        });
        parts.len() == 3
            && first_party
            && qualified(parts[0])
            && identifier(parts[1])
            && !parts[2].is_empty()
            && parts[2].len() <= 10
            && parts[2].bytes().all(|b| b.is_ascii_digit())
            && parts[2].parse::<u32>().is_ok_and(|line| line > 0)
    }
}

impl ApplicationError {
    pub fn new(code: ErrorCode, operation: Operation) -> Self {
        let message = match code {
            ErrorCode::InvalidArguments => "Invalid application arguments",
            ErrorCode::PackageUnavailable => "The application package could not be verified",
            ErrorCode::EnvironmentFailed => "The packaged environment could not be prepared",
            ErrorCode::TimedOut => "The child process exceeded its deadline",
            ErrorCode::OutputLimit => "The child output exceeded its limit",
            ErrorCode::SpawnFailed => "The child process could not be started",
            ErrorCode::ChildFailed => "The child process exited unsuccessfully",
            ErrorCode::ReadFailed => "The child output could not be read",
            ErrorCode::WriteFailed => "The child input could not be written",
            ErrorCode::ResizeFailed => "The terminal could not be resized",
            ErrorCode::CleanupFailed => "Child cleanup could not be confirmed",
            ErrorCode::SessionUnavailable => "The terminal session is unavailable",
            ErrorCode::QueueFull => "The terminal input queue is full",
            ErrorCode::CliBusy => "The sign-in helper is busy",
            ErrorCode::CliWaitTimedOut => "Waiting for the sign-in helper timed out",
            ErrorCode::LockPoisoned => "Application state is unavailable after a worker failure",
            ErrorCode::LogUnavailable => "The diagnostic log could not be written",
            ErrorCode::DesktopUnavailable => "No interactive desktop is available; use --headless",
            ErrorCode::WebviewFailed => "The application window could not be created",
            ErrorCode::WebviewProcessFailed => "An application browser process failed",
            ErrorCode::WebviewMonitorUnavailable => "Browser process diagnostics are unavailable",
            ErrorCode::UnsupportedPlatform => "Desktop operation is not available on this platform",
            ErrorCode::InstanceLockForeign => "Another account holds the application lock",
            ErrorCode::ManagerUnavailable => "The background-services manager is unavailable",
            ErrorCode::ManagerDispatchFailed => {
                "The background-services manager could not be started"
            }
            ErrorCode::InstallationUnavailable => {
                "The background-services installation kit is unavailable"
            }
            ErrorCode::InstallationRefused => {
                "The background-services installation kit could not be verified"
            }
            ErrorCode::InstallationCancelled => "Background-services installation was cancelled",
            ErrorCode::InstallationFailed => "Native background-services installation failed",
            ErrorCode::InstallationUnsettled => {
                "Background-services installation could not be confirmed"
            }
            ErrorCode::Panic => "An unexpected application failure occurred",
        };
        Self {
            code,
            operation,
            message,
            io_kind: None,
            os_code: None,
            reason: None,
            causes: Vec::new(),
            cause: None,
        }
    }
    /// Names which of the checks sharing this code failed.
    pub fn with_reason(mut self, reason: &'static str) -> Self {
        self.reason = Some(Cow::Borrowed(reason));
        self
    }
    pub fn caused_by<E: Error + Send + Sync + 'static>(mut self, cause: E) -> Self {
        // Wrappers can carry an I/O cause; only its enum kind and numeric OS
        // code may leave this boundary, never its path or formatted message.
        self.io_kind = None;
        self.os_code = None;
        self.causes.clear();
        let mut io_settled = false;
        let mut current: &(dyn Error + 'static) = &cause;
        for _ in 0..32 {
            if !io_settled && let Some(error) = current.downcast_ref::<std::io::Error>() {
                self.io_kind = Some(error.kind());
                self.os_code = error.raw_os_error();
                io_settled = self.os_code.is_some();
            }
            self.causes.push(Cause::of(current));
            // A nested boundary error already holds the facts of its own chain.
            if let Some(nested) = current.downcast_ref::<ApplicationError>() {
                self.causes.extend(nested.causes.iter().cloned());
                if self.io_kind.is_none() {
                    self.io_kind = nested.io_kind;
                    self.os_code = nested.os_code;
                }
                break;
            }
            match current.source() {
                Some(source) => current = source,
                None => break,
            }
        }
        self.cause = Some(Arc::new(cause));
        self
    }
    /// The reason and each cause, in one payload-free line for a log view.
    pub fn chain_summary(&self) -> Option<String> {
        let mut parts: Vec<String> = self.reason.iter().map(|r| r.to_string()).collect();
        parts.extend(self.causes.iter().map(Cause::summary));
        (!parts.is_empty()).then(|| parts.join(" <- "))
    }
}
fn serialize_io_kind<S: serde::Serializer>(
    kind: &Option<std::io::ErrorKind>,
    serializer: S,
) -> std::result::Result<S::Ok, S::Error> {
    match kind {
        Some(kind) => serializer.serialize_str(&format!("{kind:?}")),
        None => serializer.serialize_none(),
    }
}
impl fmt::Display for ApplicationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}: {}", self.code, self.message)?;
        if let Some(chain) = self.chain_summary() {
            write!(f, " [{chain}]")?;
        }
        Ok(())
    }
}
impl fmt::Debug for ApplicationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}
impl Error for ApplicationError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        self.cause.as_deref().map(|e| e as &dyn Error)
    }
}
pub type Result<T> = std::result::Result<T, ApplicationError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn distinct_reasons_and_each_link_of_the_chain_are_serialized_without_payloads() {
        let inner = ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
            .with_reason("frame_size")
            .caused_by(std::io::Error::new(
                std::io::ErrorKind::UnexpectedEof,
                "private payload 12345678Z",
            ));
        let outer = ApplicationError::new(ErrorCode::SpawnFailed, Operation::Cli).caused_by(inner);
        let document = serde_json::to_value(&outer).unwrap();
        assert_eq!(document["causes"][0]["kind"], "application");
        assert_eq!(document["causes"][0]["code"], "read_failed");
        assert_eq!(document["causes"][0]["reason"], "frame_size");
        assert_eq!(document["causes"][1]["kind"], "io");
        assert_eq!(document["causes"][1]["ioKind"], "UnexpectedEof");
        assert_eq!(document["ioKind"], "UnexpectedEof");
        assert!(!document.to_string().contains("private"));
        assert!(
            outer
                .to_string()
                .contains("read_failed during cli (frame_size) <- io UnexpectedEof")
        );
        for cause in &outer.causes {
            assert!(cause.admissible());
        }
    }

    #[test]
    fn json_and_channel_causes_keep_their_category() {
        let parse = serde_json::from_slice::<serde_json::Value>(b"{").unwrap_err();
        let error = ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli).caused_by(parse);
        assert!(matches!(&error.causes[..], [Cause::Json { category, .. }] if category == "eof"));
        let timeout = ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
            .caused_by(std::sync::mpsc::RecvTimeoutError::Timeout);
        assert_eq!(timeout.causes, vec![Cause::TimedOut]);
    }

    #[test]
    fn a_child_report_admits_only_registered_identifiers() {
        let stderr = br#"diagnostic prose
{"schema_version":"2","command":"session.hold","status":"error","error":{"code":"REFUSED_LOCAL_RUNTIME","trace_id":"0123456789abcdef0123456789abcdef","context":{"reason":"runtime_peer_untrusted","exception_type":"cadrumo_client.contracts.contracts.RefusalError","raised_at":"cadrumo_runtime.host.session_hold:main:12","note":"PRIVATE"}}}
"#;
        let refusal = ChildRefusal::answered(
            &serde_json::json!({"kind":"session_refused","code":"unavailable"}),
        )
        .with_report(ChildRefusal::reported(stderr));
        assert_eq!(refusal.code.as_deref(), Some("unavailable"));
        assert_eq!(refusal.reason.as_deref(), Some("runtime_peer_untrusted"));
        assert_eq!(
            refusal.raised_at.as_deref(),
            Some("cadrumo_runtime.host.session_hold:main:12")
        );
        assert_eq!(
            refusal.trace_id.as_deref(),
            Some("0123456789abcdef0123456789abcdef")
        );
        assert!(!serde_json::to_string(&refusal).unwrap().contains("PRIVATE"));

        let forged = br#"{"schema_version":"2","status":"error","error":{"code":"a b","context":{"raised_at":"/home/person/file.py:1:2","exception_type":"PRIVATE text"}}}"#;
        let forged = ChildRefusal::reported(forged).unwrap();
        assert_eq!(forged, ChildRefusal::default());
        assert!(ChildRefusal::reported(b"not json").is_none());
    }
}
