//! The generated window fixtures the host's tests read.
//!
//! They are projections of the product's own application, produced into the build tree and
//! never committed. CMake names their directory in the environment of every host test run.

use std::path::PathBuf;

const DIRECTORY: &str = "CADRUMO_WINDOW_FIXTURES";

/// The text of one generated window fixture, named by its path below the fixtures directory.
///
/// A missing directory or file stops the test with the command that produces it: a test never
/// writes a fixture.
pub(crate) fn window_fixture(name: &str) -> String {
    let directory = std::env::var_os(DIRECTORY).unwrap_or_else(|| {
        panic!("{DIRECTORY} names the generated window fixtures; run the host tests through `just test-native`")
    });
    let path = PathBuf::from(directory).join(name);
    std::fs::read_to_string(&path).unwrap_or_else(|error| {
        panic!(
            "the window fixture {} is unreadable ({error}); run `just fixtures-seed modelo-envelopes`",
            path.display()
        )
    })
}
