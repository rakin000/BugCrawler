import requests
from requests.auth import HTTPBasicAuth
from dateutil.parser import parse as parse_date
import openpyxl
from openpyxl import Workbook
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

JIRA_SEARCH_API = "https://jira.mariadb.org/rest/api/2/search"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
excel_file = "mariadb_data_test.xlsx"

MAX_RESULTS = 50
end_date_str = "2024-12-31T23:59:59.000+0000"
end_dt = parse_date(end_date_str)


def fetch_mariadb_issues():
    issues_all = []
    start_at = 0

    while True and start_at == 0:
        params = {
            "jql": "project=MDEV ORDER BY created DESC",  # revise project
            "startAt": start_at,
            "maxResults": MAX_RESULTS
        }

        response = requests.get(JIRA_SEARCH_API, params=params)
        response.raise_for_status()
        data = response.json()

        issues = data.get("issues", [])
        if not issues:
            break

        issues_all.extend(issues)

        # if creat time early than six years ago, then stop
        last_issue = issues_all[-1]
        fields = last_issue.get("fields", {})

        created_str = fields.get("created")
        created_dt = parse_date(created_str) if created_str else None

        if (created_dt < end_dt):
            print("Stop crawling")
            break

        start_at += MAX_RESULTS
        print(start_at)

    return issues_all


def main():
    print("Start...")
    all_issues = fetch_mariadb_issues()
    print("Finish fetching...")

    bug_issues = []
    for issue in all_issues:
        fields = issue.get("fields", {})
        issuetype = fields.get("issuetype", {}).get("name", "")
        if issuetype.lower() == "bug":
            bug_issues.append(issue)

    if not os.path.exists(excel_file):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
    else:
        workbook = openpyxl.load_workbook(excel_file)
        sheet = workbook.active

    for bug in bug_issues:
        issue_key = bug["key"]
        summary = bug["fields"].get("summary", "")
        # print(f"- {issue_key}: {summary}")

        fields = bug.get("fields", {})

        # record jira's create time, fix time and result of fix
        created_str = fields.get("created")
        created_dt = parse_date(created_str) if created_str else None

        resolution_date_str = fields.get("resolutiondate")
        resolution_dt = parse_date(resolution_date_str) if resolution_date_str else None

        resolution_info = fields.get("resolution")
        resolution_name = resolution_info["name"] if resolution_info else "Not fixed"

        sheet.append([created_str, resolution_date_str, resolution_name])

    workbook.save(excel_file)


if __name__ == "__main__":
    main()