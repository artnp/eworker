import os, subprocess

ass_file = r"d:\Github\eworker\scratch\test_user.ass"
raw_video = r"d:\Github\eworker\scratch\ohi4h7.mp4"
tts_audio = r"d:\Github\eworker\scratch\test_synth.mp3"
final_video = r"d:\Github\eworker\scratch\test_user_final3.mp4"

esc_colon = r"\:"
escaped_ass = os.path.abspath(ass_file).replace('\\', '/').replace(':', esc_colon)
vdoai_fonts = r"D:\Github\vdoAI\fonts".replace('\\', '/').replace(':', esc_colon)

# Test wrong way (old code):
old_filter = f"subtitles='{escaped_ass}':fontsdir='{vdoai_fonts}'"
print("Old filter:", old_filter)

# Test correct FFmpeg syntax:
correct_filter = f"subtitles=filename='{escaped_ass}':fontsdir='{vdoai_fonts}'"
print("Correct filter:", correct_filter)

for name, flt in [("OLD", old_filter), ("CORRECT", correct_filter)]:
    fc = f"[0:v]scale=640:360,{flt}[vsub];[0:a]volume=0.15[ducked];[1:a]volume=2.2[tts];[ducked][tts]amix=inputs=2:duration=first[aout]"
    cmd = [
        "ffmpeg", "-y",
        "-i", raw_video,
        "-i", tts_audio,
        "-filter_complex", fc,
        "-map", "[vsub]",
        "-map", "[aout]",
        "-t", "1",
        final_video
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    print(f"\n{name} -> Return Code: {p.returncode}")
    if p.returncode != 0:
        print("Error snippet:", [l for l in p.stderr.splitlines() if "Error" in l or "Unable" in l or "Invalid" in l])
