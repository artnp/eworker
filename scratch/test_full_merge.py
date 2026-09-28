import sys, os, subprocess, shutil
sys.path.insert(0, r"D:\Github\eworker")
from auto_donate_watcher import detect_audio_speech_bounds, build_ass_center_live_tts

speech_text = "การระบายน้ำย่านบางกะปิและพื้นที่ใกล้เคียงไม่สามารถระบายลงคลองสายรองได้ จึงต้องใช้วิธีสูบลงสู่แม่น้ำเจ้าพระยาเป็นหลัก"
tts_audio = r"d:\Github\eworker\scratch\test_synth.mp3"
raw_video = r"d:\Github\eworker\scratch\ohi4h7.mp4"
ass_file = r"d:\Github\eworker\scratch\test_user.ass"
final_video = r"d:\Github\eworker\scratch\test_user_final.mp4"

tts_start_offset, tts_speech_duration, total_audio_duration = detect_audio_speech_bounds(tts_audio)
print(f"Timing: offset={tts_start_offset}, speech_dur={tts_speech_duration}, total={total_audio_duration}")

target_w, target_h = 640, 360
is_vertical = False

ass_content = build_ass_center_live_tts(
    speech_text,
    start_offset=tts_start_offset,
    speech_duration=tts_speech_duration,
    target_w=target_w,
    target_h=target_h,
    is_vertical=is_vertical
)

with open(ass_file, 'w', encoding='utf-8') as f:
    f.write(ass_content)

escaped_ass = os.path.abspath(ass_file).replace('\\', '/').replace(':', r'\\:')
vdoai_fonts = r"D:\Github\vdoAI\fonts".replace('\\', '/')
escaped_fonts = vdoai_fonts.replace(':', r'\:')
fonts_dir_param = f":fontsdir='{escaped_fonts}'" if os.path.exists(r"D:\Github\vdoAI\fonts") else ""
subtitles_filter = f"subtitles='{escaped_ass}'{fonts_dir_param}"
scale_param = f"scale={target_w}:{target_h}"

duck_expr = f"volume='if(lt(t,{total_audio_duration + 0.3}),0.15,1.0)':eval=frame"
filter_complex = (
    f"[0:v]{scale_param},{subtitles_filter}[vsub];"
    f"[0:a]{duck_expr}[ducked];"
    f"[1:a]volume=2.2[tts];"
    f"[ducked][tts]amix=inputs=2:duration=first:dropout_transition=0.1:normalize=0[aout]"
)

merge_cmd = [
    "ffmpeg", "-y",
    "-i", raw_video,
    "-i", tts_audio,
    "-filter_complex", filter_complex,
    "-map", "[vsub]",
    "-map", "[aout]",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "fastdecode",
    "-crf", "26",
    "-c:a", "aac",
    "-b:a", "128k",
    "-movflags", "+faststart",
    final_video
]

print("Running merge_cmd...")
res_merge = subprocess.run(merge_cmd, capture_output=True, text=True)
print("Return code:", res_merge.returncode)
if res_merge.returncode != 0:
    print("STDERR:\n", res_merge.stderr)
else:
    print("SUCCESS! Output size:", os.path.getsize(final_video))
