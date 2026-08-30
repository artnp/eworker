import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def get_thai_font(size_pt, is_bold=False):
    font_paths = [
        "C:/Windows/Fonts/tahomabd.ttf" if is_bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/LeelaUIb.ttf" if is_bold else "C:/Windows/Fonts/leelawad.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if is_bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size_pt)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_vector_scan_icon(draw, x, y, size, color=(255, 255, 255, 255)):
    """Draw a crisp vector QR/Scan viewfinder icon at (x, y)."""
    corner_len = int(size * 0.32)
    thick = max(1, int(size * 0.14))
    x2 = x + size
    y2 = y + size
    
    # Top-Left
    draw.line([(x, y), (x + corner_len, y)], fill=color, width=thick)
    draw.line([(x, y), (x, y + corner_len)], fill=color, width=thick)
    # Top-Right
    draw.line([(x2 - corner_len, y), (x2, y)], fill=color, width=thick)
    draw.line([(x2, y), (x2, y + corner_len)], fill=color, width=thick)
    # Bottom-Left
    draw.line([(x, y2), (x + corner_len, y2)], fill=color, width=thick)
    draw.line([(x, y2 - corner_len), (x, y2)], fill=color, width=thick)
    # Bottom-Right
    draw.line([(x2 - corner_len, y2), (x2, y2)], fill=color, width=thick)
    draw.line([(x2, y2 - corner_len), (x2, y2)], fill=color, width=thick)
    
    cx, cy = x + size // 2, y + size // 2
    r = max(1, int(size * 0.12))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

def draw_luxury_lock(draw, x, y, size, color=(255, 255, 255, 255)):
    body_w = int(size * 0.82)
    body_h = int(size * 0.62)
    shackle_r = int(size * 0.32)
    shackle_thick = max(2, int(size * 0.12))
    
    shackle_cx = x + body_w // 2
    shackle_top = y - int(size * 0.32)
    
    draw.arc(
        [shackle_cx - shackle_r, shackle_top, shackle_cx + shackle_r, shackle_top + shackle_r * 2],
        start=180, end=0, fill=color, width=shackle_thick
    )
    draw.line([(shackle_cx - shackle_r, shackle_top + shackle_r), (shackle_cx - shackle_r, y + int(size * 0.08))], fill=color, width=shackle_thick)
    draw.line([(shackle_cx + shackle_r, shackle_top + shackle_r), (shackle_cx + shackle_r, y + int(size * 0.08))], fill=color, width=shackle_thick)
    
    draw.rounded_rectangle([x, y, x + body_w, y + body_h], radius=max(2, int(size * 0.16)), fill=color)
    
    kh_color = (190, 18, 60, 255)
    kh_r = max(2, int(size * 0.11))
    kh_cx = x + body_w // 2
    kh_cy = y + int(body_h * 0.42)
    draw.ellipse([kh_cx - kh_r, kh_cy - kh_r, kh_cx + kh_r, kh_cy + kh_r], fill=kh_color)
    draw.line([(kh_cx, kh_cy), (kh_cx, kh_cy + int(size * 0.16))], fill=kh_color, width=max(1, int(size * 0.08)))

draw_vector_lock = draw_luxury_lock

def render_luxury_qr_slip(card_w=235):
    """
    สร้างสลิปใบเสร็จ QR PromptPay สไตล์ Receipt กะทัดรัด พอดีข้อความ:
    - พื้นขาวสะอาด ไร้ขอบสีดำ (Zero dark border)
    - ฟันปลาสีขาวล้วนต่อจากการ์ด
    - สัดส่วนกะทัดรัด ไม่กินพื้นที่รูปภาพ
    - เงา Drop shadow นุ่มนวล
    """
    scale = card_w / 235.0
    s = scale

    script_dir = r"d:\Github\eworker\assets"
    os.makedirs(script_dir, exist_ok=True)
    desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')

    # --- Load assets ---
    qr_p = os.path.join(script_dir, "qr_code_clean.png")
    if not os.path.exists(qr_p):
        src_60 = os.path.join(desktop, "60.- .jpg")
        if os.path.exists(src_60):
            Image.open(src_60).crop((96, 162, 324, 388)).save(qr_p)
    qr_img = Image.open(qr_p).convert("RGBA") if os.path.exists(qr_p) else Image.new("RGBA", (200, 200), (200, 200, 200))

    logos_p = os.path.join(script_dir, "bank_logos.png")
    if not os.path.exists(logos_p):
        src_pp = os.path.join(desktop, "promptpay.png")
        if os.path.exists(src_pp):
            Image.open(src_pp).crop((180, 560, 460, 605)).save(logos_p)
    bank_logos = Image.open(logos_p).convert("RGBA") if os.path.exists(logos_p) else None

    pp_logo_p = os.path.join(script_dir, "promptpay_header_full.png")
    if not os.path.exists(pp_logo_p):
        src_pp = os.path.join(desktop, "promptpay.png")
        if os.path.exists(src_pp):
            Image.open(src_pp).crop((170, 10, 470, 120)).save(pp_logo_p)
    pp_logo = Image.open(pp_logo_p).convert("RGBA") if os.path.exists(pp_logo_p) else None

    # --- Fonts ---
    f_brand    = get_thai_font(int(14.5 * s), is_bold=True)
    f_sublabel = get_thai_font(int(9.5 * s), is_bold=False)
    f_amount   = get_thai_font(int(28 * s), is_bold=True)
    f_cur      = get_thai_font(int(12 * s), is_bold=False)
    f_cta      = get_thai_font(int(12 * s), is_bold=True)
    f_row_val  = get_thai_font(int(9.5 * s), is_bold=False)

    # --- Pre-calculate dynamic heights for pixel-perfect receipt layout ---
    hdr_txt = "สแกนจ่ายได้ทุกธนาคาร!!"
    lbl = "ยอดชำระค่าบริการ"
    amt_txt = "฿ 60.00"
    bht = "( หกสิบบาทถ้วน )"
    cta_txt = "จ่ายแล้วไม่ต้องส่งสลิป"

    _dummy = Image.new("RGBA", (1, 1))
    _ddraw = ImageDraw.Draw(_dummy)

    hbb  = _ddraw.textbbox((0, 0), hdr_txt, font=f_brand)
    lbb  = _ddraw.textbbox((0, 0), lbl, font=f_sublabel)
    ab   = _ddraw.textbbox((0, 0), amt_txt, font=f_amount)
    bb2  = _ddraw.textbbox((0, 0), bht, font=f_row_val)
    ctab = _ddraw.textbbox((0, 0), cta_txt, font=f_cta)

    PAD       = int(10 * s)                 # compact horizontal padding
    HEADER_H  = int(38 * s)                 # Header text zone
    DIV_GAP   = int(8 * s)                  # gap around dashed lines
    QR_SZ     = int(148 * s)                # compact QR size (sharp & clear)
    QR_GAP_B  = int(12 * s)                 # space under QR
    CTA_H     = int(36 * s)                 # CTA button height
    CTA_PAD_B = int(10 * s)                 # space under CTA before zigzag
    ZIGZAG_H  = max(5, int(6.5 * s))        # neat fine zigzag

    # Calculate exact section vertical positions
    y_hdr  = int(10 * s)
    y_div1 = y_hdr + HEADER_H
    y_amt_lbl = y_div1 + DIV_GAP
    y_amt_val = y_amt_lbl + (lbb[3] - lbb[1]) + int(4 * s)
    y_amt_sub = y_amt_val + (ab[3] - ab[1]) + int(4 * s)
    y_div2 = y_amt_sub + (bb2[3] - bb2[1]) + int(6 * s)
    y_qr   = y_div2 + DIV_GAP
    qr_avail = card_w - PAD * 2
    qr_display = min(qr_avail, int(QR_SZ))
    y_div3 = y_qr + qr_display + QR_GAP_B
    y_cta  = y_div3 + DIV_GAP
    body_h = y_cta + CTA_H + CTA_PAD_B
    total_h = body_h + ZIGZAG_H

    # --- Canvas ---
    BORDER_COL = (40, 42, 45, 255)         # near-black charcoal
    WHITE      = (255, 255, 255, 255)
    GRAY_TXT   = (120, 120, 120, 255)
    DARK_TXT   = (22, 22, 22, 255)
    DASH_COL   = (200, 200, 200, 255)
    GREEN      = (22, 163, 74, 255)

    card = Image.new("RGBA", (card_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    RADIUS = int(10 * s)
    num_t  = max(18, int(20 * s))
    tw     = card_w / float(num_t)

    # ════════════════════════════════════════════
    # 0. PURE WHITE RECEIPT BODY (ZERO DARK BORDER)
    # ════════════════════════════════════════════
    draw.rounded_rectangle([0, 0, card_w - 1, body_h], radius=RADIUS, fill=WHITE)
    draw.rectangle([0, RADIUS, card_w - 1, body_h], fill=WHITE)

    # Pure white frequent sawtooth teeth
    for i in range(num_t):
        x1 = i * tw
        xm = (i + 0.5) * tw
        x2 = (i + 1.0) * tw
        draw.polygon(
            [(x1, body_h - 1),
             (xm, body_h + ZIGZAG_H),
             (x2, body_h - 1)],
            fill=WHITE
        )

    def draw_dashed_line(y):
        dash_len = max(3, int(4 * s))
        gap_len  = max(2, int(3 * s))
        x = PAD
        while x < card_w - PAD:
            x2 = min(x + dash_len, card_w - PAD)
            draw.line([(x, y), (x2, y)], fill=DASH_COL, width=1)
            x += dash_len + gap_len

    # 1. Header
    hw = hbb[2] - hbb[0]
    hh = hbb[3] - hbb[1]
    draw.text(((card_w - hw) // 2, y_hdr + (HEADER_H - hh) // 2),
              hdr_txt, font=f_brand, fill=DARK_TXT)

    # 2. Divider 1
    draw_dashed_line(y_div1)

    # 3. Amount section
    draw.text(((card_w - (lbb[2]-lbb[0])) // 2, y_amt_lbl), lbl, font=f_sublabel, fill=GRAY_TXT)
    aw = ab[2] - ab[0]
    draw.text(((card_w - aw) // 2, y_amt_val), amt_txt, font=f_amount, fill=DARK_TXT)
    draw.text(((card_w - (bb2[2]-bb2[0])) // 2, y_amt_sub), bht, font=f_row_val, fill=GRAY_TXT)

    # 4. Divider 2
    draw_dashed_line(y_div2)

    # 5. QR Code
    qr_bx = (card_w - qr_display) // 2
    qr_r = qr_img.resize((qr_display, qr_display), Image.Resampling.LANCZOS)
    card.paste(qr_r, (qr_bx, y_qr), qr_r)

    # 6. Divider 3
    draw_dashed_line(y_div3)

    # 7. CTA Button
    foot_r = int(6 * s)
    cta_pad_x = int(6 * s)
    draw.rounded_rectangle(
        [cta_pad_x, y_cta, card_w - 1 - cta_pad_x, y_cta + CTA_H],
        radius=foot_r, fill=GREEN
    )

    tw_txt = ctab[2] - ctab[0]
    th_txt = ctab[3] - ctab[1]
    icon_sz  = int(12 * s)
    icon_gap = int(4 * s)
    block_w  = icon_sz + icon_gap + tw_txt
    cta_bx   = (card_w - block_w) // 2
    cta_ty   = y_cta + (CTA_H - th_txt) // 2 - int(1 * s)
    icy      = y_cta + (CTA_H - icon_sz) // 2
    draw_vector_scan_icon(draw, cta_bx, icy, icon_sz, color=(255, 255, 255, 255))
    draw.text((cta_bx + icon_sz + icon_gap, cta_ty), cta_txt, font=f_cta, fill=(255, 255, 255, 255))

    # ════════════════════════════════════════════
    # 8. Realistic Soft Drop Shadow
    # ════════════════════════════════════════════
    shadow_pad = max(8, int(14 * s))
    shadow_img = Image.new("RGBA",
                           (card_w + shadow_pad * 2, total_h + shadow_pad * 2),
                           (0, 0, 0, 0))
    card_alpha = card.split()[3]
    shadow_silhouette = Image.new("RGBA", (card_w, total_h), (0, 0, 0, 0))
    shadow_silhouette.paste((0, 0, 0, 85), (0, 0), mask=card_alpha)
    shadow_img.paste(shadow_silhouette, (shadow_pad, shadow_pad + int(2.5 * s)), shadow_silhouette)
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(7 * s)))

    return card, shadow_img, shadow_pad


def create_anti_ai_watermark(img_path_or_img, text="โปรดชำระค่าบริการเพื่อรับไฟล์เต็ม"):

    if isinstance(img_path_or_img, str):
        base_img = Image.open(img_path_or_img).convert("RGBA")
    else:
        base_img = img_path_or_img.convert("RGBA")
        
    w, h = base_img.size
    scale = max(0.65, min(w, h) / 800.0)
    
    font_title = get_thai_font(int(22 * scale), is_bold=True)
    font_sub = get_thai_font(int(11 * scale), is_bold=False)
    font_grid = get_thai_font(int(13 * scale), is_bold=False)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # 1. Geometric Diamond Grid
    grid_spacing = int(max(75 * scale, 65))
    line_w = max(1, int(1.6 * scale))
    grid_red = (225, 29, 72, 140)
    grid_shadow = (0, 0, 0, 45)
    
    for offset in range(-h * 2, w + h * 2, grid_spacing):
        draw.line([(offset + 1, -1), (offset + h + 1, h + 1)], fill=grid_shadow, width=line_w + 1)
        draw.line([(offset, 0), (offset + h, h)], fill=grid_red, width=line_w)

    for offset in range(-h * 2, w + h * 2, grid_spacing):
        draw.line([(offset - 1, -1), (offset - h - 1, h + 1)], fill=grid_shadow, width=line_w + 1)
        draw.line([(offset, 0), (offset - h, h)], fill=grid_red, width=line_w)

    # 2. Tiled Watermark Text
    watermark_label = "SAMPLE PREVIEW • ภาพตัวอย่าง"
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.textbbox((0, 0), watermark_label, font=font_grid)
    tw = bbox[2] - bbox[0] + int(20 * scale)
    th = bbox[3] - bbox[1] + int(10 * scale)
    
    text_stamp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ts_draw = ImageDraw.Draw(text_stamp)
    ts_draw.text((int(5 * scale) + 1, int(2 * scale) + 1), watermark_label, font=font_grid, fill=(0, 0, 0, 90))
    ts_draw.text((int(5 * scale), int(2 * scale)), watermark_label, font=font_grid, fill=(255, 255, 255, 175))
    
    rot_text = text_stamp.rotate(45, expand=True, resample=Image.Resampling.BICUBIC)
    rt_w, rt_h = rot_text.size
    
    step_x = int(rt_w * 1.8)
    step_y = int(rt_h * 1.8)
    for y in range(-rt_h, h + rt_h, step_y):
        row_offset = ((y // step_y) % 2) * (step_x // 2)
        for x in range(-rt_w + row_offset, w + rt_w, step_x):
            overlay.paste(rot_text, (x, y), rot_text)

    # 3. Hero Ribbon
    angle = -18
    banner_h = int(68 * scale)
    diag = int(math.sqrt(w*w + h*h) * 1.3)
    
    ribbon = Image.new("RGBA", (diag, banner_h), (0, 0, 0, 0))
    r_draw = ImageDraw.Draw(ribbon)
    
    for y in range(banner_h):
        t = y / float(banner_h)
        r = int(225 * (1 - t) + 180 * t)
        g = int(29 * (1 - t) + 15 * t)
        b = int(72 * (1 - t) + 40 * t)
        r_draw.line([(0, y), (diag, y)], fill=(r, g, b, 245))

    gold_color = (251, 191, 36, 255)
    white_color = (255, 255, 255, 220)
    
    r_draw.line([(0, 0), (diag, 0)], fill=gold_color, width=max(1, int(2.5 * scale)))
    r_draw.line([(0, int(3 * scale)), (diag, int(3 * scale))], fill=white_color, width=max(1, int(1 * scale)))
    r_draw.line([(0, banner_h - 1), (diag, banner_h - 1)], fill=gold_color, width=max(1, int(2.5 * scale)))
    r_draw.line([(0, banner_h - 1 - int(3 * scale)), (diag, banner_h - 1 - int(3 * scale))], fill=white_color, width=max(1, int(1 * scale)))
    
    main_txt = f"ตัวอย่างสำหรับตรวจสอบ • {text}"
    sub_txt = "SAMPLE PREVIEW • PLEASE PAY SERVICE FEE TO RECEIVE HIGH-RES ORIGINAL FILE"
    
    m_bbox = r_draw.textbbox((0, 0), main_txt, font=font_title)
    mw = m_bbox[2] - m_bbox[0]
    
    lock_size = int(18 * scale)
    lock_gap = int(10 * scale)
    unit_w = lock_size + lock_gap + mw + int(90 * scale)
    
    for bx in range(0, diag + unit_w, unit_w):
        ty1 = int(10 * scale)
        lx = bx
        ly = ty1 + int(3 * scale)
        draw_luxury_lock(r_draw, lx, ly, lock_size, color=(255, 255, 255, 255))
        
        tx = lx + lock_size + lock_gap
        r_draw.text((tx + 1, ty1 + 1), main_txt, font=font_title, fill=(50, 5, 20, 200))
        r_draw.text((tx, ty1), main_txt, font=font_title, fill=(255, 255, 255, 255))
        
        ty2 = ty1 + int(27 * scale)
        r_draw.text((tx + 1, ty2 + 1), sub_txt, font=font_sub, fill=(50, 5, 20, 180))
        r_draw.text((tx, ty2), sub_txt, font=font_sub, fill=(254, 240, 138, 250))

    rot_ribbon = ribbon.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    rr_w, rr_h = rot_ribbon.size
    
    ribbon_shadow = Image.new("RGBA", (rr_w, rr_h), (0, 0, 0, 0))
    ribbon_shadow.paste((0, 0, 0, 95), (0, 0), mask=rot_ribbon.split()[3])
    ribbon_shadow = ribbon_shadow.filter(ImageFilter.GaussianBlur(int(7 * scale)))
    
    pos_x = (w - rr_w) // 2
    pos_y = int(h * 0.45) - rr_h // 2
    overlay.paste(ribbon_shadow, (pos_x, pos_y + int(4 * scale)), ribbon_shadow)
    overlay.paste(rot_ribbon, (pos_x, pos_y), rot_ribbon)

    # 4. Stamp Receipt-style PromptPay QR Slip — TOP LEFT corner
    try:
        margin = max(14, int(w * 0.02))
        # Card width: compact & snug to content (max ~240px)
        max_w_by_width = int(w * 0.28)
        max_w_by_height = int((h * 0.40) / 1.5)
        target_card_w = max(180, min(max_w_by_width, max_w_by_height, 240))

        bill_card, bill_shadow, shadow_pad = render_luxury_qr_slip(card_w=target_card_w)
        bw, bh = bill_card.size

        # Ensure card fits horizontally — clamp if needed
        if bw > w - margin * 2:
            ratio = (w - margin * 2) / float(bw)
            bw_fit = w - margin * 2
            bh_fit = int(bh * ratio)
            bill_card = bill_card.resize((bw_fit, bh_fit), Image.Resampling.LANCZOS)
            bill_shadow = bill_shadow.resize((bw_fit + shadow_pad*2, bh_fit + shadow_pad*2), Image.Resampling.LANCZOS)
            bw, bh = bw_fit, bh_fit

        # Position: TOP LEFT corner
        bill_x = margin
        bill_y = margin

        overlay.paste(bill_shadow, (bill_x - shadow_pad, bill_y - shadow_pad + 4), bill_shadow)
        overlay.paste(bill_card, (bill_x, bill_y), bill_card)
    except Exception as e_bill:
        print(f"[Watermark] Warning: Could not stamp PromptPay QR slip: {e_bill}")

    # 5. Composite
    final_img = Image.alpha_composite(base_img, overlay).convert("RGB")
    return final_img
