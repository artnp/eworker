Created At: 2026-07-03T01:20:52Z
Completed At: 2026-07-03T01:20:52Z
File Path: `file:///d:/Github/eworker/full_view_efac9002-97fd-4faa-af49-bd9b1fcefc5e_step169.py`
Total Lines: 106
Total Bytes: 8403
Showing lines 1 to 106
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: Created At: 2026-07-03T01:20:25Z
2: Completed At: 2026-07-03T01:20:29Z
3: 
4: 				The command completed successfully.
5: 				Output:
6: 				<truncated 432 lines>
7: Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 11
8: Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 25
9: Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 44
10: Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 160
11: Found create_ad_banner in tool call in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 163
12: Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 164
13: Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 176
14: Found create_ad_banner in tool call in efac9002-97fd-4faa-af49-bd9b1fcefc5e step 154
15: Found create_ad_banner in tool call in efac9002-97fd-4faa-af49-bd9b1fcefc5e step 154
16: 
17: 
18: --- CONTENT efac9002-97fd-4faa-af49-bd9b1fcefc5e step 163 ---
19: 29: 221: def create_ad_banner(width):
20: 30: 222:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
21: 31: 223:     scale = max(0.85, min(width / 900.0, 2.5))
22: 32: 224:     banner_h = int(95 * scale)
23: 33: 225:     
24: 34: 226:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
25: 35: 227:     grad = Image.new('RGBA', (2, 1))
26: 36: 228:     grad.putpixel((0, 0), (253, 224, 71, 255))
27: 37: 229:     grad.putpixel((1, 0), (234, 179, 8, 255))
28: 38: 230:     try:
29: 39: 231:      
30: 40: <truncated 19364 bytes>
31: 41: et, 'wb') as f:
32: 42: 609:                 f.write(data)
33: 43: 610:     except Exception as e:
34: 44: 611:         print(f"Error saving file: {e}")
35: 45: 612:     
36: 46: 613:     if no_paste:
37: 47: 614:         print("[Donate] Process only completed. Saved to target/Desktop. Skipped clipboard/pasting.")
38: 48: 615:         return
39: 49: 616: 
40: 50: 617:     copy_image_to_clipboard(target)
41: 51: 618:     
42: 52: 619:     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
43: 53: 620:     time.sleep(2.0)
44: 54: 621:     auto_paste()
45: 55: 622:     
46: 56: 623:     # --- ★ ล้าง Clipboard หลัง Paste เสร็จ เพื่อป้องกัน complete.png หลุดไปวางใน Gemini sidetab ---
47: 57: 624:     time.sleep(1.0)
48: 58: 625:     try:
49: 59: 626:         ps_clear = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'
50: 60: 627:         subprocess.run(
51: 61: 628:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_clear}"',
52: 62: 629:             shell=True, capture_output=True, text=True, timeout=5
53: 63: 630:         )
54: 64: 631:         print("[Clipboard] ✅ Clipboard cleared after paste (prevent Gemini sidetab leak)")
55: 65: 632:     except Exception as e:
56: 66: 633:         print(f"[Clipboard] Clear error (non-critical): {e}")
57: 67: 634: 
58: 68: 635: if __name__ == "__main__":
59: --- CONTENT efac9002-97fd-4faa-af49-bd9b1fcefc5e step 165 ---
60: 1: "import os\nimport sys\nfrom PIL import Image, ImageDraw, ImageFont\n\n# Add directory of screenshot_donate.py to path\nsys.path.append(r\"d:\\Github\\eworker\")\n\nfrom screenshot_donate import preprocess_thai_text\n\ndef create_ad_banner_new(width):\n    \"\"\"สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)\"\"\"\n    scale = max(0.85, min(width / 900.0, 2.5))\n    banner_h = int(120 * scale)\n    \n    # สร้างแถบ gradient สีน้ำเงิน ดูมืออาชีพน่าไว้วางใจ (น้ำเงินเข้ม -> น้ำเงินสว่าง)\n    grad = Image.new('RGBA', (2, 1))\n    grad.putpixel((0, 0), (10, 46, 92, 255))   # Dark Blue\n    grad.putpixel((1, 0), (21, 95, 160, 255))  # Professional lighter Blue\n    \n    try:\n        resample_filter = Image.Resampling.BILINEAR\n    except AttributeError:\n        resample_filter = Image.BILINEAR\n    banner = grad.resize((width, banner_h), resample_filter)\n    draw = ImageDraw.Draw(banner)\n    \n    # เส้นคั่น/เส้นปะสีขาวและกรรไกรด้านขวา\n    # เราจะวาดเส้นรอยปะสีขาวที่ด้านล่างของแบนเนอร์\n    accent_h = max(2, int(3 * scale))\n    # แต่ผู้ใช้ขอกรอบล่างเป็นรอยปะขาว\n    dash_w = int(10 * scale)\n    dash_g = int(6 * scale)\n    line_y = banner_h - int(6 * scale)\n    line_thickness = max(1, int(2 * scale))\n    \n    # เว้นที่ทางขวาสำหรับกรรไกรตัด\n    scissors_width = int(50 * scale)\n    end_x = width - scissors_width\n    \n    # วาดเส้นปะขาว\n    for x in range(0, end_x, dash_w + dash_g):\n        draw.line([(x, line_y), (min(x + dash_w, end_x), line_y)], fill=(255, 255, 255, 220),
61: 2: <truncated 8141 bytes>
62: The above content shows the entire, complete file contents of the requested file.
63: 
64: --- TOOL CALL efac9002-97fd-4faa-af49-bd9b1fcefc5e step 166 ---
65:                         if 'def create_ad_banner' in line:
66:                             try:
67:                                 data = json.loads(line)
68:                                 step = data.get('step_index', 0)
69:                                 content = data.get('content', '')
70:                                 if 'def create_ad_banner' in content:
71:                                     folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
72:                                     print(f"--- CONTENT {folder_name} step {step} ---")
73:                                     # Print first 20 lines of the function
74:                                     lines = content.split('\n')
75:                                     for idx, l in enumerate(lines):
76:                                         if 'def create_ad_banner' in l:
77:                                             for jl in lines[idx:idx+40]:
78:                                                 print(jl)
79:                                             break
80:                             except Exception:
81:                                 pass
82:                         # Also check tool_calls
83:                         if 'create_ad_banner' in line:
84:                             try:
85:                                 data = json.loads(line)
86:                                 step = data.get('step_index', 0)
87:                                 tool_calls = data.get('tool_calls', [])
88:                                 for tc in tool_calls:
89:                                     args = tc.get('args', {})
90:                                     code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
91:                                     if 'def create_ad_banner' in code or 'create_ad_banner' in code:
92:                                         folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
93:                                         print(f"--- TOOL CALL {folder_name} step {step} ---")
94:                                         lines = code.split('\n')
95:                                         for idx, l in enumerate(lines):
96:                                             if 'create_ad_banner' in l:
97:                                                 for jl in lines[idx:idx+40]:
98:                                                     print(jl)
99:                                                 break
100:                             except Exception:
101:                                 pass
102:             except Exception:
103:                 pass
104: 
105: 
106: 
The above content shows the entire, complete file contents of the requested file.
