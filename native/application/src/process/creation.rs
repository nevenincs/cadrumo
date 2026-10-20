//! Coordinate Windows handle inheritance across application process creators.
//!
//! CreatePseudoConsole temporarily duplicates its pipe ends as inheritable.
//! A simultaneous std::process spawn can inherit them, keeping a closed
//! terminal's reader alive until that unrelated process exits. Rust's internal
//! spawn lock cannot coordinate with ConPTY. Both use this outer lock.

/// Run only the creation step here, including any temporary inheritable
/// handles. Release before waiting for output, readiness, or process exit.
/// Never nest calls. Other platforms need no Windows inheritance exclusion.
pub fn run<T>(create: impl FnOnce() -> T) -> T {
    #[cfg(windows)]
    let _guard = {
        static CREATION: std::sync::Mutex<()> = std::sync::Mutex::new(());
        CREATION.lock().unwrap_or_else(|error| error.into_inner())
    };
    create()
}
