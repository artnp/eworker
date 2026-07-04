Created At: 2026-06-14T01:37:48Z
Completed At: 2026-06-14T01:37:48Z
File Path: `file:///D:/Github/eworker/screenshot_donate.py`
Total Lines: 600
Total Bytes: 26110
Showing lines 410 to 600
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
410: 
411: def process_donate(full_path=None):
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
431:     #     donate_link = f"https://artnp.github.io/eworker/download.html?d={b64_url}&exp={expiry}&type=img&donate=1"
432:     #     preview_img = original_img.copy()
433:     #     w, h = preview_img.size
434:     #     final_img = preview_img
435:     #     final_h = h
436:     #     scale = max(0.65, min(w / 850.0, 3.0))
437:     #     qr_size = int(145 * scale)
438:     #     qr_img = generate_qr_image(donate_li
<truncated 7303 bytes>
:     
560:     try:
561:         if os.path.exists(target):
562:             with open(target, 'r+b') as f:
563:                 f.seek(0)
564:                 f.write(data)
565:                 f.truncate()
566:         else:
567:             with open(target, 'wb') as f:
568:                 f.write(data)
569:     except Exception as e:
570:         print(f"Error saving file: {e}")
571:     
572:     copy_image_to_clipboard(target)
573:     
574:     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
575:     time.sleep(2.0)
576:     auto_paste()
577:     
578:     # --- ★ ล้าง Clipboard หลัง Paste เสร็จ เพื่อป้องกัน complete.png หลุดไปวางใน Gemini sidetab ---
579:     time.sleep(1.0)
580:     try:
581:         ps_clear = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'
582:         subprocess.run(
583:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_clear}"',
584:             shell=True, capture_output=True, text=True, timeout=5
585:         )
586:         print("[Clipboard] ✅ Clipboard cleared after paste (prevent Gemini sidetab leak)")
587:     except Exception as e:
588:         print(f"[Clipboard] Clear error (non-critical): {e}")
589: 
590: if __name__ == "__main__":
591:     mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
592:     target_path = sys.argv[2] if len(sys.argv) > 2 else None
593:     
594:     if mode_flag == "--clean":
595:         process_clean_only(target_path)
596:     elif mode_flag == "--donate":
597:         process_donate(target_path)
598:     else:
599:         process_donate()
600: 
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
