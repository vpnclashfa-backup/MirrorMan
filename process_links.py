# -*- coding: utf-8 -*-
import os
import base64
import re
import requests
from datetime import datetime
import pytz
from pathlib import Path

# --- Configuration ---
LINKS_FILE = "links.txt"
NORMAL_DIR = "normal"
BASE64_DIR = "base64"
README_FILE = "README.md"
# GITHUB_REPOSITORY is expected to be set by the GitHub Actions environment
# Example: 'owner/repo'
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
if not GITHUB_REPO:
    raise ValueError("GITHUB_REPOSITORY environment variable not set. This script should be run in a GitHub Action.")

# --- Helper Functions ---

def is_url(s: str) -> bool:
    """Checks if a given string is a valid URL."""
    return re.match(r'^https?://', s) is not None

def is_base64(s: str) -> bool:
    """Checks if a given string is a valid Base64 encoded string."""
    try:
        s_padded = s + '=' * (-len(s) % 4)
        return base64.b64encode(base64.b64decode(s_padded)).decode('utf-8') == s_padded
    except (ValueError, TypeError):
        return False

def get_content_from_source(source: str) -> (str, str):
    """
    Fetches content from a URL or decodes a Base64 string.
    Returns the content and the type of source ('url' or 'base64').
    If an error occurs, it prints a message and returns None, ensuring the script doesn't stop.
    """
    source = source.strip()
    if is_url(source):
        try:
            response = requests.get(source, timeout=10)
            response.raise_for_status()
            return response.text, 'url'
        except requests.RequestException as e:
            # ROBUSTNESS: Catch network/HTTP errors and print a message instead of crashing.
            print(f"Error fetching URL {source}: {e}")
            return None, 'error'
    elif is_base64(source):
        try:
            decoded_bytes = base64.b64decode(source)
            return decoded_bytes.decode('utf-8'), 'base64_string'
        except Exception as e:
            # ROBUSTNESS: Catch Base64 decoding errors.
            print(f"Error decoding Base64 string: {e}")
            return None, 'error'
    else:
        print(f"Warning: Source '{source[:30]}...' is not a valid URL or Base64 string. Treating as plain text.")
        return source, 'plaintext'

# --- Main Logic ---

def main():
    """
    Main function to process links, generate files, and update the README.
    It supports combining multiple sources for a single output.
    Format for links.txt: source1|source2|...,output_name
    """
    Path(NORMAL_DIR).mkdir(exist_ok=True)
    Path(BASE64_DIR).mkdir(exist_ok=True)

    if not Path(LINKS_FILE).exists():
        print(f"Error: Input file '{LINKS_FILE}' not found.")
        return

    processed_files = []

    with open(LINKS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(',', 1)
            if len(parts) != 2:
                print(f"Warning: Skipping malformed line: {line}")
                continue
            
            sources_part, output_name = parts[0].strip(), parts[1].strip()
            individual_sources = [s.strip() for s in sources_part.split('|')]
            
            all_contents = []
            for source in individual_sources:
                content, _ = get_content_from_source(source)
                # ROBUSTNESS: Only add content if it was successfully fetched/decoded.
                # If get_content_from_source returned None due to an error, it is simply skipped.
                if content is not None:
                    all_contents.append(content)
            
            # If after trying all sources, none of them yielded content, skip to the next line in links.txt.
            if not all_contents:
                print(f"Warning: Could not fetch any content for '{output_name}'. Skipping.")
                continue

            combined_content = "\n".join(all_contents)

            # 1. Save normal text file
            normal_path = Path(NORMAL_DIR) / f"{output_name}.txt"
            normal_path.write_text(combined_content, encoding='utf-8')

            # 2. Save Base64 encoded file
            base64_content = base64.b64encode(combined_content.encode('utf-8')).decode('utf-8')
            base64_path = Path(BASE64_DIR) / f"{output_name}.b64"
            base64_path.write_text(base64_content, encoding='utf-8')
            
            print(f"Processed '{output_name}' (from {len(individual_sources)} sources): created {normal_path} and {base64_path}")
            processed_files.append({
                "name": output_name,
                "normal_path": normal_path.as_posix(),
                "base64_path": base64_path.as_posix()
            })

    # 3. Update README.md
    update_readme(processed_files)
    print("README.md has been updated.")


def update_readme(processed_files):
    """
    Generates and writes the new content for README.md.
    """
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    timestamp = now_tehran.strftime('%Y-%m-%d %H:%M:%S %Z')

    content = f"# Processed Links Collection\n\n"
    content += f"Last updated: `{timestamp}`\n\n"
    content += "This repository contains automatically processed lists from various sources.\n\n"

    content += "| File Name | Normal Format (Raw) | Base64 Format (Raw) |\n"
    content += "|-----------|-----------------------|-----------------------|\n"

    raw_base_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

    if not processed_files:
        content += "| *No files processed* | | |\n"
    else:
        for file_info in sorted(processed_files, key=lambda x: x['name']):
            name = file_info['name']
            normal_link = f"{raw_base_url}/{file_info['normal_path']}"
            base64_link = f"{raw_base_url}/{file_info['base64_path']}"
            content += f"| `{name}` | [Link]({normal_link}) | [Link]({base64_link}) |\n"

    Path(README_FILE).write_text(content, encoding='utf-8')


if __name__ == "__main__":
    main()
