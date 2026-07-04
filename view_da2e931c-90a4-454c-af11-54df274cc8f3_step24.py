Created At: 2026-07-01T10:36:55Z
Completed At: 2026-07-01T10:36:56Z
File Path: `file:///D:/Github/eworker/screenshot_donate.py`
Total Lines: 413
Total Bytes: 17914
Showing lines 100 to 250
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
100: 
101:         def _find_window_by_keywords(keywords):
102:             matches = []
103:             @EnumWindowsProc
104:             def _enum(hwnd, lparam):
105:                 title = _get_title(hwnd)
106:                 if not title: return True
107:                 title_lower = title.lower()
108:                 for kw in keywords:
109:                     if kw.lower() in title_lower:
110:                         matches.append((hwnd, title))
111:                         break
112:                 return True
113:             user32.EnumWindows(_enum, 0)
114:             return matches
115: 
116:         def _force_foreground(hwnd):
117:             user32.ShowWindow(hwnd, 9)
118:             user32.SetForegroundWindow(hwnd)
119:             return True
120: 
121:         def _parse_coords(title):
122:             try:
123:                 import re
124:                 if 'READY_TO_PASTE|' in title:
125:                     pattern = r'READY_TO_PASTE\|([\d\.]+)\|([\d\.]+)'
126:                     match = re.search(pattern, title)
127:                     if match:
128:                         return int(float(match.group(1))), int(float(match.group(2)))
129:                 return None
130:             except: return None
131: 
132:         print("[System] Mouse control sequence ACTIVATED.")
133:         target_hwnd, coords = None, None
134:         
135:         for i in range(300):
136:             wins = _find_window_by_keywords(['READY_TO_PASTE', 'READY_TO_POST'])
137:             if wins:
138:                 for h, t in wins:
139:                     c = _parse_coords(t)
140:                     if c:
141:                         target_hwnd, coords = h, c
142:                         pyautogui.moveTo(c[0], c[1], duration=0)
143:                         pyautogui.click()
144:                         break
145:                 if target_hwnd: break
146:             time.sleep(0.1)
147: 
148:         if not target_hwnd:
149:             print("[Fail] Handshake Timeout.")
150:             return
151:         
152:         _force_foreground(target_hwnd)
153:         time.sleep(0.5)
154:         pyautogui.hotkey('ctrl', 'v')
155:         
156:         for _ in range(40):
157:             wins = _find_window_by_keywords(['READY_TO_POST'])
158:             if wins:
159:                 _force_foreground(wins[0][0])
160:                 time.sleep(0.6)
161:                 pyautogui.press('enter')
162:                 break
163:             time.sleep(0.5)
164: 
165:         print("[AutoPaste] Sequence finished.")
166:     except Exception as e:
167:         print(f"[AutoPaste] Error: {e}")
168: 
169: def get_white_band_height(img):
170:     w, h = img.size
171:     img_rgb = img.convert('RGB')
172:     for y in range(h - 1, h - int(h * 0.4), -1):
173:         white_count = 0
174:         samples = 20
175:         for i in range(samples):
176:             x = int((i / samples) * (w * 0.75))
177:             r, g, b = img_rgb.getpixel((x, y))
178:             if r > 190 and g > 190 and b > 190: white_count += 1
179:         if white_count < samples * 0.8:
180:             detected = h - y
181:             if detected >= 20: return detected
182:             else: return 0
183:     return int(h * 0.065)
184: 
185: def crop_watermark(source_path):
186:     if not os.path.exists(source_path):
187:         print(f"ไม่พบไฟล์: {source_path}")
188:         return None
189:     with Image.open(source_path) as img:
190:         img_rgb = img.convert('RGB')
191:         orig_w, orig_h = img_rgb.size
192:         white_band_h = get_white_band_height(img_rgb)
193:         if white_band_h > 0:
194:             crop_bottom = max(160, white_band_h) + 2
195:         else:
196:             crop_bottom = max(60, int(orig_h * 0.065))
197:         return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))
198: 
199: def process_clean_only(full_path=None):
200:     is_bot = '--bot' in sys.argv
201:     target_name = 'complete_bot.png' if is_bot else 'complete.png'
202:     print(f"[CleanOnly] เริ่มต้น... (target: {target_name})")
203:     source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
204:     target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
205:     img = crop_watermark(source)
206:     if img:
207:         img.save(target, format='PNG')
208:         print(f"[Done] {target}")
209:     else:
210:         print("[Error] Failed")
211: 
212: def _upload_with_timeout(file_path, timeout_sec=30):
213:     """Upload ไปที่ Litterbox โดยมี timeout ที่แน่นอน ผ่าน threading"""
214:     import threading
215:     result = [None]
216:     
217:     def _do_upload():
218:         result[0] = upload_litterbox_24h(file_path)
219:     
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
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
