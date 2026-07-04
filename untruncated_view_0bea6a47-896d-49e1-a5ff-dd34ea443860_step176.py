Created At: 2026-06-14T12:01:57Z
Completed At: 2026-06-14T12:01:57Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 645
Total Bytes: 27937
Showing lines 195 to 225
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
195: def crop_watermark(source_path):
196:     if not os.path.exists(source_path):
197:         print(f"ไม่พบไฟล์: {source_path}")
198:         return None
199:     with Image.open(source_path) as img:
200:         img_rgb = img.convert('RGB')
201:         orig_w, orig_h = img_rgb.size
202:         white_band_h = get_white_band_height(img_rgb)
203:         if white_band_h > 0:
204:             crop_bottom = max(160, white_band_h) + 2
205:         else:
206:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
207: 
208: def preprocess_thai_text(text):
209:     if not text:
210:         return text
211:     upper_vowels = {'ิ', 'ี', 'ึ', 'ื'}
212:     tone_marks = {'่', '้', '๊', '๋', '็', '์'}
213:     result = []
214:     for i in range(len(text)):
215:         result.append(text[i])
216:         if text[i] in upper_vowels and i + 1 < len(text) and text[i+1] in tone_marks:
217:             result.append('\u200a')
218:     return "".join(result)
219: 
220: def create_ad_banner(width):
221:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
222:     scale = max(0.85, min(width / 900.0, 2.5))
223:     banner_h = int(95 * scale)
224:     
225:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
