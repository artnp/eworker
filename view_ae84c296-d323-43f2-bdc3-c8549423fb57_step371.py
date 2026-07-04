Created At: 2026-06-14T11:22:06Z
Completed At: 2026-06-14T11:22:06Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 606
Total Bytes: 26355
Showing lines 360 to 430
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
360:     return banner.convert('RGB')
361: 
362: def paste_ad_banner(img):
363:     """แปะแถบโฆษณาบนหัวภาพ"""
364:     w, h = img.size
365:     banner = create_ad_banner(w)
366:     bh = banner.size[1]
367:     
368:     # สร้างภาพใหม่ที่สูงขึ้นเท่ากับ banner
369:     new_img = Image.new('RGB', (w, h + bh))
370:     new_img.paste(banner, (0, 0))
371:     new_img.paste(img, (0, bh))
372:     return new_img
373: 
374: 
375: def process_clean_only(full_path=None):
376:     print("[CleanOnly] เริ่มต้น...")
377:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
378:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'complete.png')
379:     img = crop_watermark(source)
380:     if img:
381:         # hub/dashboard mode: ไม่มีโฆษณา ไม่มีกรอบ แค่ crop watermark
382:         img.save(target, format='PNG')
383:         print(f"[Done] {target}")
384:     else:
385:         print("[Error] Failed")
386: 
387: def _upload_with_timeout(file_path, timeout_sec=30):
388:     """Upload ไปที่ Litterbox โดยมี timeout ที่แน่นอน ผ่าน threading"""
389:     import threading
390:     result = [None]
391:     
392:     def _do_upload():
393:         result[0] = upload_litterbox_24h(file_path)
394:     
395:     t = threading.Thread(target=_do_upload, daemon=True)
396:     start = time.time()
397:     t.start()
398:     t.join(timeout=timeout_sec)
399:     elapsed = time.time() - start
400:     
401:     if t.is_alive():
402:         print(f"[Donate] Upload timeout! ({elapsed:.1f}s > {timeout_sec}s) → fallback to no-upload mode")
403:         return None
404:     
405:     if result[0]:
406:         print(f"[Donate] Upload สำเร็จใน {elapsed:.1f}s")
407:     else:
408:         print(f"[Donate] Upload ล้มเหลวใน {elapsed:.1f}s → fallback to no-upload mode")
409:     return result[0]
410: 
411: def process_donate(full_path=None, no_paste=False):
412:     print("[Donate] เริ่มต้น...")
413:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
414:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'complete.png')
415:     
416:     original_img = crop_watermark(source)
417:     if not original_img: return
418: 
419:     # // ส่วนนี้ถูก bypass ทั้งหมด — upload littlebox + สร้าง QR + แถบ QR
420:     # // คอมเมนต์ไว้เพื่อกู้คืนได้ในอนาคต ไม่ได้ลบทิ้ง
421: 
422:     # temp_path = os.path.join(tempfile.gettempdir(), 'ps_cropped_temp.png')
423:     # original_img.save(temp_path, format='PNG')
424:     # poisoned = scrub_and_poison(temp_path)
425:     # upload_url = _upload_with_timeout(poisoned, timeout_sec=30)
426:     upload_url = None  # bypass: ข้ามการ upload ทั้งหมด
427: 
428:     # if upload_url:
429:     #     b64_url = base64.b64encode(upload_url.encode()).decode()
430:     #     expiry = int((time.time() + 86400) * 1000)
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
