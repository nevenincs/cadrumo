use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    package::PackageManifest,
    process::status::{ProcessPhase, ProcessRole, Stream},
    value::RelativePath,
};
use serde::Deserialize;
use std::{
    collections::BTreeMap,
    ffi::OsString,
    path::{Path, PathBuf},
    process::Stdio,
    sync::Arc,
    time::Duration,
};
use tokio::io::{AsyncRead, AsyncReadExt};

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
    storage_environment_allowlist: Vec<String>,
}
#[derive(Deserialize)]
struct Layout {
    abi: u32,
    platform: String,
    paths: Paths,
    files: Files,
    user_docs: UserDocs,
}
#[derive(Deserialize)]
struct Paths {
    executable: RelativePath,
    docs: RelativePath,
}
#[derive(Deserialize)]
struct UserDocs {
    directory: RelativePath,
    manifest: RelativePath,
}
#[derive(Deserialize)]
struct Files {
    package_manifest: RelativePath,
}
#[derive(Deserialize)]
struct Projection {
    environment: BTreeMap<String, String>,
    storage: PathBuf,
    storage_variable: String,
    /// The webview profile directory the storage taxonomy resolves.
    webview: PathBuf,
    logs: PathBuf,
    log_file: PathBuf,
    log_format: String,
    log_max_bytes: u64,
    log_backups: u32,
    output_language: String,
    home: PathBuf,
}

pub struct Launch {
    pub child: ChildConfiguration,
    /// The projected storage root; the child environment pins Settings to it.
    pub working_directory: PathBuf,
    /// The webview profile directory, which also holds the window state.
    pub webview: PathBuf,
    pub diagnostics: Arc<Diagnostics>,
    /// The user's home directory, where interactive shells start.
    pub home: PathBuf,
    pub package_root: PathBuf,
    /// The packaged user documentation and its manifest inside the package.
    pub docs_root: PathBuf,
    pub docs_manifest: PathBuf,
    /// The Python log file and the line format Python writes it with.
    pub log_file: PathBuf,
    pub log_format: String,
    /// The output language Settings resolved, for the shell chrome.
    pub output_language: String,
}

/// The environment and working directory the host was started with.
pub struct Parent {
    pub environment: Vec<(OsString, OsString)>,
    pub working_directory: PathBuf,
}

impl Parent {
    pub fn current() -> Result<Self> {
        Ok(Self {
            environment: std::env::vars_os().collect(),
            working_directory: std::env::current_dir()
                .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?,
        })
    }
}

// The native interpreter prepares the platform environment before this fixed query.
// Never retain this query's stdout: the environment can contain credentials.
const PROJECTION: &str = include_str!("python/environment.py");

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Environment)
}

pub async fn resolve(
    root: PathBuf,
    parent: &Parent,
    diagnostics: Arc<Diagnostics>,
) -> Result<Launch> {
    let (executable, projection, layout) = project(&root, parent, &diagnostics).await?;
    let docs_root = layout
        .user_docs
        .directory
        .under(&layout.paths.docs.under(&root));
    let docs_manifest = layout.user_docs.manifest.under(&docs_root);
    if let Err(error) = diagnostics.configure(
        &projection.logs,
        projection.log_max_bytes,
        projection.log_backups,
    ) {
        diagnostics.failure(error);
    }
    let child = ChildConfiguration::new(
        executable,
        projection.storage.clone(),
        projection
            .environment
            .into_iter()
            .map(|(key, value)| (key.into(), value.into()))
            .collect(),
    )
    .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?;
    Ok(Launch {
        child,
        working_directory: projection.storage,
        webview: projection.webview,
        diagnostics,
        home: projection.home,
        package_root: root,
        docs_root,
        docs_manifest,
        log_file: projection.log_file,
        log_format: projection.log_format,
        output_language: projection.output_language,
    })
}

/// Verifies the package interpreter and runs the fixed projection query with
/// the parent's environment and working directory.
async fn project(
    root: &Path,
    parent: &Parent,
    diagnostics: &Diagnostics,
) -> Result<(PathBuf, Projection, Layout)> {
    let invalid = || ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Package);
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|e| invalid().caused_by(e))?;
    let layout = contract.layout;
    let manifest = PackageManifest::read(root, &layout.files.package_manifest)
        .map_err(|e| invalid().caused_by(e))?;
    if manifest.layout.platform != layout.platform || manifest.layout.abi != layout.abi {
        return Err(invalid());
    }
    let executable = layout.paths.executable.under(root);
    let digest = manifest
        .files
        .get(&layout.paths.executable)
        .ok_or_else(invalid)?;
    binary::verify(
        &executable,
        digest,
        BinaryExpectation::host().map_err(|e| invalid().caused_by(e))?,
    )
    .map_err(|e| invalid().caused_by(e))?;
    let mut command = tokio::process::Command::new(&executable);
    command
        .args(["-I", "-c", PROJECTION])
        .env_clear()
        .envs(parent.environment.iter().map(|(key, value)| (key, value)))
        .current_dir(&parent.working_directory)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let mut child = command
        .spawn()
        .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(e))?;
    let id = diagnostics.start(
        child.id().ok_or_else(|| failure(ErrorCode::SpawnFailed))?,
        ProcessRole::Environment,
    );
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| failure(ErrorCode::ReadFailed))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| failure(ErrorCode::ReadFailed))?;
    let outcome = tokio::time::timeout(Duration::from_secs(30), async {
        let (output, errors) =
            tokio::try_join!(bounded(stdout, 1024 * 1024), bounded(stderr, 65536))?;
        if !errors.is_empty() {
            diagnostics.capture(id, Stream::Stderr, &errors);
        }
        let status = child
            .wait()
            .await
            .map_err(|e| failure(ErrorCode::CleanupFailed).caused_by(e))?;
        diagnostics.finish(id, status.code(), ProcessPhase::Exited);
        if !status.success() {
            return Err(failure(ErrorCode::EnvironmentFailed));
        }
        Ok(output)
    })
    .await;
    let output = match outcome {
        Ok(Ok(output)) => output,
        failure_result => {
            let primary = match failure_result {
                Ok(Err(error)) => error,
                _ => failure(ErrorCode::TimedOut),
            };
            if child.try_wait().ok().flatten().is_none()
                && let Err(error) = child.kill().await
            {
                diagnostics.failure(failure(ErrorCode::CleanupFailed).caused_by(error));
            }
            let reaped = child.wait().await;
            diagnostics.finish(
                id,
                reaped.as_ref().ok().and_then(|s| s.code()),
                ProcessPhase::Failed,
            );
            if let Err(error) = reaped {
                diagnostics.failure(failure(ErrorCode::CleanupFailed).caused_by(error));
            }
            return Err(primary);
        }
    };
    let projection: Projection = serde_json::from_slice(&output)
        .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?;
    if !admissible(&projection, &contract.storage_environment_allowlist) {
        return Err(failure(ErrorCode::EnvironmentFailed));
    }
    Ok((executable, projection, layout))
}

fn admissible(projection: &Projection, settings_storage_names: &[String]) -> bool {
    [
        &projection.webview,
        &projection.storage,
        &projection.logs,
        &projection.log_file,
        &projection.home,
    ]
    .iter()
    .all(|path| path.is_absolute())
        && projection.log_file.parent() == Some(projection.logs.as_path())
        && !projection.log_format.is_empty()
        && !projection.output_language.is_empty()
        && projection
            .output_language
            .bytes()
            .all(|byte| byte.is_ascii_lowercase())
        && pins_storage(projection, settings_storage_names)
}

/// Every child must carry the resolved root under the Settings-owned name, or
/// a child started elsewhere would resolve storage against its own directory.
fn pins_storage(projection: &Projection, settings_storage_names: &[String]) -> bool {
    settings_storage_names.contains(&projection.storage_variable)
        && projection
            .environment
            .iter()
            .filter(|(key, _)| key.eq_ignore_ascii_case(&projection.storage_variable))
            .map(|(_, value)| Path::new(value))
            .eq([projection.storage.as_path()])
}

async fn bounded(mut reader: impl AsyncRead + Unpin, limit: usize) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    let mut buffer = [0; 8192];
    loop {
        let count = reader
            .read(&mut buffer)
            .await
            .map_err(|e| failure(ErrorCode::ReadFailed).caused_by(e))?;
        if count == 0 {
            return Ok(bytes);
        }
        if bytes.len() + count > limit {
            return Err(failure(ErrorCode::OutputLimit));
        }
        bytes.extend_from_slice(&buffer[..count]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn projection(environment: serde_json::Value) -> Projection {
        serde_json::from_value(serde_json::json!({
            "environment": environment,
            "storage": "C:/state/var/storage",
            "storage_variable": "CADRUMO_LOCAL_STORAGE_ROOT",
            "webview": "C:/state/var/storage/webview",
            "logs": "C:/state/var/storage/logs",
            "log_file": "C:/state/var/storage/logs/cadrumo.log",
            "log_format": "%(message)s",
            "log_max_bytes": 1,
            "log_backups": 1,
            "output_language": "es",
            "home": "C:/Users/someone",
        }))
        .unwrap()
    }

    #[test]
    fn storage_pin_requires_the_resolved_root_under_a_settings_owned_name() {
        let owned = ["CADRUMO_LOCAL_STORAGE_ROOT".to_owned()];
        let pinned = serde_json::json!({"CADRUMO_LOCAL_STORAGE_ROOT": "C:/state/var/storage"});
        assert!(pins_storage(&projection(pinned.clone()), &owned));
        assert!(!pins_storage(
            &projection(pinned),
            &["CADRUMO_STORAGE_ROOT".to_owned()]
        ));
        for unpinned in [
            serde_json::json!({}),
            serde_json::json!({"CADRUMO_LOCAL_STORAGE_ROOT": "var/storage"}),
            serde_json::json!({"CADRUMO_LOCAL_STORAGE_ROOT": "C:/elsewhere"}),
            serde_json::json!({
                "CADRUMO_LOCAL_STORAGE_ROOT": "C:/state/var/storage",
                "cadrumo_local_storage_root": "C:/elsewhere",
            }),
        ] {
            assert!(!pins_storage(&projection(unpinned), &owned));
        }
    }

    #[test]
    fn a_projection_with_a_relative_webview_location_is_refused() {
        let owned = ["CADRUMO_LOCAL_STORAGE_ROOT".to_owned()];
        // Absolute on the running platform, so only the webview field varies.
        let storage = std::env::temp_dir().join("state");
        let mut admitted = projection(serde_json::json!({
            "CADRUMO_LOCAL_STORAGE_ROOT": storage.to_string_lossy(),
        }));
        admitted.logs = storage.join("logs");
        admitted.log_file = admitted.logs.join("cadrumo.log");
        admitted.home = std::env::temp_dir();
        admitted.webview = storage.join("webview");
        admitted.storage = storage;
        assert!(admissible(&admitted, &owned));
        let mut relative = admitted;
        relative.webview = PathBuf::from("webview");
        assert!(!admissible(&relative, &owned));
    }

    // Launch does not carry these facts until their consumers land; this keeps
    // the fixed query's output for them exercised against a real package.
    #[cfg(feature = "live-package-tests")]
    #[tokio::test]
    async fn packaged_projection_reports_host_facts() {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let contract: serde_json::Value =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        let parent = Parent::current().unwrap();
        let (_, projection, _) = project(&root, &parent, &Diagnostics::default())
            .await
            .unwrap();
        assert!(projection.home.is_absolute() && projection.home.is_dir());
        assert_ne!(projection.home, projection.storage);
        assert_eq!(
            projection.log_file.parent(),
            Some(projection.logs.as_path())
        );
        for field in ["%(asctime)s", "%(levelname)s", "%(name)s", "%(message)s"] {
            assert!(projection.log_format.contains(field), "{field}");
        }
        let languages = contract["layout"]["user_docs"]["languages"]
            .as_array()
            .unwrap();
        assert!(languages.contains(&serde_json::Value::from(
            projection.output_language.as_str()
        )));
        assert!(pins_storage(
            &projection,
            &serde_json::from_value::<Vec<String>>(
                contract["storage_environment_allowlist"].clone()
            )
            .unwrap()
        ));
    }
}
