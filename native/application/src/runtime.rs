//! Bounded runtime identity query through the selected installed interpreter.

use crate::{child::ChildConfiguration, component::Cancellation, error::Error};
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
const REAP_BOUND: Duration = Duration::from_secs(5);

#[derive(Debug)]
struct IdentitySettlementFailure {
    primary: Error,
    settlement: std::io::Error,
}

impl std::fmt::Display for IdentitySettlementFailure {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            formatter,
            "runtime identity child settlement failed: {:?}",
            self.settlement.kind()
        )
    }
}

impl std::error::Error for IdentitySettlementFailure {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.primary)
    }
}

async fn terminate_and_reap(child: &mut tokio::process::Child) -> std::io::Result<()> {
    if child.try_wait()?.is_none() {
        child.start_kill()?;
    }
    tokio::time::timeout(REAP_BOUND, child.wait())
        .await
        .map_err(|_| std::io::Error::from(std::io::ErrorKind::TimedOut))??;
    Ok(())
}

/// The caller verifies the package and supplies its pinned strict environment.
/// Timeout and malformed output terminate and reap the immediate query child.
pub async fn identity(
    configuration: &ChildConfiguration,
    bound: Duration,
) -> Result<RuntimeIdentity, Error> {
    identity_cancellable(configuration, bound, &Cancellation::default()).await
}

async fn until_cancelled<T>(
    future: impl std::future::Future<Output = Result<T, Error>>,
    cancellation: &Cancellation,
) -> Result<T, Error> {
    cancellation.check()?;
    tokio::select! {
        biased;
        error = async {
            loop {
                if let Err(error) = cancellation.check() {
                    return error;
                }
                tokio::time::sleep(Duration::from_millis(25)).await;
            }
        } => Err(error),
        result = future => result,
    }
}

pub async fn identity_cancellable(
    configuration: &ChildConfiguration,
    bound: Duration,
    cancellation: &Cancellation,
) -> Result<RuntimeIdentity, Error> {
    cancellation.check()?;
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
    let outcome = tokio::time::timeout(
        bound,
        until_cancelled(
            async {
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
            },
            cancellation,
        ),
    )
    .await;
    match outcome {
        Ok(Ok(identity)) => Ok(identity),
        other => {
            let primary = match other {
                Ok(Err(error)) => error,
                _ => Error::TimedOut,
            };
            match terminate_and_reap(&mut child).await {
                Ok(()) => Err(primary),
                Err(settlement) => Err(Error::Io(std::io::Error::other(
                    IdentitySettlementFailure {
                        primary,
                        settlement,
                    },
                ))),
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

#[cfg(all(test, windows))]
mod tests {
    use super::*;

    #[tokio::test]
    async fn termination_reaps_the_exact_query_child_and_accepts_already_settled_child() {
        let image = std::path::PathBuf::from(std::env::var_os("SystemRoot").unwrap())
            .join("System32/WindowsPowerShell/v1.0/powershell.exe");
        let mut child = tokio::process::Command::new(image)
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Start-Sleep -Seconds 30",
            ])
            .creation_flags(0x0800_0000)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .kill_on_drop(true)
            .spawn()
            .unwrap();
        assert!(child.try_wait().unwrap().is_none());
        let cancellation = Cancellation::default();
        {
            let waiting = child.wait();
            tokio::pin!(waiting);
            let observation = std::future::poll_fn(|context| {
                let state = std::future::Future::poll(waiting.as_mut(), context);
                // Cancel only after the real retained child wait was polled.
                cancellation.cancel();
                state.map(|result| result.map_err(Error::from))
            });
            assert!(matches!(
                tokio::time::timeout(
                    Duration::from_secs(2),
                    until_cancelled(observation, &cancellation)
                )
                .await
                .unwrap(),
                Err(Error::Cancelled)
            ));
        }
        terminate_and_reap(&mut child).await.unwrap();
        assert!(child.try_wait().unwrap().is_some());
        terminate_and_reap(&mut child).await.unwrap();
    }

    #[tokio::test]
    async fn cancelled_identity_refuses_before_spawning_even_a_missing_image() {
        let root = std::path::PathBuf::from(std::env::var_os("SystemRoot").unwrap());
        let configuration = ChildConfiguration::new(
            root.join("cadrumo-missing-test-interpreter.exe"),
            root,
            Default::default(),
        )
        .unwrap();
        let cancellation = Cancellation::default();
        cancellation.cancel();
        assert!(matches!(
            identity_cancellable(&configuration, Duration::from_secs(30), &cancellation).await,
            Err(Error::Cancelled)
        ));
    }
}
