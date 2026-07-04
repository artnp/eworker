Created At: 2026-07-03T01:19:35Z
Completed At: 2026-07-03T01:19:35Z
File Path: `file:///d:/Github/eworker/viewed_efac9002-97fd-4faa-af49-bd9b1fcefc5e_step27.py`
Total Lines: 591
Total Bytes: 30289
Showing lines 1 to 591
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: Created At: 2026-07-03T01:16:13Z
2: Completed At: 2026-07-03T01:16:14Z
3: File Path: `file:///d:/Github/eworker/screenshot_donate.py`
4: Total Lines: 582
5: Total Bytes: 26385
6: Showing lines 1 to 582
7: The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
8: 1: import sys
9: 2: import os
10: 3: import subprocess
11: 4: import tempfile
12: 5: import time
13: 6: import random
14: 7: import string
15: 8: import ctypes
16: 9: import ctypes.wintypes
17: 10: import base64
18: 11: 
19: 12: # --- ติดตั้ง dependencies ที่จำเป็นก่อน ---
20: 13: def ensure_deps():
21: 14:     try:
22: 15:         from PIL import Image
23: 16:         import qrcode
24: 17:         import requests
25: 18:         import pyautogui
26: 19:     except ImportError:
27: 20:         subprocess.run([sys.executable, '-m', 'pip', 'install', 'Pillow', 'qrcode[pil]', 'requests', 'pyautogui', '--quiet'], check=True)
28: 21: 
29: 22: ensure_deps()
30: 23: 
31: 24: from PIL import Image, ImageDraw, ImageFont, ImageFilter
32: 25: import qrcode
33: 26: import requests
34: 27: import pyautogui
35: 28: 
36: 29: # ตั้งค่าความเร็วสูงสุด
37: 30: pyautogui.PAUSE = 0
38: 31: pyautogui.FAILSAFE = False
39: 32: 
40: 33: def scrub_and_poison(file_path):
41: 34:     ext = os.path.splitext(file_path)[1].lower()
42: 35:     temp_dir = tempfile.gettempdir()
43: 36:     random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
44: 37:     temp_path = os.path.join(temp_dir, f"donate_{random_name}{ext}")
45: 38:     try:
46: 39:         with Image.open(file_path) as img:
47: 40:             if ext in ['.jpg', '.jpeg'] and img.mode != 'RGB':
48: 41:                 img = img.convert('RGB')
49: 42:             if ext in ['.jpg', '.jpeg']:
50: 43:                 img.save(temp_path, quality=95, subsampling=0)
51: 44:             else:
52: 45:                 img.save(temp_path)
53: 46:         with open(temp_path, 'ab') as f:
54: 47:             random_junk = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
55: 48:             f.write(f"\n#DN_{random_junk}".encode())
56: 49:         return temp_path
57: 50:     except Exception:
58: 51:         return file_path
59: 52: 
60: 53: def upload_litterbox_24h(file_path):
61: 54:     try:
62: 55:         url = 'https://litterbox.catbox.moe/resources/internals/api.php'
63: 56:         with open(file_path, 'rb') as f:
64: 57:             files = {'fileToUpload': f}
65: 58:             data = {'reqtype': 'fileupload', 'time': '24h'}
66: 59:             response = requests.post(url, data=data, files=files, timeout=30)
67: 60:             if response.status_code == 200 and response.text.startswith('http'):
68: 61:                 return response.text.strip()
69: 62:     except Exception as e:
70: 63:         print(f"Upload error: {e}")
71: 64:     return None
72: 65: 
73: 66: def generate_qr_image(data, size=120):
74: 67:     qr = qrcode.QRCode(version=1, box_size=6, border=2)
75: 68:     qr.add_data(data)
76: 69:     qr.make(fit=True)
77: 70:     img = qr.make_image(fill_color="black", back_color="white")
78: 71:     img = img.resize((size, size), Image.LANCZOS)
79: 72:     return img
80: 73: 
81: 74: def copy_image_to_clipboard(file_path):
82: 75:     try:
83: 76:         abs_path = os.path.abspath(file_path).replace('/', '\\')
84: 77:         ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; $img = [System.Drawing.Image]::FromFile('{abs_path}'); [System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose()"
85: 78:         result = subprocess.run(
86: 79:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_cmd}"',
87: 80:             shell=True, capture_output=True, text=True
88: 81:         )
89: 82:         if result.returncode != 0:
90: 83:             print(f"[Clipboard] PowerShell error: {result.stderr}")
91: 84:         else:
92: 85:             print(f"[Clipboard] Image copied to clipboard OK")
93: 86:     except Exception as e:
94: 87:         print(f"[Clipboard] Error: {e}")
95: 88: 
96: 89: def auto_paste():
97: 90:     try:
98: 91:         user32 = ctypes.windll.user32
99: 92:         EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
100: 93: 
101: 94:         def _get_title(hwnd):
102: 95:             length = user32.GetWindowTextLengthW(hwnd)
103: 96:             if length <= 0: return ""
104: 97:             buf = ctypes.create_unicode_buffer(length + 1)
105: 98:             user32.GetWindowTextW(hwnd, buf, length + 1)
106: 99:             return buf.value
107: 100: 
108: 101:         def _find_window_by_keywords(keywords):
109: 102:             matches = []
110: 103:             @EnumWindowsProc
111: 104:             def _enum(hwnd, lparam):
112: 105:                 title = _get_title(hwnd)
113: 106:                 if not title: return True
114: 107:                 title_lower = title.lower()
115: 108:                 for kw in keywords:
116: 109:                     if kw.lower() in title_lower:
117: 110:                         matches.append((hwnd, title))
118: 111:                         break
119: 112:                 return True
120: 113:             user32.EnumWindows(_enum, 0)
121: 114:             return matches
122: 115: 
123: 116:         def _force_foreground(hwnd):
124: 117:             user32.ShowWindow(hwnd, 9)
125: 118:             user32.SetForegroundWindow(hwnd)
126: 119:             return True
127: 120: 
128: 121:         def _parse_coords(title):
129: 122:             try:
130: 123:                 import re
131: 124:                 if 'READY_TO_PASTE|' in title:
132: 125:                     pattern = r'READY_TO_PASTE\|([\d\.]+)\|([\d\.]+)'
133: 126:                     match = re.search(pattern, title)
134: 127:                     if match:
135: 128:                         return int(float(match.group(1))), int(float(match.group(2)))
136: 129:                 return None
137: 130:             except: return None
138: 131: 
139: 132:         print("[System] Mouse control sequence ACTIVATED.")
140: 133:         target_hwnd, coords = None, None
141: 134:         
142: 135:         for i in range(300):
143: 136:             wins = _find_window_by_keywords(['READY_TO_PASTE', 'READY_TO_POST'])
144: 137:             if wins:
145: 138:                 for h, t in wins:
146: 139:                     c = _parse_coords(t)
147: 140:                     if c:
148: 141:                         target_hwnd, coords = h, c
149: 142:                         pyautogui.moveTo(c[0], c[1], duration=0)
150: 143:                         pyautogui.click()
151: 144:                         break
152: 145:                 if target_hwnd: break
153: 146:             time.sleep(0.1)
154: 147: 
155: 148:         if not target_hwnd:
156: 149:             print("[Fail] Handshake Timeout.")
157: 150:             return
158: 151:         
159: 152:         _force_foreground(target_hwnd)
160: 153:         time.sleep(0.5)
161: 154:         pyautogui.hotkey('ctrl', 'v')
162: 155:         
163: 156:         for _ in range(40):
164: 157:             wins = _find_window_by_keywords(['READY_TO_POST'])
165: 158:             if wins:
166: 159:                 _force_foreground(wins[0][0])
167: 160:                 time.sleep(0.6)
168: 161:                 pyautogui.press('enter')
169: 162:                 break
170: 163:             time.sleep(0.5)
171: 164: 
172: 165:         print("[AutoPaste] Sequence finished.")
173: 166:     except Exception as e:
174: 167:         print(f"[AutoPaste] Error: {e}")
175: 168: 
176: 169: def get_white_band_height(img):
177: 170:     w, h = img.size
178: 171:     img_rgb = img.convert('RGB')
179: 172:     
180: 173:     # เริ่มสแกนจากด้านล่างขึ้นไป หาจุดที่ไม่ใช่สีขาว
181: 174:     for y in range(h - 1, max(0, h - int(h * 0.5)), -1):  # สแกนมากขึ้น (50% แทน 40%)
182: 175:         white_count = 0
183: 176:         samples = 30  # เพิ่มจำนวน sample points
184: 177:         for i in range(samples):
185: 178:             x = int((i / samples) * (w * 0.9))  # ครอบคลุมพื้นที่มากขึ้น (90% แทน 75%)
186: 179:             r, g, b = img_rgb.getpixel((x, y))
187: 180:             # ใช้เกณฑ์เข้มงวดขึ้นสำหรับสีขาว (220 แทน 190)
188: 181:             if r > 220 and g > 220 and b > 220: 
189: 182:                 white_count += 1
190: 183:         
191: 184:         # ถ้าไม่ใช่พื้นที่สีขาวส่วนใหญ่ (70% แทน 80%)
192: 185:         if white_count < samples * 0.7:
193: 186:             detected = h - y
194: 187:             # เพิ่มการตัดขั้นต่ำ (40px แทน 20px)
195: 188:             if detected >= 40: 
196: 189:                 return detected + 20  # เพิ่ม buffer 20px
197: 190:             else: 
198: 191:                 return 60  # minimum cut 60px
199: 192:     
200: 193:     # กรณี fallback ตัดมากขึ้น (10% แทน 6.5%)
201: 194:     return int(h * 0.1)
202: 195: 
203: 196: def crop_watermark(source_path):
204: 197:     if not os.path.exists(source_path):
205: 198:         print(f"ไม่พบไฟล์: {source_path}")
206: 199:         return None
207: 200:     with Image.open(source_path) as img:
208: 201:         img_rgb = img.convert('RGB')
209: 202:         orig_w, orig_h = img_rgb.size
210: 203:         white_band_h = get_white_band_height(img_rgb)
211: 204:         
212: 205:         # *** แก้: ลบพื้นที่ขาวจริงๆ ไม่เพิ่ม ***
213: 206:         if white_band_h > 0:
214: 207:             # ตัดตามที่ detect ได้จริงๆ + เล็กน้อย buffer
215: 208:             crop_bottom = white_band_h + 10
216: 209:         else:
217: 210:             # ถ้า detect ไม่เจอ ก็ตัดน้อยลง (ไม่ใช่มากกว่า)
218: 211:             crop_bottom = int(orig_h * 0.08)  # ประมาณ 8% เท่านั้น
219: 212:         
220: 213:         print(f"[Crop] white_band_h={white_band_h}px, crop_bottom={crop_bottom}px, original_h={orig_h}px")
221: 214:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
222: 215: 
223: 216: def process_clean_only(full_path=None):
224: 217:     is_bot = '--bot' in sys.argv
225: 218:     target_name = 'complete_bot.png' if is_bot else 'complete.png'
226: 219:     print(f"[CleanOnly] เริ่มต้น... (target: {target_name})")
227: 220:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
228: 221:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
229: 222:     img = crop_watermark(source)
230: 223:     if img:
231: 224:         img.save(target, format='PNG')
232: 225:         print(f"[Done] {target}")
233: 226:     else:
234: 227:         print("[Error] Failed")
235: 228: 
236: 229: def _upload_with_timeout(file_path, timeout_sec=30):
237: 230:     """Upload ไปที่ Litterbox โดยมี timeout ที่แน่นอน ผ่าน threading"""
238: 231:     import threading
239: 232:     result = [None]
240: 233:     
241: 234:     def _do_upload():
242: 235:         result[0] = upload_litterbox_24h(file_path)
243: 236:     
244: 237:     t = threading.Thread(target=_do_upload, daemon=True)
245: 238:     start = time.time()
246: 239:     t.start()
247: 240:     t.join(timeout=timeout_sec)
248: 241:     elapsed = time.time() - start
249: 242:     
250: 243:     if t.is_alive():
251: 244:         print(f"[Donate] Upload timeout! ({elapsed:.1f}s > {timeout_sec}s) → fallback to no-upload mode")
252: 245:         return None
253: 246:     
254: 247:     if result[0]:
255: 248:         print(f"[Donate] Upload สำเร็จใน {elapsed:.1f}s")
256: 249:     else:
257: 250:         print(f"[Donate] Upload ล้มเหลวใน {elapsed:.1f}s → fallback to no-upload mode")
258: 251:     return result[0]
259: 252: 
260: 253: def process_donate(full_path=None):
261: 254:     is_bot = '--bot' in sys.argv
262: 255:     target_name = 'complete_bot.png' if is_bot else 'complete.png'
263: 256:     print(f"[Donate] เริ่มต้น... (target: {target_name})")
264: 257:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
265: 258:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
266: 259:     
267: 260:     original_img = crop_watermark(source)
268: 261:     if not original_img: return
269: 262: 
270: 263:     # // ส่วนนี้ถูก bypass ทั้งหมด — upload littlebox + สร้าง QR + แถบ QR
271: 264:     # // คอมเมนต์ไว้เพื่อกู้คืนได้ในอนาคต ไม่ได้ลบทิ้ง
272: 265: 
273: 266:     # temp_path = os.path.join(tempfile.gettempdir(), 'ps_cropped_temp.png')
274: 267:     # original_img.save(temp_path, format='PNG')
275: 268:     # poisoned = scrub_and_poison(temp_path)
276: 269:     # upload_url = _upload_with_timeout(poisoned, timeout_sec=30)
277: 270:     upload_url = None  # bypass: ข้ามการ upload ทั้งหมด
278: 271: 
279: 272:     # if upload_url:
280: 273:     #     b64_url = base64.b64encode(upload_url.encode()).decode()
281: 274:     #     expiry = int((time.time() + 86400) * 1000)
282: 275:     #     donate_link = f"https://artnp.github.io/eworker/download.html?d={b64_url}&exp={expiry}&type=img&donate=1"
283: 276:     #     preview_img = original_img.copy()
284: 277:     #     w, h = preview_img.size
285: 278:     #     final_img = preview_img
286: 279:     #     final_h = h
287: 280:     #     scale = max(0.65, min(w / 850.0, 3.0))
288: 281:     #     qr_size = int(145 * scale)
289: 282:     #     qr_img = generate_qr_image(donate_link, size=qr_size).convert("RGBA")
290: 283:     #     overlay_w, overlay_h = int(540 * scale), int(175 * scale)
291: 284:     #     margin, radius = int(22 * scale), int(24 * scale)
292: 285:     #     shadow_pad = int(12 * scale)
293: 286:     #     # Fonts
294: 287:     #     font = None
295: 288:     #     small_font = None
296: 289:     #     for fp in ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf"]:
297: 290:     #         if os.path.exists(fp):
298: 291:     #             font = ImageFont.truetype(fp, int(22 * scale))
299: 292:     #             small_font = ImageFont.truetype(fp, int(16 * scale))
300: 293:     #             break
301: 294:     #     if not font:
302: 295:     #         font = ImageFont.load_default()
303: 296:     #         small_font = ImageFont.load_default()
304: 297:     #     # สร้าง Overlay และ Shadow
305: 298:     #     shadow_img = Image.new('RGBA', (overlay_w + shadow_pad*2, overlay_h + shadow_pad*2), (0,0,0,0))
306: 299:     #     shadow_draw = ImageDraw.Draw(shadow_img)
307: 300:     #     shadow_draw.rounded_rectangle((shadow_pad, shadow_pad, overlay_w + shadow_pad, overlay_h + shadow_pad), radius=radius, fill=(0, 0, 0, 60))
308: 301:     #     shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(10 * scale)))
309: 302:     #     # Supersampling
310: 303:     #     aa_scale = 3
311: 304:     #     aa_img = Image.new('RGBA', (overlay_w * aa_scale, overlay_h * aa_scale), (0,0,0,0))
312: 305:     #     aa_draw = ImageDraw.Draw(aa_img)
313: 306:     #     import math
314: 307:     #     aw = (overlay_w * aa_scale) - 1
315: 308:     #     ah = (overlay_h * aa_scale) - 1
316: 309:     #     ar = radius * aa_scale
317: 310:     #     aa_draw.rounded_rectangle((0, 0, aw, ah), radius=ar, fill=(255, 255, 255, 248))
318: 311:     #     def get_rrect_point(p, w, h, r):
319: 312:     #         seg_horiz = w - 2*r
320: 313:     #         seg_vert = h - 2*r
321: 314:     #         arc_len = math.pi * r / 2
322: 315:     #         if p <= seg_horiz: return (r + p, 0)
323: 316:     #         p -= seg_horiz
324: 317:     #         if p <= arc_len:
325: 318:     #             angle = -math.pi/2 + (p / arc_len) * (math.pi/2)
326: 319:     #             return (w - r + r * math.cos(angle), r + r * math.sin(angle))
327: 320:     #         p -= arc_len
328: 321:     #         if p <= seg_vert: return (w, r + p)
329: 322:     #         p -= seg_vert
330: 323:     #         if p <= arc_len:
331: 324:     #             angle = (p / arc_len) * (math.pi/2)
332: 325:     #             return (w - r + r * math.cos(angle), h - r + r * math.sin(angle))
333: 326:     #         p -= arc_len
334: 327:     #         if p <= seg_horiz: return (w - r - p, h)
335: 328:     #         p -= seg_horiz
336: 329:     #         if p <= arc_len:
337: 330:     #             angle = math.pi/2 + (p / arc_len) * (math.pi/2)
338: 331:     #             return (r + r * math.cos(angle), h - r + r * math.sin(angle))
339: 332:     #         p -= arc_len
340: 333:     #         if p <= seg_vert: return (0, h - r - p)
341: 334:     #         p -= seg_vert
342: 335:     #         if p <= arc_len:
343: 336:     #             angle = math.pi + (p / arc_len) * (math.pi/2)
344: 337:     #             return (r + r * math.cos(angle), r + r * math.sin(angle))
345: 338:     #         return (r, 0)
346: 339:     #     perimeter = 2 * (aw - 2 * ar) + 2 * (ah - 2 * ar) + 2 * math.pi * ar
347: 340:     #     dash_len = 20 * aa_scale * scale
348: 341:     #     gap_len = 14 * aa_scale * scale
349: 342:     #     dash_total = dash_len + gap_len
350: 343:     #     num_dashes = max(1, int(perimeter / dash_total))
351: 344:     #     actual_dash_total = perimeter / num_dashes
352: 345:     #     ratio = actual_dash_total / dash_total
353: 346:     #     actual_dash = dash_len * ratio
354: 347:     #     samples = int(perimeter)
355: 348:     #     border_color = '#f97316'
356: 349:     #     outline_w = max(2, int(3.0 * scale))
357: 350:     #     draw_width = outline_w * aa_scale
358: 351:     #     last_pt = None
359: 352:     #     for i in range(samples + 1):
360: 353:     #         dist = (i / samples) * perimeter
361: 354:     #         pt = get_rrect_point(dist, aw, ah, ar)
362: 355:     #         if (dist % actual_dash_total) <= actual_dash:
363: 356:     #             if last_pt:
364: 357:     #                 aa_draw.line([last_pt, pt], fill=border_color, width=draw_width)
365: 358:     #             last_pt = pt
366: 359:     #         else:
367: 360:     #             last_pt = None
368: 361:     #     overlay_img = aa_img.resize((overlay_w, overlay_h), Image.Resampling.LANCZOS)
369: 362:     #     overlay_draw = ImageDraw.Draw(overlay_img)
370: 363:     #     qr_x, qr_y = int(15 * scale), int(15 * scale)
371: 364:     #     overlay_img.paste(qr_img, (qr_x, qr_y))
372: 365:     #     text_x = qr_x + qr_size + int(22 * scale)
373: 366:     #     text_y = qr_y + int(4 * scale)
374: 367:     #     overlay_draw.text((text_x, text_y), ":) โปรเจคการกุศลช่วยเหลือฟรี", fill='#059669', font=font)
375: 368:     #     overlay_draw.text((text_x, text_y + int(36 * scale)), "สแกน QR code !!", fill='#0f172a', font=font)
376: 369:     #     overlay_draw.text((text_x, text_y + int(64 * scale)), "ดาวน์โหลดภาพเต็มชัดแจ๋ว-ไฟล์ไม่แตก!", fill='#0f172a', font=font)
377: 370:     #     dash_length = max(1, int(6 * scale))
378: 371:     #     dash_gap = max(1, int(4 * scale))
379: 372:     #     line_y = text_y + int(92 * scale)
380: 373:     #     line_start_x = text_x
381: 374:     #     line_end_x = overlay_w - int(20 * scale)
382: 375:     #     for cx in range(line_start_x, line_end_x, dash_length + dash_gap):
383: 376:     #         end_x = min(cx + dash_length, line_end_x)
384: 377:     #         overlay_draw.line([(cx, line_y), (end_x, line_y)], fill='#f97316', width=max(1, int(1.5 * scale)))
385: 378:     #     overlay_draw.text((text_x, text_y + int(106 * scale)), "> อยากจ้างตัดต่อส่วนตัว 60฿ | ทักแชทมาได้เลย", fill='#64748b', font=small_font)
386: 379:     #     pos_x = margin
387: 380:     #     pos_y = final_h - overlay_h - margin
388: 381:     #     rgba_final = final_img.convert('RGBA')
389: 382:     #     rgba_final.paste(shadow_img, (pos_x - shadow_pad, pos_y - shadow_pad + int(4 * scale)), shadow_img)
390: 383:     #     rgba_final.paste(overlay_img, (pos_x, pos_y), overlay_img)
391: 384:     #     final_export = rgba_final.convert('RGB')
392: 385:     # else:
393: 386:     # === โหมดไม่อัพโหลด: ลบลายน้ำ + กรอบเขียว + แบนเนอร์หัวภาพ ===
394: 387:     print("[Donate] → bypass mode: ลบลายน้ำ + กรอบเขียว + แบนเนอร์หัว (ไม่ upload / ไม่ QR)")
395: 388:     base_img = original_img.copy().convert('RGB')
396: 389:     fw, fh = base_img.size
397: 390: 
398: 391:     # --- Scale factor ตามความกว้างภาพ ---
399: 392:     scale = max(0.8, min(fw / 400.0, 3.0))
400: 393: 
401: 394:     # --- โหลด Font ---
402: 395:     font_large = None
403: 396:     font_small = None
404: 397:     font_bold = None
405: 398:     font_paths = [
406: 399:         "C:/Windows/Fonts/tahoma.ttf",
407: 400:         "C:/Windows/Fonts/Tahoma.ttf",
408: 401:         "C:/Windows/Fonts/arial.ttf",
409: 402:         "C:/Windows/Fonts/Arial.ttf",
410: 403:         "C:/Windows/Fonts/segoeui.ttf",
411: 404:         "C:/Windows/Fonts/Segoeui.ttf",
412: 405:     ]
413: 406:     font_bold_paths = [
414: 407:         "C:/Windows/Fonts/tahomabd.ttf",
415: 408:         "C:/Windows/Fonts/arialbd.ttf",
416: 409:         "C:/Windows/Fonts/Arialbd.ttf",
417: 410:         "C:/Windows/Fonts/segoeuib.ttf",
418: 411:     ]
419: 412:     sz_large = int(20 * scale)
420: 413:     sz_small = int(13 * scale)
421: 414:     sz_bold = int(22 * scale)
422: 415: 
423: 416:     for fp in font_bold_paths:
424: 417:         if os.path.exists(fp):
425: 418:             try:
426: 419:                 font_bold = ImageFont.truetype(fp, sz_bold)
427: 420:                 break
428: 421:             except Exception:
429: 422:                 pass
430: 423:     for fp in font_paths:
431: 424:         if os.path.exists(fp):
432: 425:             try:
433: 426:                 font_large = ImageFont.truetype(fp, sz_large)
434: 427:                 font_small = ImageFont.truetype(fp, sz_small)
435: 428:                 break
436: 429:             except Exception:
437: 430:                 pass
438: 431:     if not font_bold:
439: 432:         font_bold = font_large or ImageFont.load_default()
440: 433:     if not font_large:
441: 434:         font_large = ImageFont.load_default()
442: 435:     if not font_small:
443: 436:         font_small = ImageFont.load_default()
444: 437: 
445: 438:     # --- คำนวณความสูงแบนเนอร์ ---
446: 439:     pad_v = int(10 * scale)
447: 440:     pad_h = int(14 * scale)
448: 441:     line_gap = int(5 * scale)
449: 442: 
450: 443:     dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))
451: 444:     txt1 = 'อยากจะแก้ไขบ้าง'
452: 445:     txt2 = 'เพียง 60 ฿'
453: 446:     txt3 = '/ ทำแกมให้หมด ช่วย ๆ กัน / inbox มาแน่ท่าน. /'
454: 447:     h1 = dummy.textbbox((0, 0), txt1, font=font_bold)[3]
455: 448:     h3 = dummy.textbbox((0, 0), txt3, font=font_small)[3]
456: 449:     banner_h = pad_v + h1 + line_gap + h3 + pad_v + int(4 * scale)  # +4 เผื่อเส้นประ
457: 450: 
458: 451:     # --- สร้าง banner RGBA (รองรับ alpha สำหรับ gradient) ---
459: 452:     banner = Image.new('RGBA', (fw, banner_h), (0, 0, 0, 0))
460: 453: 
461: 454:     # Gradient ฟ้าสด → น้ำเงินเข้ม (ซ้าย→ขวา) แบบของเดิม
462: 455:     bd = ImageDraw.Draw(banner)
463: 456:     for x in range(fw):
464: 457:         t = x / max(fw - 1, 1)
465: 458:         r = int(0 * (1 - t) + 0 * t)
466: 459:         g = int(162 * (1 - t) + 98 * t)
467: 460:         b = int(255 * (1 - t) + 230 * t)
468: 461:         bd.line([(x, 0), (x, banner_h - 1)], fill=(r, g, b, 255))
469: 462: 
470: 463:     # --- วาดข้อความ row 1: 💞 อยากจะแก้ไขบ้าง  เพียง 60 ฿ ---
471: 464:     y1 = pad_v
472: 465:     x_text = pad_h
473: 466: 
474: 467:     # วาดหัวใจ (วงกลมสีชมพู-แดง แทน emoji ที่ font ไม่รองรับ)
475: 468:     heart_r = int(10 * scale)
476: 469:     heart_cx = x_text + heart_r
477: 470:     heart_cy = y1 + h1 // 2
478: 471:     bd.ellipse([heart_cx - heart_r, heart_cy - heart_r,
479: 472:                 heart_cx + heart_r, heart_cy + heart_r], fill=(255, 80, 120, 255))
480: 473:     bd.ellipse([heart_cx - heart_r + int(2*scale), heart_cy - heart_r + int(2*scale),
481: 474:                 heart_cx + heart_r - int(2*scale), heart_cy + heart_r - int(2*scale)],
482: 475:                fill=(255, 130, 160, 255))
483: 476:     x_text = heart_cx + heart_r + int(6 * scale)
484: 477: 
485: 478:     # เงาข้อความ row 1 (ออฟเซ็ต 1px)
486: 479:     bd.text((x_text + 1, y1 + 1), txt1, fill=(0, 0, 80, 180), font=font_bold)
487: 480:     bd.text((x_text, y1), txt1, fill=(255, 255, 255, 255), font=font_bold)
488: 481: 
489: 482:     # "เพียง 60 ฿" สีเหลืองสด ต่อท้าย
490: 483:     w1 = dummy.textbbox((0, 0), txt1, font=font_bold)[2]
491: 484:     x_price = x_text + w1 + int(8 * scale)
492: 485: 
493: 486:     # กล่องพื้นหลังสีเหลืองใส
494: 487:     price_bbox = dummy.textbbox((0, 0), txt2, font=font_large)
495: 488:     pw, ph = price_bbox[2], price_bbox[3]
496: 489:     px1 = x_price - int(4 * scale)
497: 490:     py1 = y1 + (h1 - ph) // 2 - int(1 * scale)
498: 491:     px2 = x_price + pw + int(4 * scale)
499: 492:     py2 = y1 + (h1 + ph) // 2 + int(2 * scale)
500: 493:     bd.rounded_rectangle([px1, py1, px2, py2], radius=int(4 * scale), fill=(255, 220, 0, 220))
501: 494:     bd.text((x_price + 1, py1 + 1), txt2, fill=(0, 0, 0, 120), font=font_large)
502: 495:     bd.text((x_price, py1), txt2, fill=(20, 20, 20, 255), font=font_large)
503: 496: 
504: 497:     # --- วาดข้อความ row 2 ---
505: 498:     y2 = y1 + h1 + line_gap
506: 499:     bd.text((pad_h + 1, y2 + 1), txt3, fill=(0, 0, 80, 150), font=font_small)
507: 500:     bd.text((pad_h, y2), txt3, fill=(220, 240, 255, 255), font=font_small)
508: 501: 
509: 502:     # --- ไอคอนกรรไกร ✂ มุมขวาล่างของ banner ---
510: 503:     scissor_r = int(9 * scale)
511: 504:     sx = fw - scissor_r - int(8 * scale)
512: 505:     sy = banner_h - scissor_r - int(6 * scale)
513: 506:     # วงกลมสีแดงเป็น background
514: 507:     bd.ellipse([sx - scissor_r, sy - scissor_r, sx + scissor_r, sy + scissor_r],
515: 508:                fill=(220, 30, 30, 230))
516: 509:     # วาด X ขาว (แทน ✂)
517: 510:     cr = int(5 * scale)
518: 511:     bd.line([sx - cr, sy - cr, sx + cr, sy + cr], fill=(255, 255, 255, 255), width=max(2, int(2 * scale)))
519: 512:     bd.line([sx + cr, sy - cr, sx - cr, sy + cr], fill=(255, 255, 255, 255), width=max(2, int(2 * scale)))
520: 513: 
521: 514:     # --- เส้นประสีเหลืองด้านล่าง banner ---
522: 515:     dash_y = banner_h - int(3 * scale)
523: 516:     dash_len = int(14 * scale)
524: 517:     gap_len = int(7 * scale)
525: 518:     x_pos = 0
526: 519:     while x_pos < fw:
527: 520:         end_x = min(x_pos + dash_len, fw)
528: 521:         bd.line([(x_pos, dash_y), (end_x, dash_y)],
529: 522:                 fill=(255, 220, 0, 255), width=max(2, int(2 * scale)))
530: 523:         x_pos += dash_len + gap_len
531: 524: 
532: 525:     # --- รวม banner (RGBA) + ภาพหลัก ---
533: 526:     banner_rgb = banner.convert('RGB')
534: 527:     combined = Image.new('RGB', (fw, banner_h + fh), (0, 0, 0))
535: 528:     combined.paste(banner_rgb, (0, 0))
536: 529:     combined.paste(base_img, (0, banner_h))
537: 530:     final_export = combined
538: 531: 
539: 532:     # วาดกรอบสี Lime เขียวสด หนา 4px ล้อมรอบทั้งหมด (สวยกว่า)
540: 533:     border_draw = ImageDraw.Draw(final_export)
541: 534:     fw, fh = final_export.size
542: 535:     border_color = "#00FF00"  # Lime สดใส
543: 536:     for i in range(4):
544: 537:         border_draw.rectangle([i, i, fw - 1 - i, fh - 1 - i], outline=border_color, width=1)
545: 538:     
546: 539:     # --- Export เซฟลงเป้าหมายโดยตรง (เขียนทับไฟล์เดิม ห้ามลบ) ---
547: 540:     try:
548: 541:         # ใช้วิธีเขียนทับโดยไม่ลบไฟล์เดิม (เพื่อไม่ให้ไอคอนหาย)
549: 542:         import tempfile
550: 543:         with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
551: 544:             final_export.save(temp_file.name, format='PNG')
552: 545:             temp_path = temp_file.name
553: 546:         
554: 547:         # อ่านข้อมูลจากไฟล์ชั่วคราว
555: 548:         with open(temp_path, 'rb') as temp_f:
556: 549:             data = temp_f.read()
557: 550:         
558: 551:         # เขียนทับไฟล์เป้าหมาย (ไม่ลบก่อน)
559: 552:         with open(target, 'wb') as target_f:
560: 553:             target_f.write(data)
561: 554:         
562: 555:         # ลบไฟล์ชั่วคราว
563: 556:         os.unlink(temp_path)
564: 557:         
565: 558:         print(f"[Done] Overwritten: {target}")
566: 559:         
567: 560:     except Exception as e:
568: 561:         print(f"Error overwriting file: {e}")
569: 562:         # fallback ไปวิธีเดิม
570: 563:         final_export.save(target, format='PNG')
571: 564:     
572: 565:     copy_image_to_clipboard(target)
573: 566:     
574: 567:     # --- ถ้าเป็น --donate-no-paste → bot.js จะจัดการ upload เองผ่าน setInputFiles, ไม่ต้อง auto_paste ---
575: 568:     if '--donate-no-paste' not in sys.argv:
576: 569:         time.sleep(2.0)
577: 570:         auto_paste()
578: 571: 
579: 572: if __name__ == "__main__":
580: 573:     mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
581: 574:     target_path = sys.argv[2] if len(sys.argv) > 2 else None
582: 575:     
583: 576:     if mode_flag == "--clean":
584: 577:         process_clean_only(target_path)
585: 578:     elif mode_flag in ["--donate", "--donate-no-paste"]:
586: 579:         process_donate(target_path)
587: 580:     else:
588: 581:         process_donate()
589: 582: 
590: The above content shows the entire, complete file contents of the requested file.
591: 
The above content shows the entire, complete file contents of the requested file.
