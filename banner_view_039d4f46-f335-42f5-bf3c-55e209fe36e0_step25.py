Created At: 2026-06-16T11:48:11Z
Completed At: 2026-06-16T11:48:11Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 647
Total Bytes: 27903
Showing lines 221 to 402
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
221: def create_ad_banner(width):
222:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
223:     scale = max(0.85, min(width / 900.0, 2.5))
224:     banner_h = int(95 * scale)
225:     
226:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
227:     grad = Image.new('RGBA', (2, 1))
228:     grad.putpixel((0, 0), (253, 224, 71, 255))
229:     grad.putpixel((1, 0), (234, 179, 8, 255))
230:     try:
231:         resample_filter = Image.Resampling.BILINEAR
232:     except AttributeError:
233:         resample_filter = Image.BILINEAR
234:     banner = grad.resize((width, banner_h), resample_filter)
235:     draw = ImageDraw.Draw(banner)
236:     
237:     # เส้นคั่นสีส้ม/น้ำตาลทองด้านล่าง
238:     accent_h = max(2, int(3 * scale))
239:     draw.rectangle([0, banner_h - accent_h, width - 1, banner_h - 1], fill=(180, 83, 9, 255))
240:     
241:     # โหลดฟอนต์: emoji, ข้อความหลัก, ข้อความรอง
242:     emoji_size = int(26 * scale)
243:     text_size = int(22 * scale)
244:     sub_size = int(15 * scale)
245:     
246:     font_emoji = None
247:     for fp in ["C:/Windows/Fonts/seguiemj.ttf"]:
248:         if os.path.exists(fp):
249:       
<truncated 5397 bytes>
nt=p["font"])
362:                 pw = bb[2] - bb[0]
363:             except:
364:                 pw = int(len(p["text"]) * 5 * scale)
365:             part_widths_l2.append(pw)
366:             total_w2 += pw
367:             
368:         text_size = t_sz2
369:         sub_size = s_sz2
370:         
371:     # จัดกึ่งกลางแนวตั้งสำหรับ 2 บรรทัด
372:     spacing = int(4 * scale)
373:     total_text_h = text_size + spacing + sub_size
374:     available_h = banner_h - accent_h
375:     start_y = (available_h - total_text_h) // 2
376:     y1 = start_y
377:     y2 = start_y + text_size + spacing
378:     
379:     # === วาดบรรทัดแรก (กึ่งกลางแนวนอน) ===
380:     start_x1 = max(margin_pad, (width - total_w1) // 2)
381:     cur_x = start_x1
382:     for i, p in enumerate(parts_l1):
383:         if p["emoji"] and font_emoji:
384:             emoji_y = y1 - int(2 * scale)
385:             draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
386:         else:
387:             draw.text((cur_x, y1), p["text"], fill=p["fill"], font=p["font"])
388:         cur_x += part_widths_l1[i]
389:         
390:     # === วาดบรรทัดที่สอง (กึ่งกลางแนวนอน) ===
391:     start_x2 = max(margin_pad, (width - total_w2) // 2)
392:     cur_x = start_x2
393:     for i, p in enumerate(parts_l2):
394:         if p["emoji"] and font_emoji:
395:             emoji_y = y2 - int(2 * scale)
396:             draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
397:         else:
398:             draw.text((cur_x, y2), p["text"], fill=p["fill"], font=p["font"])
399:         cur_x += part_widths_l2[i]
400:         
401:     return banner.convert('RGB')
402: 
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
