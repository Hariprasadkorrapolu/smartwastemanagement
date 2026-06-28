import os

css_path = r"c:\Users\DELL\Documents\Codex\2026-05-02\you-are-an-expert-full-stack\core\static\core\styles.css"

with open(css_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

found = []
for line_num, line in enumerate(content.splitlines(), 1):
    if "guide-" in line or "guide_layout" in line:
        found.append(f"Line {line_num}: {line.strip()}")

if found:
    print(f"Found {len(found)} references to 'guide-' in styles.css:")
    for f in found[:50]: # Print first 50
        print(f)
else:
    print("No references to 'guide-' found in styles.css!")
