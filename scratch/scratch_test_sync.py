import re
from pythainlp import word_tokenize

def format_ass_time(sec):
    if sec is None or sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def build_caption_chunks(words):
    if not words:
        return []
    chunks = []
    i = 0
    while i < len(words):
        remaining = len(words) - i
        chunk_size = 4
        if remaining <= 5:
            total_chars = sum(len(words[i + k].get('word', '')) for k in range(remaining))
            if total_chars <= 22 or remaining <= 3:
                chunk_size = remaining
            else:
                chunk_size = (remaining + 1) // 2
        elif remaining == 6:
            chunk_size = 3
        elif remaining in (7, 8):
            chunk_size = 4
        else:
            char_len = 0
            count = 0
            for k in range(min(6, len(words) - i)):
                char_len += len(words[i + k].get('word', ''))
                count = k + 1
                if char_len >= 18 and count >= 3:
                    break
            chunk_size = max(3, min(5, count))

        chunk_words = words[i:i + chunk_size]
        chunks.append({
            'words': chunk_words,
            'startSec': chunk_words[0]['startSec'],
            'endSec': chunk_words[-1]['endSec']
        })
        i += chunk_size
    return chunks

def build_ass(clean_text, start_offset, speech_duration, target_w=640, target_h=360):
    raw_tokens = word_tokenize(clean_text)
    raw_words = [w.strip() for w in raw_tokens if w.strip() and not re.match(r'^[\s\.,;:\-–—\(\)\[\]]+$', w)]
    if not raw_words:
        return ''

    def word_phonetic_weight(w):
        # Tone marks and upper/lower vowels don't add full syllable length
        base_chars = re.sub(r'[\u0E31\u0E34-\u0E3A\u0E47-\u0E4E]', '', w)
        return max(2, len(base_chars))

    total_weight = sum(word_phonetic_weight(w) for w in raw_words)
    accum = 0.0
    words = []
    for idx, w in enumerate(raw_words):
        wt = word_phonetic_weight(w)
        s_sec = start_offset + (accum / total_weight) * speech_duration
        accum += wt
        e_sec = start_offset + (accum / total_weight) * speech_duration
        words.append({'word': w, 'startSec': s_sec, 'endSec': e_sec})

    chunks = build_caption_chunks(words)
    print(f"Generated {len(chunks)} chunks for {len(words)} words over {speech_duration:.2f}s")
    for c_idx, c in enumerate(chunks):
        c_text = ''.join(w['word'] for w in c['words'])
        print(f" Chunk {c_idx}: [{format_ass_time(c['startSec'])} - {format_ass_time(c['endSec'])}] '{c_text}'")

build_ass('วงรอบของดาวศุกร์มีรอบเวลาสำคัญ 8 ปี ซึ่งเป็นวัฏจักรที่เกิดขึ้นซ้ำและนักเทรดนิยมนำมาใช้วิเคราะห์การกลับมาของรอบเวลาในตลาด', 0.1, 8.54)
