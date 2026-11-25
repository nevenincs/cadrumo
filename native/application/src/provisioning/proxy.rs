//! The operator's proxy for the downloads the engine starts, from the `CADRUMO_PROXY_*`
//! settings the package environment declares.
//!
//! Only a plain `http://` proxy reached with `CONNECT` is supported: the tunnel carries TLS
//! to the publisher end to end. The package declares no password name, so a password
//! travels inside the address, and the whole address is treated as a credential: this
//! value has no `Debug` or `Display` that shows any of it, and its texts are wiped on drop.

use super::failure::{FailureCategory, TransferFailure};
use crate::{error::Error, value::Sha256Digest};
use std::fmt;
use zeroize::Zeroizing;

pub const PROXY_URL: &str = "CADRUMO_PROXY_URL";
pub const PROXY_USERNAME: &str = "CADRUMO_PROXY_USERNAME";
pub const PROXY_BYPASS: &str = "CADRUMO_PROXY_BYPASS";

pub struct ProxySettings {
    host: Zeroizing<String>,
    port: u16,
    username: Zeroizing<String>,
    password: Zeroizing<String>,
    bypass: Vec<String>,
}

impl fmt::Debug for ProxySettings {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("ProxySettings(redacted)")
    }
}

impl ProxySettings {
    /// Reads the declared settings through `lookup`; `None` when no proxy is set. A
    /// setting the engine cannot use is the network in between: `blocked_by_network`.
    pub fn from_settings(lookup: impl Fn(&str) -> Option<String>) -> Result<Option<Self>, Error> {
        let Some(url) = lookup(PROXY_URL).map(Zeroizing::new) else {
            return Ok(None);
        };
        let raw = url.trim();
        if raw.is_empty() {
            return Ok(None);
        }
        let refused =
            || Error::Download(TransferFailure::final_(FailureCategory::BlockedByNetwork));
        let (scheme, rest) = raw.split_once("://").ok_or_else(refused)?;
        if !scheme.eq_ignore_ascii_case("http") {
            return Err(refused());
        }
        let authority = rest.strip_suffix('/').unwrap_or(rest);
        if authority.contains(['/', '?', '#']) {
            return Err(refused());
        }
        let (userinfo, hostport) = match authority.rsplit_once('@') {
            Some((userinfo, hostport)) => (Some(userinfo), hostport),
            None => (None, authority),
        };
        let (host, port) = match hostport.rsplit_once(':') {
            Some((host, port)) => (host, port.parse::<u16>().map_err(|_| refused())?),
            None => (hostport, 80),
        };
        if port == 0 || !proxy_host(host) {
            return Err(refused());
        }
        let (mut username, mut password) =
            (Zeroizing::new(String::new()), Zeroizing::new(String::new()));
        if let Some(userinfo) = userinfo {
            let (user, pass) = userinfo.split_once(':').unwrap_or((userinfo, ""));
            username = percent_decoded(user).ok_or_else(refused)?;
            password = percent_decoded(pass).ok_or_else(refused)?;
        }
        if let Some(named) = lookup(PROXY_USERNAME).map(Zeroizing::new)
            && !named.trim().is_empty()
        {
            username = Zeroizing::new(named.trim().to_owned());
        }
        let bypass = lookup(PROXY_BYPASS)
            .unwrap_or_default()
            .split(',')
            .map(|entry| {
                entry
                    .trim()
                    .trim_start_matches('*')
                    .trim_start_matches('.')
                    .trim_end_matches('.')
                    .to_ascii_lowercase()
            })
            .filter(|entry| !entry.is_empty())
            .collect();
        Ok(Some(Self {
            host: Zeroizing::new(host.to_ascii_lowercase()),
            port,
            username,
            password,
            bypass,
        }))
    }

    /// A digest of the whole effective setting, so one start's setting can be compared
    /// with another's without holding or recording any part of the address.
    ///
    /// The address is a credential, so only this digest is ever recorded, and the
    /// password is left out of the material: the digest is there to tell one route from
    /// another, and a password that changes on its own routes the download the same way.
    /// Leaving it out keeps the recorded file from committing to a secret at all.
    pub fn fingerprint(&self) -> Sha256Digest {
        let mut material = Zeroizing::new(String::new());
        for field in [
            self.host.as_str(),
            &self.port.to_string(),
            self.username.as_str(),
            &self.bypass.join(","),
        ] {
            material.push_str(field);
            material.push('\u{1f}');
        }
        Sha256Digest::of(material.as_bytes())
    }

    /// Whether `host` is reached directly: equal to, or a subdomain of, a bypass entry.
    pub fn bypasses(&self, host: &str) -> bool {
        let name = host.trim_end_matches('.').to_ascii_lowercase();
        self.bypass
            .iter()
            .any(|entry| name == *entry || name.ends_with(&format!(".{entry}")))
    }

    pub(crate) fn host(&self) -> &str {
        &self.host
    }

    pub(crate) fn port(&self) -> u16 {
        self.port
    }

    /// The standard proxy variables for a program the engine starts that downloads on
    /// its own: the whole address with its credentials, and loopback always reached
    /// directly beside the bypass entries. Every value is a credential.
    pub(crate) fn child_environment(&self) -> Vec<(&'static str, Zeroizing<String>)> {
        let mut address = Zeroizing::new(String::from("http://"));
        if !self.username.is_empty() {
            address.push_str(&percent_encoded(&self.username));
            if !self.password.is_empty() {
                address.push(':');
                address.push_str(&percent_encoded(&self.password));
            }
            address.push('@');
        }
        address.push_str(&self.host);
        address.push(':');
        address.push_str(&self.port.to_string());
        let mut bypass: Vec<&str> = self.bypass.iter().map(String::as_str).collect();
        for loopback in ["localhost", "127.0.0.1", "::1"] {
            if !bypass.contains(&loopback) {
                bypass.push(loopback);
            }
        }
        vec![
            ("HTTPS_PROXY", address.clone()),
            ("HTTP_PROXY", address),
            ("NO_PROXY", Zeroizing::new(bypass.join(","))),
        ]
    }

    /// The `Proxy-Authorization` value, when the settings carry a user name.
    pub(crate) fn authorization(&self) -> Option<Zeroizing<String>> {
        if self.username.is_empty() {
            return None;
        }
        let credentials = Zeroizing::new(format!("{}:{}", *self.username, *self.password));
        Some(Zeroizing::new(format!(
            "Basic {}",
            *base64(credentials.as_bytes())
        )))
    }
}

fn proxy_host(host: &str) -> bool {
    !host.is_empty()
        && host.len() <= 253
        && host.split('.').all(|label| {
            !label.is_empty()
                && label.len() <= 63
                && !label.starts_with('-')
                && !label.ends_with('-')
                && label
                    .bytes()
                    .all(|c| c.is_ascii_alphanumeric() || c == b'-')
        })
}

/// `value` with every byte but the unreserved characters percent-encoded, for the user
/// information of an address.
fn percent_encoded(value: &str) -> Zeroizing<String> {
    let mut out = Zeroizing::new(String::with_capacity(value.len()));
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || b"-._~".contains(&byte) {
            out.push(char::from(byte));
        } else {
            out.push_str(&format!("%{byte:02X}"));
        }
    }
    out
}

fn percent_decoded(value: &str) -> Option<Zeroizing<String>> {
    let bytes = value.as_bytes();
    let mut out = Zeroizing::new(Vec::with_capacity(bytes.len()));
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' {
            let pair = bytes.get(index + 1..index + 3)?;
            let text = std::str::from_utf8(pair).ok()?;
            out.push(u8::from_str_radix(text, 16).ok()?);
            index += 3;
        } else {
            out.push(bytes[index]);
            index += 1;
        }
    }
    String::from_utf8(out.to_vec()).ok().map(Zeroizing::new)
}

fn base64(bytes: &[u8]) -> Zeroizing<String> {
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = Zeroizing::new(String::with_capacity(bytes.len().div_ceil(3) * 4));
    for chunk in bytes.chunks(3) {
        let triple = (u32::from(chunk[0]) << 16)
            | (u32::from(chunk.get(1).copied().unwrap_or(0)) << 8)
            | u32::from(chunk.get(2).copied().unwrap_or(0));
        for position in 0..4 {
            if position <= chunk.len() {
                let index = (triple >> (18 - 6 * position)) & 0x3f;
                out.push(char::from(ALPHABET[index as usize]));
            } else {
                out.push('=');
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn settings(pairs: &[(&str, &str)]) -> Result<Option<ProxySettings>, Error> {
        let map: BTreeMap<String, String> = pairs
            .iter()
            .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
            .collect();
        ProxySettings::from_settings(|name| map.get(name).cloned())
    }

    #[test]
    fn no_setting_or_an_empty_one_is_no_proxy() {
        assert!(settings(&[]).unwrap().is_none());
        assert!(settings(&[(PROXY_URL, "  ")]).unwrap().is_none());
    }

    #[test]
    fn the_address_carries_host_port_and_credentials_and_the_user_setting_wins() {
        let proxy = settings(&[(PROXY_URL, "http://al%40ice:p%3Ass@Proxy.Corp.example:3128/")])
            .unwrap()
            .unwrap();
        assert_eq!((proxy.host(), proxy.port()), ("proxy.corp.example", 3128));
        assert_eq!(
            proxy.authorization().unwrap().as_str(),
            format!("Basic {}", *base64(b"al@ice:p:ss"))
        );
        let named = settings(&[
            (PROXY_URL, "http://al:secret@10.0.0.1"),
            (PROXY_USERNAME, "bob"),
        ])
        .unwrap()
        .unwrap();
        assert_eq!((named.host(), named.port()), ("10.0.0.1", 80));
        assert_eq!(
            named.authorization().unwrap().as_str(),
            format!("Basic {}", *base64(b"bob:secret"))
        );
        assert!(
            settings(&[(PROXY_URL, "http://proxy.example:8080")])
                .unwrap()
                .unwrap()
                .authorization()
                .is_none()
        );
    }

    #[test]
    fn a_proxy_the_engine_cannot_use_is_blocked_by_the_network() {
        for value in [
            "https://proxy.example:443",
            "socks5://proxy.example:1080",
            "proxy.example:3128",
            "http://proxy.example:0",
            "http://proxy.example:notaport",
            "http://proxy.example/path",
            "http://pro xy.example",
            "http://user:%zz@proxy.example",
        ] {
            match settings(&[(PROXY_URL, value)]) {
                Err(Error::Download(failure)) => {
                    assert_eq!(
                        failure.category,
                        FailureCategory::BlockedByNetwork,
                        "{value}"
                    );
                    assert!(!failure.transient);
                }
                other => panic!("{value}: {other:?}"),
            }
        }
    }

    #[test]
    fn the_settings_never_show_the_address_or_credentials() {
        let proxy = settings(&[(PROXY_URL, "http://user:hunter2@secret-proxy.example:3128")])
            .unwrap()
            .unwrap();
        let shown = format!("{proxy:?}");
        assert!(
            !shown.contains("hunter2")
                && !shown.contains("secret-proxy")
                && !shown.contains("3128")
        );
    }

    #[test]
    fn the_fingerprint_tells_one_route_from_another_and_commits_to_no_password() {
        let route = |url: &str| {
            settings(&[(PROXY_URL, url)])
                .unwrap()
                .unwrap()
                .fingerprint()
        };
        assert_eq!(
            route("http://user:hunter2@proxy.example:3128"),
            route("http://user:another@proxy.example:3128"),
            "a password that changes on its own routes the download the same way"
        );
        for other in [
            "http://user:hunter2@proxy.example:8080",
            "http://user:hunter2@other.example:3128",
            "http://bob:hunter2@proxy.example:3128",
        ] {
            assert_ne!(
                route("http://user:hunter2@proxy.example:3128"),
                route(other),
                "{other}"
            );
        }
        let bypassing = settings(&[
            (PROXY_URL, "http://user:hunter2@proxy.example:3128"),
            (PROXY_BYPASS, "corp.example"),
        ])
        .unwrap()
        .unwrap();
        assert_ne!(
            route("http://user:hunter2@proxy.example:3128"),
            bypassing.fingerprint()
        );
    }

    #[test]
    fn bypass_entries_match_a_host_or_its_subdomains() {
        let proxy = settings(&[
            (PROXY_URL, "http://proxy.example"),
            (
                PROXY_BYPASS,
                " *.corp.example, .Internal.example ,localhost,",
            ),
        ])
        .unwrap()
        .unwrap();
        assert!(proxy.bypasses("corp.example"));
        assert!(proxy.bypasses("a.b.corp.example"));
        assert!(proxy.bypasses("svc.internal.example."));
        assert!(proxy.bypasses("localhost"));
        assert!(!proxy.bypasses("notcorp.example"));
        assert!(!proxy.bypasses("cdn.playwright.dev"));
    }

    #[test]
    fn a_started_program_downloads_through_the_same_proxy_and_never_proxies_loopback() {
        let proxy = settings(&[
            (PROXY_URL, "http://al%40ice:p%3Ass@proxy.corp.example:3128"),
            (PROXY_BYPASS, "corp.example,localhost"),
        ])
        .unwrap()
        .unwrap();
        let environment: Vec<(&str, String)> = proxy
            .child_environment()
            .into_iter()
            .map(|(name, value)| (name, value.as_str().to_owned()))
            .collect();
        let address = "http://al%40ice:p%3Ass@proxy.corp.example:3128".to_owned();
        assert_eq!(
            environment,
            [
                ("HTTPS_PROXY", address.clone()),
                ("HTTP_PROXY", address),
                (
                    "NO_PROXY",
                    "corp.example,localhost,127.0.0.1,::1".to_owned()
                ),
            ]
        );
        let anonymous = settings(&[(PROXY_URL, "http://10.0.0.1")])
            .unwrap()
            .unwrap();
        assert_eq!(
            anonymous.child_environment()[0].1.as_str(),
            "http://10.0.0.1:80"
        );
    }

    #[test]
    fn base64_matches_the_standard_alphabet_and_padding() {
        for (input, expected) in [
            (&b""[..], ""),
            (b"f", "Zg=="),
            (b"fo", "Zm8="),
            (b"foo", "Zm9v"),
            (b"foob", "Zm9vYg=="),
            (b"Aladdin:open sesame", "QWxhZGRpbjpvcGVuIHNlc2FtZQ=="),
        ] {
            assert_eq!(base64(input).as_str(), expected);
        }
    }
}
