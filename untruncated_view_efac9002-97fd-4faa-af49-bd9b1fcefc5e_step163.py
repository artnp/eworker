Created At: 2026-07-03T01:20:14Z
Completed At: 2026-07-03T01:20:14Z
File Path: `file:///d:/Github/eworker/banner_view_039d4f46-f335-42f5-bf3c-55e209fe36e0_step4.py`
Total Lines: 82
Total Bytes: 4202
Showing lines 1 to 82
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: Created At: 2026-06-16T11:47:10Z
2: Completed At: 2026-06-16T11:47:10Z
3: File Path: `file:///d:/Github/eworker/screenshot_donate.py`
4: Total Lines: 647
5: Total Bytes: 27903
6: Showing lines 200 to 647
7: The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
8: 200:         img_rgb = img.convert('RGB')
9: 201:         orig_w, orig_h = img_rgb.size
10: 202:         white_band_h = get_white_band_height(img_rgb)
11: 203:         if white_band_h > 0:
12: 204:             crop_bottom = max(160, white_band_h) + 2
13: 205:         else:
14: 206:             crop_bottom = max(60, int(orig_h * 0.065))
15: 207:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
16: 208: 
17: 209: def preprocess_thai_text(text):
18: 210:     if not text:
19: 211:         return text
20: 212:     upper_vowels = {'ิ', 'ี', 'ึ', 'ื'}
21: 213:     tone_marks = {'่', '้', '๊', '๋', '็', '์'}
22: 214:     result = []
23: 215:     for i in range(len(text)):
24: 216:         result.append(text[i])
25: 217:         if text[i] in upper_vowels and i + 1 < len(text) and text[i+1] in tone_marks:
26: 218:             result.append('\u200a')
27: 219:     return "".join(result)
28: 220: 
29: 221: def create_ad_banner(width):
30: 222:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
31: 223:     scale = max(0.85, min(width / 900.0, 2.5))
32: 224:     banner_h = int(95 * scale)
33: 225:     
34: 226:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
35: 227:     grad = Image.new('RGBA', (2, 1))
36: 228:     grad.putpixel((0, 0), (253, 224, 71, 255))
37: 229:     grad.putpixel((1, 0), (234, 179, 8, 255))
38: 230:     try:
39: 231:      
40: <truncated 19364 bytes>
41: et, 'wb') as f:
42: 609:                 f.write(data)
43: 610:     except Exception as e:
44: 611:         print(f"Error saving file: {e}")
45: 612:     
46: 613:     if no_paste:
47: 614:         print("[Donate] Process only completed. Saved to target/Desktop. Skipped clipboard/pasting.")
48: 615:         return
49: 616: 
50: 617:     copy_image_to_clipboard(target)
51: 618:     
52: 619:     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
53: 620:     time.sleep(2.0)
54: 621:     auto_paste()
55: 622:     
56: 623:     # --- ★ ล้าง Clipboard หลัง Paste เสร็จ เพื่อป้องกัน complete.png หลุดไปวางใน Gemini sidetab ---
57: 624:     time.sleep(1.0)
58: 625:     try:
59: 626:         ps_clear = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'
60: 627:         subprocess.run(
61: 628:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_clear}"',
62: 629:             shell=True, capture_output=True, text=True, timeout=5
63: 630:         )
64: 631:         print("[Clipboard] ✅ Clipboard cleared after paste (prevent Gemini sidetab leak)")
65: 632:     except Exception as e:
66: 633:         print(f"[Clipboard] Clear error (non-critical): {e}")
67: 634: 
68: 635: if __name__ == "__main__":
69: 636:     mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
70: 637:     target_path = sys.argv[2] if len(sys.argv) > 2 else None
71: 638:     
72: 639:     if mode_flag == "--clean":
73: 640:         process_clean_only(target_path)
74: 641:     elif mode_flag == "--donate":
75: 642:         process_donate(target_path)
76: 643:     elif mode_flag == "--donate-no-paste":
77: 644:         process_donate(target_path, no_paste=True)
78: 645:     else:
79: 646:         process_donate()
80: 647: 
81: The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
82: 
The above content shows the entire, complete file contents of the requested file.
