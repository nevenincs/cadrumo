use crate::error::Error;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fmt,
    path::{Path, PathBuf},
};

/// A portable package-relative path, with the same meaning on every target.
#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct RelativePath(String);

impl RelativePath {
    pub fn from_native(value: &Path) -> Result<Self, Error> {
        let mut parts = Vec::new();
        for component in value.components() {
            let std::path::Component::Normal(part) = component else {
                return Err(Error::Invalid("unsafe native relative path".into()));
            };
            parts.push(
                part.to_str()
                    .ok_or_else(|| Error::Invalid("non-UTF8 relative path".into()))?,
            );
        }
        Self::new(parts.join("/"))
    }
    pub fn new(value: impl Into<String>) -> Result<Self, Error> {
        let value = value.into();
        if value.is_empty()
            || value.contains(['\\', ':', '\0'])
            || value.chars().any(char::is_control)
        {
            return Err(Error::Invalid("unsafe relative path".into()));
        }
        for part in value.split('/') {
            let stem = part.split('.').next().unwrap_or("").to_ascii_uppercase();
            if part.is_empty()
                || part == "."
                || part == ".."
                || part.ends_with(['.', ' '])
                || matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                || (stem.len() == 4
                    && (stem.starts_with("COM") || stem.starts_with("LPT"))
                    && matches!(stem.as_bytes()[3], b'1'..=b'9'))
                || part.contains(['<', '>', '"', '|', '?', '*'])
            {
                return Err(Error::Invalid("unsafe relative path component".into()));
            }
        }
        Ok(Self(value))
    }
    pub fn as_str(&self) -> &str {
        &self.0
    }
    pub fn under(&self, root: &Path) -> PathBuf {
        root.join(&self.0)
    }
}
impl TryFrom<String> for RelativePath {
    type Error = Error;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}
impl From<RelativePath> for String {
    fn from(value: RelativePath) -> Self {
        value.0
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct Sha256Digest(String);

impl Sha256Digest {
    pub fn new(value: impl Into<String>) -> Result<Self, Error> {
        let value = value.into();
        if value.len() != 64 || !value.bytes().all(|c| c.is_ascii_hexdigit()) {
            return Err(Error::Invalid("expected SHA256 hex digest".into()));
        }
        Ok(Self(value.to_ascii_lowercase()))
    }
    /// The digest of `bytes`.
    pub fn of(bytes: impl AsRef<[u8]>) -> Self {
        Self(hex(&Sha256::digest(bytes)))
    }
    /// Renders a finished SHA-256 hash; any other length is refused.
    pub fn from_hash(hash: impl AsRef<[u8]>) -> Result<Self, Error> {
        let hash = hash.as_ref();
        if hash.len() != 32 {
            return Err(Error::Invalid("expected a 32-byte SHA256 hash".into()));
        }
        Ok(Self(hex(hash)))
    }
    pub fn as_str(&self) -> &str {
        &self.0
    }
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}
impl TryFrom<String> for Sha256Digest {
    type Error = Error;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}
impl From<Sha256Digest> for String {
    fn from(value: Sha256Digest) -> Self {
        value.0
    }
}
impl fmt::Display for Sha256Digest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

/// A lowercase, fully qualified DNS host name with no port, as declared in package data.
#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct HostName(String);

impl HostName {
    pub fn new(value: impl Into<String>) -> Result<Self, Error> {
        let value = value.into();
        let labels: Vec<&str> = value.split('.').collect();
        // A top-level label is never all digits, which keeps IPv4 literals out.
        if value.len() > 253
            || labels.len() < 2
            || labels
                .last()
                .is_some_and(|label| label.bytes().all(|c| c.is_ascii_digit()))
            || labels.iter().any(|label| {
                label.is_empty()
                    || label.len() > 63
                    || label.starts_with('-')
                    || label.ends_with('-')
                    || !label
                        .bytes()
                        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
            })
        {
            return Err(Error::Invalid("expected a lowercase host name".into()));
        }
        Ok(Self(value))
    }
    pub fn as_str(&self) -> &str {
        &self.0
    }
}
impl TryFrom<String> for HostName {
    type Error = Error;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}
impl From<HostName> for String {
    fn from(value: HostName) -> Self {
        value.0
    }
}
impl fmt::Display for HostName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
