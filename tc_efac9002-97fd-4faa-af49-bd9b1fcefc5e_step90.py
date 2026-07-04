import os
import json

brain_dir = r"C:\Users\artwh\.gemini\antigravity-ide\brain"

# Let's search in C:\Users\artwh\.gemini\antigravity-ide\brain\da2e931c-90a4-454c-af11-54df274cc8f3\.system_generated\logs\transcript.jsonl
# and print the code of process_donate.
target_paths = [
    r"C:\Users\artwh\.gemini\antigravity-ide\brain\da2e931c-90a4-454c-af11-54df274cc8f3\.system_generated\logs\transcript.jsonl",
    r"C:\Users\artwh\.gemini\antigravity-ide\brain\ae84c296-d323-43f2-bdc3-c8549423fb57\.system_generated\logs\transcript.jsonl",
    r"C:\Users\artwh\.gemini\antigravity-ide\brain\c7eb83e6-0ec2-41e3-aa79-7ff24025367d\.system_generated\logs\transcript.jsonl",
]

for path in target_paths:
    if not os.path.exists(path):
        continue
    print(f"Reading {path}...")
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'def process_donate' in line or 'ハート' in line or 'อยากจะแก้ไขบ้าง' in line:
                data = json.loads(line)
                tool_calls = data.get('tool_calls', [])
                for tc in tool_calls:
                    args = tc.get('arguments', {})
                    code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                    if 'def process_donate' in code:
                        print(f"Found code in {path}")
                        # Let's write this code to a file so we can view it
                        out_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path)))) + "_screenshot_donate.py"
                        out_path = os.path.join(r"d:\Github\eworker", out_name)
                        with open(out_path, 'w', encoding='utf-8') as out_f:
                            out_f.write(code)
                        print(f"Saved code to {out_path}")
                        break
