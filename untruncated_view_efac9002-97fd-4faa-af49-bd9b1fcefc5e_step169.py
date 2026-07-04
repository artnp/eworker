Created At: 2026-07-03T01:20:25Z
Completed At: 2026-07-03T01:20:29Z

				The command completed successfully.
				Output:
				<truncated 432 lines>
Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 11
Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 25
Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 44
Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 160
Found create_ad_banner in tool call in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 163
Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 164
Found def create_ad_banner in content in 0bea6a47-896d-49e1-a5ff-dd34ea443860 step 176
Found create_ad_banner in tool call in efac9002-97fd-4faa-af49-bd9b1fcefc5e step 154
Found create_ad_banner in tool call in efac9002-97fd-4faa-af49-bd9b1fcefc5e step 154


--- CONTENT efac9002-97fd-4faa-af49-bd9b1fcefc5e step 163 ---
29: 221: def create_ad_banner(width):
30: 222:     """สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)"""
31: 223:     scale = max(0.85, min(width / 900.0, 2.5))
32: 224:     banner_h = int(95 * scale)
33: 225:     
34: 226:     # สร้างแถบ gradient สีเหลือง (เหลืองเข้ม -> เหลืองอ่อน) โดยใช้การย่อขยายด้วย Bilinear interpolation เพื่อความเร็วสูงสุด
35: 227:     grad = Image.new('RGBA', (2, 1))
36: 228:     grad.putpixel((0, 0), (253, 224, 71, 255))
37: 229:     grad.putpixel((1, 0), (234, 179, 8, 255))
38: 230:     try:
39: 231:      
40: <truncated 19364 bytes>
41: et, 'wb') as f:
42: 609:                 f.write(data)
43: 610:     except Exception as e:
44: 611:         print(f"Error saving file: {e}")
45: 612:     
46: 613:     if no_paste:
47: 614:         print("[Donate] Process only completed. Saved to target/Desktop. Skipped clipboard/pasting.")
48: 615:         return
49: 616: 
50: 617:     copy_image_to_clipboard(target)
51: 618:     
52: 619:     # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
53: 620:     time.sleep(2.0)
54: 621:     auto_paste()
55: 622:     
56: 623:     # --- ★ ล้าง Clipboard หลัง Paste เสร็จ เพื่อป้องกัน complete.png หลุดไปวางใน Gemini sidetab ---
57: 624:     time.sleep(1.0)
58: 625:     try:
59: 626:         ps_clear = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'
60: 627:         subprocess.run(
61: 628:             f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_clear}"',
62: 629:             shell=True, capture_output=True, text=True, timeout=5
63: 630:         )
64: 631:         print("[Clipboard] ✅ Clipboard cleared after paste (prevent Gemini sidetab leak)")
65: 632:     except Exception as e:
66: 633:         print(f"[Clipboard] Clear error (non-critical): {e}")
67: 634: 
68: 635: if __name__ == "__main__":
--- CONTENT efac9002-97fd-4faa-af49-bd9b1fcefc5e step 165 ---
1: "import os\nimport sys\nfrom PIL import Image, ImageDraw, ImageFont\n\n# Add directory of screenshot_donate.py to path\nsys.path.append(r\"d:\\Github\\eworker\")\n\nfrom screenshot_donate import preprocess_thai_text\n\ndef create_ad_banner_new(width):\n    \"\"\"สร้างแถบโฆษณาสวยๆ ขนาดเท่ากับความกว้างของภาพ (รองรับ Emoji สี)\"\"\"\n    scale = max(0.85, min(width / 900.0, 2.5))\n    banner_h = int(120 * scale)\n    \n    # สร้างแถบ gradient สีน้ำเงิน ดูมืออาชีพน่าไว้วางใจ (น้ำเงินเข้ม -> น้ำเงินสว่าง)\n    grad = Image.new('RGBA', (2, 1))\n    grad.putpixel((0, 0), (10, 46, 92, 255))   # Dark Blue\n    grad.putpixel((1, 0), (21, 95, 160, 255))  # Professional lighter Blue\n    \n    try:\n        resample_filter = Image.Resampling.BILINEAR\n    except AttributeError:\n        resample_filter = Image.BILINEAR\n    banner = grad.resize((width, banner_h), resample_filter)\n    draw = ImageDraw.Draw(banner)\n    \n    # เส้นคั่น/เส้นปะสีขาวและกรรไกรด้านขวา\n    # เราจะวาดเส้นรอยปะสีขาวที่ด้านล่างของแบนเนอร์\n    accent_h = max(2, int(3 * scale))\n    # แต่ผู้ใช้ขอกรอบล่างเป็นรอยปะขาว\n    dash_w = int(10 * scale)\n    dash_g = int(6 * scale)\n    line_y = banner_h - int(6 * scale)\n    line_thickness = max(1, int(2 * scale))\n    \n    # เว้นที่ทางขวาสำหรับกรรไกรตัด\n    scissors_width = int(50 * scale)\n    end_x = width - scissors_width\n    \n    # วาดเส้นปะขาว\n    for x in range(0, end_x, dash_w + dash_g):\n        draw.line([(x, line_y), (min(x + dash_w, end_x), line_y)], fill=(255, 255, 255, 220),
2: <truncated 8141 bytes>
The above content shows the entire, complete file contents of the requested file.

--- TOOL CALL efac9002-97fd-4faa-af49-bd9b1fcefc5e step 166 ---
                        if 'def create_ad_banner' in line:
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                content = data.get('content', '')
                                if 'def create_ad_banner' in content:
                                    folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                    print(f"--- CONTENT {folder_name} step {step} ---")
                                    # Print first 20 lines of the function
                                    lines = content.split('\n')
                                    for idx, l in enumerate(lines):
                                        if 'def create_ad_banner' in l:
                                            for jl in lines[idx:idx+40]:
                                                print(jl)
                                            break
                            except Exception:
                                pass
                        # Also check tool_calls
                        if 'create_ad_banner' in line:
                            try:
                                data = json.loads(line)
                                step = data.get('step_index', 0)
                                tool_calls = data.get('tool_calls', [])
                                for tc in tool_calls:
                                    args = tc.get('args', {})
                                    code = args.get('CodeContent', '') or args.get('ReplacementContent', '') or ''
                                    if 'def create_ad_banner' in code or 'create_ad_banner' in code:
                                        folder_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
                                        print(f"--- TOOL CALL {folder_name} step {step} ---")
                                        lines = code.split('\n')
                                        for idx, l in enumerate(lines):
                                            if 'create_ad_banner' in l:
                                                for jl in lines[idx:idx+40]:
                                                    print(jl)
                                                break
                            except Exception:
                                pass
            except Exception:
                pass


