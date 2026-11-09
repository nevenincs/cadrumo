//! The provider-settings answers, parsed into the closed shapes the contract
//! names. A value outside a closed set is a protocol failure, never passed on.
use crate::shell::sign_in::wire::Outcome;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const NAME_LIMIT: usize = 100;
const URL_LIMIT: usize = 2048;
const PROVIDER_LIMIT: usize = 64;
const AUTH_URL_LIMIT: usize = 8192;
const CONSOLE_COMMAND_LIMIT: usize = 200;

fn protocol() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
}

/// Why a change was refused, as the stable code the window words.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Refusal {
    NotSignedIn,
    ProfileLocked,
    InvalidKeyFormat,
    BaseUrlRejected,
    RevisionConflict,
    CommittedReadbackFailed,
    CatalogUnavailable,
    RuntimeUnavailable,
    PersonActRequired,
    UnsupportedFlow,
    Busy,
    Unknown,
}

/// What a command refuses with. Only the code crosses to the window.
#[derive(Debug, Serialize)]
pub struct Refused {
    pub code: Refusal,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum CommandFailure {
    Host(ApplicationError),
    Refused(Refused),
}
impl From<ApplicationError> for CommandFailure {
    fn from(error: ApplicationError) -> Self {
        Self::Host(error)
    }
}
impl From<Refusal> for CommandFailure {
    fn from(code: Refusal) -> Self {
        Self::Refused(Refused { code })
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Transport {
    Api,
    Cli,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthKind {
    ApiKey,
    ApiKeyWithBaseUrl,
    ProviderSignInOnly,
    /// A lane on this computer that takes no key and no sign-in.
    #[serde(rename = "none")]
    Keyless,
}

/// What may use a provider. Extraction is not one of them.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Consumer {
    Assistant,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    Key,
    OauthToken,
    ProviderSignIn,
    Disabled,
    Unset,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    Profile,
    None,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Readiness {
    Ready,
    NotVerified,
    Missing,
    Disabled,
    SignInRequired,
    Unusable,
}

/// A refusal code, or one of the four states that are not refusals.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reason {
    NotSignedIn,
    ProfileLocked,
    InvalidKeyFormat,
    BaseUrlRejected,
    RevisionConflict,
    CommittedReadbackFailed,
    CatalogUnavailable,
    RuntimeUnavailable,
    PersonActRequired,
    Unknown,
    NotConfigured,
    TurnedOff,
    SignInWithProviderTool,
    RecordUnreadable,
}

/// Where a provider's own command-line app stands on this computer.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CliState {
    InstalledSignedIn,
    InstalledSignedOut,
    NotInstalled,
    Unknown,
}

/// Why a cli lane's state is not established, in the service's closed words;
/// never provider output.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CliStateCause {
    CliNotFound,
    HomeInGitProject,
    HomeUnavailable,
    ProbeStartFailed,
    ProbeTimedOut,
    ProbeOutputUnreadable,
    ProbeCleanupUnconfirmed,
    StatusReadFailed,
    StatusUnreadable,
    StatusContextUnavailable,
}

/// What a person can do about a cause, in the service's closed words.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum NextStep {
    Retry,
    InstallCli,
    MoveProfileOutsideGit,
    CloseOtherSignIn,
    ConsoleSignIn,
    UpdateApp,
}

/// One provider as the profile holds it. No field is, or is derived from, a
/// secret; a field the contract does not name is dropped, not forwarded.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Entry {
    pub id: String,
    pub provider: String,
    pub display_name: String,
    pub transport: Transport,
    pub auth_kind: AuthKind,
    pub consumers: Vec<Consumer>,
    pub mode: Mode,
    /// Whether a key is stored for the lane, whatever its mode: an off lane
    /// keeps its key. Never the key itself.
    pub credential_saved: bool,
    pub available: bool,
    pub source: Source,
    pub readiness: Readiness,
    pub reason: Option<Reason>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_base_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cli_state: Option<CliState>,
    /// Why the app's state is not established, when the probe says.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cli_state_cause: Option<CliStateCause>,
    /// What to do about `cli_state_cause`; never without one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub next_step: Option<NextStep>,
    pub revision: String,
}

#[derive(Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Status {
    pub providers: Vec<Entry>,
    #[serde(default)]
    pub sign_in_providers: Vec<String>,
    #[serde(default)]
    pub sign_in_methods: BTreeMap<String, Vec<SignInMethod>>,
    /// The console command that signs a provider in by hand, with a
    /// `{provider}` slot for the window to fill.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub console_sign_in_command: Option<String>,
}

impl Status {
    /// Admission uses the exact provider and transport, independently of the
    /// catalog's model support and completed-turn evidence.
    pub fn permits_agent(&self, provider: &str, transport: &str) -> bool {
        let transport = match transport {
            "api" => Transport::Api,
            "cli" => Transport::Cli,
            _ => return false,
        };
        self.providers.iter().any(|entry| {
            let login_required = entry.auth_kind == AuthKind::ProviderSignInOnly
                || entry.mode == Mode::ProviderSignIn;
            entry.provider == provider
                && entry.transport == transport
                && entry.consumers.contains(&Consumer::Assistant)
                && entry.available
                && entry.mode != Mode::Disabled
                && (!login_required || entry.cli_state == Some(CliState::InstalledSignedIn))
        })
    }
}

/// The attended sign-in route the person selected.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum SignInMethod {
    Browser,
    Device,
    BrowserCode,
}

impl SignInMethod {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "browser" => Some(Self::Browser),
            "device" => Some(Self::Device),
            "browser-code" => Some(Self::BrowserCode),
            _ => None,
        }
    }
}

/// A service-owned attempt's current transient event.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignInEvent {
    Starting,
    Started,
    BrowserAction,
    AuthorizationCodeRequired,
    Succeeded,
    Cancelled,
    Failed,
}

/// Helper failures are closed protocol values; arbitrary process output never
/// becomes an error detail sent to the window.
#[derive(Clone, Copy, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignInReason {
    InvalidRequest,
    HostDisconnected,
    Timeout,
    Busy,
    ProviderUnavailable,
    ProviderError,
    UnsupportedFlow,
    CleanupFailed,
    ProfileRequired,
}

/// Why an attempt did not succeed, in the helper's and the service's closed
/// words; never process output.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignInCause {
    ProfileMissing,
    UnsupportedMethod,
    HostInputInvalid,
    HostDisconnected,
    LoginAlreadyRunning,
    TimedOut,
    HomeInGitProject,
    HomeUnavailable,
    CliNotFound,
    BrowserRelayUnavailable,
    CliStartFailed,
    CliExitedEarly,
    CliProtocolMismatch,
    CliReportedError,
    LoginNotCompleted,
    CleanupUnconfirmed,
    InternalError,
    HelperStartFailed,
    HelperOutputInvalid,
    HelperEndedWithoutResult,
    HelperExitNonzero,
    AgentStopFailed,
    StatusNotConfirmed,
}

/// The snapshot returned to the person during a provider sign-in attempt.
/// Deliberately has no `Debug` implementation: URL and device-code fields are
/// transient and must not be written to diagnostics by formatting this value.
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SignInSnapshot {
    pub attempt_id: String,
    pub provider: String,
    pub event: SignInEvent,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<SignInReason>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cause: Option<SignInCause>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub next_step: Option<NextStep>,
    /// Why the status read that confirmed (or failed to confirm) a sign-in
    /// could not establish it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub status_cause: Option<CliStateCause>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_code: Option<String>,
}

/// A provider's identifier: a lower-case token the product's command line
/// reads as itself.
pub fn is_provider_id(text: &str) -> bool {
    (1..=40).contains(&text.len())
        && text.starts_with(|c: char| c.is_ascii_lowercase())
        && text
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

/// The helper uses canonical lower-case UUID text for each attempt.
pub fn is_attempt_id(text: &str) -> bool {
    let bytes = text.as_bytes();
    bytes.len() == 36
        && bytes.iter().enumerate().all(|(index, byte)| match index {
            8 | 13 | 18 | 23 => *byte == b'-',
            _ => byte.is_ascii_digit() || (b'a'..=b'f').contains(byte),
        })
}

fn is_https_url(text: &str) -> bool {
    if text.len() > AUTH_URL_LIMIT
        || !text.starts_with("https://")
        || !text
            .bytes()
            .all(|byte| byte.is_ascii_graphic() && byte != b'\\')
    {
        return false;
    }
    let Some(authority) = text
        .strip_prefix("https://")
        .and_then(|rest| rest.split(['/', '?', '#']).next())
    else {
        return false;
    };
    if authority.is_empty() || authority.contains('@') {
        return false;
    }
    let Ok(url) = tauri::Url::parse(text) else {
        return false;
    };
    let mut code_seen = false;
    url.scheme() == "https"
        && url.host_str().is_some_and(|host| !host.is_empty())
        && url.username().is_empty()
        && url.password().is_none()
        && url.port().is_none_or(|port| port == 443)
        && url.fragment().is_none()
        && url
            .query_pairs()
            .all(|(key, value)| match key.to_ascii_lowercase().as_str() {
                "access_token" | "refresh_token" | "id_token" => false,
                "code" => {
                    let allowed = !code_seen && value == "true";
                    code_seen = true;
                    allowed
                }
                _ => true,
            })
}

/// The console command template: printable ASCII, bounded, naming the
/// provider once and no path.
fn is_console_command(text: &str) -> bool {
    text.len() <= CONSOLE_COMMAND_LIMIT
        && text.matches("{provider}").count() == 1
        && text
            .bytes()
            .all(|b| (b' '..=b'~').contains(&b) && !matches!(b, b'/' | b'\\'))
}

fn valid_user_code(text: &str) -> bool {
    (4..=32).contains(&text.len())
        && text
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
}

impl SignInSnapshot {
    fn checked(self) -> Result<Self, ApplicationError> {
        let browser_event = self.event == SignInEvent::BrowserAction;
        let url_event = browser_event || self.event == SignInEvent::AuthorizationCodeRequired;
        let terminal_event = matches!(
            self.event,
            SignInEvent::Succeeded | SignInEvent::Cancelled | SignInEvent::Failed
        );
        let valid = is_attempt_id(&self.attempt_id)
            && is_provider_id(&self.provider)
            && ((self.reason.is_none()
                && self.cause.is_none()
                && self.next_step.is_none()
                && self.status_cause.is_none())
                || matches!(self.event, SignInEvent::Cancelled | SignInEvent::Failed))
            && (self
                .url
                .as_ref()
                .is_none_or(|url| url_event && is_https_url(url)))
            && (self
                .user_code
                .as_ref()
                .is_none_or(|code| browser_event && valid_user_code(code)))
            && (!terminal_event || self.url.is_none() && self.user_code.is_none());
        if valid { Ok(self) } else { Err(protocol()) }
    }
}

/// Parse a service attempt snapshot and bind it to the request that observed it.
pub fn sign_in_snapshot(
    outcome: Outcome,
    expected_provider: Option<&str>,
    expected_attempt: Option<&str>,
) -> Result<SignInSnapshot, CommandFailure> {
    let snapshot: SignInSnapshot =
        serde_json::from_value(result_of(outcome)?).map_err(|_| protocol())?;
    let snapshot = snapshot.checked()?;
    if expected_provider.is_some_and(|provider| snapshot.provider != provider)
        || expected_attempt.is_some_and(|attempt| snapshot.attempt_id != attempt)
    {
        return Err(protocol().into());
    }
    Ok(snapshot)
}

/// A revision the product handed out: opaque, and safe to hand back as one
/// command-line argument.
pub fn is_revision(text: &str) -> bool {
    (1..=128).contains(&text.len())
        && !text.starts_with('-')
        && text
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b':' | b'-'))
}

fn is_plain_text(text: &str, limit: usize) -> bool {
    !text.is_empty() && text.chars().count() <= limit && !text.chars().any(char::is_control)
}

impl Entry {
    fn checked(self) -> Result<Self, ApplicationError> {
        let ok = is_provider_id(&self.id)
            && is_provider_id(&self.provider)
            && is_plain_text(&self.display_name, NAME_LIMIT)
            && is_revision(&self.revision)
            && self
                .base_url
                .iter()
                .chain(&self.default_base_url)
                .all(|url| is_plain_text(url, URL_LIMIT))
            // A provider's own app has a state; a web API has none.
            && (self.transport == Transport::Cli) == self.cli_state.is_some()
            // Only an app's state has a cause, and a step answers a cause.
            && (self.transport == Transport::Cli
                || (self.cli_state_cause.is_none() && self.next_step.is_none()))
            && (self.next_step.is_none() || self.cli_state_cause.is_some())
            && self.consumers.len() <= 1
            // Only a lane that takes a key can hold one, and a key mode has one.
            && (!self.credential_saved
                || matches!(self.auth_kind, AuthKind::ApiKey | AuthKind::ApiKeyWithBaseUrl))
            // A keyless lane is only ever unset or turned off.
            && (self.auth_kind != AuthKind::Keyless || matches!(self.mode, Mode::Unset | Mode::Disabled))
            && (self.credential_saved || !matches!(self.mode, Mode::Key | Mode::OauthToken));
        if ok { Ok(self) } else { Err(protocol()) }
    }
}

/// The refusal a code names, if it is one of the closed set.
pub fn refusal(code: &str) -> Result<Refusal, ApplicationError> {
    serde_json::from_value(serde_json::Value::String(code.to_owned())).map_err(|_| protocol())
}

/// A successful envelope can still carry a refusal as its whole result.
fn refused_result(result: &serde_json::Value) -> Option<Result<Refusal, ApplicationError>> {
    let object = result.as_object()?;
    let code = object.get("refused")?;
    Some(match (object.len(), code.as_str()) {
        (1, Some(code)) => refusal(code),
        _ => Err(protocol()),
    })
}

fn result_of(outcome: Outcome) -> Result<serde_json::Value, CommandFailure> {
    match outcome {
        Outcome::Refused { refusal: row, .. } => Err(refusal(&row.code)?.into()),
        Outcome::Success { result, .. } => match refused_result(&result) {
            Some(code) => Err(code?.into()),
            None => Ok(result),
        },
    }
}

/// Every provider the profile lists.
pub fn status(outcome: Outcome) -> Result<Status, CommandFailure> {
    let status: Status = serde_json::from_value(result_of(outcome)?).map_err(|_| protocol())?;
    let mut seen = BTreeSet::new();
    let mut seen_sign_in = BTreeSet::new();
    let coherent = status.providers.len() <= PROVIDER_LIMIT
        && status.sign_in_providers.len() <= PROVIDER_LIMIT
        && status
            .sign_in_providers
            .iter()
            .all(|provider| is_provider_id(provider) && seen_sign_in.insert(provider.clone()))
        && status.sign_in_methods.len() <= PROVIDER_LIMIT
        && status.sign_in_methods.iter().all(|(provider, methods)| {
            seen_sign_in.contains(provider)
                && !methods.is_empty()
                && methods.len() <= 3
                && methods
                    .iter()
                    .enumerate()
                    .all(|(index, method)| !methods[..index].contains(method))
        })
        && status
            .providers
            .iter()
            .all(|entry| seen.insert(entry.id.clone()));
    if !coherent {
        return Err(protocol().into());
    }
    if status
        .console_sign_in_command
        .as_deref()
        .is_some_and(|command| !is_console_command(command))
    {
        return Err(protocol().into());
    }
    let providers = status
        .providers
        .into_iter()
        .map(Entry::checked)
        .collect::<Result<_, _>>()?;
    Ok(Status {
        providers,
        sign_in_providers: status.sign_in_providers,
        sign_in_methods: status.sign_in_methods,
        console_sign_in_command: status.console_sign_in_command,
    })
}

/// The new status of the provider a change was made to.
pub fn changed(outcome: Outcome, provider: &str) -> Result<Entry, CommandFailure> {
    let entry: Entry = serde_json::from_value(result_of(outcome)?).map_err(|_| protocol())?;
    let entry = entry.checked()?;
    if entry.id != provider {
        return Err(protocol().into());
    }
    Ok(entry)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn browser_urls_allow_only_a_single_boolean_code_flag() {
        assert!(is_https_url("https://example.org/login?code=true"));
        for query in [
            "code=secret",
            "code=",
            "code=false",
            "code=true&Code=true",
            "Access_Token=",
        ] {
            assert!(!is_https_url(&format!("https://example.org/login?{query}")));
        }
    }
    use serde_json::{Value, json};

    fn api() -> Value {
        json!({
            "id": "alpha_api", "provider": "alpha", "display_name": "Alpha API", "transport": "api",
            "auth_kind": "api_key", "consumers": ["assistant"], "mode": "key",
            "credential_saved": true,
            "available": true, "source": "profile", "readiness": "not_verified",
            "reason": null, "base_url": null, "default_base_url": null,
            "revision": "00ff"
        })
    }

    fn cli() -> Value {
        json!({
            "id": "beta_cli", "provider": "beta", "display_name": "Beta CLI", "transport": "cli",
            "auth_kind": "provider_sign_in_only", "consumers": ["assistant"],
            "mode": "provider_sign_in", "credential_saved": false,
            "available": false, "source": "none",
            "readiness": "sign_in_required", "reason": "sign_in_with_provider_tool",
            "cli_state": "installed_signed_out", "revision": "absent"
        })
    }

    fn keyless() -> Value {
        json!({
            "id": "local_api", "provider": "local", "display_name": "Local", "transport": "api",
            "auth_kind": "none", "consumers": ["assistant"], "mode": "unset",
            "credential_saved": false,
            "available": true, "source": "none", "readiness": "not_verified",
            "reason": null, "base_url": null, "default_base_url": "http://127.0.0.1:41000",
            "revision": "absent"
        })
    }

    #[test]
    fn a_keyless_lane_is_admitted_with_no_key_and_no_sign_in() {
        let read = status_of(&[keyless()]);
        assert_eq!(read.providers[0].auth_kind, AuthKind::Keyless);
        assert!(read.permits_agent("local", "api"));
        let sent = serde_json::to_value(&read).unwrap();
        assert_eq!(sent["providers"][0]["auth_kind"], "none");
        assert_eq!(
            sent["providers"][0]["default_base_url"],
            "http://127.0.0.1:41000"
        );

        let mut off = keyless();
        off["mode"] = json!("disabled");
        off["available"] = json!(false);
        off["readiness"] = json!("disabled");
        off["reason"] = json!("turned_off");
        assert!(!status_of(&[off]).permits_agent("local", "api"));

        let mut with_key = keyless();
        with_key["credential_saved"] = json!(true);
        let mut signing_in = keyless();
        signing_in["mode"] = json!("provider_sign_in");
        let mut keyed = keyless();
        keyed["mode"] = json!("key");
        for entry in [with_key, signing_in, keyed] {
            assert_eq!(
                failed(status(success(envelope(&[entry]))))["code"],
                "read_failed"
            );
        }
    }

    fn success(result: Value) -> Outcome {
        Outcome::Success {
            result,
            active_profile: None,
        }
    }

    fn envelope(entries: &[Value]) -> Value {
        json!({"providers": entries})
    }

    fn failed(result: Result<impl std::fmt::Debug, CommandFailure>) -> Value {
        serde_json::to_value(result.unwrap_err()).unwrap()
    }

    fn sign_in_failure(result: Result<SignInSnapshot, CommandFailure>) -> Value {
        match result {
            Err(error) => serde_json::to_value(error).unwrap(),
            Ok(_) => panic!("expected sign-in protocol failure"),
        }
    }

    #[test]
    fn agent_admission_requires_current_settings_for_the_exact_transport() {
        let mut observed = status(success(envelope(&[api(), cli()]))).unwrap();
        assert!(observed.permits_agent("alpha", "api"));
        assert!(!observed.permits_agent("alpha", "cli"));
        assert!(!observed.permits_agent("missing", "api"));
        assert!(!observed.permits_agent("beta", "cli"));

        let cli = &mut observed.providers[1];
        cli.available = true;
        // A stale availability flag cannot authorize a missing login.
        for login in [
            CliState::Unknown,
            CliState::NotInstalled,
            CliState::InstalledSignedOut,
        ] {
            observed.providers[1].cli_state = Some(login);
            assert!(!observed.permits_agent("beta", "cli"));
        }
        observed.providers[1].cli_state = Some(CliState::InstalledSignedIn);
        assert!(observed.permits_agent("beta", "cli"));
        observed.providers[1].mode = Mode::Disabled;
        assert!(!observed.permits_agent("beta", "cli"));
        observed.providers[0].available = false;
        assert!(!observed.permits_agent("alpha", "api"));
    }

    #[test]
    fn configured_cli_api_keys_do_not_require_provider_owned_login() {
        let mut observed = status(success(envelope(&[api()]))).unwrap();
        observed.providers[0].transport = Transport::Cli;
        observed.providers[0].cli_state = Some(CliState::Unknown);
        assert!(observed.permits_agent("alpha", "cli"));
        observed.providers[0].consumers.clear();
        assert!(!observed.permits_agent("alpha", "cli"));
    }

    #[test]
    fn a_status_read_parses_into_the_closed_shapes_and_serializes_as_the_window_reads_it() {
        let status = status(success(envelope(&[api(), cli()]))).unwrap();
        assert!(
            serde_json::to_value(&status)
                .unwrap()
                .get("development")
                .is_none()
        );
        assert_eq!(status.providers.len(), 2);
        assert!(status.sign_in_providers.is_empty());
        assert_eq!(status.providers[0].mode, Mode::Key);
        assert_eq!(status.providers[0].readiness, Readiness::NotVerified);
        assert_eq!(
            status.providers[1].cli_state,
            Some(CliState::InstalledSignedOut)
        );
        assert_eq!(
            status.providers[1].reason,
            Some(Reason::SignInWithProviderTool)
        );
        let sent = serde_json::to_value(&status).unwrap();
        assert_eq!(sent["providers"][0]["auth_kind"], "api_key");
        assert_eq!(sent["providers"][0]["provider"], "alpha");
        assert_eq!(sent["providers"][0]["reason"], Value::Null);
        // Absent stays absent: a web API has no app state, and an unset URL is not sent.
        assert!(sent["providers"][0].get("cli_state").is_none());
        assert!(sent["providers"][0].get("base_url").is_none());
        assert_eq!(sent["providers"][1]["cli_state"], "installed_signed_out");
        assert_eq!(sent["providers"][1]["auth_kind"], "provider_sign_in_only");
        assert_eq!(sent["sign_in_providers"], json!([]));
        assert_eq!(status.providers[1].revision, "absent");
        // A listing with nothing in it is a listing.
        assert!(status_of(&[]).providers.is_empty());
    }

    #[test]
    fn canonical_python_status_is_admitted_without_a_development_flag() {
        let produced: Value = serde_json::from_str(include_str!(env!(
            "CADRUMO_PROVIDER_STATUS_CONTRACT_FIXTURE"
        )))
        .unwrap();
        let document = produced["status"].clone();
        assert!(document.get("development").is_none());
        let parsed = status(success(document.clone())).unwrap();
        assert_eq!(parsed.providers.len(), 3);
        assert!(parsed.permits_agent("local", "api"));
        assert!(!parsed.permits_agent("alpha", "api"));
        assert!(!parsed.permits_agent("beta", "cli"));
        assert_eq!(parsed.providers[0].auth_kind, AuthKind::Keyless);
        assert_eq!(parsed.providers[0].readiness, Readiness::NotVerified);
        assert!(!parsed.providers[0].credential_saved);
        assert_eq!(parsed.providers[1].readiness, Readiness::Missing);
        assert_eq!(parsed.providers[2].readiness, Readiness::SignInRequired);
        assert!(
            serde_json::to_value(parsed)
                .unwrap()
                .get("development")
                .is_none()
        );

        // Corrupt real serialized producer bytes at the consumer boundary.
        for (field, value) in [
            ("available", json!("true")),
            ("credential_saved", json!(1)),
            ("consumers", json!("assistant")),
            ("source", json!("environment")),
        ] {
            let mut invalid = document.clone();
            invalid["providers"][0][field] = value;
            assert_eq!(failed(status(success(invalid)))["code"], "read_failed");
        }
        let refused = super::super::outcome(produced["refusal"].clone());
        assert_eq!(failed(status(refused))["code"], "profile_locked");
    }

    fn status_of(entries: &[Value]) -> Status {
        status(success(envelope(entries))).unwrap()
    }

    #[test]
    fn an_off_lane_keeps_its_saved_key_and_a_saved_key_needs_a_lane_that_takes_one() {
        let mut off = api();
        off["mode"] = json!("disabled");
        off["available"] = json!(false);
        off["source"] = json!("none");
        off["readiness"] = json!("disabled");
        off["reason"] = json!("turned_off");
        let read = status_of(&[off.clone()]);
        assert!(read.providers[0].credential_saved);
        assert_eq!(read.providers[0].reason, Some(Reason::TurnedOff));
        assert!(!read.permits_agent("alpha", "api"));
        let sent = serde_json::to_value(&read).unwrap();
        assert_eq!(sent["providers"][0]["credential_saved"], true);
        assert_eq!(sent["providers"][0]["mode"], "disabled");
        off["credential_saved"] = json!(false);
        assert!(!status_of(&[off]).providers[0].credential_saved);

        let mut sign_in_with_key = cli();
        sign_in_with_key["credential_saved"] = json!(true);
        let mut key_without_key = api();
        key_without_key["credential_saved"] = json!(false);
        for entry in [sign_in_with_key, key_without_key] {
            assert_eq!(
                failed(status(success(envelope(&[entry]))))["code"],
                "read_failed"
            );
        }
    }

    #[test]
    fn a_stored_base_url_and_a_default_come_through_as_text() {
        let mut gateway = api();
        gateway["base_url"] = json!("https://gateway.example/v1");
        gateway["default_base_url"] = json!("https://api.example/v1");
        let read = status_of(&[gateway]);
        let sent = serde_json::to_value(&read).unwrap();
        assert_eq!(
            sent["providers"][0]["base_url"],
            "https://gateway.example/v1"
        );
        assert_eq!(
            sent["providers"][0]["default_base_url"],
            "https://api.example/v1"
        );
    }

    #[test]
    fn a_value_outside_a_closed_set_is_a_protocol_failure() {
        let outside = [
            ("transport", json!("grpc")),
            ("auth_kind", json!("password")),
            ("consumers", json!(["extraction"])),
            ("consumers", json!(["assistant", "assistant"])),
            ("mode", json!("keyring")),
            ("source", json!("keychain")),
            ("readiness", json!("healthy")),
            ("reason", json!("because")),
            ("available", json!("yes")),
            ("credential_saved", json!("yes")),
            ("credential_saved", json!(null)),
            ("id", json!("Alpha_api")),
            ("id", json!("-x")),
            ("provider", json!("Alpha")),
            ("display_name", json!("")),
            ("display_name", json!("Any\nthing")),
            ("revision", json!("")),
            ("revision", json!("-1")),
            ("revision", json!("a b")),
            ("revision", json!("a%20b")),
            ("base_url", json!("")),
        ];
        for (field, value) in outside {
            let mut entry = api();
            entry[field] = value.clone();
            let failure = failed(status(success(envelope(&[entry]))));
            assert_eq!(failure["code"], "read_failed", "{field}: {value}");
        }
        for field in [
            "id",
            "provider",
            "display_name",
            "transport",
            "auth_kind",
            "consumers",
            "mode",
            "credential_saved",
            "available",
            "source",
            "readiness",
            "revision",
        ] {
            let mut entry = api();
            entry.as_object_mut().unwrap().remove(field);
            let failure = failed(status(success(envelope(&[entry]))));
            assert_eq!(failure["code"], "read_failed", "{field} missing");
        }
        // The provider collection is required and every row must be an object.
        for malformed in [
            json!({}),
            json!({"providers": null}),
            json!({"providers": {}}),
        ] {
            assert!(status(success(malformed)).is_err());
        }
        assert!(status(success(envelope(&[json!("alpha_api")]))).is_err());
    }

    #[test]
    fn a_providers_own_app_has_a_state_and_a_web_api_has_none() {
        let mut app_without_state = cli();
        app_without_state
            .as_object_mut()
            .unwrap()
            .remove("cli_state");
        let mut api_with_state = api();
        api_with_state["cli_state"] = json!("not_installed");
        let mut unknown_state = cli();
        unknown_state["cli_state"] = json!("running");
        for entry in [app_without_state, api_with_state, unknown_state] {
            assert!(status(success(envelope(&[entry]))).is_err());
        }
        for state in [
            "installed_signed_in",
            "installed_signed_out",
            "not_installed",
            "unknown",
        ] {
            let mut entry = cli();
            entry["cli_state"] = json!(state);
            assert_eq!(
                status_of(&[entry]).providers[0]
                    .cli_state
                    .map(|s| serde_json::to_value(s).unwrap()),
                Some(json!(state))
            );
        }
    }

    #[test]
    fn environment_credentials_are_refused_and_ids_are_unique() {
        let mut from_environment = api();
        from_environment["source"] = json!("environment");
        let read = json!({"development": true, "providers": [from_environment.clone()]});
        assert!(status(success(read)).is_err());
        assert!(status(success(envelope(&[from_environment]))).is_err());
        assert!(status(success(envelope(&[api(), api()]))).is_err());
        let many: Vec<Value> = (0..=PROVIDER_LIMIT)
            .map(|n| {
                let mut entry = api();
                entry["id"] = json!(format!("p{n}"));
                entry
            })
            .collect();
        assert!(status(success(envelope(&many))).is_err());
    }

    #[test]
    fn gui_sign_in_capabilities_are_a_bounded_unique_provider_slug_list() {
        let mut read = envelope(&[cli()]);
        read["sign_in_providers"] = json!(["codex", "claude"]);
        read["sign_in_methods"] = json!({"codex": ["browser", "device"], "claude": ["browser"]});
        let parsed = status(success(read)).unwrap();
        assert_eq!(
            parsed.sign_in_methods["claude"],
            vec![SignInMethod::Browser]
        );
        assert_eq!(
            parsed.sign_in_providers,
            vec!["codex".to_owned(), "claude".to_owned()]
        );

        for providers in [
            json!(["codex", "codex"]),
            json!(["Codex"]),
            json!(["-codex"]),
            json!(["codex provider"]),
            json!("codex"),
        ] {
            let mut read = envelope(&[]);
            read["sign_in_providers"] = providers;
            assert_eq!(failed(status(success(read)))["code"], "read_failed");
        }

        let too_many = (0..=PROVIDER_LIMIT)
            .map(|index| format!("p{index}"))
            .collect::<Vec<_>>();
        let mut read = envelope(&[]);
        read["sign_in_providers"] = json!(too_many);
        assert_eq!(failed(status(success(read)))["code"], "read_failed");
    }

    #[test]
    fn gui_methods_must_belong_to_advertised_providers_and_be_unique() {
        for methods in [
            json!({"example": []}),
            json!({"example": ["browser", "browser"]}),
            json!({"example": ["password"]}),
            json!({"other": ["browser"]}),
        ] {
            let mut read = envelope(&[]);
            read["sign_in_providers"] = json!(["example"]);
            read["sign_in_methods"] = methods;
            assert_eq!(failed(status(success(read)))["code"], "read_failed");
        }
    }

    #[test]
    fn sign_in_snapshots_are_closed_bounded_and_correlated_to_the_request() {
        let active = json!({
            "attempt_id":"123e4567-e89b-42d3-a456-426614174000",
            "provider":"codex_cli",
            "event":"browser_action",
            "url":"https://auth.openai.com/oauth/authorize?state=opaque",
            "user_code":"A1-B2"
        });
        let parsed = sign_in_snapshot(
            success(active.clone()),
            Some("codex_cli"),
            Some("123e4567-e89b-42d3-a456-426614174000"),
        )
        .unwrap();
        let sent = serde_json::to_value(parsed).unwrap();
        assert_eq!(sent["event"], "browser_action");
        assert_eq!(sent["url"], active["url"]);
        assert_eq!(sent["user_code"], "A1-B2");

        let mut code_required = active.clone();
        code_required["event"] = json!("authorization_code_required");
        code_required.as_object_mut().unwrap().remove("user_code");
        let parsed = sign_in_snapshot(success(code_required.clone()), None, None).unwrap();
        assert_eq!(parsed.event, SignInEvent::AuthorizationCodeRequired);
        assert!(parsed.url.is_some());
        code_required["user_code"] = json!("DEVICE-1234");
        assert!(sign_in_snapshot(success(code_required), None, None).is_err());

        let cancellation_pending = json!({
            "attempt_id":"123e4567-e89b-42d3-a456-426614174000",
            "provider":"codex_cli",
            "event":"browser_action"
        });
        let pending = sign_in_snapshot(
            success(cancellation_pending),
            Some("codex_cli"),
            Some("123e4567-e89b-42d3-a456-426614174000"),
        )
        .unwrap();
        assert_eq!(pending.event, SignInEvent::BrowserAction);
        assert!(pending.url.is_none() && pending.user_code.is_none());
        assert_eq!(
            sign_in_failure(sign_in_snapshot(
                success(active.clone()),
                Some("other_cli"),
                None
            ))["code"],
            "read_failed"
        );
        assert_eq!(
            sign_in_failure(sign_in_snapshot(
                success(active.clone()),
                None,
                Some("123e4567-e89b-42d3-a456-426614174001")
            ))["code"],
            "read_failed"
        );

        for invalid in [
            json!({"attempt_id":"not-a-uuid","provider":"codex_cli","event":"starting"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"Codex_cli","event":"starting"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"ready"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"failed","reason":"raw output"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"started","url":"https://auth.openai.com/"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"http://auth.openai.com/"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://user@auth.openai.com/"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com:444/"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/#fragment"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/?access_token=secret"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/?refresh_token=secret"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/?id_token=secret"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/?code=secret"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/?%63ode=secret"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/","user_code":"bad code"}),
            json!({"attempt_id":"123e4567-e89b-42d3-a456-426614174000","provider":"codex_cli","event":"browser_action","url":"https://auth.openai.com/","unexpected":"not forwarded"}),
        ] {
            assert_eq!(
                sign_in_failure(sign_in_snapshot(success(invalid.clone()), None, None))["code"],
                "read_failed",
                "{invalid}"
            );
        }

        let failed_snapshot = json!({
            "attempt_id":"123e4567-e89b-42d3-a456-426614174000",
            "provider":"codex_cli",
            "event":"failed",
            "reason":"unsupported_flow"
        });
        assert_eq!(
            sign_in_snapshot(success(failed_snapshot), None, None)
                .unwrap()
                .event,
            SignInEvent::Failed
        );
    }

    const ATTEMPT: &str = "123e4567-e89b-42d3-a456-426614174000";

    fn terminal(event: &str, extra: Value) -> Value {
        let mut snapshot = json!({"attempt_id": ATTEMPT, "provider": "codex_cli", "event": event});
        snapshot
            .as_object_mut()
            .unwrap()
            .extend(extra.as_object().unwrap().clone());
        snapshot
    }

    fn sent_snapshot(snapshot: Value) -> Value {
        serde_json::to_value(sign_in_snapshot(success(snapshot), None, None).unwrap()).unwrap()
    }

    #[test]
    fn a_failed_sign_in_carries_its_closed_cause_next_step_and_status_cause() {
        let failed = terminal(
            "failed",
            json!({
                "reason": "provider_error", "cause": "status_not_confirmed",
                "next_step": "console_sign_in", "status_cause": "probe_timed_out"
            }),
        );
        let parsed = sign_in_snapshot(success(failed), None, None).unwrap();
        assert_eq!(parsed.cause, Some(SignInCause::StatusNotConfirmed));
        assert_eq!(parsed.next_step, Some(NextStep::ConsoleSignIn));
        assert_eq!(parsed.status_cause, Some(CliStateCause::ProbeTimedOut));
        let sent = serde_json::to_value(parsed).unwrap();
        assert_eq!(sent["cause"], "status_not_confirmed");
        assert_eq!(sent["next_step"], "console_sign_in");
        assert_eq!(sent["status_cause"], "probe_timed_out");

        let cancelled = terminal(
            "cancelled",
            json!({"reason": "cleanup_failed", "cause": "cleanup_unconfirmed", "next_step": "retry"}),
        );
        let parsed = sign_in_snapshot(success(cancelled), None, None).unwrap();
        assert_eq!(parsed.cause, Some(SignInCause::CleanupUnconfirmed));
        assert_eq!(parsed.next_step, Some(NextStep::Retry));

        // Absent stays absent, as before the service served them.
        let bare = sent_snapshot(terminal("failed", json!({"reason": "provider_error"})));
        for field in ["cause", "next_step", "status_cause"] {
            assert!(bare.get(field).is_none(), "{field}");
        }
    }

    #[test]
    fn every_closed_word_the_service_serves_is_accepted() {
        for word in [
            "profile_missing",
            "unsupported_method",
            "host_input_invalid",
            "host_disconnected",
            "login_already_running",
            "timed_out",
            "home_in_git_project",
            "home_unavailable",
            "cli_not_found",
            "browser_relay_unavailable",
            "cli_start_failed",
            "cli_exited_early",
            "cli_protocol_mismatch",
            "cli_reported_error",
            "login_not_completed",
            "cleanup_unconfirmed",
            "internal_error",
            "helper_start_failed",
            "helper_output_invalid",
            "helper_ended_without_result",
            "helper_exit_nonzero",
            "agent_stop_failed",
            "status_not_confirmed",
        ] {
            let failed = terminal("failed", json!({"reason": "provider_error", "cause": word}));
            assert_eq!(sent_snapshot(failed)["cause"], word);
        }
        for word in [
            "retry",
            "install_cli",
            "move_profile_outside_git",
            "close_other_sign_in",
            "console_sign_in",
            "update_app",
        ] {
            let failed = terminal(
                "failed",
                json!({"reason": "provider_error", "next_step": word}),
            );
            assert_eq!(sent_snapshot(failed)["next_step"], word);
        }
        for word in [
            "cli_not_found",
            "home_in_git_project",
            "home_unavailable",
            "probe_start_failed",
            "probe_timed_out",
            "probe_output_unreadable",
            "probe_cleanup_unconfirmed",
            "status_read_failed",
            "status_unreadable",
            "status_context_unavailable",
        ] {
            let failed = terminal(
                "failed",
                json!({"reason": "provider_error", "status_cause": word}),
            );
            assert_eq!(sent_snapshot(failed)["status_cause"], word);
        }
    }

    #[test]
    fn a_cause_outside_the_closed_words_or_off_a_terminal_failure_is_a_protocol_failure() {
        for invalid in [
            terminal("failed", json!({"cause": "raw provider output"})),
            terminal("failed", json!({"cause": "probe_timed_out"})),
            terminal("failed", json!({"next_step": "reboot"})),
            terminal("failed", json!({"status_cause": "timed_out"})),
            terminal("failed", json!({"status_cause": "raw output"})),
            terminal("succeeded", json!({"cause": "timed_out"})),
            terminal("succeeded", json!({"next_step": "retry"})),
            terminal("succeeded", json!({"status_cause": "probe_timed_out"})),
            terminal("started", json!({"cause": "timed_out"})),
            terminal("browser_action", json!({"next_step": "retry"})),
            terminal("starting", json!({"status_cause": "probe_timed_out"})),
        ] {
            assert_eq!(
                sign_in_failure(sign_in_snapshot(success(invalid.clone()), None, None))["code"],
                "read_failed",
                "{invalid}"
            );
        }
    }

    #[test]
    fn a_cli_lane_may_say_why_its_state_is_unconfirmed_and_a_web_api_never() {
        let mut unconfirmed = cli();
        unconfirmed["cli_state"] = json!("unknown");
        unconfirmed["cli_state_cause"] = json!("probe_timed_out");
        unconfirmed["next_step"] = json!("console_sign_in");
        let read = status_of(&[unconfirmed]);
        assert_eq!(read.providers[0].cli_state, Some(CliState::Unknown));
        assert_eq!(
            read.providers[0].cli_state_cause,
            Some(CliStateCause::ProbeTimedOut)
        );
        assert_eq!(read.providers[0].next_step, Some(NextStep::ConsoleSignIn));
        let sent = serde_json::to_value(&read).unwrap();
        assert_eq!(sent["providers"][0]["cli_state_cause"], "probe_timed_out");
        assert_eq!(sent["providers"][0]["next_step"], "console_sign_in");

        // Absent stays absent.
        let sent = serde_json::to_value(status_of(&[cli()])).unwrap();
        assert!(sent["providers"][0].get("cli_state_cause").is_none());
        assert!(sent["providers"][0].get("next_step").is_none());

        let mut api_with_cause = api();
        api_with_cause["cli_state_cause"] = json!("probe_timed_out");
        let mut api_with_step = api();
        api_with_step["next_step"] = json!("retry");
        let mut step_without_cause = cli();
        step_without_cause["next_step"] = json!("retry");
        let mut unknown_cause = cli();
        unknown_cause["cli_state_cause"] = json!("raw output");
        let mut unknown_step = cli();
        unknown_step["cli_state_cause"] = json!("probe_timed_out");
        unknown_step["next_step"] = json!("reboot");
        let mut helper_word = cli();
        helper_word["cli_state_cause"] = json!("timed_out");
        for entry in [
            api_with_cause,
            api_with_step,
            step_without_cause,
            unknown_cause,
            unknown_step,
            helper_word,
        ] {
            assert_eq!(
                failed(status(success(envelope(std::slice::from_ref(&entry)))))["code"],
                "read_failed",
                "{entry}"
            );
        }
    }

    #[test]
    fn the_console_sign_in_command_is_one_bounded_printable_template_with_a_provider_slot() {
        let served = "cadrumo-agent-service provider-login --provider {provider}";
        let mut answer = envelope(&[cli()]);
        answer["console_sign_in_command"] = json!(served);
        let read = status(success(answer)).unwrap();
        assert_eq!(read.console_sign_in_command.as_deref(), Some(served));
        let sent = serde_json::to_value(&read).unwrap();
        assert_eq!(sent["console_sign_in_command"], served);

        // Absent stays absent, for a service that does not serve it.
        let read = status_of(&[cli()]);
        assert!(read.console_sign_in_command.is_none());
        assert!(
            serde_json::to_value(&read)
                .unwrap()
                .get("console_sign_in_command")
                .is_none()
        );

        let long = format!("aeat {} {{provider}}", "x".repeat(300));
        for refused in [
            "",
            "cadrumo-agent-service provider-login",
            "aeat {provider} {provider}",
            "aeat /usr/bin/x {provider}",
            "aeat C:\\x {provider}",
            "aeat\n{provider}",
            long.as_str(),
        ] {
            let mut answer = envelope(&[cli()]);
            answer["console_sign_in_command"] = json!(refused);
            assert_eq!(
                failed(status(success(answer)))["code"],
                "read_failed",
                "{refused:?}"
            );
        }
        let mut answer = envelope(&[cli()]);
        answer["console_sign_in_command"] = json!(7);
        assert_eq!(failed(status(success(answer)))["code"], "read_failed");
    }

    #[test]
    fn sign_in_method_and_attempt_identifiers_have_closed_forms() {
        assert_eq!(SignInMethod::parse("browser"), Some(SignInMethod::Browser));
        assert_eq!(SignInMethod::parse("device"), Some(SignInMethod::Device));
        assert_eq!(
            SignInMethod::parse("browser-code"),
            Some(SignInMethod::BrowserCode)
        );
        for method in ["", "Browser", "terminal", "browser "] {
            assert_eq!(SignInMethod::parse(method), None);
        }
        assert!(is_attempt_id("123e4567-e89b-42d3-a456-426614174000"));
        for attempt in [
            "123E4567-E89B-42D3-A456-426614174000",
            "123e4567e89b42d3a456426614174000",
            "x23e4567-e89b-42d3-a456-426614174000",
            "123e4567-e89b-42d3-a456-42661417400g",
        ] {
            assert!(!is_attempt_id(attempt), "{attempt}");
        }
    }

    #[test]
    fn a_field_the_contract_does_not_name_is_not_forwarded() {
        let mut entry = api();
        entry["secret"] = json!("sk-must-not-travel");
        entry["fingerprint"] = json!("abcd");
        let sent = serde_json::to_string(&status_of(&[entry])).unwrap();
        assert!(!sent.contains("sk-must-not-travel") && !sent.contains("fingerprint"));
    }

    #[test]
    fn a_change_answers_with_the_providers_new_entry_and_only_that_provider() {
        let entry = changed(success(api()), "alpha_api").unwrap();
        assert_eq!(entry.id, "alpha_api");
        assert_eq!(
            failed(changed(success(api()), "gamma_api"))["code"],
            "read_failed"
        );
        assert_eq!(
            failed(changed(success(json!({"id": "alpha_api"})), "alpha_api"))["code"],
            "read_failed"
        );
        assert_eq!(
            failed(changed(success(envelope(&[api()])), "alpha_api"))["code"],
            "read_failed"
        );
    }

    #[test]
    fn a_refusal_in_a_result_is_a_typed_failure_whose_code_is_the_refusal() {
        for code in [
            "not_signed_in",
            "profile_locked",
            "invalid_key_format",
            "base_url_rejected",
            "revision_conflict",
            "committed_readback_failed",
            "catalog_unavailable",
            "runtime_unavailable",
            "person_act_required",
            "unknown",
        ] {
            let refused = json!({"refused": code});
            assert_eq!(
                failed(changed(success(refused.clone()), "alpha_api")),
                json!({"code": code})
            );
            assert_eq!(failed(status(success(refused))), json!({"code": code}));
        }
    }

    #[test]
    fn a_refusal_that_is_not_in_the_closed_set_or_not_alone_is_a_protocol_failure() {
        for refused in [
            json!({"refused": "teapot"}),
            json!({"refused": "NOT_SIGNED_IN"}),
            json!({"refused": ""}),
            json!({"refused": null}),
            json!({"refused": 7}),
            json!({"refused": ["unknown"]}),
            json!({"refused": "unknown", "id": "alpha_api"}),
        ] {
            assert_eq!(
                failed(changed(success(refused.clone()), "alpha_api"))["code"],
                "read_failed",
                "{refused}"
            );
            assert_eq!(
                failed(status(success(refused.clone())))["code"],
                "read_failed",
                "{refused}"
            );
        }
    }

    #[test]
    fn a_refusal_envelope_keeps_its_code_when_the_code_is_one_of_the_set() {
        use crate::shell::sign_in::wire::Refusal as Row;
        let row = |code: &str| Outcome::Refused {
            refusal: Row {
                code: code.into(),
                retry_after_seconds: None,
            },
        };
        assert_eq!(
            failed(status(row("profile_locked"))),
            json!({"code": "profile_locked"})
        );
        assert_eq!(
            failed(changed(row("revision_conflict"), "alpha_api")),
            json!({"code": "revision_conflict"})
        );
        assert_eq!(
            failed(status(row("catalog_unavailable"))),
            json!({"code": "catalog_unavailable"})
        );
        assert_eq!(
            failed(changed(row("catalog_unavailable"), "alpha_api")),
            json!({"code": "catalog_unavailable"})
        );
        // No runtime took the request: the command line's own preflight and the
        // provider bridge both name it with the same closed code.
        assert_eq!(
            failed(status(row("runtime_unavailable"))),
            json!({"code": "runtime_unavailable"})
        );
        assert_eq!(
            failed(changed(row("runtime_unavailable"), "alpha_api")),
            json!({"code": "runtime_unavailable"})
        );
        // A code the contract does not list is not guessed at.
        for code in [
            "runtime_draining",
            "THROTTLED",
            "ERROR_CALCULATIONS_REGISTRY",
        ] {
            assert_eq!(failed(status(row(code)))["code"], "read_failed", "{code}");
        }
    }

    #[test]
    fn an_ordinary_host_failure_keeps_the_hosts_own_code() {
        let failure: CommandFailure =
            ApplicationError::new(ErrorCode::OutputLimit, Operation::Cli).into();
        let sent = serde_json::to_value(failure).unwrap();
        assert_eq!(sent["code"], "output_limit");
        assert_eq!(sent["operation"], "cli");
    }

    #[test]
    fn identifiers_and_revisions_are_safe_command_line_words() {
        for id in ["alpha_api", "beta", "gamma", "p1", "delta_api"] {
            assert!(is_provider_id(id), "{id}");
        }
        let long = "a".repeat(41);
        for id in [
            "",
            "A",
            "1x",
            "_x",
            "-x",
            "x y",
            "x-y",
            "x.y",
            "é",
            "x\0",
            long.as_str(),
        ] {
            assert!(!is_provider_id(id), "{id:?}");
        }
        let longest = "a".repeat(128);
        let over = "a".repeat(129);
        for revision in ["absent", &"0".repeat(64), "r.1:2_3-4", longest.as_str()] {
            assert!(is_revision(revision), "{revision}");
        }
        for revision in [
            "",
            "-a",
            "a b",
            "a%",
            "a$",
            "a*",
            "a?",
            "a[",
            "a/",
            "é",
            over.as_str(),
        ] {
            assert!(!is_revision(revision), "{revision:?}");
        }
    }
}
