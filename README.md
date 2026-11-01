# read-google-search-console

This skill lets an agent read Google Search Console for whatever site is in the current repository. It uses the Search Analytics API and the local `gcloud` Application Default Credentials. It returns clicks, impressions, CTR, and average position. It discovers the Search Console property from that repo. It does not hardcode a site.

The installer only needs `SKILL.md`. This README is for people.

## Install

```bash
npx skills add realizingdata/read-google-search-console -g -y
```

`-g` installs it for the user, so every repository on that machine can use it. Updates are `npx skills update`.

## One-time setup

The Google account must already be a user on the Search Console property. The Cloud project only pays API quota. It does not own the website.

Run this in your own terminal. It opens a browser. Do not leave the login for an agent to run unattended.

```bash
gcloud auth login
gcloud projects list
gcloud config set project PROJECT_ID
gcloud services enable searchconsole.googleapis.com
gcloud auth application-default set-quota-project PROJECT_ID
gcloud auth application-default login \
  --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/webmasters.readonly"
```

If `gcloud` is missing, install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install). Use a user login. Do not use a service-account JSON key.

## How an agent uses it

From the installed skill folder:

```bash
python3 scripts/gsc.py sites
python3 scripts/gsc.py query --site "sc-domain:example.com" --dimensions query
```

The default window ends 3 days ago and covers 90 days. Prefer a `sc-domain:` property. Pass the property id exactly as `sites` printed it. The shell must be able to read the home directory and reach `googleapis.com`.

## Limits

Reads use the `webmasters.readonly` scope. Listing sitemaps is allowed. Submitting a sitemap or any other write needs the `webmasters` scope and an explicit request. Query totals and page totals differ, because some impressions have no query string. Do not invent clicks, impressions, or positions.
