//! The allow-list environment a managed runtime starts with.
//!
//! The manager passes only operating-system variables a desktop process needs. No product
//! override (`CADRUMO_*`, including `CADRUMO_DEV_*`), no setting the runtime would read, no
//! interpreter or loader variable and no name the packaged host pins itself reaches the
//! runtime, so a root or authority chosen by the manager's own environment stays
//! developer-owned and unmanaged. The canonical location definition replaces this list
//! when the manager consumes it through `native/platform`.

use std::ffi::{OsStr, OsString};

/// Variables a Windows desktop process needs, compared case-insensitively.
pub const WINDOWS_ALLOWED: &[&str] = &[
    "ALLUSERSPROFILE",
    "APPDATA",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "COMMONPROGRAMW6432",
    "COMPUTERNAME",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "LOGONSERVER",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "PUBLIC",
    "SESSIONNAME",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "USERDOMAIN",
    "USERDOMAIN_ROAMINGPROFILE",
    "USERNAME",
    "USERPROFILE",
    "WINDIR",
];

/// Variables a POSIX desktop session process needs, compared exactly.
pub const POSIX_ALLOWED: &[&str] = &[
    "DBUS_SESSION_BUS_ADDRESS",
    "DISPLAY",
    "HOME",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_COLLATE",
    "LC_CTYPE",
    "LC_MESSAGES",
    "LC_MONETARY",
    "LC_NUMERIC",
    "LC_TIME",
    "LOGNAME",
    "PATH",
    "SHELL",
    "TZ",
    "USER",
    "WAYLAND_DISPLAY",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_ID",
    "XDG_SESSION_TYPE",
    "XDG_STATE_HOME",
];

/// The allow-list for the platform this manager runs on.
pub fn allowed_names() -> &'static [&'static str] {
    if cfg!(windows) {
        WINDOWS_ALLOWED
    } else {
        POSIX_ALLOWED
    }
}

fn is_allowed(name: &OsStr) -> bool {
    let Some(name) = name.to_str() else {
        return false;
    };
    if cfg!(windows) {
        WINDOWS_ALLOWED
            .iter()
            .any(|allowed| allowed.eq_ignore_ascii_case(name))
    } else {
        POSIX_ALLOWED.contains(&name)
    }
}

/// Keep only allow-listed variables from `inherited`, in their original order.
pub fn runtime_environment(
    inherited: impl IntoIterator<Item = (OsString, OsString)>,
) -> Vec<(OsString, OsString)> {
    inherited
        .into_iter()
        .filter(|(name, _)| is_allowed(name))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::{
        CLEARED_NAMES, CLEARED_PREFIXES, HOST_INHERITED_ENV, NAMESPACE_PREFIX,
        PACKAGE_ENV_ALLOWLIST, PINNED_ENV, PRODUCT_ENV_ALLOWLIST, RESERVED_ENV,
    };

    #[test]
    fn no_allowed_name_is_a_product_setting_loader_or_pinned_name() {
        for name in WINDOWS_ALLOWED.iter().chain(POSIX_ALLOWED) {
            let upper = name.to_ascii_uppercase();
            assert!(!upper.starts_with(NAMESPACE_PREFIX), "{name}");
            assert!(
                !CLEARED_PREFIXES
                    .iter()
                    .any(|prefix| upper.starts_with(prefix)),
                "{name}"
            );
            for owned in [
                CLEARED_NAMES,
                RESERVED_ENV,
                PINNED_ENV,
                HOST_INHERITED_ENV,
                PRODUCT_ENV_ALLOWLIST,
                PACKAGE_ENV_ALLOWLIST,
            ] {
                assert!(!owned.contains(&upper.as_str()), "{name}");
            }
        }
    }

    #[test]
    fn product_development_and_interpreter_overrides_never_pass() {
        let inherited = [
            ("CADRUMO_LOCAL_STORAGE_ROOT", "D:\\elsewhere"),
            ("CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE", "1"),
            ("cadrumo_authority_root", "D:\\authority"),
            ("PYTHONPATH", "D:\\python"),
            ("TEMP", "D:\\temp"),
            ("AEAT_BASE_URL", "https://example.invalid"),
            ("HOME", "/home/ada"),
            ("SystemRoot", "C:\\Windows"),
            ("Path", "C:\\Windows\\System32"),
        ]
        .map(|(name, value)| (OsString::from(name), OsString::from(value)));
        let kept: Vec<String> = runtime_environment(inherited)
            .into_iter()
            .map(|(name, _)| name.into_string().expect("ASCII name"))
            .collect();
        let expected: &[&str] = if cfg!(windows) {
            &["SystemRoot", "Path"]
        } else {
            &["HOME"]
        };
        assert_eq!(kept, expected);
    }
}
