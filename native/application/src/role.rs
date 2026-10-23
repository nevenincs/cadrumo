//! The roles the one Cadrumo binary runs as, selected by a reserved first argument.
//!
//! Every Cadrumo-managed process is the `cadrumo` image, so Windows shows the whole tree
//! under one application. No argument is the desktop; `--role NAME` selects another role
//! before any window or webview exists. A role name grants nothing by itself: admission
//! still proves how a peer was started.

use std::ffi::OsStr;

/// The argument that, in first position, selects a role.
pub const ROLE_ARGUMENT: &str = "--role";

/// A role other than the desktop.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Role {
    /// The `cadrumo-runtime` console script: the supervised local runtime, and the
    /// runtime session commands the desktop runs.
    Runtime,
    /// The `aeat` console script, for the commands the desktop runs.
    Cli,
    /// The package interpreter itself, which the runtime's workers and its KDF child run.
    Python,
}

/// What a role runs inside the linked interpreter host.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HostedImage {
    /// The declared launch image whose profile defines the environment.
    pub image: &'static str,
    /// The console script it runs, or `None` for the interpreter itself.
    pub entrypoint: Option<&'static str>,
}

/// Why role selection refused the arguments.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RoleRefusal {
    /// `--role` with no name.
    Missing,
    /// A name that is not a declared role.
    Unknown,
}

impl Role {
    pub const ALL: [Role; 3] = [Role::Runtime, Role::Cli, Role::Python];

    pub const fn name(self) -> &'static str {
        match self {
            Role::Runtime => "runtime",
            Role::Cli => "cli",
            Role::Python => "python",
        }
    }

    /// The leading arguments that start this role.
    pub const fn arguments(self) -> &'static [&'static str; 2] {
        match self {
            Role::Runtime => &[ROLE_ARGUMENT, "runtime"],
            Role::Cli => &[ROLE_ARGUMENT, "cli"],
            Role::Python => &[ROLE_ARGUMENT, "python"],
        }
    }

    pub fn hosted(self) -> HostedImage {
        match self {
            Role::Runtime => HostedImage {
                image: "cadrumo-runtime",
                entrypoint: Some("cadrumo-runtime"),
            },
            Role::Cli => HostedImage {
                image: "aeat",
                entrypoint: Some("aeat"),
            },
            Role::Python => HostedImage {
                image: "python",
                entrypoint: None,
            },
        }
    }

    /// The role that runs the console script `entrypoint`, if one does.
    pub fn hosting(entrypoint: &str) -> Option<Role> {
        Role::ALL
            .into_iter()
            .find(|role| role.hosted().entrypoint == Some(entrypoint))
    }

    fn named(name: &OsStr) -> Option<Role> {
        Role::ALL.into_iter().find(|role| name == role.name())
    }
}

/// The role `arguments` (after the image path) select and the arguments it receives,
/// or `None` when the first argument is not the role argument.
pub fn select<T: AsRef<OsStr>>(arguments: &[T]) -> Option<Result<(Role, &[T]), RoleRefusal>> {
    let (first, rest) = arguments.split_first()?;
    if first.as_ref() != ROLE_ARGUMENT {
        return None;
    }
    let Some((name, forwarded)) = rest.split_first() else {
        return Some(Err(RoleRefusal::Missing));
    };
    Some(
        Role::named(name.as_ref())
            .map(|role| (role, forwarded))
            .ok_or(RoleRefusal::Unknown),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsString;

    fn arguments(values: &[&str]) -> Vec<OsString> {
        values.iter().map(OsString::from).collect()
    }

    #[test]
    fn a_declared_role_receives_only_the_arguments_after_its_name() {
        let given = arguments(&["--role", "runtime", "--supervised", "--role"]);
        let (role, forwarded) = select(&given).unwrap().unwrap();
        assert_eq!(role, Role::Runtime);
        assert_eq!(forwarded, &given[2..]);
        assert_eq!(Role::Runtime.arguments(), &["--role", "runtime"]);
        assert_eq!(Role::Cli.arguments(), &["--role", "cli"]);
    }

    #[test]
    fn other_first_arguments_are_not_a_role() {
        for given in [
            arguments(&[]),
            arguments(&["runtime"]),
            arguments(&["--headless", "--role", "runtime"]),
            arguments(&["--role=runtime"]),
        ] {
            assert!(select(&given).is_none(), "{given:?}");
        }
    }

    #[test]
    fn a_missing_or_undeclared_role_is_refused() {
        assert_eq!(
            select(&arguments(&["--role"])).unwrap().unwrap_err(),
            RoleRefusal::Missing
        );
        for name in [
            "",
            "Runtime",
            "desktop",
            "Python",
            "interpreter",
            "runtime ",
        ] {
            assert_eq!(
                select(&arguments(&["--role", name])).unwrap().unwrap_err(),
                RoleRefusal::Unknown,
                "{name:?}"
            );
        }
    }

    #[test]
    fn every_role_hosts_a_declared_launch_image() {
        for role in Role::ALL {
            let hosted = role.hosted();
            assert!(!hosted.image.is_empty());
            assert_eq!(role.arguments()[1], role.name());
            assert_eq!(select(role.arguments()).unwrap().unwrap().0, role);
            if let Some(entrypoint) = hosted.entrypoint {
                assert!(!entrypoint.is_empty());
                assert_eq!(Role::hosting(entrypoint), Some(role));
            }
        }
        assert_eq!(Role::Python.hosted().entrypoint, None);
        for entrypoint in ["cadrumo-agent-service", "cadrumo-mcp", "python", "", "AEAT"] {
            assert_eq!(Role::hosting(entrypoint), None, "{entrypoint:?}");
        }
    }
}
