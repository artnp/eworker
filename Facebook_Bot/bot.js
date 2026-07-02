import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import crypto from 'crypto';
import readline from 'readline';
import { fileURLToPath } from 'url';

const execPromise = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const LOG_FILE = path.join(__dirname, 'bot.log');
const originalLog = console.log;
const originalError = console.error;
const originalWarn = console.warn;

function logToFile(level, ...args) {
  const timestamp = new Date().toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' });
  const message = args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ');
  const line = `[${timestamp}] [${level}] ${message}\n`;
  try { fs.appendFileSync(LOG_FILE, line); } catch (e) { }
}

console.log = (...args) => { originalLog(...args); logToFile('INFO', ...args); };
console.error = (...args) => { originalError(...args); logToFile('ERROR', ...args); };
console.warn = (...args) => { originalWarn(...args); logToFile('WARN', ...args); };

const NOTIFY_SCRIPT = path.join(__dirname, 'notify.ps1');

function showWindowsNotification(title, text, type = 'Info') {
  const titleB64 = Buffer.from(title, 'utf8').toString('base64');
  const textB64 = Buffer.from(text, 'utf8').toString('base64');
  const psCommand = `powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "${NOTIFY_SCRIPT}" -TitleB64 "${titleB64}" -TextB64 "${textB64}" -Type ${type}`;
  exec(psCommand, (err) => {
    if (err) console.warn('Windows notification failed:', err.message);
  });
}

const USER_DATA_DIR = path.join(__dirname, 'user_data');
const PROCESSED_DB_FILE = path.join(__dirname, 'processed_posts.json');
const DOWNLOADS_DIR = path.join(__dirname, 'downloads');

function ensureDownloadsDir() {
  try {
    if (!fs.existsSync(DOWNLOADS_DIR)) {
      fs.mkdirSync(DOWNLOADS_DIR, { recursive: true });
      console.log('Created downloads directory.');
    }
  } catch (e) {
    console.error('Failed to create downloads directory:', e.message);
  }
}

function clearDownloadsDir() {
  try {
    if (fs.existsSync(DOWNLOADS_DIR)) {
      const files = fs.readdirSync(DOWNLOADS_DIR);
      for (const file of files) {
        const filePath = path.join(DOWNLOADS_DIR, file);
        try {
          if (fs.statSync(filePath).isFile()) {
            fs.unlinkSync(filePath);
          }
        } catch (e) {
          console.error(`Failed to delete file ${file}:`, e.message);
        }
      }
      console.log('Cleaned up downloads directory.');
    }
  } catch (e) {
    console.error('Failed to clean downloads directory:', e.message);
  }
}

const AUTO_GROUPS_MAX = 10;
const FB_URL = 'https://www.facebook.com/groups/feed/';

const GEMINI_SLOT_COUNT = 8;
const GEMINI_ACCOUNTS = Array.from({ length: GEMINI_SLOT_COUNT }, (_, i) => `https://gemini.google.com/u/${i}/app`);

let activeGeminiAccounts = [];
let currentGeminiAccountIndex = 0;

const GEMINI_STATE_FILE = path.join(__dirname, 'gemini_state.json');
const COOLDOWNS_FILE = path.join(__dirname, 'gemini_cooldowns.json');

function loadActiveAccounts() {
  try {
    if (fs.existsSync(GEMINI_STATE_FILE)) {
      return JSON.parse(fs.readFileSync(GEMINI_STATE_FILE, 'utf8'));
    }
  } catch (e) { }
  return null;
}

function saveActiveAccounts(accounts) {
  try {
    fs.writeFileSync(GEMINI_STATE_FILE, JSON.stringify(accounts, null, 2));
  } catch (e) { }
}

let processedPosts = new Set();

function loadProcessedPosts() {
  try {
    if (fs.existsSync(PROCESSED_DB_FILE)) {
      const data = JSON.parse(fs.readFileSync(PROCESSED_DB_FILE, 'utf8'));
      if (Array.isArray(data)) processedPosts = new Set(data);
    }
  } catch (e) { }
}

function saveProcessedPosts() {
  try {
    fs.writeFileSync(PROCESSED_DB_FILE, JSON.stringify(Array.from(processedPosts), null, 2));
  } catch (e) { }
}

function hashString(str) {
  return crypto.createHash('md5').update(str).digest('hex');
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function checkGeminiAccountLogged(context, index) {
  const url = `https://gemini.google.com/u/${index}/app`;
  try {
    const page = await context.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(2000);
    const hasInput = await page.evaluate(() => {
      return document.querySelector('div.ql-editor[role="textbox"], div[contenteditable="true"][role="textbox"]') !== null;
    }).catch(() => false);
    await page.close().catch(() => { });
    return hasInput;
  } catch (e) {
    return false;
  }
}

async function detectActiveGeminiAccounts(context) {
  console.log('\n===== Auto-detecting Gemini accounts =====');
  const results = [];
  for (let i = 0; i < GEMINI_SLOT_COUNT; i++) {
    const isLogged = await checkGeminiAccountLogged(context, i);
    console.log(`  u/${i}: ${isLogged ? 'Logged in' : 'Not logged in'}`);
    if (isLogged) results.push(`https://gemini.google.com/u/${i}/app`);
  }
  console.log(`\n===== Detection Result =====`);
  console.log(`Found ${results.length} active Gemini accounts:`, results);
  console.log('================================\n');
  return results;
}

function getNextGeminiUrl() {
  if (activeGeminiAccounts.length === 0) return null;
  const url = activeGeminiAccounts[currentGeminiAccountIndex % activeGeminiAccounts.length];
  currentGeminiAccountIndex = (currentGeminiAccountIndex + 1) % activeGeminiAccounts.length;
  return url;
}

async function waitForFacebookReady(page, timeoutMs = 600000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const url = page.url();
      if (url.includes('facebook.com')) {
        const ready = await page.evaluate(() => document.querySelector('div[role="feed"], div[role="main"]') !== null).catch(() => false);
        if (ready) return true;
      }
    } catch (e) { }
    await sleep(2000);
  }
  return false;
}

async function ensurePageProfile(page) {
  const switchSelectors = [
    'div[role="button"]:has-text("Switch Now")',
    'div[role="button"]:has-text("Switch profile")',
    'div[role="button"]:has-text("Switch")',
    'div[role="button"][aria-label*="Switch"]',
    'div[role="button"]:has-text("สลับตอนนี้")',
    'div[role="button"]:has-text("สลับโปรไฟล์")',
    'div[role="button"]:has-text("สลับ")',
    'button:has-text("สลับ")',
    'button:has-text("Switch")'
  ];
  for (const selector of switchSelectors) {
    try {
      const btn = page.locator(selector).first();
      if (await btn.count() > 0 && await btn.isVisible()) {
        const text = (await btn.innerText()).trim();
        console.log(`Found switch button: "${text}" (${selector}) clicking...`);
        await btn.click({ force: true });
        await sleep(2500);
        await page.waitForNavigation({ timeout: 15000 }).catch(() => { });
        await sleep(3000);
        console.log('Switched profile successfully.');
        return true;
      }
    } catch (e) { }
  }
  console.log('No switch button found, proceeding with current profile.');
  return false;
}

// ===== Helper functions for Facebook interaction =====

async function getPostText(article) {
  try {
    const seeMoreBtn = article.locator('div[role="button"]:has-text("ดูเพิ่มเติม"), div[role="button"]:has-text("See more")');
    if (await seeMoreBtn.count() > 0 && await seeMoreBtn.isVisible()) {
      await seeMoreBtn.first().click();
      await sleep(500);
    }
  } catch (e) { }
  
  try {
    return await article.evaluate((node) => {
      // *** หาข้อความจากโครงสร้าง HTML ที่แท้จริงของ Facebook ***
      
      // 1. ลำดับความสำคัญ: หาจาก div[dir="auto"] ที่มี style="text-align: start;" ก่อน
      const allDivs = node.querySelectorAll('div[dir="auto"]');
      for (const el of allDivs) {
        const style = el.getAttribute('style') || '';
        if (style.includes('text-align: start')) {
          // ข้าม element ที่อยู่ใน link, button, navigation
          if (el.closest('a') || el.closest('button') || el.closest('[role="button"]') || 
              el.closest('nav') || el.closest('[role="navigation"]')) {
            continue;
          }
          
          const text = (el.textContent || '').trim();
          if (text && text.length > 5 && 
              !text.includes('ถูกใจ') && !text.includes('แสดงความคิดเห็น') && 
              !text.includes('แชร์') && !text.includes('นาที') && !text.includes('ชั่วโมง') &&
              !text.includes('แชร์กับ')) {
            // ลบ emoji และ clean ข้อความ
            const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').replace(/\s+/g, ' ').trim();
            if (cleanText.length > 5) {
              console.log(`✓ Found post text from style="text-align: start;": "${cleanText}"`);
              return cleanText;
            }
          }
        }
      }
      
      // 2. หาจาก data-ad-comet-preview="message" หรือ data-ad-preview="message"
      const messageElements = node.querySelectorAll('[data-ad-comet-preview="message"], [data-ad-preview="message"]');
      for (const el of messageElements) {
        const text = (el.textContent || '').trim();
        if (text && text.length > 5) {
          const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').replace(/\s+/g, ' ').trim();
          if (cleanText.length > 5) {
            console.log(`✓ Found post text from data-ad-preview: "${cleanText}"`);
            return cleanText;
          }
        }
      }
      
      // 3. หาจาก span ที่มี dir="auto" แต่ไม่อยู่ใน navigation/button
      const spanElements = node.querySelectorAll('span[dir="auto"]');
      for (const el of spanElements) {
        // ข้าม element ที่อยู่ใน link, button, navigation
        if (el.closest('a') || el.closest('button') || el.closest('[role="button"]') || 
            el.closest('nav') || el.closest('[role="navigation"]')) {
          continue;
        }
        
        const text = (el.textContent || '').trim();
        if (text && text.length > 10 && 
            !text.includes('ถูกใจ') && !text.includes('แสดงความคิดเห็น') && 
            !text.includes('แชร์') && !text.includes('นาที') && !text.includes('ชั่วโมง')) {
          const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').replace(/\s+/g, ' ').trim();
          if (cleanText.length > 5) {
            console.log(`✓ Found post text from span[dir="auto"]: "${cleanText}"`);
            return cleanText;
          }
        }
      }
      
      // 4. Fallback: หาจาก div[dir="auto"] ทั่วไป
      for (const el of allDivs) {
        if (el.closest('a') || el.closest('button') || el.closest('[role="button"]')) {
          continue;
        }
        
        const text = (el.textContent || '').trim();
        if (text && text.length > 10) {
          const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').replace(/\s+/g, ' ').trim();
          if (cleanText.length > 5 && 
              !cleanText.includes('ถูกใจ') && !cleanText.includes('แสดงความคิดเห็น') && 
              !cleanText.includes('แชร์') && !cleanText.includes('นาที')) {
            console.log(`✓ Found post text from fallback div[dir="auto"]: "${cleanText}"`);
            return cleanText;
          }
        }
      }
      
      console.warn('⚠️ No post text found with any method');
      return '';
    });
  } catch (e) {
    console.warn('Error in getPostText:', e.message);
    return '';
  }
}

async function shouldFilterPost(article) {
  try {
    return await article.evaluate((node) => {
      const spamKeywords = [
        'คิวว่าง', 'รับตัดต่อ', 'ราคาเพียง', 'สอบถามได้', 'เริ่มต้นแค่',
        'ฝากร้าน', 'เปิดรับ', 'สนใจสอบถาม', 'รับประกัน', 'สร้างรายได้',
        'สอบถามเพิ่มเติม', 'รับทำ', 'รีวิว', 'บริการ', 'เน็ตบ้าน', 'ด่วน',
        'อินเตอร์เน็ตบ้าน', 'สนใจทักแชท', 'ว่างทำให้', 'ว่างแล้ว', 'ขอส่ง', 'ให้ฟรี',
        'ภาพเคลื่อนไหว', 'vdo', 'video', 'วิดีโอ', 'วีดีโอ', 'clip', 'คลิป', '#'
      ];
      const text = node.textContent || '';

      // Check if comments are disabled (text-based)
      if (text.includes('ปิดการแสดงความคิดเห็น') || text.includes('ปิดการแสดงความคิดเห็นไว้ชั่วคราว')) {
        return { action: 'hide', reason: 'Comments disabled (text)' };
      }

      // Check if the Comment button is actually present
      const commentBtnSelectors = [
        '[aria-label*="Comment"]',
        '[aria-label*="comment"]',
        '[aria-label*="แสดงความคิดเห็น"]',
        '[aria-label*="ความคิดเห็น"]'
      ];
      let hasCommentBtn = false;
      for (const sel of commentBtnSelectors) {
        if (node.querySelector(sel)) {
          hasCommentBtn = true;
          break;
        }
      }
      // Also accept if the word "Comment" appears as a button text
      if (!hasCommentBtn) {
        const btns = node.querySelectorAll('[role="button"], button');
        for (const btn of btns) {
          const label = (btn.getAttribute('aria-label') || btn.textContent || '').toLowerCase();
          if (label.includes('comment') || label.includes('ความคิดเห็น')) {
            hasCommentBtn = true;
            break;
          }
        }
      }
      if (!hasCommentBtn) {
        return { action: 'hide', reason: 'No Comment button found (Comments disabled)' };
      }

      // Check if post already liked
      const likeBtns = node.querySelectorAll('[aria-label*="Like" i], [aria-label*="ถูกใจ" i]');
      let hasLiked = false;
      for (const btn of likeBtns) {
        const pressed = btn.getAttribute('aria-pressed');
        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
        if (pressed === 'true' || label.includes('unlike') || label.includes('เลิก') || label.includes('ลบ')) {
          hasLiked = true;
          break;
        }
      }
      if (hasLiked) {
        return { action: 'hide', reason: 'Post already liked or reacted' };
      }

      // Spam keyword check
      for (const keyword of spamKeywords) {
        if (text.includes(keyword)) {
          return { action: 'spam', reason: `Spam keyword: ${keyword}` };
        }
      }
      return { action: 'none', reason: '' };
    });
  } catch (e) {
    return { action: 'error', reason: e.message };
  }
}

async function getLargeImageUrls(article) {
  try {
    return await article.evaluate((node) => {
      const results = [];
      const seen = new Set();
      const imgs = node.querySelectorAll('img');
      for (const img of imgs) {
        const src = img.src;
        if (!src || src.startsWith('data:') || src.includes('emoji') || src.includes('static.xx.fbcdn')) continue;
        const isLarge = (img.naturalWidth >= 200 && img.naturalHeight >= 200) ||
          (img.clientWidth >= 200 && img.clientHeight >= 200);
        if (isLarge && !seen.has(src)) {
          results.push(src);
          seen.add(src);
        }
      }
      return results;
    });
  } catch (e) {
    return [];
  }
}

async function getPostUrl(article) {
  try {
    return await article.evaluate((node) => {
      // Try to find a permalink link inside the post
      const links = node.querySelectorAll('a[href*="/groups/"], a[href*="facebook.com/"]');
      for (const a of links) {
        const href = a.href || '';
        // Match group post URLs: /groups/ID/posts/ID or /permalink/
        if (/\/groups\/[\w.]+\/(posts|permalink)\//.test(href) || /facebook\.com\/permalink\//.test(href)) {
          try {
            const url = new URL(href);
            url.search = '';
            return url.toString();
          } catch (e) { return href.split('?')[0]; }
        }
      }
      // Fallback: any link with /posts/ or ?story_fbid=
      for (const a of links) {
        const href = a.href || '';
        if (href.includes('/posts/') || href.includes('story_fbid=')) {
          try {
            const url = new URL(href);
            url.search = '';
            return url.toString();
          } catch (e) { return href.split('?')[0]; }
        }
      }
      return null;
    });
  } catch (e) {
    return null;
  }
}

async function waitForFastDownload(timeoutMs = 90000) {
  const downloadsDir = path.join(process.env.USERPROFILE, 'Downloads');
  const targetFile = path.join(downloadsDir, 'complete.png');
  const start = Date.now();
  // Remove stale file first so we don't pick up an old one
  try { if (fs.existsSync(targetFile)) fs.unlinkSync(targetFile); } catch (e) { }
  console.log(`[FastDL] Waiting for ${targetFile} (timeout ${timeoutMs / 1000}s)...`);
  while (Date.now() - start < timeoutMs) {
    if (fs.existsSync(targetFile)) {
      // Wait a tiny bit to ensure the file write is complete
      await sleep(600);
      const stat = fs.statSync(targetFile);
      if (stat.size > 1000) {
        console.log(`[FastDL] ✅ Downloaded: ${targetFile} (${stat.size} bytes)`);
        return targetFile;
      }
    }
    await sleep(800);
  }
  console.warn('[FastDL] ⚠️ Timeout waiting for complete.png from Extension.');
  return null;
}

async function runPythonImageEditor(imagePath) {
  const desktopPath = path.join(process.env.USERPROFILE, 'Desktop', 'complete.png');
  const isBotMode = process.argv.includes('--bot');
  const outputName = isBotMode ? 'complete_bot.png' : 'complete.png';
  const desktopOutputPath = path.join(process.env.USERPROFILE, 'Desktop', outputName);
  try {
    const pythonScript = 'D:\\Github\\eworker\\screenshot_donate.py';
    const botFlag = isBotMode ? '--bot' : '';
    const command = `python "${pythonScript}" --donate-no-paste "${imagePath}" ${botFlag}`.trim();
    console.log(`Executing: ${command}`);
    const { stdout, stderr } = await execPromise(command, { timeout: 60000 });
    if (stderr && !stderr.includes('DeprecationWarning') && !stderr.includes('UserWarning')) {
      console.warn('Python stderr:', stderr);
    }
    console.log('Python stdout:', stdout);
    if (fs.existsSync(desktopOutputPath)) {
      const botImagePath = path.join(DOWNLOADS_DIR, `final_post_${Date.now()}.png`);
      fs.copyFileSync(desktopOutputPath, botImagePath);
      console.log(`Copied ${outputName} to: ${botImagePath}`);
      return botImagePath;
    } else if (fs.existsSync(desktopPath)) {
      const botImagePath = path.join(DOWNLOADS_DIR, `final_post_${Date.now()}.png`);
      fs.copyFileSync(desktopPath, botImagePath);
      console.log(`Copied complete.png to: ${botImagePath}`);
      return botImagePath;
    } else {
      console.error('Python output not found!');
    }
    return null;
  } catch (e) {
    console.error('Python execution error:', e.message || e);
    return null;
  }
}

function generateSmartPrompt(postText) {
  try {
    const text = postText.toLowerCase();
    
    // === การขอแก้ไขคน/สัตว์ ===
    if (text.includes('ช่วยทำให้') && (text.includes('ใหญ่') || text.includes('เล็ก'))) {
      if (text.includes('ปลา')) return 'ช่วยทำให้ปลาในภาพนี้ตัวใหญ่ขึ้นให้หน่อยครับ ให้ดูใหญ่และน่าประทับใจมากขึ้น';
      if (text.includes('คน') || text.includes('เด็ก') || text.includes('ผู้หญิง') || text.includes('ผู้ชาย')) return 'ช่วยทำให้คนในภาพนี้ดูใหญ่/สูงขึ้นให้หน่อยครับ';
      return 'ช่วยปรับขนาดให้ใหญ่ขึ้นตามที่ขอครับ';
    }
    
    // === การขอเพิ่มคน/สิ่งของ ===
    if (text.includes('เพิ่ม') || text.includes('ใส่') || text.includes('มา') && (text.includes('คน') || text.includes('สาว') || text.includes('หญิง'))) {
      if (text.includes('สาว') || text.includes('หญิง') || text.includes('ผู้หญิง')) return 'กรุณาเพิ่มผู้หญิงสวยๆ เข้าไปในภาพนี้ให้เข้ากับบรรยากาศครับ';
      if (text.includes('เด็ก')) return 'กรุณาเพิ่มเด็กๆ เข้าไปในภาพนี้ให้เข้ากับบรรยากาศครับ';
      return 'กรุณาเพิ่มคนเข้าไปในภาพนี้ให้เข้ากับบรรยากาศครับ';
    }
    
    // === การขอย้ายพื้นหลัง/สถานที่ ===
    if (text.includes('ให้อยู่ใน') || text.includes('ย้ายไป') || text.includes('เปลี่ยนเป็น')) {
      if (text.includes('สนาม') || text.includes('แอนฟิลด์')) return 'กรุณาย้ายคนในภาพนี้ไปอยู่ในสนามฟุตบอลแอนฟิลด์ครับ';
      if (text.includes('ทะเล') || text.includes('ชายหาด')) return 'กรุณาย้ายไปอยู่ที่ชายหาด/ทะเลสวยๆ ครับ';
      if (text.includes('ป่า') || text.includes('ธรรมชาติ')) return 'กรุณาเปลี่ยนพื้นหลังเป็นป่า/ธรรมชาติสวยๆ ครับ';
      return 'กรุณาเปลี่ยนพื้นหลังตามที่ขอในโพสต์ครับ';
    }
    
    // === การขอแต่งรูป/ปรับปรุงทั่วไป ===
    if (text.includes('แต่งรูป') || text.includes('แก้รูป') || text.includes('ช่วยแต่ง')) {
      return 'กรุณาแต่งรูปภาพนี้ให้สวยงาม ปรับสี แสง เงา ให้ดูสวยและน่าดูมากขึ้นครับ';
    }
    
    // === การขอเพิ่มพ่อแม่ที่เสียชีวิต ===
    if ((text.includes('พ่อ') || text.includes('แม่')) && (text.includes('เสีย') || text.includes('เสียชีวิต') || text.includes('เสียก่อน'))) {
      return 'กรุณาเพิ่มพ่อและแม่ที่เสียชีวิตแล้วเข้าไปในภาพนี้ด้วยครับ ให้ดูอบอุ่นและมีความหมาย';
    }
    
    // === การขอลบสิ่งของ ===
    if (text.includes('ลบ') || text.includes('เอาออก') || text.includes('ไม่ต้องการ')) {
      return 'กรุณาลบสิ่งที่ไม่ต้องการออกจากภาพนี้ครับ และทำให้ภาพดูเรียบร้อยสวยงาม';
    }
    
    // === กรณีอื่นๆ ทั่วไป ===
    if (text.includes('ช่วย') || text.includes('ทำให้') || text.includes('แก้')) {
      return `${postText.trim()}\nกรุณาทำตามที่ขอในข้อความข้างต้นครับ`;
    }
    
    // === Default fallback ===
    return `${postText.trim()}\nกรุณาช่วยแก้ไข/ปรับปรุงภาพนี้ตามคำขอข้างต้นครับ`;
    
  } catch (e) {
    // ถ้า error ก็ใช้แบบเดิม
    return `${postText.trim()}\n(จงทำภาพ)`;
  }
}

async function processWithGemini(page, imagePaths, postText, geminiUrl) {
  try {
    await page.bringToFront().catch(() => { });
    const currentUrl = page.url();
    if (!currentUrl.startsWith(geminiUrl)) {
      console.log(`Navigating to Gemini: ${geminiUrl}`);
      await page.goto(geminiUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await sleep(1500);
    } else {
      console.log(`Already on Gemini page: ${geminiUrl}, skipping navigation.`);
      await sleep(200);
    }
    const inputSelectors = [
      'div.ql-editor[role="textbox"]',
      'div.ql-editor.textarea',
      'div[contenteditable="true"][role="textbox"]',
      'rich-textarea div[contenteditable="true"]',
      'div[contenteditable="true"]'
    ];
    let inputFound = false;
    let inputSelector = '';
    for (const sel of inputSelectors) {
      try {
        const el = page.locator(sel).first();
        if (await el.count() > 0 && await el.isVisible().catch(() => false)) {
          inputSelector = sel;
          inputFound = true;
          break;
        }
      } catch (e) { }
    }
    if (!inputFound) {
      console.error('Gemini input area not found.');
      return null;
    }
    console.log(`Found Gemini input: ${inputSelector}`);

    if (imagePaths.length > 0) {
      // Primary: use file input element directly
      const attachBtnSelectors = [
        'button[aria-label="Attach files"]',
        'button[aria-label*="attach"]',
        'button[aria-label*="แนบ"]',
        'div[role="button"][aria-label*="Attach"]',
        'div[role="button"][aria-label*="attach"]',
        'button[aria-label*="Upload"]',
        'div[role="button"]:has-text("Attach")'
      ];
      let fileUploaded = false;
      // Upload all images via file input (setInputFiles accepts array)
      const fi = page.locator('input[type="file"]').first();
      if (await fi.count() > 0) {
        try {
          await fi.setInputFiles(imagePaths);
          await sleep(3000);
          fileUploaded = true;
          console.log(`Uploaded ${imagePaths.length} images to Gemini via file input.`);
        } catch (e) {
          console.warn('File input upload failed:', e.message);
        }
      }
      if (!fileUploaded) {
        // Fallback: click attach button then set files
        for (const btnSel of attachBtnSelectors) {
          try {
            const btn = page.locator(btnSel).first();
            if (await btn.count() > 0 && await btn.isVisible().catch(() => false)) {
              await btn.click({ force: true });
              await sleep(1500);
              break;
            }
          } catch (e) { }
        }
        const fi2 = page.locator('input[type="file"]').first();
        if (await fi2.count() > 0) {
          try {
            await fi2.setInputFiles(imagePaths);
            await sleep(3000);
            fileUploaded = true;
            console.log(`Uploaded ${imagePaths.length} images to Gemini via file input (fallback click).`);
          } catch (e) {
            console.warn('File input upload (click fallback) failed:', e.message);
          }
        }
      }
      // Fallback: paste method — loop all images
      if (!fileUploaded) {
        let allPasted = true;
        for (let i = 0; i < imagePaths.length; i++) {
          const imageBuffer = fs.readFileSync(imagePaths[i]);
          const base64Str = imageBuffer.toString('base64');
          const mimeType = imagePaths[i].endsWith('.png') ? 'image/png' : 'image/jpeg';
          const pasteSuccess = await page.evaluate(async ({ base64, mimeType, selector }) => {
            const inputEl = document.querySelector(selector);
            if (!inputEl) return false;
            inputEl.focus();
            const dt = new DataTransfer();
            try {
              const resp = await fetch(`data:${mimeType};base64,${base64}`);
              const blob = await resp.blob();
              // Add white padding below image to push watermark out of visible area
              const paddedBlob = await new Promise((resolve) => {
                const img = new Image();
                const url = URL.createObjectURL(blob);
                const fallback = () => { URL.revokeObjectURL(url); resolve(blob); };
                const timer = setTimeout(fallback, 5000);
                img.onload = () => {
                  clearTimeout(timer);
                  const pad = Math.max(300, Math.floor(img.height * 0.15));
                  const c = document.createElement('canvas');
                  c.width = img.width;
                  c.height = img.height + pad;
                  const ctx = c.getContext('2d');
                  ctx.fillStyle = 'white';
                  ctx.fillRect(0, 0, c.width, c.height);
                  ctx.drawImage(img, 0, 0);
                  URL.revokeObjectURL(url);
                  c.toBlob((p) => { resolve(p || blob); }, 'image/png');
                };
                img.onerror = () => { clearTimeout(timer); fallback(); };
                img.src = url;
              });
              const ext = mimeType === 'image/png' ? 'png' : 'jpg';
              const file = new File([paddedBlob], `image_${Date.now()}.${ext}`, { type: 'image/png' });
              dt.items.add(file);
            } catch (e) { return false; }
            try {
              const pasteEvent = new ClipboardEvent('paste', {
                bubbles: true, cancelable: true, composed: true
              });
              Object.defineProperty(pasteEvent, 'clipboardData', {
                value: dt, configurable: true, enumerable: true, writable: false
              });
              inputEl.dispatchEvent(pasteEvent);
            } catch (e) { return false; }
            return true;
          }, { base64: base64Str, mimeType, selector: inputSelector });
          if (pasteSuccess) {
            console.log(`Pasted image ${i + 1}/${imagePaths.length} into Gemini (fallback).`);
            await sleep(1500);
          } else {
            console.warn(`Paste fallback failed for image ${i + 1}.`);
            allPasted = false;
            break;
          }
        }
        if (allPasted) {
          await sleep(3000);
          fileUploaded = true;
        }
      }
      if (!fileUploaded) {
        console.error('Could not upload images to Gemini.');
        return null;
      }
    }

    const promptText = generateSmartPrompt(postText.trim());
    const textInput = page.locator(inputSelector).first();
    await textInput.click();
    await sleep(300);
    await textInput.fill(promptText);
    console.log('Typed prompt text:', promptText.substring(0, 100) + '...');
    await sleep(500);
    const sendBtnSelectors = [
      'button[aria-label="ส่งข้อความ"]',
      'button[aria-label="Send"]',
      'button[data-at="send"]',
      'button[mat-icon-button]'
    ];
    let sent = false;
    for (const sel of sendBtnSelectors) {
      try {
        const btn = page.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible().catch(() => false)) {
          await btn.click({ force: true });
          sent = true;
          break;
        }
      } catch (e) { }
    }
    if (!sent) {
      await textInput.press('Enter');
    }
    console.log('Sent message to Gemini. Capturing result...');

    // --- PRIMARY: Wait for button as indicator, then capture via canvas directly ---
    // We DON'T click the button (causes window close & download never completes).
    // Instead we grab the image from the DOM via canvas.
    let captured = false;
    let retryCount = 0;
    const maxRetries = 2;

    while (!captured && retryCount <= maxRetries) {
      try {
        await page.locator('.fast-dl-button').first().waitFor({ state: 'visible', timeout: 90000 });
        console.log('[FastDL] Image ready, capturing via canvas...');
        captured = true;
      } catch (e) {
        console.warn(`[FastDL] Fast Download button not found (attempt ${retryCount + 1}/${maxRetries + 1}):`, e.message);
        
        if (retryCount < maxRetries) {
          console.log('[FastDL] Trying refresh Gemini...');
          
          // คลิกปุ่ม refresh เพื่อลองใหม่
          try {
            const refreshBtn = page.locator('mat-icon[data-mat-icon-name="refresh"]').first();
            if (await refreshBtn.count() > 0 && await refreshBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
              await refreshBtn.click({ force: true });
              console.log('[FastDL] Clicked refresh button');
              await sleep(3000); // รอ Gemini ประมวลผลใหม่
              retryCount++;
              continue;
            } else {
              console.warn('[FastDL] Refresh button not found');
            }
          } catch (refreshError) {
            console.warn('[FastDL] Refresh button click failed:', refreshError.message);
          }
        }
        
        if (retryCount >= maxRetries) {
          console.warn('[FastDL] Max retries reached, trying canvas anyway');
          break;
        }
        retryCount++;
      }
    }
    // Capture the parent image of the Fast Download button, or any large image
    const dataUrl = await page.evaluate(() => {
      // Try parent of Fast Download button first
      const btn = document.querySelector('.fast-dl-button');
      if (btn) {
        const container = btn.parentElement;
        if (container) {
          const img = container.querySelector('img');
          if (img && img.naturalWidth) {
            try {
              const c = document.createElement('canvas');
              c.width = img.naturalWidth;
              c.height = img.naturalHeight;
              c.getContext('2d').drawImage(img, 0, 0);
              return c.toDataURL('image/png');
            } catch (e) { /* canvas tainted */ }
          }
        }
      }
      // Fallback: find largest image on page
      const imgs = Array.from(document.querySelectorAll('img'));
      const canvas = document.createElement('canvas');
      for (const img of imgs) {
        if (img.naturalWidth > 200 && img.naturalHeight > 200 && !img.src.includes('emoji') && !img.closest('nav, [role="navigation"]')) {
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          canvas.getContext('2d').drawImage(img, 0, 0);
          return canvas.toDataURL('image/png');
        }
      }
      return null;
    }).catch(() => null);
    if (dataUrl && dataUrl.startsWith('data:image/png;base64,')) {
      const destPath = path.join(DOWNLOADS_DIR, `gemini_result_${Date.now()}.png`);
      fs.writeFileSync(destPath, Buffer.from(dataUrl.replace(/^data:image\/png;base64,/, ''), 'base64'));
      console.log(`[FastDL] Captured result: ${destPath}`);
      return destPath;
    }
    console.error('[FastDL] Could not capture Gemini result.');
    return null;
  } catch (e) {
    console.error('Error in processWithGemini:', e.message || e);
    if (e.message && (e.message.includes('timeout') || e.message.includes('closed'))) {
      activeGeminiAccounts = activeGeminiAccounts.filter(url => url !== geminiUrl);
      saveActiveAccounts(activeGeminiAccounts);
    }
    return null;
  }
}

async function postComment(article, imagePath) {
  try {
    const page = article.page();

    // scroll article กลับเข้า viewport ก่อนทุกอย่าง
    await article.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => {});
    await sleep(1000);
    
    // ตรวจสอบสถานะของโพสต์ก่อน
    console.log('=== POST STATUS CHECK ===');
    const postStatus = await article.evaluate((node) => {
      const text = node.textContent || '';
      
      // ตรวจสอบว่าโพสต์ถูกลบหรือไม่
      if (text.includes('เนื้อหานี้ไม่พร้อมใช้งาน') || 
          text.includes('This content isn\'t available') ||
          text.includes('โพสต์นี้ไม่พร้อมใช้งาน')) {
        return 'deleted';
      }
      
      // ตรวจสอบว่าปิดคอมเมนต์หรือไม่
      if (text.includes('ปิดการแสดงความคิดเห็น') || 
          text.includes('Comments are turned off') ||
          text.includes('ไม่สามารถแสดงความคิดเห็น')) {
        return 'comments_disabled';
      }
      
      return 'normal';
    });
    
    console.log(`Post status: ${postStatus}`);
    
    if (postStatus === 'deleted') {
      console.log('Post was deleted, skipping...');
      return { success: false, reason: 'post_deleted' };
    }
    
    if (postStatus === 'comments_disabled') {
      console.log('Comments are disabled for this post, skipping...');
      return { success: false, reason: 'comments_disabled' };
    }

    // ฟังก์ชันหา composer — ค้นทั้งใน article และ page-wide (ปรับปรุงใหม่)
    async function findComposer() {
      // รูปแบบการค้นหา composer ที่หลากหลายขึ้น
      const composerSelectors = [
        // ใน article ก่อน - comment textbox
        'div[role="textbox"][contenteditable="true"][aria-label*="ความคิดเห็น"]',
        'div[role="textbox"][contenteditable="true"][aria-label*="comment"]',
        'div[role="textbox"][contenteditable="true"][aria-label*="Comment"]',
        'div[role="textbox"][contenteditable="true"][aria-placeholder*="ความคิดเห็น"]',
        'div[role="textbox"][contenteditable="true"][aria-placeholder*="comment"]',
        
        // ทั่วไปใน article
        'div[role="textbox"][contenteditable="true"]',
        'textarea[placeholder*="ความคิดเห็น"]',
        'textarea[placeholder*="comment"]',
        'textarea[aria-label*="comment"]',
        
        // Form elements
        'form div[role="textbox"][contenteditable="true"]',
        'form textarea',
        
        // Fallback - ใช้ data attributes
        'div[contenteditable="true"][data-lexical-editor]',
        'div[contenteditable="true"][data-testid*="comment"]'
      ];

      // 1. ค้นใน article ก่อน
      for (const sel of composerSelectors) {
        try {
          const inArticle = article.locator(sel);
          const aCount = await inArticle.count();
          for (let i = 0; i < aCount; i++) {
            const c = inArticle.nth(i);
            if (await c.isVisible({ timeout: 500 }).catch(() => false)) {
              console.log(`Found composer in article: ${sel}`);
              return c;
            }
          }
        } catch (e) { }
      }
      
      // 2. ค้น page-wide
      for (const sel of composerSelectors) {
        try {
          const pageBoxes = page.locator(sel);
          const pCount = await pageBoxes.count();
          for (let i = 0; i < pCount; i++) {
            const c = pageBoxes.nth(i);
            if (await c.isVisible({ timeout: 500 }).catch(() => false)) {
              // ตรวจสอบว่าใกล้ article หรือไม่
              const isNearArticle = await c.evaluate((el, articleEl) => {
                const rect1 = el.getBoundingClientRect();
                const rect2 = articleEl.getBoundingClientRect();
                const distance = Math.abs(rect1.top - rect2.bottom);
                return distance < 500; // ห่างไม่เกิน 500px
              }, await article.elementHandle()).catch(() => true);
              
              if (isNearArticle) {
                console.log(`Found composer on page: ${sel}`);
                return c;
              }
            }
          }
        } catch (e) { }
      }
      return null;
    }

    let composer = await findComposer();

    // ถ้ายังไม่มี composer ให้คลิก Comment button
    if (!composer) {
      const commentBtnSelectors = [
        'div[role="button"][aria-label*="แสดงความคิดเห็น"]',
        'div[role="button"][aria-label*="Comment"]', 
        'div[role="button"][aria-label*="comment"]',
        '[role="button"]:has-text("ความคิดเห็น")',
        '[role="button"]:has-text("Comment")',
        'span[role="button"]:has-text("ความคิดเห็น")',
        // เพิ่ม selectors สำหรับปุ่ม comment ที่อาจจะแตกต่าง
        'div[aria-label*="แสดงความคิดเห็น"]',
        'div[aria-label*="Comment"][role="button"]',
        'div[data-testid*="comment"]'
      ];
      
      let clicked = false;
      for (const sel of commentBtnSelectors) {
        try {
          const btn = article.locator(sel).first();
          if (await btn.count() > 0 && await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
            await btn.click({ force: true });
            console.log(`Clicked comment button: ${sel}`);
            clicked = true;
            break;
          }
        } catch (e) {
          console.warn(`Failed to click ${sel}: ${e.message}`);
        }
      }
      
      if (clicked) {
        await sleep(2000); // รอนานขึ้น
        
        // ลอง scroll ดู เผื่อ comment section อยู่ล่างมาก
        await article.evaluate(el => {
          el.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }).catch(() => {});
        await sleep(1000);
        
        composer = await findComposer();
      }
    }

    // รอ composer ปรากฏสูงสุด 20 วิ (เพิ่มจาก 15 วิ)
    if (!composer) {
      console.log('Waiting for composer to appear...');
      const startWait = Date.now();
      while (Date.now() - startWait < 20000) {
        composer = await findComposer();
        if (composer) {
          console.log('Composer found after waiting!');
          break;
        }
        
        // ลอง scroll และคลิก comment อีกครั้งทุก 5 วินาที
        if ((Date.now() - startWait) % 5000 < 500) {
          console.log('Retrying comment button click...');
          try {
            const retryBtn = article.locator('[role="button"][aria-label*="ความคิดเห็น"], [role="button"][aria-label*="Comment"]').first();
            if (await retryBtn.count() > 0) {
              await retryBtn.click({ force: true });
              await sleep(1000);
            }
          } catch (e) { }
        }
        
        await sleep(500);
      }
    }

    if (!composer) {
      // พิมพ์ข้อมูล debug ช่วยวินิจฉัย
      console.log('=== COMPOSER DEBUG INFO ===');
      
      try {
        // ดู elements ที่มีอยู่ใน page
        const allTextboxes = await page.locator('[role="textbox"]').count();
        const allContenteditable = await page.locator('[contenteditable="true"]').count();
        const allForms = await page.locator('form').count();
        const allTextareas = await page.locator('textarea').count();
        
        console.log(`Found elements: textbox=${allTextboxes}, contenteditable=${allContenteditable}, form=${allForms}, textarea=${allTextareas}`);
        
        // ตรวจสอบว่ามี comment section หรือไม่
        const hasCommentSection = await page.evaluate(() => {
          const keywords = ['comment', 'ความคิดเห็น', 'แสดงความคิดเห็น'];
          const allElements = document.querySelectorAll('*');
          let found = 0;
          for (const el of allElements) {
            const text = (el.textContent || '').toLowerCase();
            const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
            for (const kw of keywords) {
              if (text.includes(kw.toLowerCase()) || ariaLabel.includes(kw.toLowerCase())) {
                found++;
                break;
              }
            }
          }
          return found;
        });
        console.log(`Comment-related elements found: ${hasCommentSection}`);
        
      } catch (e) {
        console.log(`Debug info error: ${e.message}`);
      }
      
      console.log('========================');
      console.log('Comment composer not found.');
      return { success: false, reason: 'composer_not_found' };
    }

    // --- ใช้วิธี Ctrl+V (Paste) ในการอัพโหลดภาพ (ไม่คลิก icon รูป) ---
    console.log('Uploading image to Facebook comment via Ctrl+V...');
    let imageUploaded = false;

    try {
      // 1. คัดลอกภาพไปยัง clipboard ด้วย PowerShell
      const psCmd = `powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('${imagePath.replace(/\\/g, '\\\\')}'))"`;
      await execPromise(psCmd, { timeout: 10000 });
      console.log('Image copied to clipboard.');
      
      // 2. คลิกที่ composer และกด Ctrl+V
      await composer.click({ force: true });
      await sleep(400);
      await page.keyboard.press('Control+v');
      await sleep(3000); // รอให้ Facebook โหลดภาพ
      
      // 3. ตรวจสอบว่าภาพอัพโหลดแล้วหรือยัง
      const uploaded = await page.evaluate(() => {
        return !!(document.querySelector('div[role="progressbar"], img[src*="blob:"], div[data-type="image"], img[alt*="รูปภาพ"]'));
      }).catch(() => false);
      
      imageUploaded = uploaded;
      if (imageUploaded) {
        console.log('Image uploaded via Ctrl+V successfully.');
      } else {
        console.warn('Ctrl+V executed but no upload indicator found.');
      }
    } catch (e) {
      console.error('Clipboard paste failed:', e.message);
    }

    if (!imageUploaded) {
      console.log('Could not upload image to comment.');
      return { success: false };
    }

    const promoMessages = [
      '✅ทำให้นะ',
      '✅ช่วยเหลือกัน',
      '✅ทำให้ฟรี'
    ];
    const promoText = promoMessages[Math.floor(Math.random() * promoMessages.length)];
    await composer.click();
    await sleep(300);
    await composer.fill(promoText);
    await sleep(500);
    
    // *** วิธีใหม่: คลิก Submit button แทน Enter เพื่อไม่ให้ modal ปิด ***
    let commentPosted = false;
    
    // 1. ลองหาปุ่ม Submit/Post button ใกล้ composer
    const submitBtnSelectors = [
      'div[role="button"]:has-text("โพสต์")',
      'div[role="button"]:has-text("Post")',
      'button[type="submit"]',
      'div[role="button"][aria-label*="โพสต์"]',
      'div[role="button"][data-testid*="submit"]'
    ];
    
    for (const sel of submitBtnSelectors) {
      try {
        const btn = page.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
          // ตรวจสอบว่าปุ่มอยู่ใกล้ composer หรือไม่
          const isNear = await btn.evaluate((el, compEl) => {
            const btnRect = el.getBoundingClientRect();
            const compRect = compEl.getBoundingClientRect();
            return Math.abs(btnRect.top - compRect.top) < 500 && Math.abs(btnRect.left - compRect.left) < 500;
          }, await composer.elementHandle()).catch(() => true);
          
          if (isNear) {
            // ก่อนคลิก ลองกด Ctrl+Enter ก่อน เนื่องจาก Facebook ใช้ shortcut นี้
            await composer.press('Control+Enter');
            await sleep(2000);
            commentPosted = true;
            console.log('Posted comment via Ctrl+Enter keyboard shortcut');
            break;
          }
        }
      } catch (e) { }
    }
    
    // 2. ถ้า Ctrl+Enter ไม่ได้ผล ลองกด Tab แล้ว Enter (navigate ไปปุ่ม submit)
    if (!commentPosted) {
      try {
        await composer.press('Tab');
        await sleep(300);
        // ตรวจสอบว่า focus ไปที่ปุ่ม submit หรือไม่
        const focusedEl = await page.evaluate(() => document.activeElement.getAttribute('aria-label') || document.activeElement.tagName);
        console.log(`Focused element: ${focusedEl}`);
        
        // กด Enter บนปุ่ม submit
        await page.keyboard.press('Enter');
        await sleep(2000);
        commentPosted = true;
        console.log('Posted comment via Tab+Enter');
      } catch (e) {
        console.warn('Tab+Enter failed:', e.message);
      }
    }
    
    // 3. Fallback: ใช้ Enter โดยตรง (แม้ว่าอาจปิด modal)
    if (!commentPosted) {
      try {
        await composer.press('Enter');
        await sleep(2000);
        commentPosted = true;
        console.log('Posted comment via Enter (fallback)');
      } catch (e) {
        console.warn('Enter posting failed:', e.message);
      }
    }
    
    console.log('✅ Comment posted (keeping modal open for URL extraction)');

    // *** CRITICAL: ห้ามปิด Modal/Dialog หรือกด ESC ***
    // *** ต้องให้โพสต์เปิดอยู่เพื่อเอา URL comment ได้ ***
    console.log('*** KEEPING POST OPEN - DO NOT CLOSE MODAL ***');
    
    // ป้องกันการกด ESC โดยบังเอิญ
    try {
      await page.evaluate(() => {
        // Override ESC key behavior ชั่วคราว
        document.addEventListener('keydown', (e) => {
          if (e.key === 'Escape' || e.keyCode === 27) {
            console.log('[BLOCKED] ESC key prevented to keep post open');
            e.preventDefault();
            e.stopPropagation();
          }
        }, { once: false, capture: true });
      });
    } catch (e) { }

    return { success: true, promoText };
  } catch (e) {
    console.error('Error posting comment:', e.message || e);
    return { success: false };
  }
}

async function likePost(article) {
  try {
    const page = article.page();
    const likeSelectors = [
      'div[role="button"][aria-label*="Like"]',
      'div[role="button"][aria-label*="like"]',
      'div[role="button"][aria-label*="ถูกใจ"]',
      'span[role="button"]:has-text("Like")',
      'span[role="button"]:has-text("ถูกใจ")'
    ];
    // ค้นหาใน article scope เท่านั้น (ไม่ใช้ global)
    for (const sel of likeSelectors) {
      try {
        const btn = article.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
          const ariaPressed = await btn.getAttribute('aria-pressed').catch(() => 'false');
          const ariaLabel = (await btn.getAttribute('aria-label').catch(() => '') || '').toLowerCase();
          const isPressed = ariaPressed === 'true' || ariaLabel.includes('unlike') || ariaLabel.includes('เลิก') || ariaLabel.includes('ลบ');
          if (isPressed) {
            console.log('Post already liked.');
            return true;
          }
          // ใช้ click ปกติ (ไม่ force) เพื่อให้ Playwright ตรวจ interactability จริงๆ
          await btn.scrollIntoViewIfNeeded().catch(() => {});
          await btn.click({ timeout: 5000 });
          await sleep(1000);
          console.log('Liked post.');
          return true;
        }
      } catch (e) { }
    }
    console.log('Like button not found in article scope.');
    return false;
  } catch (e) {
    console.error('Error liking post:', e.message || e);
    return false;
  }
}

async function closeFacebookModal(page) {
  try {
    const closeSelectors = [
      // Group rules / "Got it" dialogs
      'div[role="button"]:has-text("เข้าใจแล้ว")',
      'div[role="button"]:has-text("Got it")',
      'div[role="button"]:has-text("OK")',
      'div[role="button"]:has-text("ตกลง")',
      'div[role="button"]:has-text("Dismiss")',
      'div[role="button"]:has-text("ยกเลิก")',
      // Standard close buttons
      'div[role="button"][aria-label*="Close"]',
      'div[role="button"][aria-label*="close"]',
      'div[role="button"][aria-label*="ปิด"]',
      'button[aria-label*="Close"]',
      'button[aria-label*="ปิด"]',
      'button:has-text("Close")',
      'button:has-text("ปิด")'
    ];
    let closed = false;
    for (const sel of closeSelectors) {
      try {
        const btn = page.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 500 }).catch(() => false)) {
          await btn.click({ force: true });
          await sleep(600);
          closed = true;
        }
      } catch (e) { }
    }
    return closed;
  } catch (e) { }
  return false;
}

async function shareViaOwnPost(fbPage, article) {
  try {
    const page = article.page(); // FIX: ต้อง define page ก่อน

    // ขั้นตอนที่ 1: หา comment timestamp link (ลิ้งค์วันที่) ใต้ comment ที่เพิ่งโพสต์
    // *** ไม่ต้องคลิก comment button ซ้ำ เพราะคลิกไปแล้วใน postComment ***
    let commentUrl = null;
    try {
      // รอให้ FB render comment นานขึ้น
      await sleep(5000); // เพิ่มจาก 3000

      // scroll เพื่อให้ comment section lazy-load
      await article.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => {});
      await sleep(1500);

      // ดึง link จาก timestamp ของ comment ล่าสุด
      // ค้นทั้ง page และทั้ง article เพราะ FB render comments section นอก article DOM
      const allCommentLinks = await page.evaluate(() => {
        // หา timestamp links หลายรูปแบบ
        const selectors = [
          'a[href*="comment_id"]',
          'a[href*="/posts/"][href*="comment"]',
          'a[href*="story_fbid"][href*="comment"]'
        ];
        
        let allLinks = [];
        selectors.forEach(sel => {
          const links = Array.from(document.querySelectorAll(sel));
          links.forEach(a => {
            const href = a.href;
            if (href && (href.includes('comment_id') || href.includes('comment'))) {
              allLinks.push({
                href: href,
                text: a.textContent.trim(),
                rect: a.getBoundingClientRect()
              });
            }
          });
        });
        
        // เรียงตาม timestamp (หา links ที่มี text เป็นเวลา)
        allLinks = allLinks.filter(link => {
          const text = link.text.toLowerCase();
          return text.includes('วัน') || text.includes('ชั่วโมง') || 
                 text.includes('นาที') || text.includes('วินาที') ||
                 text.includes('day') || text.includes('hour') || 
                 text.includes('min') || text.includes('sec') ||
                 /\d+\s*(วัน|ชั่วโมง|นาที|h|m|s)/.test(text);
        });
        
        return allLinks.map(l => l.href);
      });
      
      console.log(`[Share] Found ${allCommentLinks.length} comment timestamp links`);
      
      if (allCommentLinks.length > 0) {
        // เอาอันสุดท้าย = comment ที่โพสต์ล่าสุด
        const rawHref = allCommentLinks[allCommentLinks.length - 1];
        try {
          const url = new URL(rawHref);
          const commentId = url.searchParams.get('comment_id');
          url.search = '';
          if (commentId) url.searchParams.set('comment_id', commentId);
          commentUrl = url.toString();
        } catch {
          const cidMatch = rawHref.match(/comment_id=([^&]+)/);
          commentUrl = rawHref.split('?')[0] + (cidMatch ? `?comment_id=${cidMatch[1]}` : '');
        }
        console.log(`[Share] Found comment URL: ${commentUrl}`);
      }
    } catch (e) {
      console.warn('[Share] Could not extract comment URL:', e.message);
    }

    if (!commentUrl) {
      console.warn('[Share] No comment URL found, skipping share.');
      return { success: false, reason: 'no_comment_url' };
    }

    // ขั้นตอนที่ 2: ไปหน้า facebook.com/me
    console.log('[Share] Navigating to facebook.com/me...');
    await fbPage.goto('https://www.facebook.com/me', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await sleep(2500);
    await closeFacebookModal(fbPage);
    await sleep(500);

    // ขั้นตอนที่ 3: คลิกกล่อง "คุณกำลังคิดอะไรอยู่" บนหน้า profile
    // ต้องหา composer ที่อยู่ใน section ของ profile ไม่ใช่ comment box
    const composerBtnSelectors = [
      'div[role="button"][aria-label*="สร้างโพสต์"]',
      'div[role="button"][aria-label*="Create post"]',
      'div[role="button"]:has-text("คุณกำลังคิดอะไรอยู่")',
      'div[role="button"]:has-text("What\'s on your mind")',
      // aria-placeholder บน textbox หน้า profile (ไม่ใช่ comment)
      'div[aria-placeholder="คุณกำลังคิดอะไรอยู่"]',
      'div[aria-placeholder*="mind"]'
    ];
    let composerOpened = false;
    for (const sel of composerBtnSelectors) {
      try {
        const btn = fbPage.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await btn.click({ force: true });
          composerOpened = true;
          console.log(`[Share] Opened composer via: ${sel}`);
          break;
        }
      } catch (e) { }
    }
    if (!composerOpened) {
      console.warn('[Share] Could not open post composer.');
      return { success: false, reason: 'composer_not_opened' };
    }
    await sleep(2000);

    // ขั้นตอนที่ 4: หา textbox ใน dialog "สร้างโพสต์" โดยเฉพาะ ไม่ใช่ comment box
    // dialog role="dialog" aria-label="สร้างโพสต์"
    const dialogTextbox = fbPage.locator('div[role="dialog"] div[role="textbox"][contenteditable="true"]').first();
    let textbox = null;
    if (await dialogTextbox.count() > 0 && await dialogTextbox.isVisible({ timeout: 3000 }).catch(() => false)) {
      textbox = dialogTextbox;
      console.log('[Share] Found textbox inside dialog.');
    } else {
      // fallback: หา textbox ที่มี aria-placeholder ว่า "คุณกำลังคิดอะไรอยู่"
      const placeholderBox = fbPage.locator('div[aria-placeholder*="คุณกำลังคิดอะไรอยู่"], div[aria-placeholder*="mind"]').first();
      if (await placeholderBox.count() > 0 && await placeholderBox.isVisible({ timeout: 2000 }).catch(() => false)) {
        textbox = placeholderBox;
        console.log('[Share] Found textbox via aria-placeholder.');
      }
    }
    if (!textbox) {
      console.warn('[Share] Textbox not found inside composer dialog.');
      return { success: false, reason: 'textbox_not_found' };
    }

    await textbox.click({ force: true });
    await sleep(300);

    // === ขั้นตอนที่ 1: วาง URL ก่อนเพื่อเช็คว่ามีลิ้งก์ขึ้นหรือไม่ ===
    console.log('[Share] Step 1: Posting URL to check link preview...');
    await fbPage.evaluate((url) => document.execCommand('insertText', false, url), commentUrl);
    await sleep(3500); // รอ Facebook โหลด link preview

    // เช็คว่ามี link preview ขึ้นมาหรือไม่
    const hasPreview = await fbPage.evaluate(() => {
      // หา element ที่แสดง link preview
      const previews = document.querySelectorAll('[role="dialog"] a[href], [role="dialog"] div[data-testid*="link"], [role="dialog"] img[src*="facebook.com"], [role="dialog"] div:has(img)');
      return previews.length > 0;
    }).catch(() => false);

    if (hasPreview) {
      console.log('[Share] ✅ Link preview detected! Proceeding to replace with message...');
    } else {
      console.log('[Share] ⚠️ No link preview detected, but continuing...');
    }

    // === ขั้นตอนที่ 2: ลบ URL และใส่ข้อความใหม่ ===
    console.log('[Share] Step 2: Replacing URL with promotional message...');
    
    // เลือกข้อความทั้งหมดและลบ
    await textbox.click({ force: true });
    await sleep(200);
    await fbPage.keyboard.press('Control+a');
    await sleep(200);
    await fbPage.keyboard.press('Delete');
    await sleep(500);

    // === ขั้นตอนที่ 3: ใส่ข้อความสุ่ม + hashtag แบบใหม่ ===
    const shareTexts = [
      '✅ตัดต่อเสร็จแล้วครับ\n\n- สนใจทักแชท【 60฿】ราคาเดียวไม่คิดเพิ่ม\n\n**#หาคนแก้ภาพด่วน** **#ปรับหน้าชัดหลังเบลอ** **#ช่วยแก้ไขรูป** **#แก้ภาพตัดต่อโป๊ะ**',
      '✅แก้ไขรูปเสร็จแล้วครับ\n\n- สนใจทักแชท【 60฿】ราคาเดียวไม่คิดเพิ่ม\n\n**#หาคนแก้ภาพด่วน** **#ตัดต่อภาพโปร** **#ช่วยแก้ไขรูป** **#แก้ภาพราคาดี**',
      '✅รีทัชรูปเรียบร้อยครับ\n\n- สนใจทักแชท【 60฿】ราคาเดียวไม่คิดเพิ่ม\n\n**#หาคนแก้ภาพด่วน** **#รับตัดต่อรูป** **#ช่วยแก้ไขรูป** **#แก้ภาพสวยๆ**',
      '✅ปรับแต่งภาพเสร็จแล้วครับ\n\n- สนใจทักแชท【 60฿】ราคาเดียวไม่คิดเพิ่ม\n\n**#หาคนแก้ภาพด่วน** **#แต่งภาพสวย** **#ช่วยแก้ไขรูป** **#รีทัชรูปโปร**',
      '✅แต่งรูปเรียบร้อยครับ\n\n- สนใจทักแชท【 60฿】ราคาเดียวไม่คิดเพิ่ม\n\n**#หาคนแก้ภาพด่วน** **#ปรับภาพชัด** **#ช่วยแก้ไขรูป** **#ตัดต่อรูปภาพ**'
    ];
    const shareText = shareTexts[Math.floor(Math.random() * shareTexts.length)];
    
    // พิมพ์ข้อความใหม่ (ใช้ evaluate เพื่อรักษา formatting)
    await fbPage.evaluate((text) => {
      document.execCommand('insertText', false, text);
    }, shareText);
    
    console.log('[Share] Added new promotional message');
    await sleep(1000);

    // ขั้นตอนที่ 5: คลิก "ถัดไป"
    const nextBtnSelectors = [
      'div[role="dialog"] div[aria-label="ถัดไป"]',
      'div[role="dialog"] div[role="button"]:has-text("ถัดไป")',
      'div[role="dialog"] div[aria-label="Next"]',
    ];
    for (const sel of nextBtnSelectors) {
      try {
        const btn = fbPage.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await btn.click({ force: true });
          console.log('[Share] Clicked "ถัดไป"');
          break;
        }
      } catch (e) { }
    }
    await sleep(2000);

    // ขั้นตอนที่ 6: กด "โพสต์"
    const postBtnSelectors = [
      'div[role="dialog"] div[aria-label="โพสต์"]',
      'div[role="dialog"] div[role="button"]:has-text("โพสต์")',
      'div[role="dialog"] div[aria-label="Post"]',
      'div[aria-label="โพสต์"][role="button"]',
    ];
    for (const sel of postBtnSelectors) {
      try {
        const btn = fbPage.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await btn.click({ force: true });
          console.log('[Share] Clicked "โพสต์"');
          await sleep(2000);
          break;
        }
      } catch (e) { }
    }

    return { success: true, commentUrl };
  } catch (e) {
    console.error('[Share] Error in shareViaOwnPost:', e.message || e);
    return { success: false, reason: 'exception' };
  }
}

async function getClipboardText() {
  try {
    const { stdout } = await execPromise('powershell -Command "Get-Clipboard"');
    return stdout.trim();
  } catch (e) {
    return '';
  }
}

async function pauseForUser(message) {
  console.log(`\n⏸️ ${message}`);
  console.log('กด Enter เพื่อดำเนินการต่อ...');
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question('', () => { rl.close(); resolve(); });
  });
}

async function pauseOnError(isDebugPause, message) {
  if (!isDebugPause) return;
  await pauseForUser(`❌ ERROR — ${message}\nตรวจสอบแล้วกด Enter เพื่อข้ามโพสต์นี้และไปต่อ`);
}

// ===== MAIN BOT =====
(async () => {
  const isHeadless = process.argv.includes('--headless');
  const isDebugPause = process.argv.includes('--debug-pause');
  const isReviewMode = process.argv.includes('--review');
  const isLoginMode = process.argv.includes('--login');
  const BOT_START_TIME = Date.now();
  const MAX_RUNTIME_MS = 1200000;

  const extensionPath = path.join(__dirname, 'For Edge Addon');
  const browserArgs = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--disable-web-security',
    '--disable-features=IsolateOrigins,site-per-process',
    `--load-extension=${extensionPath}`,
    `--disable-extensions-except=${extensionPath}`
  ];

  try {
    const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
      headless: isHeadless,
      viewport: null,
      args: browserArgs
    });

    console.log('Browser launched successfully.');
    await sleep(2500);

    const existingPages = context.pages();
    const fbPage = existingPages.length > 0 ? existingPages[0] : await context.newPage();
    const geminiPage = await context.newPage();

    loadProcessedPosts();
    ensureDownloadsDir();
    clearDownloadsDir();

    console.log('\n⏭️ Skipping Gemini account check (loading cached accounts directly)...');
    const cached = loadActiveAccounts();
    
    // *** ยกเลิกการเช็ค ใช้ cache เลย ***
    if (cached && cached.length > 0) {
      activeGeminiAccounts = cached;
      console.log(`✓ Loaded ${activeGeminiAccounts.length} cached Gemini accounts (skipped validation).`);
    } else {
      // Fallback ถ้าไม่มี cache
      console.log('No cached accounts, using default 8 accounts...');
      activeGeminiAccounts = GEMINI_ACCOUNTS;
    }

    if (activeGeminiAccounts.length > 0) {
      saveActiveAccounts(activeGeminiAccounts);
    }

    if (!isDebugPause && (activeGeminiAccounts.length === 0 || isLoginMode)) {
      if (activeGeminiAccounts.length === 0) {
        console.log('No Gemini accounts found.');
        showWindowsNotification('Facebook Bot', 'No Gemini accounts found! Please login.', 'Warning');
      }
      const server = http.createServer((req, res) => {
        if (req.url === '/' || req.url === '/index.html') {
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end();
        } else if (req.url.startsWith('/check-account')) {
          const urlObj = new URL(req.url, `http://${req.headers.host}`);
          const index = parseInt(urlObj.searchParams.get('index'), 10);
          if (isNaN(index)) { res.writeHead(400); res.end('Bad Request'); return; }
          checkGeminiAccountLogged(context, index).then(isLogged => {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ index, isLogged }));
          }).catch(() => { res.writeHead(500); res.end('{}'); });
          return;
        } else {
          res.writeHead(404);
          res.end();
        }
      });
      server.listen(0, '127.0.0.1');
      if (activeGeminiAccounts.length === 0) {
        console.error('No Gemini accounts — exiting.');
        try { await context.close(); } catch (e) { }
        process.exit(1);
      }
    }

    if (activeGeminiAccounts.length > 0) {
      saveActiveAccounts(activeGeminiAccounts);
    }

    console.log(`Ready with ${activeGeminiAccounts.length} Gemini accounts.`);

    if (isDebugPause) {
      await pauseForUser('โหมด DEBUG — กด Enter เพื่อเริ่มสแกน Facebook');
      console.log(`DEBUG: Resuming with ${activeGeminiAccounts.length} cached accounts.`);
    }

    if (!isReviewMode) {
      console.log(`\nNavigating to Facebook groups: ${FB_URL}`);
      try {
        await fbPage.bringToFront().catch(() => { });
        await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
      } catch (e) {
        console.warn('Facebook navigation slow, continuing...');
      }

      const fbReady = await waitForFacebookReady(fbPage);
      if (!fbReady) {
        console.error('Cannot login Facebook — exiting.');
        await context.close();
        process.exit(1);
      }

      await sleep(1500);

      if (isDebugPause) {
        console.log(`\n📍 Facebook page URL: ${fbPage.url()}`);
        await pauseForUser('โหมด DEBUG — ตรวจสอบหน้า Facebook ให้พร้อม แล้วกด Enter เพื่อเริ่มสแกน');
        await sleep(1000);
      }

      console.log('\nStarting main processing loop...');
      let postsProcessedCount = 0;
      let consecutiveEmptyScrolls = 0;
      let consecutiveFilteredPosts = 0;
      const MAX_EMPTY_SCROLLS = 15;
      const MAX_FILTERED_POSTS = 60;

      while (postsProcessedCount < AUTO_GROUPS_MAX) {
        const elapsedMs = Date.now() - BOT_START_TIME;
        if (postsProcessedCount < AUTO_GROUPS_MAX && elapsedMs >= MAX_RUNTIME_MS) {
          console.warn(`Bot runtime exceeded 20 minutes (${Math.round(elapsedMs / 1000)}s). Stopping.`);
          break;
        }

        console.log(`\n📋 Scanning feed... Posts processed: ${postsProcessedCount}/${AUTO_GROUPS_MAX}`);

        await closeFacebookModal(fbPage);

        const article = fbPage.locator('div[role="article"]:not([data-bot-processed="true"])').first();

        if (await article.count() === 0) {
          consecutiveEmptyScrolls++;
          if (consecutiveEmptyScrolls >= MAX_EMPTY_SCROLLS) {
            await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
            await sleep(2000);
            consecutiveEmptyScrolls = 0;
          } else {
            await fbPage.evaluate(() => window.scrollBy(0, 1500));
            await sleep(2000);
          }
          continue;
        }

        { // outer block
          await article.evaluate(el => {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.style.outline = '4px solid #fbbc04';
          }).catch(() => { });
          await sleep(500);

          const postText = await getPostText(article);
          // Compute post ID early for logging
          const imageUrlsForId = await getLargeImageUrls(article);
          let earlyPostId;
          try {
            earlyPostId = imageUrlsForId.length > 0 ? hashString(new URL(imageUrlsForId[0]).pathname) : hashString(postText.substring(0, 200));
          } catch (e) {
            earlyPostId = hashString(postText.substring(0, 200));
          }
          console.log('\n--------------------------------------------');
          console.log(`Evaluating Post ID: ${earlyPostId}`);
          console.log(`Content: "${postText.substring(0, 80).replace(/\n/g, ' ')}..."`);
          if (imageUrlsForId.length > 0) console.log('--> Processing images:', JSON.stringify(imageUrlsForId, null, 2));

          // Skip if already processed
          if (processedPosts.has(earlyPostId)) {
            console.log('--> Skipped: Already processed.');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          const filterResult = await shouldFilterPost(article);
          if (filterResult.action === 'hide' || filterResult.action === 'spam') {
            console.log(`--> Skipped: caught by shouldFilterPost. Action: ${filterResult.action}. Reason: ${filterResult.reason}`);
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            consecutiveFilteredPosts++;
            if (consecutiveFilteredPosts >= MAX_FILTERED_POSTS) {
              console.warn(`Reached ${MAX_FILTERED_POSTS} consecutive filtered posts. Reloading Facebook...`);
              await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
              await sleep(3000);
              consecutiveFilteredPosts = 0;
              consecutiveEmptyScrolls = 0;
            }
            continue;
          }

          // Post passed all filters — reset consecutive skip counter
          consecutiveFilteredPosts = 0;

          const imageUrls = imageUrlsForId; // already fetched above
          if (imageUrls.length === 0) {
            console.log('--> Skipped: No large images found.');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          console.log(`Processing ${imageUrls.length} images...`);

          // ⏸️ DEBUG PAUSE 2: ตรวจสอบโพสต์ที่จะประมวลผลก่อนส่ง Gemini
          if (isDebugPause) {
            await pauseForUser(`โหมด DEBUG — พบโพสต์ที่จะประมวลผล (${imageUrls.length} ภาพ)\nตรวจสอบโพสต์บน Facebook แล้วกด Enter เพื่อส่ง Gemini`);
          }

          // Declare outside try so finally can access them for cleanup
          let tempInputPaths = [];
          let geminiResult = null;
          let pythonResult = null;

          try {
          for (let i = 0; i < imageUrls.length; i++) {
            const tempInputPath = path.join(DOWNLOADS_DIR, `fb_input_${Date.now()}_${i}.jpg`);
            try {
              const imageResponse = await fbPage.request.get(imageUrls[i]);
              fs.writeFileSync(tempInputPath, await imageResponse.body());
              tempInputPaths.push(tempInputPath);
            } catch (dlErr) {
              console.error(`Failed to download image ${i}:`, dlErr.message);
            }
          }

          if (tempInputPaths.length === 0) {
            console.error('❌ Failed to download any images for post.');
            await pauseOnError(isDebugPause, 'โหลดภาพจาก Facebook ไม่ได้');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          const geminiUrl = getNextGeminiUrl();
          if (!geminiUrl) {
            console.error('No Gemini URL available.');
            await pauseOnError(isDebugPause, 'ไม่มี Gemini URL ที่ใช้ได้');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          geminiResult = await processWithGemini(geminiPage, tempInputPaths, postText, geminiUrl);
          if (!geminiResult) {
            console.error('Gemini processing failed.');
            await pauseOnError(isDebugPause, 'Gemini ประมวลผลล้มเหลว');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          // ⏸️ DEBUG PAUSE 3: ตรวจสอบผลจาก Gemini ก่อน Python แต่งภาพ
          if (isDebugPause) {
            await pauseForUser(`โหมด DEBUG — Gemini เสร็จแล้ว (${geminiResult})\nตรวจสอบภาพ แล้วกด Enter เพื่อให้ Python แต่งภาพต่อ`);
          }

          pythonResult = await runPythonImageEditor(geminiResult);
          if (!pythonResult) {
            console.error('Python image editing failed.');
            await pauseOnError(isDebugPause, 'Python แต่งภาพล้มเหลว');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          // ⏸️ DEBUG PAUSE 4: ตรวจสอบภาพที่แต่งแล้วก่อนโพสต์ comment
          if (isDebugPause) {
            await pauseForUser(`โหมด DEBUG — Python แต่งภาพเสร็จแล้ว (${pythonResult})\nตรวจสอบภาพ แล้วกด Enter เพื่อโพสต์ comment บน Facebook`);
          }

          await fbPage.bringToFront().catch(() => { });
          const commentResult = await postComment(article, pythonResult);

          // Extract post permalink for sharing
          const postUrl = await getPostUrl(article).catch(() => null);
          if (postUrl) console.log(`Post URL: ${postUrl}`);

          let postId;
          try {
            postId = imageUrls.length > 0 ? hashString(new URL(imageUrls[0]).pathname) : hashString(postText.substring(0, 200));
          } catch (e) {
            postId = hashString(postText.substring(0, 200));
          }

          if (commentResult && commentResult.success) {
            // ⏸️ DEBUG PAUSE 5: ตรวจสอบ comment ก่อน like/share
            if (isDebugPause) {
              await pauseForUser('โหมด DEBUG — Comment โพสต์แล้ว\nตรวจสอบ comment บน Facebook แล้วกด Enter เพื่อ Like และ Share ต่อ');
            }
            // ปิด popup/modal ก่อน like เพื่อไม่ให้คลิกผิด element
            await closeFacebookModal(fbPage);
            await sleep(800);
            // scroll article กลับขึ้นไปให้มองเห็น like button
            await article.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => {});
            await sleep(600);
            await likePost(article);
            await sleep(2000);

            // --- Share ผ่านโพสต์ในหน้าตัวเอง ---
            await fbPage.bringToFront().catch(() => { });
            const shareResult = await shareViaOwnPost(fbPage, article);
            if (shareResult && shareResult.success) {
              console.log(`[Share] Shared via own post: ${shareResult.commentUrl}`);
            } else {
              console.warn(`[Share] Share skipped or failed: ${shareResult?.reason}`);
            }

            // ⏸️ DEBUG PAUSE 6: หลัง share ให้ pause รอตรวจสอบก่อนเริ่มงานใหม่
            if (isDebugPause) {
              await pauseForUser('โหมด DEBUG — Share เสร็จแล้ว\nตรวจสอบโพสต์ใน profile ก่อน แล้วกด Enter เพื่อเริ่มงานถัดไป');
            }

            // กลับไปหน้า Facebook groups feed
            await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
            await sleep(2000);
            await closeFacebookModal(fbPage);

            postsProcessedCount++;
            processedPosts.add(postId);
            saveProcessedPosts();
            showWindowsNotification('Facebook Bot', `Task #${postsProcessedCount} completed!`);
            console.log(`Post #${postsProcessedCount} processed successfully!`);
          } else {
            console.log('Comment failed, marking as processed.');
            await pauseOnError(isDebugPause, 'Comment โพสต์ล้มเหลว');
            processedPosts.add(postId);
            saveProcessedPosts();
          }
          await article.evaluate(el => {
            el.style.display = 'none';
            el.setAttribute('data-bot-processed', 'true');
          }).catch(() => { });
          await sleep(3000);

          } catch (err) {
            console.error('Error processing article:', err.message || err);
          } finally {
          await article.evaluate(el => el.style.outline = '').catch(() => { });
          // ✅ Cleanup: ลบไฟล์ชั่วคราวทั้งหมดใน downloads
          for (const p of tempInputPaths) {
            try { if (fs.existsSync(p)) fs.unlinkSync(p); } catch (e) { }
          }
          if (geminiResult) {
            try { if (fs.existsSync(geminiResult)) fs.unlinkSync(geminiResult); } catch (e) { }
          }
          if (pythonResult) {
            try { if (fs.existsSync(pythonResult)) fs.unlinkSync(pythonResult); } catch (e) { }
          }
          // ลบภาพ Desktop output — ไม่ลบแล้ว ใช้วิธี overwrite ใน screenshot_donate.py เอง
          // (complete_bot.png จะถูก overwrite ในครั้งถัดไปเอง)
          }
        }
      }

      console.log('\n============================================');
      console.log(`Successfully completed ${postsProcessedCount} posts.`);
      console.log('============================================');
      showWindowsNotification('Facebook Bot', `Completed ${postsProcessedCount} posts. Bot closing.`);
    } else {
      console.log('Review mode: accounts scanned, no processing.');
      console.log(`Active accounts: ${activeGeminiAccounts.length}`);
      for (const acc of activeGeminiAccounts) {
        console.log(`  ${acc}`);
      }
    }

    await context.close();
    process.exit(0);
  } catch (fatalError) {
    console.error('FATAL ERROR:', fatalError.message || fatalError);
    process.exit(1);
  }
})();
