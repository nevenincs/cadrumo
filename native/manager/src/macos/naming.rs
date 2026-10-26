//! Compact manager socket identities from the shared native contract.

use crate::contract::{
    MANAGER_SOCKET_DIGEST_BYTES, MANAGER_SOCKET_DOMAIN, MANAGER_SOCKET_MAX_IDENTIFIER_BYTES,
    MANAGER_SOCKET_PREFIX, MANAGER_SOCKET_SUFFIX,
};
use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
use sha2::{Digest, Sha256};
use std::io;

pub fn socket_name(manager_id: &str, user: &str, session: &str) -> io::Result<String> {
    if manager_id.is_empty()
        || manager_id.len() > MANAGER_SOCKET_MAX_IDENTIFIER_BYTES
        || manager_id.starts_with('.')
        || manager_id.ends_with('.')
        || !manager_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'-' | b'_'))
        || !canonical_decimal(user)
        || !canonical_decimal(session)
    {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    let input = serde_json::to_vec(&[MANAGER_SOCKET_DOMAIN, manager_id, user, session])
        .map_err(io::Error::other)?;
    let digest = Sha256::digest(input);
    let encoded = URL_SAFE_NO_PAD.encode(&digest[..MANAGER_SOCKET_DIGEST_BYTES]);
    Ok(format!(
        "{MANAGER_SOCKET_PREFIX}{encoded}{MANAGER_SOCKET_SUFFIX}"
    ))
}

fn canonical_decimal(value: &str) -> bool {
    value
        .parse::<u32>()
        .is_ok_and(|parsed| parsed.to_string() == value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shared_vectors_keep_channels_owners_and_sessions_distinct() {
        let mut names = std::collections::HashSet::new();
        for vector in crate::contract::MANAGER_SOCKET_VECTORS {
            let name = socket_name(vector.manager_id, vector.user, vector.session).unwrap();
            assert_eq!(name, vector.expected_name);
            assert!(names.insert(name));
        }
        assert!(names.len() >= 4);
    }

    #[test]
    fn native_coordinates_have_one_encoding() {
        for value in ["", "01", "+1", "-1", " 1", "4294967296", "1/2", "ñ"] {
            assert!(socket_name("test.manager", value, "1").is_err());
            assert!(socket_name("test.manager", "1", value).is_err());
        }
        assert!(socket_name("test/manager", "1", "1").is_err());
        assert!(socket_name("test.manager", "0", "4294967295").is_ok());
    }
}
