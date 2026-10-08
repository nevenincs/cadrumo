//! Bounded runtime identity query through the selected installed interpreter.

use crate::{child::ChildConfiguration, error::Error};
use serde::Deserialize;
use std::{path::PathBuf, process::Stdio, time::Duration};
use tokio::io::{AsyncRead, AsyncReadExt};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeIdentity {
    pub storage: PathBuf,
    pub storage_identity: String,
    pub version: String,
}

const QUERY: &str = include_str!("runtime_identity.py");

/// The caller verifies the package and supplies its pinned strict environment.
/// Timeout and malformed output terminate and reap the immediate query child.
pub async fn identity(
    configuration: &ChildConfiguration,
    bound: Duration,
) -> Result<RuntimeIdentity, Error> {
    if bound.is_zero() || bound > Duration::from_secs(30) {
        return Err(Error::Invalid("invalid runtime identity deadline".into()));
    }
    let mut command = tokio::process::Command::from(configuration.command());
    command
        .args(["-I", "-c", QUERY])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true);
    #[cfg(windows)]
    command.creation_flags(0x0800_0000);
    let mut child = command.spawn()?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| Error::Invalid("missing query stream".into()))?;
    let outcome = tokio::time::timeout(bound, async {
        let bytes = bounded(stdout).await?;
        if !child.wait().await?.success() {
            return Err(Error::ProbeFailed);
        }
        let identity: RuntimeIdentity = serde_json::from_slice(&bytes)?;
        if !identity.storage.is_absolute()
            || identity.storage_identity.len() != 64
            || !identity
                .storage_identity
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
            || identity.version.is_empty()
            || identity.version.len() > 64
        {
            return Err(Error::Invalid("invalid runtime identity".into()));
        }
        Ok(identity)
    })
    .await;
    match outcome {
        Ok(Ok(identity)) => Ok(identity),
        other => {
            if child.try_wait()?.is_none() {
                child.kill().await?;
            }
            child.wait().await?;
            match other {
                Ok(Err(error)) => Err(error),
                _ => Err(Error::TimedOut),
            }
        }
    }
}

async fn bounded(mut reader: impl AsyncRead + Unpin) -> Result<Vec<u8>, Error> {
    let mut bytes = Vec::new();
    let mut buffer = [0; 1024];
    loop {
        let count = reader.read(&mut buffer).await?;
        if count == 0 {
            return Ok(bytes);
        }
        if bytes.len() + count > 8192 {
            return Err(Error::LimitExceeded);
        }
        bytes.extend_from_slice(&buffer[..count]);
    }
}
