Created At: 2026-07-01T11:30:21Z
Completed At: 2026-07-01T11:30:21Z
File Path: `file:///D:/Github/eworker/screenshot_donate.py`
Total Lines: 413
Total Bytes: 17937
Showing lines 220 to 300
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
220:     t = threading.Thread(target=_do_upload, daemon=True)
221:     start = time.time()
222:     t.start()
223:     t.join(timeout=timeout_sec)
224:     elapsed = time.time() - start
225:     
226:     if t.is_alive():
227:         print(f"[Donate] Upload timeout! ({elapsed:.1f}s > {timeout_sec}s) → fallback to no-upload mode")
228:         return None
229:     
230:     if result[0]:
231:         print(f"[Donate] Upload สำเร็จใน {elapsed:.1f}s")
232:     else:
233:         print(f"[Donate] Upload ล้มเหลวใน {elapsed:.1f}s → fallback to no-upload mode")
234:     return result[0]
235: 
236: def process_donate(full_path=None):
237:     is_bot = '--bot' in sys.argv
238:     target_name = 'complete_bot.png' if is_bot else 'complete.png'
239:     print(f"[Donate] เริ่มต้น... (target: {target_name})")
240:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
241:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
242:     
243:     original_img = crop_watermark(source)
244:     if not original_img: return
245: 
246:     # // ส่วนนี้ถูก bypass ทั้งหมด — upload littlebox + สร้าง QR + แถบ QR
247:     # // คอมเมนต์ไว้เพื่อกู้คืนได้ในอนาคต ไม่ได้ลบทิ้ง
248: 
249:     # temp_path = os.path.join(tempfile.gettempdir(), 'ps_cropped_temp.png')
250:     # original_img.save(temp_path, format='PNG')
251:     # poisoned = scrub_and_poison(temp_path)
252:     # upload_url = _upload_with_timeout(poisoned, timeout_sec=30)
253:     upload_url = None  # bypass: ข้ามการ upload ทั้งหมด
254: 
255:     # if upload_url:
256:     #     b64_url = base64.b64encode(upload_url.encode()).decode()
257:     #     expiry = int((time.time() + 86400) * 1000)
258:     #     donate_link = f"https://artnp.github.io/eworker/download.html?d={b64_url}&exp={expiry}&type=img&donate=1"
259:     #     preview_img = original_img.copy()
260:     #     w, h = preview_img.size
261:     #     final_img = preview_img
262:     #     final_h = h
263:     #     scale = max(0.65, min(w / 850.0, 3.0))
264:     #     qr_size = int(145 * scale)
265:     #     qr_img = generate_qr_image(donate_link, size=qr_size).convert("RGBA")
266:     #     overlay_w, overlay_h = int(540 * scale), int(175 * scale)
267:     #     margin, radius = int(22 * scale), int(24 * scale)
268:     #     shadow_pad = int(12 * scale)
269:     #     # Fonts
270:     #     font = None
271:     #     small_font = None
272:     #     for fp in ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf"]:
273:     #         if os.path.exists(fp):
274:     #             font = ImageFont.truetype(fp, int(22 * scale))
275:     #             small_font = ImageFont.truetype(fp, int(16 * scale))
276:     #             break
277:     #     if not font:
278:     #         font = ImageFont.load_default()
279:     #         small_font = ImageFont.load_default()
280:     #     # สร้าง Overlay และ Shadow
281:     #     shadow_img = Image.new('RGBA', (overlay_w + shadow_pad*2, overlay_h + shadow_pad*2), (0,0,0,0))
282:     #     shadow_draw = ImageDraw.Draw(shadow_img)
283:     #     shadow_draw.rounded_rectangle((shadow_pad, shadow_pad, overlay_w + shadow_pad, overlay_h + shadow_pad), radius=radius, fill=(0, 0, 0, 60))
284:     #     shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(10 * scale)))
285:     #     # Supersampling
286:     #     aa_scale = 3
287:     #     aa_img = Image.new('RGBA', (overlay_w * aa_scale, overlay_h * aa_scale), (0,0,0,0))
288:     #     aa_draw = ImageDraw.Draw(aa_img)
289:     #     import math
290:     #     aw = (overlay_w * aa_scale) - 1
291:     #     ah = (overlay_h * aa_scale) - 1
292:     #     ar = radius * aa_scale
293:     #     aa_draw.rounded_rectangle((0, 0, aw, ah), radius=ar, fill=(255, 255, 255, 248))
294:     #     def get_rrect_point(p, w, h, r):
295:     #         seg_horiz = w - 2*r
296:     #         seg_vert = h - 2*r
297:     #         arc_len = math.pi * r / 2
298:     #         if p <= seg_horiz: return (r + p, 0)
299:     #         p -= seg_horiz
300:     #         if p <= arc_len:
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
