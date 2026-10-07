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
    #[cfg(windows)]
    desktop_defaults: DesktopDefaults,
}
#[cfg(windows)]
#[derive(Deserialize)]
struct DesktopDefaults {
    webview: RelativePath,
    logs: RelativePath,
    log_file: RelativePath,
    manager_log_file: RelativePath,
    log_format: String,
    log_max_bytes: u64,
    log_backups: u32,
    output_language: String,
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
#[derive(Deserialize, PartialEq)]
struct Projection {
    environment: BTreeMap<String, String>,
    storage: PathBuf,
    storage_variable: String,
    /// The webview profile directory the storage taxonomy resolves.
    webview: PathBuf,
    logs: PathBuf,
    log_file: PathBuf,
    manager_log_file: PathBuf,
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
    pub manager_log_file: PathBuf,
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
        manager_log_file: projection.manager_log_file,
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
    #[cfg(windows)]
    if let Some(projection) = default_projection(
        &executable,
        parent,
        &contract.desktop_defaults,
        &contract.storage_environment_allowlist,
    )? {
        return Ok((executable, projection, layout));
    }
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
    let mut child = command.spawn().map_err(|cause| {
        let error = failure(ErrorCode::SpawnFailed).caused_by(cause);
        diagnostics.spawn_failure(ProcessRole::Environment, error.clone());
        error
    })?;
    let id = diagnostics.start(
        child.id().ok_or_else(|| {
            let error = failure(ErrorCode::SpawnFailed);
            diagnostics.spawn_failure(ProcessRole::Environment, error.clone());
            error
        })?,
        ProcessRole::Environment,
    );
    let result = async {
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
                    diagnostics.failure_for(id, failure(ErrorCode::CleanupFailed).caused_by(error));
                }
                let reaped = child.wait().await;
                diagnostics.finish(
                    id,
                    reaped.as_ref().ok().and_then(|s| s.code()),
                    ProcessPhase::Failed,
                );
                if let Err(error) = reaped {
                    diagnostics.failure_for(id, failure(ErrorCode::CleanupFailed).caused_by(error));
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
    .await;
    if let Err(error) = &result {
        diagnostics.failure_for(id, error.clone());
    }
    result
}

/// Member overrides continue through Settings, including their validation. The
/// native host already owns root validation and pins it before Python starts.
#[cfg(any(windows, test))]
fn uses_default_members(parent: &Parent, settings_storage_names: &[String], root: &str) -> bool {
    !parent.environment.iter().any(|(key, value)| {
        settings_storage_names.iter().any(|name| {
            key.to_string_lossy().eq_ignore_ascii_case(name)
                && !name.eq_ignore_ascii_case(root)
                && !value.to_string_lossy().trim().is_empty()
        })
    })
}

#[cfg(windows)]
fn default_projection(
    executable: &Path,
    parent: &Parent,
    defaults: &DesktopDefaults,
    settings_storage_names: &[String],
) -> Result<Option<Projection>> {
    use cadrumo_platform::{ROOT_VARIABLE, prepared_environment, storage::validated_absolute_path};
    if !uses_default_members(parent, settings_storage_names, ROOT_VARIABLE) {
        return Ok(None);
    }
    // Python's Path.home on Windows reads USERPROFILE, otherwise HOMEDRIVE +
    // HOMEPATH. Keep the query fallback for unusual host home configurations.
    let lookup = |name: &str| {
        parent
            .environment
            .iter()
            .rev()
            .find(|(key, _)| key.to_string_lossy().eq_ignore_ascii_case(name))
            .map(|(_, value)| value.clone())
    };
    let home = lookup("USERPROFILE").or_else(|| {
        let mut value = lookup("HOMEDRIVE").unwrap_or_default();
        value.push(lookup("HOMEPATH")?);
        Some(value)
    });
    let Some(home) = home.map(PathBuf::from).filter(|path| path.is_absolute()) else {
        return Ok(None);
    };
    // Unlike storage, a home may legitimately traverse junctions. Resolve them
    // as Path.home().resolve() does, retaining Python for a missing home.
    let Ok(home) = std::fs::canonicalize(home) else {
        return Ok(None);
    };
    let Some(home) = home.to_str() else {
        return Ok(None);
    };
    let home = if let Some(unc) = home.strip_prefix(r"\\?\UNC\") {
        PathBuf::from(format!(r"\\{unc}"))
    } else {
        PathBuf::from(home.strip_prefix(r"\\?\").unwrap_or(home))
    };
    let environment = prepared_environment(executable, &parent.environment)
        .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(std::io::Error::other(e)))?;
    let environment: BTreeMap<String, String> = environment
        .into_iter()
        .map(|(key, value)| {
            Ok((
                key.into_string()
                    .map_err(|_| failure(ErrorCode::EnvironmentFailed))?,
                value
                    .into_string()
                    .map_err(|_| failure(ErrorCode::EnvironmentFailed))?,
            ))
        })
        .collect::<Result<_>>()?;
    let storage = PathBuf::from(
        environment
            .get(ROOT_VARIABLE)
            .ok_or_else(|| failure(ErrorCode::EnvironmentFailed))?,
    );
    let path = |relative: &RelativePath| {
        validated_absolute_path(&relative.under(&storage))
            .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))
    };
    // The shell needs only storage and presentation defaults. Profile/pointer
    // validation remains with the canonical account CLI read, which can report
    // its typed refusal in the visible window instead of delaying its creation.
    let projection = Projection {
        webview: path(&defaults.webview)?,
        logs: path(&defaults.logs)?,
        log_file: path(&defaults.log_file)?,
        manager_log_file: path(&defaults.manager_log_file)?,
        environment,
        storage,
        storage_variable: ROOT_VARIABLE.to_owned(),
        log_format: defaults.log_format.clone(),
        log_max_bytes: defaults.log_max_bytes,
        log_backups: defaults.log_backups,
        output_language: defaults.output_language.clone(),
        home,
    };
    if !admissible(&projection, settings_storage_names) {
        return Err(failure(ErrorCode::EnvironmentFailed));
    }
    Ok(Some(projection))
}

fn admissible(projection: &Projection, settings_storage_names: &[String]) -> bool {
    [
        &projection.webview,
        &projection.storage,
        &projection.logs,
        &projection.log_file,
        &projection.manager_log_file,
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

    #[test]
    fn default_projection_falls_back_for_all_nonblank_member_overrides() {
        let root = "CADRUMO_LOCAL_STORAGE_ROOT";
        let names = vec![
            root.to_owned(),
            "CADRUMO_LOG_DIR".to_owned(),
            "CADRUMO_CACHE_DIR".to_owned(),
        ];
        let parent = |entries: &[(&str, &str)]| Parent {
            environment: entries
                .iter()
                .map(|(key, value)| ((*key).into(), (*value).into()))
                .collect(),
            working_directory: std::env::temp_dir(),
        };
        assert!(uses_default_members(&parent(&[]), &names, root));
        assert!(uses_default_members(
            &parent(&[(root, "C:/state")]),
            &names,
            root
        ));
        assert!(uses_default_members(
            &parent(&[("CADRUMO_LOG_DIR", "  ")]),
            &names,
            root
        ));
        for name in &names[1..] {
            assert!(!uses_default_members(
                &parent(&[(name, "C:/override")]),
                &names,
                root
            ));
            assert!(!uses_default_members(
                &parent(&[(&name.to_lowercase(), "C:/override")]),
                &names,
                root
            ));
        }
    }

    #[cfg(all(windows, feature = "live-package-tests"))]
    #[tokio::test]
    async fn native_defaults_match_the_real_python_projection() {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let contract: Contract =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        let mut parent = Parent::current().unwrap();
        parent.environment.retain(|(key, _)| {
            !contract
                .storage_environment_allowlist
                .iter()
                .any(|name| key.to_string_lossy().eq_ignore_ascii_case(name))
        });
        let storage = std::env::temp_dir().join(format!(
            "cadrumo-projection-parity-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        parent.environment.push((
            cadrumo_platform::ROOT_VARIABLE.into(),
            storage.clone().into_os_string(),
        ));
        let started = std::time::Instant::now();
        let diagnostics = Diagnostics::default();
        let (executable, native, _) = project(&root, &parent, &diagnostics).await.unwrap();
        assert!(
            diagnostics
                .snapshot(0)
                .processes
                .iter()
                .all(|process| process.role != ProcessRole::Environment),
            "default launch spawned Python"
        );
        let native_elapsed = started.elapsed();
        let started = std::time::Instant::now();
        let output = reference_projection(&executable, &parent).await;
        let python_elapsed = started.elapsed();
        assert!(output.status.success(), "canonical Python query failed");
        let python: Projection = serde_json::from_slice(&output.stdout).unwrap();
        // Never print either environment: inherited values can contain secrets.
        assert!(
            native.environment == python.environment,
            "prepared environments differ"
        );
        macro_rules! same {
            ($($field:ident),+ $(,)?) => {$(
                assert!(native.$field == python.$field, concat!("canonical projection differs: ", stringify!($field)));
            )+};
        }
        same!(
            storage,
            storage_variable,
            webview,
            logs,
            log_file,
            manager_log_file,
            log_format,
            log_max_bytes,
            log_backups,
            output_language,
            home
        );
        eprintln!("native projection: {native_elapsed:?}; Python projection: {python_elapsed:?}");

        let raw_contract: serde_json::Value =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        let log_variable = raw_contract["locations"]
            .as_array()
            .unwrap()
            .iter()
            .find(|location| location["category"] == "logs")
            .unwrap()["variable"]
            .as_str()
            .unwrap();
        assert!(
            contract
                .storage_environment_allowlist
                .iter()
                .any(|name| name == log_variable)
        );
        let explicit_logs = storage.join("explicit-logs");
        std::fs::create_dir(&explicit_logs).unwrap();
        parent
            .environment
            .push((log_variable.into(), explicit_logs.clone().into_os_string()));
        let diagnostics = Diagnostics::default();
        let (_, explicit, _) = project(&root, &parent, &diagnostics).await.unwrap();
        assert!(
            explicit.logs == explicit_logs,
            "Settings lost the explicit log directory"
        );
        assert!(
            diagnostics
                .snapshot(0)
                .processes
                .iter()
                .any(|process| process.role == ProcessRole::Environment),
            "member override did not use Settings"
        );

        // A temporary directory cannot be a regular file. The canonical
        // interpreter host validates this member before importing Settings.
        let temporary_variable = raw_contract["locations"]
            .as_array()
            .unwrap()
            .iter()
            .find(|location| location["category"] == "temporary-files")
            .unwrap()["variable"]
            .as_str()
            .unwrap();
        let invalid_temporary = storage.join("temporary-file");
        std::fs::write(&invalid_temporary, b"not a directory").unwrap();
        parent.environment.push((
            temporary_variable.into(),
            invalid_temporary.into_os_string(),
        ));
        let diagnostics = Diagnostics::default();
        assert!(project(&root, &parent, &diagnostics).await.is_err());
        assert!(
            diagnostics
                .snapshot(0)
                .processes
                .iter()
                .any(|process| process.role == ProcessRole::Environment)
        );
        assert!(
            !reference_projection(&executable, &parent)
                .await
                .status
                .success(),
            "invalid member differs from canonical Settings refusal"
        );
        std::fs::remove_dir_all(storage).unwrap();
    }

    #[cfg(all(windows, feature = "live-package-tests"))]
    async fn reference_projection(executable: &Path, parent: &Parent) -> std::process::Output {
        let mut command = tokio::process::Command::new(executable);
        command
            .args(["-I", "-c", PROJECTION])
            .env_clear()
            .envs(parent.environment.iter().map(|(key, value)| (key, value)))
            .current_dir(&parent.working_directory)
            .stdin(Stdio::null())
            .kill_on_drop(true)
            .creation_flags(0x08000000);
        tokio::time::timeout(Duration::from_secs(30), command.output())
            .await
            .expect("canonical projection exceeded deadline")
            .expect("canonical projection could not run")
    }

    fn projection(environment: serde_json::Value) -> Projection {
        serde_json::from_value(serde_json::json!({
            "environment": environment,
            "storage": "C:/state/var/storage",
            "storage_variable": "CADRUMO_LOCAL_STORAGE_ROOT",
            "webview": "C:/state/var/storage/webview",
            "logs": "C:/state/var/storage/logs",
            "log_file": "C:/state/var/storage/logs/cadrumo.log",
            "manager_log_file": "C:/state/var/storage/logs/cadrumo-manager.log",
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
        admitted.manager_log_file = admitted.logs.join("cadrumo-manager.log");
        admitted.home = std::env::temp_dir();
        admitted.webview = storage.join("webview");
        admitted.storage = storage;
        assert!(admissible(&admitted, &owned));
        let mut relative = admitted;
        relative.manager_log_file = PathBuf::from("manager.log");
        assert!(!admissible(&relative, &owned));
        relative.manager_log_file = relative.logs.join("cadrumo-manager.log");
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
