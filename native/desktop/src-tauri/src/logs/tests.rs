use super::{
    LogHub, Poller, TICK,
    format::Level,
    host,
    record::{BACKLOG, BATCH_BYTES, Entry, LogBatch, SourceKind},
    tail::{self, LINE_BYTES, SETTLE, Tail},
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
fn projected_context_survives_partial_writes_and_multiline_records() {
    let scratch = Scratch::new("diagnostic-context");
    let format = format!("{FORMAT} | %(diagnostic_context)s");
    let mut tail = Tail::new(scratch.log(), &format);
    let now = Instant::now();
    append(&scratch.log(), b"2026-10-04T12:30:01.042Z [ERROR] cadrumo.runtime: admission failed | {\"diagnostic_id\":\"attempt-7\",");
    assert!(tail.poll(now).0.is_empty());
    append(&scratch.log(), b"\"process_id\":412,\"process_role\":\"runtime_worker\",\"reason_code\":\"runtime_unavailable\"}\nTraceback (most recent call last):\nRuntimeError: refused\n");
    assert!(tail.poll(now + Duration::from_millis(1)).0.is_empty());
    let (entries, _) = tail.poll(now + SETTLE + Duration::from_millis(1));
    assert_eq!(entries.len(), 1);
    assert_eq!(entries[0].timestamp_ms, Some(1_791_117_001_042));
    assert_eq!(entries[0].message, "admission failed");
    assert_eq!(entries[0].context["diagnostic_id"], "attempt-7");
    assert_eq!(entries[0].context["reason_code"], "runtime_unavailable");
    assert_eq!(
        entries[0]
            .process
            .as_ref()
            .map(|process| (process.role.as_str(), process.pid)),
        Some(("runtime_worker", 412))
    );
    assert_eq!(
        entries[0].detail.as_deref(),
        Some("Traceback (most recent call last):\nRuntimeError: refused")
    );
    append(&scratch.log(), line(5).as_bytes());
    let (legacy, _) = drain(&mut tail);
    assert_eq!(legacy[0].message, "rec-000005");
    assert_eq!(legacy[0].timestamp_ms, None);
    assert!(legacy[0].process.is_none() && legacy[0].context.is_empty());
    let long = format!(
        "2026-10-04T12:30:01.042Z [INFO] cadrumo.runtime: {} | {{\"process_id\":412}}\n",
        "x".repeat(LINE_BYTES * 2)
    );
    append(&scratch.log(), long.as_bytes());
    let (truncated, _) = drain(&mut tail);
    assert_eq!(truncated.len(), 1);
    assert_eq!(truncated[0].logger.as_deref(), Some("cadrumo.runtime"));
    assert!(truncated[0].message.starts_with("xxxx") && truncated[0].context.is_empty());
}

#[test]
fn multiline_message_continuations_preserve_the_headers_context() {
    let scratch = Scratch::new("multiline-message-context");
    let format = format!("{FORMAT} | %(diagnostic_context)s");
    append(
        &scratch.log(),
        b"2026-10-04T12:30:01.042Z [INFO] cadrumo.runtime: first | {\"diagnostic_id\":\"attempt-7\",\"process_id\":412,\"process_role\":\"runtime_worker\"}\nsecond | {\"process_id\":999,\"process_role\":\"foreign\"}\nthird\n",
    );
    let mut tail = Tail::new(scratch.log(), &format);
    let (entries, _) = drain(&mut tail);
    assert_eq!(entries.len(), 1);
    let entry = &entries[0];
    assert_eq!(entry.message, "first");
    assert_eq!(entry.context["diagnostic_id"], "attempt-7");
    assert_eq!(entry.context["process_id"], 412);
    assert_eq!(
        entry
            .process
            .as_ref()
            .map(|process| (process.role.as_str(), process.pid)),
        Some(("runtime_worker", 412))
    );
    assert_eq!(
        entry.detail.as_deref(),
        Some("second | {\"process_id\":999,\"process_role\":\"foreign\"}\nthird")
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

/// Runs the poller on its own thread until the hub is dropped.
fn start(poller: Poller) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || poller.run())
}

fn hub(log: PathBuf, diagnostics: Arc<Diagnostics>) -> (LogHub, Poller) {
    LogHub::new(
        log.clone(),
        log.with_file_name("cadrumo-manager.log"),
        FORMAT,
        diagnostics,
    )
}

fn subscribe(hub: &LogHub) -> (u64, Frames) {
    let (channel, frames) = channel();
    let subscribed = hub.subscribe(Arc::new(move |batch| channel.send(batch).is_ok()));
    (subscribed.subscription, frames)
}

fn records_of(frames: &[(Instant, serde_json::Value)]) -> Vec<serde_json::Value> {
    frames
        .iter()
        .flat_map(|(_, batch)| batch["records"].as_array().unwrap().clone())
        .collect()
}

fn messages_of(records: &[serde_json::Value]) -> Vec<String> {
    records
        .iter()
        .map(|record| record["message"].as_str().unwrap().to_owned())
        .collect()
}

/// Waits until a frame satisfies `done`, or fails after `limit`.
fn wait_for(
    frames: &Frames,
    limit: Duration,
    done: impl Fn(&[(Instant, serde_json::Value)]) -> bool,
) {
    let deadline = Instant::now() + limit;
    while !done(&frames.lock().unwrap()) {
        assert!(Instant::now() < deadline, "no such frame within {limit:?}");
        std::thread::sleep(Duration::from_millis(10));
    }
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
    let (hub, mut poller) = hub(scratch.log(), Arc::new(Diagnostics::default()));
    // The subscription starts before anything was read; its backlog is taken
    // at its first delivery. The last record settles once the file is quiet.
    let (_, frames) = subscribe(&hub);
    let start = Instant::now();
    poller.tick(start);
    poller.tick(start + SETTLE);
    let frames = frames.lock().unwrap();
    assert_eq!(frames.len(), 2);
    assert_eq!(
        messages_of(frames[1].1["records"].as_array().unwrap()),
        ["rec-011999"]
    );
    let records = frames[0].1["records"].as_array().unwrap();
    assert_eq!(records.len(), BACKLOG);
    let expected: Vec<String> = (11_999 - BACKLOG..11_999)
        .map(|i| format!("rec-{i:06}"))
        .collect();
    assert_eq!(messages_of(records), expected);
    let first = &records[0];
    assert_eq!(first["source"], "python");
    assert_eq!(first["timestamp"], "2026-10-04 12:00:00,000");
    assert!(first["timestampMs"].is_null() && first["process"].is_null());
    assert_eq!(first["level"], "INFO");
    assert_eq!(first["logger"], "cadrumo.test");
    assert_eq!(frames[0].1["states"]["python"]["kind"], "available");
}

#[test]
fn a_flood_is_delivered_at_most_ten_batches_a_second_and_losses_are_counted() {
    let scratch = Scratch::new("flood");
    append(&scratch.log(), line(0).as_bytes());
    let (hub, poller) = hub(scratch.log(), Arc::new(Diagnostics::default()));
    let (subscription, frames) = subscribe(&hub);
    start(poller);
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
    let (hub, poller) = hub(scratch.log(), diagnostics.clone());
    let (_, frames) = subscribe(&hub);
    start(poller);
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

const TRACEBACK: &str = "Traceback (most recent call last):\n  File \"cadrumo/probe.py\", line 10, in run\n    raise ValueError(value)\nValueError: \t\"quoted\" value\n";

/// Writes records with a traceback each until the file holds `bytes`, and
/// returns how many records it holds.
fn traceback_log(path: &Path, bytes: usize) -> usize {
    let mut text = String::with_capacity(bytes + 4096);
    let mut count = 0;
    while text.len() < bytes {
        text.push_str(&line(count));
        text.push_str(TRACEBACK);
        count += 1;
    }
    append(path, text.as_bytes());
    count
}

#[test]
fn subscribing_returns_while_a_large_first_read_runs_on_the_poller() {
    let scratch = Scratch::new("large");
    // Larger than the first read's window, so the read is as long as it gets.
    let count = traceback_log(&scratch.log(), 24 * 1024 * 1024);
    // The first open of a freshly written file can wait on a virus scanner;
    // one open here keeps that out of the bound below.
    std::io::Read::read(&mut File::open(scratch.log()).unwrap(), &mut [0; 1024]).unwrap();
    let (hub, poller) = hub(scratch.log(), Arc::new(Diagnostics::default()));
    let io = poller.tail.io.clone();
    start(poller);
    let began = Instant::now();
    let (_, frames) = subscribe(&hub);
    let subscribed = began.elapsed();
    // Once the poller has opened the files, the commands and the page-load
    // hook take the shared lock while it reads.
    while io_of(&io).1 == 0 {
        assert!(began.elapsed() < Duration::from_secs(30), "no poll began");
        std::thread::sleep(Duration::from_millis(1));
    }
    let other = Instant::now();
    let (second, _) = subscribe(&hub);
    hub.unsubscribe(second).unwrap();
    hub.clear_subscriptions();
    let (_, frames_after_clear) = subscribe(&hub);
    let locked = other.elapsed();
    let read_pending = frames_after_clear.lock().unwrap().is_empty();
    wait_for(&frames_after_clear, Duration::from_secs(120), |frames| {
        !frames.is_empty()
    });
    let first_batch = began.elapsed();
    eprintln!(
        "large: {count} records; subscribe {subscribed:?}, lock users {locked:?}, first batch {first_batch:?}"
    );
    assert!(
        read_pending,
        "the first read finished before the lock users"
    );
    assert!(
        subscribed < Duration::from_millis(100),
        "subscribe took {subscribed:?}"
    );
    assert!(
        locked < Duration::from_millis(100),
        "lock users waited {locked:?}"
    );
    assert!(frames.lock().unwrap().is_empty(), "a cleared subscription");
    // The backlog ends at the newest settled record, contiguous and in order.
    let last = format!("rec-{:06}", count - 1);
    wait_for(&frames_after_clear, Duration::from_secs(60), |frames| {
        messages_of(&records_of(frames)).contains(&last)
    });
    let received = messages_of(&records_of(&frames_after_clear.lock().unwrap()));
    let first: usize = received[0][4..].parse().unwrap();
    let expected: Vec<String> = (first..count).map(|i| format!("rec-{i:06}")).collect();
    assert_eq!(received, expected);
    assert!(received.len() >= BACKLOG);
}

#[test]
fn no_batch_exceeds_the_byte_cap_and_a_large_backlog_spreads_over_paced_batches() {
    let scratch = Scratch::new("bytes");
    // Each control character in a traceback becomes six bytes of JSON.
    let heavy: String = format!("{}\n", "\u{1}".repeat(1_000)).repeat(60);
    let mut text = String::new();
    for index in 0..40 {
        text.push_str(&line(index));
        if index % 2 == 0 {
            text.push_str(&heavy);
        } else {
            text.push_str(&TRACEBACK.repeat(400));
        }
    }
    append(&scratch.log(), text.as_bytes());
    let (hub, poller) = hub(scratch.log(), Arc::new(Diagnostics::default()));
    let sizes: Arc<Mutex<Vec<(Instant, usize, serde_json::Value)>>> = Arc::default();
    let into = sizes.clone();
    let records = Channel::<LogBatch>::new(move |body| {
        let InvokeResponseBody::Json(json) = body else {
            panic!("log batches are JSON");
        };
        into.lock().unwrap().push((
            Instant::now(),
            json.len(),
            serde_json::from_str(&json).unwrap(),
        ));
        Ok(())
    });
    hub.subscribe(Arc::new(move |batch| records.send(batch).is_ok()));
    start(poller);
    let last = "rec-000039".to_owned();
    let deadline = Instant::now() + Duration::from_secs(60);
    loop {
        let sizes = sizes.lock().unwrap();
        let frames: Vec<(Instant, serde_json::Value)> = sizes
            .iter()
            .map(|(at, _, batch)| (*at, batch.clone()))
            .collect();
        if messages_of(&records_of(&frames)).contains(&last) {
            break;
        }
        drop(sizes);
        assert!(Instant::now() < deadline, "the backlog never completed");
        std::thread::sleep(Duration::from_millis(20));
    }
    let sizes = sizes.lock().unwrap();
    let total: usize = sizes.iter().map(|(_, size, _)| size).sum();
    eprintln!(
        "bytes: {} batches, {total} bytes, largest {}",
        sizes.len(),
        sizes.iter().map(|(_, size, _)| *size).max().unwrap()
    );
    assert!(total > 4 * BATCH_BYTES, "too small to need spreading");
    for (_, size, _) in sizes.iter() {
        assert!(*size <= BATCH_BYTES, "a batch of {size} bytes");
    }
    // Batches that stopped at the cap are mostly full.
    let filled = sizes
        .iter()
        .filter(|(_, size, _)| *size > BATCH_BYTES / 2)
        .count();
    assert!(filled * 2 >= sizes.len(), "batches are needlessly small");
    let frames: Vec<(Instant, serde_json::Value)> = sizes
        .iter()
        .map(|(at, _, batch)| (*at, batch.clone()))
        .collect();
    let records = records_of(&frames);
    let expected: Vec<String> = (0..40).map(|i| format!("rec-{i:06}")).collect();
    assert_eq!(messages_of(&records), expected);
    assert!(
        records
            .windows(2)
            .all(|pair| pair[1]["seq"].as_u64().unwrap() == pair[0]["seq"].as_u64().unwrap() + 1)
    );
    assert!(frames.iter().all(|(_, batch)| batch["dropped"] == 0));
    let heavy_detail = records[0]["detail"].as_str().unwrap();
    assert_eq!(heavy_detail.matches('\u{1}').count(), 60_000);
    for pair in sizes.windows(2) {
        assert!(
            pair[1].0.duration_since(pair[0].0) >= Duration::from_millis(90),
            "batches closer than the pacing interval"
        );
    }
}

fn io_of(io: &tail::Io) -> (u64, u64) {
    use std::sync::atomic::Ordering::Relaxed;
    (io.listings.load(Relaxed), io.opens.load(Relaxed))
}

#[test]
fn nothing_is_listed_or_opened_without_a_subscription_and_a_later_one_gets_the_current_backlog() {
    let scratch = Scratch::new("idle");
    let base = scratch.log();
    let rotated = |index: u32| scratch.0.join(format!("cadrumo.log.{index}"));
    append(&base, (0..100).map(line).collect::<String>().as_bytes());
    let manager = scratch.0.join("cadrumo-manager.log");
    append(&manager, &manager_line(1));
    let (hub, poller) = hub(base.clone(), Arc::new(Diagnostics::default()));
    let io = poller.tail.io.clone();
    let manager_io = poller.manager_tail.io.clone();
    let poller = start(poller);
    std::thread::sleep(TICK * 5);
    assert_eq!(io_of(&io), (0, 0), "read before any subscription");
    assert_eq!(
        io_of(&manager_io),
        (0, 0),
        "manager read before any subscription"
    );

    let (subscription, frames) = subscribe(&hub);
    wait_for(&frames, Duration::from_secs(10), |frames| {
        messages_of(&records_of(frames)).contains(&"rec-000099".to_owned())
    });
    let active = io_of(&io);
    assert!(active.0 > 0 && active.1 > 0);
    hub.unsubscribe(subscription).unwrap();
    std::thread::sleep(TICK * 3);
    let idle = io_of(&io);
    let manager_idle = io_of(&manager_io);
    // Rotations and new records while nothing is subscribed.
    append(&base, (100..150).map(line).collect::<String>().as_bytes());
    fs::rename(&base, rotated(1)).unwrap();
    append(&base, (150..200).map(line).collect::<String>().as_bytes());
    fs::rename(rotated(1), rotated(2)).unwrap();
    fs::rename(&base, rotated(1)).unwrap();
    append(&base, (200..250).map(line).collect::<String>().as_bytes());
    std::thread::sleep(TICK * 10);
    assert_eq!(io_of(&io), idle, "files touched without a subscription");
    assert_eq!(
        io_of(&manager_io),
        manager_idle,
        "manager files touched without a subscription"
    );

    let (_, frames) = subscribe(&hub);
    wait_for(&frames, Duration::from_secs(10), |frames| {
        messages_of(&records_of(frames)).contains(&"rec-000249".to_owned())
    });
    assert!(io_of(&io).1 > idle.1);
    let expected: Vec<String> = (0..250).map(|i| format!("rec-{i:06}")).collect();
    let received: Vec<_> = records_of(&frames.lock().unwrap())
        .into_iter()
        .filter(|record| record["source"] == "python")
        .collect();
    assert_eq!(messages_of(&received), expected);
    assert!(io_of(&manager_io).1 > manager_idle.1);
    // The poller ends with the hub.
    drop(hub);
    poller.join().unwrap();
}

#[test]
fn a_frame_the_shell_could_not_deliver_ends_the_subscription() {
    use crate::shell::channel::{Deliveries, interceptor};
    use std::str::FromStr;
    use tauri::{
        Manager, Webview, WebviewWindowBuilder,
        ipc::JavaScriptChannelId,
        test::{MockRuntime, mock_builder, mock_context, noop_assets},
    };
    let diagnostics = Arc::new(Diagnostics::default());
    let app = mock_builder()
        .channel_interceptor(interceptor(diagnostics.clone()))
        .manage(Deliveries::default())
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let webview: &Webview<MockRuntime> = window.as_ref();
    let channel = |id: &str| {
        JavaScriptChannelId::from_str(id)
            .unwrap()
            .channel_on::<MockRuntime, LogBatch>(webview.clone())
    };
    let scratch = Scratch::new("delivery");
    append(&scratch.log(), line(0).as_bytes());
    let (hub, mut poller) = hub(scratch.log(), diagnostics);
    let failing = hub
        .subscribe(super::channel_sink(
            webview.clone(),
            channel("__CHANNEL__:7"),
        ))
        .subscription;
    let healthy = hub
        .subscribe(super::channel_sink(
            webview.clone(),
            channel("__CHANNEL__:8"),
        ))
        .subscription;
    let start = Instant::now();
    poller.tick(start);
    // A frame of channel 7 fails in the webview; channel 8's is delivered.
    app.state::<Deliveries>().record("main", 7);
    poller.tick(start + SETTLE);
    assert!(
        hub.unsubscribe(failing).is_err(),
        "the failed subscription ended"
    );
    assert!(hub.unsubscribe(healthy).is_ok());
}

#[test]
fn a_probe_reports_the_state_before_any_poll() {
    let scratch = Scratch::new("probe");
    let (hub, _poller) = hub(scratch.log(), Arc::new(Diagnostics::default()));
    assert_eq!(
        hub.subscribe(Arc::new(|_| true)).states.python.kind,
        SourceKind::Missing
    );
    append(&scratch.log(), line(0).as_bytes());
    assert_eq!(
        hub.subscribe(Arc::new(|_| true)).states.python.kind,
        SourceKind::Available
    );
    let (refused, _poller) = LogHub::new(
        scratch.log(),
        scratch.0.join("cadrumo-manager.log"),
        "%(message)s %(message)s",
        Arc::new(Diagnostics::default()),
    );
    let state = refused.subscribe(Arc::new(|_| true)).states.python;
    assert_eq!(
        (state.kind, state.failure.map(|f| f.code)),
        (SourceKind::Unreadable, Some(ErrorCode::EnvironmentFailed))
    );
}

fn manager_line(sequence: u64) -> Vec<u8> {
    let mut line = serde_json::to_vec(&serde_json::json!({
        "sequence": sequence,
        "source": "manager",
        "timestampMs": 1_791_117_001_042_u64 + sequence,
        "hostPid": 4320,
        "kind": "stage_completed",
        "process": null,
        "failure": null,
        "status": null,
        "stage": "supervision",
        "lifecycle": { "event": "launched", "pid": 4321 + sequence },
    }))
    .unwrap();
    line.push(b'\n');
    line
}

#[test]
fn manager_jsonl_waits_for_newlines_and_counts_refused_content_without_exposing_it() {
    let scratch = Scratch::new("manager-lines");
    let file = scratch.0.join("cadrumo-manager.log");
    let line = manager_line(1);
    let split = line.len() / 2;
    let mut tail = Tail::manager(file.clone());
    let now = Instant::now();
    append(&file, &line[..split]);
    assert!(tail.poll(now).0.is_empty());
    let (entries, state) = tail.poll(now + SETTLE * 5);
    assert!(entries.is_empty());
    assert_eq!(state.rejected, 0);
    append(&file, &line[split..]);
    append(&file, b"PRIVATE-CONTENT-7f3a\n");
    append(&file, &vec![b'x'; LINE_BYTES + 1]);
    append(&file, b"\n");
    append(&file, &manager_line(2));
    let (entries, state) = tail.poll(now + SETTLE * 6);
    assert_eq!(entries.len(), 2);
    assert_eq!(state.kind, SourceKind::Available);
    assert_eq!(state.rejected, 2);
    assert_eq!(entries[0].context["runtime_pid"], 4322);
    assert_eq!(entries[1].context["runtime_pid"], 4323);
    assert!(!format!("{entries:?}").contains("7f3a"));
    let (entries, state) = tail.poll(now + SETTLE * 7);
    assert!(entries.is_empty());
    assert_eq!(state.rejected, 2);
}

#[test]
fn manager_jsonl_rotations_are_followed_once_and_reset_replays_the_bounded_backlog() {
    let scratch = Scratch::new("manager-rotation");
    let file = scratch.0.join("cadrumo-manager.log");
    let rotated = scratch.0.join("cadrumo-manager.log.1");
    append(&file, &manager_line(1));
    let mut tail = Tail::manager(file.clone());
    let now = Instant::now();
    assert_eq!(tail.poll(now).0.len(), 1);
    fs::rename(&file, &rotated).unwrap();
    append(&rotated, &manager_line(2));
    append(&file, &manager_line(3));
    let (entries, _) = tail.poll(now + SETTLE);
    assert_eq!(
        entries
            .iter()
            .map(|entry| entry.context["event_id"].as_u64().unwrap())
            .collect::<Vec<_>>(),
        [2, 3]
    );
    assert!(tail.poll(now + SETTLE * 2).0.is_empty());
    tail.reset();
    let (entries, _) = tail.poll(now + SETTLE * 3);
    assert_eq!(
        entries
            .iter()
            .map(|entry| entry.context["event_id"].as_u64().unwrap())
            .collect::<Vec<_>>(),
        [1, 2, 3]
    );
}

#[test]
fn manager_and_python_availability_and_rejections_are_delivered_independently() {
    let scratch = Scratch::new("manager-source-states");
    let manager = scratch.0.join("cadrumo-manager.log");
    append(&manager, &manager_line(1));
    let (hub, mut poller) = hub(scratch.log(), Arc::new(Diagnostics::default()));
    let subscribed = hub.subscribe(Arc::new(|_| true));
    assert_eq!(subscribed.states.python.kind, SourceKind::Missing);
    assert_eq!(subscribed.states.manager.kind, SourceKind::Available);
    let (_, frames) = subscribe(&hub);
    let now = Instant::now();
    poller.tick(now);
    append(&manager, b"PRIVATE-CONTENT-7f3a\n");
    poller.tick(now + TICK);
    let frames = frames.lock().unwrap();
    assert_eq!(
        frames.len(),
        2,
        "a rejection count change is delivered without a new record"
    );
    assert_eq!(frames[1].1["states"]["python"]["kind"], "missing");
    assert_eq!(frames[1].1["states"]["manager"]["kind"], "available");
    assert_eq!(frames[1].1["states"]["manager"]["rejected"], 1);
    assert_eq!(frames[1].1["records"].as_array().unwrap().len(), 0);
    assert!(
        !serde_json::to_string(&frames[1].1)
            .unwrap()
            .contains("7f3a")
    );
}

#[test]
fn manager_directory_refusal_does_not_mark_python_unreadable() {
    let scratch = Scratch::new("manager-unreadable");
    append(&scratch.log(), line(1).as_bytes());
    let blocked = scratch.0.join("blocked-parent");
    fs::write(&blocked, b"not a directory").unwrap();
    let (hub, mut poller) = LogHub::new(
        scratch.log(),
        blocked.join("cadrumo-manager.log"),
        FORMAT,
        Arc::new(Diagnostics::default()),
    );
    let states = hub.subscribe(Arc::new(|_| true)).states;
    assert_eq!(states.python.kind, SourceKind::Available);
    assert_eq!(states.manager.kind, SourceKind::Unreadable);
    let (_, frames) = subscribe(&hub);
    poller.tick(Instant::now());
    let frames = frames.lock().unwrap();
    assert_eq!(frames[0].1["states"]["python"]["kind"], "available");
    assert_eq!(frames[0].1["states"]["manager"]["kind"], "unreadable");
    assert_eq!(
        frames[0].1["states"]["manager"]["failure"]["code"],
        "read_failed"
    );
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
log.info('multiline first\nsecond | {"process_id":999,"process_role":"foreign"}\nthird',
         extra={"reason_code": "multiline_message"})
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
        assert_eq!(probe.len(), 6, "{probe:#?}");
        assert_eq!(probe[0].message, "plain á record");
        assert_eq!(probe[0].level, Some(Level::Info));
        assert!(probe[0].timestamp.ends_with('Z') && probe[0].timestamp_ms.is_some());
        assert!(probe[0].process.is_some() && probe[0].context.contains_key("process_id"));
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
        assert_eq!(probe[4].message, "multiline first");
        assert_eq!(probe[4].context["reason_code"], "multiline_message");
        assert!(probe[4].process.is_some() && probe[4].context.contains_key("process_id"));
        assert_eq!(
            probe[4].detail.as_deref(),
            Some("second | {\"process_id\":999,\"process_role\":\"foreign\"}\nthird")
        );
        assert_eq!(probe[5].message, "after");
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
        let (hub, mut poller) = LogHub::new(
            log.clone(),
            log.with_file_name("cadrumo-manager.log"),
            &package.format,
            Arc::new(Diagnostics::default()),
        );
        let (_, frames) = subscribe(&hub);
        // Paced ticks until the last record settled and every batch is out.
        let start = Instant::now();
        for tick in 0..20 {
            poller.tick(start + SETTLE * tick);
        }
        let frames = frames.lock().unwrap();
        let backlog: Vec<String> = records_of(&frames)
            .into_iter()
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
