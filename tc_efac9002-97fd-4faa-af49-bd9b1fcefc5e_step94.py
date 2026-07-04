import os
import json

brain_dir = r"C:\Users\artwh\.gemini\antigravity-ide\brain"

# Let's search in C:\Users\artwh\.gemini\antigravity-ide\brain\*\.system_generated\logs\transcript_full.jsonl
# and print the code of process_donate.

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == 'transcript_full.jsonl':
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'def process_donate' in line:
                            data = json.loads(line)
                            tool_calls = data.get('tool_calls', [])
                            for tc in tool_calls:
                                args = tc.get('arguments', {})
                                code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                                if 'def process_donate' in code:
                                    out_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path)))) + "_screenshot_donate.py"
                                    out_path = os.path.join(r"d:\Github\eworker", out_name)
                                    with open(out_path, 'w', encoding='utf-8') as out_f:
                                        out_f.write(code)
                                    print(f"Saved code to {out_path}")
            except Exception as e:
                pass
