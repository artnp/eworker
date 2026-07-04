Created At: 2026-07-03T01:27:32Z
Completed At: 2026-07-03T01:27:32Z
File Path: `file:///d:/Github/eworker/untruncated_view_0bea6a47-896d-49e1-a5ff-dd34ea443860_step176.py`
Total Lines: 40
Total Bytes: 2264
Showing lines 1 to 40
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: Created At: 2026-06-14T12:01:57Z
2: Completed At: 2026-06-14T12:01:57Z
3: File Path: `file:///d:/Github/eworker/screenshot_donate.py`
4: Total Lines: 645
5: Total Bytes: 27937
6: Showing lines 195 to 225
7: The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
8: 195: def crop_watermark(source_path):
9: 196:     if not os.path.exists(source_path):
10: 197:         print(f"ไม่พบไฟล์: {source_path}")
11: 198:         return None
12: 199:     with Image.open(source_path) as img:
13: 200:         img_rgb = img.convert('RGB')
14: 201:         orig_w, orig_h = img_rgb.size
15: 202:         white_band_h = get_white_band_height(img_rgb)
16: 203:         if white_band_h > 0:
17: 204:             crop_bottom = max(160, white_band_h) + 2
18: 205:         else:
19: 206:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
20: 207: 
21: 208: def preprocess_thai_text(text):
22: 209:     if not text:
23: 210:         return text
24: 211:     upper_vowels = {'ิ', 'ี', 'ึ', 'ื'}
25: 212:     tone_marks = {'่', '้', '๊', '๋', '็', '์'}
26: 213:     result = []
27: 214:     for i in range(len(text)):
28: 215:         result.append(text[i])
29: 216:         if text[i] in upper_vowels and i + 1 < len(text) and text[i+1] in tone_marks:
30: 217:             result.append('\u200a')
31: 218:     return "".join(result)
32: 219: 
33: 220: def create_ad_banner(width):
34: 221:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
35: 222:     scale = max(0.85, min(width / 900.0, 2.5))
36: 223:     banner_h = int(95 * scale)
37: 224:     
38: 225:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
39: The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
40: 
The above content shows the entire, complete file contents of the requested file.
