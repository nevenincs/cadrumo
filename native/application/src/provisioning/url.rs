use crate::{error::Error, value::HostName};
use std::fmt;

/// An absolute `https` address reduced to what a download hop is judged by.
///
/// Userinfo is refused at parse time, so an address never carries credentials, and the
/// host is a lowercase DNS name: an IP literal or an internationalised spelling is not an
/// address a pin or an approved plan can name. The fragment is dropped; it never reaches a
/// server.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HttpsUrl {
    host: HostName,
    port: Option<u16>,
    target: String,
}

impl HttpsUrl {
    pub fn parse(value: &str) -> Result<Self, Error> {
        let invalid = || Error::Invalid("expected an https address".into());
        if value.len() > 4096 || value.bytes().any(|c| c <= b' ' || c >= 0x7f) {
            return Err(invalid());
        }
        let (scheme, rest) = value.split_once("://").ok_or_else(invalid)?;
        if !scheme.eq_ignore_ascii_case("https") {
            return Err(Error::Invalid("download requires HTTPS".into()));
        }
        let rest = rest.split('#').next().unwrap_or_default();
        let split = rest.find(['/', '?']).unwrap_or(rest.len());
        let (authority, target) = rest.split_at(split);
        if authority.contains('@') {
            return Err(Error::Invalid(
                "an address must not carry credentials".into(),
            ));
        }
        let (host, port) = match authority.rsplit_once(':') {
            Some((host, port)) => {
                let port = port.parse::<u16>().map_err(|_| invalid())?;
                if port == 0 {
                    return Err(invalid());
                }
                (host, Some(port))
            }
            None => (authority, None),
        };
        let target = match target {
            "" => "/".to_owned(),
            t if t.starts_with('?') => format!("/{t}"),
            t => t.to_owned(),
        };
        Ok(Self {
            host: HostName::new(host)?,
            port,
            target,
        })
    }

    /// Resolves a `Location` value against this address: absolute, scheme-relative or
    /// path-absolute. A relative path without a leading slash is not followed.
    pub fn redirect(&self, location: &str) -> Result<Self, Error> {
        if location.contains("://") {
            Self::parse(location)
        } else if let Some(rest) = location.strip_prefix("//") {
            Self::parse(&format!("https://{rest}"))
        } else if location.starts_with('/') {
            Self::parse(&format!("https://{}{location}", self.authority()))
        } else {
            Err(Error::Invalid("unsupported redirect target".into()))
        }
    }

    pub fn host(&self) -> &HostName {
        &self.host
    }

    pub fn port(&self) -> u16 {
        self.port.unwrap_or(443)
    }

    /// Whether the address names the default HTTPS port, explicitly or not.
    pub fn default_port(&self) -> bool {
        self.port() == 443
    }

    /// The request target: the path and query sent on the request line.
    pub fn target(&self) -> &str {
        &self.target
    }

    /// The `Host` header value.
    pub fn authority(&self) -> String {
        match self.port {
            Some(port) if port != 443 => format!("{}:{port}", self.host),
            _ => self.host.to_string(),
        }
    }
}

impl fmt::Display for HttpsUrl {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "https://{}{}", self.authority(), self.target)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_https_address_keeps_its_host_port_and_target() {
        let url = HttpsUrl::parse("HTTPS://cdn.example.com/a/b.zip?x=1#frag").unwrap();
        assert_eq!(url.host().as_str(), "cdn.example.com");
        assert!(url.default_port());
        assert_eq!(url.target(), "/a/b.zip?x=1");
        assert_eq!(url.to_string(), "https://cdn.example.com/a/b.zip?x=1");
        let other = HttpsUrl::parse("https://cdn.example.com:8443").unwrap();
        assert!(!other.default_port());
        assert_eq!(other.target(), "/");
        assert_eq!(other.authority(), "cdn.example.com:8443");
        assert!(
            HttpsUrl::parse("https://cdn.example.com:443/x")
                .unwrap()
                .default_port()
        );
    }

    #[test]
    fn addresses_a_hop_rule_could_not_judge_are_refused() {
        for value in [
            "http://cdn.example.com/a",
            "https://user:pass@cdn.example.com/a",
            "https://127.0.0.1/a",
            "https://CDN.example.com/a",
            "https://cdn.example.com:0/a",
            "https://cdn.example.com:99999/a",
            "https://cdn.example.com/a b",
            "https://localhost/a",
            "ftp://cdn.example.com/a",
            "cdn.example.com/a",
        ] {
            assert!(HttpsUrl::parse(value).is_err(), "{value}");
        }
    }

    #[test]
    fn redirects_resolve_absolute_scheme_relative_and_path_targets() {
        let base = HttpsUrl::parse("https://a.example.com/one/two").unwrap();
        assert_eq!(
            base.redirect("https://b.example.com/x")
                .unwrap()
                .to_string(),
            "https://b.example.com/x"
        );
        assert_eq!(
            base.redirect("//c.example.com/y").unwrap().to_string(),
            "https://c.example.com/y"
        );
        assert_eq!(
            base.redirect("/z?q").unwrap().to_string(),
            "https://a.example.com/z?q"
        );
        assert!(base.redirect("relative/path").is_err());
        assert!(base.redirect("http://b.example.com/x").is_err());
    }
}
