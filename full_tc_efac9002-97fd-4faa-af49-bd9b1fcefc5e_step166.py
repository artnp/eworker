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
                        if 'def create_ad_banner' in line:
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                content = data.get('content', '')
                                if 'def create_ad_banner' in content:
                                    folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                    print(f"--- CONTENT {folder_name} step {step} ---")
                                    # Print first 20 lines of the function
                                    lines = content.split('\n')
                                    for idx, l in enumerate(lines):
                                        if 'def create_ad_banner' in l:
                                            for jl in lines[idx:idx+40]:
                                                print(jl)
                                            break
                            except Exception:
                                pass
                        # Also check tool_calls
                        if 'create_ad_banner' in line:
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                tool_calls = data.get('tool_calls', [])
                                for tc in tool_calls:
                                    args = tc.get('args', {})
                                    code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                                    if 'def create_ad_banner' in code or 'create_ad_banner' in code:
                                        folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                        print(f"--- TOOL CALL {folder_name} step {step} ---")
                                        lines = code.split('\n')
                                        for idx, l in enumerate(lines):
                                            if 'create_ad_banner' in l:
                                                for jl in lines[idx:idx+40]:
                                                    print(jl)
                                                break
                            except Exception:
                                pass
            except Exception:
                pass
