# -*- coding: utf-8 -*-
import os
import base64
import requests # Still useful for a quick fallback or other tasks if needed, so we keep it.
from datetime import datetime
import pytz
from pathlib import Path
import re
import time
import random

# --- Selenium Imports for Advanced Browser Automation ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- Configuration ---
LINKS_FILE = "links.txt"
NORMAL_DIR = "normal"
BASE64_DIR = "base64"
README_FILE = "README.md"
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
if not GITHUB_REPO:
    raise ValueError("GITHUB_REPOSITORY environment variable not set. This script should be run in a GitHub Action.")

# --- Realistic User-Agents to Mimic Real Browsers ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/125.0.0.0",
]

# --- Helper Functions ---

def convert_github_url_to_raw(url: str) -> str:
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def is_base64(s: str) -> bool:
    if not re.match(r'^[A-Za-z0-9+/=\s]+$', s.strip()):
        return False
    s_cleaned = "".join(s.split())
    try:
        s_padded = s_cleaned + '=' * (-len(s_cleaned) % 4)
        decoded_bytes = base64.b64decode(s_padded, validate=True)
        return base64.b64encode(decoded_bytes).decode('utf-8') == s_padded
    except (ValueError, TypeError):
        return False

def get_processed_content_from_url(url: str) -> str:
    """
    Fetches content from a URL using a real browser (Headless Chrome via Selenium)
    to simulate human behavior and bypass simple anti-bot measures.
    """
    processed_url = convert_github_url_to_raw(url)
    
    # --- Selenium WebDriver Setup ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    driver = None
    try:
        # Use webdriver-manager to automatically handle the chromedriver
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set a reasonable page load timeout
        driver.set_page_load_timeout(30)
        
        driver.get(processed_url)
        
        # Wait a few seconds for any potential JavaScript to load content
        time.sleep(3)
        
        # Extract content. Browsers often wrap plain text in a <pre> tag.
        # If not found, fall back to the body text.
        pre_elements = driver.find_elements(By.TAG_NAME, "pre")
        if pre_elements:
            content = pre_elements[0].text
        else:
            content = driver.find_element(By.TAG_NAME, "body").text
        
        # --- End of Selenium Logic ---

        if is_base64(content):
            print(f"    - [Base64 Detected] Processing URL: {processed_url[:70]}...")
            cleaned_content = "".join(content.split())
            return base64.b64decode(cleaned_content).decode('utf-8')
        else:
            print(f"    - [Plain Text] Processing URL: {processed_url[:70]}...")
            return content
            
    except Exception as e:
        print(f"    - [ERROR] Failed to fetch or process with Selenium from {processed_url[:70]}: {e}")
        return None
    finally:
        # CRITICAL: Always close the browser to free up resources
        if driver:
            driver.quit()

# --- Main Logic ---

def main():
    Path(NORMAL_DIR).mkdir(exist_ok=True)
    Path(BASE64_DIR).mkdir(exist_ok=True)

    if not Path(LINKS_FILE).exists():
        print(f"Error: Input file '{LINKS_FILE}' not found.")
        return

    processed_files = []

    with open(LINKS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Add a small, random delay to mimic human behavior between processing different output files
        time.sleep(random.uniform(1, 3))

        parts = line.split(',', 1)
        if len(parts) != 2:
            print(f"Warning: Skipping malformed line: {line}")
            continue
        
        sources_part, output_name = parts[0].strip(), parts[1].strip()
        
        print(f"\n{'='*20} Processing Output File: {output_name} {'='*20}")
        
        individual_urls = [s.strip() for s in sources_part.split('|')]
        print(f"Found {len(individual_urls)} source(s) for this file.")
        
        all_contents = []
        for i, url in enumerate(individual_urls):
            print(f"  [{i+1}/{len(individual_urls)}] Fetching from source...")
            content = get_processed_content_from_url(url)
            if content is not None:
                line_count = len(content.splitlines())
                print(f"    - [SUCCESS] Fetched {line_count} lines of content.")
                all_contents.append(content)
            else:
                print(f"    - [FAILURE] No content retrieved from this source.")
        
        if not all_contents:
            print(f"[FINAL WARNING] Could not fetch any valid content for '{output_name}'. Skipping.")
            print(f"{'='* (58 + len(output_name))}")
            continue

        print(f"\n  Combining content for '{output_name}':")
        print(f"  - Successfully fetched content from {len(all_contents)} out of {len(individual_urls)} sources.")
        
        raw_combined_content = "\n".join(c.strip() for c in all_contents)
        total_lines = raw_combined_content.splitlines()
        print(f"  - Total lines before deduplication: {len(total_lines)}")

        unique_lines = list(dict.fromkeys(line for line in total_lines if line.strip()))
        print(f"  - Total unique (non-empty) lines after deduplication: {len(unique_lines)}")
        
        final_content = "\n".join(unique_lines)

        normal_path = Path(NORMAL_DIR) / f"{output_name}.txt"
        normal_path.write_text(final_content, encoding='utf-8')

        base64_final_content = base64.b64encode(final_content.encode('utf-8')).decode('utf-8')
        base64_path = Path(BASE64_DIR) / f"{output_name}.b64"
        base64_path.write_text(base64_final_content, encoding='utf-8')
        
        print(f"\n[FINAL STATUS] Processed '{output_name}': created {normal_path} and {base64_path}")
        print(f"{'='* (58 + len(output_name))}")

        processed_files.append({
            "name": output_name,
            "normal_path": normal_path.as_posix(),
            "base64_path": base64_path.as_posix()
        })

    update_readme(processed_files)
    print("\nREADME.md has been updated.")


def update_readme(processed_files):
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    timestamp = now_tehran.strftime('%Y-m-%d %H:%M:%S %Z')
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
