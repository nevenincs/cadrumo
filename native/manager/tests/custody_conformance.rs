//! The manager's custody lock and record I/O against the Python custody owner, in real
//! processes.
//!
//! A Python peer runs `cadrumo.adapters.persistence.storage.custody.filesystem` through
//! the CMake-configured builder interpreter and answers one command per line, so
//! each test meets the runtime's own lock and record primitives on the same files: a lock
//! either side holds blocks the other, a crashed Python holder leaves the claim free, and
//! records written by either side read back on the other with their exact bytes.

use cadrumo_manager::custody::{
    LocalLock, clear_local_record, ensure_local_directory, read_optional_local_record,
};
use cadrumo_manager::session::claim::{StartClaim, start_claim_path};
use cadrumo_manager::session::quit::{
    MAXIMUM_QUIT_MARKER_BYTES, QuitMarker, QuitState, clear_quit, encode_quit_marker,
    quit_marker_path, read_quit_marker, record_quit,
};
use std::io::{BufRead, BufReader, Lines, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// The Python side: one tab-separated command per line, one answer line each.
const PEER: &str = r#"
import json
import os
import sys
from contextlib import ExitStack
from pathlib import Path

from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.filesystem import (
    clear_profile_custody_local_record,
    profile_custody_local_lock,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from cadrumo.adapters.persistence.storage.custody.filesystem_primitives import (
    ensure_profile_custody_local_directory,
)
from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant


def answer(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def security(path):
    if os.name != "nt":
        return oct(os.stat(path).st_mode & 0o777)
    import ctypes

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    descriptor = ctypes.c_void_p()
    dacl = 0x4
    if advapi.GetNamedSecurityInfoW(str(path), 1, dacl, None, None, None, None, ctypes.byref(descriptor)):
        raise OSError("security cannot be read")
    text = ctypes.c_wchar_p()
    if not advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, dacl, ctypes.byref(text), None):
        raise OSError("security cannot be rendered")
    return text.value


held = ExitStack()
answer("ready")
for line in sys.stdin:
    command, *arguments = line.rstrip("\n").split("\t")
    if command == "hold":
        held.enter_context(profile_custody_local_lock(Path(arguments[0]), timeout_seconds=30))
        answer("held")
    elif command == "release":
        held.close()
        answer("released")
    elif command == "crash":
        os._exit(70)
    elif command == "probe":
        try:
            with profile_custody_local_lock(Path(arguments[0]), timeout_seconds=float(arguments[1])):
                answer("acquired")
        except ProfileCustodyRecordError:
            answer("held-elsewhere")
    elif command == "ensure":
        ensure_profile_custody_local_directory(Path(arguments[0]))
        answer("ensured")
    elif command == "write":
        write_profile_custody_local_record(Path(arguments[0]), bytes.fromhex(arguments[1]), publish_once=False)
        answer("written")
    elif command == "read":
        raw = read_optional_profile_custody_local_record(Path(arguments[0]), maximum_bytes=int(arguments[1]))
        if raw is None:
            answer("absent")
        else:
            parsed = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
            answer(("canonical " if canonical_json_bytes(parsed) == raw else "noncanonical ") + raw.hex())
    elif command == "clear":
        clear_profile_custody_local_record(Path(arguments[0]))
        answer("cleared")
    elif command == "security":
        answer(security(Path(arguments[0])))
    else:
        answer("unknown " + command)
"#;

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

/// One Python peer process; dropping it closes its input so it exits normally.
struct Peer {
    child: Child,
    input: Option<ChildStdin>,
    output: Lines<BufReader<ChildStdout>>,
}

impl Peer {
    fn start() -> Self {
        let python = std::env::var_os("CADRUMO_TEST_PYTHON")
            .expect("CMake supplies the configured Python custody peer interpreter");
        let mut child = Command::new(python)
            .args(["-B", "-c", PEER])
            .current_dir(repository_root())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .expect("start the configured Python custody peer");
        let input = child.stdin.take();
        let output = BufReader::new(child.stdout.take().expect("peer stdout")).lines();
        let mut peer = Self {
            child,
            input,
            output,
        };
        assert_eq!(peer.line(), "ready");
        peer
    }

    fn line(&mut self) -> String {
        self.output
            .next()
            .expect("the Python peer ended without answering")
            .expect("peer output")
    }

    fn ask(&mut self, command: &str, arguments: &[&str]) -> String {
        let input = self.input.as_mut().expect("peer input");
        let mut line = command.to_owned();
        for argument in arguments {
            line.push('\t');
            line.push_str(argument);
        }
        writeln!(input, "{line}").expect("send to peer");
        input.flush().expect("flush to peer");
        self.line()
    }

    /// Make the peer end at once, as a crash would: nothing it holds is released by it.
    fn crash(mut self) {
        let input = self.input.as_mut().expect("peer input");
        writeln!(input, "crash").expect("send to peer");
        input.flush().expect("flush to peer");
        let status = self.child.wait().expect("peer exit");
        assert_eq!(status.code(), Some(70), "the peer crashed as told");
    }
}

impl Drop for Peer {
    fn drop(&mut self) {
        drop(self.input.take());
        let _ = self.child.wait();
    }
}

fn text(path: &Path) -> &str {
    path.to_str().expect("UTF-8 scratch path")
}

/// A storage root no other test uses, removed afterwards.
struct Root(PathBuf);

impl Root {
    fn new(label: &str) -> Self {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "cadrumo-manager-conformance-{label}-{}-{nanos}",
            std::process::id()
        ));
        std::fs::create_dir_all(&path).expect("storage root");
        Self(path)
    }
}

impl Drop for Root {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn marker(session: &str, set_at_ms: u64) -> QuitMarker {
    QuitMarker {
        user: "S-1-5-21-1004336348-1177238915-682003330-1001".into(),
        session: session.into(),
        set_at_ms,
    }
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

#[test]
fn a_python_holder_blocks_the_start_claim_until_it_releases() {
    let root = Root::new("python-holds");
    ensure_local_directory(&root.0.join(".runtime")).expect("runtime directory");
    let claim = start_claim_path(&root.0);
    let mut peer = Peer::start();
    assert_eq!(peer.ask("hold", &[text(&claim)]), "held");
    assert!(
        StartClaim::take(&root.0, Duration::from_millis(200))
            .expect("attempt")
            .is_none(),
        "the claim was taken while Python held it"
    );
    assert!(
        LocalLock::acquire(&claim, Duration::ZERO)
            .expect("attempt")
            .is_none()
    );
    assert_eq!(peer.ask("release", &[]), "released");
    assert!(
        StartClaim::take(&root.0, Duration::from_secs(5))
            .expect("attempt")
            .is_some(),
        "the released claim was not taken"
    );
}

#[test]
fn a_rust_holder_blocks_the_python_lock_until_it_releases() {
    let root = Root::new("rust-holds");
    let claim = start_claim_path(&root.0);
    let held = StartClaim::take(&root.0, Duration::ZERO)
        .expect("take")
        .expect("free");
    let mut peer = Peer::start();
    assert_eq!(peer.ask("probe", &[text(&claim), "0.3"]), "held-elsewhere");
    drop(held);
    assert_eq!(peer.ask("probe", &[text(&claim), "5"]), "acquired");
}

#[test]
fn a_crashed_python_holder_leaves_the_claim_free() {
    let root = Root::new("python-crash");
    ensure_local_directory(&root.0.join(".runtime")).expect("runtime directory");
    let claim = start_claim_path(&root.0);
    let mut peer = Peer::start();
    assert_eq!(peer.ask("hold", &[text(&claim)]), "held");
    assert!(
        StartClaim::take(&root.0, Duration::ZERO)
            .expect("attempt")
            .is_none()
    );
    peer.crash();
    assert!(
        StartClaim::take(&root.0, Duration::from_secs(5))
            .expect("attempt")
            .is_some(),
        "the kernel did not release a crashed holder's claim"
    );
}

#[test]
fn quit_markers_cross_between_python_and_rust_with_their_bytes() {
    let root = Root::new("records");
    let path = quit_marker_path(&root.0);
    let bound = MAXIMUM_QUIT_MARKER_BYTES.to_string();
    let mut peer = Peer::start();
    assert_eq!(
        peer.ask("ensure", &[text(&root.0.join(".runtime"))]),
        "ensured"
    );
    assert_eq!(peer.ask("read", &[text(&path), &bound]), "absent");

    // Python writes, Rust reads.
    let python_marker = marker("1", 1_790_000_000_000);
    let python_bytes = encode_quit_marker(&python_marker).expect("encode");
    assert_eq!(
        peer.ask("write", &[text(&path), &hex(&python_bytes)]),
        "written"
    );
    assert_eq!(read_quit_marker(&root.0), QuitState::Present(python_marker));

    // Rust replaces what Python wrote; Python reads the exact canonical bytes.
    let rust_marker = marker("2", 1_790_000_000_001);
    record_quit(&root.0, &rust_marker).expect("record");
    let rust_bytes = encode_quit_marker(&rust_marker).expect("encode");
    assert_eq!(
        peer.ask("read", &[text(&path), &bound]),
        format!("canonical {}", hex(&rust_bytes))
    );
    assert_eq!(
        read_optional_local_record(&path, MAXIMUM_QUIT_MARKER_BYTES).expect("read"),
        Some(rust_bytes)
    );

    // Each side clears what the other wrote.
    assert_eq!(peer.ask("clear", &[text(&path)]), "cleared");
    assert_eq!(read_quit_marker(&root.0), QuitState::Absent);
    assert_eq!(
        peer.ask("write", &[text(&path), &hex(&python_bytes)]),
        "written"
    );
    clear_quit(&root.0).expect("clear");
    assert_eq!(peer.ask("read", &[text(&path), &bound]), "absent");
    clear_local_record(&path).expect("clearing an absent record");

    // An oversized record written by Python is refused by Rust, as by Python.
    let mut oversized = python_bytes.clone();
    oversized.resize(
        usize::try_from(MAXIMUM_QUIT_MARKER_BYTES).expect("bound") + 1,
        b' ',
    );
    assert_eq!(
        peer.ask("write", &[text(&path), &hex(&oversized)]),
        "written"
    );
    assert_eq!(read_quit_marker(&root.0), QuitState::Unreadable);
}

#[test]
fn the_runtime_directory_gets_the_same_security_from_either_side() {
    let root = Root::new("security");
    let by_python = root.0.join("python");
    let by_rust = root.0.join("rust");
    std::fs::create_dir(&by_python).expect("python root");
    std::fs::create_dir(&by_rust).expect("rust root");
    let mut peer = Peer::start();
    assert_eq!(
        peer.ask("ensure", &[text(&by_python.join(".runtime"))]),
        "ensured"
    );
    ensure_local_directory(&by_rust.join(".runtime")).expect("ensure");
    let python = peer.ask("security", &[text(&by_python.join(".runtime"))]);
    let rust = peer.ask("security", &[text(&by_rust.join(".runtime"))]);
    assert_eq!(rust, python);
    if cfg!(windows) {
        assert_eq!(
            python,
            "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)"
        );
    } else {
        assert_eq!(python, "0o700");
    }
}
