import os
import json
import re

brain_dir = r"C:\Users\artwh\AppData\Local\Temp" # Wait, the actual path is C:\Users\artwh\.gemini\antigravity-ide\brain
brain_dir = r"C:\Users\artwh\.gemini\antigravity-ide\brain"

results = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == 'transcript.jsonl':
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        if 'def process_donate' in line or 'ハート' in line or 'อยากจะแก้ไขบ้าง' in line or 'สแกน QR' in line:
                            # Found a line containing code pattern
                            # Let's extract the step info
                            data = json.loads(line)
                            step_index = data.get('step_index', 0)
                            content = data.get('content', '')
                            tool_calls = data.get('tool_calls', [])
                            
                            print(f"Found match in {path} at step {step_index}")
                            # Print a snippet of the match
                            # Check tool calls
                            for tc in tool_calls:
                                args = tc.get('arguments', {})
                                code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                                if 'process_donate' in code:
                                    print(f"--- Code Content from {path} ---")
                                    # Print first 20 lines of the code to verify
                                    lines = code.splitlines()
                                    for l in lines[:40]:
                                        print(l)
                                    print("--------------------------------")
            except Exception as e:
                pass
