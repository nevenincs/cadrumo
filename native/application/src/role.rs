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
    /// The supervised local runtime, the `cadrumo-runtime` console script.
    Runtime,
}

/// What a role runs inside the linked interpreter host.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HostedImage {
    /// The declared launch image whose profile defines the environment.
    pub image: &'static str,
    /// The console script it runs.
    pub entrypoint: &'static str,
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
    pub const ALL: [Role; 1] = [Role::Runtime];

    pub const fn name(self) -> &'static str {
        match self {
            Role::Runtime => "runtime",
        }
    }

    /// The leading arguments that start this role.
    pub const fn arguments(self) -> &'static [&'static str; 2] {
        match self {
            Role::Runtime => &[ROLE_ARGUMENT, "runtime"],
        }
    }

    pub fn hosted(self) -> HostedImage {
        match self {
            Role::Runtime => HostedImage {
                image: "cadrumo-runtime",
                entrypoint: "cadrumo-runtime",
            },
        }
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
        for name in ["", "Runtime", "desktop", "python", "runtime "] {
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
            assert!(!hosted.image.is_empty() && !hosted.entrypoint.is_empty());
            assert_eq!(role.arguments()[1], role.name());
            assert_eq!(select(role.arguments()).unwrap().unwrap().0, role);
        }
    }
}
