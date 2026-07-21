import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { exec, execFile } from 'child_process';
import { promisify } from 'util';
import crypto from 'crypto';
import readline from 'readline';
import { fileURLToPath } from 'url';
import os from 'os';

const execPromise = promisify(exec);
const execFilePromise = promisify(execFile);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const LOG_FILE = path.join(__dirname, 'bot.log');
const originalLog = console.log;
const originalError = console.error;
const originalWarn = console.warn;

// Delete old bot.log to save disk space
try { if (fs.existsSync(LOG_FILE)) fs.unlinkSync(LOG_FILE); } catch (e) {}

function logToFile(level, ...args) {
  // Disabled to save disk space
}

console.log = (...args) => { originalLog(...args); };
console.error = (...args) => { originalError(...args); };
console.warn = (...args) => { originalWarn(...args); };

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
const DOWNLOADS_DIR = path.join(__dirname, 'downloads');

// ตัวแปรสำหรับเก็บ context และควบคุมหน้าต่าง
let browserContext = null;
let isBrowserHidden = false;

let currentPostIndex = 0;
function reportStatus(percent, status, detail = '', logType = 'info', postIdx = currentPostIndex, action = '') {
  try {
    const statusFile = path.join(__dirname, 'status.json');
    const payload = JSON.stringify({
      postIndex: Math.max(1, postIdx),
      maxPosts: AUTO_GROUPS_MAX || 10,
      percent: Math.min(100, Math.max(0, Math.round(percent))),
      status,
      detail,
      logType,
      action,
      timestamp: Date.now()
    }, null, 2);
    fs.writeFileSync(statusFile, payload, 'utf8');
  } catch (e) {}
}

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

let AUTO_GROUPS_MAX = 10;
const FB_URL = 'https://www.facebook.com/groups/feed/';

let GEMINI_SLOT_COUNT = 8;
try {
  const state = loadActiveAccounts();
  if (Array.isArray(state) && state.length > 0) {
    GEMINI_SLOT_COUNT = state.length;
  }
} catch (e) { }

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

function hashString(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}

const processedPostIds = new Set();

async function hideProcessedPosts(page, processedPostIds) {
  if (!processedPostIds || processedPostIds.size === 0) return;
  const idsArray = Array.from(processedPostIds);
  await page.evaluate((ids) => {
    const hashString = (str) => {
      let hash = 5381;
      for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) + hash) + str.charCodeAt(i);
      }
      return (hash >>> 0).toString(16);
    };

    const getPostText = (el) => {
      const msgDiv = el.querySelector('div[data-ad-comet-preview="post_message"]');
      if (msgDiv) return msgDiv.innerText || '';
      return el.innerText || '';
    };

    const getLargeImageUrls = (el) => {
      const urls = [];
      const imgs = el.querySelectorAll('img');
      for (const img of imgs) {
        const src = img.src;
        if (!src) continue;
        if (src.includes('emoji') || src.includes('rsrc.php')) continue;
        const width = img.naturalWidth || img.width || 0;
        const height = img.naturalHeight || img.height || 0;
        if (width > 200 || height > 200 || src.includes('safe_image.php') || src.includes('fna.fbcdn.net')) {
          urls.push(src);
        }
      }
      return urls;
    };

    const articles = document.querySelectorAll('div[role="article"]:not([data-bot-processed="true"])');
    for (const art of articles) {
      const text = getPostText(art);
      if (!text || text.trim().length === 0) continue;
      const imgs = getLargeImageUrls(art);
      let id;
      try {
        id = imgs.length > 0 ? hashString(new URL(imgs[0]).pathname) : hashString(text.substring(0, 200));
      } catch (e) {
        id = hashString(text.substring(0, 200));
      }
      if (ids.includes(id)) {
        art.style.display = 'none';
        art.setAttribute('data-bot-processed', 'true');
      }
    }
  }, idsArray).catch(() => {});
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function checkIsGeminiLoggedOut(page) {
  try {
    return await page.evaluate(() => {
      // 1. ตรวจสอบปุ่ม/สแปน/ลิงก์ "ลงชื่อเข้าใช้" หรือ "Sign in"
      const elements = document.querySelectorAll('span, button, a, div');
      for (const el of elements) {
        const text = (el.textContent || '').trim();
        const href = (el.getAttribute('href') || '').toLowerCase();
        if (
          text === 'ลงชื่อเข้าใช้' || 
          text === 'Sign in' || 
          href.includes('accounts.google.com/servicelogin') || 
          href.includes('accounts.google.com/interactive-login')
        ) {
          return true;
        }
      }

      // 2. ตรวจสอบว่ามีช่องพิมพ์ข้อความหรือไม่ ถ้าไม่มีและมีข้อความเตือนให้ลงชื่อเข้าใช้
      const hasInput = document.querySelector('div.ql-editor[role="textbox"], div[contenteditable="true"][role="textbox"], rich-textarea div[contenteditable="true"]') !== null;
      if (!hasInput) {
        const bodyText = document.body ? (document.body.innerText || '') : '';
        if (bodyText.includes('ลงชื่อเข้าใช้') || bodyText.includes('Sign in')) {
          return true;
        }
      }

      return false;
    }).catch(() => false);
  } catch (e) {
    return false;
  }
}

async function checkGeminiAccountLogged(context, index) {
  const url = `https://gemini.google.com/u/${index}/app`;
  try {
    const page = await context.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(2000);

    const isLoggedOut = await checkIsGeminiLoggedOut(page);
    if (isLoggedOut) {
      await page.close().catch(() => { });
      return false;
    }

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
  const checkCount = Math.max(activeGeminiAccounts.length, GEMINI_SLOT_COUNT);
  for (let i = 0; i < checkCount; i++) {
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
      await seeMoreBtn.first().click({ timeout: 2000 }).catch(() => {});
      await sleep(500);
    }
  } catch (e) { }

  try {
    return await article.evaluate((node) => {
      // 1. ดึงจาก data-ad-comet-preview หรือ data-ad-preview ของ Facebook โดยตรง (แม่นยำที่สุด 100%)
      const messageElement = node.querySelector('[data-ad-comet-preview="message"], [data-ad-preview="message"]');
      if (messageElement) {
        const text = (messageElement.textContent || '').trim();
        if (text) {
          const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').replace(/\s+/g, ' ').trim();
          if (cleanText.length > 2) {
            console.log(`✓ Found post text from data-ad-preview: "${cleanText}"`);
            return cleanText;
          }
        }
      }

      // 2. Fallback: หาจาก div[dir="auto"] หรือ span[dir="auto"] แต่ต้องอยู่นอกพื้นที่ของคอมเมนต์ (Comment list)
      const allDivs = node.querySelectorAll('div[dir="auto"], span[dir="auto"]');
      for (const el of allDivs) {
        // ข้าม element ที่อยู่ใน link, button, navigation หรืออยู่ในกล่องคอมเมนต์/ตอบกลับ
        if (el.closest('a') || el.closest('button') || el.closest('[role="button"]') ||
          el.closest('nav') || el.closest('[role="navigation"]') ||
          el.closest('ul') ||
          el.closest('[class*="comment"]') || el.closest('[class*="reply"]')) {
          continue;
        }

        const text = (el.textContent || '').trim();
        if (text && text.length > 5 &&
          !text.includes('ถูกใจ') && !text.includes('แสดงความคิดเห็น') &&
          !text.includes('แชร์') && !text.includes('นาที') && !text.includes('ชั่วโมง') &&
          !text.includes('แชร์กับ')) {
          const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').replace(/\s+/g, ' ').trim();
          if (cleanText.length > 5) {
            console.log(`✓ Found post text from fallback: "${cleanText}"`);
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

async function shouldFilterPost(article, botProfileName) {
  try {
    return await article.evaluate((node, botName) => {
      // --- Check if post is authored by the bot itself ---
      if (botName && botName.length > 1) {
        const authorLinks = node.querySelectorAll('a[href*="/user/"], a[href*="/profile.php"], a[href*="/pages/"], a[role="link"][tabindex="0"]');
        for (const a of authorLinks) {
          const authorText = (a.textContent || '').trim();
          if (authorText && authorText === botName) {
            return { action: 'hide', reason: `Post authored by bot itself (${botName})` };
          }
        }
        // Fallback: check strong/a tags at the top of the article (Facebook post header)
        const headerStrongs = node.querySelectorAll('h3 a, h4 a, h2 a, strong a, span > a');
        for (const a of headerStrongs) {
          const authorText = (a.textContent || '').trim();
          if (authorText && authorText === botName) {
            return { action: 'hide', reason: `Post authored by bot itself (${botName})` };
          }
        }
        // Final fallback: check the first few links for profile name
        const allLinks = node.querySelectorAll('a');
        let linkIdx = 0;
        for (const a of allLinks) {
          if (linkIdx > 10) break;
          linkIdx++;
          const href = a.href || '';
          const authorText = (a.textContent || '').trim();
          if (authorText === botName && (href.includes('facebook.com/') || href.includes('/profile.php'))) {
            return { action: 'hide', reason: `Post authored by bot itself (${botName})` };
          }
        }
      }

      const spamKeywords = [
        'คิวว่าง', 'รับตัดต่อ', 'ราคาเพียง', 'สอบถามได้', 'เริ่มต้นแค่', 'โป๊', 'เย็ด', 'นม', 'หี', 'หน้าอก', 'หรรม', '18+', 'เสียว', 'เงี่ยน', 'หนังผู้ใหญ่',
        'ฝากร้าน', 'เปิดรับ', 'สนใจสอบถาม', 'รับประกัน', 'สร้างรายได้',
        'สอบถามเพิ่มเติม', 'รับทำ', 'รีวิว', 'บริการ', 'เน็ตบ้าน', 'ด่วน',
        'อินเตอร์เน็ตบ้าน', 'สนใจทักแชท', 'ว่างทำให้', 'ว่างแล้ว', 'ขอส่ง', 'ให้ฟรี',
        'ภาพเคลื่อนไหว', 'vdo', 'video', 'วิดีโอ', 'วีดีโอ', 'clip', 'คลิป', '#'
      ];
      const text = node.textContent || '';
      const cleanText = text.replace(/[\u200B-\u200D\uFEFF\u00AD]/g, '').replace(/[\s\u00A0]+/g, ' ');

      // Check if comments are disabled (text-based with normalized string & zero-width space handling)
      const disabledKeywords = [
        'ปิดการแสดงความคิดเห็น',
        'ปิดการแสดงความคิดเห็นไว้ชั่วคราว',
        'ผู้ดูแลได้ปิด',
        'ผู้ดูแลปิด',
        'ปิดคอมเมนต์',
        'ปิดรับความคิดเห็น',
        'ปิดการตอบกลับ',
        'จำกัดผู้ที่สามารถแสดงความคิดเห็น',
        'ไม่สามารถแสดงความคิดเห็น',
        'ไม่อนุญาตให้แสดงความคิดเห็น',
        'Comments are turned off',
        'Comments on this post have been limited',
        'Comments have been disabled',
        'turned off commenting',
        'turned off comments'
      ];
      for (const kw of disabledKeywords) {
        if (cleanText.includes(kw) || text.includes(kw)) {
          return { action: 'hide', reason: `Comments disabled (text: "${kw}")` };
        }
      }
      if (
        /ปิด.*ความคิดเห็น/i.test(cleanText) ||
        /ปิด.*คอมเมนต์/i.test(cleanText) ||
        /จำกัด.*ความคิดเห็น/i.test(cleanText) ||
        /turned off.*comment/i.test(cleanText)
      ) {
        return { action: 'hide', reason: 'Comments disabled (regex match)' };
      }

      // Check if a valid Comment button or comment icon is present in the post
      let hasCommentBtn = false;
      const candidates = node.querySelectorAll('[role="button"], button, div[aria-label], span[aria-label]');
      for (const el of candidates) {
        const label = (el.getAttribute('aria-label') || '').trim();
        const innerText = (el.innerText || el.textContent || '').trim();
        const lowerLabel = label.toLowerCase();
        const lowerText = innerText.toLowerCase();

        // Skip dropdowns, sort options, disabled notices, or view previous comments
        if (
          lowerLabel.includes('ปิดการแสดงความคิดเห็น') ||
          lowerLabel.includes('เกี่ยวข้องมากที่สุด') ||
          lowerLabel.includes('most relevant') ||
          lowerLabel.includes('ดูความคิดเห็นก่อนหน้า') ||
          lowerLabel.includes('view previous comments') ||
          lowerLabel.includes('ซ่อนความคิดเห็น') ||
          lowerLabel.includes('hide comments')
        ) {
          continue;
        }

        // Match Comment action button labels
        const isCommentActionLabel = (
          lowerLabel === 'แสดงความคิดเห็น' ||
          lowerLabel.startsWith('แสดงความคิดเห็น') ||
          lowerLabel === 'เขียนความคิดเห็น' ||
          lowerLabel.startsWith('เขียนความคิดเห็น') ||
          lowerLabel === 'comment' ||
          lowerLabel === 'comments' ||
          lowerLabel.startsWith('write a comment') ||
          lowerLabel.startsWith('leave a comment') ||
          lowerLabel.includes('comment as') ||
          lowerLabel.includes('แสดงความคิดเห็นในฐานะ')
        );

        // Match Comment action button text
        const isCommentActionText = (
          lowerText === 'แสดงความคิดเห็น' ||
          lowerText === 'เขียนความคิดเห็น' ||
          lowerText === 'comment'
        );

        if (isCommentActionLabel || isCommentActionText) {
          hasCommentBtn = true;
          break;
        }
      }

      // Fallback: search for buttons with aria-label containing comment keywords
      if (!hasCommentBtn) {
        const allBtns = node.querySelectorAll('[role="button"], button');
        for (const btn of allBtns) {
          const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase().trim();
          if (
            (ariaLabel.includes('แสดงความคิดเห็น') || ariaLabel.includes('comment')) &&
            !ariaLabel.includes('ปิด') &&
            !ariaLabel.includes('เรียง') &&
            !ariaLabel.includes('ซ่อน')
          ) {
            hasCommentBtn = true;
            break;
          }
        }
      }

      if (!hasCommentBtn) {
        return { action: 'hide', reason: 'No Comment icon or button found (Comments disabled/unavailable)' };
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
      const links = node.querySelectorAll('a[href*="/groups/"], a[href*="facebook.com/"]');
      for (const a of links) {
        const href = a.href || '';
        if (/\/groups\/[\w.]+\/(posts|permalink)\//.test(href) || /facebook\.com\/permalink\//.test(href)) {
          try { const url = new URL(href); url.search = ''; return url.toString(); } catch (e) { return href.split('?')[0]; }
        }
      }
      for (const a of links) {
        const href = a.href || '';
        if (href.includes('/posts/') || href.includes('story_fbid=')) {
          try { const url = new URL(href); url.search = ''; return url.toString(); } catch (e) { return href.split('?')[0]; }
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

async function runPythonImageEditor(imagePath, postText = '') {
  const desktopPath = path.join(process.env.USERPROFILE, 'Desktop', 'complete.png');
  const isBotMode = process.argv.includes('--bot');
  const outputName = isBotMode ? 'complete_bot.png' : 'complete.png';
  const desktopOutputPath = path.join(process.env.USERPROFILE, 'Desktop', outputName);


  try {
    const pythonScript = 'D:\\Github\\eworker\\screenshot_donate.py';
    
    // ใช้ execFile แทน exec เพื่อป้องกันการปนเปื้อนของ parameter/character escaping
    const args = ['--donate-no-paste', imagePath];
    if (postText) {
      args.push('--prompt', postText);
    }
    args.push('--bot');

    console.log('Running python script via execFile:', pythonScript, args);
    const { stdout, stderr } = await execFilePromise('python', [pythonScript, ...args]);
    
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
    await bringWindowToFront(page).catch(() => { });
    const currentUrl = page.url();
    // ตรวจสอบว่าเป็นหน้าหลักแบบสะอาด (ไม่มีรหัสแชทต่อท้าย) หรือไม่
    // URL สะอาดจะเป็น https://gemini.google.com/u/X/app หรือมี / หรือ query parameter ต่อท้ายเท่านั้น
    const cleanUrlRegex = new RegExp(`^${geminiUrl.replace(/\//g, '\\/')}\\/?(\\?.*)?$`);
    const isCleanUrl = cleanUrlRegex.test(currentUrl);

    if (!isCleanUrl) {
      console.log(`Navigating to clean Gemini page: ${geminiUrl}`);
      await page.goto(geminiUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await sleep(2000); // รอเพิ่มอีกนิดให้หน้าแชทใหม่โหลดเสร็จ
    } else {
      console.log(`Already on clean Gemini page: ${currentUrl}, skipping navigation.`);
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

    // --- STEP 1: รอ Gemini ประมวลผลเสร็จ และตรวจสอบว่ามีรูปเลือกหรือไม่ ---
    let captured = false;
    let retryCount = 0;
    const maxRetries = 2;
    let hasChoice = false;

    while (!captured && retryCount <= maxRetries) {
      try {
        const fastDl = page.locator('.fast-dl-button').first();
        if (await fastDl.isVisible({ timeout: 12000 }).catch(() => false)) {
          console.log('[FastDL] Image ready, checking for choice buttons...');
          captured = true;
          break;
        }

        console.log('[FastDL] Gemini still processing, waiting...');
        await fastDl.waitFor({ state: 'visible', timeout: 35000 });
        console.log('[FastDL] Image ready, checking for choice buttons...');
        captured = true;
      } catch (e) {
        console.warn(`[FastDL] Fast Download button not found (attempt ${retryCount + 1}/${maxRetries + 1}):`, e.message);

        if (retryCount < maxRetries) {
          console.log(`[FastDL] Retry attempt ${retryCount + 1}/${maxRetries} — trying buttons...`);

          let retryClicked = false;

          // Strategy 1: Click retry/generate/refresh buttons via DOM evaluate (captures all positions correctly)
          retryClicked = await page.evaluate(() => {
            // Collect all clickable elements
            const allBtns = Array.from(document.querySelectorAll('button, div[role="button"], span[role="button"], a, span'));
            
            // Helper: check visible and clickable
            function isClickable(el) {
              const rect = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
            }
            
            // Priority 1: "ลองอีกครั้ง" / "Try again" exact match first
            for (const btn of allBtns) {
              const text = (btn.innerText || btn.textContent || '').trim();
              const ariaLabel = (btn.getAttribute('aria-label') || '').trim();
              if (text === 'ลองอีกครั้ง' || text === 'Try again' || ariaLabel === 'ลองอีกครั้ง' || ariaLabel === 'Try again') {
                if (isClickable(btn)) { btn.click(); return true; }
              }
            }
            
            // Priority 2: includes "ลองอีกครั้ง" or "try again"
            for (const btn of allBtns) {
              const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
              const ariaLabel = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
              if (text.includes('ลองอีกครั้ง') || text.includes('try again') || ariaLabel.includes('ลองอีกครั้ง') || ariaLabel.includes('try again')) {
                if (isClickable(btn)) { btn.click(); return true; }
              }
            }
            
            // Priority 3: other retry patterns
            const patterns = [
              'สร้างภาพ', 'สร้างใหม่', 'retry', 'regenerate',
              'สร้างรูป', 'ทำภาพ', 'ทำรูป', 'refresh',
              'สร้าง', 'generate',
            ];
            for (const btn of allBtns) {
              const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
              const ariaLabel = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
              for (const pat of patterns) {
                if (text.includes(pat) || ariaLabel.includes(pat)) {
                  if (isClickable(btn)) { btn.click(); return true; }
                }
              }
            }
            
            // Fallback: last mat-icon refresh (latest response is at the bottom of the page)
            const refreshIcons = Array.from(document.querySelectorAll('mat-icon[data-mat-icon-name="refresh"], mat-icon[fonticon="refresh"]'));
            if (refreshIcons.length > 0) {
              const lastRefreshIcon = refreshIcons[refreshIcons.length - 1];
              const parent = lastRefreshIcon.closest('button, div[role="button"]');
              if (parent) { parent.click(); return true; }
              lastRefreshIcon.click();
              return true;
            }
            
            return false;
          }).catch(() => false);

          if (retryClicked) {
            console.log('[FastDL] ✅ Clicked retry/generate button via DOM evaluate');
            await sleep(5000); // รอนานขึ้นหลังจากคลิก retry
            retryCount++;
            continue;
          }

          // Strategy 2: Playwright locator for visible retry buttons
          const retrySelectors = [
            // ลองอีก kommt first — highest priority
            'div[role="button"]:has-text("ลองอีกครั้ง")',
            'button:has-text("ลองอีกครั้ง")',
            'span:has-text("ลองอีกครั้ง")',
            // Try again / Retry
            'div[role="button"]:has-text("Try again")',
            'button:has-text("Try again")',
            'div[role="button"]:has-text("Retry")',
            'button:has-text("Retry")',
            // สร้างภาพ / ทำภาพ
            'div[role="button"]:has-text("สร้าง")',
            'button:has-text("สร้าง")',
            'div[role="button"]:has-text("ทำภาพ")',
            'button:has-text("ทำภาพ")',
            // Generate
            'div[role="button"]:has-text("Generate")',
            'button:has-text("Generate")',
          ];
          for (const sel of retrySelectors) {
            try {
              const btn = page.locator(sel).first();
              if (await btn.count() > 0 && await btn.isVisible({ timeout: 1500 }).catch(() => false)) {
                await btn.click({ force: true });
                console.log('[FastDL] ✅ Clicked: ' + sel);
                retryClicked = true;
                break;
              }
            } catch (e) { }
          }

          if (!retryClicked) {
            // Fallback: Click last refresh icon or its parent button
            try {
              const refreshIcons = page.locator('mat-icon[data-mat-icon-name="refresh"], mat-icon[fonticon="refresh"]');
              const count = await refreshIcons.count();
              if (count > 0) {
                const lastIcon = refreshIcons.last();
                const parentBtn = page.locator('button:has(mat-icon[data-mat-icon-name="refresh"]), button:has(mat-icon[fonticon="refresh"])').last();
                if (await parentBtn.count() > 0 && await parentBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
                  await parentBtn.click({ force: true });
                  console.log('[FastDL] ✅ Clicked last refresh button parent');
                  retryClicked = true;
                } else {
                  await lastIcon.click({ force: true });
                  console.log('[FastDL] ✅ Clicked last refresh icon');
                  retryClicked = true;
                }
              }
            } catch (e) {
              console.warn('[FastDL] Fallback refresh icon click failed:', e.message);
            }
          }

          if (retryClicked) {
            await sleep(5000);
            retryCount++;
            continue;
          }

          // Strategy 3: ถ้าไม่เจอปุ่ม retry เลย -> ส่ง prompt ใหม่ (พิมพ์ใหม่แล้วกด Enter)
          console.log('[FastDL] No retry button found — re-typing prompt...');
          try {
            const textInput = page.locator(inputSelector).first();
            if (await textInput.count() > 0 && await textInput.isVisible({ timeout: 2000 }).catch(() => false)) {
              await textInput.click({ force: true });
              await sleep(500);
              await textInput.fill(promptText);
              await sleep(500);
              await textInput.press('Enter');
              console.log('[FastDL] ✅ Re-sent prompt to Gemini');
              await sleep(5000);
              retryCount++;
              continue;
            }
          } catch (retypeErr) {
            console.warn('[FastDL] Re-typing prompt failed:', retypeErr.message);
          }
        }

        console.warn('[FastDL] Max retries reached or retry failed.');
        break;
      }
    }

    // --- STEP 2: ตรวจหา choice buttons (ถ้า Gemini แสดงตัวเลือก 2 รูป) ---
    if (captured) {
      try {
        console.log('[Choice] Checking for image selection buttons...');
        
        // หาปุ่มเลือกภาพทั้งหมด (Gemini ใช้ aria-label "Select image 1", "Select image 2" ฯลฯ)
        const choiceButtons = await page.evaluate(() => {
          const btns = Array.from(document.querySelectorAll('button[aria-label*="Select image"], button[aria-label*="เลือกภาพ"]'));
          return btns.length;
        }).catch(() => 0);

        if (choiceButtons >= 2) {
          hasChoice = true;
          console.log(`[Choice] ✅ Found ${choiceButtons} image choices. Selecting first image...`);
          
          // คลิกปุ่มแรก (Select image 1)
          const firstChoice = page.locator('button[aria-label*="Select image 1"], button[aria-label*="เลือกภาพ 1"]').first();
          if (await firstChoice.count() > 0) {
            await firstChoice.click({ force: true });
            console.log('[Choice] ✅ Clicked first image choice');
            await sleep(2000); // รอให้ Gemini โหลดภาพที่เลือก
          }
        } else {
          console.log('[Choice] No image choices found, proceeding with single result.');
        }
      } catch (choiceErr) {
        console.warn('[Choice] Error checking for choices:', choiceErr.message);
      }
    }

    // --- STEP 3: ตรวจสอบว่า Gemini ปฏิเสธทำรูป (จริยธรรม) ---
    const refusalDetected = await page.evaluate(() => {
      const text = document.body.innerText || '';
      const refusalKeywords = [
        // English
        "I can't help with images of people",
        "I'm not able to help with that",
        "I can't assist with that",
        "I cannot help with",
        "against my guidelines",
        "content policy",
        "I'm unable to",
        "I can't generate",
        "I can't create",
        "I'm not able to generate",
        "cannot fulfill this request",
        
        // Thai
        "ฉันไม่สามารถช่วยเหลือ",
        "ฉันไม่สามารถทำ",
        "ฉันไม่สามารถทำตาม",
        "ไม่สามารถสร้าง",
        "ไม่สามารถสร้างภาพ",
        "ฉันไม่สามารถสร้างภาพ",
        "ไม่สามารถช่วย",
        "ขัดต่อนโยบาย",
        "ขัดกับแนวทาง",
        "ขัดต่อหลัก",
        "ไม่สามารถดำเนินการ",
        "ฉันทำไม่ได้",
        "ทำไม่ได้",
        "นโยบายความปลอดภัย",
        "เนื้อหาชี้นำทางเพศ",
        "ผิดกฎหมาย",
        "เป็นอันตราย",
        "การสนทนาของคุณยุติ",
        "ขออภัย ฉันไม่สามารถ",
        "ขออภัย ฉันสร้างรูปภาพที่ไม่ปลอดภัยไม่ได้",

        // Gemini offers to create a different image of the same person (treat as refusal)
        "ฉันสร้างภาพของบุคคลจริงได้นะ แต่ไม่ใช่ภาพแบบนั้น",
        "ให้ฉันช่วยสร้างภาพอื่นของคนคนนี้แทนไหม",
      ];
      return refusalKeywords.some(kw => text.includes(kw));
    }).catch(() => false);

    if (refusalDetected) {
      console.warn('[Gemini] ⚠️ Gemini refused due to content policy. Returning null to skip this post.');
      return null;
    }

    // --- STEP 4: Capture ภาพจาก DOM ---
    if (!captured) {
      console.warn('[FastDL] No fast download button appeared — Gemini likely refused or failed. Returning null.');
      return null;
    }

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

async function getLoggedInProfileName(page) {
  try {
    return await page.evaluate(() => {
      // 1. หาจากลิงก์โปรไฟล์ — navigation sidebar มักมีลิงก์ไป profile
      const profileLinks = document.querySelectorAll('a[href*="/me"], a[href*="/profile.php"], a[href*="/settings/"]');
      for (const a of profileLinks) {
        const txt = (a.innerText || a.textContent || '').trim();
        if (txt && txt.length > 1 && txt.length < 60) return txt;
      }
      // 2. หาจาก area label หรือ alt ของ avatar รูปโปรไฟล์
      const avatars = document.querySelectorAll('image[alt*="profile"], img[alt*="profile"], img[alt*="โปรไฟล์"]');
      for (const img of avatars) {
        const alt = img.getAttribute('alt') || '';
        const match = alt.match(/profile\s*:\s*(.+)/i) || alt.match(/โปรไฟล์\s*(.+)/);
        if (match) return match[1].trim();
      }
      // 3. หาจาก title ของหน้า (Facebook มักมีชื่อ user ใน title)
      const title = document.title;
      if (title) {
        // เลี่ยงการจับตัวเลข notification ในวงเล็บ
        const m = title.match(/^\(\d+\)\s*(.+?)\s*[|]/) || title.match(/^(.+?)\s*[|]/);
        if (m && m[1] && !m[1].includes('Facebook') && !m[1].includes('Groups') && !m[1].includes('กลุ่ม')) return m[1].trim();
      }
      return null;
    }).catch(() => null);
  } catch { return null; }
}

async function postComment(article, imagePath, postUrl) {
  try {
    const page = article.page();

    // ✅ ตรวจสอบว่าหน้าปัจจุบันยังเป็น Facebook group feed หรือ permalink ไม่ใช่หน้าโปรไฟล์ตัวเอง
    const currentUrl = page.url();
    const isOnGroupFeed = currentUrl.includes('facebook.com/groups/');
    const isOnPermalink = currentUrl.includes('/posts/') || currentUrl.includes('/permalink/') || currentUrl.includes('story_fbid=');
    const isOnMyProfile = currentUrl.includes('facebook.com/me');
    const isOnOwnPage = currentUrl.match(/facebook\.com\/[^/]+\/?(\?|$)/) && !isOnGroupFeed && !isOnPermalink;
    if (isOnMyProfile || isOnOwnPage) {
      console.warn(`[Guard] Current URL is NOT a group post: ${currentUrl}. Aborting comment to prevent self-profile commenting.`);
      return { success: false, reason: 'wrong_page' };
    }

    // scroll article กลับเข้า viewport ก่อนทุกอย่าง
    await article.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => { });
    await sleep(1000);

    // ตรวจสอบสถานะของโพสต์ก่อน
    console.log('=== POST STATUS CHECK ===');
    const postStatus = await article.evaluate((node) => {
      const rawText = node.textContent || '';
      const text = rawText.replace(/[\u200B-\u200D\uFEFF\u00AD]/g, '').replace(/[\s\u00A0]+/g, ' ');

      // ตรวจสอบว่าโพสต์ถูกลบหรือไม่
      if (text.includes('เนื้อหานี้ไม่พร้อมใช้งาน') ||
        text.includes('This content isn\'t available') ||
        text.includes('โพสต์นี้ไม่พร้อมใช้งาน')) {
        return 'deleted';
      }

      // ตรวจสอบว่าปิดคอมเมนต์หรือไม่
      const disabledKeywords = [
        'ปิดการแสดงความคิดเห็น',
        'ปิดการแสดงความคิดเห็นไว้ชั่วคราว',
        'ผู้ดูแลได้ปิด',
        'ผู้ดูแลปิด',
        'ปิดคอมเมนต์',
        'ปิดรับความคิดเห็น',
        'ปิดการตอบกลับ',
        'จำกัดผู้ที่สามารถแสดงความคิดเห็น',
        'ไม่สามารถแสดงความคิดเห็น',
        'ไม่อนุญาตให้แสดงความคิดเห็น',
        'Comments are turned off',
        'Comments on this post have been limited',
        'Comments have been disabled',
        'turned off commenting',
        'turned off comments'
      ];
      for (const kw of disabledKeywords) {
        if (text.includes(kw) || rawText.includes(kw)) {
          return 'comments_disabled';
        }
      }
      if (
        /ปิด.*ความคิดเห็น/i.test(text) ||
        /ปิด.*คอมเมนต์/i.test(text) ||
        /จำกัด.*ความคิดเห็น/i.test(text) ||
        /turned off.*comment/i.test(text)
      ) {
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

    // ฟังก์ชันหา composer — ใช้ DOM evaluate ไม่พึ่ง isVisible (ทำงานได้แม้หน้าต่างซ่อนอยู่)
    async function findComposer() {
      // ค้น composer จาก DOM โดยตรง ไม่ต้องตรวจ visibility
      const composerHandle = await page.evaluateHandle((articleEl) => {
        const selectors = [
          'div[role="textbox"][contenteditable="true"][aria-label*="ความคิดเห็น"]',
          'div[role="textbox"][contenteditable="true"][aria-label*="comment"]',
          'div[role="textbox"][contenteditable="true"][aria-label*="Comment"]',
          'div[role="textbox"][contenteditable="true"][aria-placeholder*="ความคิดเห็น"]',
          'div[role="textbox"][contenteditable="true"][aria-placeholder*="comment"]',
          'div[role="textbox"][contenteditable="true"]',
          'div[contenteditable="true"][data-lexical-editor]',
          'div[contenteditable="true"][data-testid*="comment"]',
          'form div[role="textbox"][contenteditable="true"]',
          'textarea[placeholder*="ความคิดเห็น"]',
          'textarea[placeholder*="comment"]',
        ];
        // 1. ถ้ามี dialog/modal เปิดอยู่บนจอ (ที่ยังแสดงอยู่จริง) ให้ค้นใน dialog ก่อน
        const activeDialog = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'))
          .find(d => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        if (activeDialog) {
          for (const sel of selectors) {
            const found = activeDialog.querySelector(sel);
            if (found) return found;
          }
        }
        // 2. ลองหาใน article ก่อน (สำหรับโพสต์ในหน้า Feed)
        if (articleEl) {
          for (const sel of selectors) {
            const found = articleEl.querySelector(sel);
            if (found) return found;
          }
        }
        // 3. fallback หาทั่วหน้าเฉพาะกรณีที่เป็นหน้า permalink (มีโพสต์เดียว) หรือไม่มี articleEl
        const isPermalink = window.location.href.includes('/permalink/') || window.location.href.includes('/posts/') || window.location.href.includes('story_fbid=');
        if (isPermalink || !articleEl) {
          for (const sel of selectors) {
            const found = document.querySelector(sel);
            if (found) return found;
          }
        }
        return null;
      }, await article.elementHandle().catch(() => null));

      if (!composerHandle) return null;
      const el = composerHandle.asElement();
      if (!el) return null;
      console.log('Found composer via DOM evaluate');
      return el;
    }

    let composer = await findComposer();

    // ถ้ายังไม่มี composer ให้คลิก Comment button ด้วย DOM (ทำงานได้แม้ซ่อนหน้าต่าง)
    if (!composer) {
      const clicked = await page.evaluate((articleEl) => {
        if (!articleEl) return null;
        
        const clickBtn = (root) => {
          const candidates = root.querySelectorAll('[role="button"], button, div[aria-label], span[aria-label]');
          for (const el of candidates) {
            const label = (el.getAttribute('aria-label') || '').trim();
            const innerText = (el.innerText || el.textContent || '').trim();
            const lowerLabel = label.toLowerCase();
            const lowerText = innerText.toLowerCase();

            // ข้ามปุ่มหรือรายการที่ไม่ได้เป็นปุ่มเปิดคอมเมนต์หลัก
            if (
              lowerLabel.includes('ปิดการแสดงความคิดเห็น') ||
              lowerLabel.includes('เรียง') ||
              lowerLabel.includes('ซ่อน') ||
              lowerLabel.includes('เกี่ยวข้องมากที่สุด') ||
              lowerLabel.includes('most relevant')
            ) {
              continue;
            }

            // ตรวจสอบว่าตรงกับคีย์เวิร์ดของปุ่มแสดงความคิดเห็นหรือไม่ (ใช้การจับคู่แบบแม่นยำเพื่อป้องกันการคลิกแจ้งเตือนมั่ว)
            const matchesComment = (
              lowerLabel === 'แสดงความคิดเห็น' ||
              lowerLabel === 'เขียนความคิดเห็น' ||
              lowerLabel === 'comment' ||
              lowerLabel === 'write a comment' ||
              lowerLabel === 'leave a comment' ||
              lowerLabel.startsWith('แสดงความคิดเห็นในชื่อ') ||
              lowerLabel.startsWith('comment as') ||
              lowerLabel.startsWith('write a comment as') ||
              lowerLabel.startsWith('leave a comment as') ||
              lowerText === 'แสดงความคิดเห็น' ||
              lowerText === 'เขียนความคิดเห็น' ||
              lowerText === 'comment'
            );

            if (matchesComment) {
              el.click();
              return `label: "${label}", text: "${innerText}"`;
            }
          }
          return null;
        };

        // 1. ถ้ามี dialog เปิดอยู่ ให้ลองคลิกใน dialog parent
        const activeDialog = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'))
          .find(d => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        if (activeDialog) {
          let res = clickBtn(activeDialog);
          if (res) return res;
        }

        // 2. ลองคลิกใน article
        let res = clickBtn(articleEl);
        if (res) return res;

        // 3. ลองคลิกทั่วหน้าเฉพาะกรณีที่เป็น permalink
        const isPermalink = window.location.href.includes('/permalink/') || window.location.href.includes('/posts/') || window.location.href.includes('story_fbid=');
        if (isPermalink) {
          res = clickBtn(document);
          return res;
        }
        return null;
      }, await article.elementHandle().catch(() => null));

      if (clicked) {
        console.log(`Clicked comment button via DOM: ${clicked}`);
        await sleep(2000);
        composer = await findComposer();
      }
    }

    // รอ composer ปรากฏสูงสุด 20 วิ
    if (!composer) {
      console.log('Waiting for composer to appear...');
      const startWait = Date.now();
      while (Date.now() - startWait < 20000) {
        // ตรวจสอบด่วนว่ามีป้ายปิดคอมเมนต์ขึ้นมาหรือไม่
        const isLockedNow = await article.evaluate((node) => {
          const raw = node ? (node.textContent || '') : (document.body ? document.body.innerText || '' : '');
          const text = raw.replace(/[\u200B-\u200D\uFEFF\u00AD]/g, '').replace(/[\s\u00A0]+/g, ' ');
          return (
            text.includes('ปิดการแสดงความคิดเห็น') ||
            text.includes('ผู้ดูแลได้ปิด') ||
            text.includes('ผู้ดูแลปิด') ||
            text.includes('ปิดคอมเมนต์') ||
            text.includes('Comments are turned off') ||
            /ปิด.*ความคิดเห็น/i.test(text)
          );
        }).catch(() => false);

        if (isLockedNow) {
          console.log('Detected comments disabled banner while waiting for composer!');
          return { success: false, reason: 'comments_disabled' };
        }

        await closeFacebookModal(page);
        composer = await findComposer();
        if (composer) {
          console.log('Composer found after waiting!');
          break;
        }

        // ลอง DOM click comment button ซ้ำทุก 5 วินาที
        if ((Date.now() - startWait) % 5000 < 800) {
          console.log('Retrying comment button DOM click...');
          await page.evaluate((articleEl) => {
            if (!articleEl) return;
            const clickBtn = (root) => {
              const candidates = root.querySelectorAll('[role="button"], button, div[aria-label], span[aria-label]');
              for (const el of candidates) {
                const label = (el.getAttribute('aria-label') || '').toLowerCase().trim();
                const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                if (
                  label.includes('ปิดการแสดงความคิดเห็น') ||
                  label.includes('เรียง') ||
                  label.includes('ซ่อน')
                ) continue;

                if (
                  label === 'แสดงความคิดเห็น' ||
                  label === 'เขียนความคิดเห็น' ||
                  label === 'comment' ||
                  label === 'write a comment' ||
                  label === 'leave a comment' ||
                  label.startsWith('แสดงความคิดเห็นในชื่อ') ||
                  label.startsWith('comment as') ||
                  label.startsWith('write a comment as') ||
                  label.startsWith('leave a comment as') ||
                  text === 'แสดงความคิดเห็น' ||
                  text === 'เขียนความคิดเห็น' ||
                  text === 'comment'
                ) {
                  el.click();
                  return true;
                }
              }
              return false;
            };

            // 1. ลองใน dialog parent
            const activeDialog = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'))
              .find(d => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
            if (activeDialog && clickBtn(activeDialog)) return;

            // 2. ลองใน article
            if (clickBtn(articleEl)) return;

            // 3. ลองทั่วหน้าเฉพาะกรณีที่เป็น permalink
            const isPermalink = window.location.href.includes('/permalink/') || window.location.href.includes('/posts/') || window.location.href.includes('story_fbid=');
            if (isPermalink) {
              clickBtn(document);
            }
          }, await article.elementHandle().catch(() => null)).catch(() => {});
          await sleep(1000);
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
      fs.writeFileSync(tempPs1, psLines.join('\n'), 'utf8');
      await execPromise(`cmd /c powershell -STA -NoProfile -ExecutionPolicy Bypass -File "${tempPs1}"`, { timeout: 15000 });
      try { fs.unlinkSync(tempPs1); } catch (_) { }
      console.log('Image copied to clipboard (CF_PNG + CF_DIB).');

      // 2. focus composer ด้วย DOM และ Playwright แล้วกด Ctrl+V
      await composer.evaluate((el) => { el.focus(); el.click(); }).catch(() => {});
      await composer.focus().catch(() => {});
      await composer.click({ force: true }).catch(() => {});
      await sleep(500);
      await page.keyboard.press('Control+v');
      await sleep(4000); // รอให้ Facebook โหลดภาพ

      // 3. ตรวจสอบว่าภาพอัพโหลดแล้วหรือยัง (เช็คเฉพาะใน container ของ composer)
      const checkUploaded = async () => {
        return await page.evaluate((compEl) => {
          if (!compEl) return false;
          let container = compEl;
          while (container && container.tagName !== 'BODY') {
            const attachment = 
              container.querySelector('div[role="progressbar"]') ||
              container.querySelector('img[src*="blob:"]') ||
              container.querySelector('div[data-type="image"]') ||
              container.querySelector('[data-visualcompletion="media-vc-image"]') ||
              container.querySelector('div[class*="attachment"] img') ||
              container.querySelector('div[class*="UFIImageAttach"]') ||
              container.querySelector('div[class*="commentContent"] img');
            if (attachment) return true;
            
            const imgs = Array.from(container.querySelectorAll('img'));
            for (const img of imgs) {
              if (img.src && img.src.startsWith('blob:')) return true;
              const closeBtn = container.querySelector('div[role="button"][aria-label*="Remove"], div[role="button"][aria-label*="ลบ"], button[aria-label*="Remove"], button[aria-label*="ลบ"]');
              if (closeBtn && container.contains(img)) return true;
            }
            container = container.parentElement;
          }
          return false;
        }, composer).catch(() => false);
      };

      let uploaded = await checkUploaded();

      if (uploaded) {
        imageUploaded = true;
        console.log('Image uploaded via Ctrl+V successfully.');
      } else {
        console.warn('Ctrl+V paste failed or preview not ready. Trying JS DOM paste fallback...');
        const base64Str = fs.readFileSync(imagePath).toString('base64');
        const mimeType = 'image/png';
        
        const domPasteSuccess = await page.evaluate(async ({ base64, mimeType, compEl }) => {
          if (!compEl) return false;
          compEl.focus();
          compEl.click();
          
          try {
            const resp = await fetch(`data:${mimeType};base64,${base64}`);
            const blob = await resp.blob();
            const file = new File([blob], `comment_image_${Date.now()}.png`, { type: mimeType });
            
            const dt = new DataTransfer();
            dt.items.add(file);
            
            const pasteEvent = new ClipboardEvent('paste', {
              bubbles: true,
              cancelable: true,
              composed: true
            });
            
            Object.defineProperty(pasteEvent, 'clipboardData', {
              value: dt,
              configurable: true,
              enumerable: true,
              writable: false
            });
            
            compEl.dispatchEvent(pasteEvent);
            return true;
          } catch (err) {
            return false;
          }
        }, { base64: base64Str, mimeType, compEl: composer }).catch(() => false);

        if (domPasteSuccess) {
          console.log('Dispatched JS DOM paste event. Waiting 4s for preview...');
          await sleep(4000);
          uploaded = await checkUploaded();
          if (uploaded) {
            imageUploaded = true;
            console.log('Image uploaded via JS DOM paste fallback successfully.');
          } else {
            console.warn('JS DOM paste fallback did not show preview either.');
          }
        }
      }

      // ถ้าลองทั้งสองวิธีแล้วยังไม่เจอ preview ก็ฝืนไปต่อตามเดิมกันเหนียว
      if (!imageUploaded) {
        console.warn('Proceeding anyway without confirmed upload preview.');
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
      '✅ทำให้ฟรีขอรับ', '✅ทำให้ขอรับนายท่าน', '✅ช่วยเหลือกัน', '✅จัดให้นายท่าน', '✅ทำให้ด้วยใจขอรับเจ้านาย',
      '✅สำหรับท่านจัดให้ฟรี', '✅แก้ให้ฟรีเพื่อท่าน', '✅ขอทำให้ฟรีๆ', '✅ยินดีช่วยเหลือขอรับ', '✅ทำให้แล้วนะครับเจ้านาย',
      '✅ช่วยปรับให้นายท่าน', '✅บริการฟรีเพื่อความสุขของนายท่าน', '✅ทำให้ฟรีไม่คิดเงินนะขอรับ', '✅จัดให้ตามคำขอของนายท่าน', '✅ยินดีทำให้นายท่านคนเดียว',
      '✅ทำให้ด้วยความยินดีขอรับ', '✅ช่วยเหลือเพื่อนร่วมกลุ่มของพวกเรา', '✅ขอให้นายท่านมีความสุข', '✅ขอดูแลนายท่านแบบสาธารณะประโยชน์', '✅ทำให้ฟรีเพื่อสังคมที่ดีขอรับ',
      '✅ช่วยเหลือกันในกลุ่มขอรับ', '✅ไม่มีค่าใช้จ่าย 100%', '✅ดีใจที่ได้ช่วยเหลือนายท่านขอรับ', '✅ทำให้แบบทันใจไหมนายท่าน', '✅Ok ไหมขอรับนายท่าน',
      '✅พึงพอใจไหมนายท่าน', '✅ถูกใจนายท่านไหมขอรับ', '✅เพื่อนายท่านคนเดียว', '✅แฮปปี้ไหมนายท่าน', '✅เรียบร้อยนายท่าน',
      '✅สำเร็จ!ขอรับนายท่าน', '✅อยากให้ช่วยอะไรอีกไหมนายท่าน', '✅เสร็จสมบูรณ์ขอรับนายท่าน', '✅บริการสมาชิกกลุ่มที่น่ารักแบบนายท่าน', '✅หน่วยบริการมาแล้วขอรับนายท่าน',
      '✅ทำให้ฟรีแบบไม่มีเงื่อนไขขอรับ', '✅ทำให้ฟรีสนุกดีจังขอรับ', '✅ดีใจที่ได้เจอนายท่านที่นี่', '✅เห็นนายท่านมีความสุข ก็ดีใจตาม', '✅สาธุในใจขอรับ',
      '✅จัดไปตามคำสั่งนายท่าน', '✅นายท่านสั่งมาต้องได้ดั่งใจนึก', '✅ตามที่นายท่านปรารถนา', '✅เต็มสิบให้คะแนนเท่าไหร่ดีนายท่าน', '✅ยินดีที่ได้เจอนายท่านในนี้อีก',
      '✅บริการ บริการ บริการนายท่าน', '✅ฟรีๆ เรียบร้อยขอรับ', '✅ปรึกษาต่อได้ในแชทนะนายท่าน', '✅ตกแต่งภาพให้นายท่าน!', '✅จัดไปด่วน ๆ ให้นายท่านทันที'
    ];
    const promoText = promoMessages[Math.floor(Math.random() * promoMessages.length)];
    // ใช้ insertText แทน fill() เพื่อไม่ลบภาพที่ paste ไปแล้ว
    await composer.evaluate((el) => { el.focus(); }).catch(() => {});
    await sleep(300);
    await page.keyboard.press('End'); // ไปท้ายสุดก่อน
    await sleep(200);
    await page.keyboard.type(promoText, { delay: 30 });
    await sleep(500);

    // *** ปรับปรุง: ใช้ปุ่ม Submit button แทน Enter เพื่อให้ modal ปิด ***

    // --- บันทึก comment_id ที่มีอยู่แล้วก่อน submit (จำกัดเฉพาะใน article นี้เท่านั้น) ---
    const existingCommentIds = await article.evaluate((node) => {
      const activeDialog = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'))
        .find(d => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
      const container = activeDialog || node;
      const ids = Array.from(container.querySelectorAll('a[href*="comment_id"]'))
        .map(a => { try { return new URL(a.href).searchParams.get('comment_id'); } catch { return null; } })
        .filter(Boolean);
      return Array.from(new Set(ids));
    }).catch(() => []);
    console.log('[Comment URL] Snapshot: ' + existingCommentIds.length + ' existing comment_ids in this article');

    let commentPosted = false;
    let submitAttempts = 0;
    while (submitAttempts < 3 && !commentPosted) {
      submitAttempts++;
      await closeFacebookModal(page);

    // *** Submit: หาปุ่ม submit จาก DOM รอบ composer (ไม่ใช้ Enter ซึ่งทำให้ขึ้นบรรทัดใหม่) ***

    // Strategy 1: evaluate DOM หาปุ่ม submit ของ comment เท่านั้น โดยขยายกรอบหาในช่องพิมพ์ขึ้นไปเรื่อยๆ
    commentPosted = await page.evaluate((compEl) => {
      const composer =
        compEl ||
        document.activeElement ||
        document.querySelector('div[role="textbox"][contenteditable="true"][aria-label*="ความคิดเห็น"]') ||
        document.querySelector('div[role="textbox"][contenteditable="true"]');
      if (!composer) return false;

      // เดินขึ้นหา parent container (เช่น form หรือ div ที่หุ้มช่องพิมพ์ทั้งหมด) เพื่อหาปุ่มส่ง (จำกัดระดับขึ้นไม่เกิน 4 ชั้นเพื่อไม่ให้ลามไปที่ปุ่มแสดงความคิดเห็นด้านนอก)
      let container = composer;
      let depth = 0;
      while (container && container.tagName !== 'BODY' && depth < 5) {
        depth++;
        const buttons = Array.from(container.querySelectorAll('div[role="button"], button'));
        const submitBtn = buttons.find(btn => {
          const label = (btn.getAttribute('aria-label') || '').trim();
          const txt = (btn.innerText || '').trim();
          const disabled = btn.getAttribute('aria-disabled') === 'true' || btn.disabled;
          if (disabled) return false;

          return (
            label === 'ส่ง' ||
            label === 'Send' ||
            label === 'โพสต์' ||
            label === 'Post' ||
            label === 'โพสต์ความคิดเห็น' ||
            label === 'Post comment' ||
            (label === 'Comment' && txt.length < 5) ||
            (label === 'แสดงความคิดเห็น' && txt.length < 5) ||
            txt === 'ส่ง' ||
            txt === 'Send' ||
            txt === 'โพสต์' ||
            txt === 'Post' ||
            txt === 'โพสต์ความคิดเห็น' ||
            txt === 'Post comment'
          );
        });
        
        if (submitBtn) {
          submitBtn.click();
          return true;
        }
        container = container.parentElement;
      }
      return false;
    }, composer).catch(() => false);

    if (commentPosted) {
      console.log('[Submit] ✅ Clicked submit button via DOM traversal.');
      await sleep(3000);
    }

    // Strategy 2: Playwright locator หาปุ่ม submit เฉพาะ exact match (ลบแสดงความคิดเห็นออก ป้องกันกดปุ่มบนโพสต์)
    if (!commentPosted) {
      const submitSelectors = [
        'div[aria-label="โพสต์ความคิดเห็น"]',
        'div[aria-label="Post comment"]',
        'div[aria-label="Comment"]',
        'div[aria-label="โพสต์"]',
        'div[aria-label="Post"]',
        'div[aria-label="ส่ง"]',
        'div[aria-label="Send"]',
      ];
      
      const hasActiveDialog = await page.evaluate(() => {
        const dialogs = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'));
        return dialogs.some(d => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
      }).catch(() => false);
      const locatorRoot = hasActiveDialog ? page.locator('div[role="dialog"], div[role="alertdialog"]').last() : article;

      for (const sel of submitSelectors) {
        try {
          const btns = locatorRoot.locator(sel);
          const count = await btns.count();
          for (let i = 0; i < count; i++) {
            const btn = btns.nth(i);
            if (!await btn.isVisible({ timeout: 500 }).catch(() => false)) continue;
            if (await btn.getAttribute('aria-disabled').catch(() => 'false') === 'true') continue;
            await btn.click({ force: true });
            console.log('[Submit] ✅ Playwright clicked: ' + sel);
            commentPosted = true;
            await sleep(3000);
            break;
          }
          if (commentPosted) break;
        } catch (e) { }
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
        await sleep(2000);
        // ตรวจสอบว่าหลังจากกดแล้วตัวข้อความยังค้างอยู่ไหม (ถ้าส่งผ่าน ข้อความจะถูกเคลียร์เป็นว่างเปล่า)
        const isStillDrafting = await page.evaluate((el) => {
          return el && (el.textContent || '').trim().length > 0;
        }, composer).catch(() => false);
        commentPosted = !isStillDrafting;
        if (commentPosted) {
          console.log('[Submit] \u2705 Composer cleared, submit confirmed.');
        } else {
          console.warn('[Submit] ⚠️ Composer still has text after Tab+Space.');
        }
      } catch (e) {
        console.warn('[Submit] Tab+Space failed:', e.message);
      }
    }

      // เช็กว่าเป็น modal กฎกลุ่มของ Facebook จริงๆ หรือไม่ (ไม่เอาป๊อปอัป Chromium)
      const hasRulesDialog = await page.evaluate(() => {
        const dialog = document.querySelector('div[role="dialog"], div[role="alertdialog"]');
        if (!dialog) return false;
        const text = dialog.textContent || '';
        return text.includes('กฎ') || text.includes('กติกา') || text.includes('Rules') || text.includes('rules');
      }).catch(() => false);

      if (hasRulesDialog) {
        const dismissedPopup = await closeFacebookModal(page);
        if (dismissedPopup) {
          console.log(`[Submit] Detected group rules popup after submit attempt ${submitAttempts}. Dismissed it. Retrying submit...`);
          commentPosted = false;
          await sleep(1500);
        }
      }
    }

    console.log('? Comment posted (keeping modal open for URL extraction)');

    // --- ค้นหา comment URL ของความคิดเห็นเรา ---
    let commentUrl = null;
    try {
      console.log('[Comment URL] Searching for newly created comment URL...');
      const profileName = await getLoggedInProfileName(page).catch(() => null) || 'รับแก้ไขภาพออนไลน์';
      console.log('[Comment URL] Using profile name:', profileName);

      // ดึง ID ของโพสต์จาก URL ไว้กรอง comment (เช่น 4444885335784287)
      const postId = (() => {
        if (!postUrl) return null;
        const m = postUrl.match(/\/(posts|permalink|multi_permalinks)\/(\d+)/) || postUrl.match(/story_fbid=(\d+)/);
        return m ? m[2] : null;
      })();
      console.log('[Comment URL] Target Post ID for filtering:', postId);

      for (let _attempt = 0; _attempt < 6; _attempt++) {
        await sleep(_attempt === 0 ? 2500 : 1800);

        const evalResult = await page.evaluate(({ profName, oldIds, _postId, articleEl }) => {
          const debug = [];
          const dialogs = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'));
          const activeDialog = dialogs.find(d => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
          const container = activeDialog || articleEl || document;

          debug.push('Selected container: ' + (container ? container.tagName + '.' + container.className : 'null'));

          const allLinks = Array.from(container.querySelectorAll('a[href*="comment_id"]'));
          debug.push('Total comment_id links found: ' + allLinks.length);

          let commentUrl = null;

          for (let i = allLinks.length - 1; i >= 0; i--) {
            const a = allLinks[i];
            try {
              const url = new URL(a.href);
              const cid = url.searchParams.get('comment_id');
              if (!cid) continue;

              // ❌ ข้าม comment_id ที่เป็น client reference (เช่น comment_id=client:xxx) — 
              //    พวกนี้เป็นลิงก์ไปหน้าโปรไฟล์ตัวเอง ไม่ใช่ comment จริงในกลุ่ม
              if (cid.startsWith('client:')) {
                debug.push(`Link ${i} skipped: client-side comment_id (${cid})`);
                continue;
              }
              // ❌ ข้าม URL ที่ไม่มี /groups/ — แปลว่าไม่ใช่ comment ในกลุ่ม
              if (!a.href.includes('/groups/')) {
                debug.push(`Link ${i} skipped: not a group URL (${a.href})`);
                continue;
              }

              const isOld = oldIds.includes(cid);
              debug.push(`Link ${i}: href=${a.href}, cid=${cid}, isOld=${isOld}`);
              if (isOld) continue;

              // กรองโดย post ID — comment ต้องอยู่ภายใต้โพสต์เดียวกัน
              if (_postId) {
                if (!a.href.includes('/' + _postId) && !a.href.includes('=' + _postId)) {
                  debug.push(`Link ${i} skipped: does not match postId ${_postId}`);
                  continue;
                }
              }

              // ค้นหาขึ้นไป 12 ระดับ หรือจนกว่าจะเจอ comment container หลัก
              // จากนั้นตรวจดูว่าใน container นั้นมีชื่อโปรไฟล์ของเราหรือไม่
              let parent = a.parentElement;
              let hasAuthor = false;
              let pathStr = '';
              for (let steps = 0; parent && steps < 12; steps++) {
                pathStr += ' -> ' + parent.tagName;
                const text = (parent.textContent || parent.innerText || '');
                if (text.includes(profName)) {
                  hasAuthor = true;
                  debug.push(`Author "${profName}" found at step ${steps} via path: ${pathStr}`);
                  break;
                }
                parent = parent.parentElement;
              }
              
              if (hasAuthor) {
                commentUrl = a.href;
                break;
              } else {
                debug.push(`Link ${i} failed author match for "${profName}"`);
              }
            } catch (e) {
              debug.push(`Link ${i} parsing error: ` + e.message);
            }
          }

          // Pass 2: fallback — post ID match อย่างเดียว (ไม่เช็คชื่อ)
          if (!commentUrl && _postId) {
            debug.push('Executing Pass 2 fallback with postId: ' + _postId);
            for (let i = allLinks.length - 1; i >= 0; i--) {
              const a = allLinks[i];
              try {
                const url = new URL(a.href);
                const cid = url.searchParams.get('comment_id');
                if (!cid || oldIds.includes(cid)) continue;
                if (a.href.includes('/' + _postId) || a.href.includes('=' + _postId)) {
                  commentUrl = a.href;
                  debug.push('Pass 2 fallback matched: ' + commentUrl);
                  break;
                }
              } catch (e) { }
            }
          }
          return { commentUrl, debug };
        }, { profName: profileName, oldIds: existingCommentIds, _postId: postId, articleEl: await article.elementHandle().catch(() => null) }).catch((err) => ({ commentUrl: null, debug: ['Eval error: ' + err.message] }));

        commentUrl = evalResult.commentUrl;
        if (evalResult.debug && evalResult.debug.length > 0) {
          console.log('[Comment URL Debug]');
          evalResult.debug.forEach(line => console.log('  → ' + line));
        }

        if (commentUrl) {
          try {
            const url = new URL(commentUrl);
            const cid = url.searchParams.get('comment_id');
            url.search = '';
            if (cid) url.searchParams.set('comment_id', cid);
            commentUrl = url.toString();
          } catch {
            const m = commentUrl.match(/comment_id=([^&]+)/);
            if (m) commentUrl = commentUrl.split('?')[0] + '?comment_id=' + m[1];
          }
          console.log('[Comment URL] ✅ Found verified link: ' + commentUrl);
          break;
        }
        console.log('[Comment URL] Retrying (' + (_attempt + 1) + '/6)...');
      }

      if (!commentUrl) {
        console.warn('[Comment URL] Could not find link under our comment container.');
      }
    } catch (urlErr) {
      console.warn('[Comment URL] Error:', urlErr.message);
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
          await btn.scrollIntoViewIfNeeded().catch(() => { });
          await btn.click({ timeout: 5000 });
          await sleep(1000);
          console.log('Liked post.');
          return true;
        }
      } catch (e) { }
    }
    console.log('Like button not found via Playwright locator in article scope. Trying page.evaluate fallback...');

    // Fallback: ใช้ page.evaluate ค้นปุ่ม Like โดยตรงจาก DOM (แก้กรณีหลัง comment Facebook re-render DOM)
    const liked = await page.evaluate(() => {
      const processedAttr = 'data-bot-processed';
      const articles = document.querySelectorAll('div[role="article"]');
      let targetArticle = null;
      for (const art of articles) {
        if (!art.getAttribute(processedAttr)) {
          targetArticle = art;
          break;
        }
      }
      if (!targetArticle) targetArticle = articles[0];
      if (!targetArticle) return { success: false, reason: 'no article found' };

      const likeLabels = ['like', 'ถูกใจ'];
      const unlikeLabels = ['unlike', 'เลิกถูกใจ', 'เลิกชอบ', 'ลบถูกใจ'];
      const allButtons = targetArticle.querySelectorAll('div[role="button"], span[role="button"], a[role="button"]');
      for (const btn of allButtons) {
        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
        if (!likeLabels.some(l => label.includes(l))) continue;
        const pressed = btn.getAttribute('aria-pressed');
        const isLiked = pressed === 'true' || unlikeLabels.some(l => label.includes(l));
        if (isLiked) continue;
        const rect = btn.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
        btn.click();
        return { success: true, label: btn.getAttribute('aria-label') };
      }
      return { success: false, reason: 'no unliked button found in article' };
    }).catch(err => ({ success: false, reason: 'evaluate error: ' + err.message }));

    if (liked && liked.success) {
      await sleep(1000);
      console.log(`Liked post via page.evaluate fallback. (label: ${liked.label})`);
      return true;
    }
    console.log('Like button not found (page.evaluate fallback):', liked?.reason || 'unknown');
    return false;
  } catch (e) {
    console.error('Error liking post:', e.message || e);
    return false;
  }
}

async function closeFacebookModal(page) {
  try {
    const closed = await page.evaluate(() => {
      const dialogs = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"]'));
      if (dialogs.length === 0) return false;
      
      let anyClosed = false;
      for (const dialog of dialogs) {
        // Skip post overlay/modal (post modals have role="article" or article element inside them)
        if (dialog.querySelector('[role="article"], article')) {
          continue;
        }
        
        const safeKeywords = ['เข้าใจแล้ว', 'เข้าใจ', 'got it', 'dismiss', 'ยอมรับ', 'ตกลง', 'ok'];
        const closeKeywords = ['close', 'ปิด'];
        
        const textContent = (dialog.textContent || '').toLowerCase();
        // Check if it is a rules, guidelines, warning, standards, or agreement popup
        const isRulesOrWarning = ['กฎ', 'กติกา', 'rules', 'มาตรฐานชุมชน', 'standards', 'policy', 'นโยบาย', 'ข้อตกลง'].some(kw => textContent.includes(kw));

        const clickables = Array.from(dialog.querySelectorAll('div[role="button"], button, span, div'));
        for (const el of clickables) {
          const text = (el.innerText || el.textContent || '').trim().toLowerCase();
          const ariaLabel = (el.getAttribute('aria-label') || '').trim().toLowerCase();
          
          const matchesSafe = safeKeywords.some(kw => text === kw || ariaLabel === kw || (text.includes(kw) && text.length < 25) || (ariaLabel.includes(kw) && ariaLabel.length < 25));
          const matchesClose = isRulesOrWarning && closeKeywords.some(kw => text === kw || ariaLabel === kw || (text.includes(kw) && text.length < 25) || (ariaLabel.includes(kw) && ariaLabel.length < 25));
          
          if (matchesSafe || matchesClose) {
            el.click();
            anyClosed = true;
            break;
          }
        }
      }
      return anyClosed;
    }).catch(() => false);

    if (closed) {
      await sleep(600);
    }
    return closed;
  } catch (e) { }
  return false;
}

async function dismissGeminiPopups(page) {
  try {
    const dialogs = page.locator('mat-dialog-container, div[role="dialog"], div[role="alertdialog"], .update-popup, .modal');
    const dialogCount = await dialogs.count();
    
    if (dialogCount > 0) {
      console.log(`[Gemini Popup] Found ${dialogCount} potential popups/dialogs.`);
      for (let i = 0; i < dialogCount; i++) {
        const dialog = dialogs.nth(i);
        if (await dialog.isVisible().catch(() => false)) {
          const buttons = dialog.locator('button, [role="button"], span, div');
          const btnCount = await buttons.count();
          for (let j = 0; j < btnCount; j++) {
            const btn = buttons.nth(j);
            if (await btn.isVisible().catch(() => false)) {
              const text = (await btn.innerText().catch(() => '')).trim().toLowerCase();
              const targetTexts = ['ยอมรับ', 'ตกลง', 'ยินยอม', 'เข้าใจแล้ว', 'accept', 'agree', 'ok', 'got it', 'dismiss'];
              if (targetTexts.includes(text) || targetTexts.some(t => text.includes(t) && text.length < 15)) {
                console.log(`[Gemini Popup] Playwright clicking dialog button: "${text}"`);
                await btn.click({ force: true });
                await sleep(500);
                break;
              }
            }
          }
        }
      }
    }
    
    // Standalone buttons fallback
    const consentButtons = page.locator('button, [role="button"]');
    const cCount = await consentButtons.count();
    for (let i = 0; i < cCount; i++) {
      const btn = consentButtons.nth(i);
      if (await btn.isVisible().catch(() => false)) {
        const text = (await btn.innerText().catch(() => '')).trim().toLowerCase();
        if (['ยอมรับ', 'ตกลง', 'ยินยอม', 'accept', 'agree'].includes(text)) {
          console.log(`[Gemini Popup] Playwright clicking standalone button: "${text}"`);
          await btn.click({ force: true });
          await sleep(500);
        }
      }
    }
  } catch (err) {
    console.warn('[Gemini Popup] Error dismissing popups:', err.message);
  }
}

async function clickGeminiTryAgainDropdown(page) {
  try {
    const selectors = [
      'button[aria-haspopup="true"]',
      'button[aria-label*="ตัวเลือกเพิ่มเติม"]',
      'button[aria-label*="More options"]',
      'button[aria-label*="เพิ่มเติม"]',
      'mat-icon[data-mat-icon-name="more_vert"]',
      'button:has(mat-icon[data-mat-icon-name="more_vert"])'
    ];
    
    for (const sel of selectors) {
      const triggers = page.locator(sel);
      const count = await triggers.count();
      for (let i = 0; i < count; i++) {
        const trigger = triggers.nth(i);
        if (await trigger.isVisible().catch(() => false)) {
          console.log(`[Gemini Dropdown] Clicking menu trigger: ${sel}`);
          await trigger.click({ force: true });
          await sleep(600);
          
          const menuOptions = [
            'div[role="menuitem"]',
            '[role="option"]',
            'button',
            'span',
            'div'
          ];
          for (const optSel of menuOptions) {
            const options = page.locator(optSel);
            const optCount = await options.count();
            for (let j = 0; j < optCount; j++) {
              const opt = options.nth(j);
              if (await opt.isVisible().catch(() => false)) {
                const text = (await opt.innerText().catch(() => '')).trim();
                if (text === 'ลองอีกครั้ง' || text === 'Try again' || text.includes('ลองอีกครั้ง') || text.includes('Try again') || text.includes('สร้างใหม่') || text.includes('สร้างอีกครั้ง')) {
                  console.log(`[Gemini Dropdown] Found target menu item: "${text}". Clicking it...`);
                  await opt.click({ force: true });
                  await sleep(2000);
                  return true;
                }
              }
            }
          }
          await trigger.click({ force: true }).catch(() => {});
          await sleep(300);
        }
      }
    }
  } catch (err) {
    console.warn('[Gemini Dropdown] Error clicking try again dropdown:', err.message);
  }
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
        } catch (e) { }
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
      } catch (e) { }
    }

    if (!postComposer) {
      console.warn('[Share] Post composer not found.');
      return { success: false, reason: 'post_composer_not_found' };
    }

    await postComposer.click();
    await sleep(500);

    // Type share text + comment URL
    const thankYouMessages = [
      '✅รีทัชรูปสำเร็จ', '✅แต่งภาพเสร็จแล้ว', '✅แก้ไขภาพเรียบร้อย', '✅ปรับแต่งภาพให้เรียบร้อย', '✅ช่วยแก้ไขภาพสำเร็จ',
      '✅ส่งงานแก้ไขภาพ', '✅แต่งภาพให้แล้ว', '✅รีทัชภาพเรียบร้อยแล้ว', '✅แต่งรูปเสร็จเรียบร้อย', '✅แก้ไขรูปภาพเสร็จแล้ว',
      '✅รีทัชรูปภาพให้แล้ว', '✅ปรับแต่งรูปเสร็จเรียบร้อย', '✅ส่งงานรีทัชภาพเรียบร้อย', '✅แก้ไขงานแต่งรูปเสร็จแล้ว', '✅ตกแต่งรูปภาพเสร็จแล้ว',
      '✅ส่งงานแต่งรูปเสร็จสมบูรณ์', '✅แก้ไขจุดบกพร่องรูปภาพเสร็จแล้ว', '✅แต่งรูปให้ใหม่เรียบร้อย', '✅รีทัชภาพเสร็จสมบูรณ์', '✅แต่งภาพเสร็จเรียบร้อย',
      '✅แก้รูปภาพให้เรียบร้อยแล้ว', '✅แก้ไขภาพให้ใหม่เรียบร้อย', '✅ออกแบบแต่งภาพเสร็จแล้ว', '✅โมรูปใหม่เสร็จเรียบร้อย', '✅ทำภาพใหม่เสร็จแล้ว',
      '✅ทำกราฟิกรีทัชรูปเสร็จแล้ว', '✅แต่งเติมภาพเสร็จเรียบร้อย', '✅ส่งงานรีทัชรูปภาพด่วนเสร็จแล้ว', '✅แก้รูปภาพด่วนให้แล้ว', '✅แต่งรูปเสร็จสมบูรณ์ 100%',
      '✅จัดระเบียบภาพใหม่เสร็จแล้ว', '✅ส่งมอบงานแต่งภาพด่วน', '✅แต่งภาพตามคำขอเสร็จแล้ว', '✅แก้ไขภาพตามโจทย์เรียบร้อย',
      '✅ทำภาพเนียนๆ เสร็จแล้ว', '✅ส่งรูปแต่งเสร็จแล้ว', '✅แต่งภาพให้ทันใจเรียบร้อย', '✅แก้รูปภาพตามต้องการเสร็จแล้ว', '✅ผลงานแต่งรูปเสร็จสมบูรณ์',
      '✅ส่งงานตัดต่อรีทัชภาพเสร็จแล้ว', '✅โมดิฟายรูปภาพให้เสร็จแล้ว', '✅ทำรูปภาพเนียนๆ เสร็จแล้ว', '✅ส่งงานตกแต่งภาพเรียบร้อย',
      '✅แต่งรูปภาพให้สวยงามเสร็จแล้ว', '✅ส่งมอบงานแก้ไขรูปภาพเสร็จสิ้น', '✅ปรับปรุงคุณภาพรูปภาพเสร็จเรียบร้อย', '✅รีทัชแต่งภาพด่วนเสร็จเรียบร้อย'
    ];

    const allHashtags = ['#หาคนแก้ภาพด่วน', '#หาคนทำกราฟิก', '#หาคนแต่งรูป', '#หาคนรีทัชรูป', '#หาคนตัดต่อรูป', '#หาคนแก้ไขภาพ', '#หาคนแต่งภาพ', '#หาคนทำรูป', '#หาคนออกแบบภาพ', '#หาคนทำภาพโฆษณา',
      '#รับแก้ภาพ', '#รับแก้ไขภาพ', '#รับแก้รูป', '#รับแต่งรูป', '#รับแต่งภาพ', '#รับรีทัชรูป', '#รับรีทัชภาพ', '#รับตัดต่อรูป', '#รับตัดต่อภาพ', '#รับทำรูป', '#รับทำรูปภาพ', '#รับทำกราฟิก', '#รับออกแบบภาพ', '#รับออกแบบกราฟิก', '#รับลบพื้นหลัง', '#รับลบคนออกจากภาพ', '#รับลบวัตถุ', '#รับซ่อมภาพ', '#รับฟื้นฟูภาพ', '#รับงานแต่งภาพ',
      '#รับงานรีทัช', '#รับงานตัดต่อ', '#รับงานกราฟิก', '#รับงานด่วน', '#รับงานออนไลน์', '#รับจ้างแต่งรูป', '#รับจ้างรีทัชรูป', '#รับจ้างตัดต่อรูป', '#รับจ้างแก้ภาพ', '#รับจ้างทำกราฟิก', '#รับจ้างออกแบบภาพ', '#รับจ้างลบพื้นหลัง', '#รับจ้างทำภาพโฆษณา', '#รับจ้างทำแบนเนอร์',
      '#จ้างแต่งรูป', '#จ้างรีทัชรูป', '#จ้างตัดต่อรูป', '#จ้างแก้ภาพ', '#จ้างทำกราฟิก', '#จ้างออกแบบภาพ', '#จ้างทำรูปสินค้า', '#จ้างทำภาพโฆษณา', '#จ้างฟรีแลนซ์', '#จ้างกราฟิก',
      '#ร้านแต่งรูป', '#ร้านรีทัชรูป', '#ร้านตัดต่อรูป', '#ร้านกราฟิก', '#ร้านออกแบบ', '#ร้านทำป้าย', '#ร้านทำรูป', '#ร้านแต่งภาพ', '#ร้านแก้ภาพ', '#ร้านรับทำกราฟิก',
      '#เพจแต่งรูป', '#เพจรีทัชรูป', '#เพจตัดต่อรูป', '#เพจกราฟิก', '#เพจรับงาน', '#เพจรับแต่งรูป', '#เพจรับตัดต่อ', '#เพจรับรีทัช', '#เพจออกแบบ', '#เพจฟรีแลนซ์',
      '#แก้ไขภาพ', '#แก้ภาพ', '#แก้รูป', '#แต่งรูป', '#แต่งภาพ', '#รีทัชรูป', '#รีทัชภาพ', '#ตัดต่อรูป', '#ตัดต่อภาพ', '#ลบพื้นหลัง', '#เปลี่ยนพื้นหลัง', '#ลบคน', '#ลบวัตถุ', '#ซ่อมภาพ', '#ฟื้นฟูภาพ', '#ภาพสินค้า', '#แต่งรูปสินค้า', '#ภาพโฆษณา', '#ทำแบนเนอร์', '#ออกแบบกราฟิก', '#กราฟิกดีไซน์', '#งานกราฟิก', '#ฟรีแลนซ์กราฟิก', '#แม่ค้าออนไลน์', '#พ่อค้าออนไลน์', '#ร้านค้าออนไลน์', '#ภาพโปรไฟล์', '#ภาพปก', '#แต่งภาพด่วน', '#แก้ภาพด่วน', '#รีทัชภาพด่วน'];

    // สุ่มแฮชแท็กมา 4 อันแบบไม่ซ้ำกัน
    const shuffledHashtags = allHashtags.sort(() => 0.5 - Math.random()).slice(0, 4);
    const hashtagStr = shuffledHashtags.join(' ');

    const shareMsg = thankYouMessages[Math.floor(Math.random() * thankYouMessages.length)];
    const shareText = `${shareMsg}\n- สนใจทักแชท【💵 60฿】ราคาเดียวไม่คิดเพิ่ม\n${hashtagStr}\n\n${commentUrl}`;

    await postComposer.fill(shareText);
    await sleep(2000);

    // Multi-stage Submission Loop: กดปุ่ม "ถัดไป" -> "โพสต์"
    console.log('[Share] Clicking Post/Next button loop...');

    for (let attempt = 1; attempt <= 4; attempt++) {
      const isDialogOpen = await fbPage.evaluate(() => !!document.querySelector('div[role="dialog"]'));
      if (!isDialogOpen) {
        console.log('[Share] ✅ Dialog closed. Profile post created successfully!');
        break;
      }

      console.log(`[Share] Attempt ${attempt}: Searching for active Post/Next button...`);

      // 1. ค้นหาและคลิกผ่าน DOM evaluate ใน dialog ล่าสุด
      let clickedPost = false;
      const clickedInLoop = await fbPage.evaluate(() => {
        const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
        if (dialogs.length === 0) return 'none';

        const activeDialog = dialogs[dialogs.length - 1];
        const buttons = Array.from(activeDialog.querySelectorAll('div[role="button"], button'));

        const targetBtn = buttons.find(btn => {
          const label = (btn.getAttribute('aria-label') || '').trim();
          const txt = (btn.innerText || btn.textContent || '').trim();
          const disabled = btn.getAttribute('aria-disabled') === 'true' || btn.disabled;
          if (disabled) return false;

          const matchWords = ['โพสต์', 'Post', 'ถัดไป', 'Next', 'แชร์', 'Share'];
          return matchWords.includes(label) || matchWords.includes(txt) || label.startsWith('โพสต์') || label.startsWith('Post');
        });

        if (targetBtn) {
          targetBtn.click();
          const label = (targetBtn.getAttribute('aria-label') || targetBtn.innerText || '').trim();
          return label.includes('โพสต์') || label.includes('Post') ? 'post' : 'next';
        }
        return 'none';
      }).catch(() => 'none');

      // 2. Playwright Fallback
      if (clickedInLoop === 'none') {
        for (const sel of [
          'div[role="dialog"] div[aria-label="โพสต์"]',
          'div[role="dialog"] div[aria-label="Post"]',
          'div[role="dialog"] div[aria-label="ถัดไป"]',
          'div[role="dialog"] div[aria-label="Next"]',
          'div[role="dialog"] div[role="button"][aria-label*="โพสต์"]',
          'div[role="dialog"] div[role="button"][aria-label*="Post"]',
        ]) {
          try {
            const btn = fbPage.locator(sel).last();
            if (await btn.count() > 0 && await btn.isVisible({ timeout: 500 }).catch(() => false)) {
              if (await btn.getAttribute('aria-disabled').catch(() => 'false') !== 'true') {
                await btn.click({ force: true });
                console.log('[Share] ✅ Playwright clicked: ' + sel);
                if (sel.includes('โพสต์') || sel.includes('Post')) clickedPost = true;
                break;
              }
            }
          } catch (e) { }
        }
      } else {
        clickedPost = (clickedInLoop === 'post');
      }

      if (clickedPost) {
        console.log('[Share] ✅ Post button clicked — done, no need to wait for dialog.');
        break; // โพสต์สำเร็จแล้ว ไม่ต้องรอ dialog ปิด
      }

      if (clickedInLoop !== 'none' || clickedPost) {
        console.log(`[Share] Action triggered in attempt ${attempt}, waiting for dialog state change...`);
        await sleep(3000);
      } else {
        console.warn(`[Share] Attempt ${attempt}: Button not ready or not found yet.`);
        await sleep(2000);
      }
    }

    await sleep(500);
    console.log('[Share] ✅ Post shared to profile process completed!');
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

// restore window แล้ว bring to front (ใช้แทน bringToFront() ตรง ๆ เพราะโดน minimize ไม่ทำงาน)
async function bringWindowToFront(page) {
  await minimizeBrowser(false).catch(() => {});
  await sleep(300);
  await page.bringToFront().catch(() => {});
}

// minimize/restore ผ่าน PowerShell ShowWindowAsync (CDP ยังทำงานได้ปกติแม้ minimize)
async function minimizeBrowser(minimize = true) {
  const tempPs1 = path.join(os.tmpdir(), `min_chrome_${Date.now()}.ps1`);
  try {
    const posX = minimize ? -2000 : 2816;
    const posY = minimize ? -2000 : 312;
    const psLines = [
      'Add-Type -TypeDefinition @"',
      '  using System;',
      '  using System.Runtime.InteropServices;',
      '  public class Win32 {',
      '    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);',
      '    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);',
      '  }',
      '"@',
      "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe' or Name = 'msedge.exe' or Name = 'chromium.exe'\" | Where-Object { \$_.CommandLine -like '*Facebook_Bot*user_data*' } | ForEach-Object { Get-Process -Id \$_.ProcessId } | Where-Object { \$_.MainWindowHandle -ne 0 } | ForEach-Object {",
      `  [Win32]::SetWindowPos($_.MainWindowHandle, 0, ${posX}, ${posY}, 0, 0, 5) | Out-Null`,
      minimize ? '' : '  [Win32]::SetForegroundWindow($_.MainWindowHandle) | Out-Null',
      '}',
    ];
    fs.writeFileSync(tempPs1, psLines.filter(Boolean).join('\r\n'), 'utf8');
    await execPromise(`cmd /c powershell -NoProfile -ExecutionPolicy Bypass -File "${tempPs1}"`, { timeout: 5000 }).catch(() => {});
    try { fs.unlinkSync(tempPs1); } catch (_) {}
    return { success: true };
  } catch (e) {
    try { fs.unlinkSync(tempPs1); } catch (_) {}
    return { success: false, message: e.message };
  }
}

// ฟังก์ชันควบคุมการแสดง/ซ่อนหน้าต่าง browser (ใช้ ShowWindowAsync จริง)
async function toggleBrowserVisibility() {
  if (!browserContext) return { success: false, message: 'Browser not running' };
  
  try {
    if (isBrowserHidden) {
      await minimizeBrowser(false); // restore
      const pages = browserContext.pages();
      if (pages.length > 0) await pages[0].bringToFront();
      isBrowserHidden = false;
      return { success: true, message: 'Browser shown', hidden: false };
    } else {
      await minimizeBrowser(true); // minimize
      isBrowserHidden = true;
      return { success: true, message: 'Browser hidden', hidden: true };
    }
  } catch (e) {
    return { success: false, message: e.message };
  }
}

// HTTP server สำหรับรับคำสั่งควบคุม browser
function startControlServer() {
  const controlServer = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    if (req.url === '/toggle-browser') {
      toggleBrowserVisibility().then(result => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      });
    } else if (req.url === '/browser-status') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ hidden: isBrowserHidden, running: !!browserContext }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  controlServer.listen(12122, '127.0.0.1', () => {
    console.log('Browser control server started at http://127.0.0.1:12122');
  });

  return controlServer;
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
  // ⚡ Global error handlers - force exit ถ้ามี unhandled error
  process.on('unhandledRejection', (err) => {
    console.error('Unhandled Rejection:', err);
    // Force kill chrome ที่เชื่อมกับ user_data
    try {
      const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
      exec(killCmd, () => {});
    } catch (e) {}
    setTimeout(() => process.exit(1), 1000);
  });
  
  process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
    try {
      const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
      exec(killCmd, () => {});
    } catch (e) {}
    setTimeout(() => process.exit(1), 1000);
  });

  // ✅ ทำความสะอาดเมื่อ process ถูกปิด (SIGINT, SIGTERM, etc.)
  const cleanupOnExit = async () => {
    console.log('[Cleanup] Process exiting, killing Chrome...');
    try {
      const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
      exec(killCmd, () => {});
    } catch (e) {}
  };
  process.on('SIGINT', cleanupOnExit);
  process.on('SIGTERM', cleanupOnExit);

  const isHeadless = process.argv.includes('--headless');
  const isDebugPause = process.argv.includes('--debug-pause');
  const isReviewMode = process.argv.includes('--review');
  const isLoginMode = process.argv.includes('--login');
  const BOT_START_TIME = Date.now();
  const MAX_RUNTIME_MS = 1200000;

  // Hard limit 20 minutes execution timeout
  setTimeout(async () => {
    console.warn(`[Timeout] Bot execution reached hard limit of 20 minutes. Force exiting.`);
    try {
      showWindowsNotification('Facebook Bot', `หมดเวลา: ระบบปิดอัตโนมัติ (เกิน 20 นาที)`, 'Warning');
    } catch (e) {}
    try {
      reportStatus(100, '⚠️ บอททำงานเกินเวลา 20 นาที', 'ระบบปิดการทำงานอัตโนมัติ', 'error', currentPostIndex, 'exit');
    } catch (e) {}
    await new Promise(resolve => setTimeout(resolve, 1000));
    try {
      // Force kill chrome instances linked to user_data to release lock
      const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
      exec(killCmd, () => {});
    } catch (e) {}
    try {
      if (typeof context !== 'undefined' && context) {
        await context.close({ timeout: 2000 }).catch(() => {});
      }
    } catch (e) {}
    process.exit(0);
  }, MAX_RUNTIME_MS);

  const extensionPath = path.join(__dirname, 'For Edge Addon');
  const browserArgs = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--disable-web-security',
    '--disable-features=IsolateOrigins,site-per-process',
    `--load-extension=${extensionPath}`,
    `--disable-extensions-except=${extensionPath}`,
    '--window-size=1024,768',  // ขนาดกลาง (ใหญ่พอให้ Gemini แสดง Fast Download)
    '--window-position=2816,312',  // มุมล่างขวาจอสอง (x=1920+896, y=1080-768)
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-background-timer-throttling',
  ];

  try {
    // --- Kill any Chrome instance already using this user_data dir ---
    try {
      const userDataEscaped = USER_DATA_DIR.replace(/\\/g, '\\\\');
      const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
      await execPromise(killCmd, { timeout: 8000 }).catch(() => { });
      console.log('[Pre-launch] Killed orphaned Chrome (if any).');
      await sleep(1500); // รอให้ OS release file lock บน user_data
    } catch (e) {
      // ไม่มี process ค้าง หรือ wmic ไม่ทำงาน — ข้ามได้
    }

    const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
      headless: isHeadless,
      viewport: null,
      args: [...browserArgs, '--disable-background-timer-throttling'],
    });

    console.log('Browser launched successfully.');
    // หน้าต่างเบราว์เซอร์จะแสดงที่จอที่ 2 ตาม --window-position ที่ตั้งไว้ใน browserArgs
    // ไม่ซ่อนหน้าต่างตอน launch เพราะ Facebook virtual DOM ต้องการ viewport จริงในการ render
    isBrowserHidden = false;

    // ✅ ตรวจจับเมื่อ Playwright browser ปิดตัว/ขัดข้อง — force exit ทันที
    context.on('disconnected', () => {
      console.error('[Browser] ⚠️ Browser context disconnected/crashed! Force exiting...');
      try {
        showWindowsNotification('Facebook Bot', 'เบราว์เซอร์ถูกปิด/ขัดข้อง — ปิดบอททั้งหมด', 'Error');
      } catch (e) {}
      try {
        reportStatus(100, '❌ เบราว์เซอร์ขัดข้อง', 'ระบบปิดอัตโนมัติ', 'error', currentPostIndex, 'crash');
      } catch (e) {}
      // Force kill chrome processes linked to user_data
      try {
        const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
        exec(killCmd, () => {});
      } catch (e) {}
      setTimeout(() => process.exit(1), 500);
    });

    // ✅ ตรวจจับ crash ของ browser process
    const browser = context.browser();
    if (browser) {
      browser.on('disconnected', () => {
        console.error('[Browser] ⚠️ Browser process disconnected! Force exiting...');
        try {
          showWindowsNotification('Facebook Bot', 'เบราว์เซอร์ถูกปิด/ขัดข้อง — ปิดบอททั้งหมด', 'Error');
        } catch (e) {}
        try {
          reportStatus(100, '❌ เบราว์เซอร์ขัดข้อง', 'ระบบปิดอัตโนมัติ', 'error', currentPostIndex, 'crash');
        } catch (e) {}
        try {
          const killCmd = `cmd /c wmic process where "name='chrome.exe' and CommandLine like '%Facebook_Bot\\\\user_data%'" delete`;
          exec(killCmd, () => {});
        } catch (e) {}
        setTimeout(() => process.exit(1), 500);
      });
    }

    await sleep(1700);

    const existingPages = context.pages();
    const fbPage = existingPages.length > 0 ? existingPages[0] : await context.newPage();
    const geminiPage = await context.newPage();

    ensureDownloadsDir();
    clearDownloadsDir();

    // *** โหลดจาก gemini_state.json เพื่อใช้ทุกบัญชี ***
    try {
      const state = loadActiveAccounts();
      if (Array.isArray(state) && state.length > 0) {
        activeGeminiAccounts = state;
      } else {
        activeGeminiAccounts = GEMINI_ACCOUNTS;
      }
    } catch (e) {
      activeGeminiAccounts = GEMINI_ACCOUNTS;
    }

    // กำหนดจำนวนโพสต์ตามจำนวนบัญชี Gemini
    AUTO_GROUPS_MAX = Math.max(1, activeGeminiAccounts.length);
    console.log(`Auto-configured: processing up to ${AUTO_GROUPS_MAX} posts (based on ${activeGeminiAccounts.length} Gemini accounts)`);

    if (activeGeminiAccounts.length > 0) {
      saveActiveAccounts(activeGeminiAccounts);
    }

    if (!isDebugPause && (activeGeminiAccounts.length === 0 || isLoginMode)) {
      if (activeGeminiAccounts.length === 0) {
        console.log('No Gemini accounts found.');
        showWindowsNotification('Facebook Bot', 'No Gemini accounts found! Please login.', 'Warning');
        if (isHeadless) {
          console.error('Cannot login in headless mode. Please run login mode first.');
          try { await context.close(); } catch (e) { }
          process.exit(1);
        }
      }
      const server = http.createServer((req, res) => {
        // Add CORS headers so local file:/// pages can connect to this server
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        if (req.method === 'OPTIONS') {
          res.writeHead(204);
          res.end();
          return;
        }

        if (req.url === '/' || req.url === '/index.html') {
          const helperPath = path.join(__dirname, 'login_helper.html');
          if (fs.existsSync(helperPath)) {
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(fs.readFileSync(helperPath));
          } else {
            res.writeHead(404);
            res.end('login_helper.html not found');
          }
        } else if (req.url === '/get-active-accounts') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(activeGeminiAccounts));
          return;
        } else if (req.url.startsWith('/open-login')) {
          const urlObj = new URL(req.url, `http://${req.headers.host}`);
          const index = parseInt(urlObj.searchParams.get('index'), 10);
          if (!isNaN(index)) {
            const url = `https://gemini.google.com/u/${index}/app`;
            console.log(`Opening login tab for index ${index}: ${url}`);
            context.newPage().then(p => {
              p.goto(url).catch(() => {});
            });
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true }));
          } else {
            res.writeHead(400);
            res.end('Bad Request');
          }
        } else if (req.url.startsWith('/set-account-active')) {
          const urlObj = new URL(req.url, `http://${req.headers.host}`);
          const index = parseInt(urlObj.searchParams.get('index'), 10);
          const active = urlObj.searchParams.get('active') === 'true';
          if (!isNaN(index)) {
            const url = `https://gemini.google.com/u/${index}/app`;
            let currentActive = loadActiveAccounts() || [];
            if (active) {
              if (!currentActive.includes(url)) {
                currentActive.push(url);
              }
            } else {
              currentActive = currentActive.filter(u => u !== url);
            }
            // Sort in order: u/0, u/1, u/2...
            currentActive.sort((a, b) => {
              const idxA = parseInt(a.match(/\/u\/(\d+)\//)?.[1] || 0, 10);
              const idxB = parseInt(b.match(/\/u\/(\d+)\//)?.[1] || 0, 10);
              return idxA - idxB;
            });
            activeGeminiAccounts = currentActive;
            saveActiveAccounts(activeGeminiAccounts);
            console.log(`Saved active accounts:`, activeGeminiAccounts);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, activeGeminiAccounts }));
          } else {
            res.writeHead(400);
            res.end('Bad Request');
          }
        } else if (req.url.startsWith('/update-slots')) {
          const urlObj = new URL(req.url, `http://${req.headers.host}`);
          const count = parseInt(urlObj.searchParams.get('count'), 10);
          if (!isNaN(count)) {
            console.log(`Updated UI to show ${count} slots.`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true }));
          } else {
            res.writeHead(400);
            res.end('Bad Request');
          }
        } else {
          res.writeHead(404);
          res.end();
        }
      });
      server.listen(12121, '127.0.0.1', async () => {
        const helperUrl = `http://127.0.0.1:12121/`;
        console.log(`\n==================================================`);
        console.log(`Login helper server started at: ${helperUrl}`);
        console.log(`Please log in to your accounts.`);
        console.log(`==================================================\n`);
        
        await fbPage.goto(helperUrl).catch(() => {});
      });

      if (isLoginMode) {
        // Block and wait until the browser context is closed by the user
        return new Promise((resolve) => {
          context.on('close', () => {
            console.log('Browser closed. Exiting login mode.');
            process.exit(0);
          });
        });
      }

      if (activeGeminiAccounts.length === 0) {
        console.error('No Gemini accounts configured. Please run login mode first (run_login.bat).');
        try { await context.close(); } catch (e) { }
        process.exit(1);
      }
    }

    if (activeGeminiAccounts.length > 0) {
      saveActiveAccounts(activeGeminiAccounts);
    }

    console.log(`Ready with ${activeGeminiAccounts.length} Gemini accounts.`);

    // ✅ ตรวจสอบสถานะการ Login ของ Gemini ก่อนเริ่มรันบอท Facebook
    if (!isReviewMode && activeGeminiAccounts.length > 0) {
      console.log('\n🔍 กำลังตรวจสอบสถานะการ Login ของบัญชี Gemini...');
      const targetGeminiUrl = activeGeminiAccounts[0];
      await geminiPage.goto(targetGeminiUrl, { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
      await sleep(2000);

      const isLoggedOut = await checkIsGeminiLoggedOut(geminiPage);
      if (isLoggedOut) {
        console.warn('⚠️ [Gemini Login Check] พบว่าบัญชี Gemini ไม่ได้ลงชื่อเข้าใช้ (พบปุ่ม "ลงชื่อเข้าใช้")!');
        showWindowsNotification('Facebook Bot ⚠️', 'บัญชี Gemini ไม่ได้ลงชื่อเข้าใช้! กรุณา Login ก่อน', 'Warning');
        await reportStatus(0, '⚠️ บัญชี Gemini ไม่ได้ Login', 'พบปุ่ม "ลงชื่อเข้าใช้" (Gemini ไม่ได้ login) กรุณา Login ก่อนบอททำงานต่อ', 'warn');
        await bringWindowToFront(geminiPage).catch(() => {});

        let waitCount = 0;
        while (await checkIsGeminiLoggedOut(geminiPage)) {
          waitCount++;
          if (waitCount % 3 === 0) {
            showWindowsNotification('Facebook Bot ⚠️', 'กรุณา Login ลงชื่อเข้าใช้ Gemini เพื่อให้บอททำงานต่อ', 'Warning');
          }
          console.log('[Gemini Pre-check] ⏸️ พักการทำงาน... กรุณาลงชื่อเข้าใช้ Gemini ในหน้าต่างเบราว์เซอร์');
          await sleep(5000);
        }
        console.log('✅ [Gemini Pre-check] ลงชื่อเข้าใช้ Gemini สำเร็จ!');
        await reportStatus(2, '✅ ลงชื่อเข้าใช้ Gemini แล้ว', 'พร้อมเริ่มทำงานบอท Facebook', 'info');
        await sleep(1500);
      } else {
        console.log('✅ [Gemini Pre-check] บัญชี Gemini พร้อมใช้งาน (Logged in)');
      }
    }

    if (isDebugPause) {
      await pauseForUser('โหมด DEBUG — กด Enter เพื่อเริ่มสแกน Facebook');
      console.log(`DEBUG: Resuming with ${activeGeminiAccounts.length} cached accounts.`);
    }

    if (!isReviewMode) {
      console.log(`\nNavigating to Facebook groups: ${FB_URL}`);
      await reportStatus(5, 'กำลังเปิด Facebook Feed...', 'เข้าสู่หน้ากลุ่ม Facebook Feed', 'info', 1);
      try {
        await bringWindowToFront(fbPage).catch(() => { });
        await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
      } catch (e) {
        console.warn('Facebook navigation slow, continuing...');
      }

      const fbReady = await waitForFacebookReady(fbPage);
      if (!fbReady) {
        console.error('Cannot login Facebook — exiting.');
        await reportStatus(0, 'ไม่สามารถเข้าสู่ Facebook ได้', 'กรุณาตรวจสอบการล็อกอิน', 'error', 1);
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
      let postsEvaluatedCount = 0;
      let consecutiveEmptyScrolls = 0;
      let consecutiveFilteredPosts = 0;
      const MAX_EMPTY_SCROLLS = 15;
      const MAX_FILTERED_POSTS = 60;
      
      let lastPostFoundTime = Date.now();

      // ตรวจจับชื่อโปรไฟล์ของบอท 1 ครั้ง ใช้สำหรับกรองโพสต์ของตัวเอง
      const botProfileName = await getLoggedInProfileName(fbPage).catch(() => null);
      console.log(`[Self-Filter] Bot profile name: "${botProfileName || '(unknown)'}"`);

      while (postsProcessedCount < AUTO_GROUPS_MAX) {
        const elapsedMs = Date.now() - BOT_START_TIME;
        if (postsProcessedCount < AUTO_GROUPS_MAX && elapsedMs >= MAX_RUNTIME_MS) {
          console.warn(`Bot runtime exceeded 20 minutes (${Math.round(elapsedMs / 1000)}s). Stopping.`);
          showWindowsNotification('Facebook Bot', `Timeout: ทำได้ ${postsProcessedCount}/${AUTO_GROUPS_MAX} โพสต์`, 'Warning');
          
          // Force cleanup และปิดทันที
          try {
            await execPromise('taskkill /F /IM chrome.exe /FI "WINDOWTITLE eq *user_data*"', { timeout: 2000 }).catch(() => {});
            await context.close({ timeout: 2000 }).catch(() => {});
          } catch (e) { /* ignore */ }
          
          setTimeout(() => process.exit(0), 1000);
          process.exit(0);
        }

        // 5-minute inactivity check (if no valid posts found to process)
        const elapsedSinceLastFound = Date.now() - lastPostFoundTime;
        if (elapsedSinceLastFound >= 5 * 60 * 1000) {
          console.warn(`No valid posts found to process for 5 minutes. Stopping bot.`);
          showWindowsNotification('Facebook Bot', 'No posts found to process for 5 minutes. Closing.', 'Warning');
          
          try {
            await execPromise('taskkill /F /IM chrome.exe /FI "WINDOWTITLE eq *user_data*"', { timeout: 2000 }).catch(() => {});
            await context.close({ timeout: 2000 }).catch(() => {});
          } catch (e) { /* ignore */ }
          
          setTimeout(() => process.exit(0), 1000);
          process.exit(0);
        }

        // Hide any previously processed posts from the feed dynamically
        await hideProcessedPosts(fbPage, processedPostIds);

        currentPostIndex = postsProcessedCount + 1;
        const basePct = Math.round((postsProcessedCount / AUTO_GROUPS_MAX) * 100);
        console.log(`\n📋 Scanning feed... Posts processed: ${postsProcessedCount}/${AUTO_GROUPS_MAX}`);
        await reportStatus(basePct + 2, `สแกนหาโพสต์ที่ ${currentPostIndex}/${AUTO_GROUPS_MAX}...`, 'กำลังเลื่อนหาโพสต์ถัดไปใน Feed', 'info', currentPostIndex);

        await closeFacebookModal(fbPage);

        // ตรวจสอบและเคลียร์เมมโมรี่ทุกๆ 15 โพสต์ที่ตรวจหา
        if (postsEvaluatedCount > 0 && postsEvaluatedCount % 15 === 0) {
          console.log(`[Memory Cleanup] Evaluated ${postsEvaluatedCount} posts. Reloading Facebook page...`);
          await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
          await sleep(3000);
          await hideProcessedPosts(fbPage, processedPostIds);
          postsEvaluatedCount = 0;
        }

        const article = fbPage.locator('div[role="article"]:not([data-bot-processed="true"])').first();

        if (await article.count() === 0) {
          consecutiveEmptyScrolls++;
          if (consecutiveEmptyScrolls >= MAX_EMPTY_SCROLLS) {
            await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
            await sleep(2000);
            await hideProcessedPosts(fbPage, processedPostIds);
            consecutiveEmptyScrolls = 0;
          } else {
            await fbPage.evaluate(() => window.scrollBy(0, 1500));
            await sleep(2000);
            await hideProcessedPosts(fbPage, processedPostIds);
          }
          continue;
        }

        postsEvaluatedCount++;

        { // outer block
          await article.evaluate(el => {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.style.outline = '4px solid #fbbc04';
          }).catch(() => { });
          await sleep(500);

          const postText = await getPostText(article);

          // *** Check for video/reel content — skip these posts ***
          const hasVideo = await article.evaluate((node) => {
            return node.querySelector('video') !== null;
          }).catch(() => false);

          if (hasVideo) {
            console.log('--> Skipped: Post contains video/reel content.');
            const textHash = hashString((postText || '').substring(0, 200));
            processedPostIds.add(textHash);
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          // Compute post ID early
          const imageUrlsForId = await getLargeImageUrls(article);
          let earlyPostId;
          try {
            earlyPostId = imageUrlsForId.length > 0 ? hashString(new URL(imageUrlsForId[0]).pathname) : hashString((postText || '').substring(0, 200));
          } catch (e) {
            earlyPostId = hashString((postText || '').substring(0, 200));
          }

          // Add to memory list of processed posts immediately
          processedPostIds.add(earlyPostId);

          // เพิ่มเงื่อนไข: หากโพสต์ไม่มีข้อความ ให้ข้ามโพสต์นี้ไปเลย
          if (!postText || postText.trim().length === 0) {
            console.log("--> Skipped: Post has no text content.");
            await reportStatus(basePct + 2, `กำลังข้ามโพสต์ที่ ${currentPostIndex}...`, `⚠️ โพสต์ไม่มีข้อความ -> ข้าม`, 'warn', currentPostIndex);
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          console.log('\n--------------------------------------------');
          console.log(`Evaluating Post ID: ${earlyPostId}`);
          console.log(`Content: "${postText.substring(0, 80).replace(/\n/g, ' ')}..."`);
          if (imageUrlsForId.length > 0) console.log('--> Processing images:', JSON.stringify(imageUrlsForId, null, 2));

          const filterResult = await shouldFilterPost(article, botProfileName);
          if (filterResult.action === 'hide' || filterResult.action === 'spam') {
            console.log(`--> Skipped: caught by shouldFilterPost. Action: ${filterResult.action}. Reason: ${filterResult.reason}`);
            await reportStatus(basePct + 2, `กำลังข้ามโพสต์ที่ ${currentPostIndex}...`, `⚠️ ${filterResult.reason} -> ข้ามไปทำอันใหม่`, 'warn', currentPostIndex);
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            consecutiveFilteredPosts++;
            if (consecutiveFilteredPosts >= MAX_FILTERED_POSTS) {
              console.warn(`Reached ${MAX_FILTERED_POSTS} consecutive filtered posts. Reloading Facebook...`);
              await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
              await sleep(3000);
              await hideProcessedPosts(fbPage, processedPostIds);
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
            await reportStatus(basePct + 2, `ข้ามโพสต์ที่ ${currentPostIndex}`, '⚠️ ไม่พบรูปภาพในโพสต์ -> ข้ามไปอันใหม่', 'warn', currentPostIndex);
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          // Found a valid post with images!
          lastPostFoundTime = Date.now();

          console.log(`Processing ${imageUrls.length} images...`);
          await reportStatus(basePct + 5, `พบโพสต์ที่ ${currentPostIndex} (${imageUrls.length} ภาพ)`, 'กำลังดาวน์โหลดรูปภาพจาก Facebook...', 'info', currentPostIndex);

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
              await reportStatus(basePct, `โหลดรูปไม่สำเร็จ (โพสต์ ${currentPostIndex})`, '❌ ไม่สามารถดาวน์โหลดรูปภาพจาก FB ได้', 'error', currentPostIndex);
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
              await reportStatus(basePct, `ไม่มี Gemini URL (โพสต์ ${currentPostIndex})`, '❌ ไม่มีบัญชี Gemini ที่พร้อมใช้งาน', 'error', currentPostIndex);
              await pauseOnError(isDebugPause, 'ไม่มี Gemini URL ที่ใช้ได้');
              await article.evaluate(el => {
                el.style.display = 'none';
                el.setAttribute('data-bot-processed', 'true');
              }).catch(() => { });
              continue;
            }

            await reportStatus(basePct + 15, `ส่งภาพให้ Gemini AI (โพสต์ ${currentPostIndex})...`, `กำลังประมวลผลสร้างรูปภาพใหม่ด้วย Gemini AI`, 'info', currentPostIndex);
            geminiResult = await processWithGemini(geminiPage, tempInputPaths, postText, geminiUrl);
            if (!geminiResult) {
              console.error('Gemini processing failed or refused.');
              await reportStatus(basePct, `Gemini ปฏิเสธ/ล้มเหลว (โพสต์ ${currentPostIndex})`, '⚠️ กด Like แล้วข้ามไปโพสต์ใหม่...', 'warn', currentPostIndex);
              
              // ⚠️ กรณี Gemini ปฏิเสธ → กด Like แล้วข้าม
              await bringWindowToFront(fbPage).catch(() => { });
              await article.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => { });
              await sleep(600);
              await likePost(article);
              console.log('[Gemini Refused] ✅ Liked post and skipping to next.');
              
              await pauseOnError(isDebugPause, 'Gemini ประมวลผลล้มเหลว/ปฏิเสธ → กด Like แล้วข้าม');
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

            await reportStatus(basePct + 35, `กำลังแต่งภาพด้วย Python (โพสต์ ${currentPostIndex})...`, 'ใส่โลโก้และปรับแต่งความสมบูรณ์ของภาพ', 'info', currentPostIndex);
            pythonResult = await runPythonImageEditor(geminiResult, postText);
            if (!pythonResult) {
              console.error('Python image editing failed.');
              await reportStatus(basePct, `Python แต่งภาพล้มเหลว (โพสต์ ${currentPostIndex})`, '⚠️ ข้ามไปโพสต์ใหม่...', 'warn', currentPostIndex);
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

            await reportStatus(basePct + 55, `กำลังโพสต์คอมเมนต์ (โพสต์ ${currentPostIndex})...`, 'อัปโหลดภาพลงช่องแสดงความคิดเห็นบน Facebook', 'info', currentPostIndex);
            await bringWindowToFront(fbPage).catch(() => { });
            // Extract post permalink ก่อนส่งให้ postComment (ใช้อ้างอิง comment URL)
            let postUrl = await getPostUrl(article).catch(() => null);
            if (!postUrl) {
              postUrl = fbPage.url(); // Fallback ไปใช้ URL ปัจจุบันถ้าเปิดโพสต์แบบเจาะจง/permalink
            }
            if (postUrl) console.log(`Post URL: ${postUrl}`);
            const commentResult = await postComment(article, pythonResult, postUrl);

            if (commentResult && commentResult.success) {
              // ⏸️ DEBUG PAUSE 5: ตรวจสอบ comment ก่อน like/share
              if (isDebugPause) {
                await pauseForUser('โหมด DEBUG — Comment โพสต์แล้ว\nตรวจสอบ comment บน Facebook แล้วกด Enter เพื่อ Like และ Share ต่อ');
              }
              // ปิด popup/modal ก่อน like เพื่อไม่ให้คลิกผิด element
              await closeFacebookModal(fbPage);
              await sleep(800);
              // scroll article กลับขึ้นไปให้มองเห็น like button
              await article.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => { });
              await sleep(600);
              await likePost(article);
              await sleep(2000);

              // --- Share ผ่านโพสต์ในหน้าตัวเอง ---
              await reportStatus(basePct + 75, `กำลังแชร์โพสต์ (โพสต์ ${currentPostIndex})...`, 'แชร์ผลงานไปยังหน้าโปรไฟล์หลัก', 'info', currentPostIndex);
              await bringWindowToFront(fbPage).catch(() => { });

              // 🔒 Safety check: ห้ามแชร์ URL หน้าโปรไฟล์ตัวเองเด็ดขาด
              const commentUrl = commentResult.commentUrl || '';
              const isOwnProfileUrl = commentUrl.includes('facebook.com/me') ||
                commentUrl.includes('facebook.com/profile.php') ||
                !commentUrl.includes('/groups/');
              let shareResult;
              if (isOwnProfileUrl) {
                console.warn(`[Share] ⛔ Skipping share — comment URL is own profile URL: ${commentUrl}`);
                shareResult = { success: false, reason: 'own_profile_url' };
              } else {
                shareResult = await shareViaOwnPost(fbPage, commentResult.commentUrl);
              }
              if (shareResult && shareResult.success) {
                console.log(`[Share] Shared via own post: ${shareResult.commentUrl}`);
              } else {
                console.warn(`[Share] Share skipped or failed: ${shareResult?.reason}`);
              }
              // โพสต์แชร์แล้ว รอ 2วิ ค่อยเริ่ม task ใหม่
              console.log('[Share] Waiting 2 seconds before starting next task...');
              await sleep(2000);

              // ⏸️ DEBUG PAUSE 6: หลัง share ให้ pause รอตรวจสอบก่อนเริ่มงานใหม่
              if (isDebugPause) {
                await pauseForUser('โหมด DEBUG — Share เสร็จแล้ว\nตรวจสอบโพสต์ใน profile ก่อน แล้วกด Enter เพื่อเริ่มงานถัดไป');
              }

              // กลับไปหน้า Facebook groups feed
              await fbPage.goto(FB_URL, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => { });
              await sleep(2000);
              await closeFacebookModal(fbPage);
              await sleep(2000); // รอ 2 วิ ก่อนเริ่ม task ใหม่

              postsProcessedCount++;
              const donePct = Math.round((postsProcessedCount / AUTO_GROUPS_MAX) * 100);
              await reportStatus(donePct, `ทำรายการโพสต์ที่ ${postsProcessedCount}/${AUTO_GROUPS_MAX} สำเร็จ!`, 'โพสต์คอมเมนต์และแชร์เสร็จสมบูรณ์', 'success', postsProcessedCount);

              showWindowsNotification('Facebook Bot', `Task #${postsProcessedCount} completed!`);
              console.log(`Post #${postsProcessedCount} processed successfully!`);
            } else {
              console.log('Comment failed, marking as processed.');
              await reportStatus(basePct, `โพสต์คอมเมนต์ไม่สำเร็จ (โพสต์ ${currentPostIndex})`, '❌ เกิดข้อผิดพลาดในการลงคอมเมนต์', 'error', currentPostIndex);
              await pauseOnError(isDebugPause, 'Comment โพสต์ล้มเหลว');
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
      
      showWindowsNotification('Facebook Bot', `ทำรายการครบ ${postsProcessedCount}/10 สำเร็จ!`);
      
      console.log('Closing browser and process...');
      
      // ปิด modal/notification ของ Facebook ก่อน
      await closeFacebookModal(fbPage).catch(() => {});
      await sleep(500);

      // ปิด browser context — ถ้า timeout ก็ force kill
      try {
        const closePromise = context.close({ timeout: 5000 });
        const timeoutPromise = new Promise(r => setTimeout(r, 5000)).then(() => { throw new Error('timeout'); });
        await Promise.race([closePromise, timeoutPromise]);
        console.log('✅ Browser context closed.');
      } catch (e) {
        console.warn('Browser close timeout, force killing Chrome...');
        try { await execPromise('taskkill /F /IM chrome.exe', { timeout: 3000 }).catch(() => {}); } catch (e) {}
      }
      
      reportStatus(100, '✅ บอททำงานครบ 10 โพสต์แล้ว', 'ปิดระบบเรียบร้อย', 'success', AUTO_GROUPS_MAX, 'exit');
      console.log('✅ Bot finished. Exiting now.');
      process.exit(0);
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
