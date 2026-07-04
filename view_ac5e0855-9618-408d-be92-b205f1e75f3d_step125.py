Created At: 2026-06-14T01:37:51Z
Completed At: 2026-06-14T01:37:55Z
The following changes were made by the multi_replace_file_content tool to: D:\Github\eworker\screenshot_donate.py. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -408,7 +408,7 @@
         print(f"[Donate] Upload ล้มเหลวใน {elapsed:.1f}s → fallback to no-upload mode")
     return result[0]
 
-def process_donate(full_path=None):
+def process_donate(full_path=None, no_paste=False):
     print("[Donate] เริ่มต้น...")
     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'complete.png')
@@ -568,6 +568,10 @@
     except Exception as e:
         print(f"Error saving file: {e}")
     
+    if no_paste:
+        print("[Donate] Process only completed. Saved to target/Desktop. Skipped clipboard/pasting.")
+        return
+
     copy_image_to_clipboard(target)
     
     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
@@ -593,6 +593,8 @@
         process_clean_only(target_path)
     elif mode_flag == "--donate":
         process_donate(target_path)
+    elif mode_flag == "--donate-no-paste":
+        process_donate(target_path, no_paste=True)
     else:
         process_donate()
 
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.