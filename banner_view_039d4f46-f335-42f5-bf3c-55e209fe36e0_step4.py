Created At: 2026-06-16T11:47:10Z
Completed At: 2026-06-16T11:47:10Z
File Path: `file:///d:/Github/eworker/screenshot_donate.py`
Total Lines: 647
Total Bytes: 27903
Showing lines 200 to 647
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
200:         img_rgb = img.convert('RGB')
201:         orig_w, orig_h = img_rgb.size
202:         white_band_h = get_white_band_height(img_rgb)
203:         if white_band_h > 0:
204:             crop_bottom = max(160, white_band_h) + 2
205:         else:
206:             crop_bottom = max(60, int(orig_h * 0.065))
207:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
208: 
209: def preprocess_thai_text(text):
210:     if not text:
211:         return text
212:     upper_vowels = {'ิ', 'ี', 'ึ', 'ื'}
213:     tone_marks = {'่', '้', '๊', '๋', '็', '์'}
214:     result = []
215:     for i in range(len(text)):
216:         result.append(text[i])
217:         if text[i] in upper_vowels and i + 1 < len(text) and text[i+1] in tone_marks:
218:             result.append('\u200a')
219:     return "".join(result)
220: 
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
231:      
<truncated 19364 bytes>
et, 'wb') as f:
609:                 f.write(data)
610:     except Exception as e:
611:         print(f"Error saving file: {e}")
612:     
613:     if no_paste:
614:         print("[Donate] Process only completed. Saved to target/Desktop. Skipped clipboard/pasting.")
615:         return
616: 
617:     copy_image_to_clipboard(target)
618:     
619:     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
620:     time.sleep(2.0)
621:     auto_paste()
622:     
623:     # --- ★ ล้าง Clipboard หลัง Paste เสร็จ เพื่อป้องกัน complete.png หลุดไปวางใน Gemini sidetab ---
624:     time.sleep(1.0)
625:     try:
626:         ps_clear = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'
627:         subprocess.run(
628:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_clear}"',
629:             shell=True, capture_output=True, text=True, timeout=5
630:         )
631:         print("[Clipboard] ✅ Clipboard cleared after paste (prevent Gemini sidetab leak)")
632:     except Exception as e:
633:         print(f"[Clipboard] Clear error (non-critical): {e}")
634: 
635: if __name__ == "__main__":
636:     mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
637:     target_path = sys.argv[2] if len(sys.argv) > 2 else None
638:     
639:     if mode_flag == "--clean":
640:         process_clean_only(target_path)
641:     elif mode_flag == "--donate":
642:         process_donate(target_path)
643:     elif mode_flag == "--donate-no-paste":
644:         process_donate(target_path, no_paste=True)
645:     else:
646:         process_donate()
647: 
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
