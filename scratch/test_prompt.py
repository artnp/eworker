import subprocess, os

fonts_dir = r"D:\Github\vdoAI\fonts".replace('\\', '/').replace(':', r'\:')
ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PillBox,Prompt,10,&H75181008,&H75181008,&H30E8B208,&H80000000,0,0,0,0,100,100,0,0,1,2,0,7,0,0,0,222
Style: LiveTts,Prompt,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,1.4,0,5,0,0,0,222

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 1,0:00:00.00,0:00:05.00,LiveTts,,0,0,0,,{\\an5\\pos(320,180)}{\\c&H00FFFFFF&\\b1}ผู้คิดค้น{\\c&H003C92FB&\\b1}หลอดไฟ{\\c&H00FFFFFF&\\b1}คน
"""

with open('test_prompt.ass', 'w', encoding='utf-8') as f:
    f.write(ass_content)

escaped_ass = os.path.abspath('test_prompt.ass').replace('\\', '/').replace(':', r'\:')
vf_filter = f"subtitles='{escaped_ass}':fontsdir='{fonts_dir}'"
cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=640x360:d=1', '-vf', vf_filter, '-frames:v', '1', 'test_prompt.png']
res = subprocess.run(cmd, capture_output=True, text=True)
print('FFmpeg returncode:', res.returncode)
if res.returncode != 0:
    print('Stderr:', res.stderr[-500:])
else:
    print('Generated test_prompt.png successfully!')
