Created At: 2026-06-16T11:47:49Z
Completed At: 2026-06-16T11:47:49Z
The following changes were made by the replace_file_content tool to: C:\Users\artwh\.gemini\antigravity-ide\brain\039d4f46-f335-42f5-bf3c-55e209fe36e0\scratch\test_banner.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -10,7 +10,7 @@
 def create_ad_banner_new(width):
     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
     scale = max(0.85, min(width / 900.0, 2.5))
-    banner_h = int(120 * scale)
+    banner_h = int(130 * scale)
     
     # สร้างแถบ gradient สีน้ำเงิน ดูมืออาชีพน่าไว้วางใจ (น้ำเงินเข้ม -> น้ำเงินสว่าง)
     grad = Image.new('RGBA', (2, 1))
@@ -25,15 +25,13 @@
     
     # เส้นคั่น/เส้นปะสีขาวและกรรไกรด้านขวา
     # เราจะวาดเส้นรอยปะสีขาวที่ด้านล่างของแบนเนอร์
-    accent_h = max(2, int(3 * scale))
-    # แต่ผู้ใช้ขอกรอบล่างเป็นรอยปะขาว
     dash_w = int(10 * scale)
     dash_g = int(6 * scale)
-    line_y = banner_h - int(6 * scale)
+    line_y = banner_h - int(18 * scale)
     line_thickness = max(1, int(2 * scale))
     
     # เว้นที่ทางขวาสำหรับกรรไกรตัด
-    scissors_width = int(50 * scale)
+    scissors_width = int(60 * scale)
     end_x = width - scissors_width
     
     # วาดเส้นปะขาว
@@ -51,9 +51,9 @@
             break
             
     # วาดกรรไกร ✂️ (Unicode: \u2702) ที่ทางขวาของเส้นปะ
-    scissors_x = width - int(40 * scale)
-    if font_emoji:
-        scissors_y = line_y - emoji_size // 2 - int(2 * scale)
+    scissors_x = width - int(48 * scale)
+    if font_emoji:
+        scissors_y = line_y - emoji_size // 2 - int(1 * scale)
         draw.text((scissors_x, scissors_y), "✂️", font=font_emoji, embedded_color=True)
     else:
         # Fallback to main font if no emoji font
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.