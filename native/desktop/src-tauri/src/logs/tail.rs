//! Follows an appended log and its numbered rotations by polling.
//!
//! Several Python processes append to one `RotatingFileHandler` file. On
//! Windows a rotation fails while another process holds the file, so rotation
//! can be skipped, partial (`.1` already shifted to `.2`) or late; on other
//! platforms a writer can keep appending to a file after it was renamed. File
//! names therefore do not identify files. A file is identified by its first
//! bytes, which a log file never rewrites, and each identified file keeps its
//! own read offset wherever it moves. File events never imply anything about
//! the processes that write the file.
//!
//! The reader opens each file only for the duration of one read, with the
//! platform's default sharing, so it never blocks a writer's rename.
use super::{
    format::LinePattern,
    record::{BATCH_BYTES, Entry, LogSourceState, ProcessRef, SourceKind},
};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use std::{
    collections::BTreeMap,
    fs::{self, File},
    io::{self, Read, Seek, SeekFrom},
    path::{Path, PathBuf},
    time::{Duration, Instant},
};

enum LineParser {
    Python(LinePattern),
    Manager,
}

/// Python lines longer than this are truncated; manager JSONL rows are refused.
pub const LINE_BYTES: usize = 16 * 1024;
/// Continuation lines beyond this are not attached to a record's detail.
const DETAIL_BYTES: usize = 64 * 1024;
/// Bytes that identify a file.
const FINGERPRINT: usize = 1024;
/// Bytes read from one file in one poll; the rest is read by later polls.
const READ_BYTES: u64 = 4 * 1024 * 1024;
/// Bytes read across the existing files on the first poll, newest first.
const INITIAL_BYTES: u64 = 16 * 1024 * 1024;
// A record's JSON is at most six bytes per byte of its line and detail (a
// control character becomes `\u00XX`), plus field names; one record always
// fits in a batch.
const _: () = assert!(6 * (LINE_BYTES + DETAIL_BYTES) + LINE_BYTES < BATCH_BYTES);
/// A record whose file has not grown for this long is complete.
pub const SETTLE: Duration = Duration::from_millis(250);
/// Identified files kept beyond those present, so a file missed during a
/// racing rotation is still recognised when it reappears.
const RETAINED: usize = 64;

struct Draft {
    timestamp: String,
    level: Option<super::format::Level>,
    logger: Option<String>,
    message: String,
    detail: String,
    detail_lines: bool,
    context: BTreeMap<String, serde_json::Value>,
}

impl Draft {
    fn entry(self) -> Entry {
        let timestamp_ms = super::timestamp::milliseconds(&self.timestamp);
        let process = self
            .context
            .get("process_id")
            .and_then(serde_json::Value::as_u64)
            .and_then(|pid| u32::try_from(pid).ok())
            .zip(
                self.context
                    .get("process_role")
                    .and_then(serde_json::Value::as_str),
            )
            .map(|(pid, role)| ProcessRef {
                role: role.to_owned(),
                pid,
            });
        Entry {
            source: "python",
            timestamp: self.timestamp,
            timestamp_ms,
            level: self.level,
            logger: self.logger,
            message: self.message,
            detail: self.detail_lines.then_some(self.detail),
            process,
            context: self.context,
        }
    }
}

/// Polls that may defer a new file while the current one is hidden.
const DEFERRALS: u32 = 5;
/// Directory observations per poll while rotations keep changing it.
const OBSERVATIONS: u32 = 3;

/// One identified log file.
struct Tracked {
    id: u64,
    fingerprint: Vec<u8>,
    offset: u64,
    partial: Vec<u8>,
    truncated: bool,
    /// Reading began inside the file: drop the first, possibly partial, line
    /// and then continuation lines until a record starts.
    skip_line: bool,
    resync: bool,
    draft: Option<Draft>,
    progressed: Instant,
    seen: u64,
    rejected: u64,
}

impl Tracked {
    /// Starts reading at `start`. Inside a file, reading begins one byte
    /// earlier, so the dropped first line is empty when `start` begins a line.
    fn new(id: u64, start: u64, now: Instant) -> Self {
        Self {
            id,
            fingerprint: Vec::new(),
            offset: start.saturating_sub(1),
            partial: Vec::new(),
            truncated: false,
            skip_line: start > 0,
            resync: start > 0,
            draft: None,
            progressed: now,
            seen: 0,
            rejected: 0,
        }
    }

    fn feed(&mut self, bytes: &[u8], parser: &LineParser, out: &mut Vec<Entry>) {
        let mut rest = bytes;
        while !rest.is_empty() {
            let (segment, ended) = match rest.iter().position(|byte| *byte == b'\n') {
                Some(end) => (&rest[..end], true),
                None => (rest, false),
            };
            rest = &rest[segment.len() + usize::from(ended)..];
            let room = LINE_BYTES.saturating_sub(self.partial.len());
            self.partial
                .extend_from_slice(&segment[..segment.len().min(room)]);
            self.truncated |= segment.len() > room;
            if ended {
                self.end_line(parser, out);
            }
        }
    }

    fn end_line(&mut self, parser: &LineParser, out: &mut Vec<Entry>) {
        let mut line = std::mem::take(&mut self.partial);
        let truncated = std::mem::take(&mut self.truncated);
        if std::mem::take(&mut self.skip_line) {
            return;
        }
        if !truncated && line.last() == Some(&b'\r') {
            line.pop();
        }
        let pattern = match parser {
            LineParser::Python(pattern) => pattern,
            LineParser::Manager => {
                match (!truncated).then(|| super::manager::parse(&line)).flatten() {
                    Some(entry) => out.push(entry),
                    None => self.rejected += 1,
                }
                return;
            }
        };
        let text = String::from_utf8_lossy(&line);
        match pattern.head(&text) {
            Some(head) => {
                self.resync = false;
                if let Some(draft) = self.draft.take() {
                    out.push(draft.entry());
                }
                self.draft = Some(Draft {
                    timestamp: head.time.unwrap_or_default().to_owned(),
                    level: head.level,
                    logger: head.logger.map(str::to_owned),
                    message: head.message.to_owned(),
                    detail: String::new(),
                    detail_lines: false,
                    context: head.context,
                });
            }
            None if self.resync => {}
            None => match &mut self.draft {
                Some(draft) => {
                    if draft.detail.len() + text.len() < DETAIL_BYTES {
                        if draft.detail_lines {
                            draft.detail.push('\n');
                        }
                        draft.detail.push_str(&text);
                        draft.detail_lines = true;
                    }
                }
                // Text before any record start in a file read from its
                // beginning still reaches the view, unattributed.
                None => {
                    self.draft = Some(Draft {
                        timestamp: String::new(),
                        level: None,
                        logger: None,
                        message: text.into_owned(),
                        detail: String::new(),
                        detail_lines: false,
                        context: BTreeMap::new(),
                    });
                }
            },
        }
    }

    /// Completes Python records after [`SETTLE`]. Manager JSONL rows require
    /// their newline, even when an append pauses for longer than that.
    fn settle(&mut self, now: Instant, parser: &LineParser, out: &mut Vec<Entry>) {
        if matches!(parser, LineParser::Manager) {
            return;
        }
        if now.saturating_duration_since(self.progressed) < SETTLE {
            return;
        }
        if !self.partial.is_empty() {
            self.end_line(parser, out);
        }
        if let Some(draft) = self.draft.take() {
            out.push(draft.entry());
        }
    }
}

pub struct Tail {
    file: PathBuf,
    parser: Result<LineParser, ApplicationError>,
    tracked: Vec<Tracked>,
    polls: u64,
    /// Consecutive polls with a read failure. One failure can be a racing
    /// rotation; a second in a row is reported.
    failing: u32,
    reported: Option<LogSourceState>,
    /// The file last seen under the log file's own name.
    current: Option<u64>,
    deferred: u32,
    next_id: u64,
    rejected: u64,
    #[cfg(test)]
    pub io: std::sync::Arc<Io>,
}

/// Directory listings and file opens a tail made, counted where it makes them.
#[cfg(test)]
#[derive(Default)]
pub struct Io {
    pub listings: std::sync::atomic::AtomicU64,
    pub opens: std::sync::atomic::AtomicU64,
}

struct Opened {
    file: File,
    prefix: Vec<u8>,
    length: u64,
    base: bool,
    known: Option<usize>,
}

fn unreadable() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Logging)
}

impl Tail {
    pub fn new(file: PathBuf, format: &str) -> Self {
        Self {
            file,
            parser: LinePattern::compile(format)
                .map(LineParser::Python)
                .map_err(|_| {
                    ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Logging)
                }),
            tracked: Vec::new(),
            polls: 0,
            failing: 0,
            reported: None,
            current: None,
            deferred: 0,
            next_id: 0,
            rejected: 0,
            #[cfg(test)]
            io: Default::default(),
        }
    }

    pub fn manager(file: PathBuf) -> Self {
        let mut tail = Self::new(file, "%(message)s");
        tail.parser = Ok(LineParser::Manager);
        tail
    }

    /// Why the configured line format cannot be followed, if it cannot.
    pub fn refusal(&self) -> Option<ApplicationError> {
        self.parser.as_ref().err().cloned()
    }

    /// Forgets every file and record in progress, so the next poll starts
    /// like the first: from a bounded window at the end of the files.
    pub fn reset(&mut self) {
        self.tracked.clear();
        self.polls = 0;
        self.failing = 0;
        self.reported = None;
        self.current = None;
        self.deferred = 0;
        self.rejected = 0;
    }

    fn state(&self, kind: SourceKind, failure: Option<ApplicationError>) -> LogSourceState {
        let mut state = state(&self.file, kind, failure);
        state.rejected = self.rejected;
        state
    }

    /// Reads what was appended since the previous poll and returns the
    /// completed records with the source state.
    pub fn poll(&mut self, now: Instant) -> (Vec<Entry>, LogSourceState) {
        let mut out = Vec::new();
        let parser = match &self.parser {
            Ok(parser) => parser,
            Err(error) => {
                let failure = error.clone();
                return (out, self.state(SourceKind::Unreadable, Some(failure)));
            }
        };
        self.polls += 1;
        let polls = self.polls;
        // A rotation between two opens can show one file under two names or
        // hide one, and reading a successor before its predecessor reorders
        // records. The files are read only when two observations in a row
        // find the same files under the same names.
        let mut attempts = 0;
        let files = loop {
            attempts += 1;
            let observed = self
                .observe()
                .and_then(|first| self.observe().map(|second| (same(&first, &second), second)));
            match observed {
                Ok((consistent, files)) if consistent || attempts == OBSERVATIONS => break files,
                Ok(_) => {}
                Err(error) => {
                    let failure = unreadable().caused_by(error);
                    return (out, self.state(SourceKind::Unreadable, Some(failure)));
                }
            }
        };
        let present = files.len();
        let mut failure = None;
        let mut opened = Vec::new();
        for (path, file) in files {
            match file {
                Ok(Some((file, prefix, length))) => {
                    let known = self.identify(&prefix);
                    opened.push(Opened {
                        file,
                        prefix,
                        length,
                        base: path == self.file,
                        known,
                    });
                }
                Ok(None) => {}
                Err(error) => failure = Some(unreadable().caused_by(error)),
            }
        }
        // A rotation that lands between two opens can hide the file the
        // writer used last while its successor is already visible. Reading
        // the successor first would reorder records, so a new file waits for
        // a poll that sees the previous current file again, a bounded number
        // of times in case that file was deleted.
        let current_seen = self.current.is_none_or(|id| {
            opened
                .iter()
                .any(|file| file.known.is_some_and(|index| self.tracked[index].id == id))
        });
        let unknown = opened.iter().any(|file| file.known.is_none());
        let defer = unknown && !current_seen && self.deferred < DEFERRALS;
        self.deferred = if defer { self.deferred + 1 } else { 0 };
        // The first poll reads at most INITIAL_BYTES, from the newest file
        // backwards; older content is passed over, not replayed.
        let first = polls == 1;
        let mut budget = INITIAL_BYTES;
        let mut starts: Vec<u64> = opened
            .iter()
            .rev()
            .map(|file| {
                let window = file.length.min(budget);
                budget -= window;
                file.length - window
            })
            .collect();
        starts.reverse();
        // A window inside a file starts one byte early; see `Tracked::new`.
        let cap = if first { INITIAL_BYTES + 1 } else { READ_BYTES };
        for (file, start) in opened.into_iter().zip(starts) {
            let index = match file.known.or_else(|| self.identify(&file.prefix)) {
                Some(index) => index,
                None if defer => continue,
                None => {
                    self.next_id += 1;
                    let start = if first { start } else { 0 };
                    self.tracked.push(Tracked::new(self.next_id, start, now));
                    self.tracked.len() - 1
                }
            };
            let tracked = &mut self.tracked[index];
            tracked.seen = polls;
            if file.base {
                self.current = Some(tracked.id);
            }
            if file.prefix.len() > tracked.fingerprint.len() {
                tracked.fingerprint = file.prefix;
            }
            if file.length < tracked.offset {
                // Not how a log file changes; read it again as a new file.
                tracked.settle(now + SETTLE, parser, &mut out);
                let id = tracked.id;
                *tracked = Tracked::new(id, 0, now);
                tracked.seen = polls;
            }
            let bytes = match read(file.file, tracked.offset, file.length, cap) {
                Ok(bytes) => bytes,
                Err(error) if error.kind() == io::ErrorKind::NotFound => Vec::new(),
                Err(error) => {
                    failure = Some(unreadable().caused_by(error));
                    Vec::new()
                }
            };
            if !bytes.is_empty() {
                // Writers complete a record in one write, so a record pending
                // in another file precedes these bytes.
                for (other, tracked) in self.tracked.iter_mut().enumerate() {
                    if other != index
                        && let Some(draft) = tracked.draft.take()
                    {
                        out.push(draft.entry());
                    }
                }
                let tracked = &mut self.tracked[index];
                tracked.offset += bytes.len() as u64;
                tracked.progressed = now;
                let rejected = tracked.rejected;
                tracked.feed(&bytes, parser, &mut out);
                self.rejected += tracked.rejected - rejected;
            }
            // A rotated file's last record ends before anything a newer file
            // holds, so it is completed now to keep records in file order.
            if !file.base
                && let Some(draft) = self.tracked[index].draft.take()
            {
                out.push(draft.entry());
            }
        }
        for tracked in &mut self.tracked {
            tracked.settle(now, parser, &mut out);
        }
        self.forget(present);
        self.failing = if failure.is_some() {
            self.failing + 1
        } else {
            0
        };
        let mut state = match failure {
            Some(_) if self.failing == 1 && self.reported.is_some() => self
                .reported
                .clone()
                .unwrap_or_else(|| self.state(SourceKind::Missing, None)),
            Some(failure) => self.state(SourceKind::Unreadable, Some(failure)),
            None if present == 0 => self.state(SourceKind::Missing, None),
            None => self.state(SourceKind::Available, None),
        };
        state.rejected = self.rejected;
        self.reported = Some(state.clone());
        (out, state)
    }

    fn observe(&self) -> io::Result<Observation> {
        #[cfg(test)]
        self.io
            .listings
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let observation = observe(&self.file);
        #[cfg(test)]
        if let Ok(files) = &observation {
            self.io
                .opens
                .fetch_add(files.len() as u64, std::sync::atomic::Ordering::Relaxed);
        }
        observation
    }

    /// The tracked file whose identifying bytes begin `prefix`; the longest
    /// match wins.
    fn identify(&self, prefix: &[u8]) -> Option<usize> {
        self.tracked
            .iter()
            .enumerate()
            .filter(|(_, tracked)| {
                !tracked.fingerprint.is_empty() && prefix.starts_with(&tracked.fingerprint)
            })
            .max_by_key(|(_, tracked)| tracked.fingerprint.len())
            .map(|(index, _)| index)
    }

    fn forget(&mut self, present: usize) {
        let keep = present + RETAINED;
        if self.tracked.len() > keep {
            self.tracked
                .sort_by_key(|tracked| std::cmp::Reverse(tracked.seen));
            self.tracked.truncate(keep);
        }
    }
}

fn state(file: &Path, kind: SourceKind, failure: Option<ApplicationError>) -> LogSourceState {
    LogSourceState {
        kind,
        detail: file.display().to_string(),
        failure,
        rejected: 0,
    }
}

/// The source state from listing and opening the files, without reading
/// past their identifying bytes. Unlike a poll, it reports a single failed
/// open at once.
pub fn probe(file: &Path) -> LogSourceState {
    let failed = |error: io::Error| {
        state(
            file,
            SourceKind::Unreadable,
            Some(unreadable().caused_by(error)),
        )
    };
    match observe(file) {
        Err(error) => failed(error),
        Ok(files) if files.is_empty() => state(file, SourceKind::Missing, None),
        Ok(files) => match files.into_iter().find_map(|(_, opened)| opened.err()) {
            Some(error) => failed(error),
            None => state(file, SourceKind::Available, None),
        },
    }
}

/// The log file and its numbered rotations that exist now, oldest first.
/// Only regular files directly in the log directory qualify.
fn files(file: &Path) -> io::Result<Vec<PathBuf>> {
    let directory = file.parent().ok_or_else(|| io::Error::other("log file"))?;
    let base = file
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| io::Error::other("log file"))?;
    let mut files = Vec::new();
    for entry in fs::read_dir(directory)? {
        let entry = entry?;
        let name = entry.file_name();
        let Some(name) = name.to_str() else {
            continue;
        };
        let index = if name == base {
            0
        } else {
            match name
                .strip_prefix(base)
                .and_then(|rest| rest.strip_prefix('.'))
                .filter(|digits| {
                    (1..=6).contains(&digits.len()) && digits.bytes().all(|b| b.is_ascii_digit())
                })
                .and_then(|digits| digits.parse::<u32>().ok())
            {
                Some(index) if index > 0 => index,
                _ => continue,
            }
        };
        match entry.file_type() {
            Ok(kind) if kind.is_file() => files.push((index, entry.path())),
            Ok(_) => {}
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
    }
    files.sort_by_key(|file| std::cmp::Reverse(file.0));
    Ok(files.into_iter().map(|(_, path)| path).collect())
}

/// Lists the log file and its rotations, oldest first, and opens each.
fn observe(file: &Path) -> io::Result<Observation> {
    let files = match files(file) {
        Ok(files) => files,
        Err(error) if error.kind() == io::ErrorKind::NotFound => Vec::new(),
        Err(error) => return Err(error),
    };
    Ok(files
        .into_iter()
        .map(|path| {
            let file = open(&path);
            (path, file)
        })
        .collect())
}

type Observation = Vec<(PathBuf, io::Result<Option<(File, Vec<u8>, u64)>>)>;

/// Whether two observations found the same files under the same names. A
/// file shorter than [`FINGERPRINT`] may have grown in between.
fn same(left: &Observation, right: &Observation) -> bool {
    let shape = |observation: &Observation| -> Vec<(PathBuf, Vec<u8>)> {
        observation
            .iter()
            .filter_map(|(path, file)| match file {
                Ok(Some((_, prefix, _))) => Some((path.clone(), prefix.clone())),
                _ => None,
            })
            .collect()
    };
    let (left, right) = (shape(left), shape(right));
    left.len() == right.len()
        && left
            .iter()
            .zip(&right)
            .all(|((a, x), (b, y))| a == b && (x.starts_with(y) || y.starts_with(x)))
}

/// Opens a file for one read and returns its identifying prefix and length.
/// A file that vanished in a racing rotation, or is still empty, is skipped.
fn open(path: &Path) -> io::Result<Option<(File, Vec<u8>, u64)>> {
    let mut file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let length = file.metadata()?.len();
    if length == 0 {
        return Ok(None);
    }
    let mut prefix = Vec::with_capacity(FINGERPRINT);
    (&mut file)
        .take(FINGERPRINT as u64)
        .read_to_end(&mut prefix)?;
    if prefix.is_empty() {
        return Ok(None);
    }
    Ok(Some((file, prefix, length)))
}

fn read(mut file: File, offset: u64, length: u64, cap: u64) -> io::Result<Vec<u8>> {
    if length <= offset {
        return Ok(Vec::new());
    }
    file.seek(SeekFrom::Start(offset))?;
    let mut bytes = Vec::new();
    file.take((length - offset).min(cap))
        .read_to_end(&mut bytes)?;
    Ok(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observations_differ_when_a_rotation_moved_files_between_them() {
        let directory = std::env::temp_dir()
            .join("cadrumo-desktop-logs-tests")
            .join(format!("observe-{}", std::process::id()));
        fs::create_dir_all(&directory).unwrap();
        let base = directory.join("cadrumo.log");
        let rotated = directory.join("cadrumo.log.1");
        fs::write(&base, b"first file\n").unwrap();
        let tail = Tail::new(base.clone(), "%(message)s");
        let before = tail.observe().unwrap();
        assert!(same(&before, &tail.observe().unwrap()));
        // Growth inside the identifying bytes is the same file.
        fs::write(&base, b"first file\nmore\n").unwrap();
        assert!(same(&before, &tail.observe().unwrap()));
        fs::rename(&base, &rotated).unwrap();
        let moved = tail.observe().unwrap();
        assert!(!same(&before, &moved));
        fs::write(&base, b"second file\n").unwrap();
        let after = tail.observe().unwrap();
        assert!(!same(&moved, &after));
        assert!(same(&after, &tail.observe().unwrap()));
        drop((before, moved, after));
        fs::remove_dir_all(&directory).unwrap();
    }
}
