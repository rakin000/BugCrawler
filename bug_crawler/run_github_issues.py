import os
import json
import requests
from tqdm import tqdm
from openpyxl import Workbook, load_workbook
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from service.gpt_service.util import get_gpt_answer

def load_config(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

config_file = "config/memory_bug/config.json"
config = load_config(config_file)

# jira config
JIRA_SEARCH_API = config["jira"]["search_api"]
JIRA_ISSUE_DETAIL_API = config["jira"]["issue_detail_api"]
JIRA_BROWSE_URL = config["jira"]["browse_url"]
BUG_TYPE = config["jira"]["bug_type"]
MAX_TOTAL_ISSUES = config["jira"]["max_total_issues"]
PAGE_SIZE = config["jira"]["page_size"]
MIN_LOG_LINE = config["jira"]["min_log_line"]
SAVE_EVERY = config["jira"]["save_every"]
ATTACHMENT_FILE_TYPES = config["jira"]["attachment_file_types"]
GPT_MAX_ATTACHMENT_LINE = config["jira"]["gpt_max_attachment_line"]
LOG_SAVE_PATH = config["jira"]["log_save_path"]

# excel config
EXCEL_FILE = config["excel"]["file_name"].format(bug_type=BUG_TYPE)

# predefined rules & prompt question
PREDEFINED_RULE_FILE = './prompt_template/predefined_rules.txt'
with open(PREDEFINED_RULE_FILE, 'r') as file:
    PREDEFINED_RULE_FOR_GPT = file.read()
PROMPT_QUESTION_FILE = [
    './prompt_template/question_reason_process_relationship.txt',
    './prompt_template/question_calculate_process_memory_usage.txt'
    # './prompt_template/question_deduce_bug_root_cause.txt'
]
QUESTIONS_FOR_GPT = [
    open(prompt_template_file, 'r').read()
    for prompt_template_file in PROMPT_QUESTION_FILE
]

def fetch_memory_bugs():
    jql_query = config["jira"]["jql"].format(search_term=BUG_TYPE)

    start_at = 0
    all_bugs = []

    while start_at < MAX_TOTAL_ISSUES:
        params = {
            "jql": jql_query,
            "startAt": start_at,
            "maxResults": PAGE_SIZE
        }

        response = requests.get(JIRA_SEARCH_API, params=params)
        response.raise_for_status()
        data = response.json()

        issues = data.get("issues", [])
        if not issues:
            break

        all_bugs.extend(issues)
        print(f"Fetched {len(issues)} issues (startAt={start_at})")

        start_at += PAGE_SIZE
        if start_at >= data.get("total", 0):
            break

    return all_bugs


def fetch_attachments_with_linecount(issue_key):
    """返回 issue_key, [(attachment_link, line_count)]"""
    url = f"{JIRA_ISSUE_DETAIL_API}{issue_key}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        attachments = data.get("fields", {}).get("attachment", [])
        result = []

        for att in attachments:
            att_url = att["content"]
            att_file_name = att['filename']
            try:
                content_resp = requests.get(att_url, timeout=10)
                content_resp.raise_for_status()
                text = content_resp.text
                line_count = len(text.strip().splitlines())
            except Exception as e:
                print(f"⚠️ 附件无法获取：{att_url}，Error：{e}")
                line_count = "N/A"

            result.append((att_url, att_file_name, line_count))

        return issue_key, result

    except Exception as e:
        print(f"❌ 获取 issue {issue_key} 附件失败: {e}")
        return issue_key, []


def load_written_issue_keys():
    if not os.path.exists(EXCEL_FILE):
        return set()

    wb = load_workbook(EXCEL_FILE)
    sheet = wb.active
    keys = set()
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0]:
            keys.add(row[0])
    return keys


def save_to_excel_incremental(bugs, attachment_map, save_every=SAVE_EVERY):
    if os.path.exists(EXCEL_FILE):
        workbook = load_workbook(EXCEL_FILE)
        sheet = workbook.active
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Memory Bugs"
        sheet.append(["Issue Key", "Summary", "Issue Link", "Attachment Link", "Attachment type & lines", "GPT response"])

    written_keys = load_written_issue_keys()
    count_since_last_save = 0

    print("\n📄 增量写入 Excel 文件（每写入 {} 条自动保存）...\n".format(save_every))

    for bug in tqdm(bugs, desc="写入进度", ncols=100):
        key = bug.get("key")
        # skip lines that are already written
        if key in written_keys:
            print(f"Case {key} already exists in Excel. Skipping write operation to Excel.")
            continue

        summary = bug.get("fields", {}).get("summary", "")
        issue_link = f"{JIRA_BROWSE_URL}{key}"
        attachments = attachment_map.get(key, [])

        if attachments:
            excel_line = [key, summary, issue_link]
            for index, (attachment_link, attachment_file_name, line_count) in enumerate(attachments):
                # filter logs < 100 lines
                if isinstance(line_count, int) and line_count < MIN_LOG_LINE:
                    continue
                file_type = Path(attachment_link).suffix[1:] or "unknown"
                excel_line.append(attachment_link)
                excel_line.append(f"{file_type}, {line_count}")
                # insert GPT response into the excel result.
                if file_type in ATTACHMENT_FILE_TYPES:
                    # download log file into local folder '/bug_cases/logs'.
                    response = requests.get(attachment_link)
                    full_save_path = LOG_SAVE_PATH + key + f"/{attachment_file_name}"
                    if response.status_code == 200:
                        # Ensure the directory exists
                        os.makedirs(os.path.dirname(full_save_path), exist_ok=True)
                        with open(full_save_path, 'wb') as f:
                            f.write(response.content)
                        print(f"{key} - {attachment_file_name} is downloaded successfully.")
                    # OpenAI restrict GPT-4 model's maximum context length is 8192 tokens.
                    if line_count > GPT_MAX_ATTACHMENT_LINE:
                        continue
                    for q_index, question in enumerate(QUESTIONS_FOR_GPT):
                        if q_index == 0:
                            question = PREDEFINED_RULE_FOR_GPT + question
                        try:
                            response = get_gpt_answer(question, full_save_path)
                        except Exception as e:
                            response = f"Can't get response from GPT: {e}"
                        excel_line.append(response)
            sheet.append(excel_line)
        else:
            sheet.append([key, summary, issue_link, "None", "0"])

        written_keys.add(key)
        count_since_last_save += 1

        if count_since_last_save >= save_every:
            workbook.save(EXCEL_FILE)
            print(f"💾 中间保存 Excel（已写入 {len(written_keys)} 个 issue）")
            count_since_last_save = 0

    workbook.save(EXCEL_FILE)
    print(f"\n✅ 最终写入完成：{EXCEL_FILE}（共写入 {len(written_keys)} 个 issue）")


def main():
    bugs = fetch_memory_bugs()
    print(f"\n📦 共获取到 {len(bugs)} 个 memory 相关的 Bug。\n")

    attachment_map = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_key = {executor.submit(fetch_attachments_with_linecount, bug["key"]): bug["key"] for bug in bugs}
        for future in as_completed(future_to_key):
            try:
                issue_key, attachments = future.result()
                attachment_map[issue_key] = attachments
            except Exception as e:
                print(f"⚠️ 获取附件失败：{e}")
    save_to_excel_incremental(bugs, attachment_map)


if __name__ == "__main__":
    main()
