//! Short-lived canonical CLI invocations. No runtime connection or credential is retained.
mod observation;
mod reads;
// The child runner and the envelope decoder are also the provider settings'
// channel: one set of lanes, one deadline, one output bound, one settlement.
pub(crate) mod process;
pub(crate) mod wire;
use observation::{
    __cmd__sign_in_subscribe, __cmd__sign_in_unsubscribe, __tauri_command_name_sign_in_subscribe,
    __tauri_command_name_sign_in_unsubscribe, sign_in_subscribe, sign_in_unsubscribe,
};

use crate::environment::Launch;
use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    diagnostics::helper::{HelperExecutable, HelperIdentity},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    package::PackageManifest,
    value::RelativePath,
};
use serde::Deserialize;
use std::{collections::BTreeMap, sync::Arc};
use tauri::{
    State,
    http::HeaderMap,
    ipc::{InvokeBody, Request},
};
use zeroize::Zeroizing;

use process::Children;
pub(crate) use wire::Presence;
use wire::{ProfileCreateResult, ProfileList, SignInResult, SignInStatus, SignOutResult};

/// The header that names a profile by its label, percent-encoded as UTF-8:
/// a header carries no other text, and the body is the password alone.
const PROFILE_HEADER: &str = "x-cadrumo-profile";
/// The product's own bound on a profile label, in characters.
const LABEL_LIMIT: usize = 160;
/// Characters the product's command line rewrites in an argument on Windows,
/// after the option terminator too: it expands environment variables and
/// file-name patterns before it reads its arguments. Asked directly, a
/// package created `%USERNAME% y Cia` as the user's name followed by "y Cia"
/// and `Taller [2025]` as the name of a file beside it. A label holding one
/// would name another profile, so it is not passed at all.
pub(crate) const REWRITTEN: [char; 5] = ['*', '?', '[', '%', '$'];

/// One command under `config`: its words, the name its answer must carry,
/// whether it only reads, its owning image, and its enrollment deadline.
struct Call {
    words: &'static [&'static str],
    leaf: &'static str,
    reads: bool,
    runtime: bool,
    slow: bool,
    command: &'static str,
}
const STATUS: Call = Call {
    words: &["sign-in-status"],
    leaf: "sign-in-status",
    command: "config.sign-in-status",
    reads: true,
    runtime: true,
    slow: false,
};
const LOGIN: Call = Call {
    words: &["login"],
    leaf: "login",
    command: "config.login",
    reads: false,
    runtime: false,
    slow: false,
};
const LOGOUT: Call = Call {
    words: &["logout"],
    leaf: "logout",
    command: "config.logout",
    reads: false,
    runtime: false,
    slow: false,
};
const LIST: Call = Call {
    words: &["profile", "list"],
    leaf: "profile.list",
    command: "config.profile.list",
    reads: true,
    runtime: false,
    slow: false,
};
const CREATE: Call = Call {
    words: &["profile", "create", "--quiet"],
    leaf: "profile.create",
    command: "config.profile.create",
    reads: false,
    runtime: false,
    slow: true,
};

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Cli)
}

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
}
#[derive(Deserialize)]
struct Layout {
    paths: Paths,
    files: Files,
    entrypoints: BTreeMap<String, String>,
    entrypoint_suffix: String,
}
#[derive(Deserialize)]
struct Paths {
    native: RelativePath,
}
#[derive(Deserialize)]
struct Files {
    package_manifest: RelativePath,
}

pub struct SignIn {
    child: Result<ChildConfiguration>,
    runtime: Result<ChildConfiguration>,
    service: Result<ChildConfiguration>,
    pub children: Children,
    observation: observation::Observer,
    reads: Arc<reads::Reads>,
}

impl SignIn {
    pub fn new(launch: &Launch) -> Self {
        Self {
            child: resolve_cli(launch),
            runtime: resolve_image(launch, "cadrumo-runtime"),
            service: resolve_image(launch, "cadrumo-agent-service"),
            children: Children::new(launch.diagnostics.clone()),
            observation: observation::Observer::default(),
            reads: Arc::new(reads::Reads::default()),
        }
    }

    pub(crate) fn runtime(&self) -> Result<ChildConfiguration> {
        self.runtime.clone()
    }
    pub(crate) fn service(&self) -> Result<ChildConfiguration> {
        self.service.clone()
    }

    pub(crate) fn profile_id(&self, label: &str) -> Result<String> {
        let wire::Outcome::Success {
            result,
            active_profile,
        } = self.run(&STATUS, None, None)?
        else {
            return Err(failure(ErrorCode::ReadFailed));
        };
        if active_profile.as_deref() != Some(label) {
            return Err(failure(ErrorCode::ReadFailed));
        }
        let id = result
            .get("profile_id")
            .and_then(serde_json::Value::as_str)
            .filter(|id| super::agent_access::wire::is_uuid(id))
            .ok_or_else(|| failure(ErrorCode::ReadFailed))?;
        Ok(id.to_owned())
    }

    pub(crate) async fn read_status(self: &Arc<Self>) -> Result<SignInStatus> {
        if !supported() {
            return Ok(SignInStatus::unsupported());
        }
        let state = self.clone();
        self.reads
            .read(move || async move {
                super::blocking(move || wire::status(state.run(&STATUS, None, None)?)).await
            })
            .await
    }

    pub async fn stop(&self) -> Result<()> {
        self.observation.close();
        let result = self.children.stop();
        let joined = self.observation.join().await;
        result?;
        joined
    }

    fn run(
        &self,
        call: &Call,
        label: Option<&str>,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<wire::Outcome> {
        wire::decode(call.leaf, &self.output(call, label, secret)?)
    }

    fn output(
        &self,
        call: &Call,
        label: Option<&str>,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<process::Output> {
        let _mutation = (!call.reads).then(|| self.reads.mutation());
        let image = if call.runtime {
            &self.runtime
        } else {
            &self.child
        };
        let mut command = image.as_ref().map_err(Clone::clone)?.command();
        command.args(arguments(call, label, secret.is_some()));
        let identity = HelperIdentity {
            command: call.command,
            executable: if call.runtime {
                HelperExecutable::Runtime
            } else {
                HelperExecutable::Cli
            },
        };
        if call.reads {
            self.children.read(identity, command)
        } else if call.slow {
            self.children
                .run_within(identity, command, secret, process::CREATION_DEADLINE)
        } else {
            self.children.run(identity, command, secret)
        }
    }
}

/// The arguments of one call. A label is the person's own text: it follows
/// the option terminator, so that none of it is read as an option.
fn arguments(call: &Call, label: Option<&str>, secret: bool) -> Vec<String> {
    let mut arguments: Vec<String> = ["--format", "json", "config"]
        .iter()
        .chain(call.words)
        .map(|word| (*word).to_owned())
        .collect();
    if secret {
        arguments.push("--secrets-stdin".to_owned());
    }
    if let Some(label) = label {
        arguments.push("--".to_owned());
        arguments.push(label.to_owned());
    }
    arguments
}

fn resolve_cli(launch: &Launch) -> Result<ChildConfiguration> {
    resolve_image(launch, "aeat")
}

fn resolve_image(launch: &Launch, entrypoint: &str) -> Result<ChildConfiguration> {
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let layout = contract.layout;
    if !layout.entrypoints.contains_key(entrypoint) {
        return Err(failure(ErrorCode::PackageUnavailable));
    }
    let relative = RelativePath::new(format!(
        "{}/{}{}",
        layout.paths.native.as_str(),
        entrypoint,
        layout.entrypoint_suffix
    ))
    .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let manifest = PackageManifest::read(&launch.package_root, &layout.files.package_manifest)
        .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let digest = manifest
        .files
        .get(&relative)
        .ok_or_else(|| failure(ErrorCode::PackageUnavailable))?;
    let executable = relative.under(&launch.package_root);
    binary::verify(
        &executable,
        digest,
        BinaryExpectation::host().map_err(|_| failure(ErrorCode::PackageUnavailable))?,
    )
    .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    ChildConfiguration::new(
        executable,
        launch.working_directory.clone(),
        launch.child.environment().clone(),
    )
    .map_err(|_| failure(ErrorCode::EnvironmentFailed))
}

// The CLI currently exposes no GNOME binding capability. Until that projection
// exists, non-Windows hosts must not claim a positively observed login binding.
fn supported() -> bool {
    cfg!(windows)
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        sign_in_status,
        sign_in_subscribe,
        sign_in_unsubscribe,
        sign_in_submit,
        sign_out,
        profile_list,
        profile_create
    ]
}

#[tauri::command]
pub async fn sign_in_status(
    state: State<'_, Arc<SignIn>>,
    manager: State<'_, Arc<crate::manager::ManagerStart>>,
) -> Result<SignInStatus> {
    if !supported() {
        return Ok(SignInStatus::unsupported());
    }
    // Dispatch completion is not runtime readiness. The canonical CLI below
    // remains the only authority on availability and authentication.
    let started = manager.start(false).await;
    status_after_manager(started, state.inner().read_status().await)
}

fn status_after_manager(
    started: Result<crate::manager::StartOutcome>,
    observed: Result<SignInStatus>,
) -> Result<SignInStatus> {
    let status = observed?;
    // A working runtime remains authoritative even if manager dispatch failed.
    // When it is unavailable, retain the preceding startup failure as the cause.
    if !status.runtime_available {
        started?;
    }
    Ok(status)
}

#[tauri::command]
pub async fn sign_in_submit(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> Result<SignInResult> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform));
    }
    // Named, the profile is the one signed in to; unnamed, the product's
    // selected one is.
    let profile = label(request.headers())?;
    let secret = secret(request.body())?;
    let state = state.inner().clone();
    super::blocking(move || wire::login(state.run(&LOGIN, profile.as_deref(), Some(secret))?)).await
}

/// The profiles on this computer, by label. It needs no password, session or
/// runtime, and it changes nothing.
#[tauri::command]
pub async fn profile_list(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<ProfileList, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let state = state.inner().clone();
    let output = super::blocking(move || state.output(&LIST, None, None)).await?;
    wire::profiles(&output)
}

/// Creates a profile under the label in the header, with the password in the
/// raw body. One attempt: nothing is retried, and the new profile is left
/// signed out, as the product leaves it.
#[tauri::command]
pub async fn profile_create(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> Result<ProfileCreateResult> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform));
    }
    let name = label(request.headers())?.ok_or_else(|| failure(ErrorCode::InvalidArguments))?;
    let secret = confirmed_secret(request.body())?;
    let state = state.inner().clone();
    super::blocking(move || wire::created(state.run(&CREATE, Some(&name), Some(secret))?)).await
}

#[tauri::command]
pub async fn sign_out(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<SignOutResult, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let state = state.inner().clone();
    let outcome = super::blocking(move || state.run(&LOGOUT, None, None)).await?;
    wire::logout(outcome)
}

/// The label a call names, or none. Refused unless it is text the product
/// could hold as a label and its command line would read as written: within
/// the bound, without surrounding space or control characters, not led by a
/// hyphen, which is read as an option, nor by a tilde, which is read as a
/// home directory, and free of the characters the command line rewrites.
fn label(headers: &HeaderMap) -> Result<Option<String>> {
    let invalid = || failure(ErrorCode::InvalidArguments);
    let Some(value) = headers.get(PROFILE_HEADER) else {
        return Ok(None);
    };
    let mut rest = value.to_str().map_err(|_| invalid())?.as_bytes();
    let mut bytes = Vec::with_capacity(rest.len());
    while let [first, tail @ ..] = rest {
        if *first == b'%' {
            let [high, low, after @ ..] = tail else {
                return Err(invalid());
            };
            let digit = |byte: u8| char::from(byte).to_digit(16).ok_or_else(invalid);
            bytes.push(u8::try_from(digit(*high)? * 16 + digit(*low)?).map_err(|_| invalid())?);
            rest = after;
        } else {
            bytes.push(*first);
            rest = tail;
        }
    }
    let label = String::from_utf8(bytes).map_err(|_| invalid())?;
    let length = label.chars().count();
    if length == 0
        || length > LABEL_LIMIT
        || label != label.trim()
        || label.starts_with('-')
        || label.starts_with('~')
        || label
            .chars()
            .any(|c| c.is_control() || REWRITTEN.contains(&c))
    {
        return Err(invalid());
    }
    Ok(Some(label))
}

fn secret(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
    encoded(body, false)
}

/// The secret of a creation: the one password the person confirmed in the
/// window, as the password and its confirmation.
fn confirmed_secret(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
    encoded(body, true)
}

fn encoded(body: &InvokeBody, confirmed: bool) -> Result<Zeroizing<Vec<u8>>> {
    let InvokeBody::Raw(bytes) = body else {
        return Err(failure(ErrorCode::InvalidArguments));
    };
    if bytes.len() > 8192 {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    let password = std::str::from_utf8(bytes).map_err(|_| failure(ErrorCode::InvalidArguments))?;
    // Serialize borrowed text directly into the one owned, wipe-on-drop buffer.
    // The transport-owned Request bytes remain Tauri's unwipeable copy.
    #[derive(serde::Serialize)]
    struct Payload<'a> {
        passphrase: &'a str,
        #[serde(skip_serializing_if = "Option::is_none")]
        passphrase_confirmation: Option<&'a str>,
    }
    let mut encoded = Zeroizing::new(Vec::with_capacity(8192 * 12 + 64));
    serde_json::to_writer(
        &mut *encoded,
        &Payload {
            passphrase: password,
            passphrase_confirmation: confirmed.then_some(password),
        },
    )
    .map_err(|_| failure(ErrorCode::InvalidArguments))?;
    if encoded.len() > 8192 {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    Ok(encoded)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn status_observation(available: bool) -> Result<SignInStatus> {
        wire::status(if available {
            wire::Outcome::Success {
                result: serde_json::json!({"status":{"presence":"absent"}}),
                active_profile: Some("Test profile".into()),
            }
        } else {
            wire::Outcome::Refused {
                refusal: wire::Refusal {
                    code: "runtime_unavailable".into(),
                    retry_after_seconds: None,
                },
                active_profile: Some("Test profile".into()),
            }
        })
    }

    #[test]
    fn unavailable_runtime_preserves_the_preceding_manager_failure_and_safe_context() {
        let denied = if cfg!(windows) { 5 } else { 13 };
        let error = ApplicationError::new(ErrorCode::ManagerDispatchFailed, Operation::Manager)
            .caused_by(std::io::Error::from_raw_os_error(denied));
        let failure = status_after_manager(Err(error), status_observation(false)).unwrap_err();
        let document = serde_json::to_value(failure).unwrap();
        assert_eq!(document["code"], "manager_dispatch_failed");
        assert_eq!(document["operation"], "manager");
        assert_eq!(document["ioKind"], "PermissionDenied");
        assert_eq!(document["osCode"], denied);

        let private = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Manager)
            .caused_by(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                "private installation path and exception payload",
            ));
        let failure = status_after_manager(Err(private), status_observation(false)).unwrap_err();
        let document = serde_json::to_value(failure).unwrap();
        assert_eq!(document["code"], "package_unavailable");
        assert_eq!(document["operation"], "manager");
        assert_eq!(document["ioKind"], "NotFound");
        assert!(!document.to_string().contains("private"));
    }

    #[test]
    fn a_working_runtime_remains_available_after_a_manager_dispatch_failure() {
        let failure = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Manager);
        let status = status_after_manager(Err(failure), status_observation(true)).unwrap();
        assert!(status.runtime_available);
        assert_eq!(status.state, wire::Presence::Absent);
        assert_eq!(status.active_profile.as_deref(), Some("Test profile"));
        assert!(status.refusal.is_none());
    }

    #[test]
    fn successful_or_unsupported_dispatch_never_claims_runtime_readiness() {
        fn check(outcome: crate::manager::StartOutcome) {
            let status = status_after_manager(Ok(outcome), status_observation(false)).unwrap();
            assert!(!status.runtime_available);
            assert_eq!(status.refusal.unwrap().code, "runtime_unavailable");
        }
        check(crate::manager::StartOutcome::Dispatched);
        #[cfg(not(windows))]
        check(crate::manager::StartOutcome::Unsupported);
    }

    #[test]
    fn an_unreadable_cli_status_retains_its_own_failure() {
        let manager = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Manager);
        let cli = ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli);
        let failure = status_after_manager(Err(manager), Err(cli)).unwrap_err();
        assert_eq!(failure.code, ErrorCode::ReadFailed);
        assert_eq!(failure.operation, Operation::Cli);
    }

    #[test]
    fn secret_is_raw_utf8_and_bounded_after_json_encoding() {
        let encoded = secret(&InvokeBody::Raw("á\"\n漢".as_bytes().to_vec())).unwrap();
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&encoded).unwrap(),
            serde_json::json!({"passphrase":"á\"\n漢"})
        );
        for body in [
            InvokeBody::Json(serde_json::json!([97])),
            InvokeBody::Raw(vec![255]),
            InvokeBody::Raw(vec![b'\n'; 8192]),
        ] {
            assert_eq!(secret(&body).unwrap_err().code, ErrorCode::InvalidArguments);
        }
    }

    #[test]
    fn a_creation_sends_the_one_password_as_itself_and_its_confirmation() {
        let encoded = confirmed_secret(&InvokeBody::Raw("á\"\n漢".as_bytes().to_vec())).unwrap();
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&encoded).unwrap(),
            serde_json::json!({"passphrase":"á\"\n漢","passphrase_confirmation":"á\"\n漢"})
        );
        // Twice the text must still fit the product's one bounded read.
        assert_eq!(
            confirmed_secret(&InvokeBody::Raw(vec![b'x'; 4096]))
                .unwrap_err()
                .code,
            ErrorCode::InvalidArguments
        );
        assert!(confirmed_secret(&InvokeBody::Raw(vec![b'x'; 1024])).is_ok());
    }

    fn named(value: &str) -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(PROFILE_HEADER, value.parse().unwrap());
        headers
    }

    #[test]
    fn a_label_is_percent_encoded_utf8_and_absent_when_unnamed() {
        assert_eq!(label(&HeaderMap::new()).unwrap(), None);
        for (sent, read) in [
            ("Demo%20profile", "Demo profile"),
            ("Taller%20Ribera%2C%20S.L.", "Taller Ribera, S.L."),
            ("%E6%BC%A2%C3%A1", "漢á"),
            ("Ana-Maria", "Ana-Maria"),
            (
                "Ana%7EMaria%20%26%20Hijos%20%282025%29",
                "Ana~Maria & Hijos (2025)",
            ),
        ] {
            assert_eq!(
                label(&named(sent)).unwrap().as_deref(),
                Some(read),
                "{sent}"
            );
        }
        let longest = "x".repeat(LABEL_LIMIT);
        assert_eq!(label(&named(&longest)).unwrap().as_deref(), Some(&*longest));
    }

    #[test]
    fn a_label_the_product_could_not_hold_or_would_read_as_an_option_is_refused() {
        let long = "x".repeat(LABEL_LIMIT + 1);
        for sent in [
            "",
            "%20",
            "%20Ana",
            "Ana%20",
            "-Ana",
            "--help",
            "%2D%2Dquiet",
            "Ana%0ASoler",
            "Ana%00",
            "%",
            "%4",
            "%zz",
            "%FF",
            "%E6%BC",
            long.as_str(),
            // What the command line would rewrite into another label.
            "%25USERNAME%25%20y%20Cia",
            "Rebajas%2050%25",
            "Caja%20%24USERNAME",
            "Taller%20%5B2025%5D",
            "Todo%2A",
            "Cu%C3%A1l%3F",
            "~",
            "%7Eana",
        ] {
            assert_eq!(
                label(&named(sent)).unwrap_err().code,
                ErrorCode::InvalidArguments,
                "{sent:?}"
            );
        }
    }

    #[test]
    fn a_label_follows_the_option_terminator_and_fixed_words_precede_it() {
        assert_eq!(
            arguments(&LOGIN, Some("Demo profile"), true),
            [
                "--format",
                "json",
                "config",
                "login",
                "--secrets-stdin",
                "--",
                "Demo profile"
            ]
        );
        assert_eq!(
            arguments(&LOGIN, None, true),
            ["--format", "json", "config", "login", "--secrets-stdin"]
        );
        assert_eq!(
            arguments(&CREATE, Some("Ana"), true),
            [
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "--quiet",
                "--secrets-stdin",
                "--",
                "Ana"
            ]
        );
        assert_eq!(
            arguments(&LIST, None, false),
            ["--format", "json", "config", "profile", "list"]
        );
        assert_eq!(
            arguments(&STATUS, None, false),
            ["--format", "json", "config", "sign-in-status"]
        );
        assert_eq!(
            arguments(&LOGOUT, None, false),
            ["--format", "json", "config", "logout"]
        );
    }

    // What the fixtures assert of the product's models, asked of a real
    // package: its command line lists, creates and refuses as the window
    // expects. The profiles go to storage of this test's own, under the
    // run's, so no other live test meets them.
    #[cfg(feature = "live-package-tests")]
    #[tokio::test]
    async fn a_real_package_lists_creates_and_refuses_profiles_as_the_window_expects() {
        use crate::environment::{Parent, resolve};
        use cadrumo_application::diagnostics::Diagnostics;
        use std::path::PathBuf;

        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let mut parent = Parent::current().unwrap();
        let shared = resolve(root.clone(), &parent, Arc::new(Diagnostics::default()))
            .await
            .unwrap()
            .working_directory;
        let own = shared.join(format!("sign-in-profiles-{}", std::process::id()));
        std::fs::create_dir_all(&own).unwrap();
        let mut pinned = 0;
        for (_, value) in &mut parent.environment {
            if std::path::Path::new(&*value) == shared {
                *value = own.clone().into_os_string();
                pinned += 1;
            }
        }
        assert_eq!(pinned, 1, "the run names its storage root once");
        let launch = resolve(root, &parent, Arc::new(Diagnostics::default()))
            .await
            .unwrap();
        assert_eq!(launch.working_directory, own);
        let state = SignIn::new(&launch);

        let listed = |state: &SignIn| {
            serde_json::to_value(
                wire::profiles(&state.output(&LIST, None, None).unwrap())
                    .ok()
                    .unwrap(),
            )
            .unwrap()
        };
        let password =
            || confirmed_secret(&InvokeBody::Raw(b"Live-test-password-1".to_vec())).unwrap();
        let create = |state: &SignIn, name: &str| {
            serde_json::to_value(
                wire::created(state.run(&CREATE, Some(name), Some(password())).unwrap()).unwrap(),
            )
            .unwrap()
        };

        assert_eq!(
            listed(&state),
            serde_json::json!({"profiles": [], "complete": true})
        );
        let first = "Perfil de prueba á漢";
        assert_eq!(
            create(&state, first),
            serde_json::json!({"kind": "created", "name": first})
        );
        assert_eq!(
            listed(&state),
            serde_json::json!({"profiles": [{"name": first, "active": true}], "complete": true})
        );
        // The same label in another case is the same label to the product.
        assert_eq!(
            create(&state, "PERFIL de prueba á漢"),
            serde_json::json!({
                "kind": "refused", "code": "profile_already_exists", "retryAfterSeconds": null
            })
        );
        // A second profile is the one selected once it exists. Its label
        // holds what a command line is most often wrong about: quotes,
        // spaces, an ampersand, and a backslash at its very end.
        let second = r#"Segundo "el nuevo" & Cía (2026) \"#;
        assert_eq!(
            create(&state, second),
            serde_json::json!({"kind": "created", "name": second})
        );
        assert_eq!(
            listed(&state),
            serde_json::json!({
                "profiles": [
                    {"name": first, "active": false},
                    {"name": second, "active": true}
                ],
                "complete": true
            })
        );
        // A sign-in that names a profile reaches the product's login for
        // that label: with no runtime behind this storage it is refused for
        // that, and not as a call the command line could not read.
        let login = serde_json::to_value(
            wire::login(
                state
                    .run(
                        &LOGIN,
                        Some(first),
                        Some(secret(&InvokeBody::Raw(b"Live-test-password-1".to_vec())).unwrap()),
                    )
                    .unwrap(),
            )
            .unwrap(),
        )
        .unwrap();
        assert_eq!(
            login,
            serde_json::json!({
                "kind": "refused", "code": "runtime_unavailable", "retryAfterSeconds": null
            })
        );
        // Signing in did not happen, so the selection is where creation left it.
        assert_eq!(listed(&state)["profiles"][1]["active"], true);
    }
}
