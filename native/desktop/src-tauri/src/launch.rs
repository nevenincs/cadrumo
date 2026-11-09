use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::ffi::{OsStr, OsString};

#[derive(Debug, PartialEq)]
pub enum Mode {
    Gui,
    Health { hold_seconds: u64 },
    Cli(Vec<OsString>),
}

/// Whether this process runs in a session that can show a window. A refusal
/// carries only the kind and OS code of what established it, so a launch that
/// falls back to the CLI records why.
pub fn desktop_available() -> Result<()> {
    let unavailable = || ApplicationError::new(ErrorCode::DesktopUnavailable, Operation::Launch);
    #[cfg(windows)]
    {
        cadrumo_platform::desktop::available()
            .then_some(())
            .ok_or_else(unavailable)
    }
    #[cfg(target_os = "linux")]
    {
        ["WAYLAND_DISPLAY", "DISPLAY"]
            .iter()
            .any(|name| std::env::var_os(name).is_some_and(|v| !v.is_empty()))
            .then_some(())
            .ok_or_else(unavailable)
    }
    #[cfg(target_os = "macos")]
    {
        graphical_session()
            .map(drop)
            .map_err(|error| unavailable().caused_by(error))
    }
}

/// How the host puts its windows on the operator's desktop.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ShowMode {
    /// A window is shown, restored and focused as the operator expects.
    Activate,
    /// The isolated WebDriver test host: a window appears but never takes the
    /// foreground or focus, because the automation plugin drives the page
    /// through the webview and needs neither.
    NoActivate,
}

impl ShowMode {
    /// `NoActivate` only for a host compiled with `native-automation` whose launcher
    /// supplied `TAURI_WEBDRIVER_PORT`. Every other host activates.
    pub fn decide(automation_feature: bool, webdriver_port: Option<&OsStr>) -> Self {
        if automation_feature && webdriver_port.is_some() {
            Self::NoActivate
        } else {
            Self::Activate
        }
    }

    pub fn current() -> Self {
        Self::decide(
            cfg!(feature = "native-automation"),
            std::env::var_os("TAURI_WEBDRIVER_PORT").as_deref(),
        )
    }

    pub fn activates(self) -> bool {
        self == Self::Activate
    }
}

/// The kernel audit session of this process, when the Security framework
/// reports it as a local graphical login. A remote or background session,
/// such as an SSH login, has no window server access and is refused, as is
/// any failure to establish the session, so the launch falls back to the
/// CLI. The admission is the one the manager applies to its own process.
#[cfg(target_os = "macos")]
pub fn graphical_session() -> std::io::Result<u32> {
    use cadrumo_manager::macos::{login::Login, process::Process};
    let process = Process::open(std::process::id())?;
    Ok(Login::open()?.current(&process)?.id())
}

pub fn select(mut arguments: Vec<OsString>, desktop: bool) -> Result<Mode> {
    if arguments.first().is_some_and(|arg| arg == "--check-health") {
        let hold_seconds = match arguments.as_slice() {
            [_] => Some(0),
            [_, flag, value] if flag == "--hold-seconds" => value
                .to_str()
                .and_then(|value| value.parse::<u64>().ok())
                .filter(|value| (1..=60).contains(value)),
            _ => None,
        }
        .ok_or_else(|| ApplicationError::new(ErrorCode::InvalidArguments, Operation::Launch))?;
        return Ok(Mode::Health { hold_seconds });
    }
    if arguments.first().is_some_and(|arg| arg == "--headless") {
        arguments.remove(0);
        if arguments.first().is_some_and(|arg| arg == "--") {
            arguments.remove(0);
        }
        return Ok(Mode::Cli(arguments));
    }
    if arguments.first().is_some_and(|arg| arg == "--gui") {
        if arguments.len() != 1 {
            return Err(ApplicationError::new(
                ErrorCode::InvalidArguments,
                Operation::Launch,
            ));
        }
        return if desktop {
            Ok(Mode::Gui)
        } else {
            Err(ApplicationError::new(
                ErrorCode::DesktopUnavailable,
                Operation::Launch,
            ))
        };
    }
    if !arguments.is_empty() || !desktop {
        Ok(Mode::Cli(arguments))
    } else {
        Ok(Mode::Gui)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_automation_host_with_a_webdriver_port_shows_without_activating() {
        let port = OsStr::new("4444");
        assert_eq!(ShowMode::decide(true, Some(port)), ShowMode::NoActivate);
        assert_eq!(ShowMode::decide(true, None), ShowMode::Activate);
        assert_eq!(ShowMode::decide(false, Some(port)), ShowMode::Activate);
        assert_eq!(ShowMode::decide(false, None), ShowMode::Activate);
        assert!(!ShowMode::NoActivate.activates());
        assert!(ShowMode::Activate.activates());
    }

    #[test]
    fn mode_selection_preserves_cli_arguments_and_refuses_forced_headless_gui() {
        assert_eq!(
            select(vec!["--check-health".into()], false).unwrap(),
            Mode::Health { hold_seconds: 0 }
        );
        assert_eq!(select(vec![], true).unwrap(), Mode::Gui);
        assert_eq!(select(vec![], false).unwrap(), Mode::Cli(vec![]));
        let args = vec!["--format".into(), "json".into(), "a b á漢".into()];
        assert_eq!(select(args.clone(), true).unwrap(), Mode::Cli(args.clone()));
        let mut headless = vec!["--headless".into(), "--".into()];
        headless.extend(args.clone());
        assert_eq!(select(headless, true).unwrap(), Mode::Cli(args));
        assert_eq!(
            select(vec!["--gui".into()], false).unwrap_err().code,
            ErrorCode::DesktopUnavailable
        );
        assert!(select(vec!["--gui".into(), "--help".into()], true).is_err());
    }

    #[test]
    fn health_observation_is_bounded_and_rejects_malformed_arguments() {
        assert_eq!(
            select(
                vec![
                    "--check-health".into(),
                    "--hold-seconds".into(),
                    "60".into()
                ],
                false
            )
            .unwrap(),
            Mode::Health { hold_seconds: 60 }
        );
        for value in ["0", "61", "-1", "forever"] {
            assert_eq!(
                select(
                    vec![
                        "--check-health".into(),
                        "--hold-seconds".into(),
                        value.into()
                    ],
                    false
                )
                .unwrap_err()
                .code,
                ErrorCode::InvalidArguments
            );
        }
        assert!(
            select(
                vec!["--check-health".into(), "--hold-seconds".into()],
                false
            )
            .is_err()
        );
    }
}
