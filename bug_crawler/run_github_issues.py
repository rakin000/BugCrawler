from github_fetcher import fetch_github_issues
from service.gpt_service.openai_client import call_openai
import json 

# Configuration
config_all = json.load(open("bug_crawler/config/config.json"))
config = config_all['github']
config_csv=config_all['csv']
 

try:
    issues = fetch_github_issues(
        owner=config['owner'],
        repo=config['repo'],
        state=config['state'],      # Search for closed issues
        per_page=config['per_page'],
        max_pages=config['max_pages'],
        start_date=config['start_date'],
        end_date=config['end_date'],
        keywords=config['keywords'],
        token=config['token'],
        include_comments=False
    )

    print(f"\nFound {len(issues)} issues in the date range.")
    for issue in issues:
        print(f"  #{issue['number']}: {issue['title']} (Created: {issue['created_at']})")

except Exception as e:
    print(f"An error occurred: {e}")


with open("bug_crawler/prompt_template/filter_application_resource.txt", "r") as f:
    FILTER_PROMPT = f.read()

for issue in issues:
    issue_text = f"Title: {issue['title']}\n\nDescription: {issue['body']}\n\nComments: {issue.get('comments_thread_text', '')}"
    response = call_openai(FILTER_PROMPT.format(app_name=config['repo'], issue_text=issue_text))
    issue['application_resoure'] = response


import pandas as pd
df = pd.json_normalize(issues)
df.to_csv(config_csv['file_name'].format(repo=config['repo'], bug_type=config['bug_type']))



