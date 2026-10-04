use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    diagnostics::Diagnostics,
    failure::{Failure, FailureCode, Operation, Result},
    package::PackageManifest,
    tracking::{ProcessPhase, ProcessRole, Stream},
    value::RelativePath,
};
use serde::Deserialize;
use std::{collections::BTreeMap, path::PathBuf, process::Stdio, sync::Arc, time::Duration};
use tokio::io::{AsyncRead, AsyncReadExt};

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
}
#[derive(Deserialize)]
struct Layout {
    abi: u32,
    platform: String,
    paths: Paths,
    files: Files,
}
#[derive(Deserialize)]
struct Paths {
    executable: RelativePath,
}
#[derive(Deserialize)]
struct Files {
    package_manifest: RelativePath,
}
#[derive(Deserialize)]
struct Projection {
    environment: BTreeMap<String, String>,
    storage: PathBuf,
    cache: PathBuf,
    logs: PathBuf,
    log_max_bytes: u64,
    log_backups: u32,
}

pub struct Launch {
    pub child: ChildConfiguration,
    pub working_directory: PathBuf,
    pub webview: PathBuf,
    pub diagnostics: Arc<Diagnostics>,
}

// The native interpreter prepares the platform environment before this fixed query.
// Never retain this query's stdout: the environment can contain credentials.
const PROJECTION: &str = r#"
import json, os, sys
from cadrumo.core.storage_environment import configured_storage_root, tool_storage_environment
from cadrumo.core.logging import default_log_file_path
from cadrumo.core.config import load_settings
settings = load_settings()
json.dump(dict(environment=dict(os.environ), storage=str(configured_storage_root()),
               cache=tool_storage_environment()['XDG_CACHE_HOME'], logs=str(default_log_file_path().parent),
               log_max_bytes=settings.cadrumo_log_file_max_bytes,
               log_backups=settings.cadrumo_log_file_backup_count), sys.stdout)
"#;

fn failure(code: FailureCode) -> Failure {
    Failure::new(code, Operation::Environment)
}

pub async fn resolve(root: PathBuf, diagnostics: Arc<Diagnostics>) -> Result<Launch> {
    let invalid = || Failure::new(FailureCode::PackageUnavailable, Operation::Package);
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|e| invalid().caused_by(e))?;
    let layout = contract.layout;
    let manifest = PackageManifest::read(&root, &layout.files.package_manifest)
        .map_err(|e| invalid().caused_by(e))?;
    if manifest.layout.platform != layout.platform || manifest.layout.abi != layout.abi {
        return Err(invalid());
    }
    let executable = layout.paths.executable.under(&root);
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
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let mut child = command
        .spawn()
        .map_err(|e| failure(FailureCode::SpawnFailed).caused_by(e))?;
    let id = diagnostics.start(
        child
            .id()
            .ok_or_else(|| failure(FailureCode::SpawnFailed))?,
        ProcessRole::Environment,
    );
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| failure(FailureCode::ReadFailed))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| failure(FailureCode::ReadFailed))?;
    let outcome = tokio::time::timeout(Duration::from_secs(30), async {
        let (output, errors) =
            tokio::try_join!(bounded(stdout, 1024 * 1024), bounded(stderr, 65536))?;
        if !errors.is_empty() {
            diagnostics.capture(id, Stream::Stderr, &errors);
        }
        let status = child
            .wait()
            .await
            .map_err(|e| failure(FailureCode::CleanupFailed).caused_by(e))?;
        diagnostics.finish(id, status.code(), ProcessPhase::Exited);
        if !status.success() {
            return Err(failure(FailureCode::EnvironmentFailed));
        }
        Ok(output)
    })
    .await;
    let output = match outcome {
        Ok(Ok(output)) => output,
        failure_result => {
            let primary = match failure_result {
                Ok(Err(error)) => error,
                _ => failure(FailureCode::TimedOut),
            };
            if child.try_wait().ok().flatten().is_none()
                && let Err(error) = child.kill().await
            {
                diagnostics.failure(failure(FailureCode::CleanupFailed).caused_by(error));
            }
            let reaped = child.wait().await;
            diagnostics.finish(
                id,
                reaped.as_ref().ok().and_then(|s| s.code()),
                ProcessPhase::Failed,
            );
            if let Err(error) = reaped {
                diagnostics.failure(failure(FailureCode::CleanupFailed).caused_by(error));
            }
            return Err(primary);
        }
    };
    let projection: Projection = serde_json::from_slice(&output)
        .map_err(|e| failure(FailureCode::EnvironmentFailed).caused_by(e))?;
    if !projection.cache.is_absolute()
        || !projection.storage.is_absolute()
        || !projection.logs.is_absolute()
    {
        return Err(failure(FailureCode::EnvironmentFailed));
    }
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
    .map_err(|e| failure(FailureCode::EnvironmentFailed).caused_by(e))?;
    Ok(Launch {
        child,
        working_directory: projection.storage,
        webview: projection.cache.join("desktop-webview"),
        diagnostics,
    })
}

async fn bounded(mut reader: impl AsyncRead + Unpin, limit: usize) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    let mut buffer = [0; 8192];
    loop {
        let count = reader
            .read(&mut buffer)
            .await
            .map_err(|e| failure(FailureCode::ReadFailed).caused_by(e))?;
        if count == 0 {
            return Ok(bytes);
        }
        if bytes.len() + count > limit {
            return Err(failure(FailureCode::OutputLimit));
        }
        bytes.extend_from_slice(&buffer[..count]);
    }
}
