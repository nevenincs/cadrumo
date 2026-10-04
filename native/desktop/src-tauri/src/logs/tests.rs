use super::{
    LogHub,
    format::Level,
    host,
    record::{BACKLOG, Entry, LogBatch, SourceKind},
    tail::{LINE_BYTES, SETTLE, Tail},
};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ErrorCode, Operation},
    process::status::{ProcessPhase, ProcessRole, Stream},
};
use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::ipc::{Channel, InvokeResponseBody};

// Tests that write lines themselves need a format; the live tests below take
// the one the packaged Python projects.
const FORMAT: &str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s";

struct Scratch(PathBuf);

impl Scratch {
    fn new(name: &str) -> Self {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir()
            .join("cadrumo-desktop-logs-tests")
            .join(format!("{name}-{}-{nanos}", std::process::id()));
        fs::create_dir_all(&path).unwrap();
        Self(path)
    }
    fn log(&self) -> PathBuf {
        self.0.join("cadrumo.log")
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn append(path: &Path, text: &[u8]) {
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .unwrap()
        .write_all(text)
        .unwrap();
}

fn line(index: usize) -> String {
    format!("2026-10-04 12:00:00,000 [INFO] cadrumo.test: rec-{index:06}\n")
}

fn messages(entries: &[Entry]) -> Vec<String> {
    entries.iter().map(|entry| entry.message.clone()).collect()
}

/// Polls once now and once after the pending record settles.
fn drain(tail: &mut Tail) -> (Vec<Entry>, SourceKind) {
    let now = Instant::now();
    let (mut entries, _) = tail.poll(now);
    let (settled, state) = tail.poll(now + SETTLE);
    entries.extend(settled);
    (entries, state.kind)
}

#[test]
fn missing_empty_available_and_unreadable_states_are_distinct() {
    let scratch = Scratch::new("states");
    let absent = Scratch::new("absent-directory");
    let mut gone = Tail::new(absent.0.join("logs").join("cadrumo.log"), FORMAT);
    assert_eq!(drain(&mut gone).1, SourceKind::Missing);

    let mut tail = Tail::new(scratch.log(), FORMAT);
    assert_eq!(drain(&mut tail), (vec![], SourceKind::Missing));
    File::create(scratch.log()).unwrap();
    assert_eq!(drain(&mut tail), (vec![], SourceKind::Available));
    append(&scratch.log(), line(1).as_bytes());
    let (entries, kind) = drain(&mut tail);
    assert_eq!(
        (messages(&entries), kind),
        (vec!["rec-000001".into()], SourceKind::Available)
    );

    let mut refused = Tail::new(scratch.log(), "%(message)s %(message)s");
    let (_, state) = refused.poll(Instant::now());
    assert_eq!(state.kind, SourceKind::Unreadable);
    assert_eq!(
        state.failure.map(|f| (f.code, f.operation)),
        Some((ErrorCode::EnvironmentFailed, Operation::Logging))
    );
}

#[cfg(windows)]
#[test]
fn a_share_deny_handle_makes_the_file_unreadable_until_released() {
    use std::os::windows::fs::OpenOptionsExt;
    let scratch = Scratch::new("share-deny");
    append(&scratch.log(), line(1).as_bytes());
    let mut tail = Tail::new(scratch.log(), FORMAT);
    assert_eq!(messages(&drain(&mut tail).0), ["rec-000001"]);
    let holder = OpenOptions::new()
        .read(true)
        .write(true)
        .share_mode(0)
        .open(scratch.log())
        .unwrap();
    // One failed poll can be a racing rotation; a second is reported.
    let (_, first) = tail.poll(Instant::now());
    assert_eq!(first.kind, SourceKind::Available);
    let (_, second) = tail.poll(Instant::now());
    assert_eq!(second.kind, SourceKind::Unreadable);
    let failure = second.failure.unwrap();
    assert_eq!(
        (failure.code, failure.operation),
        (ErrorCode::ReadFailed, Operation::Logging)
    );
    assert_eq!(second.detail, scratch.log().display().to_string());
    drop(holder);
    append(&scratch.log(), line(2).as_bytes());
    let (entries, kind) = drain(&mut tail);
    assert_eq!(
        (messages(&entries), kind),
        (vec!["rec-000002".into()], SourceKind::Available)
    );
}

#[test]
fn continuation_lines_crlf_truncation_and_lossy_utf8() {
    let scratch = Scratch::new("lines");
    let mut bytes = Vec::new();
    bytes.extend_from_slice(b"orphan before any record\r\n");
    bytes.extend_from_slice(
        b"2026-10-04 12:00:00,001 [ERROR] cadrumo.x: failed\r\nTraceback (most recent call last):\r\n  File \"a.py\", line 1, in <module>\r\nKeyError: 'k'\r\n",
    );
    bytes.extend_from_slice(b"2026-10-04 12:00:00,002 [WARNING] cadrumo.y: bad \xff byte\n");
    bytes.extend_from_slice(b"2026-10-04 12:00:00,003 [DEBUG] cadrumo.z: ");
    bytes.extend(std::iter::repeat_n(b'x', LINE_BYTES * 2));
    bytes.extend_from_slice(b"\n2026-10-04 12:00:00,004 [CRITICAL] root: last");
    append(&scratch.log(), &bytes);
    let mut tail = Tail::new(scratch.log(), FORMAT);
    let now = Instant::now();
    let (early, _) = tail.poll(now);
    // The unterminated last line and its record wait for more bytes.
    assert_eq!(early.len(), 3);
    let (late, _) = tail.poll(now + SETTLE);
    let entries: Vec<Entry> = early.into_iter().chain(late).collect();
    assert_eq!(entries.len(), 5);
    assert_eq!(entries[0].message, "orphan before any record");
    assert_eq!(
        (entries[0].level, entries[0].logger.as_deref()),
        (None, None)
    );
    assert_eq!(entries[1].message, "failed");
    assert_eq!(entries[1].level, Some(Level::Error));
    assert_eq!(entries[1].timestamp, "2026-10-04 12:00:00,001");
    assert_eq!(entries[1].timestamp_ms, None);
    assert_eq!(
        entries[1].detail.as_deref(),
        Some(
            "Traceback (most recent call last):\n  File \"a.py\", line 1, in <module>\nKeyError: 'k'"
        )
    );
    assert_eq!(entries[2].message, "bad \u{FFFD} byte");
    assert_eq!(entries[3].logger.as_deref(), Some("cadrumo.z"));
    let truncated = LINE_BYTES - "2026-10-04 12:00:00,003 [DEBUG] cadrumo.z: ".len();
    assert_eq!(entries[3].message, "x".repeat(truncated));
    assert_eq!(
        (entries[4].message.as_str(), entries[4].level),
        ("last", Some(Level::Critical))
    );
    assert!(
        entries
            .iter()
            .all(|entry| entry.source == "python" && entry.process.is_none())
    );
}

#[test]
fn skipped_partial_late_and_racing_rotations_lose_and_repeat_nothing() {
    let scratch = Scratch::new("rotation");
    let base = scratch.log();
    let rotated = |index: u32| scratch.0.join(format!("cadrumo.log.{index}"));
    let mut tail = Tail::new(base.clone(), FORMAT);
    let mut seen = Vec::new();
    let mut poll = |tail: &mut Tail| {
        let (entries, kind) = drain(tail);
        assert_eq!(kind, SourceKind::Available);
        seen.extend(messages(&entries));
    };
    for index in 0..3 {
        append(&base, line(index).as_bytes());
    }
    poll(&mut tail);
    // Rotation: base becomes .1 after one more line, then a new base.
    append(&base, line(3).as_bytes());
    fs::rename(&base, rotated(1)).unwrap();
    append(&base, line(4).as_bytes());
    poll(&mut tail);
    // Partial rotation: .1 shifted to .2, base rename skipped.
    fs::rename(rotated(1), rotated(2)).unwrap();
    append(&base, line(5).as_bytes());
    poll(&mut tail);
    // Late rotation of the skipped base, plus a writer that still appends to
    // the renamed file, then two rotations between polls.
    fs::rename(&base, rotated(1)).unwrap();
    append(&rotated(1), line(6).as_bytes());
    append(&base, line(7).as_bytes());
    fs::rename(rotated(2), rotated(3)).unwrap();
    fs::rename(rotated(1), rotated(2)).unwrap();
    fs::rename(&base, rotated(1)).unwrap();
    append(&base, line(8).as_bytes());
    poll(&mut tail);
    // Base absent mid-rotation: still available through the rotations.
    fs::rename(&base, rotated(4)).unwrap();
    poll(&mut tail);
    append(&base, line(9).as_bytes());
    poll(&mut tail);
    assert_eq!(
        seen,
        (0..10).map(|i| format!("rec-{i:06}")).collect::<Vec<_>>()
    );
}

#[test]
fn a_new_file_waits_while_a_racing_rotation_hides_the_current_one() {
    let scratch = Scratch::new("hidden");
    let base = scratch.log();
    let hidden = scratch.0.join("moving");
    let mut tail = Tail::new(base.clone(), FORMAT);
    append(&base, line(0).as_bytes());
    assert_eq!(messages(&drain(&mut tail).0), ["rec-000000"]);
    // The poll lists the directory while the current file is between names.
    append(&base, line(1).as_bytes());
    fs::rename(&base, &hidden).unwrap();
    append(&base, line(2).as_bytes());
    assert!(
        drain(&mut tail).0.is_empty(),
        "successor read before predecessor"
    );
    fs::rename(&hidden, scratch.0.join("cadrumo.log.1")).unwrap();
    assert_eq!(messages(&drain(&mut tail).0), ["rec-000001", "rec-000002"]);
    // A current file that is gone for good delays its successor only briefly.
    fs::rename(&base, &hidden).unwrap();
    fs::remove_file(&hidden).unwrap();
    append(&base, line(3).as_bytes());
    let mut polls = 0;
    let mut seen = Vec::new();
    while seen.is_empty() {
        polls += 1;
        assert!(polls <= 10, "deferred without bound");
        // drain() settles at a future instant; let real time catch up.
        std::thread::sleep(SETTLE);
        seen = messages(&drain(&mut tail).0);
    }
    assert_eq!(seen, ["rec-000003"]);
}

#[test]
fn first_poll_reads_a_bounded_window_and_resynchronises() {
    let scratch = Scratch::new("window");
    let mut bytes = Vec::new();
    // Each record carries a continuation line, so a window that starts inside
    // a record must not attach an orphaned continuation.
    let mut index = 0;
    while bytes.len() < 17 * 1024 * 1024 {
        bytes.extend_from_slice(line(index).as_bytes());
        bytes.extend_from_slice(b"  continuation\n");
        index += 1;
    }
    append(&scratch.log(), &bytes);
    let mut tail = Tail::new(scratch.log(), FORMAT);
    let (entries, _) = drain(&mut tail);
    assert!(entries.len() < index);
    assert_eq!(
        entries.last().unwrap().message,
        format!("rec-{:06}", index - 1)
    );
    let first: usize = entries[0].message[4..].parse().unwrap();
    assert_eq!(entries.len(), index - first);
    assert!(
        entries
            .iter()
            .all(|entry| entry.detail.as_deref() == Some("  continuation"))
    );
}

type Frames = Arc<Mutex<Vec<(Instant, serde_json::Value)>>>;

/// A real IPC channel whose frames are kept with their arrival time.
fn channel() -> (Channel<LogBatch>, Frames) {
    let frames: Frames = Arc::default();
    let into = frames.clone();
    let channel = Channel::new(move |body| {
        let InvokeResponseBody::Json(json) = body else {
            panic!("log batches are JSON");
        };
        into.lock()
            .unwrap()
            .push((Instant::now(), serde_json::from_str(&json).unwrap()));
        Ok(())
    });
    (channel, frames)
}

fn start(hub: &Arc<LogHub>) {
    let poller = Arc::downgrade(hub);
    std::thread::spawn(move || LogHub::run(poller));
}

fn subscribe(hub: &LogHub) -> (u64, Frames) {
    let (channel, frames) = channel();
    let subscribed = hub.subscribe(Box::new(move |batch| channel.send(batch).is_ok()));
    (subscribed.subscription, frames)
}

#[test]
fn backlog_spans_rotations_in_order() {
    let scratch = Scratch::new("backlog");
    for (file, range) in [
        ("cadrumo.log.2", 0..4_000),
        ("cadrumo.log.1", 4_000..8_000),
        ("cadrumo.log", 8_000..12_000),
    ] {
        let text: String = range.map(line).collect();
        append(&scratch.0.join(file), text.as_bytes());
    }
    let hub = Arc::new(LogHub::new(
        scratch.log(),
        FORMAT,
        Arc::new(Diagnostics::default()),
    ));
    // The last record of the log file settles once the file is quiet; the
    // backlog is taken when the subscription starts.
    let start = Instant::now();
    hub.tick(start);
    hub.tick(start + SETTLE);
    let (_, frames) = subscribe(&hub);
    hub.tick(start + SETTLE * 2);
    let frames = frames.lock().unwrap();
    assert_eq!(frames.len(), 1);
    let records = frames[0].1["records"].as_array().unwrap();
    assert_eq!(records.len(), BACKLOG);
    let expected: Vec<String> = (12_000 - BACKLOG..12_000)
        .map(|i| format!("rec-{i:06}"))
        .collect();
    let received: Vec<&str> = records
        .iter()
        .map(|r| r["message"].as_str().unwrap())
        .collect();
    assert_eq!(received, expected);
    let first = &records[0];
    assert_eq!(first["source"], "python");
    assert_eq!(first["timestamp"], "2026-10-04 12:00:00,000");
    assert!(first["timestampMs"].is_null() && first["process"].is_null());
    assert_eq!(first["level"], "INFO");
    assert_eq!(first["logger"], "cadrumo.test");
    assert_eq!(frames[0].1["state"]["kind"], "available");
}

#[test]
fn a_flood_is_delivered_at_most_ten_batches_a_second_and_losses_are_counted() {
    let scratch = Scratch::new("flood");
    append(&scratch.log(), line(0).as_bytes());
    let hub = Arc::new(LogHub::new(
        scratch.log(),
        FORMAT,
        Arc::new(Diagnostics::default()),
    ));
    let (subscription, frames) = subscribe(&hub);
    start(&hub);
    let path = scratch.log();
    let writer = std::thread::spawn(move || {
        let mut file = OpenOptions::new().append(true).open(path).unwrap();
        let deadline = Instant::now() + Duration::from_millis(2_500);
        let mut written = 1;
        // About 100,000 records a second: more than one batch a tick holds.
        while Instant::now() < deadline {
            let chunk: String = (written..written + 500).map(line).collect();
            file.write_all(chunk.as_bytes()).unwrap();
            written += 500;
            std::thread::sleep(Duration::from_millis(5));
        }
        written
    });
    let written = writer.join().unwrap() as u64;
    let deadline = Instant::now() + Duration::from_secs(30);
    while accounted_of(&frames.lock().unwrap()) < written && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(50));
    }
    hub.unsubscribe(subscription).unwrap();
    let frames = frames.lock().unwrap();
    assert_eq!(
        accounted_of(&frames),
        written,
        "every record delivered or counted dropped"
    );
    let times: Vec<Instant> = frames.iter().map(|(time, _)| *time).collect();
    for (index, first) in times.iter().enumerate() {
        let within = times[index..]
            .iter()
            .take_while(|time| time.duration_since(*first) < Duration::from_secs(1))
            .count();
        assert!(within <= 10, "{within} batches within one second");
    }
    let mut next = None;
    for (_, batch) in frames.iter() {
        for record in batch["records"].as_array().unwrap() {
            let seq = record["seq"].as_u64().unwrap();
            assert!(
                next.is_none_or(|next| seq >= next),
                "sequence went backwards"
            );
            next = Some(seq + 1);
        }
    }
    eprintln!(
        "flood: {written} records, {} batches, {} dropped",
        frames.len(),
        frames
            .iter()
            .map(|(_, b)| b["dropped"].as_u64().unwrap())
            .sum::<u64>()
    );
}

fn accounted_of(frames: &[(Instant, serde_json::Value)]) -> u64 {
    frames
        .iter()
        .map(|(_, batch)| {
            batch["records"].as_array().unwrap().len() as u64 + batch["dropped"].as_u64().unwrap()
        })
        .sum()
}

#[test]
fn live_pty_bytes_never_reach_a_batch_while_host_events_do() {
    use portable_pty::{CommandBuilder, PtySize, native_pty_system};
    use std::io::Read;
    let marker = format!("PTY-MARKER-{}", std::process::id());
    let scratch = Scratch::new("pty");
    let diagnostics = Arc::new(Diagnostics::default());
    let hub = Arc::new(LogHub::new(scratch.log(), FORMAT, diagnostics.clone()));
    let (_, frames) = subscribe(&hub);
    start(&hub);
    let pair = native_pty_system()
        .openpty(PtySize {
            rows: 24,
            cols: 80,
            pixel_width: 0,
            pixel_height: 0,
        })
        .unwrap();
    let mut command = if cfg!(windows) {
        let mut command = CommandBuilder::new("cmd.exe");
        command.args(["/d", "/c", "echo", &marker]);
        command
    } else {
        let mut command = CommandBuilder::new("sh");
        command.args(["-c", &format!("echo {marker}")]);
        command
    };
    command.cwd(&scratch.0);
    let mut child = pair.slave.spawn_command(command).unwrap();
    drop(pair.slave);
    let id = diagnostics.start(child.process_id().unwrap(), ProcessRole::Tui);
    let mut reader = pair.master.try_clone_reader().unwrap();
    let mut writer = pair.master.take_writer().unwrap();
    let (sender, received) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let mut buffer = [0; 8192];
        while let Ok(count) = reader.read(&mut buffer) {
            if count == 0 || sender.send(buffer[..count].to_vec()).is_err() {
                return;
            }
        }
    });
    let mut output = Vec::new();
    let deadline = Instant::now() + Duration::from_secs(20);
    while !String::from_utf8_lossy(&output).contains(&marker) && Instant::now() < deadline {
        if let Ok(bytes) = received.recv_timeout(Duration::from_millis(100)) {
            // What a terminal session capturing into diagnostics would do.
            diagnostics.capture(id, Stream::Terminal, &bytes);
            // ConPTY waits for a cursor position report before output.
            if bytes.windows(4).any(|window| window == b"\x1b[6n") {
                writer.write_all(b"\x1b[1;1R").unwrap();
            }
            output.extend(bytes);
        }
    }
    assert!(
        String::from_utf8_lossy(&output).contains(&marker),
        "no PTY output"
    );
    let status = child.wait().unwrap();
    diagnostics.finish(id, Some(status.exit_code() as i32), ProcessPhase::Exited);
    drop(pair.master);
    assert!(
        diagnostics
            .snapshot(0)
            .output
            .iter()
            .any(|chunk| String::from_utf8_lossy(&chunk.bytes).contains(&marker)),
        "the bytes were available to leak"
    );
    std::thread::sleep(Duration::from_millis(500));
    let frames = frames.lock().unwrap();
    let serialized: String = frames.iter().map(|(_, batch)| batch.to_string()).collect();
    assert!(!serialized.contains(&marker));
    let host: Vec<&serde_json::Value> = frames
        .iter()
        .flat_map(|(_, batch)| batch["records"].as_array().unwrap())
        .filter(|record| record["source"] == host::SOURCE)
        .collect();
    assert_eq!(host.len(), 2, "{host:?}");
    assert!(
        host[0]["message"]
            .as_str()
            .unwrap()
            .starts_with("child_started: tui pid")
    );
    assert!(
        host[1]["message"]
            .as_str()
            .unwrap()
            .starts_with("child_exited: tui pid")
    );
    assert_eq!(host[1]["process"]["role"], "tui");
    assert_eq!(host[1]["process"]["pid"], host[0]["process"]["pid"]);
    assert!(host.iter().all(|record| record["timestampMs"].is_u64()));
}

#[cfg(feature = "live-package-tests")]
mod live {
    use super::*;
    use std::process::{Command, Stdio};

    const PRELUDE: &str = r#"
import logging, logging.handlers, sys
from cadrumo.core.logging import configure_logging, default_log_file_path
configure_logging()
handler = next(h for h in logging.getLogger().handlers
               if isinstance(h, logging.handlers.RotatingFileHandler))
print(default_log_file_path(), flush=True)
"#;

    struct Package {
        executable: PathBuf,
        environment: Vec<(std::ffi::OsString, std::ffi::OsString)>,
        format: String,
    }

    /// The packaged interpreter with the projected child environment, its
    /// pinned storage root moved into `storage`.
    async fn package(storage: &Path) -> Package {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let parent = crate::environment::Parent::current().unwrap();
        let launch = crate::environment::resolve(root, &parent, Arc::new(Diagnostics::default()))
            .await
            .unwrap();
        let pinned = launch.working_directory.as_os_str();
        let environment = launch
            .child
            .environment()
            .iter()
            .map(|(key, value)| {
                if value.as_os_str() == pinned {
                    (key.clone(), storage.as_os_str().to_owned())
                } else {
                    (key.clone(), value.clone())
                }
            })
            .collect();
        Package {
            executable: launch.child.executable().to_owned(),
            environment,
            format: launch.log_format.clone(),
        }
    }

    impl Package {
        fn command(&self, script: &str, directory: &Path) -> Command {
            let mut command = Command::new(&self.executable);
            command
                .arg("-c")
                .arg(format!("{PRELUDE}\n{script}"))
                .env_clear()
                .envs(self.environment.iter().map(|(k, v)| (k, v)))
                .current_dir(directory)
                .stdin(Stdio::null());
            command
        }
    }

    fn reported_log(stdout: &[u8], storage: &Path) -> PathBuf {
        let path = PathBuf::from(
            String::from_utf8_lossy(stdout)
                .lines()
                .next()
                .unwrap()
                .trim(),
        );
        assert!(path.starts_with(storage), "{path:?} outside {storage:?}");
        path
    }

    #[tokio::test]
    async fn real_python_logging_lines_parse_with_the_projected_format() {
        let scratch = Scratch::new("python-lines");
        let package = package(&scratch.0).await;
        let output = package
            .command(
                r#"
log = logging.getLogger("cadrumo.s06.probe")
log.info("plain á record")
try:
    {}["missing"]
except KeyError:
    log.exception("with traceback")
record = logging.LogRecord("cadrumo.s06.probe", logging.WARNING, "probe", 1,
                           "bad \udcff byte", None, None)
handler.acquire()
try:
    handler.flush()
    handler.stream.flush()
    handler.stream.buffer.write((handler.format(record) + "\n").encode("utf-8", "surrogateescape"))
    handler.stream.buffer.flush()
finally:
    handler.release()
log.info("long " * 4000)
log.error("after")
"#,
                &scratch.0,
            )
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let log = reported_log(&output.stdout, &scratch.0);
        let mut tail = Tail::new(log, &package.format);
        let (entries, kind) = drain(&mut tail);
        assert_eq!(kind, SourceKind::Available);
        let probe: Vec<&Entry> = entries
            .iter()
            .filter(|entry| entry.logger.as_deref() == Some("cadrumo.s06.probe"))
            .collect();
        assert_eq!(probe.len(), 5, "{probe:#?}");
        assert_eq!(probe[0].message, "plain á record");
        assert_eq!(probe[0].level, Some(Level::Info));
        assert!(!probe[0].timestamp.is_empty() && probe[0].timestamp_ms.is_none());
        assert_eq!(probe[1].message, "with traceback");
        assert_eq!(probe[1].level, Some(Level::Error));
        let detail = probe[1].detail.as_deref().unwrap();
        assert!(
            detail.starts_with("Traceback (most recent call last):"),
            "{detail}"
        );
        assert!(detail.ends_with("KeyError: 'missing'"), "{detail}");
        assert_eq!(probe[2].message, "bad \u{FFFD} byte");
        assert_eq!(probe[2].level, Some(Level::Warning));
        // The line, not the message, is truncated to LINE_BYTES.
        let long = &probe[3].message;
        assert!(long.starts_with("long long "));
        assert_eq!(
            long.len() + probe[3].timestamp.len() + " [INFO] cadrumo.s06.probe: ".len(),
            LINE_BYTES
        );
        assert_eq!(probe[4].message, "after");
        assert!(entries.iter().all(|entry| entry.source == "python"));
    }

    const HOLDER: &str = r#"
log = logging.getLogger("cadrumo.s06.holder")
log.info("holder-start")
sys.stdin.read()
log.info("holder-end")
"#;

    const WRITER: &str = r#"
import time
handler.maxBytes = 4096
handler.backupCount = 200
log = logging.getLogger("cadrumo.s06.writer")
total = 3000
for index in range(total):
    if index % 97 == 0:
        try:
            raise ValueError(f"boom {index}")
        except ValueError:
            log.exception("rec-%05d failed", index)
    else:
        log.info("rec-%05d", index)
    if index == total // 2:
        print("half", flush=True)
    time.sleep(0.001)
"#;

    fn ours(entries: &[Entry]) -> Vec<String> {
        entries
            .iter()
            .filter(|entry| {
                entry
                    .logger
                    .as_deref()
                    .is_some_and(|logger| logger.starts_with("cadrumo.s06."))
            })
            .map(|entry| entry.message.clone())
            .collect()
    }

    #[tokio::test]
    async fn real_rotation_across_processes_while_tailing() {
        use std::io::{BufRead, BufReader};
        let scratch = Scratch::new("python-rotation");
        let package = package(&scratch.0).await;
        let mut holder = package
            .command(HOLDER, &scratch.0)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(File::create(scratch.0.join("holder.err")).unwrap())
            .spawn()
            .unwrap();
        let mut holder_out = BufReader::new(holder.stdout.take().unwrap());
        let mut reported = String::new();
        holder_out.read_line(&mut reported).unwrap();
        let log = reported_log(reported.as_bytes(), &scratch.0);
        let deadline = Instant::now() + Duration::from_secs(30);
        while !fs::read_to_string(&log).is_ok_and(|text| text.contains("holder-start")) {
            assert!(Instant::now() < deadline, "holder never logged");
            std::thread::sleep(Duration::from_millis(20));
        }
        let mut tail = Tail::new(log.clone(), &package.format);
        let mut live = Vec::new();
        let mut states = Vec::new();
        let mut writer = package
            .command(WRITER, &scratch.0)
            .stdout(Stdio::piped())
            .stderr(File::create(scratch.0.join("writer.err")).unwrap())
            .spawn()
            .unwrap();
        let writer_out = writer.stdout.take().unwrap();
        let mut release = holder.stdin.take();
        let releaser = std::thread::spawn(move || {
            for line in BufReader::new(writer_out).lines() {
                if line.unwrap() == "half" {
                    // Releasing the holder lets the next rotation succeed late.
                    release.take();
                }
            }
        });
        while writer.try_wait().unwrap().is_none() {
            let (entries, state) = tail.poll(Instant::now());
            live.extend(entries);
            states.push(state.kind);
            std::thread::sleep(Duration::from_millis(15));
        }
        assert!(writer.wait().unwrap().success());
        assert!(holder.wait().unwrap().success());
        releaser.join().unwrap();
        let (rest, _) = drain(&mut tail);
        live.extend(rest);
        assert!(
            states.iter().all(|kind| *kind == SourceKind::Available),
            "{states:?}"
        );

        let rotations = fs::read_dir(log.parent().unwrap())
            .unwrap()
            .filter(|entry| {
                entry
                    .as_ref()
                    .unwrap()
                    .file_name()
                    .to_string_lossy()
                    .starts_with("cadrumo.log.")
            })
            .count();
        let writer_errors = fs::read_to_string(scratch.0.join("writer.err")).unwrap();
        let tail_of = |text: &str| text[text.len().saturating_sub(3000)..].to_owned();
        assert!(
            rotations >= 2,
            "only {rotations} rotations; {} skipped; holder: {}; live: {:?}; writer: {}",
            writer_errors.matches("PermissionError").count(),
            fs::read_to_string(scratch.0.join("holder.err")).unwrap(),
            ours(&live)
                .iter()
                .filter(|m| m.starts_with("holder"))
                .collect::<Vec<_>>(),
            tail_of(&writer_errors)
        );
        if cfg!(windows) {
            assert!(
                writer_errors.contains("PermissionError"),
                "no rotation was skipped"
            );
        }

        // Every record in the files was read live exactly once, in file order.
        let mut fresh = Tail::new(log.clone(), &package.format);
        let (all, _) = drain(&mut fresh);
        let expected = ours(&all);
        let received = ours(&live);
        let first = received
            .iter()
            .zip(&expected)
            .position(|(left, right)| left != right)
            .unwrap_or(received.len().min(expected.len()));
        assert_eq!(
            received,
            expected,
            "live {} vs files {}; first difference at {first}: live {:?} files {:?}",
            received.len(),
            expected.len(),
            &received[first.saturating_sub(2)..(first + 3).min(received.len())],
            &expected[first.saturating_sub(2)..(first + 3).min(expected.len())],
        );
        let indices: Vec<u32> = received
            .iter()
            .filter_map(|message| message.strip_prefix("rec-"))
            .map(|rest| rest[..5].parse().unwrap())
            .collect();
        assert!(indices.windows(2).all(|pair| pair[0] < pair[1]));
        assert!(received.contains(&"holder-end".to_owned()));
        let failed: Vec<&Entry> = live
            .iter()
            .filter(|entry| entry.message.ends_with(" failed"))
            .collect();
        assert!(!failed.is_empty());
        assert!(failed.iter().all(|entry| {
            entry
                .detail
                .as_deref()
                .is_some_and(|detail| detail.contains("ValueError: boom"))
        }));

        // A later subscriber's backlog spans the rotations in the same order.
        let hub = LogHub::new(log, &package.format, Arc::new(Diagnostics::default()));
        let (_, frames) = subscribe(&hub);
        hub.tick(Instant::now() + SETTLE);
        let frames = frames.lock().unwrap();
        let backlog: Vec<String> = frames
            .iter()
            .flat_map(|(_, batch)| batch["records"].as_array().unwrap().clone())
            .filter(|record| {
                record["logger"]
                    .as_str()
                    .is_some_and(|logger| logger.starts_with("cadrumo.s06."))
            })
            .map(|record| record["message"].as_str().unwrap().to_owned())
            .collect();
        assert_eq!(backlog, expected);
        eprintln!(
            "rotation: {} records over {rotations} rotations",
            expected.len()
        );
    }
}
