#!/usr/bin/env python3
"""Read Google Search Console with the local gcloud Application Default Credentials.

The access token stays in this process. Stdout is JSON. Errors go to stderr.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://www.googleapis.com/webmasters/v3/sites"
DIMENSIONS = {"query", "page", "country", "device", "date", "searchAppearance"}
OPERATORS = {"equals", "contains", "notContains", "includingRegex", "excludingRegex"}


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def gcloud_bin():
    found = shutil.which("gcloud")
    if found:
        return found
    bundled = Path.home() / "google-cloud-sdk" / "bin" / "gcloud"
    if bundled.is_file():
        return str(bundled)
    fail(
        "gcloud is not installed. Install the Google Cloud CLI, open a new shell, "
        "then run the login steps in the google-search-console skill."
    )


def adc_path():
    override = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if override:
        return Path(override)
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def access_token():
    try:
        completed = subprocess.run(
            [gcloud_bin(), "auth", "application-default", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        fail(
            "Application Default Credentials are missing or expired. "
            "The user has to sign in in a browser. Run:\n"
            "gcloud auth application-default login "
            '--scopes="openid,https://www.googleapis.com/auth/userinfo.email,'
            "https://www.googleapis.com/auth/cloud-platform,"
            'https://www.googleapis.com/auth/webmasters.readonly"\n'
            + detail
        )
    token = completed.stdout.strip()
    if not token or token.startswith("{"):
        fail("gcloud did not return an access token.")
    return token


def quota_project():
    override = os.environ.get("GSC_QUOTA_PROJECT")
    if override:
        return override
    path = adc_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            fail(f"Could not read {path}.")
        if data.get("type") == "service_account":
            fail(
                "The credential is a service-account key. Use a user login instead: "
                "gcloud auth application-default login with the webmasters.readonly scope."
            )
        project = data.get("quota_project_id")
        if project:
            return str(project)
    try:
        project = subprocess.run(
            [gcloud_bin(), "config", "get-value", "project"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        project = ""
    if not project or project == "(unset)":
        fail(
            "No quota project. The user should run: "
            "gcloud auth application-default set-quota-project PROJECT_ID"
        )
    try:
        number = subprocess.run(
            [gcloud_bin(), "projects", "describe", project, "--format=value(projectNumber)"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        number = ""
    return number or project


def request(method, url, token, project, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": project,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        fail(f"Search Console API returned HTTP {error.code}.\n{detail}")
    return json.loads(raw) if raw else {}


def encode_site(site):
    return urllib.parse.quote(site, safe="")


def default_range(args):
    end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(days=3)
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days - 1)
    if start > end:
        fail("The start date is after the end date.")
    return start.isoformat(), end.isoformat()


def parse_filters(pairs):
    filters = []
    for raw in pairs:
        parts = raw.split(" ", 2)
        if len(parts) != 3:
            fail(f"Filter must be 'dimension operator expression', got: {raw}")
        dimension, operator, expression = parts
        if dimension not in DIMENSIONS:
            fail(f"Unknown dimension: {dimension}")
        if operator not in OPERATORS:
            fail(f"Unknown operator: {operator}")
        filters.append({"dimension": dimension, "operator": operator, "expression": expression})
    return filters


def command_sites(token, project):
    payload = request("GET", API, token, project)
    sites = [
        {"siteUrl": entry.get("siteUrl"), "permissionLevel": entry.get("permissionLevel")}
        for entry in payload.get("siteEntry", [])
    ]
    json.dump({"sites": sites}, sys.stdout, indent=2)
    print()


def command_query(args, token, project):
    dimensions = [part.strip() for part in args.dimensions.split(",") if part.strip()]
    for dimension in dimensions:
        if dimension not in DIMENSIONS:
            fail(f"Unknown dimension: {dimension}")
    start, end = default_range(args)
    filters = parse_filters(args.filter)
    rows = []
    start_row = args.start_row
    while True:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions,
            "rowLimit": args.limit,
            "startRow": start_row,
            "type": args.search_type,
        }
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]
        page = request("POST", f"{API}/{encode_site(args.site)}/searchAnalytics/query", token, project, body)
        batch = page.get("rows", [])
        rows.extend(batch)
        if not args.all or len(batch) < args.limit:
            break
        start_row += args.limit
    json.dump(
        {
            "property": args.site,
            "searchType": args.search_type,
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions,
            "rows": rows,
        },
        sys.stdout,
        indent=2,
    )
    print()


def command_sitemaps(args, token, project):
    payload = request("GET", f"{API}/{encode_site(args.site)}/sitemaps", token, project)
    json.dump(payload, sys.stdout, indent=2)
    print()


def build_parser():
    parser = argparse.ArgumentParser(description="Read Google Search Console.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sites", help="List properties this login can see")
    query = sub.add_parser("query", help="Run a Search Analytics query")
    query.add_argument("--site", required=True, help="Property id, such as sc-domain:example.com")
    query.add_argument("--start", help="YYYY-MM-DD. Default is the end date minus --days.")
    query.add_argument("--end", help="YYYY-MM-DD. Default is today minus 3 days.")
    query.add_argument("--days", type=int, default=90)
    query.add_argument("--dimensions", default="query")
    query.add_argument("--filter", action="append", default=[], metavar="'DIM OP VALUE'")
    query.add_argument("--limit", type=int, default=100)
    query.add_argument("--start-row", type=int, default=0)
    query.add_argument("--search-type", default="web")
    query.add_argument("--all", action="store_true", help="Page until the result is exhausted")
    sitemaps = sub.add_parser("sitemaps", help="List sitemaps on a property")
    sitemaps.add_argument("--site", required=True)
    return parser


def main():
    args = build_parser().parse_args()
    if getattr(args, "limit", 1) < 1 or getattr(args, "limit", 1) > 25000:
        fail("--limit must be from 1 to 25000.")
    token = access_token()
    project = quota_project()
    if args.command == "sites":
        command_sites(token, project)
    elif args.command == "query":
        command_query(args, token, project)
    elif args.command == "sitemaps":
        command_sitemaps(args, token, project)


if __name__ == "__main__":
    main()
