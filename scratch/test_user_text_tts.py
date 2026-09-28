import sys, os, re, asyncio, math
sys.path.insert(0, r"D:\Github\eworker")
from auto_donate_watcher import detect_audio_speech_bounds, build_ass_center_live_tts

text = "การระบายน้ำย่านบางกะปิและพื้นที่ใกล้เคียงไม่สามารถระบายลงคลองสายรองได้ จึงต้องใช้วิธีสูบลงสู่แม่น้ำเจ้าพระยาเป็นหลัก"
print("Input text:", text)

import edge_tts
target_text = re.sub(r'ยักษ์', 'ยัก', str(text or ''))

async def _synth():
    for voice in ('th-TH-PremwadeeNeural', 'th-TH-NiwatNeural'):
        try:
            print(f"Trying voice {voice}...")
            comm = edge_tts.Communicate(target_text, voice)
            audio_bytes = bytearray()
            boundaries = []
            async for ch in comm.stream():
                if ch['type'] == 'audio':
                    audio_bytes.extend(ch['data'])
                elif ch['type'] == 'SentenceBoundary':
                    boundaries.append(ch)
            if audio_bytes:
                out_mp3 = r"d:\Github\eworker\scratch\test_synth.mp3"
                with open(out_mp3, 'wb') as f:
                    f.write(audio_bytes)
                print(f"Success! Bytes: {len(audio_bytes)}, boundaries: {len(boundaries)}")
                return True
        except Exception as e:
            print(f"Failed {voice}: {e}")
    return False

res = asyncio.run(_synth())
print("Synth result:", res)
