@echo off
:: auto_text_retouch_submit.bat
:: ใช้งานเมื่อ Photoshop ไม่สามารถเรียก server ได้โดยตรง
:: ลากไฟล์ผลลัพธ์มาวางที่ไอคอนนี้ หรือดับเบิ้ลคลิกเพื่อส่ง active patch

setlocal
set "ENGINE=D:\Github\eworker\text_retouch_engine.py"

if "%~1"=="" (
    :: ส่ง active patch อัตโนมัติ
    python "%ENGINE%" --submit
) else (
    :: ลากไฟล์มาวาง → copy ไปที่ result path แล้วส่ง
    echo กำลังคัดลอกไฟล์ผลลัพธ์...
    python -c "
import json, shutil, os
state_file = r'D:\Github\eworker\cache\text_retouch\active_patch.json'
if os.path.exists(state_file):
    with open(state_file) as f:
        s = json.load(f)
    dest = s.get('result_path', '')
    if dest:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(r'%~1', dest)
        print(f'คัดลอกไปที่ {dest} เรียบร้อย')
    else:
        print('ไม่พบ result_path ใน state')
else:
    print('ไม่พบ active patch state')
"
    python "%ENGINE%" --submit
)

pause
