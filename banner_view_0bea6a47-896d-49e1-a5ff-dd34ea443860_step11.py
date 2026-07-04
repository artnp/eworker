Created At: 2026-06-14T11:45:29Z
Completed At: 2026-06-14T11:45:31Z
The following changes were made by the replace_file_content tool to: d:\Github\eworker\screenshot_donate.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -209,34 +209,28 @@
 def create_ad_banner(width):
     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
     scale = max(0.85, min(width / 900.0, 2.5))
-    banner_h = int(58 * scale)
-    
-    # สร้างแถบ gradient สีเข้ม (น้ำเงินเข้ม -> ม่วงเข้ม)
-    banner = Image.new('RGBA', (width, banner_h), (15, 23, 42, 255))
+    banner_h = int(95 * scale)
+    
+    # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน)
+    banner = Image.new('RGBA', (width, banner_h), (253, 224, 71, 255))
     draw = ImageDraw.Draw(banner)
     
-    # วาด gradient background
+    # วาด gradient background (จาก Yellow-300: 253, 224, 71 ถึง Yellow-500: 234, 179, 8)
     for x in range(width):
         ratio = x / width
-        r = int(15 + ratio * 50)   # 15 -> 65
-        g = int(23 + ratio * 10)   # 23 -> 33
-        b = int(42 + ratio * 80)   # 42 -> 122
-        draw.line([(x, 0), (x, banner_h)], fill=(r, g, b))
-    
-    # เส้นคั่นสีทองด้านล่าง
-    accent_h = max(3, int(4 * scale))
-    for y in range(banner_h - accent_h, banner_h):
-        for x in range(width):
-            ratio = x / width
-            r2 = int(250 - ratio * 30)
-            g2 = int(204 - ratio * 50)
-            b2 = int(21 + ratio * 40)
-            draw.point((x, y), fill=(r2, g2, b2))
-    
-    # โหลดฟอนต์ 3 ตัว: emoji, ข้อความหลัก, URL
-    emoji_size = int(28 * scale)
+        r = in
<truncated 8881 bytes>
(2 * scale)  # emoji มักสูงกว่า ปรับขึ้นนิด
-            draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
-        else:
-            draw.text((cur_x, text_y), p["text"], fill=p["fill"], font=p["font"])
-        cur_x += part_widths[i]
-    
+        sub_size = s_sz2
+        
+    # จัดกึ่งกลางแนวตั้งสำหรับ 2 บรรทัด
+    spacing = int(4 * scale)
+    total_text_h = text_size + spacing + sub_size
+    available_h = banner_h - accent_h
+    start_y = (available_h - total_text_h) // 2
+    y1 = start_y
+    y2 = start_y + text_size + spacing
+    
+    # === วาดบรรทัดแรก (กึ่งกลางแนวนอน) ===
+    start_x1 = max(margin_pad, (width - total_w1) // 2)
+    cur_x = start_x1
+    for i, p in enumerate(parts_l1):
+        if p["emoji"] and font_emoji:
+            emoji_y = y1 - int(2 * scale)
+            draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
+        else:
+            draw.text((cur_x, y1), p["text"], fill=p["fill"], font=p["font"])
+        cur_x += part_widths_l1[i]
+        
+    # === วาดบรรทัดที่สอง (กึ่งกลางแนวนอน) ===
+    start_x2 = max(margin_pad, (width - total_w2) // 2)
+    cur_x = start_x2
+    for i, p in enumerate(parts_l2):
+        if p["emoji"] and font_emoji:
+            emoji_y = y2 - int(2 * scale)
+            draw.text((cur_x, emoji_y), p["text"], font=p["font"], embedded_color=True)
+        else:
+            draw.text((cur_x, y2), p["text"], fill=p["fill"], font=p["font"])
+        cur_x += part_widths_l2[i]
+        
     return banner.convert('RGB')
 
 def paste_ad_banner(img):
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.