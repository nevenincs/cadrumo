//! The provider-settings answers, parsed into the closed shapes the contract
//! names. A value outside a closed set is a protocol failure, never passed on.
use crate::shell::sign_in::wire::Outcome;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

const NAME_LIMIT: usize = 100;
const URL_LIMIT: usize = 2048;
const PROVIDER_LIMIT: usize = 64;

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
    Environment,
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

/// One provider as the profile holds it. No field is, or is derived from, a
/// secret; a field the contract does not name is dropped, not forwarded.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Entry {
    pub id: String,
    pub display_name: String,
    pub transport: Transport,
    pub auth_kind: AuthKind,
    pub consumers: Vec<Consumer>,
    pub mode: Mode,
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
    pub revision: String,
}

#[derive(Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Status {
    pub development: bool,
    pub providers: Vec<Entry>,
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
            && is_plain_text(&self.display_name, NAME_LIMIT)
            && is_revision(&self.revision)
            && self
                .base_url
                .iter()
                .chain(&self.default_base_url)
                .all(|url| is_plain_text(url, URL_LIMIT))
            // A provider's own app has a state; a web API has none.
            && (self.transport == Transport::Cli) == self.cli_state.is_some()
            && self.consumers.len() <= 1;
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
    let coherent = status.providers.len() <= PROVIDER_LIMIT
        && status
            .providers
            .iter()
            .all(|entry| seen.insert(entry.id.clone()))
        // The environment is a source in a development build only.
        && (status.development
            || status
                .providers
                .iter()
                .all(|entry| entry.source != Source::Environment));
    if !coherent {
        return Err(protocol().into());
    }
    let providers = status
        .providers
        .into_iter()
        .map(Entry::checked)
        .collect::<Result<_, _>>()?;
    Ok(Status {
        development: status.development,
        providers,
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
    use serde_json::{Value, json};

    fn api() -> Value {
        json!({
            "id": "alpha_api", "display_name": "Alpha API", "transport": "api",
            "auth_kind": "api_key", "consumers": ["assistant"], "mode": "key",
            "available": true, "source": "profile", "readiness": "not_verified",
            "reason": null, "base_url": null, "default_base_url": null,
            "revision": "00ff"
        })
    }

    fn cli() -> Value {
        json!({
            "id": "beta_cli", "display_name": "Beta CLI", "transport": "cli",
            "auth_kind": "provider_sign_in_only", "consumers": ["assistant"],
            "mode": "provider_sign_in", "available": false, "source": "none",
            "readiness": "sign_in_required", "reason": "sign_in_with_provider_tool",
            "cli_state": "installed_signed_out", "revision": "absent"
        })
    }

    fn success(result: Value) -> Outcome {
        Outcome::Success {
            result,
            active_profile: None,
        }
    }

    fn envelope(entries: &[Value]) -> Value {
        json!({"development": false, "providers": entries})
    }

    fn failed(result: Result<impl std::fmt::Debug, CommandFailure>) -> Value {
        serde_json::to_value(result.unwrap_err()).unwrap()
    }

    #[test]
    fn a_status_read_parses_into_the_closed_shapes_and_serializes_as_the_window_reads_it() {
        let status = status(success(envelope(&[api(), cli()]))).unwrap();
        assert!(!status.development);
        assert_eq!(status.providers.len(), 2);
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
        assert_eq!(sent["providers"][0]["reason"], Value::Null);
        // Absent stays absent: a web API has no app state, and an unset URL is not sent.
        assert!(sent["providers"][0].get("cli_state").is_none());
        assert!(sent["providers"][0].get("base_url").is_none());
        assert_eq!(sent["providers"][1]["cli_state"], "installed_signed_out");
        assert_eq!(sent["providers"][1]["auth_kind"], "provider_sign_in_only");
        assert_eq!(status.providers[1].revision, "absent");
        // A listing with nothing in it is a listing.
        assert!(status_of(&[]).providers.is_empty());
    }

    fn status_of(entries: &[Value]) -> Status {
        status(success(envelope(entries))).unwrap()
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
            ("id", json!("Alpha_api")),
            ("id", json!("-x")),
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
            "display_name",
            "transport",
            "auth_kind",
            "consumers",
            "mode",
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
        // The flag is required, and every row must be an object.
        assert!(status(success(json!({"providers": []}))).is_err());
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
    fn the_environment_is_a_source_only_in_a_development_build_and_ids_are_unique() {
        let mut from_environment = api();
        from_environment["source"] = json!("environment");
        let read = json!({"development": true, "providers": [from_environment.clone()]});
        assert_eq!(
            status(success(read)).unwrap().providers[0].source,
            Source::Environment
        );
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
            active_profile: Some("Profile".into()),
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
