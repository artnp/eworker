Created At: 2026-06-16T11:48:17Z
Completed At: 2026-06-16T11:48:18Z
The following changes were made by the replace_file_content tool to: d:\Github\eworker\screenshot_donate.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -221,12 +221,13 @@
 def create_ad_banner(width):
     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
     scale = max(0.85, min(width / 900.0, 2.5))
-    banner_h = int(95 * scale)
-    
-    # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
+    banner_h = int(130 * scale)
+    
+    # สร้างแถบ gradient สีน้ำเงิน ดูมืออาชีพน่าไว้วางใจ (น้ำเงินเข้ม -> น้ำเงินสว่าง)
     grad = Image.new('RGBA', (2, 1))
-    grad.putpixel((0, 0), (253, 224, 71, 255))
-    grad.putpixel((1, 0), (234, 179, 8, 255))
+    grad.putpixel((0, 0), (10, 46, 92, 255))   # Dark Blue
+    grad.putpixel((1, 0), (21, 95, 160, 255))  # Professional lighter Blue
+    
     try:
         resample_filter = Image.Resampling.BILINEAR
     except AttributeError:
@@ -233,14 +233,25 @@
     banner = grad.resize((width, banner_h), resample_filter)
     draw = ImageDraw.Draw(banner)
     
-    # เส้นคั่นสีส้ม/น้ำตาลทองด้านล่าง
-    accent_h = max(2, int(3 * scale))
-    draw.rectangle([0, banner_h - accent_h, width - 1, banner_h - 1], fill=(180, 83, 9, 255))
-    
+    # เส้นคั่น/เส้นปะสีขาวและกรรไกรด้านขวา
+    # เราจะวาดเส้นรอยปะส
<truncated 4019 bytes>
ื่อจัดกึ่งกลาง ===
     for p in parts_l1:
@@ -309,11 +309,10 @@
     
     # === ถ้าข้อความกว้างเกิน ให้ย่อฟอนต์ลง ===
     margin_pad = int(16 * scale)
-    usable_w = width - margin_pad * 2
+    usable_w = width - margin_pad * 2 - scissors_width
     max_w = max(total_w1, total_w2)
     if max_w > usable_w:
         shrink = usable_w / max_w
-        # โหลดฟอนต์ใหม่ด้วยขนาดที่ย่อลง
         e_sz2 = max(14, int(emoji_size * shrink))
         t_sz2 = max(12, int(text_size * shrink))
         s_sz2 = max(10, int(sub_size * shrink))
@@ -327,7 +327,6 @@
                 font_sub = ImageFont.truetype(fp, s_sz2)
                 break
         
-        # อัพเดท font ใน parts
         for p in parts_l1:
             if p["emoji"] and font_emoji:
                 p["font"] = font_emoji
@@ -335,7 +335,6 @@
         for p in parts_l2:
             p["font"] = font_sub
             
-        # คำนวณความกว้างใหม่
         total_w1 = 0
         part_widths_l1 = []
         for p in parts_l1:
@@ -361,9 +361,9 @@
         sub_size = s_sz2
         
     # จัดกึ่งกลางแนวตั้งสำหรับ 2 บรรทัด
-    spacing = int(4 * scale)
+    spacing = int(5 * scale)
     total_text_h = text_size + spacing + sub_size
-    available_h = banner_h - accent_h
+    available_h = line_y - int(6 * scale) # เผื่อพื้นที่ด้านบนของเส้นปะไม่ให้เบียดตัวหนังสือ
     start_y = (available_h - total_text_h) // 2
     y1 = start_y
     y2 = start_y + text_size + spacing
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.