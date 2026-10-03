use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    package::{PackageManifest, Readiness},
    value::RelativePath,
};
use serde::Deserialize;
use std::{collections::BTreeMap, path::PathBuf, process::Stdio, time::Duration};
use tokio::io::AsyncReadExt;

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
}

pub struct Launch {
    pub child: ChildConfiguration,
    pub working_directory: PathBuf,
    pub webview: PathBuf,
}

// The sealed interpreter prepares the platform environment before this fixed query.
// Settings remains the owner of storage overrides and defaults.
const PROJECTION: &str = r#"
import json, os
from cadrumo.core.storage_environment import configured_storage_root, tool_storage_environment
json.dump(dict(environment=dict(os.environ), storage=str(configured_storage_root()),
               cache=tool_storage_environment()['XDG_CACHE_HOME']), __import__('sys').stdout)
"#;

pub async fn resolve(root: PathBuf) -> Result<Launch, String> {
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|e| e.to_string())?;
    let layout = contract.layout;
    let manifest =
        PackageManifest::read(&root, &layout.files.package_manifest).map_err(|e| e.to_string())?;
    if manifest.layout.platform != layout.platform || manifest.layout.abi != layout.abi {
        return Err(format!(
            "Package unavailable: {:?}",
            Readiness::Incompatible("package target or ABI differs".into())
        ));
    }
    let executable = layout.paths.executable.under(&root);
    // Native interpreter startup checks essential package files. Full-inventory
    // hashing belongs to the package acceptance check, not each window launch.
    let digest = manifest
        .files
        .get(&layout.paths.executable)
        .ok_or("Interpreter absent from package inventory")?;
    binary::verify(
        &executable,
        digest,
        BinaryExpectation::host().map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;

    let mut command = tokio::process::Command::new(&executable);
    command
        .args(["-I", "-c", PROJECTION])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true);
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let mut child = command.spawn().map_err(|e| e.to_string())?;
    let stdout = child.stdout.take().ok_or("Missing projection output")?;
    let mut output = Vec::new();
    let result = tokio::time::timeout(Duration::from_secs(30), async {
        stdout
            .take(1024 * 1024 + 1)
            .read_to_end(&mut output)
            .await?;
        if output.len() > 1024 * 1024 {
            return Err(std::io::Error::other(
                "Environment projection exceeds limit",
            ));
        }
        let status = child.wait().await?;
        if !status.success() {
            return Err(std::io::Error::other(
                "Packaged environment projection failed",
            ));
        }
        Ok(())
    })
    .await;
    if !matches!(result, Ok(Ok(()))) {
        let _ = child.kill().await;
        let _ = child.wait().await;
        return Err("Packaged environment projection failed or timed out".into());
    }
    let projection: Projection = serde_json::from_slice(&output).map_err(|e| e.to_string())?;
    if !projection.cache.is_absolute() || !projection.storage.is_absolute() {
        return Err("Storage owner returned a relative path".into());
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
    .map_err(|e| e.to_string())?;
    Ok(Launch {
        child,
        working_directory: projection.storage,
        webview: projection.cache.join("desktop-webview"),
    })
}
