use super::framing::{document, text};
use serde_json::{Map, Value};

/// What the runtime pushed to this connection: a reason to read again,
/// never a value or an authority.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Event {
    /// A watched sign-in or the selection may have changed.
    SignInChanged,
    /// This connection's session ended: `kind` says how, `reason` why.
    SessionRetired {
        kind: String,
        reason: String,
    },
    LanguageChanged,
    RecordsChanged,
    AttendanceChanged,
    AttendanceAnswered,
    OperationChanged,
    ServiceLeaseChanged,
    ServiceAdmissionChanged,
    ProfileLoginChanged {
        login_request_id: String,
    },
    LifecycleNotice,
    ModelRunRequested,
    /// The connection ended; no further reply or event will arrive.
    Disconnected,
}

/// A pushed event with the profile and session the runtime addressed it to,
/// for a holder that must tell its own session's cues from another's.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Pushed {
    pub event: Event,
    pub profile_id: Option<String>,
    pub session_id: Option<String>,
}

pub(super) fn event(document: &Map<String, Value>) -> Event {
    match text(document, "kind") {
        Some("sign_in_changed") => Event::SignInChanged,
        Some("session_event") => Event::SessionRetired {
            kind: text(document, "event").unwrap_or_default().to_owned(),
            reason: text(document, "reason").unwrap_or_default().to_owned(),
        },
        Some("profile_language_changed") => Event::LanguageChanged,
        Some("profile_records_changed") => Event::RecordsChanged,
        Some("attendance_changed") => Event::AttendanceChanged,
        Some("attendance_answered") => Event::AttendanceAnswered,
        Some("operation_changed") => Event::OperationChanged,
        Some("service_lease_changed") => Event::ServiceLeaseChanged,
        Some("service_admission_changed") => Event::ServiceAdmissionChanged,
        Some("profile_login_changed") => Event::ProfileLoginChanged {
            login_request_id: text(document, "login_request_id")
                .unwrap_or_default()
                .to_owned(),
        },
        Some("lifecycle_notice") => Event::LifecycleNotice,
        Some("model_run_requested") => Event::ModelRunRequested,
        _ => Event::Disconnected,
    }
}
