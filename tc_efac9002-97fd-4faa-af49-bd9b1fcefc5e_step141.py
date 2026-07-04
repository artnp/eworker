import os
import json

brain_dir = r"C:\Users\artwh\.gemini\antigravity-ide\brain"

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file in ['transcript.jsonl', 'transcript_full.jsonl']:
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        if 'screenshot_donate.py' in line and ('def process_donate' in line or 'อยากจะแก้ไขบ้าง' in line):
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                type_ = data.get('type', '')
                                
                                # Check tool calls first
                                tool_calls = data.get('tool_calls', [])
                                for tc in tool_calls:
                                    args = tc.get('args', {})
                                    code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                                    if 'process_donate' in code:
                                        folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                        out_name = f"tc_{folder_name}_step{step}.py"
                                        out_path = os.path.join(r"d:\Github\eworker", out_name)
                                        with open(out_path, 'w', encoding='utf-8') as out_f:
                                            out_f.write(code)
                                        print(f"Saved tc file {out_name} from {file}")
                                
                                # Check viewed file content
                                content = data.get('content', '')
                                if content and 'def process_donate' in content:
                                    folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                    out_name = f"view_{folder_name}_step{step}.py"
                                    out_path = os.path.join(r"d:\Github\eworker", out_name)
                                    with open(out_path, 'w', encoding='utf-8') as out_f:
                                        out_f.write(content)
                                    print(f"Saved view file {out_name} from {file}")
                            except Exception as json_err:
                                pass
            except Exception as e:
                pass
