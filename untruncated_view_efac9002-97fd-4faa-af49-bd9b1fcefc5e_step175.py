Created At: 2026-07-03T01:20:40Z
Completed At: 2026-07-03T01:20:41Z
File Path: `file:///d:/Github/eworker/banner_view_0bea6a47-896d-49e1-a5ff-dd34ea443860_step9.py`
Total Lines: 87
Total Bytes: 4206
Showing lines 1 to 87
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: Created At: 2026-06-14T11:45:19Z
2: Completed At: 2026-06-14T11:45:19Z
3: File Path: `file:///d:/Github/eworker/screenshot_donate.py`
4: Total Lines: 606
5: Total Bytes: 26355
6: Showing lines 208 to 365
7: The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
8: 208: 
9: 209: def create_ad_banner(width):
10: 210:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
11: 211:     scale = max(0.85, min(width / 900.0, 2.5))
12: 212:     banner_h = int(58 * scale)
13: 213:     
14: 214:     # สร้างแถบ gradient สีเข้ม (น้ำเงินเข้ม -> ม่วงเข้ม)
15: 215:     banner = Image.new('RGBA', (width, banner_h), (15, 23, 42, 255))
16: 216:     draw = ImageDraw.Draw(banner)
17: 217:     
18: 218:     # วาด gradient background
19: 219:     for x in range(width):
20: 220:         ratio = x / width
21: 221:         r = int(15 + ratio * 50)   # 15 -> 65
22: 222:         g = int(23 + ratio * 10)   # 23 -> 33
23: 223:         b = int(42 + ratio * 80)   # 42 -> 122
24: 224:         draw.line([(x, 0), (x, banner_h)], fill=(r, g, b))
25: 225:     
26: 226:     # เส้นคั่นสีทองด้านล่าง
27: 227:     accent_h = max(3, int(4 * scale))
28: 228:     for y in range(banner_h - accent_h, banner_h):
29: 229:         for x in range(width):
30: 230:             ratio = x / width
31: 231:             r2 = int(250 - ratio * 30)
32: 232:             g2 = int(204 - ratio * 50)
33: 233:             b2 = int(21 + ratio * 40)
34: 234:             draw.point((x, y), fill=(r2, g2, b2))
35: 235:     
36: 236:     # โหลดฟอนต์ 3 ตัว: emoji, ข้อความหลัก, URL
37: 237:     emoji_size = int(28 * scale)
38: 238:     text_size = int(22 * scale)
39: 239:     url_size = int(20 * scale)
40: 240:     
41: 241:     font_emoji = None
42: 242:     for fp in ["C:/Windo
43: <truncated 4282 bytes>
44:         for p in parts:
45: 325:             if p["emoji"] and font_emoji:
46: 326:                 p["font"] = font_emoji
47: 327:             elif "artnp" in p["text"]:
48: 328:                 p["font"] = font_url
49: 329:             elif not p["emoji"]:
50: 330:                 p["font"] = font_main
51: 331:         # คำนวณความกว้างใหม่
52: 332:         total_w = 0
53: 333:         part_widths = []
54: 334:         for p in parts:
55: 335:             try:
56: 336:                 bb = draw.textbbox((0, 0), p["text"], font=p["font"])
57: 337:                 pw = bb[2] - bb[0]
58: 338:             except:
59: 339:                 pw = int(len(p["text"]) * 6 * scale)
60: 340:             part_widths.append(pw)
61: 341:             total_w += pw
62: 342:         text_size = t_sz2
63: 343:     
64: 344:     # จัดกึ่งกลางแนวนอน
65: 345:     start_x = max(margin_pad, (width - total_w) // 2)
66: 346:     # จัดกึ่งกลางแนวตั้ง
67: 347:     text_y = int((banner_h - accent_h - text_size) / 2)
68: 348:     
69: 349:     # === วาดแต่ละชิ้นทีละตัว ===
70: 350:     cur_x = start_x
71: 351:     for i, p in enumerate(parts):
72: 352:         if p["emoji"] and font_emoji:
73: 353:             # วาด emoji สีด้วย embedded_color
74: 354:             emoji_y = text_y - int(2 * scale)  # emoji มักสูงกว่า ปรับขึ้นนิด
75: 355:             draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
76: 356:         else:
77: 357:             draw.text((cur_x, text_y), p["text"], fill=p["fill"], font=p["font"])
78: 358:         cur_x += part_widths[i]
79: 359:     
80: 360:     return banner.convert('RGB')
81: 361: 
82: 362: def paste_ad_banner(img):
83: 363:     """แปะแถบโฆษณาบนหัวภาพ"""
84: 364:     w, h = img.size
85: 365:     banner = create_ad_banner(w)
86: The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
87: 
The above content shows the entire, complete file contents of the requested file.
