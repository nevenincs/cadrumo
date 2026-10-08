//! Explicit, bounded interpreter interrogation. No browser/driver launch or acquisition.
//! The caller supplies a trusted digest and the complete platform-owned child environment.
use crate::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    error::Error,
    filesystem,
    value::Sha256Digest,
};
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, path::PathBuf, process::Stdio, time::Duration};
use tokio::{
    io::{AsyncRead, AsyncReadExt, AsyncWriteExt},
    process::Command,
};

#[derive(Debug)]
pub struct PythonExpectation {
    pub executable_sha256: Sha256Digest,
    pub version: String,
    pub distributions: BTreeMap<String, String>,
}

impl PythonExpectation {
    /// Project the assembler's version cohort and executable hash. The caller must first
    /// verify the package inventory and select the path from its canonical layout.
    pub fn from_manifest(
        manifest: &crate::package::PackageManifest,
        executable: &crate::value::RelativePath,
    ) -> Result<Self, Error> {
        Ok(Self {
            executable_sha256: manifest
                .files
                .get(executable)
                .ok_or_else(|| {
                    Error::Invalid("executable is absent from package inventory".into())
                })?
                .clone(),
            version: manifest.python.clone(),
            distributions: manifest.distributions.clone(),
        })
    }
}

#[derive(Debug, Default)]
pub struct BrowserQuery {
    /// None delegates storage resolution to the Python settings owner.
    pub root: Option<PathBuf>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PythonReport {
    pub schema: u32,
    pub implementation: String,
    pub version: String,
    pub pointer_bits: u32,
    pub executable: PathBuf,
    pub distributions: BTreeMap<String, Option<String>>,
    pub browser: Option<BrowserReport>,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BrowserState {
    MissingDependency,
    UnreadableManifest,
    MissingBuilds,
    Ready,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BrowserBuild {
    pub name: String,
    pub revision: String,
    pub directory_name: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BrowserReport {
    pub state: BrowserState,
    pub builds: Vec<BrowserBuild>,
    /// Canonical facts and recovery verdict, retained without reinterpreting domain policy.
    pub owner_report: Option<serde_json::Value>,
}

#[derive(Serialize)]
struct Request<'a> {
    distributions: Vec<&'a String>,
    browser: bool,
    browser_root: Option<&'a std::path::Path>,
}

/// Requires a Tokio runtime with time and I/O enabled. Timeout covers the child execution
/// and pipe draining; preflight file reads are synchronous. The immediate child is killed
/// and reaped on timeout or cancellation. Descendant process containment is not provided.
/// Dropping this future requests termination through Tokio's kill-on-drop mechanism.
pub async fn probe(
    configuration: &ChildConfiguration,
    expected: &PythonExpectation,
    browser: Option<&BrowserQuery>,
    timeout: Duration,
    cancel: &crate::component::Cancellation,
) -> Result<PythonReport, Error> {
    cancel.check()?;
    if timeout.is_zero() || timeout > Duration::from_secs(60) {
        return Err(Error::Invalid(
            "probe timeout must be within 0..60 seconds".into(),
        ));
    }
    if let Some(root) = browser.and_then(|b| b.root.as_ref()) {
        filesystem::absolute_root(root)?;
    }
    let request = serde_json::to_vec(&Request {
        distributions: expected.distributions.keys().collect(),
        browser: browser.is_some(),
        browser_root: browser.and_then(|b| b.root.as_deref()),
    })?;
    if request.len() > 65536 {
        return Err(Error::LimitExceeded);
    }
    binary::verify(
        configuration.executable(),
        &expected.executable_sha256,
        BinaryExpectation::host()?,
    )?;
    cancel.check()?;
    let mut command = Command::from(configuration.command());
    command.args(["-I", "-B", "-c", include_str!("python_probe.py")]);
    let bytes = run(command, request, timeout, cancel).await?;
    let report: PythonReport = serde_json::from_slice(&bytes)?;
    if report.schema != 1
        || report.implementation != "cpython"
        || report.version != expected.version
        || report.pointer_bits != usize::BITS
        || std::fs::canonicalize(&report.executable)?
            != std::fs::canonicalize(configuration.executable())?
        || report.distributions.len() != expected.distributions.len()
        || expected
            .distributions
            .iter()
            .any(|(name, version)| report.distributions.get(name) != Some(&Some(version.clone())))
        || report.browser.is_some() != browser.is_some()
    {
        return Err(Error::Incompatible(
            "interpreter or distributions differ".into(),
        ));
    }
    Ok(report)
}

async fn bounded_read(mut input: impl AsyncRead + Unpin) -> Result<Vec<u8>, Error> {
    let mut bytes = Vec::new();
    (&mut input)
        .take(1024 * 1024 + 1)
        .read_to_end(&mut bytes)
        .await?;
    if bytes.len() > 1024 * 1024 {
        return Err(Error::LimitExceeded);
    }
    Ok(bytes)
}

async fn run(
    mut command: Command,
    request: Vec<u8>,
    timeout: Duration,
    cancel: &crate::component::Cancellation,
) -> Result<Vec<u8>, Error> {
    cancel.check()?;
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    let mut child = command.spawn()?;
    let mut stdin = child.stdin.take().ok_or(Error::ProbeFailed)?;
    let stdout = child.stdout.take().ok_or(Error::ProbeFailed)?;
    let stderr = child.stderr.take().ok_or(Error::ProbeFailed)?;
    let result = {
        let work = async {
            let (status, output, _, _) = tokio::try_join!(
                async { child.wait().await.map_err(Error::from) },
                bounded_read(stdout),
                bounded_read(stderr),
                async {
                    stdin.write_all(&request).await?;
                    stdin.shutdown().await?;
                    drop(stdin);
                    Ok(())
                },
            )?;
            if !status.success() {
                return Err(Error::ProbeFailed);
            }
            Ok(output)
        };
        tokio::select! {
            result = work => result,
            _ = tokio::time::sleep(timeout) => Err(Error::TimedOut),
            error = async {
                loop {
                    if let Err(error) = cancel.check() { break error; }
                    tokio::time::sleep(Duration::from_millis(10)).await;
                }
            } => Err(error),
        }
    };
    if result.is_err() {
        // A completed child may still have inherited pipes held by a descendant.
        // Killing/waiting the immediate child does not wait for those pipes.
        child.kill().await?;
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::component::Cancellation;
    use std::io::Write;

    #[test]
    fn helper() {
        let Ok(mode) = std::env::var("CADRUMO_PROBE_TEST_MODE") else {
            return;
        };
        let _lock = std::env::var_os("CADRUMO_PROBE_TEST_LOCK").map(|path| {
            let file = std::fs::File::options()
                .read(true)
                .write(true)
                .open(&path)
                .unwrap();
            file.try_lock().unwrap();
            std::fs::write(
                std::path::PathBuf::from(path).with_extension("ready"),
                b"ready",
            )
            .unwrap();
            file
        });
        match mode.as_str() {
            "hang" => std::thread::sleep(Duration::from_secs(30)),
            "overflow" => {
                std::io::stdout()
                    .write_all(&vec![b'x'; 1024 * 1024 + 1])
                    .unwrap();
                std::thread::sleep(Duration::from_secs(30));
            }
            "fail" => std::process::exit(7),
            "eof" => {
                let mut request = String::new();
                std::io::Read::read_to_string(&mut std::io::stdin(), &mut request).unwrap();
                assert_eq!(request, "probe request");
            }
            _ => panic!("unknown helper mode"),
        }
    }

    fn helper_command(mode: &str) -> Command {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args(["--exact", "python::tests::helper", "--nocapture"])
            .env("CADRUMO_PROBE_TEST_MODE", mode);
        command
    }

    #[tokio::test]
    async fn request_closes_stdin_for_eof_readers() {
        run(
            helper_command("eof"),
            b"probe request".to_vec(),
            Duration::from_secs(5),
            &Cancellation::default(),
        )
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn bounds_output_and_terminates_child() {
        let result = run(
            helper_command("overflow"),
            vec![],
            Duration::from_secs(10),
            &Cancellation::default(),
        )
        .await;
        assert!(matches!(result, Err(Error::LimitExceeded)), "{result:?}");
    }

    #[tokio::test]
    async fn timeout_and_cancellation_terminate_child() {
        let cancel = Cancellation::default();
        let result = run(
            helper_command("hang"),
            vec![],
            Duration::from_millis(100),
            &cancel,
        )
        .await;
        assert!(matches!(result, Err(Error::TimedOut)), "{result:?}");
        let operation = run(
            helper_command("hang"),
            vec![],
            Duration::from_secs(10),
            &cancel,
        );
        let trigger = async {
            tokio::time::sleep(Duration::from_millis(100)).await;
            cancel.cancel();
        };
        let (result, ()) = tokio::join!(operation, trigger);
        assert!(matches!(result, Err(Error::Cancelled)), "{result:?}");
    }

    #[tokio::test]
    async fn reports_unsuccessful_exit_without_stderr() {
        let result = run(
            helper_command("fail"),
            vec![],
            Duration::from_secs(10),
            &Cancellation::default(),
        )
        .await;
        assert!(matches!(result, Err(Error::ProbeFailed)), "{result:?}");
    }

    #[tokio::test]
    async fn cancellation_reaps_child_and_releases_its_os_lock() {
        let directory = tempfile::tempdir().unwrap();
        let lock_path = directory.path().join("child.lock");
        let file = std::fs::File::options()
            .create_new(true)
            .read(true)
            .write(true)
            .open(&lock_path)
            .unwrap();
        let mut command = helper_command("hang");
        command.env("CADRUMO_PROBE_TEST_LOCK", &lock_path);
        let cancel = Cancellation::default();
        let operation = run(command, vec![], Duration::from_secs(10), &cancel);
        let trigger = async {
            tokio::time::timeout(Duration::from_secs(5), async {
                while !lock_path.with_extension("ready").exists() {
                    tokio::time::sleep(Duration::from_millis(10)).await;
                }
            })
            .await
            .unwrap();
            assert!(file.try_lock().is_err(), "helper did not hold its lock");
            cancel.cancel();
        };
        let (result, ()) = tokio::join!(operation, trigger);
        assert!(matches!(result, Err(Error::Cancelled)), "{result:?}");
        file.try_lock()
            .expect("child retained OS resources after cancellation");
    }
}
