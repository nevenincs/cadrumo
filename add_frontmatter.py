import os
import glob

docs_dir = r"Y:\code\aeat-worktrees\chore-476-restructure-execution\docs"

def add_frontmatter_if_missing(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if content.startswith("---\n"):
        return

    frontmatter = "---\nsummary: \"A documentation guide.\"\nread_time: \"5 min\"\n---\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + content)
    
    print(f"Added frontmatter to {file_path}")

for root, _, files in os.walk(docs_dir):
    for file in files:
        if file.endswith(".md"):
            add_frontmatter_if_missing(os.path.join(root, file))

print("Done.")
