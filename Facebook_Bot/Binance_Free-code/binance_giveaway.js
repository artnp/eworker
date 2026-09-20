import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Directories and Paths
export const BINANCE_DIR = __dirname;
export const LINKS_FILE = path.join(BINANCE_DIR, 'referral_links.txt');
export const PROMOTE_IMAGE = path.join(BINANCE_DIR, 'promote.png');

// RedPacket_Code Workspace Files
const candidatePaths = [
  path.resolve(__dirname, '../../../RedPacket_Code'),
  'D:\\Github\\RedPacket_Code',
  path.resolve(__dirname, '../../RedPacket_Code')
];
export const REDPACKET_DIR = candidatePaths.find((p) => fs.existsSync(p)) || 'D:\\Github\\RedPacket_Code';
export const CLAIMED_SUCCESS_FILE = path.join(REDPACKET_DIR, 'claimed_success_codes.json');
export const INVALID_CODES_FILE = path.join(REDPACKET_DIR, 'invalid_codes.json');
export const FAILED_ATTEMPTS_FILE = path.join(REDPACKET_DIR, 'failed_attempts.json');

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const DAILY_SET_FILE = path.join(BINANCE_DIR, 'daily_set.json');

/**
 * ดึงหมายเลขชุดถัดไปของวันจาก daily_set.json
 * - หากเป็นวันใหม่ จะรีเซ็ตกลับเป็นชุดที่ 1 อัตโนมัติ
 * - หากเป็นวันเดิม จะรันนับต่อ 1 -> 2 -> 3 ไปเรื่อยๆ ไม่ซ้ำ
 */
export function getDailySetNumber() {
  const now = new Date();
  const d = String(now.getDate()).padStart(2, '0');
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const y = now.getFullYear();
  const todayStr = `${d}/${m}/${y}`;

  let currentSet = 1;
  if (fs.existsSync(DAILY_SET_FILE)) {
    try {
      const data = JSON.parse(fs.readFileSync(DAILY_SET_FILE, 'utf8'));
      if (data && data.date === todayStr && Number.isInteger(data.lastSet) && data.lastSet >= 1) {
        currentSet = data.lastSet + 1;
      }
    } catch (e) {
      console.warn('[BinanceGiveaway] Error reading daily_set.json:', e.message);
    }
  }
  return currentSet;
}

/**
 * บันทึกหมายเลขชุดล่าสุดของวันนี้ลงใน daily_set.json (ขนาดไฟล์ 3 บรรทัด ไม่สะสมขยะ)
 */
export function saveDailySetNumber(setNumber) {
  const now = new Date();
  const d = String(now.getDate()).padStart(2, '0');
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const y = now.getFullYear();
  const todayStr = `${d}/${m}/${y}`;
  try {
    fs.writeFileSync(DAILY_SET_FILE, JSON.stringify({ date: todayStr, lastSet: setNumber }, null, 2), 'utf8');
    console.log(`[BinanceGiveaway] 💾 บันทึกเลขชุดล่าสุด: วันที่ ${todayStr} --[ชุด (${setNumber})]`);
  } catch (e) {
    console.warn('[BinanceGiveaway] Error saving daily_set.json:', e.message);
  }
}

/**
 * สลับดึง Referral Link ถัดไปจาก referral_links.txt
 * สลับอัตโนมัติตามรอบเวลา โดยไม่ต้องใช้ไฟล์ state
 */
export function getNextReferralLink() {
  const defaultLink = 'https://www.facebook.com/ImageTextEditor/posts/pfbid0BfCoyV7z5gDmG7rMoryLP9DicqRtc5KX1zoM15JEfF8nGQ9Z3on8YnELQucXnJ2pl';
  if (!fs.existsSync(LINKS_FILE)) return defaultLink;

  const content = fs.readFileSync(LINKS_FILE, 'utf8');
  const links = content
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith('#'));

  if (links.length === 0) return defaultLink;

  const slot = Math.floor(new Date().getHours() / 3);
  return links[slot % links.length];
}

/**
 * ดึงโค้ด Red Packet ที่เคลมสำเร็จสดใหม่ล่าสุด 10-15 โค้ด
 * (ดึงจากท้ายลิสต์ย้อนกลับมา = โค้ดที่เพิ่งเคลมได้สดๆ ร้อนๆ ล่าสุด)
 */
export function getAvailableRedPacketCodes(maxLimit = 15) {
  let successCodes = [];
  if (fs.existsSync(CLAIMED_SUCCESS_FILE)) {
    try {
      const raw = JSON.parse(fs.readFileSync(CLAIMED_SUCCESS_FILE, 'utf8'));
      if (Array.isArray(raw)) {
        successCodes = raw;
      } else if (raw && Array.isArray(raw.codes)) {
        successCodes = raw.codes;
      }
    } catch (e) {
      console.error('[BinanceGiveaway] Error reading claimed_success_codes:', e.message);
    }
  }

  // Blacklist invalid codes
  const invSet = new Set();
  if (fs.existsSync(INVALID_CODES_FILE)) {
    try {
      const invRaw = JSON.parse(fs.readFileSync(INVALID_CODES_FILE, 'utf8'));
      const list = Array.isArray(invRaw) ? invRaw : Object.keys(invRaw || {});
      list.forEach((c) => invSet.add(String(c).trim().toUpperCase()));
    } catch (e) { }
  }

  // Blacklist failed attempts
  const failSet = new Set();
  if (fs.existsSync(FAILED_ATTEMPTS_FILE)) {
    try {
      const failRaw = JSON.parse(fs.readFileSync(FAILED_ATTEMPTS_FILE, 'utf8'));
      const items = (failRaw && failRaw.items) || {};
      for (const k of Object.keys(items)) {
        const item = items[k];
        if (item && item.type === 'cryptobox' && item.id) {
          failSet.add(String(item.id).trim().toUpperCase());
        }
      }
    } catch (e) { }
  }

  // ดึงจากท้ายลิสต์ย้อนขึ้นมา (Newest first)
  const newestCodes = [...successCodes].reverse();
  const candidates = [];

  for (const c of newestCodes) {
    const clean = String(c).trim().toUpperCase();
    if (
      clean &&
      clean.length >= 6 &&
      !invSet.has(clean) &&
      !failSet.has(clean) &&
      !candidates.includes(clean)
    ) {
      candidates.push(clean);
      if (candidates.length >= maxLimit) break;
    }
  }

  return candidates;
}

/**
 * ดึง Mapping ของรหัสโค้ดคู่กับชื่อเหรียญ เช่น { 'AY1CGKMB': 'ETH' }
 */
export function getClaimedCoinMap() {
  if (fs.existsSync(CLAIMED_SUCCESS_FILE)) {
    try {
      const raw = JSON.parse(fs.readFileSync(CLAIMED_SUCCESS_FILE, 'utf8'));
      if (raw && typeof raw.coin_map === 'object' && raw.coin_map !== null) {
        return raw.coin_map;
      }
    } catch (e) {
      console.error('[BinanceGiveaway] Error reading coin_map:', e.message);
    }
  }
  return {};
}

/**
 * สร้างข้อความแคปชั่นสำหรับโพสต์หลัก
 */
export function buildPostCaption(codesList, setNumber = 1, refLink = null) {
  const now = new Date();
  const d = String(now.getDate()).padStart(2, '0');
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const y = now.getFullYear();
  const dateStr = `${d}/${m}/${y}`;

  const link = refLink || getNextReferralLink();
  const coinMap = getClaimedCoinMap();
  const formattedCodes = codesList.map((c) => {
    const clean = String(c).trim().toUpperCase();
    const coin = coinMap[clean];
    return coin ? `[ ${coin} ] ➨ ${clean}` : `[ 🎲 ] ➨ ${clean}`;
  });
  const codesText = formattedCodes.join('\n');

  return `🎁 คืนกำไรให้สังคม แจกเหรียญคริปโตฟรี ให้ลูกค้าที่ติดตามเพจ🎁
📅 วันที่: ${dateStr} --[ชุด (${setNumber})]
⚡ เคลมได้ที่หมวด Binance Red packet ⚡

👇 กรอกโค้ดล่าสุด:
${codesText}

🔥 โค้ดหมดอายุวันต่อวัน! รีบกรอกทันทีที่เห็นโค้ดนี้

---------
📍 👇สมัครเพื่อกรอกโค้ดทางนี้เลยขอรับ:
${link}
---------


- อยากได้อีกไหมท่าน ?
👉 โปรดติดตามเพจนี้! มีแจกโค้ดใหม่ ๆ เรื่อย ๆ อีกแน่นอน 🔔
---
#RedPacket #Binance #โค้ดเคลมเหรียญคริปโต #แจกคริปโตฟรี`;
}

/**
 * สร้างข้อความสำหรับคอมเมนต์แรก (First Comment) - ไม่ได้ใช้งานแล้ว
 */
export function buildFirstCommentText(refLink) {
  return `🎁⚡ สมัครเพื่อกรอกโค้ดทางนี้เลยขอรับ:
 ${refLink}`;
}

/**
 * ฟังก์ชันหลักในการโพสต์แจกโค้ดลง Facebook Profile/Page
 * ขั้นตอนกด 2 ครั้ง: กด "ถัดไป" (ครั้งที่ 1) -> กด "โพสต์" (ครั้งที่ 2)
 */
export async function publishGiveawayPost(fbPage, reportStatusFn = null) {
  console.log('\n============================================');
  console.log('🎁 [BinanceGiveaway] Starting Red Packet Post...');
  console.log('============================================');

  // 1. ดึงโค้ดสดใหม่ล่าสุด (10-15 โค้ด)
  const codes = getAvailableRedPacketCodes(15);
  if (!codes || codes.length === 0) {
    console.warn('[BinanceGiveaway] ⚠️ ไม่พบโค้ดในระบบ');
    return { success: false, reason: 'no_codes_found' };
  }

  const setNumber = getDailySetNumber();
  const refLink = getNextReferralLink();
  const caption = buildPostCaption(codes, setNumber, refLink);

  console.log(`[BinanceGiveaway] Preparing Set (${setNumber}) with ${codes.length} newest codes.`);
  console.log(`[BinanceGiveaway] Referral Link: ${refLink}`);

  if (reportStatusFn) {
    await reportStatusFn(96, `กำลังเตรียมโพสต์แจกโค้ด ชุด (${setNumber})...`, `จำนวน ${codes.length} โค้ด`, 'info');
  }

  try {
    // 2. ไปที่หน้า facebook.com/me
    console.log('[BinanceGiveaway] Navigating to https://www.facebook.com/me...');
    await fbPage.goto('https://www.facebook.com/me', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await sleep(3500);

    // ปิด Popup/Dialog ที่อาจค้างอยู่
    await fbPage.evaluate(() => {
      const closeButtons = Array.from(document.querySelectorAll('div[role="dialog"] div[role="button"][aria-label*="ปิด"], div[role="dialog"] div[role="button"][aria-label*="Close"]'));
      closeButtons.forEach((b) => b.click());
    }).catch(() => { });
    await sleep(800);

    // 3. เปิด Create Post Dialog
    console.log('[BinanceGiveaway] Opening Create Post dialog...');
    let postBoxClicked = false;
    const postBoxFound = await fbPage.evaluate(() => {
      const candidates = ['คุณกำลังคิดอะไรอยู่', 'คุณกำลังคิดอะไร', "What's on your mind", 'Share something'];
      const spans = Array.from(document.querySelectorAll('span'));
      for (const txt of candidates) {
        const span = spans.find((s) => s.textContent.trim() === txt);
        if (span) {
          let el = span;
          for (let i = 0; i < 8; i++) {
            el = el.parentElement;
            if (!el) break;
            if (el.getAttribute('role') === 'button') {
              el.click();
              return true;
            }
          }
        }
      }
      return false;
    }).catch(() => false);

    if (postBoxFound) {
      postBoxClicked = true;
    } else {
      const texts = ['คุณกำลังคิดอะไรอยู่', 'คุณกำลังคิดอะไร', "What's on your mind"];
      for (const txt of texts) {
        try {
          const el = fbPage.locator(`div[role="button"]:has-text("${txt}")`).first();
          if ((await el.count()) > 0 && (await el.isVisible({ timeout: 1500 }).catch(() => false))) {
            await el.click({ force: true });
            postBoxClicked = true;
            break;
          }
        } catch (e) { }
      }
    }

    if (!postBoxClicked) {
      console.warn('[BinanceGiveaway] Could not open create post dialog.');
      return { success: false, reason: 'cannot_open_create_post' };
    }

    await sleep(3000);

    // 4. แนบรูปภาพ promote.png
    if (fs.existsSync(PROMOTE_IMAGE)) {
      console.log(`[BinanceGiveaway] Attaching promote image: ${PROMOTE_IMAGE}`);
      if (reportStatusFn) {
        await reportStatusFn(97, `กำลังแนบรูปภาพโปรโมต...`, 'promote.png', 'info');
      }

      const fileInput = fbPage.locator('div[role="dialog"] input[type="file"]').first();
      if ((await fileInput.count()) > 0) {
        await fileInput.setInputFiles(PROMOTE_IMAGE);
        console.log('[BinanceGiveaway] ✅ Image attached via direct file input.');
      }
      await sleep(3000);
    }

    // 5. พิมพ์ข้อความแคปชั่น
    console.log('[BinanceGiveaway] Filling post caption...');
    if (reportStatusFn) {
      await reportStatusFn(98, `กำลังกรอกข้อความแจกโค้ด...`, `ชุด (${setNumber})`, 'info');
    }

    const postComposer = fbPage.locator('div[role="dialog"] div[role="textbox"][contenteditable="true"]').first();
    await postComposer.focus();
    await postComposer.fill(caption);
    await sleep(2500);

    // -------------------------------------------------------------
    // 6. กดปุ่มครั้งที่ 1: "ถัดไป" (Next)
    // -------------------------------------------------------------
    console.log('[BinanceGiveaway] 👉 Step 1: Clicking "ถัดไป" (Next button)...');

    let nextClicked = false;
    for (let t = 0; t < 5; t++) {
      // ค้นหาปุ่มที่มีคำว่า "ถัดไป"
      const nextBtn = fbPage.locator('div[role="dialog"] div[role="button"][aria-label="ถัดไป"], div[role="dialog"] div[role="button"]:has(span:text-is("ถัดไป"))').first();
      if ((await nextBtn.count()) > 0 && (await nextBtn.isVisible().catch(() => false))) {
        const isDisabled = (await nextBtn.getAttribute('aria-disabled').catch(() => 'false')) === 'true';
        if (!isDisabled) {
          await nextBtn.click({ force: true });
          nextClicked = true;
          console.log('[BinanceGiveaway] ✅ Clicked "ถัดไป" successfully!');
          break;
        }
      }
      await sleep(1500);
    }

    if (!nextClicked) {
      // Fallback DOM evaluate สำหรับปุ่ม "ถัดไป"
      nextClicked = await fbPage.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('div[role="dialog"] div[role="button"]'));
        for (const b of buttons) {
          const l = (b.getAttribute('aria-label') || '').trim();
          const t = (b.innerText || '').trim();
          if (l === 'ถัดไป' || t === 'ถัดไป') {
            b.click();
            return true;
          }
        }
        return false;
      }).catch(() => false);
      if (nextClicked) console.log('[BinanceGiveaway] ✅ Clicked "ถัดไป" via evaluate!');
    }

    // รอให้หน้าต่างสลับเข้าสู่หน้า "การตั้งค่าโพสต์"
    console.log('[BinanceGiveaway] Waiting for "การตั้งค่าโพสต์" screen to appear...');
    await sleep(3500);

    // -------------------------------------------------------------
    // 7. กดปุ่มครั้งที่ 2: "โพสต์" (Post)
    // -------------------------------------------------------------
    console.log('[BinanceGiveaway] 👉 Step 2: Clicking final "โพสต์" (Post button)...');

    let postClicked = false;
    for (let t = 0; t < 5; t++) {
      // หาปุ่มสีฟ้าที่มีคำว่า "โพสต์" ในหน้าการตั้งค่าโพสต์
      const postBtn = fbPage.locator('div[role="dialog"] div[role="button"][aria-label="โพสต์"], div[role="dialog"] div[role="button"]:has(span:text-is("โพสต์"))').last();
      if ((await postBtn.count()) > 0 && (await postBtn.isVisible().catch(() => false))) {
        const isDisabled = (await postBtn.getAttribute('aria-disabled').catch(() => 'false')) === 'true';
        if (!isDisabled) {
          await postBtn.click({ force: true });
          postClicked = true;
          console.log('[BinanceGiveaway] 🚀 Clicked "โพสต์" button successfully!');
          break;
        }
      }
      await sleep(1500);
    }

    if (!postClicked) {
      // Fallback DOM evaluate สำหรับปุ่ม "โพสต์" ในหน้าต่างปัจจุบัน
      postClicked = await fbPage.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('div[role="dialog"] div[role="button"]'));
        for (const b of buttons) {
          const l = (b.getAttribute('aria-label') || '').trim();
          const t = (b.innerText || '').trim();
          if ((l === 'โพสต์' || t === 'โพสต์') && b.getAttribute('aria-disabled') !== 'true') {
            b.click();
            return true;
          }
        }
        return false;
      }).catch(() => false);
      if (postClicked) console.log('[BinanceGiveaway] 🚀 Clicked "โพสต์" via evaluate!');
    }

    console.log('[BinanceGiveaway] Waiting for post publication and dialog to close...');
    await sleep(6000);

    if (reportStatusFn) {
      await reportStatusFn(100, `✅ โพสต์แจกโค้ด ชุด (${setNumber}) สำเร็จ!`, `จำนวน ${codes.length} โค้ด`, 'success');
    }

    // บันทึกหมายเลขชุดล่าสุดของวันนี้ เพื่อให้รอบถัดไปรันเป็นชุดถัดไปอัตโนมัติ
    saveDailySetNumber(setNumber);

    console.log(`[BinanceGiveaway] 🎉 Completed Binance Giveaway Post Set (${setNumber})!`);
    return {
      success: true,
      setNumber,
      codesCount: codes.length,
      refLink,
    };
  } catch (err) {
    console.error('[BinanceGiveaway] ❌ Error in publishGiveawayPost:', err.message || err);
    return { success: false, error: err.message };
  }
}

// Standalone runner for manual execution & testing
if (process.argv[1] && process.argv[1].replace(/\\/g, '/').endsWith('Binance_Free-code/binance_giveaway.js')) {
  (async () => {
    console.log('============================================');
    console.log(' 🚀 Running Binance Giveaway Post (Standalone)');
    console.log('============================================\n');
    const { chromium } = await import('playwright');
    const userDataDir = path.resolve(__dirname, '../user_data');
    console.log(`Using user_data: ${userDataDir}`);

    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      channel: 'chrome',
      args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
      viewport: null
    });

    const page = context.pages().length > 0 ? context.pages()[0] : await context.newPage();
    const res = await publishGiveawayPost(page, (pct, status, detail) => {
      console.log(`[${pct}%] ${status} - ${detail}`);
    });

    console.log('\n[Standalone Finished] Result:', JSON.stringify(res, null, 2));
    await sleep(4000);
    await context.close();
    process.exit(0);
  })().catch((e) => {
    console.error('[Standalone Fatal Error]:', e);
    process.exit(1);
  });
}
