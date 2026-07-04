Created At: 2026-07-03T01:16:13Z
Completed At: 2026-07-03T01:16:14Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 582
Total Bytes: 26385
Showing lines 1 to 582
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: import sys
2: import os
3: import subprocess
4: import tempfile
5: import time
6: import random
7: import string
8: import ctypes
9: import ctypes.wintypes
10: import base64
11: 
12: # --- ติดตั้ง dependencies ที่จำเป็นก่อน ---
13: def ensure_deps():
14:     try:
15:         from PIL import Image
16:         import qrcode
17:         import requests
18:         import pyautogui
19:     except ImportError:
20:         subprocess.run([sys.executable, '-m', 'pip', 'install', 'Pillow', 'qrcode[pil]', 'requests', 'pyautogui', '--quiet'], check=True)
21: 
22: ensure_deps()
23: 
24: from PIL import Image, ImageDraw, ImageFont, ImageFilter
25: import qrcode
26: import requests
27: import pyautogui
28: 
29: # ตั้งค่าความเร็วสูงสุด
30: pyautogui.PAUSE = 0
31: pyautogui.FAILSAFE = False
32: 
33: def scrub_and_poison(file_path):
34:     ext = os.path.splitext(file_path)[1].lower()
35:     temp_dir = tempfile.gettempdir()
36:     random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
37:     temp_path = os.path.join(temp_dir, f"donate_{random_name}{ext}")
38:     try:
39:         with Image.open(file_path) as img:
40:             if ext in ['.jpg', '.jpeg'] and img.mode != 'RGB':
41:                 img = img.convert('RGB')
42:             if ext in ['.jpg', '.jpeg']:
43:                 img.save(temp_path, quality=95, subsampling=0)
44:             else:
45:                 img.save(temp_path)
46:         with open(temp_path, 'ab') as f:
47:             random_junk = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
48:             f.write(f"\n#DN_{random_junk}".encode())
49:         return temp_path
50:     except Exception:
51:         return file_path
52: 
53: def upload_litterbox_24h(file_path):
54:     try:
55:         url = 'https://litterbox.catbox.moe/resources/internals/api.php'
56:         with open(file_path, 'rb') as f:
57:             files = {'fileToUpload': f}
58:             data = {'reqtype': 'fileupload', 'time': '24h'}
59:             response = requests.post(url, data=data, files=files, timeout=30)
60:             if response.status_code == 200 and response.text.startswith('http'):
61:                 return response.text.strip()
62:     except Exception as e:
63:         print(f"Upload error: {e}")
64:     return None
65: 
66: def generate_qr_image(data, size=120):
67:     qr = qrcode.QRCode(version=1, box_size=6, border=2)
68:     qr.add_data(data)
69:     qr.make(fit=True)
70:     img = qr.make_image(fill_color="black", back_color="white")
71:     img = img.resize((size, size), Image.LANCZOS)
72:     return img
73: 
74: def copy_image_to_clipboard(file_path):
75:     try:
76:         abs_path = os.path.abspath(file_path).replace('/', '\\')
77:         ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; $img = [System.Drawing.Image]::FromFile('{abs_path}'); [System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose()"
78:         result = subprocess.run(
79:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_cmd}"',
80:             shell=True, capture_output=True, text=True
81:         )
82:         if result.returncode != 0:
83:             print(f"[Clipboard] PowerShell error: {result.stderr}")
84:         else:
85:             print(f"[Clipboard] Image copied to clipboard OK")
86:     except Exception as e:
87:         print(f"[Clipboard] Error: {e}")
88: 
89: def auto_paste():
90:     try:
91:         user32 = ctypes.windll.user32
92:         EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
93: 
94:         def _get_title(hwnd):
95:             length = user32.GetWindowTextLengthW(hwnd)
96:             if length <= 0: return ""
97:             buf = ctypes.create_unicode_buffer(length + 1)
98:             user32.GetWindowTextW(hwnd, buf, length + 1)
99:             return buf.value
100: 
101:         def _find_window_by_keywords(keywords):
102:             matches = []
103:             @EnumWindowsProc
104:             def _enum(hwnd, lparam):
105:                 title = _get_title(hwnd)
106:                 if not title: return True
107:                 title_lower = title.lower()
108:                 for kw in keywords:
109:                     if kw.lower() in title_lower:
110:                         matches.append((hwnd, title))
111:                         break
112:                 return True
113:             user32.EnumWindows(_enum, 0)
114:             return matches
115: 
116:         def _force_foreground(hwnd):
117:             user32.ShowWindow(hwnd, 9)
118:             user32.SetForegroundWindow(hwnd)
119:             return True
120: 
121:         def _parse_coords(title):
122:             try:
123:                 import re
124:                 if 'READY_TO_PASTE|' in title:
125:                     pattern = r'READY_TO_PASTE\|([\d\.]+)\|([\d\.]+)'
126:                     match = re.search(pattern, title)
127:                     if match:
128:                         return int(float(match.group(1))), int(float(match.group(2)))
129:                 return None
130:             except: return None
131: 
132:         print("[System] Mouse control sequence ACTIVATED.")
133:         target_hwnd, coords = None, None
134:         
135:         for i in range(300):
136:             wins = _find_window_by_keywords(['READY_TO_PASTE', 'READY_TO_POST'])
137:             if wins:
138:                 for h, t in wins:
139:                     c = _parse_coords(t)
140:                     if c:
141:                         target_hwnd, coords = h, c
142:                         pyautogui.moveTo(c[0], c[1], duration=0)
143:                         pyautogui.click()
144:                         break
145:                 if target_hwnd: break
146:             time.sleep(0.1)
147: 
148:         if not target_hwnd:
149:             print("[Fail] Handshake Timeout.")
150:             return
151:         
152:         _force_foreground(target_hwnd)
153:         time.sleep(0.5)
154:         pyautogui.hotkey('ctrl', 'v')
155:         
156:         for _ in range(40):
157:             wins = _find_window_by_keywords(['READY_TO_POST'])
158:             if wins:
159:                 _force_foreground(wins[0][0])
160:                 time.sleep(0.6)
161:                 pyautogui.press('enter')
162:                 break
163:             time.sleep(0.5)
164: 
165:         print("[AutoPaste] Sequence finished.")
166:     except Exception as e:
167:         print(f"[AutoPaste] Error: {e}")
168: 
169: def get_white_band_height(img):
170:     w, h = img.size
171:     img_rgb = img.convert('RGB')
172:     
173:     # เริ่มสแกนจากด้านล่างขึ้นไป หาจุดที่ไม่ใช่สีขาว
174:     for y in range(h - 1, max(0, h - int(h * 0.5)), -1):  # สแกนมากขึ้น (50% แทน 40%)
175:         white_count = 0
176:         samples = 30  # เพิ่มจำนวน sample points
177:         for i in range(samples):
178:             x = int((i / samples) * (w * 0.9))  # ครอบคลุมพื้นที่มากขึ้น (90% แทน 75%)
179:             r, g, b = img_rgb.getpixel((x, y))
180:             # ใช้เกณฑ์เข้มงวดขึ้นสำหรับสีขาว (220 แทน 190)
181:             if r > 220 and g > 220 and b > 220: 
182:                 white_count += 1
183:         
184:         # ถ้าไม่ใช่พื้นที่สีขาวส่วนใหญ่ (70% แทน 80%)
185:         if white_count < samples * 0.7:
186:             detected = h - y
187:             # เพิ่มการตัดขั้นต่ำ (40px แทน 20px)
188:             if detected >= 40: 
189:                 return detected + 20  # เพิ่ม buffer 20px
190:             else: 
191:                 return 60  # minimum cut 60px
192:     
193:     # กรณี fallback ตัดมากขึ้น (10% แทน 6.5%)
194:     return int(h * 0.1)
195: 
196: def crop_watermark(source_path):
197:     if not os.path.exists(source_path):
198:         print(f"ไม่พบไฟล์: {source_path}")
199:         return None
200:     with Image.open(source_path) as img:
201:         img_rgb = img.convert('RGB')
202:         orig_w, orig_h = img_rgb.size
203:         white_band_h = get_white_band_height(img_rgb)
204:         
205:         # *** แก้: ลบพื้นที่ขาวจริงๆ ไม่เพิ่ม ***
206:         if white_band_h > 0:
207:             # ตัดตามที่ detect ได้จริงๆ + เล็กน้อย buffer
208:             crop_bottom = white_band_h + 10
209:         else:
210:             # ถ้า detect ไม่เจอ ก็ตัดน้อยลง (ไม่ใช่มากกว่า)
211:             crop_bottom = int(orig_h * 0.08)  # ประมาณ 8% เท่านั้น
212:         
213:         print(f"[Crop] white_band_h={white_band_h}px, crop_bottom={crop_bottom}px, original_h={orig_h}px")
214:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
215: 
216: def process_clean_only(full_path=None):
217:     is_bot = '--bot' in sys.argv
218:     target_name = 'complete_bot.png' if is_bot else 'complete.png'
219:     print(f"[CleanOnly] เริ่มต้น... (target: {target_name})")
220:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
221:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
222:     img = crop_watermark(source)
223:     if img:
224:         img.save(target, format='PNG')
225:         print(f"[Done] {target}")
226:     else:
227:         print("[Error] Failed")
228: 
229: def _upload_with_timeout(file_path, timeout_sec=30):
230:     """Upload ไปที่ Litterbox โดยมี timeout ที่แน่นอน ผ่าน threading"""
231:     import threading
232:     result = [None]
233:     
234:     def _do_upload():
235:         result[0] = upload_litterbox_24h(file_path)
236:     
237:     t = threading.Thread(target=_do_upload, daemon=True)
238:     start = time.time()
239:     t.start()
240:     t.join(timeout=timeout_sec)
241:     elapsed = time.time() - start
242:     
243:     if t.is_alive():
244:         print(f"[Donate] Upload timeout! ({elapsed:.1f}s > {timeout_sec}s) → fallback to no-upload mode")
245:         return None
246:     
247:     if result[0]:
248:         print(f"[Donate] Upload สำเร็จใน {elapsed:.1f}s")
249:     else:
250:         print(f"[Donate] Upload ล้มเหลวใน {elapsed:.1f}s → fallback to no-upload mode")
251:     return result[0]
252: 
253: def process_donate(full_path=None):
254:     is_bot = '--bot' in sys.argv
255:     target_name = 'complete_bot.png' if is_bot else 'complete.png'
256:     print(f"[Donate] เริ่มต้น... (target: {target_name})")
257:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
258:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
259:     
260:     original_img = crop_watermark(source)
261:     if not original_img: return
262: 
263:     # // ส่วนนี้ถูก bypass ทั้งหมด — upload littlebox + สร้าง QR + แถบ QR
264:     # // คอมเมนต์ไว้เพื่อกู้คืนได้ในอนาคต ไม่ได้ลบทิ้ง
265: 
266:     # temp_path = os.path.join(tempfile.gettempdir(), 'ps_cropped_temp.png')
267:     # original_img.save(temp_path, format='PNG')
268:     # poisoned = scrub_and_poison(temp_path)
269:     # upload_url = _upload_with_timeout(poisoned, timeout_sec=30)
270:     upload_url = None  # bypass: ข้ามการ upload ทั้งหมด
271: 
272:     # if upload_url:
273:     #     b64_url = base64.b64encode(upload_url.encode()).decode()
274:     #     expiry = int((time.time() + 86400) * 1000)
275:     #     donate_link = f"https://artnp.github.io/eworker/download.html?d={b64_url}&exp={expiry}&type=img&donate=1"
276:     #     preview_img = original_img.copy()
277:     #     w, h = preview_img.size
278:     #     final_img = preview_img
279:     #     final_h = h
280:     #     scale = max(0.65, min(w / 850.0, 3.0))
281:     #     qr_size = int(145 * scale)
282:     #     qr_img = generate_qr_image(donate_link, size=qr_size).convert("RGBA")
283:     #     overlay_w, overlay_h = int(540 * scale), int(175 * scale)
284:     #     margin, radius = int(22 * scale), int(24 * scale)
285:     #     shadow_pad = int(12 * scale)
286:     #     # Fonts
287:     #     font = None
288:     #     small_font = None
289:     #     for fp in ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf"]:
290:     #         if os.path.exists(fp):
291:     #             font = ImageFont.truetype(fp, int(22 * scale))
292:     #             small_font = ImageFont.truetype(fp, int(16 * scale))
293:     #             break
294:     #     if not font:
295:     #         font = ImageFont.load_default()
296:     #         small_font = ImageFont.load_default()
297:     #     # สร้าง Overlay และ Shadow
298:     #     shadow_img = Image.new('RGBA', (overlay_w + shadow_pad*2, overlay_h + shadow_pad*2), (0,0,0,0))
299:     #     shadow_draw = ImageDraw.Draw(shadow_img)
300:     #     shadow_draw.rounded_rectangle((shadow_pad, shadow_pad, overlay_w + shadow_pad, overlay_h + shadow_pad), radius=radius, fill=(0, 0, 0, 60))
301:     #     shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(10 * scale)))
302:     #     # Supersampling
303:     #     aa_scale = 3
304:     #     aa_img = Image.new('RGBA', (overlay_w * aa_scale, overlay_h * aa_scale), (0,0,0,0))
305:     #     aa_draw = ImageDraw.Draw(aa_img)
306:     #     import math
307:     #     aw = (overlay_w * aa_scale) - 1
308:     #     ah = (overlay_h * aa_scale) - 1
309:     #     ar = radius * aa_scale
310:     #     aa_draw.rounded_rectangle((0, 0, aw, ah), radius=ar, fill=(255, 255, 255, 248))
311:     #     def get_rrect_point(p, w, h, r):
312:     #         seg_horiz = w - 2*r
313:     #         seg_vert = h - 2*r
314:     #         arc_len = math.pi * r / 2
315:     #         if p <= seg_horiz: return (r + p, 0)
316:     #         p -= seg_horiz
317:     #         if p <= arc_len:
318:     #             angle = -math.pi/2 + (p / arc_len) * (math.pi/2)
319:     #             return (w - r + r * math.cos(angle), r + r * math.sin(angle))
320:     #         p -= arc_len
321:     #         if p <= seg_vert: return (w, r + p)
322:     #         p -= seg_vert
323:     #         if p <= arc_len:
324:     #             angle = (p / arc_len) * (math.pi/2)
325:     #             return (w - r + r * math.cos(angle), h - r + r * math.sin(angle))
326:     #         p -= arc_len
327:     #         if p <= seg_horiz: return (w - r - p, h)
328:     #         p -= seg_horiz
329:     #         if p <= arc_len:
330:     #             angle = math.pi/2 + (p / arc_len) * (math.pi/2)
331:     #             return (r + r * math.cos(angle), h - r + r * math.sin(angle))
332:     #         p -= arc_len
333:     #         if p <= seg_vert: return (0, h - r - p)
334:     #         p -= seg_vert
335:     #         if p <= arc_len:
336:     #             angle = math.pi + (p / arc_len) * (math.pi/2)
337:     #             return (r + r * math.cos(angle), r + r * math.sin(angle))
338:     #         return (r, 0)
339:     #     perimeter = 2 * (aw - 2 * ar) + 2 * (ah - 2 * ar) + 2 * math.pi * ar
340:     #     dash_len = 20 * aa_scale * scale
341:     #     gap_len = 14 * aa_scale * scale
342:     #     dash_total = dash_len + gap_len
343:     #     num_dashes = max(1, int(perimeter / dash_total))
344:     #     actual_dash_total = perimeter / num_dashes
345:     #     ratio = actual_dash_total / dash_total
346:     #     actual_dash = dash_len * ratio
347:     #     samples = int(perimeter)
348:     #     border_color = '#f97316'
349:     #     outline_w = max(2, int(3.0 * scale))
350:     #     draw_width = outline_w * aa_scale
351:     #     last_pt = None
352:     #     for i in range(samples + 1):
353:     #         dist = (i / samples) * perimeter
354:     #         pt = get_rrect_point(dist, aw, ah, ar)
355:     #         if (dist % actual_dash_total) <= actual_dash:
356:     #             if last_pt:
357:     #                 aa_draw.line([last_pt, pt], fill=border_color, width=draw_width)
358:     #             last_pt = pt
359:     #         else:
360:     #             last_pt = None
361:     #     overlay_img = aa_img.resize((overlay_w, overlay_h), Image.Resampling.LANCZOS)
362:     #     overlay_draw = ImageDraw.Draw(overlay_img)
363:     #     qr_x, qr_y = int(15 * scale), int(15 * scale)
364:     #     overlay_img.paste(qr_img, (qr_x, qr_y))
365:     #     text_x = qr_x + qr_size + int(22 * scale)
366:     #     text_y = qr_y + int(4 * scale)
367:     #     overlay_draw.text((text_x, text_y), ":) โปรเจคการกุศลช่วยเหลือฟรี", fill='#059669', font=font)
368:     #     overlay_draw.text((text_x, text_y + int(36 * scale)), "สแกน QR code !!", fill='#0f172a', font=font)
369:     #     overlay_draw.text((text_x, text_y + int(64 * scale)), "ดาวน์โหลดภาพเต็มชัดแจ๋ว-ไฟล์ไม่แตก!", fill='#0f172a', font=font)
370:     #     dash_length = max(1, int(6 * scale))
371:     #     dash_gap = max(1, int(4 * scale))
372:     #     line_y = text_y + int(92 * scale)
373:     #     line_start_x = text_x
374:     #     line_end_x = overlay_w - int(20 * scale)
375:     #     for cx in range(line_start_x, line_end_x, dash_length + dash_gap):
376:     #         end_x = min(cx + dash_length, line_end_x)
377:     #         overlay_draw.line([(cx, line_y), (end_x, line_y)], fill='#f97316', width=max(1, int(1.5 * scale)))
378:     #     overlay_draw.text((text_x, text_y + int(106 * scale)), "> อยากจ้างตัดต่อส่วนตัว 60฿ | ทักแชทมาได้เลย", fill='#64748b', font=small_font)
379:     #     pos_x = margin
380:     #     pos_y = final_h - overlay_h - margin
381:     #     rgba_final = final_img.convert('RGBA')
382:     #     rgba_final.paste(shadow_img, (pos_x - shadow_pad, pos_y - shadow_pad + int(4 * scale)), shadow_img)
383:     #     rgba_final.paste(overlay_img, (pos_x, pos_y), overlay_img)
384:     #     final_export = rgba_final.convert('RGB')
385:     # else:
386:     # === โหมดไม่อัพโหลด: ลบลายน้ำ + กรอบเขียว + แบนเนอร์หัวภาพ ===
387:     print("[Donate] → bypass mode: ลบลายน้ำ + กรอบเขียว + แบนเนอร์หัว (ไม่ upload / ไม่ QR)")
388:     base_img = original_img.copy().convert('RGB')
389:     fw, fh = base_img.size
390: 
391:     # --- Scale factor ตามความกว้างภาพ ---
392:     scale = max(0.8, min(fw / 400.0, 3.0))
393: 
394:     # --- โหลด Font ---
395:     font_large = None
396:     font_small = None
397:     font_bold = None
398:     font_paths = [
399:         "C:/Windows/Fonts/tahoma.ttf",
400:         "C:/Windows/Fonts/Tahoma.ttf",
401:         "C:/Windows/Fonts/arial.ttf",
402:         "C:/Windows/Fonts/Arial.ttf",
403:         "C:/Windows/Fonts/segoeui.ttf",
404:         "C:/Windows/Fonts/Segoeui.ttf",
405:     ]
406:     font_bold_paths = [
407:         "C:/Windows/Fonts/tahomabd.ttf",
408:         "C:/Windows/Fonts/arialbd.ttf",
409:         "C:/Windows/Fonts/Arialbd.ttf",
410:         "C:/Windows/Fonts/segoeuib.ttf",
411:     ]
412:     sz_large = int(20 * scale)
413:     sz_small = int(13 * scale)
414:     sz_bold = int(22 * scale)
415: 
416:     for fp in font_bold_paths:
417:         if os.path.exists(fp):
418:             try:
419:                 font_bold = ImageFont.truetype(fp, sz_bold)
420:                 break
421:             except Exception:
422:                 pass
423:     for fp in font_paths:
424:         if os.path.exists(fp):
425:             try:
426:                 font_large = ImageFont.truetype(fp, sz_large)
427:                 font_small = ImageFont.truetype(fp, sz_small)
428:                 break
429:             except Exception:
430:                 pass
431:     if not font_bold:
432:         font_bold = font_large or ImageFont.load_default()
433:     if not font_large:
434:         font_large = ImageFont.load_default()
435:     if not font_small:
436:         font_small = ImageFont.load_default()
437: 
438:     # --- คำนวณความสูงแบนเนอร์ ---
439:     pad_v = int(10 * scale)
440:     pad_h = int(14 * scale)
441:     line_gap = int(5 * scale)
442: 
443:     dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))
444:     txt1 = 'อยากจะแก้ไขบ้าง'
445:     txt2 = 'เพียง 60 ฿'
446:     txt3 = '/ ทำแกมให้หมด ช่วย ๆ กัน / inbox มาแน่ท่าน. /'
447:     h1 = dummy.textbbox((0, 0), txt1, font=font_bold)[3]
448:     h3 = dummy.textbbox((0, 0), txt3, font=font_small)[3]
449:     banner_h = pad_v + h1 + line_gap + h3 + pad_v + int(4 * scale)  # +4 เผื่อเส้นประ
450: 
451:     # --- สร้าง banner RGBA (รองรับ alpha สำหรับ gradient) ---
452:     banner = Image.new('RGBA', (fw, banner_h), (0, 0, 0, 0))
453: 
454:     # Gradient ฟ้าสด → น้ำเงินเข้ม (ซ้าย→ขวา) แบบของเดิม
455:     bd = ImageDraw.Draw(banner)
456:     for x in range(fw):
457:         t = x / max(fw - 1, 1)
458:         r = int(0 * (1 - t) + 0 * t)
459:         g = int(162 * (1 - t) + 98 * t)
460:         b = int(255 * (1 - t) + 230 * t)
461:         bd.line([(x, 0), (x, banner_h - 1)], fill=(r, g, b, 255))
462: 
463:     # --- วาดข้อความ row 1: 💞 อยากจะแก้ไขบ้าง  เพียง 60 ฿ ---
464:     y1 = pad_v
465:     x_text = pad_h
466: 
467:     # วาดหัวใจ (วงกลมสีชมพู-แดง แทน emoji ที่ font ไม่รองรับ)
468:     heart_r = int(10 * scale)
469:     heart_cx = x_text + heart_r
470:     heart_cy = y1 + h1 // 2
471:     bd.ellipse([heart_cx - heart_r, heart_cy - heart_r,
472:                 heart_cx + heart_r, heart_cy + heart_r], fill=(255, 80, 120, 255))
473:     bd.ellipse([heart_cx - heart_r + int(2*scale), heart_cy - heart_r + int(2*scale),
474:                 heart_cx + heart_r - int(2*scale), heart_cy + heart_r - int(2*scale)],
475:                fill=(255, 130, 160, 255))
476:     x_text = heart_cx + heart_r + int(6 * scale)
477: 
478:     # เงาข้อความ row 1 (ออฟเซ็ต 1px)
479:     bd.text((x_text + 1, y1 + 1), txt1, fill=(0, 0, 80, 180), font=font_bold)
480:     bd.text((x_text, y1), txt1, fill=(255, 255, 255, 255), font=font_bold)
481: 
482:     # "เพียง 60 ฿" สีเหลืองสด ต่อท้าย
483:     w1 = dummy.textbbox((0, 0), txt1, font=font_bold)[2]
484:     x_price = x_text + w1 + int(8 * scale)
485: 
486:     # กล่องพื้นหลังสีเหลืองใส
487:     price_bbox = dummy.textbbox((0, 0), txt2, font=font_large)
488:     pw, ph = price_bbox[2], price_bbox[3]
489:     px1 = x_price - int(4 * scale)
490:     py1 = y1 + (h1 - ph) // 2 - int(1 * scale)
491:     px2 = x_price + pw + int(4 * scale)
492:     py2 = y1 + (h1 + ph) // 2 + int(2 * scale)
493:     bd.rounded_rectangle([px1, py1, px2, py2], radius=int(4 * scale), fill=(255, 220, 0, 220))
494:     bd.text((x_price + 1, py1 + 1), txt2, fill=(0, 0, 0, 120), font=font_large)
495:     bd.text((x_price, py1), txt2, fill=(20, 20, 20, 255), font=font_large)
496: 
497:     # --- วาดข้อความ row 2 ---
498:     y2 = y1 + h1 + line_gap
499:     bd.text((pad_h + 1, y2 + 1), txt3, fill=(0, 0, 80, 150), font=font_small)
500:     bd.text((pad_h, y2), txt3, fill=(220, 240, 255, 255), font=font_small)
501: 
502:     # --- ไอคอนกรรไกร ✂ มุมขวาล่างของ banner ---
503:     scissor_r = int(9 * scale)
504:     sx = fw - scissor_r - int(8 * scale)
505:     sy = banner_h - scissor_r - int(6 * scale)
506:     # วงกลมสีแดงเป็น background
507:     bd.ellipse([sx - scissor_r, sy - scissor_r, sx + scissor_r, sy + scissor_r],
508:                fill=(220, 30, 30, 230))
509:     # วาด X ขาว (แทน ✂)
510:     cr = int(5 * scale)
511:     bd.line([sx - cr, sy - cr, sx + cr, sy + cr], fill=(255, 255, 255, 255), width=max(2, int(2 * scale)))
512:     bd.line([sx + cr, sy - cr, sx - cr, sy + cr], fill=(255, 255, 255, 255), width=max(2, int(2 * scale)))
513: 
514:     # --- เส้นประสีเหลืองด้านล่าง banner ---
515:     dash_y = banner_h - int(3 * scale)
516:     dash_len = int(14 * scale)
517:     gap_len = int(7 * scale)
518:     x_pos = 0
519:     while x_pos < fw:
520:         end_x = min(x_pos + dash_len, fw)
521:         bd.line([(x_pos, dash_y), (end_x, dash_y)],
522:                 fill=(255, 220, 0, 255), width=max(2, int(2 * scale)))
523:         x_pos += dash_len + gap_len
524: 
525:     # --- รวม banner (RGBA) + ภาพหลัก ---
526:     banner_rgb = banner.convert('RGB')
527:     combined = Image.new('RGB', (fw, banner_h + fh), (0, 0, 0))
528:     combined.paste(banner_rgb, (0, 0))
529:     combined.paste(base_img, (0, banner_h))
530:     final_export = combined
531: 
532:     # วาดกรอบสี Lime เขียวสด หนา 4px ล้อมรอบทั้งหมด (สวยกว่า)
533:     border_draw = ImageDraw.Draw(final_export)
534:     fw, fh = final_export.size
535:     border_color = "#00FF00"  # Lime สดใส
536:     for i in range(4):
537:         border_draw.rectangle([i, i, fw - 1 - i, fh - 1 - i], outline=border_color, width=1)
538:     
539:     # --- Export เซฟลงเป้าหมายโดยตรง (เขียนทับไฟล์เดิม ห้ามลบ) ---
540:     try:
541:         # ใช้วิธีเขียนทับโดยไม่ลบไฟล์เดิม (เพื่อไม่ให้ไอคอนหาย)
542:         import tempfile
543:         with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
544:             final_export.save(temp_file.name, format='PNG')
545:             temp_path = temp_file.name
546:         
547:         # อ่านข้อมูลจากไฟล์ชั่วคราว
548:         with open(temp_path, 'rb') as temp_f:
549:             data = temp_f.read()
550:         
551:         # เขียนทับไฟล์เป้าหมาย (ไม่ลบก่อน)
552:         with open(target, 'wb') as target_f:
553:             target_f.write(data)
554:         
555:         # ลบไฟล์ชั่วคราว
556:         os.unlink(temp_path)
557:         
558:         print(f"[Done] Overwritten: {target}")
559:         
560:     except Exception as e:
561:         print(f"Error overwriting file: {e}")
562:         # fallback ไปวิธีเดิม
563:         final_export.save(target, format='PNG')
564:     
565:     copy_image_to_clipboard(target)
566:     
567:     # --- ถ้าเป็น --donate-no-paste → bot.js จะจัดการ upload เองผ่าน setInputFiles, ไม่ต้อง auto_paste ---
568:     if '--donate-no-paste' not in sys.argv:
569:         time.sleep(2.0)
570:         auto_paste()
571: 
572: if __name__ == "__main__":
573:     mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
574:     target_path = sys.argv[2] if len(sys.argv) > 2 else None
575:     
576:     if mode_flag == "--clean":
577:         process_clean_only(target_path)
578:     elif mode_flag in ["--donate", "--donate-no-paste"]:
579:         process_donate(target_path)
580:     else:
581:         process_donate()
582: 
The above content shows the entire, complete file contents of the requested file.
