//! Names projected from the canonical product identity at build time.
//!
//! The build supplies each value as a `CADRUMO_ID_*` environment variable from the
//! distribution identity projection, so channel suffixes match the rest of the package.
//! A build without the projection fails to compile instead of falling back to a literal.

/// Release version of the package this image belongs to.
pub const VERSION: &str = env!(
    "CADRUMO_ID_VERSION",
    "CADRUMO_ID_VERSION must come from the distribution identity projection"
);
/// User-facing product name for the installation channel.
pub const NAME: &str = env!(
    "CADRUMO_ID_NAME",
    "CADRUMO_ID_NAME must come from the distribution identity projection"
);
/// Reverse-DNS application identifier for the installation channel.
pub const APPLICATION_ID: &str = env!(
    "CADRUMO_ID_APPLICATION_ID",
    "CADRUMO_ID_APPLICATION_ID must come from the distribution identity projection"
);
/// Reverse-DNS component identifier of the manager under [`APPLICATION_ID`].
pub const MANAGER_ID: &str = env!(
    "CADRUMO_ID_MANAGER_ID",
    "CADRUMO_ID_MANAGER_ID must come from the distribution identity projection"
);
/// User-facing name of the manager.
pub const MANAGER_NAME: &str = env!(
    "CADRUMO_ID_MANAGER_NAME",
    "CADRUMO_ID_MANAGER_NAME must come from the distribution identity projection"
);

const _: () = assert!(
    !VERSION.is_empty()
        && !NAME.is_empty()
        && !APPLICATION_ID.is_empty()
        && !MANAGER_ID.is_empty()
        && !MANAGER_NAME.is_empty(),
    "the distribution identity projection supplied an empty name"
);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manager_id_is_a_component_of_the_channel_application_id() {
        assert_eq!(MANAGER_ID, format!("{APPLICATION_ID}.manager"));
    }

    #[test]
    fn manager_name_extends_the_channel_name() {
        let suffix = MANAGER_NAME
            .strip_prefix(NAME)
            .expect("manager name starts with the channel name");
        assert!(
            suffix.starts_with(' ') && suffix.trim().len() > 1,
            "{suffix:?}"
        );
    }

    #[test]
    fn version_is_a_numeric_release_version() {
        let parts: Vec<_> = VERSION.split('.').collect();
        assert_eq!(parts.len(), 3, "{VERSION}");
        assert!(
            parts
                .iter()
                .all(|part| !part.is_empty() && part.bytes().all(|byte| byte.is_ascii_digit())),
            "{VERSION}"
        );
    }
}
