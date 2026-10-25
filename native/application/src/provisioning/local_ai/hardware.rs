//! The hardware floor: whether this computer can hold a model at all.
//!
//! A model needs its size, as the selected catalogue entry states it, either in the
//! computer's memory or in one NVIDIA card's memory. A computer below that for a selected
//! model reads `blocked hardware` for it: a limit, not a failure, so no button can change
//! it. A computer with no selected local model is never held back. A computer whose memory could not be measured is never held back by the floor,
//! because an unread value must not invent a shortfall.
//!
//! Memory is read from `/proc/meminfo` on Linux, `sysctl hw.memsize` on macOS and the
//! system's management instrumentation on Windows; a card's memory from `nvidia-smi`
//! when the NVIDIA driver installed it. Each query is a separate program started with no
//! console window, bounded in time and output, whose answer is parsed strictly. A host
//! that already measured supplies the values instead.

use std::{
    ffi::OsString,
    io::Read,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::mpsc,
    time::Duration,
};

/// Bound for one hardware query to answer.
pub const QUERY_BUDGET: Duration = Duration::from_secs(5);
const QUERY_OUTPUT_LIMIT: u64 = 64 * 1024;
const MEBIBYTE: u64 = 1024 * 1024;
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// What this computer can hold a model in.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Hardware {
    pub total_memory_bytes: Option<u64>,
    /// The largest NVIDIA card's memory; `None` without an NVIDIA card or driver.
    pub nvidia_vram_bytes: Option<u64>,
}

impl Hardware {
    /// Whether a model needing `required_bytes` cannot fit here: measured memory and any
    /// NVIDIA card's memory are both below it.
    pub fn below_floor(&self, required_bytes: u64) -> bool {
        match self.total_memory_bytes {
            None => false,
            Some(total) => {
                total < required_bytes
                    && self
                        .nvidia_vram_bytes
                        .is_none_or(|vram| vram < required_bytes)
            }
        }
    }

    /// Measures this computer. `ambient` reads the engine's environment, for the `PATH`
    /// and system folder the query programs are found in.
    pub fn measure(ambient: &dyn Fn(&str) -> Option<OsString>) -> Self {
        Self::measure_with(ambient, &run_query)
    }

    /// [`Self::measure`] with the query programs run by `query`, which returns a program's
    /// standard output when it ran and succeeded.
    pub fn measure_with(
        ambient: &dyn Fn(&str) -> Option<OsString>,
        query: &dyn Fn(&Path, &[&str]) -> Option<String>,
    ) -> Self {
        Self {
            total_memory_bytes: total_memory(ambient, query),
            nvidia_vram_bytes: nvidia_smi(ambient)
                .and_then(|program| {
                    query(
                        &program,
                        &["--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    )
                })
                .and_then(|output| parse_nvidia_memory(&output)),
        }
    }
}

#[cfg(target_os = "linux")]
fn total_memory(
    _: &dyn Fn(&str) -> Option<OsString>,
    _: &dyn Fn(&Path, &[&str]) -> Option<String>,
) -> Option<u64> {
    parse_meminfo(&std::fs::read_to_string("/proc/meminfo").ok()?)
}

#[cfg(target_os = "macos")]
fn total_memory(
    _: &dyn Fn(&str) -> Option<OsString>,
    query: &dyn Fn(&Path, &[&str]) -> Option<String>,
) -> Option<u64> {
    parse_count(&query(
        Path::new("/usr/sbin/sysctl"),
        &["-n", "hw.memsize"],
    )?)
}

#[cfg(windows)]
fn total_memory(
    ambient: &dyn Fn(&str) -> Option<OsString>,
    query: &dyn Fn(&Path, &[&str]) -> Option<String>,
) -> Option<u64> {
    let root = PathBuf::from(ambient("SystemRoot")?);
    let shell = root
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");
    parse_count(&query(
        &shell,
        &[
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory",
        ],
    )?)
}

#[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
fn total_memory(
    _: &dyn Fn(&str) -> Option<OsString>,
    _: &dyn Fn(&Path, &[&str]) -> Option<String>,
) -> Option<u64> {
    None
}

/// Where the NVIDIA driver put `nvidia-smi`: on `PATH`, or in the Windows system folder.
fn nvidia_smi(ambient: &dyn Fn(&str) -> Option<OsString>) -> Option<PathBuf> {
    let name = if cfg!(windows) {
        "nvidia-smi.exe"
    } else {
        "nvidia-smi"
    };
    let mut candidates: Vec<PathBuf> = ambient("PATH")
        .map(|path| {
            std::env::split_paths(&path)
                .map(|folder| folder.join(name))
                .collect()
        })
        .unwrap_or_default();
    if cfg!(windows)
        && let Some(root) = ambient("SystemRoot")
    {
        candidates.push(PathBuf::from(root).join("System32").join(name));
    }
    candidates
        .into_iter()
        .find(|candidate| candidate.is_absolute() && candidate.is_file())
}

/// One whole decimal count of bytes, as the memory queries print it.
fn parse_count(output: &str) -> Option<u64> {
    let text = output.trim();
    if text.is_empty() || !text.bytes().all(|c| c.is_ascii_digit()) {
        return None;
    }
    text.parse().ok().filter(|bytes| *bytes > 0)
}

/// `MemTotal` from Linux's `/proc/meminfo`, which counts kibibytes.
#[cfg(any(target_os = "linux", test))]
fn parse_meminfo(text: &str) -> Option<u64> {
    let line = text.lines().find(|line| line.starts_with("MemTotal:"))?;
    let mut fields = line["MemTotal:".len()..].split_whitespace();
    let kibibytes = parse_count(fields.next()?)?;
    (fields.next() == Some("kB") && fields.next().is_none())
        .then(|| kibibytes.checked_mul(1024))
        .flatten()
}

/// The largest card's memory from `nvidia-smi`'s one line per card in mebibytes; `None`
/// when any line is not a count, so a garbled answer never passes for a card.
fn parse_nvidia_memory(output: &str) -> Option<u64> {
    let mut largest = None;
    for line in output
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
    {
        let bytes = parse_count(line)?.checked_mul(MEBIBYTE)?;
        largest = Some(largest.map_or(bytes, |seen: u64| seen.max(bytes)));
    }
    largest
}

/// Runs one query program with no console window and no input, returning its standard
/// output when it succeeds inside [`QUERY_BUDGET`] and [`QUERY_OUTPUT_LIMIT`]. A program
/// that overruns is ended.
fn run_query(program: &Path, arguments: &[&str]) -> Option<String> {
    let mut command = Command::new(program);
    command
        .args(arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    #[cfg(unix)]
    crate::process::group::place(&mut command).ok()?;
    let mut child = crate::process::creation::run(|| command.spawn()).ok()?;
    let mut stdout = child.stdout.take()?;
    let (sender, receiver) = mpsc::channel();
    std::thread::Builder::new()
        .name("cadrumo-hardware-query".into())
        .spawn(move || {
            let mut output = Vec::new();
            let read = (&mut stdout)
                .take(QUERY_OUTPUT_LIMIT + 1)
                .read_to_end(&mut output);
            let _ = sender.send(read.ok().map(|_| output));
        })
        .ok()?;
    let output = receiver.recv_timeout(QUERY_BUDGET).ok().flatten();
    if output.is_none() {
        let _ = child.kill();
    }
    let status = child.wait().ok()?;
    let output = output?;
    if !status.success() || output.len() as u64 > QUERY_OUTPUT_LIMIT {
        return None;
    }
    String::from_utf8(output).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    const GIB: u64 = 1024 * 1024 * 1024;

    #[test]
    fn the_floor_holds_back_only_a_measured_computer_with_no_card_large_enough() {
        let model = 2 * GIB;
        let computer = |total, vram| Hardware {
            total_memory_bytes: total,
            nvidia_vram_bytes: vram,
        };
        assert!(computer(Some(GIB), None).below_floor(model));
        assert!(computer(Some(GIB), Some(GIB)).below_floor(model));
        assert!(!computer(Some(GIB), Some(4 * GIB)).below_floor(model));
        assert!(!computer(Some(model), None).below_floor(model));
        assert!(!computer(None, None).below_floor(model));
        assert!(!computer(None, Some(GIB)).below_floor(model));
    }

    #[test]
    fn query_answers_are_parsed_strictly() {
        assert_eq!(parse_nvidia_memory("16376\n"), Some(16_376 * MEBIBYTE));
        assert_eq!(
            parse_nvidia_memory("8192\r\n24564\r\n"),
            Some(24_564 * MEBIBYTE)
        );
        assert_eq!(parse_nvidia_memory(""), None);
        assert_eq!(parse_nvidia_memory("8192\n[N/A]\n"), None);
        assert_eq!(
            parse_nvidia_memory("NVIDIA-SMI has failed because it couldn't communicate"),
            None
        );
        assert_eq!(parse_count("137341362176\r\n"), Some(137_341_362_176));
        assert_eq!(parse_count("-1"), None);
        assert_eq!(parse_count("0"), None);
        assert_eq!(
            parse_meminfo("MemTotal:       16314092 kB\nMemFree:  1 kB\n"),
            Some(16_314_092 * 1024)
        );
        assert_eq!(parse_meminfo("MemTotal: 16314092 MB\n"), None);
        assert_eq!(parse_meminfo("MemFree: 1 kB\n"), None);
    }

    #[test]
    fn a_card_is_read_only_where_its_driver_put_the_query_program() {
        let root = tempfile::tempdir().unwrap();
        let tools = root.path().join("tools");
        std::fs::create_dir_all(&tools).unwrap();
        let path = std::env::join_paths([&tools]).unwrap();
        let ambient = |name: &str| (name == "PATH").then(|| path.clone());
        let asked = std::cell::RefCell::new(Vec::new());
        let query = |program: &Path, arguments: &[&str]| {
            asked.borrow_mut().push(program.to_path_buf());
            arguments
                .contains(&"--query-gpu=memory.total")
                .then(|| "6144\n".to_owned())
        };
        let without = Hardware::measure_with(&ambient, &query);
        assert_eq!(without.nvidia_vram_bytes, None);
        assert!(
            asked
                .borrow()
                .iter()
                .all(|program| !program.starts_with(&tools))
        );
        let name = if cfg!(windows) {
            "nvidia-smi.exe"
        } else {
            "nvidia-smi"
        };
        std::fs::write(tools.join(name), b"stand-in").unwrap();
        let with = Hardware::measure_with(&ambient, &query);
        assert_eq!(with.nvidia_vram_bytes, Some(6144 * MEBIBYTE));
        assert!(asked.borrow().contains(&tools.join(name)));
    }

    #[test]
    fn a_query_program_that_fails_or_cannot_start_answers_nothing() {
        let missing = std::env::temp_dir().join("cadrumo-no-such-query-program.exe");
        assert_eq!(run_query(&missing, &[]), None);
        let this = std::env::current_exe().unwrap();
        assert!(run_query(&this, &["--exact", "no::such::test"]).is_some());
        assert_eq!(
            run_query(&this, &["--no-such-harness-flag"]),
            None,
            "an unsuccessful exit answers nothing"
        );
    }
}
