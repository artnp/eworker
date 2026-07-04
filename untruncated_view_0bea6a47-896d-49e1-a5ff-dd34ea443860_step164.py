Created At: 2026-06-14T12:01:36Z
Completed At: 2026-06-14T12:01:37Z
The following changes were made by the replace_file_content tool to: d:\Github\eworker\screenshot_donate.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -203,9 +203,20 @@
         if white_band_h > 0:
             crop_bottom = max(160, white_band_h) + 2
         else:
-            crop_bottom = max(60, int(orig_h * 0.065))
         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
 
+def preprocess_thai_text(text):
+    if not text:
+        return text
+    upper_vowels = {'ิ', 'ี', 'ึ', 'ื'}
+    tone_marks = {'่', '้', '๊', '๋', '็', '์'}
+    result = []
+    for i in range(len(text)):
+        result.append(text[i])
+        if text[i] in upper_vowels and i + 1 < len(text) and text[i+1] in tone_marks:
+            result.append('\u200a')
+    return "".join(result)
+
 def create_ad_banner(width):
     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
     scale = max(0.85, min(width / 900.0, 2.5))
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.