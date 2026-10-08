//! Per-user sign-in preference; installers never mutate this record.

use crate::{
    contract::MANAGER_PREFERENCES,
    custody::{ensure_local_directory, read_optional_local_record, write_local_record},
};
use serde::{Deserialize, Serialize};
use std::{io, path::Path};

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Preferences {
    schema: u32,
    pub start_at_sign_in: bool,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            schema: 1,
            start_at_sign_in: true,
        }
    }
}
impl Preferences {
    pub fn read(root: &Path) -> io::Result<Self> {
        let bytes = match read_optional_local_record(&root.join(MANAGER_PREFERENCES), 4096) {
            Ok(Some(bytes)) => bytes,
            Ok(None) => return Ok(Self::default()),
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Self::default()),
            Err(error) => return Err(error),
        };
        let value: Self = serde_json::from_slice(&bytes).map_err(io::Error::other)?;
        if value.schema != 1 {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok(value)
    }
    pub fn store(&self, root: &Path) -> io::Result<()> {
        if !root.is_absolute() || self.schema != 1 {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        ensure_local_directory(root)?;
        let bytes = serde_json::to_vec(self).map_err(io::Error::other)?;
        write_local_record(&root.join(MANAGER_PREFERENCES), &bytes, 4096)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn opt_out_is_atomic_persistent_and_malformed_records_refuse() {
        let root = std::env::temp_dir().join(format!(
            "manager-preferences-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        assert!(Preferences::read(&root).unwrap().start_at_sign_in);
        let preference = Preferences {
            start_at_sign_in: false,
            ..Default::default()
        };
        preference.store(&root).unwrap();
        assert_eq!(Preferences::read(&root).unwrap(), preference);
        for bytes in [
            br#"{"schema":2,"start_at_sign_in":true}"#.as_slice(),
            br#"{"schema":1,"start_at_sign_in":true,"extra":0}"#,
            br#"{"schema":1,"start_at_sign_in":true,"start_at_sign_in":false}"#,
            br#"{"schema":1,"start_at_sign_in":1}"#,
        ] {
            write_local_record(&root.join(MANAGER_PREFERENCES), bytes, 4096).unwrap();
            assert!(Preferences::read(&root).is_err());
        }
        std::fs::remove_dir_all(root).unwrap();
    }
}
