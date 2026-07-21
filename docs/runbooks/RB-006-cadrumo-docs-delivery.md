# RB-006 Publish Cadrumo documentation

Publish the [Cadrumo documentation](https://cadrumo.neve.md/docs/).

## Check prerequisites

1. Require `aws`, `just`, and `uv`.
2. Run `aws sts get-caller-identity`.
3. Require one `ISSUED` AWS Certificate Manager (ACM) certificate for `cadrumo.neve.md` in `us-east-1`.
4. Stop and escalate if any check fails.

## Provision the stack

1. Run `just docs-stack-deploy`.
2. Record `DocsDistributionDomainName`.
3. Record `DocsDistributionId`, `DocsBucketName`, and `DocsCanonicalUrl`.
4. If the stack has no changes, accept a zero exit status.

## Configure DNS and redirects

1. Add Domain Name System (DNS)-only CNAME `cadrumo` to recorded `DocsDistributionDomainName`.
2. Keep apex record `@` proxied.
3. Add Cloudflare Wildcard URL Redirect `http*://neve.md/cadrumo/docs` to `https://cadrumo.neve.md/docs/`.
4. Add Cloudflare Wildcard URL Redirect `http*://neve.md/cadrumo/docs/*` to `https://cadrumo.neve.md/docs/${2}`.
5. Set both redirects to `308`.
6. Preserve query strings on both redirects.

## Publish documentation

1. Run `just docs-deploy`.
2. Require a zero exit status from the strict build.
3. Require canonical sitemap and Pagefind index generation.
4. Require Amazon S3 (S3) sync without doctrees.
5. Require `/docs/*` invalidation completion.
6. Confirm `Published https://cadrumo.neve.md/docs/`.
7. If any publish step fails, stop and escalate.
8. Treat a completed S3 sync as changed content until invalidation completes.

## Verify delivery

1. Require `200` from `https://cadrumo.neve.md/docs/`.
2. Require `308` from `https://neve.md/cadrumo/docs`.
3. Require `308` to `https://cadrumo.neve.md/docs/index.html?runbook=RB-006` from `https://neve.md/cadrumo/docs/index.html?runbook=RB-006`.
4. Require `404` from `https://cadrumo.neve.md/docs/__missing-rb-006__.html`.
5. Require `403` from `https://<DocsBucketName>.s3.us-east-1.amazonaws.com/docs/index.html`.

## Roll back

1. Keep both redirect rules enabled.
2. Run `just docs-deploy` from a known-good revision.
3. If rollback fails, stop and escalate.

## Escalate

1. Open an issue at <https://github.com/nevenincs/aeat/issues>.
2. Assign the Cadrumo repository owner.
3. Attach command output and a timestamp with time zone.
4. State whether S3 sync started.
5. State whether CloudFront invalidation started.

## Delivery reference

- Canonical: public Cadrumo documentation.
- Legacy: redirected old path.
- DNS-only: bypasses the Cloudflare proxy.
- Proxied: uses Cloudflare.
- CNAME: DNS alias.
- ACM: issues the CloudFront Transport Layer Security (TLS) certificate.
- CloudFront: private S3 delivery.
- Pagefind: static search.
- Sitemap: canonical URL list.
- Invalidation: CloudFront cache refresh.
- `infra/docs-static-site.yaml`: origin authority.
- `dev/deploy/docs_static_site.py`: publish authority.
- `justfile`: command authority.
- `docs/pagefind.yml`: search-scope authority.
- `docs/conf.py`: sitemap authority.
