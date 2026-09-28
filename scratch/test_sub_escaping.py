import os, subprocess

ass_file = r"d:\Github\eworker\scratch\test_user.ass"
raw_video = r"d:\Github\eworker\scratch\ohi4h7.mp4"
tts_audio = r"d:\Github\eworker\scratch\test_synth.mp3"
final_video = r"d:\Github\eworker\scratch\test_user_final2.mp4"

esc_colon = r"\:"
esc_path = ass_file.replace("\\", "/").replace(":", esc_colon)

candidates = [
    # Variant 1: filename='...' with single backslash before colon
    "subtitles=filename='d\\:/Github/eworker/scratch/test_user.ass'",
    # Variant 2: filename='d\\:\\/...'
    "subtitles='d\\:/Github/eworker/scratch/test_user.ass'",
    # Variant 3: forward slashes, replace ':' with '\:'
    f"subtitles='{esc_path}'",
    # Variant 4: filename= escaped
    f"subtitles=filename='{esc_path}'",
    # Variant 5: relative path!
    f"subtitles='test_user.ass'",
]

for i, sub_f in enumerate(candidates):
    print(f"\n--- Testing Candidate {i}: {sub_f} ---")
    fc = f"[0:v]scale=640:360,{sub_f}[vsub];[0:a]volume=0.15[ducked];[1:a]volume=2.2[tts];[ducked][tts]amix=inputs=2:duration=first[aout]"
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
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=r"d:\Github\eworker\scratch")
    if p.returncode == 0:
        print(f"Candidate {i} SUCCESS!")
    else:
        err_lines = [l for l in p.stderr.splitlines() if "Error" in l or "Unable" in l or "Invalid" in l]
        print(f"Candidate {i} FAILED: {err_lines}")
