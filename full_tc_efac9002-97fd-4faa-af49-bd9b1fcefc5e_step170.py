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
                        if 'create_ad_banner' in line:
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                
                                # Check tool calls
                                tool_calls = data.get('tool_calls', [])
                                for tc in tool_calls:
                                    args = tc.get('args', {})
                                    code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                                    if 'create_ad_banner' in code:
                                        folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                        out_name = f"full_tc_{folder_name}_step{step}.py"
                                        with open(os.path.join(r"d:\Github\eworker", out_name), 'w', encoding='utf-8') as out_f:
                                            out_f.write(code)
                                        print(f"Saved full tc file {out_name}")
                                
                                content = data.get('content', '')
                                if content and 'def create_ad_banner' in content:
                                    folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                    out_name = f"full_view_{folder_name}_step{step}.py"
                                    with open(os.path.join(r"d:\Github\eworker", out_name), 'w', encoding='utf-8') as out_f:
                                        out_f.write(content)
                                    print(f"Saved full view file {out_name}")
                            except Exception as e:
                                print(f"Error parsing: {e}")
            except Exception as e:
                pass
