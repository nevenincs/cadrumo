use crate::logs::Level;
use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    installation::{DiscoveryContract, maintenance::Lease},
    package::PackageManifest,
    value::RelativePath,
};
use serde::Deserialize;
use std::{
    collections::BTreeMap,
    ffi::OsString,
    path::{Path, PathBuf},
    sync::Arc,
};

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
    application_environment: ApplicationEnvironment,
    desktop_defaults: DesktopDefaults,
}
/// The package's declared environment: the storage root and the member locations an
/// operator may relocate, whose overrides the desktop leaves to the command line's Settings.
#[derive(Deserialize)]
struct ApplicationEnvironment {
    location_names: Vec<String>,
}
/// The package's own locations under the storage root, and the command line's log
/// location, format and limits, which the desktop reads without asking Python.
#[derive(Deserialize)]
struct DesktopDefaults {
    console_workspace: RelativePath,
    webview: RelativePath,
    logs: RelativePath,
    log_variable: String,
    log_file: RelativePath,
    manager_log_file: RelativePath,
    log_format: String,
    log_max_bytes: u64,
    log_backups: u32,
    output_language: String,
    output_language_variable: String,
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
    console_workspace: PathBuf,
    #[serde(default)]
    log_level: Level,
}

pub struct Launch {
    /// This process's independent removal fence, retained through GUI/headless use.
    pub(crate) _publication: Option<Arc<Lease>>,
    pub child: ChildConfiguration,
    /// The projected storage root; the child environment pins Settings to it.
    pub working_directory: PathBuf,
    /// The webview profile directory, which also holds the window state.
    pub webview: PathBuf,
    pub diagnostics: Arc<Diagnostics>,
    /// Operator workspace for all terminals; separate from encrypted profile custody.
    pub console_workspace: PathBuf,
    pub package_root: PathBuf,
    /// What the package manifest states about the optional user documentation.
    pub docs: PackagedDocs,
    /// The Python log file and the line format Python writes it with.
    pub log_file: PathBuf,
    pub manager_log_file: PathBuf,
    pub log_format: String,
    /// The output language Settings resolved, for the shell chrome.
    pub output_language: String,
    pub log_level: Level,
}

/// The package manifest's statement about the optional user documentation.
pub enum PackagedDocs {
    Bundled(DocsLocation),
    NotBundled,
    /// The manifest does not say; the documentation is treated as unavailable.
    Undeclared,
}

/// The packaged user documentation tree and its manifest inside the package.
pub struct DocsLocation {
    pub root: PathBuf,
    pub manifest: PathBuf,
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

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Environment)
}

pub async fn resolve(
    root: PathBuf,
    parent: &Parent,
    diagnostics: Arc<Diagnostics>,
) -> Result<Launch> {
    let admission: DiscoveryContract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|e| failure(ErrorCode::PackageUnavailable).caused_by(e))?;
    let publication = admission
        .acquire_package(&root)
        .map_err(|e| failure(ErrorCode::PackageUnavailable).caused_by(e))?;
    let (executable, projection, layout, bundled) = project(&root, parent)?;
    let docs = match bundled {
        Some(true) => {
            let root = layout
                .user_docs
                .directory
                .under(&layout.paths.docs.under(&root));
            PackagedDocs::Bundled(DocsLocation {
                manifest: layout.user_docs.manifest.under(&root),
                root,
            })
        }
        Some(false) => PackagedDocs::NotBundled,
        None => PackagedDocs::Undeclared,
    };
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
    diagnostics.service(
        None,
        cadrumo_application::diagnostics::service::ServiceFact::EnvironmentResolved {
            package_abi: layout.abi,
            log_level: projection.log_level,
            log_level_overridden: parent.environment.iter().any(|(key, value)| {
                key.to_string_lossy()
                    .eq_ignore_ascii_case("CADRUMO_LOG_LEVEL")
                    && !value.to_string_lossy().trim().is_empty()
            }),
        },
    );
    Ok(Launch {
        _publication: publication,
        child,
        working_directory: projection.storage,
        webview: projection.webview,
        diagnostics,
        console_workspace: projection.console_workspace,
        package_root: root,
        docs,
        log_file: projection.log_file,
        manager_log_file: projection.manager_log_file,
        log_format: projection.log_format,
        output_language: projection.output_language,
        log_level: projection.log_level,
    })
}

/// Verifies the package interpreter and projects the environment its children receive
/// and the locations the desktop uses, from the package's own declarations. Also returns
/// the package manifest's statement of whether the optional user documentation is bundled.
fn project(root: &Path, parent: &Parent) -> Result<(PathBuf, Projection, Layout, Option<bool>)> {
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
    let bundled = manifest
        .user_docs
        .as_ref()
        .map(|statement| statement.bundled);
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
    let projection = native_projection(
        &executable,
        parent,
        &contract.desktop_defaults,
        &contract.application_environment.location_names,
    )?;
    Ok((executable, projection, layout, bundled))
}

/// The environment the package's interpreter defines for the parent, and the locations
/// beneath its pinned root: the package's own components at their declared places, and
/// the command line's log directory where an admitted override relocates it.
fn native_projection(
    executable: &Path,
    parent: &Parent,
    defaults: &DesktopDefaults,
    location_names: &[String],
) -> Result<Projection> {
    use cadrumo_platform::{
        ROOT_VARIABLE, prepared_environment,
        storage::{member_path, validated_absolute_path},
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
    let defined = |name: &str| {
        environment
            .iter()
            .find(|(key, _)| key.eq_ignore_ascii_case(name))
            .map(|(_, value)| OsString::from(value))
    };
    let storage =
        PathBuf::from(defined(ROOT_VARIABLE).ok_or_else(|| failure(ErrorCode::EnvironmentFailed))?);
    let path = |relative: &RelativePath| {
        validated_absolute_path(&relative.under(&storage))
            .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))
    };
    let logs = member_path(
        &storage,
        &defaults.log_variable,
        defaults.logs.as_str(),
        &defined,
    )
    .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?;
    let log_file = logs.join(
        Path::new(defaults.log_file.as_str())
            .file_name()
            .ok_or_else(|| failure(ErrorCode::EnvironmentFailed))?,
    );
    let output_language = defined(&defaults.output_language_variable)
        .and_then(|value| value.into_string().ok())
        .map(|value| value.trim().to_ascii_lowercase())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| defaults.output_language.clone());
    let log_level = defined("CADRUMO_LOG_LEVEL")
        .filter(|value| !value.to_string_lossy().trim().is_empty())
        .map(|value| {
            value
                .into_string()
                .ok()
                .and_then(|value| Level::operator(&value))
                .ok_or_else(|| failure(ErrorCode::EnvironmentFailed))
        })
        .transpose()?
        .unwrap_or_default();
    // The shell needs only storage and presentation defaults. Profile/pointer
    // validation remains with the canonical account CLI read, which can report
    // its typed refusal in the visible window instead of delaying its creation.
    let console_workspace = path(&defaults.console_workspace)?;
    std::fs::create_dir_all(&console_workspace)
        .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?;
    let console_workspace = path(&defaults.console_workspace)?;
    let projection = Projection {
        webview: path(&defaults.webview)?,
        logs,
        log_file,
        manager_log_file: path(&defaults.manager_log_file)?,
        environment,
        storage,
        storage_variable: ROOT_VARIABLE.to_owned(),
        log_format: defaults.log_format.clone(),
        log_max_bytes: defaults.log_max_bytes,
        log_backups: defaults.log_backups,
        output_language,
        console_workspace,
        log_level,
    };
    if !admissible(&projection, location_names) {
        return Err(failure(ErrorCode::EnvironmentFailed));
    }
    Ok(projection)
}

fn admissible(projection: &Projection, location_names: &[String]) -> bool {
    [
        &projection.webview,
        &projection.storage,
        &projection.logs,
        &projection.log_file,
        &projection.manager_log_file,
        &projection.console_workspace,
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
        && pins_storage(projection, location_names)
}

/// Every child must carry the resolved root under the package's declared root name, or
/// a child started elsewhere would resolve storage against its own directory.
fn pins_storage(projection: &Projection, location_names: &[String]) -> bool {
    location_names.contains(&projection.storage_variable)
        && projection
            .environment
            .iter()
            .filter(|(key, _)| key.eq_ignore_ascii_case(&projection.storage_variable))
            .map(|(_, value)| Path::new(value))
            .eq([projection.storage.as_path()])
}

#[cfg(test)]
impl Parent {
    fn clone_for_test(&self) -> Self {
        Self {
            environment: self.environment.clone(),
            working_directory: self.working_directory.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(windows)]
    #[test]
    fn native_projection_creates_workspace_and_refuses_non_directory_or_link() {
        let contract: Contract =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        let scratch = std::env::temp_dir().join(format!(
            "cadrumo-workspace-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let package = scratch.join("package");
        let manifest = contract.layout.files.package_manifest.under(&package);
        std::fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        std::fs::write(manifest, "{}").unwrap();
        let storage = scratch.join("storage");
        let workspace = storage.join("workspace");
        let executable = contract.layout.paths.executable.under(&package);
        let mut parent = Parent::current().unwrap();
        parent.environment.retain(|(key, _)| {
            !contract
                .application_environment
                .location_names
                .iter()
                .any(|name| key.eq_ignore_ascii_case(name))
        });
        parent.environment.push((
            cadrumo_platform::ROOT_VARIABLE.into(),
            storage.clone().into_os_string(),
        ));
        let project = || {
            native_projection(
                &executable,
                &parent,
                &contract.desktop_defaults,
                &contract.application_environment.location_names,
            )
        };
        let projection = project().unwrap();
        assert_eq!(projection.log_level, Level::Info);
        for (value, expected) in [
            ("DEBUG", Level::Debug),
            ("info", Level::Info),
            (" WARNING ", Level::Warning),
            ("ERROR", Level::Error),
            ("CRITICAL", Level::Critical),
            ("verbose", Level::Info),
            ("quiet", Level::Error),
            ("", Level::Info),
        ] {
            let mut overridden = parent.clone_for_test();
            overridden
                .environment
                .push(("CADRUMO_LOG_LEVEL".into(), value.into()));
            let observed = native_projection(
                &executable,
                &overridden,
                &contract.desktop_defaults,
                &contract.application_environment.location_names,
            )
            .unwrap();
            assert_eq!(observed.log_level, expected);
        }
        let mut invalid = parent.clone_for_test();
        invalid.environment.push((
            "CADRUMO_LOG_LEVEL".into(),
            "private-invalid-level-canary".into(),
        ));
        let error = native_projection(
            &executable,
            &invalid,
            &contract.desktop_defaults,
            &contract.application_environment.location_names,
        )
        .err()
        .unwrap();
        assert_eq!(error.code, ErrorCode::EnvironmentFailed);
        assert!(!serde_json::to_string(&error).unwrap().contains("canary"));
        assert_eq!(
            projection.webview,
            contract.desktop_defaults.webview.under(&storage)
        );
        assert_eq!(
            projection.logs,
            contract.desktop_defaults.logs.under(&storage)
        );
        assert_eq!(
            projection.manager_log_file,
            contract.desktop_defaults.manager_log_file.under(&storage)
        );

        // A relocated log directory moves the command line's log file and nothing else:
        // the package's own components stay at their declared places under the root.
        let explicit_logs = scratch.join("explicit-logs");
        let mut relocated = parent.clone_for_test();
        relocated.environment.push((
            contract.desktop_defaults.log_variable.clone().into(),
            explicit_logs.clone().into_os_string(),
        ));
        let moved = native_projection(
            &executable,
            &relocated,
            &contract.desktop_defaults,
            &contract.application_environment.location_names,
        )
        .unwrap();
        assert_eq!(moved.logs, explicit_logs);
        assert_eq!(moved.log_file.parent(), Some(explicit_logs.as_path()));
        assert_eq!(moved.webview, projection.webview);
        assert_eq!(moved.console_workspace, projection.console_workspace);
        assert_eq!(moved.manager_log_file, projection.manager_log_file);
        let mut relative = parent.clone_for_test();
        relative.environment.push((
            contract.desktop_defaults.log_variable.clone().into(),
            "relocated-logs".into(),
        ));
        let anchored = native_projection(
            &executable,
            &relative,
            &contract.desktop_defaults,
            &contract.application_environment.location_names,
        )
        .unwrap();
        assert_eq!(anchored.logs, storage.join("relocated-logs"));
        assert_eq!(projection.console_workspace, workspace);
        assert!(workspace.is_dir());
        std::fs::remove_dir(&workspace).unwrap();
        std::fs::write(&workspace, "not a directory").unwrap();
        assert!(project().is_err());
        std::fs::remove_file(&workspace).unwrap();
        let other = scratch.join("elsewhere");
        std::fs::create_dir(&other).unwrap();
        std::os::windows::fs::symlink_dir(&other, &workspace).unwrap();
        assert!(project().is_err());
        assert!(std::fs::read_dir(&other).unwrap().next().is_none());
        std::fs::remove_dir(&workspace).unwrap();
        std::fs::remove_dir_all(scratch).unwrap();
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
            "console_workspace": "C:/state/var/storage/workspace",
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
        admitted.console_workspace = storage.join("workspace");
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
    // the projection of them exercised against a real package.
    #[cfg(feature = "live-package-tests")]
    #[test]
    fn packaged_projection_reports_host_facts() {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let contract: serde_json::Value =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        let parent = Parent::current().unwrap();
        let (_, projection, _, _) = project(&root, &parent).unwrap();
        assert!(
            projection.console_workspace.is_absolute() && projection.console_workspace.is_dir()
        );
        assert!(
            projection
                .console_workspace
                .starts_with(&projection.storage)
        );
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
                contract["application_environment"]["location_names"].clone()
            )
            .unwrap()
        ));
    }
}
