import os
import json

brain_dir = r"C:\Users\artwh\.gemini\antigravity-ide\brain"

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == 'transcript_full.jsonl':
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        if 'screenshot_donate.py' in line and 'VIEW_FILE' in line:
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                type_ = data.get('type', '')
                                content = data.get('content', '')
                                if content and 'def process_donate' in content:
                                    folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                    out_name = f"viewed_{folder_name}_step{step}.py"
                                    out_path = os.path.join(r"d:\Github\eworker", out_name)
                                    with open(out_path, 'w', encoding='utf-8') as out_f:
                                        out_f.write(content)
                                    print(f"Saved viewed file to {out_name} from step {step}")
                            except Exception as json_err:
                                pass
            except Exception as e:
                pass
