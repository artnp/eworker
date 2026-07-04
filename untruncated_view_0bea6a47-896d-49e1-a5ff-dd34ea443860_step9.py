Created At: 2026-06-14T11:45:19Z
Completed At: 2026-06-14T11:45:19Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 606
Total Bytes: 26355
Showing lines 208 to 365
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
208: 
209: def create_ad_banner(width):
210:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
211:     scale = max(0.85, min(width / 900.0, 2.5))
212:     banner_h = int(58 * scale)
213:     
214:     # สร้างแถบ gradient สีเข้ม (น้ำเงินเข้ม -> ม่วงเข้ม)
215:     banner = Image.new('RGBA', (width, banner_h), (15, 23, 42, 255))
216:     draw = ImageDraw.Draw(banner)
217:     
218:     # วาด gradient background
219:     for x in range(width):
220:         ratio = x / width
221:         r = int(15 + ratio * 50)   # 15 -> 65
222:         g = int(23 + ratio * 10)   # 23 -> 33
223:         b = int(42 + ratio * 80)   # 42 -> 122
224:         draw.line([(x, 0), (x, banner_h)], fill=(r, g, b))
225:     
226:     # เส้นคั่นสีทองด้านล่าง
227:     accent_h = max(3, int(4 * scale))
228:     for y in range(banner_h - accent_h, banner_h):
229:         for x in range(width):
230:             ratio = x / width
231:             r2 = int(250 - ratio * 30)
232:             g2 = int(204 - ratio * 50)
233:             b2 = int(21 + ratio * 40)
234:             draw.point((x, y), fill=(r2, g2, b2))
235:     
236:     # โหลดฟอนต์ 3 ตัว: emoji, ข้อความหลัก, URL
237:     emoji_size = int(28 * scale)
238:     text_size = int(22 * scale)
239:     url_size = int(20 * scale)
240:     
241:     font_emoji = None
242:     for fp in ["C:/Windo
<truncated 4282 bytes>
        for p in parts:
325:             if p["emoji"] and font_emoji:
326:                 p["font"] = font_emoji
327:             elif "artnp" in p["text"]:
328:                 p["font"] = font_url
329:             elif not p["emoji"]:
330:                 p["font"] = font_main
331:         # คำนวณความกว้างใหม่
332:         total_w = 0
333:         part_widths = []
334:         for p in parts:
335:             try:
336:                 bb = draw.textbbox((0, 0), p["text"], font=p["font"])
337:                 pw = bb[2] - bb[0]
338:             except:
339:                 pw = int(len(p["text"]) * 6 * scale)
340:             part_widths.append(pw)
341:             total_w += pw
342:         text_size = t_sz2
343:     
344:     # จัดกึ่งกลางแนวนอน
345:     start_x = max(margin_pad, (width - total_w) // 2)
346:     # จัดกึ่งกลางแนวตั้ง
347:     text_y = int((banner_h - accent_h - text_size) / 2)
348:     
349:     # === วาดแต่ละชิ้นทีละตัว ===
350:     cur_x = start_x
351:     for i, p in enumerate(parts):
352:         if p["emoji"] and font_emoji:
353:             # วาด emoji สีด้วย embedded_color
354:             emoji_y = text_y - int(2 * scale)  # emoji มักสูงกว่า ปรับขึ้นนิด
355:             draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
356:         else:
357:             draw.text((cur_x, text_y), p["text"], fill=p["fill"], font=p["font"])
358:         cur_x += part_widths[i]
359:     
360:     return banner.convert('RGB')
361: 
362: def paste_ad_banner(img):
363:     """แปะแถบโฆษณาบนหัวภาพ"""
364:     w, h = img.size
365:     banner = create_ad_banner(w)
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
