import os, subprocess, re, sys
sys.path.insert(0, r"D:\Github\eworker")
from auto_donate_watcher import build_ass_center_live_tts, detect_audio_speech_bounds

speech_start, speech_dur, total_dur = detect_audio_speech_bounds('test_audio.mp3')
print(f"Detected bounds: speech_start={speech_start:.2f}s, speech_dur={speech_dur:.2f}s, total_dur={total_dur:.2f}s")

ass_content = build_ass_center_live_tts(
    'ผู้คิดค้นหลอดไฟคนแรกของโลกไม่ใช่ทอมัส เอดิสันอย่างที่หลายคนเข้าใจ',
    start_offset=speech_start,
    speech_duration=speech_dur,
    target_w=640,
    target_h=360,
    is_vertical=False
)

with open('test_complete.ass', 'w', encoding='utf-8') as f:
    f.write(ass_content)

escaped_ass = os.path.abspath('test_complete.ass').replace('\\', '/').replace(':', r'\:')
vdoai_fonts = r"D:\Github\vdoAI\fonts".replace('\\', '/')
escaped_fonts = vdoai_fonts.replace(':', r'\:')
fonts_dir_param = f":fontsdir='{escaped_fonts}'"
subtitles_filter = f"subtitles='{escaped_ass}'{fonts_dir_param}"

# Render at 1.0s (active karaoke word highlight)
cmd = [
    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=640x360:d=5',
    '-vf', subtitles_filter,
    '-ss', '1.0',
    '-frames:v', '1',
    'test_complete_frame.png'
]
res = subprocess.run(cmd, capture_output=True, text=True)
print("FFmpeg returncode:", res.returncode)
if res.returncode == 0:
    print("Generated test_complete_frame.png successfully!")
else:
    print("FFmpeg error:", res.stderr[-500:])
