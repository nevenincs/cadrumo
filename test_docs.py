import os
import re
import subprocess
import glob

docs_dir = r"Y:\code\aeat-worktrees\chore-476-restructure-execution\docs"
failed_commands = []
passed_commands = []

for root, _, files in os.walk(docs_dir):
    for file in files:
        if file.endswith(".md"):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all bash/sh/pwsh blocks
            blocks = re.findall(r'```(?:bash|sh|pwsh)\n(.*?)\n```', content, re.DOTALL)
            
            for block in blocks:
                commands = block.strip().split('\n')
                for cmd in commands:
                    cmd = cmd.strip()
                    if cmd and not cmd.startswith('#'):
                        # If the command starts with '$ ', strip it
                        if cmd.startswith('$ '):
                            cmd = cmd[2:]
                        
                        print(f"Running in {file}: {cmd}")
                        try:
                            # Using shell=True to execute commands properly
                            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                            if result.returncode != 0:
                                failed_commands.append((file, cmd, result.returncode, result.stderr))
                                print(f"FAILED (code {result.returncode}): {result.stderr.strip()}")
                            else:
                                passed_commands.append((file, cmd))
                                print("PASSED")
                        except subprocess.TimeoutExpired:
                            failed_commands.append((file, cmd, -1, "Timeout"))
                            print("TIMEOUT")
                        except Exception as e:
                            failed_commands.append((file, cmd, -1, str(e)))
                            print(f"EXCEPTION: {e}")

print("\n--- Summary ---")
print(f"Passed: {len(passed_commands)}")
print(f"Failed: {len(failed_commands)}")

if failed_commands:
    print("\nFailures:")
    for file, cmd, code, err in failed_commands:
        print(f"{file} | {cmd} | Code: {code}")
        if err:
            print(f"  Error: {err.strip()}")
