//! The read-only `cadrumo-docs` scheme that serves the packaged user
//! documentation to the shell's documentation frame.

mod policy;
mod request;
mod site;
#[cfg(test)]
mod tests;
mod webview;

use crate::{app::Commands, environment::Launch, shell};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Serialize;
use site::Site;
use std::{
    ffi::OsString,
    path::{Path, PathBuf},
    sync::{Arc, OnceLock},
};
use tauri::{AppHandle, Manager, Runtime, Url, plugin::TauriPlugin};

/// Selects a staged documentation tree in development builds. The tree must
/// carry its own documentation manifest; packaged builds ignore it.
const DEVELOPMENT_ROOT: &str = "CADRUMO_DESKTOP_DOCS_ROOT";

/// The documentation the shell may open: the origin the host serves it on
/// and each language's entry page as a URL on that origin.
#[derive(Clone, Serialize)]
pub struct Published {
    origin: String,
    languages: Vec<Language>,
}

#[derive(Clone, Serialize)]
struct Language {
    code: String,
    entry: String,
}

/// Each entry's URL, its path segments percent-encoded so the scheme
/// handler maps the URL back to the same manifest member.
fn published(site: &Site, origin: &str) -> Result<Published> {
    let refused = || ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview);
    let base = Url::parse(origin).map_err(|e| refused().caused_by(e))?;
    let languages = site
        .entries()
        .iter()
        .map(|(code, path)| {
            let mut entry = base.clone();
            entry
                .path_segments_mut()
                .map_err(|()| refused())?
                .clear()
                .extend(path.as_str().split('/'));
            Ok(Language {
                code: code.clone(),
                entry: entry.into(),
            })
        })
        .collect::<Result<_>>()?;
    Ok(Published {
        origin: origin.to_owned(),
        languages,
    })
}

pub fn plugin<R: Runtime>(launch: &Launch) -> Result<TauriPlugin<R>> {
    let development = std::env::var_os(DEVELOPMENT_ROOT).filter(|_| tauri::is_dev());
    let site = Arc::new(open(
        &launch.package_root,
        &launch.docs_root,
        &launch.docs_manifest,
        development,
    )?);
    let policy = Arc::new(OnceLock::<String>::new());
    let diagnostics = launch.diagnostics.clone();
    let served = site.clone();
    let issued = policy.clone();
    let builder = tauri::plugin::Builder::new("cadrumo-docs")
        .setup(move |app, _| {
            prepare(app, &site, &policy).map_err(|error| {
                diagnostics.failure(error.clone());
                Box::new(error) as Box<dyn std::error::Error>
            })
        })
        .register_asynchronous_uri_scheme_protocol(policy::SCHEME, move |_, request, responder| {
            let site = served.clone();
            let issued = issued.clone();
            // Reads leave the webview's thread; the response may arrive later.
            tauri::async_runtime::spawn_blocking(move || {
                let policy = issued.get().map_or(policy::CLOSED, String::as_str);
                responder.respond(request::respond(&site, policy, &request));
            });
        });
    #[cfg(windows)]
    let builder = {
        let diagnostics = launch.diagnostics.clone();
        builder.on_webview_ready(move |webview| {
            webview::require_interfaces(&webview, diagnostics.clone());
        })
    };
    Ok(builder.build())
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![]
}

/// Admits the packaged tree, or in development the staged tree the override
/// names, refusing when no documentation manifest is present.
fn open(
    package_root: &Path,
    docs_root: &Path,
    docs_manifest: &Path,
    development: Option<OsString>,
) -> Result<Site> {
    let Some(override_root) = development.filter(|value| !value.is_empty()) else {
        if !docs_root.starts_with(package_root) {
            return Err(site::unavailable());
        }
        return Site::open(docs_root, docs_manifest);
    };
    let root = PathBuf::from(override_root);
    let name = docs_manifest.file_name().ok_or_else(site::unavailable)?;
    Site::open(&root, &root.join(name))
}

/// Fixes the documentation policy for the shell origins of this application
/// and refuses a shell policy that does not frame the documentation origin.
fn prepare<R: Runtime>(app: &AppHandle<R>, site: &Site, issued: &OnceLock<String>) -> Result<()> {
    let config = app.config();
    let window =
        config.app.windows.first().ok_or_else(|| {
            ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview)
        })?;
    if !policy::shell_frames(config, &policy::origin(window)) {
        return Err(ApplicationError::new(
            ErrorCode::WebviewFailed,
            Operation::Webview,
        ));
    }
    let header =
        policy::content_security_policy(site.script_hashes(), &shell::origins(config, window))?;
    app.manage(published(site, &policy::origin(window))?);
    issued
        .set(header)
        .map_err(|_| ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview))
}
