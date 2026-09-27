import re
from pythainlp import word_tokenize

def format_ass_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f'{h}:{m:02d}:{s:05.2f}'

def build_caption_chunks(words):
    if not words: return []
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

text = 'วงรอบของดาวศุกร์มีรอบเวลาสำคัญ 8 ปี ซึ่งเป็นวัฏจักรที่เกิดขึ้นซ้ำและนักเทรดนิยมนำมาใช้วิเคราะห์การกลับมาของรอบเวลาในตลาด'
raw_words = [w.strip() for w in word_tokenize(text) if w.strip()]
total_duration = 8.54
total_weight = sum(max(2, len(w)) for w in raw_words)
accum = 0.0
words = []
for idx, w in enumerate(raw_words):
    wt = max(2, len(w))
    s_sec = (accum / total_weight) * total_duration
    accum += wt
    e_sec = (accum / total_weight) * total_duration
    words.append({'word': w, 'startSec': s_sec, 'endSec': e_sec})

chunks = build_caption_chunks(words)
for c_idx, chunk in enumerate(chunks):
    full_c = ''.join(w['word'] for w in chunk['words'])
    print(f"Chunk {c_idx}: [{format_ass_time(chunk['startSec'])} -> {format_ass_time(chunk['endSec'])}] '{full_c}'")
    for w in chunk['words']:
        print(f"   word: {w['word']} ({format_ass_time(w['startSec'])} - {format_ass_time(w['endSec'])})")
