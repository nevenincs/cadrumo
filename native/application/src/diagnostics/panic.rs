//! Process panic recording: every panic reaches the durable diagnostics log
//! before unwinding begins, so a panic that cannot unwind (an FFI callback, a
//! panic during cleanup) still leaves its record before the process aborts.
//!
//! The payload is never written. Panic messages can carry formatted values,
//! including `Debug` output of private data; the record keeps only the source
//! location, the thread and a closed category derived from the message.
use super::Diagnostics;
use serde::{Deserialize, Serialize};
use std::{
    panic::{Location, PanicHookInfo},
    sync::{Arc, OnceLock},
};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PanicCategory {
    OptionNone,
    ResultErr,
    IndexOutOfBounds,
    SliceRange,
    ArithmeticOverflow,
    DivisionByZero,
    BorrowConflict,
    LockPoisoned,
    NoAsyncRuntime,
    NestedAsyncRuntime,
    Unreachable,
    Unimplemented,
    Assertion,
    AllocationFailure,
    CannotUnwind,
    Explicit,
    Unclassified,
}

/// Fixed library wording only; the first matching rule decides.
const CATEGORIES: [(&str, PanicCategory); 22] = [
    (
        "panic in a function that cannot unwind",
        PanicCategory::CannotUnwind,
    ),
    (
        "panic in a destructor during cleanup",
        PanicCategory::CannotUnwind,
    ),
    ("PoisonError", PanicCategory::LockPoisoned),
    ("on a `None` value", PanicCategory::OptionNone),
    ("on an `Err` value", PanicCategory::ResultErr),
    ("index out of bounds", PanicCategory::IndexOutOfBounds),
    ("range start index", PanicCategory::SliceRange),
    ("range end index", PanicCategory::SliceRange),
    ("is not a char boundary", PanicCategory::SliceRange),
    ("divide by zero", PanicCategory::DivisionByZero),
    ("divisor of zero", PanicCategory::DivisionByZero),
    ("with overflow", PanicCategory::ArithmeticOverflow),
    ("already borrowed", PanicCategory::BorrowConflict),
    ("already mutably borrowed", PanicCategory::BorrowConflict),
    ("no reactor running", PanicCategory::NoAsyncRuntime),
    ("context of a Tokio", PanicCategory::NoAsyncRuntime),
    (
        "runtime from within a runtime",
        PanicCategory::NestedAsyncRuntime,
    ),
    ("entered unreachable code", PanicCategory::Unreachable),
    ("not yet implemented", PanicCategory::Unimplemented),
    ("assertion", PanicCategory::Assertion),
    ("capacity overflow", PanicCategory::AllocationFailure),
    ("explicit panic", PanicCategory::Explicit),
];

impl PanicCategory {
    pub fn of(message: Option<&str>) -> Self {
        message
            .and_then(|message| {
                CATEGORIES
                    .iter()
                    .find(|(wording, _)| message.contains(wording))
                    .map(|(_, category)| *category)
            })
            .unwrap_or(Self::Unclassified)
    }
}

/// One panic: where it was raised and on which thread, never what it said.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PanicFact {
    /// Crate-relative source file, e.g. `tokio-1.47.1/src/runtime/context.rs`.
    pub file: Option<String>,
    pub line: Option<u32>,
    pub column: Option<u32>,
    pub thread: String,
    pub thread_id: u64,
    pub category: PanicCategory,
}

const FILE_LIMIT: usize = 160;
const THREAD_LIMIT: usize = 64;

impl PanicFact {
    pub fn new(
        location: Option<&Location<'_>>,
        thread: Option<&str>,
        thread_id: u64,
        message: Option<&str>,
    ) -> Self {
        Self {
            file: location.map(|location| source_file(location.file())),
            line: location.map(Location::line),
            column: location.map(Location::column),
            thread: thread.map_or_else(|| "unnamed".into(), |name| bounded(name, THREAD_LIMIT)),
            thread_id,
            category: PanicCategory::of(message),
        }
    }
    fn observe(info: &PanicHookInfo<'_>) -> Self {
        let payload = info.payload();
        let message = payload
            .downcast_ref::<&str>()
            .copied()
            .or_else(|| payload.downcast_ref::<String>().map(String::as_str));
        let current = std::thread::current();
        Self::new(
            info.location(),
            current.name(),
            thread_number(current.id()),
            message,
        )
    }
}

/// Compiled source paths are absolute for path and registry dependencies and
/// would expose the build account's home directory. Keep the crate-relative
/// tail beginning at the directory that holds the last `src` component.
fn source_file(path: &str) -> String {
    let components: Vec<&str> = path
        .split(['/', '\\'])
        .filter(|part| !part.is_empty())
        .collect();
    let start = components
        .iter()
        .rposition(|part| *part == "src")
        .map_or(components.len().saturating_sub(1), |index| {
            index.saturating_sub(1)
        });
    bounded(&components[start..].join("/"), FILE_LIMIT)
}

fn bounded(text: &str, limit: usize) -> String {
    text.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '/' | '.' | '-' | '_' | ':' | ' ') {
                c
            } else {
                '_'
            }
        })
        .take(limit)
        .collect()
}

/// `ThreadId` exposes its number only through `Debug` on stable Rust.
fn thread_number(id: std::thread::ThreadId) -> u64 {
    format!("{id:?}")
        .chars()
        .filter(char::is_ascii_digit)
        .collect::<String>()
        .parse()
        .unwrap_or(0)
}

static PROCESS: OnceLock<Arc<Diagnostics>> = OnceLock::new();

/// Bind this process's panics to `diagnostics`. Call first in `main`, before any
/// thread or runtime starts; later calls keep the first binding. The default
/// hook is replaced because it prints the raw payload on standard error.
pub fn install(diagnostics: Arc<Diagnostics>) {
    if PROCESS.set(diagnostics).is_err() {
        return;
    }
    std::panic::set_hook(Box::new(|info| {
        if let Some(diagnostics) = PROCESS.get() {
            diagnostics.panicked(PanicFact::observe(info));
        }
    }));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_paths_keep_only_the_crate_relative_tail() {
        assert_eq!(
            source_file(
                r"C:\Users\someone\.cargo\registry\src\index.crates.io-1949\tokio-1.47.1\src\runtime\context.rs"
            ),
            "tokio-1.47.1/src/runtime/context.rs"
        );
        assert_eq!(
            source_file("/rustc/0123abcd/library/core/src/option.rs"),
            "core/src/option.rs"
        );
        assert_eq!(
            source_file(r"src\shell\language.rs"),
            "src/shell/language.rs"
        );
        assert_eq!(source_file("/home/someone/private/build.rs"), "build.rs");
    }

    #[test]
    fn categories_never_carry_message_text() {
        let private = "called `Result::unwrap()` on an `Err` value: \"ES12345678Z\"";
        assert_eq!(PanicCategory::of(Some(private)), PanicCategory::ResultErr);
        assert_eq!(
            PanicCategory::of(Some(
                "there is no reactor running, must be called from the context of a Tokio 1.x runtime"
            )),
            PanicCategory::NoAsyncRuntime
        );
        assert_eq!(
            PanicCategory::of(Some("taxpayer ES12345678Z missing")),
            PanicCategory::Unclassified
        );
        assert_eq!(PanicCategory::of(None), PanicCategory::Unclassified);
        let fact = PanicFact::new(None, Some("worker\n\"x\""), 7, Some(private));
        let encoded = serde_json::to_string(&fact).unwrap();
        assert!(!encoded.contains("ES12345678Z"));
        assert_eq!(fact.thread, "worker__x_");
    }
}
