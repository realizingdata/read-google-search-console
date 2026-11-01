---
name: google-search-console
description: >-
  Reads Google Search Console through the Search Analytics API using the local
  gcloud Application Default Credentials. Use when the user asks for Search
  Console, GSC, impressions, clicks, CTR, average position, query or page
  performance, cannibalization, or which URL ranks for a query. Works in any
  repository. Discover the property from that repo. Do not hardcode a site.
---

# Google Search Console

Copy this whole `google-search-console` folder into another repo at `.agents/skills/google-search-console/` or `.cursor/skills/google-search-console/`. The script and these instructions stay together. Nothing in this folder is site-specific.

Use the script from this skill folder. Do not rebuild the request with curl, and do not print the access token.

```bash
python3 scripts/gsc.py sites
python3 scripts/gsc.py query --site "sc-domain:example.com" --dimensions query
```

Run it in a shell that can read the home directory and reach `googleapis.com`. A sandboxed shell fails even when the login is valid.

## Connect

The login is a user credential on the machine, shared by every repo. The Google account must already be a user on the Search Console property. The Cloud project only pays the API quota. It does not own the website.

1. Find `gcloud` on `PATH`, or at `$HOME/google-cloud-sdk/bin/gcloud`. If it is missing, stop and ask the user to install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install). Do not install it for them.
2. Run `python3 scripts/gsc.py sites` from this skill folder.
3. If that fails because there is no login, ask the user to run this in their own terminal. It opens a browser. Do not run it unattended.

```bash
gcloud auth login
gcloud projects list
gcloud config set project PROJECT_ID
gcloud services enable searchconsole.googleapis.com
gcloud auth application-default set-quota-project PROJECT_ID
gcloud auth application-default login \
  --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/webmasters.readonly"
```

Use a user login. Refuse a service-account JSON key. Never commit credentials, and never write the token into the repo.

Reads use `webmasters.readonly`. Submitting a sitemap or any other write needs the `webmasters` scope and an explicit request from the user. Do not do that as part of a read.

## Pick the property

Run `sites` first. Then find the site host in the current repo, in this order, and stop at the first confident host:

- `metadataBase` or an absolute canonical
- `SITE_URL` or `NEXT_PUBLIC_SITE_URL` in an example env file, not a secrets file
- the sitemap base URL
- `homepage` in `package.json`

Match the host to a property the login can see:

- Prefer `sc-domain:HOST`, without a leading `www`.
- Otherwise use the URL-prefix property for that exact host, such as `https://example.com/`.
- If several properties match and none is the domain property, ask which one.
- If none match, stop. Report the properties that were returned and do not query a different site.

A domain property and a URL-prefix property are different ids. Pass the `siteUrl` value exactly as `sites` printed it.

## Query

The default window ends 3 days ago and covers 90 days, because the newest days are incomplete. Pass `--start` and `--end` as `YYYY-MM-DD` when the user wants a different window. `--search-type` defaults to `web`.

```bash
python3 scripts/gsc.py query \
  --site "sc-domain:example.com" \
  --dimensions query,page \
  --filter "page equals https://example.com/pricing" \
  --limit 100
```

`--filter` repeats. Each value is `dimension operator expression`. Dimensions: `query`, `page`, `country`, `device`, `date`, `searchAppearance`. Operators: `equals`, `contains`, `notContains`, `includingRegex`, `excludingRegex`. Filters in one command are combined with AND.

`--all` pages through the full result. Use it only for an export. A normal read stays at the default limit.

`sitemaps --site "..."` lists submitted sitemaps. It does not submit one.

## How to report

State the property, search type, date range, and the date retrieved. Query rows and page rows are different totals: some impressions have no query string. Say which one a number comes from.

Use a fresh query. A report already saved in the repo is historical, not current performance.

Do not invent search volume, clicks, or positions for rows the API did not return.
