Created At: 2026-06-14T11:46:59Z
Completed At: 2026-06-14T11:46:59Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 628
Total Bytes: 27047
Showing lines 208 to 230
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
208: 
209: def create_ad_banner(width):
210:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
211:     scale = max(0.85, min(width / 900.0, 2.5))
212:     banner_h = int(95 * scale)
213:     
214:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน)
215:     banner = Image.new('RGBA', (width, banner_h), (253, 224, 71, 255))
216:     draw = ImageDraw.Draw(banner)
217:     
218:     # วาด gradient background (จาก Yellow-300: 253, 224, 71 ถึง Yellow-500: 234, 179, 8)
219:     for x in range(width):
220:         ratio = x / width
221:         r = int(253 - ratio * 19)
222:         g = int(224 - ratio * 45)
223:         b = int(71 - ratio * 63)
224:         draw.line([(x, 0), (x, banner_h)], fill=(r, g, b, 255))
225:     
226:     # เส้นคั่นสีส้ม/น้ำตาลทองด้านล่าง
227:     accent_h = max(2, int(3 * scale))
228:     draw.rectangle([0, banner_h - accent_h, width - 1, banner_h - 1], fill=(180, 83, 9, 255))
229:     
230:     # โหลดฟอนต์: emoji, ข้อความหลัก, ข้อความรอง
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
