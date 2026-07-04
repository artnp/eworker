Created At: 2026-07-03T01:20:55Z
Completed At: 2026-07-03T01:20:55Z
File Path: `file:///d:/Github/eworker/full_view_efac9002-97fd-4faa-af49-bd9b1fcefc5e_step163.py`
Total Lines: 91
Total Bytes: 5157
Showing lines 1 to 91
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: Created At: 2026-07-03T01:20:14Z
2: Completed At: 2026-07-03T01:20:14Z
3: File Path: `file:///d:/Github/eworker/banner_view_039d4f46-f335-42f5-bf3c-55e209fe36e0_step4.py`
4: Total Lines: 82
5: Total Bytes: 4202
6: Showing lines 1 to 82
7: The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
8: 1: Created At: 2026-06-16T11:47:10Z
9: 2: Completed At: 2026-06-16T11:47:10Z
10: 3: File Path: `file:///d:/Github/eworker/screenshot_donate.py`
11: 4: Total Lines: 647
12: 5: Total Bytes: 27903
13: 6: Showing lines 200 to 647
14: 7: The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
15: 8: 200:         img_rgb = img.convert('RGB')
16: 9: 201:         orig_w, orig_h = img_rgb.size
17: 10: 202:         white_band_h = get_white_band_height(img_rgb)
18: 11: 203:         if white_band_h > 0:
19: 12: 204:             crop_bottom = max(160, white_band_h) + 2
20: 13: 205:         else:
21: 14: 206:             crop_bottom = max(60, int(orig_h * 0.065))
22: 15: 207:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
23: 16: 208: 
24: 17: 209: def preprocess_thai_text(text):
25: 18: 210:     if not text:
26: 19: 211:         return text
27: 20: 212:     upper_vowels = {'ิ', 'ี', 'ึ', 'ื'}
28: 21: 213:     tone_marks = {'่', '้', '๊', '๋', '็', '์'}
29: 22: 214:     result = []
30: 23: 215:     for i in range(len(text)):
31: 24: 216:         result.append(text[i])
32: 25: 217:         if text[i] in upper_vowels and i + 1 < len(text) and text[i+1] in tone_marks:
33: 26: 218:             result.append('\u200a')
34: 27: 219:     return "".join(result)
35: 28: 220: 
36: 29: 221: def create_ad_banner(width):
37: 30: 222:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
38: 31: 223:     scale = max(0.85, min(width / 900.0, 2.5))
39: 32: 224:     banner_h = int(95 * scale)
40: 33: 225:     
41: 34: 226:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
42: 35: 227:     grad = Image.new('RGBA', (2, 1))
43: 36: 228:     grad.putpixel((0, 0), (253, 224, 71, 255))
44: 37: 229:     grad.putpixel((1, 0), (234, 179, 8, 255))
45: 38: 230:     try:
46: 39: 231:      
47: 40: <truncated 19364 bytes>
48: 41: et, 'wb') as f:
49: 42: 609:                 f.write(data)
50: 43: 610:     except Exception as e:
51: 44: 611:         print(f"Error saving file: {e}")
52: 45: 612:     
53: 46: 613:     if no_paste:
54: 47: 614:         print("[Donate] Process only completed. Saved to target/Desktop. Skipped clipboard/pasting.")
55: 48: 615:         return
56: 49: 616: 
57: 50: 617:     copy_image_to_clipboard(target)
58: 51: 618:     
59: 52: 619:     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
60: 53: 620:     time.sleep(2.0)
61: 54: 621:     auto_paste()
62: 55: 622:     
63: 56: 623:     # --- ★ ล้าง Clipboard หลัง Paste เสร็จ เพื่อป้องกัน complete.png หลุดไปวางใน Gemini sidetab ---
64: 57: 624:     time.sleep(1.0)
65: 58: 625:     try:
66: 59: 626:         ps_clear = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'
67: 60: 627:         subprocess.run(
68: 61: 628:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_clear}"',
69: 62: 629:             shell=True, capture_output=True, text=True, timeout=5
70: 63: 630:         )
71: 64: 631:         print("[Clipboard] ✅ Clipboard cleared after paste (prevent Gemini sidetab leak)")
72: 65: 632:     except Exception as e:
73: 66: 633:         print(f"[Clipboard] Clear error (non-critical): {e}")
74: 67: 634: 
75: 68: 635: if __name__ == "__main__":
76: 69: 636:     mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
77: 70: 637:     target_path = sys.argv[2] if len(sys.argv) > 2 else None
78: 71: 638:     
79: 72: 639:     if mode_flag == "--clean":
80: 73: 640:         process_clean_only(target_path)
81: 74: 641:     elif mode_flag == "--donate":
82: 75: 642:         process_donate(target_path)
83: 76: 643:     elif mode_flag == "--donate-no-paste":
84: 77: 644:         process_donate(target_path, no_paste=True)
85: 78: 645:     else:
86: 79: 646:         process_donate()
87: 80: 647: 
88: 81: The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
89: 82: 
90: The above content shows the entire, complete file contents of the requested file.
91: 
The above content shows the entire, complete file contents of the requested file.
