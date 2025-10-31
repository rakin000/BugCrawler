def dict_to_markdown_list(obj, indent=0):
    """
    Recursively converts a dictionary or list into a markdown nested list string.
    """
    markdown = ""
    prefix = "  " * indent + "- "  # Markdown list prefix with indentation

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                markdown += f"{prefix}{key}:\n"
                markdown += dict_to_markdown_list(value, indent + 1)
            else:
                markdown += f"{prefix}{key}: {value}\n"
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if isinstance(value, (dict, list)):
                markdown += f"{prefix}Item {i+1}:\n"
                markdown += dict_to_markdown_list(value, indent + 1)
            else:
                markdown += f"{prefix}{value}\n"
    return markdown


def json_list_to_markdown(json_list, output_file="report.md"):
    """
    Takes a list of JSON-like objects (dicts) and writes them as markdown nested lists.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# JSON Report\n\n")
        for i, obj in enumerate(json_list, start=1):
            f.write(f"## Item {i}\n\n")
            f.write(dict_to_markdown_list(obj))
            f.write("\n")
    print(f"✅ Markdown report generated: {output_file}")
