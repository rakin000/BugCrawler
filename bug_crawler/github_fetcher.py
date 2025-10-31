import requests

def fetch_issue_comments(issue, headers):
    """
    Fetches comments for a specific GitHub issue.

    Args:
        issue_number (int): The issue number.
        owner (str): The repository owner.
        repo (str): The repository name.
        headers (dict): Headers for the API request.
    Returns:
        list: A list of comment dictionaries.
    """
    comments_url = issue["comments_url"]
    comments_resp = requests.get(comments_url, headers=headers)
    if comments_resp.status_code == 200:
        comments_thread = [
            {
                "user": c["user"]["login"],
                "created_at": c["created_at"],
                "body": c["body"]
            }
            for c in comments_resp.json()
        ]
    else:
        comments_thread = []
    comments_thread_text = "\n".join([f"Comment by {c['user']} at {c['created_at']}:\n{c['body']}\n" for c in comments_thread])
    return comments_thread, comments_thread_text


def fetch_github_issues(owner, repo, state="open", per_page=30, max_pages=5, token=None,
                        start_date=None, end_date=None, keywords=None, include_comments=False):
    """
    Fetches GitHub issues for a repository using the Search API to filter by creation date, keywords,
    and optionally includes the full discussion thread (comments).

    Args:
        owner (str): The repository owner.
        repo (str): The repository name.
        state (str): 'open' or 'closed'. Note: Search API doesn't support 'all'.
        per_page (int): Number of items per page (max 100).
        max_pages (int): Maximum number of pages to fetch.
        token (str, optional): A GitHub Personal Access Token.
        start_date (str, optional): Start date in "YYYY-MM-DD" format.
        end_date (str, optional): End date in "YYYY-MM-DD" format.
        keywords (str | list, optional): Keyword(s) to search for in issues' title or body.
        include_comments (bool): If True, fetches each issue's comment thread.

    Returns:
        list: A list of issue dictionaries (each may include 'comments_thread' if requested).
    """

    search_url = "https://api.github.com/search/issues"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    query_parts = [
        f"repo:{owner}/{repo}",
        "is:issue",
        f"is:{state}"
    ]

    # Filter by date
    if start_date and end_date:
        query_parts.append(f"created:{start_date}..{end_date}")
    elif start_date:
        query_parts.append(f"created:>{start_date}")
    elif end_date:
        query_parts.append(f"created:<{end_date}")

    # Add keyword search
    if keywords:
        if isinstance(keywords, list):
            keyword_query = " ".join(keywords)
        else:
            keyword_query = keywords
        query_parts.append(keyword_query)

    query_string = " ".join(query_parts)

    issues = []
    for page in range(1, max_pages + 1):
        params = {
            "q": query_string,
            "sort": "created",
            "order": "desc",
            "per_page": per_page,
            "page": page
        }

        response = requests.get(search_url, headers=headers, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"GitHub API error: {response.status_code} {response.text}")

        data = response.json()
        items = data.get("items", [])
        if not items:
            break

        for issue in items:
            issue_data = {
                "number": issue["number"],
                "title": issue.get("title"),
                "body": issue.get("body"),
                "user": issue.get("user", {}).get("login"),
                "state": issue.get("state"),
                "labels": [label.get("name") for label in issue.get("labels", [])],
                "url": issue.get("html_url"),
                "created_at": issue.get("created_at"),
                "comments": issue.get("comments", 0),
                "repository_url": issue.get("repository_url"),
                "html_url": issue.get("html_url")
            }

            # Fetch comments if requested
            if include_comments and issue.get("comments", 0) > 0:
                comments_thread, comments_thread_text = fetch_issue_comments(issue, headers)
                issue_data["comments_thread"] = comments_thread
                issue_data["comments_thread_text"] = comments_thread_text
            
            issues.append(issue_data)

    return issues
