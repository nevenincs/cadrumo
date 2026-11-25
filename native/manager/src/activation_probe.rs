//! Read-only activation compatibility for an already catalogue-verified manager image.

use std::{
    io,
    os::windows::process::CommandExt,
    path::Path,
    process::{Child, Command, ExitStatus, Stdio},
    thread,
    time::{Duration, Instant},
};

const PROBE_BOUND: Duration = Duration::from_secs(2);
const CLEANUP_BOUND: Duration = Duration::from_secs(2);
const POLL: Duration = Duration::from_millis(10);
/// A late answer is asked again: on a loaded machine a capable image can miss one bound,
/// and refusing the person's Retry for that would leave the recovery they asked for undone.
const PROBE_ATTEMPTS: u32 = 3;
const PROBE_BACKOFF: Duration = Duration::from_millis(250);

/// The caller retains its admitted package lease throughout this metadata-only probe.
/// Success establishes Retry grammar support, never session admission or readiness.
/// Only a late answer is asked again; an image that answers without Retry support, or
/// fails, is refused at once.
pub fn require_retry_support(manager: &Path, package: &Path) -> io::Result<()> {
    let mut attempt = 1;
    loop {
        match probe_once(manager, package) {
            Err(error) if error.kind() == io::ErrorKind::TimedOut && attempt < PROBE_ATTEMPTS => {
                thread::sleep(PROBE_BACKOFF * attempt);
                attempt += 1;
            }
            settled => return settled,
        }
    }
}

fn probe_once(manager: &Path, package: &Path) -> io::Result<()> {
    let mut child = cadrumo_application::process::creation::run(|| {
        Command::new(manager)
            .arg("--supports-retry")
            .env_clear()
            .envs(cadrumo_platform::storage::strict_host_environment(
                std::env::vars_os(),
            ))
            .current_dir(package)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x0800_0000)
            .spawn()
    })?;
    match wait_exit(&mut child, PROBE_BOUND) {
        Ok(status) if status.success() => Ok(()),
        Ok(_) => Err(io::ErrorKind::Unsupported.into()),
        Err(error) => {
            // Only our metadata child is terminated; no owner or runtime is targeted.
            cleanup(&mut child)?;
            Err(error)
        }
    }
}

pub(crate) fn wait_exit(child: &mut Child, bound: Duration) -> io::Result<ExitStatus> {
    let deadline = Instant::now() + bound;
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(status);
        }
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Err(io::ErrorKind::TimedOut.into());
        }
        thread::sleep(POLL.min(remaining));
    }
}

pub(crate) fn cleanup(child: &mut Child) -> io::Result<()> {
    if matches!(child.try_wait(), Ok(Some(_))) {
        return Ok(());
    }
    if let Err(error) = child.kill() {
        // An exit between the poll and termination is already settled.
        if matches!(child.try_wait(), Ok(Some(_))) {
            return Ok(());
        }
        return Err(error);
    }
    wait_exit(child, CLEANUP_BOUND).map(|_| ())
}
