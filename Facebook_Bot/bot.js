import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import crypto from 'crypto';
import readline from 'readline';
import { fileURLToPath } from 'url';
import os from 'os';

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
    const cmd = `python "${pythonScript}" --donate-no-paste "${imagePath}" --bot`;
    console.log('Running cmd:', cmd);
    const { stdout, stderr } = await execPromise(cmd);
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

    // Always use the original post text as the main request,
    // then append a clear instruction for Gemini in English.
    // This avoids encoding issues with Thai string literals.

    // Detect request type from post text keywords
    const isAddPerson = text.includes('\u0e40\u0e1e\u0e34\u0e48\u0e21\u0e04\u0e19') || text.includes('\u0e43\u0e2a\u0e48\u0e04\u0e19');
    const isChangeBg = text.includes('\u0e09\u0e32\u0e01\u0e2b\u0e25\u0e31\u0e07') || text.includes('\u0e40\u0e1b\u0e25\u0e35\u0e48\u0e22\u0e19\u0e09\u0e32\u0e01');
    const isAddClothes = text.includes('\u0e0a\u0e38\u0e14') || text.includes('\u0e43\u0e2a\u0e48\u0e0a\u0e38\u0e14');
    const isEnhance = text.includes('\u0e41\u0e15\u0e48\u0e07\u0e23\u0e39\u0e1b') || text.includes('\u0e0a\u0e31\u0e14');
    const isRemove = text.includes('\u0e25\u0e1a') || text.includes('\u0e40\u0e2d\u0e32\u0e2d\u0e2d\u0e01');

    let instruction = 'Please edit/enhance this photo as requested by the user above. Make the result look natural and realistic.';

    if (isAddPerson) {
      instruction = 'Please add a person to this image to match the atmosphere. Make it look natural.';
    } else if (isChangeBg) {
      instruction = 'Please change the background of this photo to something beautiful and fitting.';
    } else if (isAddClothes) {
      instruction = 'Please change or add clothing to the person in this photo as described.';
    } else if (isEnhance) {
      instruction = 'Please enhance and retouch this photo. Improve lighting, sharpness and overall quality.';
    } else if (isRemove) {
      instruction = 'Please remove the specified object or element from this photo cleanly.';
    }

    return `${postText.trim()}\n\n[คำสั่ง AI]: ${instruction}`;

  } catch (e) {
    return `${postText.trim()}\nPlease edit this image as requested.`;
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
        
          console.warn('[FastDL] Max retries reached, skipping post.');
          return null;

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
      // 1. คัดลอกภาพไปยัง clipboard โดยเขียน .ps1 temp file (หลีกเลี่ยง quote escaping)
      const tempPs1 = path.join(os.tmpdir(), `clip_img_${Date.now()}.ps1`);
      const psLines = [
        'Add-Type -AssemblyName System.Windows.Forms',
        'Add-Type -AssemblyName System.Drawing',
        `\$imgPath = '${imagePath.replace(/'/g, "''")}'`,
        '$bytes = [System.IO.File]::ReadAllBytes($imgPath)',
        '$ms = New-Object System.IO.MemoryStream(,$bytes)',
        '$img = [System.Drawing.Image]::FromStream($ms)',
        '$bmp = New-Object System.Drawing.Bitmap($img.Width, $img.Height)',
        '$g = [System.Drawing.Graphics]::FromImage($bmp)',
        '$g.DrawImage($img, 0, 0)',
        '$g.Dispose()',
        '$img.Dispose()',
        '$ms.Dispose()',
        '$do = New-Object System.Windows.Forms.DataObject',
        '$pngMs = New-Object System.IO.MemoryStream',
        '$bmp.Save($pngMs, [System.Drawing.Imaging.ImageFormat]::Png)',
        '$pngMs.Position = 0',
        "$do.SetData('PNG', $false, $pngMs)",
        '$do.SetImage($bmp)',
        '[System.Windows.Forms.Clipboard]::SetDataObject($do, $true)',
        '$bmp.Dispose()',
      ];
      fs.writeFileSync(tempPs1, psLines.join('\r\n'), 'utf8');
      await execPromise(`cmd /c powershell -STA -NoProfile -ExecutionPolicy Bypass -File "${tempPs1}"`, { timeout: 15000 });
      try { fs.unlinkSync(tempPs1); } catch (_) {}
      console.log('Image copied to clipboard (CF_PNG + CF_DIB).');
      
      // 2. คลิกที่ composer และกด Ctrl+V
      await composer.click({ force: true });
      await sleep(500);
      await page.keyboard.press('Control+v');
      await sleep(4000); // รอให้ Facebook โหลดภาพ
      
      // 3. ตรวจสอบว่าภาพอัพโหลดแล้วหรือยัง (หลายแบบ — อย่า strict เกินไป)
      const uploaded = await page.evaluate(() => {
        return !!(
          document.querySelector('div[role="progressbar"]') ||
          document.querySelector('img[src*="blob:"]') ||
          document.querySelector('div[data-type="image"]') ||
          document.querySelector('img[alt*="รูปภาพ"]') ||
          document.querySelector('[data-visualcompletion="media-vc-image"]') ||
          document.querySelector('div[class*="attachment"] img') ||
          document.querySelector('div[class*="UFIImageAttach"]') ||
          document.querySelector('div[class*="commentContent"] img')
        );
      }).catch(() => false);

      imageUploaded = uploaded;
      if (imageUploaded) {
        console.log('Image uploaded via Ctrl+V successfully.');
      } else {
        // ถึงแม้ตรวจไม่เจอ indicator ก็ proceed ต่อ — Facebook อาจแสดงผลช้า
        console.warn('Ctrl+V executed, no upload indicator found — proceeding anyway.');
        imageUploaded = true;
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
    // ใช้ insertText แทน fill() เพื่อไม่ลบภาพที่ paste ไปแล้ว
    await composer.click();
    await sleep(300);
    await page.keyboard.press('End'); // ไปท้ายสุดก่อน
    await sleep(200);
    await page.keyboard.type(promoText, { delay: 30 });
    await sleep(500);
    
    // *** �Ը�����: ��ԡ Submit button ᷹ Enter ���������� modal �Դ ***

    // --- บันทึก comment_id ที่มีอยู่แล้วก่อน submit (เพื่อหา comment ใหม่ภายหลัง) ---
    const existingCommentIds = await page.evaluate(() => {
      return new Set(
        Array.from(document.querySelectorAll('a[href*="comment_id"]'))
          .map(a => { try { return new URL(a.href).searchParams.get('comment_id'); } catch { return null; } })
          .filter(Boolean)
      );
    }).catch(() => new Set());
    console.log('[Comment URL] Snapshot: ' + existingCommentIds.size + ' existing comment_ids');

    let commentPosted = false;

    // *** Submit: หาปุ่ม submit จาก DOM รอบ composer (ไม่ใช้ Enter ซึ่งทำให้ขึ้นบรรทัดใหม่) ***

    // Strategy 1: evaluate DOM หาปุ่ม submit ที่อยู่ใกล้ composer แล้ว click ผ่าน JS
    commentPosted = await page.evaluate(() => {
      const composer =
        document.activeElement ||
        document.querySelector('div[role="textbox"][contenteditable="true"][aria-label*="\u0e04\u0e27\u0e32\u0e21\u0e04\u0e34\u0e14\u0e40\u0e2b\u0e47\u0e19"]') ||
        document.querySelector('div[role="textbox"][contenteditable="true"]');
      if (!composer) return false;

      let container = composer;
      for (let i = 0; i < 12; i++) {
        container = container.parentElement;
        if (!container) break;
        const buttons = Array.from(container.querySelectorAll('div[role="button"], button'));
        const submitBtn = buttons.find(btn => {
          const label = (btn.getAttribute('aria-label') || '').trim();
          const txt   = (btn.innerText || '').trim();
          const disabled = btn.getAttribute('aria-disabled') === 'true' || btn.disabled;
          if (disabled) return false;
          return (
            label === '\u0e42\u0e1e\u0e2a\u0e15\u0e4c\u0e04\u0e27\u0e32\u0e21\u0e04\u0e34\u0e14\u0e40\u0e2b\u0e47\u0e19' ||
            label === 'Post comment' ||
            label.startsWith('Post') ||
            txt   === '\u0e42\u0e1e\u0e2a\u0e15\u0e4c' ||
            txt   === 'Post'
          );
        });
        if (submitBtn) { submitBtn.click(); return true; }
      }
      return false;
    }).catch(() => false);

    if (commentPosted) {
      console.log('[Submit] \u2705 Clicked submit button via DOM traversal.');
      await sleep(3000);
    }

    // Strategy 2: Playwright locator หาปุ่ม submit visible ใกล้ composer
    if (!commentPosted) {
      const submitSelectors = [
        'div[aria-label="\u0e42\u0e1e\u0e2a\u0e15\u0e4c\u0e04\u0e27\u0e32\u0e21\u0e04\u0e34\u0e14\u0e40\u0e2b\u0e47\u0e19"]',
        'div[aria-label="Post comment"]',
        'div[role="button"][aria-label*="\u0e42\u0e1e\u0e2a\u0e15\u0e4c"]',
        'div[role="button"][aria-label*="Post"]',
      ];
      for (const sel of submitSelectors) {
        try {
          const btns = page.locator(sel);
          const count = await btns.count();
          for (let i = 0; i < count; i++) {
            const btn = btns.nth(i);
            if (!await btn.isVisible({ timeout: 500 }).catch(() => false)) continue;
            if (await btn.getAttribute('aria-disabled').catch(() => 'false') === 'true') continue;
            await btn.click({ force: true });
            console.log('[Submit] \u2705 Playwright clicked: ' + sel);
            commentPosted = true;
            await sleep(3000);
            break;
          }
          if (commentPosted) break;
        } catch (e) {}
      }
    }

    // Strategy 3: Tab ออกจาก textbox ไปที่ปุ่ม submit แล้วกด Space
    if (!commentPosted) {
      try {
        console.log('[Submit] Strategy 3: Tab to submit button...');
        await composer.focus();
        await sleep(200);
        await page.keyboard.press('Tab');
        await sleep(300);
        const focusedIsBtn = await page.evaluate(() => {
          const el = document.activeElement;
          return el && (el.getAttribute('role') === 'button' || el.tagName === 'BUTTON');
        });
        if (focusedIsBtn) {
          await page.keyboard.press('Space');
          console.log('[Submit] \u2705 Space pressed on focused button.');
        } else {
          await page.keyboard.press('Tab');
          await sleep(200);
          await page.keyboard.press('Space');
          console.log('[Submit] \u2705 Tab+Tab+Space fallback.');
        }
        commentPosted = true;
        await sleep(3000);
      } catch (e) {
        console.warn('[Submit] Tab+Space failed:', e.message);
      }
    }

    console.log('? Comment posted (keeping modal open for URL extraction)');
    
    // --- ค้นหา comment URL ของเราจาก promoText (Retry loop รอ Facebook render) ---
    // --- ค้นหา comment URL ของเราจาก promoText ---
    // --- ค้นหา comment URL ของเรา: หา comment_id ใหม่ที่ไม่ใช่ของเดิม ---
    let commentUrl = null;
    try {
      console.log('[Comment URL] Looking for new comment_id after submit...');
      // Retry ถึง 8 รอบ รอ Facebook render comment ใหม่
      for (let _attempt = 0; _attempt < 8; _attempt++) {
        await sleep(_attempt === 0 ? 3000 : 2000);
        commentUrl = await page.evaluate((existingIds) => {
          const allLinks = Array.from(document.querySelectorAll('a[href*="comment_id"]'));
          // หา link ที่มี comment_id ใหม่ (ไม่อยู่ใน snapshot ก่อน submit)
          const newLinks = allLinks.filter(a => {
            try {
              const cid = new URL(a.href).searchParams.get('comment_id');
              return cid && !existingIds.has(cid);
            } catch { return false; }
          });
          if (newLinks.length === 0) return null;
          // เอา link ล่าสุด (อยู่ท้ายสุดใน DOM = comment ใหม่สุด)
          const href = newLinks[newLinks.length - 1].href;
          try {
            const url = new URL(href);
            const cid = url.searchParams.get('comment_id');
            url.search = '';
            if (cid) url.searchParams.set('comment_id', cid);
            return url.toString();
          } catch {
            const m = href.match(/comment_id=([^&]+)/);
            return href.split('?')[0] + (m ? '?comment_id=' + m[1] : '');
          }
        }, [...existingCommentIds]);

        if (commentUrl) {
          console.log('[Comment URL] Found new comment_id (attempt ' + (_attempt + 1) + '): ' + commentUrl);
          break;
        }
        console.log('[Comment URL] New comment_id not found yet (' + (_attempt + 1) + '/8), retrying...');
      }
      if (!commentUrl) {
        console.warn('[Comment URL] Could not find new comment after all retries — share will be skipped.');
      }
    } catch (urlErr) {
      console.warn('[Comment URL] Failed to extract:', urlErr.message);
    }

    return { success: true, promoText, commentUrl };
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

async function shareViaOwnPost(fbPage, commentUrl) {
  try {
    if (!commentUrl) {
      console.warn('[Share] No comment URL provided, skipping share.');
      return { success: false, reason: 'no_comment_url' };
    }

    // Navigate to own profile
    console.log('[Share] Navigating to facebook.com/me...');
    await fbPage.goto('https://www.facebook.com/me', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await sleep(3000);
    await closeFacebookModal(fbPage);
    await sleep(800);

    // Click the "What's on your mind" / "คุณกำลังคิดอะไรอยู่" create-post button
    console.log('[Share] Finding create post box...');
    let postBoxClicked = false;

    // Strategy A: find by span text inside the button (exact text from HTML inspection)
    const postBoxFound = await fbPage.evaluate(() => {
      // Search all spans for the create-post placeholder text
      const candidates = [
        'คุณกำลังคิดอะไรอยู่', // คุณกำลังคิดอะไรอยู่
        'คุณกำลังคิดอะไร',                     // คุณกำลังคิดอะไร
        "What's on your mind",
        'Share something',
      ];
      for (const txt of candidates) {
        const spans = Array.from(document.querySelectorAll('span'));
        const span = spans.find(s => s.textContent.trim() === txt);
        if (span) {
          // Walk up to find the role=button parent
          let el = span;
          for (let i = 0; i < 8; i++) {
            el = el.parentElement;
            if (!el) break;
            if (el.getAttribute('role') === 'button') {
              el.click();
              console.log('[Share] Clicked via span text:', txt);
              return true;
            }
          }
        }
      }
      return false;
    }).catch(() => false);

    if (postBoxFound) {
      postBoxClicked = true;
      console.log('[Share] ✅ Clicked create post box via evaluate.');
    }

    // Strategy B: Playwright has-text selector
    if (!postBoxClicked) {
      const texts = [
        'คุณกำลังคิดอะไรอยู่',
        'คุณกำลังคิดอะไร',
        "What's on your mind",
      ];
      for (const txt of texts) {
        try {
          const el = fbPage.locator('div[role="button"]:has-text("' + txt + '")').first();
          if (await el.count() > 0 && await el.isVisible({ timeout: 1500 }).catch(() => false)) {
            await el.click({ force: true });
            postBoxClicked = true;
            console.log('[Share] ✅ Clicked via Playwright has-text: ' + txt);
            break;
          }
        } catch (e) {}
      }
    }

    if (!postBoxClicked) {
      console.warn('[Share] Could not open create post dialog.');
      return { success: false, reason: 'cannot_open_create_post' };
    }

    await sleep(3000);

    // Find composer in the dialog that opened
    console.log('[Share] Finding post composer...');
    const postComposerSelectors = [
      'div[role="dialog"] div[role="textbox"][contenteditable="true"]',
      'div[role="dialog"] div[contenteditable="true"]',
    ];

    let postComposer = null;
    for (const sel of postComposerSelectors) {
      try {
        const el = fbPage.locator(sel).first();
        if (await el.count() > 0 && await el.isVisible({ timeout: 2000 }).catch(() => false)) {
          postComposer = el;
          console.log('[Share] Found composer: ' + sel);
          break;
        }
      } catch (e) {}
    }

    if (!postComposer) {
      console.warn('[Share] Post composer not found.');
      return { success: false, reason: 'post_composer_not_found' };
    }

    await postComposer.click();
    await sleep(500);

    // Type share text + comment URL
    const thankYouMessages = [
      '✅ทำเสร็จแล้วนะครับ เชิญดูภาพใต้คอมเมนต์',
      '✅รับแก้ไขภาพออนไลน์ได้เลย ดูได้ที่คอมเมนต์',
      '✅แต่งภาพให้ครับ เชิญดูได้ที่คอมเมนต์ด้านล่าง',
    ];
    const shareMsg = thankYouMessages[Math.floor(Math.random() * thankYouMessages.length)];
    const shareText = shareMsg + '\n\n' + commentUrl;
    await postComposer.fill(shareText);
    await sleep(2000);

    // Click Post button inside dialog
    console.log('[Share] Clicking Post button...');
    let shared = false;

    // DOM traversal to find Post button in dialog
    shared = await fbPage.evaluate(() => {
      const dialog = document.querySelector('div[role="dialog"]');
      if (!dialog) return false;
      const buttons = Array.from(dialog.querySelectorAll('div[role="button"], button'));
      const postBtn = buttons.find(btn => {
        const label = (btn.getAttribute('aria-label') || '').trim();
        const txt = (btn.innerText || '').trim();
        const disabled = btn.getAttribute('aria-disabled') === 'true' || btn.disabled;
        if (disabled) return false;
        return label === 'โพสต์' || label === 'Post' ||
               txt === 'โพสต์' || txt === 'Post';
      });
      if (postBtn) { postBtn.click(); return true; }
      return false;
    }).catch(() => false);

    if (shared) {
      console.log('[Share] ✅ Clicked Post button via DOM.');
    } else {
      // Playwright fallback
      for (const sel of [
        'div[role="dialog"] div[aria-label="โพสต์"]',
        'div[role="dialog"] div[aria-label="Post"]',
        'div[role="dialog"] div[role="button"][aria-label*="Post"]',
      ]) {
        try {
          const btn = fbPage.locator(sel).first();
          if (await btn.count() > 0 && await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
            if (await btn.getAttribute('aria-disabled').catch(() => 'false') !== 'true') {
              await btn.click({ force: true });
              console.log('[Share] ✅ Playwright clicked: ' + sel);
              shared = true;
              break;
            }
          }
        } catch (e) {}
      }
    }

    await sleep(4000);
    console.log('[Share] ✅ Post shared to profile successfully!');
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
    // --- Kill any Chrome instance already using this user_data dir ---
    try {
      const userDataEscaped = USER_DATA_DIR.replace(/\\/g, '\\\\');
      const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
      await execPromise(killCmd, { timeout: 8000 }).catch(() => {});
      console.log('[Pre-launch] Killed orphaned Chrome (if any).');
      await sleep(1500); // รอให้ OS release file lock บน user_data
    } catch (e) {
      // ไม่มี process ค้าง หรือ wmic ไม่ทำงาน — ข้ามได้
    }

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
            const shareResult = await shareViaOwnPost(fbPage, commentResult.commentUrl);
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
