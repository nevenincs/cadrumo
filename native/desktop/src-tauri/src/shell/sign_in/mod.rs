//! Short-lived canonical CLI invocations. No runtime connection or credential is retained.
mod process;
mod wire;

use crate::environment::Launch;
use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
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
use wire::{ProfileCreateResult, ProfileList, SignInResult, SignInStatus, SignOutResult};

/// The header that names a profile by its label, percent-encoded as UTF-8:
/// a header carries no other text, and the body is the password alone.
const PROFILE_HEADER: &str = "x-cadrumo-profile";
/// The product's own bound on a profile label, in characters.
const LABEL_LIMIT: usize = 160;

/// One command under `config`: its words, the name its answer must carry,
/// and whether it only reads.
struct Call {
    words: &'static [&'static str],
    leaf: &'static str,
    reads: bool,
}
const STATUS: Call = Call {
    words: &["sign-in-status"],
    leaf: "sign-in-status",
    reads: true,
};
const LOGIN: Call = Call {
    words: &["login"],
    leaf: "login",
    reads: false,
};
const LOGOUT: Call = Call {
    words: &["logout"],
    leaf: "logout",
    reads: false,
};
const LIST: Call = Call {
    words: &["profile", "list"],
    leaf: "profile.list",
    reads: true,
};
const CREATE: Call = Call {
    words: &["profile", "create", "--quiet"],
    leaf: "profile.create",
    reads: false,
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
    pub children: Children,
}

impl SignIn {
    pub fn new(launch: &Launch) -> Self {
        Self {
            child: resolve_cli(launch),
            children: Children::default(),
        }
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
        let mut command = self.child.as_ref().map_err(Clone::clone)?.command();
        command.args(arguments(call, label, secret.is_some()));
        if call.reads {
            self.children.read(command)
        } else {
            self.children.run(command, secret)
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
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let layout = contract.layout;
    if !layout.entrypoints.contains_key("aeat") {
        return Err(failure(ErrorCode::PackageUnavailable));
    }
    let relative = RelativePath::new(format!(
        "{}/aeat{}",
        layout.paths.native.as_str(),
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
        sign_in_submit,
        sign_out,
        profile_list,
        profile_create
    ]
}

#[tauri::command]
pub async fn sign_in_status(state: State<'_, Arc<SignIn>>) -> Result<SignInStatus> {
    if !supported() {
        return Ok(SignInStatus::unsupported());
    }
    let state = state.inner().clone();
    super::blocking(move || wire::status(state.run(&STATUS, None, None)?)).await
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
/// could hold as a label: within its bound, without surrounding space or
/// control characters, and not led by a hyphen, which the command line would
/// read as an option.
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
        || label.chars().any(char::is_control)
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
            ("100%25", "100%"),
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
            if PathBuf::from(&*value) == shared {
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
        // A second profile is the one selected once it exists.
        assert_eq!(
            create(&state, "Segundo, S.L."),
            serde_json::json!({"kind": "created", "name": "Segundo, S.L."})
        );
        assert_eq!(
            listed(&state),
            serde_json::json!({
                "profiles": [
                    {"name": first, "active": false},
                    {"name": "Segundo, S.L.", "active": true}
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
