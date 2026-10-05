//! Refuses ambient WebView2 overrides before the window exists.
//!
//! The WebView2 loader and runtime read these variables from the host's own
//! environment, and they take precedence over the profile directory and
//! browser arguments the host chooses. Inherited from a parent process or a
//! user profile, they could move the profile out of the storage root, load a
//! browser from another folder, add browser arguments such as a remote
//! debugging port, attach a script debugger, or select a preview channel the
//! security settings were not verified against. A packaged build therefore
//! refuses to start while any of them is set.
//!
//! The variables were taken from the loader in `webview2-com-sys` 0.39.1 and
//! the installed WebView2 runtime. Variables that only affect presentation,
//! such as the default background color or the hosting mode, are not refused.
//!
//! Development builds, which load the shell from the development server,
//! are not checked. A build with the `webview2-remote-debugging` feature,
//! made only for the packaged end-to-end test, also admits
//! `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` when it is exactly one
//! `--remote-debugging-port=<port>` argument. No runtime switch relaxes the
//! check.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::ffi::OsString;

const ADDITIONAL_BROWSER_ARGUMENTS: &str = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS";

/// The refused variables and what each overrides.
const REFUSED: [&str; 9] = [
    // The profile directory.
    "WEBVIEW2_USER_DATA_FOLDER",
    // The browser executable folder.
    "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER",
    // Arbitrary browser command-line arguments.
    ADDITIONAL_BROWSER_ARGUMENTS,
    // A named pipe a script debugger attaches through, and a wait for it.
    "WEBVIEW2_PIPE_FOR_SCRIPT_DEBUGGER",
    "WEBVIEW2_WAIT_FOR_SCRIPT_DEBUGGER",
    // Which installed runtime or Edge channel is loaded.
    "WEBVIEW2_RELEASE_CHANNEL_PREFERENCE",
    "WEBVIEW2_RELEASE_CHANNELS",
    "WEBVIEW2_CHANNEL_SEARCH_KIND",
    "WEBVIEW2_USE_EDGE_VIEW",
];

/// How strictly a build checks.
#[derive(Clone, Copy)]
struct Policy {
    development: bool,
    remote_debugging: bool,
}

impl Policy {
    fn of_this_build() -> Self {
        Self {
            development: tauri::is_dev(),
            remote_debugging: cfg!(feature = "webview2-remote-debugging"),
        }
    }
}

/// Whether `value` is exactly one remote debugging port argument.
fn remote_debugging_port(value: &OsString) -> bool {
    value
        .to_str()
        .and_then(|text| text.strip_prefix("--remote-debugging-port="))
        .is_some_and(|port| {
            !port.starts_with('0')
                && port.bytes().all(|byte| byte.is_ascii_digit())
                && port.parse::<u16>().is_ok_and(|port| port > 0)
        })
}

/// The first refused variable `environment` sets under `policy`. Windows
/// variable names are case-insensitive, so names are compared that way.
fn first_refused(
    environment: impl IntoIterator<Item = (OsString, OsString)>,
    policy: Policy,
) -> Option<&'static str> {
    if policy.development {
        return None;
    }
    environment.into_iter().find_map(|(name, value)| {
        let name = name.to_str()?;
        let refused = REFUSED
            .into_iter()
            .find(|refused| name.eq_ignore_ascii_case(refused))?;
        let admitted = policy.remote_debugging
            && refused == ADDITIONAL_BROWSER_ARGUMENTS
            && remote_debugging_port(&value);
        (!admitted).then_some(refused)
    })
}

fn check(
    environment: impl IntoIterator<Item = (OsString, OsString)>,
    policy: Policy,
) -> Result<()> {
    match first_refused(environment, policy) {
        Some(name) => Err(
            ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Webview)
                .caused_by(std::io::Error::other(format!("{name} is set"))),
        ),
        None => Ok(()),
    }
}

/// Refuses to start while the process environment overrides WebView2.
pub fn refuse_overrides() -> Result<()> {
    check(std::env::vars_os(), Policy::of_this_build())
}

#[cfg(test)]
mod tests {
    use super::*;

    const PACKAGED: Policy = Policy {
        development: false,
        remote_debugging: false,
    };
    const DEBUGGING: Policy = Policy {
        development: false,
        remote_debugging: true,
    };
    const DEVELOPMENT: Policy = Policy {
        development: true,
        remote_debugging: false,
    };

    fn environment(pairs: &[(&str, &str)]) -> Vec<(OsString, OsString)> {
        pairs
            .iter()
            .map(|(name, value)| (OsString::from(name), OsString::from(value)))
            .collect()
    }

    const ORDINARY: [(&str, &str); 3] = [
        ("PATH", r"C:\Windows\System32"),
        ("WEBVIEW2_DEFAULT_BACKGROUND_COLOR", "0"),
        ("WEBVIEW2_USER_DATA", "not an override"),
    ];

    /// The variables the WebView2 loader and runtime read that relocate the
    /// profile, replace the browser, add arguments, attach a debugger or pick
    /// the channel, written out independently of the refused list.
    const OVERRIDES: [&str; 9] = [
        "WEBVIEW2_USER_DATA_FOLDER",
        "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER",
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "WEBVIEW2_PIPE_FOR_SCRIPT_DEBUGGER",
        "WEBVIEW2_WAIT_FOR_SCRIPT_DEBUGGER",
        "WEBVIEW2_RELEASE_CHANNEL_PREFERENCE",
        "WEBVIEW2_RELEASE_CHANNELS",
        "WEBVIEW2_CHANNEL_SEARCH_KIND",
        "WEBVIEW2_USE_EDGE_VIEW",
    ];

    #[test]
    fn every_override_is_refused_in_a_packaged_build() {
        assert!(check(environment(&ORDINARY), PACKAGED).is_ok());
        for name in OVERRIDES {
            for spelled in [name.to_owned(), name.to_ascii_lowercase()] {
                let mut set = environment(&ORDINARY);
                set.push((spelled.clone().into(), "x".into()));
                let error = check(set, PACKAGED).unwrap_err();
                assert_eq!(error.code, ErrorCode::EnvironmentFailed, "{spelled}");
                assert_eq!(error.operation, Operation::Webview);
            }
            // An empty value is still set.
            let set = environment(&[(name, "")]);
            assert_eq!(first_refused(set, PACKAGED), Some(name));
        }
    }

    #[test]
    fn the_test_build_admits_only_a_remote_debugging_port() {
        for value in ["--remote-debugging-port=9222", "--remote-debugging-port=1"] {
            let set = environment(&[(ADDITIONAL_BROWSER_ARGUMENTS, value)]);
            assert_eq!(first_refused(set.clone(), DEBUGGING), None, "{value}");
            assert_eq!(
                first_refused(set, PACKAGED),
                Some(ADDITIONAL_BROWSER_ARGUMENTS),
                "{value}"
            );
        }
        for value in [
            "",
            "--remote-debugging-port=0",
            "--remote-debugging-port=09222",
            "--remote-debugging-port=65536",
            "--remote-debugging-port=",
            "--remote-debugging-port=9222 --user-data-dir=C:\\elsewhere",
            "--remote-debugging-port=9222 ",
            "--remote-debugging-address=0.0.0.0",
            "--remote-allow-origins=*",
            "--remote-debugging-pipe",
        ] {
            let set = environment(&[(ADDITIONAL_BROWSER_ARGUMENTS, value)]);
            assert_eq!(
                first_refused(set, DEBUGGING),
                Some(ADDITIONAL_BROWSER_ARGUMENTS),
                "{value:?}"
            );
        }
        // Every other override stays refused in the test build.
        for name in OVERRIDES
            .into_iter()
            .filter(|name| *name != ADDITIONAL_BROWSER_ARGUMENTS)
        {
            let set = environment(&[(name, "--remote-debugging-port=9222")]);
            assert_eq!(first_refused(set, DEBUGGING), Some(name));
        }
    }

    #[test]
    fn a_development_build_is_not_checked() {
        let set = environment(&[("WEBVIEW2_USER_DATA_FOLDER", r"C:\elsewhere")]);
        assert!(check(set, DEVELOPMENT).is_ok());
    }

    #[test]
    fn this_build_is_checked_unless_it_is_a_development_build() {
        let policy = Policy::of_this_build();
        assert_eq!(policy.development, tauri::is_dev());
        assert_eq!(
            policy.remote_debugging,
            cfg!(feature = "webview2-remote-debugging")
        );
    }
}
