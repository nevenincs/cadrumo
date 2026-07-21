---
tags:
  - '#research'
  - '#docs-static-deployment'
date: '2026-07-10'
modified: '2026-07-10'
related: []
---
# `docs-static-deployment` research: `Cadrumo docs delivery`

Deploy the generated user docs to the two requested URLs.

## Findings

- Build with `AEAT_DOCS_BASE_URL=https://cadrumo.neve.md/docs`.
- Use `https://cadrumo.neve.md/docs/` as the canonical URL.
- Redirect `https://neve.md/cadrumo/docs/...` to the canonical URL.
- Keep the S3 bucket private.
- Serve only through CloudFront with OAC.
- Use a CloudFront Function for `/docs/` paths and directory indexes.
- Keep missing pages as `404` responses.
- Point `cadrumo.neve.md` at CloudFront with DNS-only Cloudflare DNS.
- Add the apex redirect in Cloudflare without changing other `neve.md` paths.
- Build and upload through a human-gated local AWS session.
- Run the full strict build before every deploy.
- Do not deploy changed-page or single-page previews.
- Require Pagefind output before upload.
- Exclude `.doctrees` from the upload.
- Current state has no AWS credentials, Cadrumo DNS, IaC, or deploy workflow.

## Sources

- `dev/docs/build.py`
- `docs/conf.py`
- `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html`
- `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html`
- `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example_cloudfront_functions_url_rewrite_single_page_apps_section.html`
- `https://developers.cloudflare.com/rules/url-forwarding/single-redirects/settings/`
