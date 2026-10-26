//! Transient user-systemd placement. A harmless scope probe precedes pipe fallback.
use std::{
    ffi::OsString,
    fs,
    io::{self, Read},
    os::unix::fs::{MetadataExt, PermissionsExt},
    path::Path,
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Scope,
    Pipe,
}

#[derive(Debug)]
pub struct Placement {
    pub unit: String,
    pub mode: Mode,
}

fn system_binary(path: &str) -> io::Result<()> {
    let metadata = fs::metadata(path)?;
    if !metadata.is_file() || metadata.uid() != 0 || metadata.permissions().mode() & 0o022 != 0 {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(())
}

fn nonce() -> io::Result<String> {
    let mut bytes = [0u8; 16];
    fs::File::open("/dev/urandom")?.read_exact(&mut bytes)?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

impl Placement {
    pub fn probe(environment: &[(OsString, OsString)]) -> io::Result<Self> {
        system_binary("/usr/bin/systemd-run")?;
        system_binary("/usr/bin/true")?;
        let stem = format!("{}-{}", crate::identity::MANAGER_ID, nonce()?);
        for mode in [Mode::Scope, Mode::Pipe] {
            let suffix = if mode == Mode::Scope {
                "scope"
            } else {
                "service"
            };
            let probe = Self {
                unit: format!("{stem}-probe.{suffix}"),
                mode,
            };
            let mut command = probe.command(Path::new("/usr/bin/true"), &[], environment)?;
            command
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            if bounded_status(command, Duration::from_secs(5))? {
                return Ok(Self {
                    unit: format!("{stem}.{suffix}"),
                    mode,
                });
            }
        }
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "user systemd placement unavailable",
        ))
    }

    /// The returned child's PID belongs to systemd-run. Readiness must independently
    /// bind a runtime pidfd, installed image, boot identity and this exact cgroup.
    pub fn command(
        &self,
        image: &Path,
        arguments: &[OsString],
        environment: &[(OsString, OsString)],
    ) -> io::Result<Command> {
        if !image.is_absolute() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let mut command = Command::new("/usr/bin/systemd-run");
        command
            .env_clear()
            .envs(environment.iter().map(|(key, value)| (key, value)))
            .args([
                "--user",
                "--quiet",
                "--no-ask-password",
                "--collect",
                "--expand-environment=no",
            ])
            .arg(format!("--unit={}", self.unit));
        match self.mode {
            Mode::Scope => {
                command.args(["--scope", "--property=TimeoutStopUSec=4s"]);
            }
            Mode::Pipe => {
                command.args([
                    "--pipe",
                    "--wait",
                    "--service-type=exec",
                    "--property=Restart=no",
                    "--property=TimeoutStopSec=4s",
                    "--property=KillMode=mixed",
                ]);
                // The service manager otherwise supplies its own environment. env -i
                // makes the canonical child snapshot authoritative in both modes.
                system_binary("/usr/bin/env")?;
                command.args(["--", "/usr/bin/env", "-i"]);
                for (key, value) in environment {
                    if key.is_empty() || key.as_encoded_bytes().contains(&b'=') {
                        return Err(io::ErrorKind::InvalidInput.into());
                    }
                    let mut assignment = key.clone();
                    assignment.push("=");
                    assignment.push(value);
                    command.arg(assignment);
                }
            }
        }
        if self.mode == Mode::Scope {
            command.arg("--");
        }
        command.arg(image).args(arguments);
        Ok(command)
    }

    pub fn contains(&self, pid: u32) -> io::Result<bool> {
        let mut text = String::new();
        fs::File::open(format!("/proc/{pid}/cgroup"))?
            .take(16385)
            .read_to_string(&mut text)?;
        if text.len() > 16384 {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok(text.lines().any(|line| {
            line.strip_prefix("0::")
                .is_some_and(|path| path.ends_with(&format!("/{}", self.unit)))
        }))
    }
}

fn bounded_status(mut command: Command, bound: Duration) -> io::Result<bool> {
    let mut child: Child = command.spawn()?;
    let deadline = Instant::now() + bound;
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(status.success());
        }
        if Instant::now() >= deadline {
            child.kill()?;
            child.wait()?;
            return Err(io::ErrorKind::TimedOut.into());
        }
        thread::sleep(Duration::from_millis(10));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn scope_command_preserves_literal_arguments_and_distinguishes_wrapper() {
        let placement = Placement {
            unit: "example-fixture.scope".into(),
            mode: Mode::Scope,
        };
        let command = placement
            .command(Path::new("/opt/runtime"), &["literal $HOME %s".into()], &[])
            .unwrap();
        let arguments: Vec<_> = command
            .get_args()
            .map(|value| value.to_string_lossy().into_owned())
            .collect();
        assert!(arguments.contains(&"--scope".into()));
        assert!(arguments.contains(&"--expand-environment=no".into()));
        assert_eq!(arguments.last().unwrap(), "literal $HOME %s");
        assert!(placement.command(Path::new("relative"), &[], &[]).is_err());
    }
}
