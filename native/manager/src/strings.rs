//! Native labels from the build's canonical locale projection.

use crate::contract::{MANAGER_LANGUAGE_DEFAULT, MANAGER_LANGUAGE_ENV, MANAGER_STRINGS_JSON};
use std::{collections::BTreeMap, io};

pub struct Strings(BTreeMap<String, String>);
impl Strings {
    pub fn current() -> io::Result<Self> {
        Self::for_language(std::env::var(MANAGER_LANGUAGE_ENV).ok().as_deref())
    }
    fn for_language(language: Option<&str>) -> io::Result<Self> {
        let mut catalogue: BTreeMap<String, BTreeMap<String, String>> =
            serde_json::from_str(MANAGER_STRINGS_JSON).map_err(io::Error::other)?;
        let language = language
            .unwrap_or(MANAGER_LANGUAGE_DEFAULT)
            .trim()
            .to_lowercase();
        let selected = catalogue
            .remove(&language)
            .or_else(|| catalogue.remove(MANAGER_LANGUAGE_DEFAULT))
            .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?;
        Ok(Self(selected))
    }
    pub fn get(&self, key: &str) -> &str {
        // A missing generated key is a build contract defect, not translated UI text.
        self.0
            .get(&format!("common.manager.{key}"))
            .expect("canonical manager label")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn supported_languages_and_invalid_value_follow_canonical_default() {
        for (language, quit) in [
            ("en", "Quit"),
            ("es", "Salir"),
            ("ca", "Sortir"),
            ("hu", "Kilépés"),
        ] {
            assert_eq!(
                Strings::for_language(Some(language)).unwrap().get("quit"),
                quit
            );
        }
        assert_eq!(
            Strings::for_language(Some("invalid")).unwrap().get("quit"),
            Strings::for_language(None).unwrap().get("quit")
        );
    }
}
