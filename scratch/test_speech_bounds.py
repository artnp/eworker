import subprocess, re, os

def detect_audio_speech_bounds(audio_file):
    try:
        cmd = ['ffmpeg', '-i', audio_file, '-af', 'silencedetect=noise=-30dB:d=0.08', '-f', 'null', '-']
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        starts = [float(m.group(1)) for m in re.finditer(r'silence_start:\s*([\d\.]+)', res.stderr)]
        ends = [float(m.group(1)) for m in re.finditer(r'silence_end:\s*([\d\.]+)', res.stderr)]
        
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_file], capture_output=True, text=True, timeout=10)
        dur = float(probe.stdout.strip())
        
        speech_start = ends[0] if ends else 0.22
        speech_end = starts[-1] if (starts and starts[-1] > speech_start) else (dur - 0.2)
        speech_start = max(0.05, min(speech_start, 0.4))
        speech_dur = max(0.8, speech_end - speech_start)
        return speech_start, speech_dur, dur
    except Exception as e:
        print(f"Error: {e}")
        return 0.22, 2.0, 3.0

print('Bounds for test_audio.mp3:', detect_audio_speech_bounds('test_audio.mp3'))
print('Bounds for temp_test.mp3:', detect_audio_speech_bounds('temp_test.mp3'))
