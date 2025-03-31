# Bug Crawler

**Bug Crawler** is an automated tool designed to efficiently collect and organize bug cases from the Apache community.

## Quick Start

### Run the Tool

Execute the following command to start the crawler:

```bash
python bug_crawler/run.py
```

Upon successful execution, the results will be generated in the directory:

```
./bug_crawler/result/xxx.xlsx
```

## Configuration

To configure the crawler for specific bug types or sources, you can customize the configuration files located in:

```
./bug_crawler/config/<bug_type>/config.json
```

For example, to set up for memory-related bugs, edit:

```
./bug_crawler/config/memory_bug/config.json
```

You can adjust parameters such as:

- **Issue Source** (e.g., Apache JIRA)
- **Bug Type** (e.g., memory, network)
- **Maximum Total Issues**
- **Attachment File Type** (e.g., `.log`)

After customization, ensure your configuration file is properly referenced in `run.py`.

## Key Features

- **Automated Issue Retrieval**: Fetch specific categories of bugs (e.g., memory, network).

- **Attachment Management**: Automatically download specified attachment types (such as `.log` files) and store them systematically in:

  ```
  ./bug_crawler/bug_cases/logs
  ```

- **Resume Capability**: Supports breakpoint resume functionality if the crawling process is interrupted.

- **LLM Integration (GPT-4)**: Automatically generates answers from the GPT-4 model based on predefined prompt questions and attachment logs, and saves the results in an organized Excel file.

> **Important Note:**
>
> OpenAI's GPT-4 model currently supports a maximum context length of **8192 tokens**. If the content exceeds this limit, please shorten your messages or attachment data accordingly.

Prompt templates are customizable and located at:

```
./bug_crawler/prompt_template/xxx.txt
```

## Directory Structure Overview

```
bug_crawler/
├── config/
│   └── memory_bug/
│       └── config.json
├── prompt_template/
│   └── xxx.txt
├── run.py
bug_cases/
└── logs/
result/
└── xxx.xlsx
```

## Requirements

Make sure Python is installed along with the following libraries:

```bash
pip install requests tqdm openpyxl pathlib
```

