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
    ipc::{InvokeBody, Request},
};
use zeroize::Zeroizing;

use process::Children;
use wire::{SignInResult, SignInStatus, SignOutResult};

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

    fn run(&self, leaf: &'static str, secret: Option<Zeroizing<Vec<u8>>>) -> Result<wire::Outcome> {
        let mut command = self.child.as_ref().map_err(Clone::clone)?.command();
        command.args(["--format", "json", "config", leaf]);
        if secret.is_some() {
            command.arg("--secrets-stdin");
        }
        let output = self.children.run(command, secret)?;
        wire::decode(leaf, &output)
    }
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
    crate::app::commands![sign_in_status, sign_in_submit, sign_out]
}

#[tauri::command]
pub async fn sign_in_status(state: State<'_, Arc<SignIn>>) -> Result<SignInStatus> {
    if !supported() {
        return Ok(SignInStatus::unsupported());
    }
    let state = state.inner().clone();
    super::blocking(move || wire::status(state.run("sign-in-status", None)?)).await
}

#[tauri::command]
pub async fn sign_in_submit(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> Result<SignInResult> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform));
    }
    let secret = secret(request.body())?;
    let state = state.inner().clone();
    super::blocking(move || wire::login(state.run("login", Some(secret))?)).await
}

#[tauri::command]
pub async fn sign_out(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<SignOutResult, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let state = state.inner().clone();
    let outcome = super::blocking(move || state.run("logout", None)).await?;
    wire::logout(outcome)
}

fn secret(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
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
    }
    let mut encoded = Zeroizing::new(Vec::with_capacity(8192 * 6 + 32));
    serde_json::to_writer(
        &mut *encoded,
        &Payload {
            passphrase: password,
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
}
