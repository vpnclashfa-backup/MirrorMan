# -*- coding: utf-8 -*-
import os
import base64
import requests
from datetime import datetime
import pytz
from pathlib import Path
import re

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

def is_base64(s: str) -> bool:
    """
    Checks if a string is a valid Base64 encoded string.
    It must contain only valid Base64 characters and have correct padding.
    A simple text like "hello world" will fail this check.
    A long subscription link will pass.
    """
    # A regex to check for valid Base64 characters.
    # It allows for multiline Base64 by ignoring whitespace.
    if not re.match(r'^[A-Za-z0-9+/=\s]+$', s.strip()):
        return False
        
    # Remove any whitespace (like newlines) before decoding
    s_cleaned = "".join(s.split())
    
    try:
        # Add padding if it's missing for a correct check
        s_padded = s_cleaned + '=' * (-len(s_cleaned) % 4)
        decoded_bytes = base64.b64decode(s_padded, validate=True)
        # Re-encode and check if it matches the original. This is a strong validation.
        return base64.b64encode(decoded_bytes).decode('utf-8') == s_padded
    except (ValueError, TypeError):
        return False

def get_processed_content_from_url(url: str) -> str:
    """
    Fetches content from a URL, auto-detects if it's Base64 encoded,
    decodes it if necessary, and returns the final plain text.
    Returns None on failure.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.text
        
        # Check if the fetched content is likely Base64
        if is_base64(content):
            print(f"Detected Base64 content from {url}")
            # Clean whitespace before decoding
            cleaned_content = "".join(content.split())
            decoded_bytes = base64.b64decode(cleaned_content)
            return decoded_bytes.decode('utf-8')
        else:
            # If not Base64, return as plain text
            return content
            
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        print(f"Error processing content from {url}: {e}")
        return None

# --- Main Logic ---

def main():
    """
    Main function to process links, generate files, and update the README.
    It auto-detects and decodes Base64 content from URLs.
    Format for links.txt: url1|url2...,output_name
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
            
            individual_urls = [s.strip() for s in sources_part.split('|')]
            
            all_contents = []
            for url in individual_urls:
                content = get_processed_content_from_url(url)
                if content is not None:
                    all_contents.append(content)
            
            if not all_contents:
                print(f"Warning: Could not fetch any valid content for '{output_name}'. Skipping.")
                continue

            combined_content = "\n".join(all_contents)

            # 1. Save normal text file
            normal_path = Path(NORMAL_DIR) / f"{output_name}.txt"
            normal_path.write_text(combined_content, encoding='utf-8')

            # 2. Save Base64 encoded file (re-encoding the final combined content)
            base64_final_content = base64.b64encode(combined_content.encode('utf-8')).decode('utf-8')
            base64_path = Path(BASE64_DIR) / f"{output_name}.b64"
            base64_path.write_text(base64_final_content, encoding='utf-8')
            
            print(f"Processed '{output_name}' (from {len(all_contents)} sources): created {normal_path} and {base64_path}")
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
