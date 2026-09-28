import subprocess, os

escaped_ass = r"d:\Github\eworker\scratch\test.ass"
with open(escaped_ass, 'w', encoding='utf-8') as f:
    f.write("""[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,Test
""")

esc = escaped_ass.replace('\\', '/').replace(':', r'\:')
cmd = [
    'ffmpeg', '-y',
    '-i', r'd:\Github\eworker\scratch\ohi4h7.mp4',
    '-vf', f"subtitles='{esc}'",
    '-t', '2',
    r'd:\Github\eworker\scratch\out_test.mp4'
]
print("CMD:", cmd)
p = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", p.returncode)
if p.returncode != 0:
    print("Stderr:", p.stderr)
else:
    print("Success! Output size:", os.path.getsize(r'd:\Github\eworker\scratch\out_test.mp4'))
