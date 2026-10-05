//! The closed set of media types the documentation scheme serves, read from
//! the package layout's `user_docs.media_types` declaration that the
//! generated package contract carries.

use super::site::unavailable;
use cadrumo_application::{
    error::application::{ApplicationError, Result},
    value::RelativePath,
};
use serde::Deserialize;
use std::collections::BTreeMap;
use tauri::http::HeaderValue;

/// The generated package contract this host was built against.
pub(super) const CONTRACT: &str = include_str!(concat!(env!("OUT_DIR"), "/contract.json"));

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
}

#[derive(Deserialize)]
struct Layout {
    user_docs: UserDocs,
}

#[derive(Deserialize)]
struct UserDocs {
    media_types: Declaration,
}

/// The declared table: exact file names, then the text after a name's last
/// dot. Any other key is refused.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Declaration {
    names: BTreeMap<String, String>,
    extensions: BTreeMap<String, String>,
}

/// The media-type table admitted for serving. A file whose name it does not
/// type is not served.
pub struct MediaTypes {
    names: BTreeMap<String, HeaderValue>,
    extensions: BTreeMap<String, HeaderValue>,
}

fn refused(reason: String) -> ApplicationError {
    unavailable().caused_by(std::io::Error::other(reason))
}

impl MediaTypes {
    /// The table the package layout declares for this build.
    pub fn declared() -> Result<Self> {
        Self::from_contract(CONTRACT)
    }

    /// Reads the table from a package contract's layout.
    pub fn from_contract(contract: &str) -> Result<Self> {
        let contract: Contract =
            serde_json::from_str(contract).map_err(|e| unavailable().caused_by(e))?;
        Self::admit(contract.layout.user_docs.media_types)
    }

    /// Reads a `user_docs.media_types` table on its own.
    #[cfg(test)]
    pub fn from_table(table: serde_json::Value) -> Result<Self> {
        Self::admit(serde_json::from_value(table).map_err(|e| unavailable().caused_by(e))?)
    }

    /// Names must not hold a separator and extensions must not hold a dot
    /// either, so each key can only match within one file name. Every type
    /// enters a response header and must be a valid header value.
    fn admit(declaration: Declaration) -> Result<Self> {
        let names = section("names", declaration.names, &['/', '\\'])?;
        let extensions = section("extensions", declaration.extensions, &['.', '/', '\\'])?;
        if extensions.is_empty() {
            return Err(refused(
                "user_docs.media_types.extensions must not be empty".into(),
            ));
        }
        Ok(Self { names, extensions })
    }

    /// The media type a file name is served as: an exact name first, then
    /// the text after the name's last dot. Both comparisons are exact and
    /// case-sensitive.
    pub fn of(&self, name: &str) -> Option<&HeaderValue> {
        if let Some(media) = self.names.get(name) {
            return Some(media);
        }
        let (_, extension) = name.rsplit_once('.')?;
        self.extensions.get(extension)
    }

    /// The media type of a manifest member, from its final path segment.
    pub fn of_member(&self, path: &RelativePath) -> Option<&HeaderValue> {
        self.of(path.as_str().rsplit('/').next().unwrap_or_default())
    }
}

fn section(
    label: &str,
    entries: BTreeMap<String, String>,
    forbidden: &[char],
) -> Result<BTreeMap<String, HeaderValue>> {
    entries
        .into_iter()
        .map(|(key, media)| {
            let invalid = || {
                refused(format!(
                    "user_docs.media_types.{label} has an invalid entry: {key:?}"
                ))
            };
            if key.is_empty() || key.contains(forbidden) || media.is_empty() {
                return Err(invalid());
            }
            let media = HeaderValue::from_str(&media).map_err(|_| invalid())?;
            Ok((key, media))
        })
        .collect()
}
