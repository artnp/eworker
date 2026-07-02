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
      const el = node.querySelector('div[data-ad-comet-preview="message"], div[data-ad-preview="message"], div[dir="auto"][style*="text-align: start"]');
      if (el) {
        const text = (el.innerText || el.textContent || "").trim();
        if (text) return text;
      }
      const candidates = Array.from(node.querySelectorAll('div[dir="auto"], span[dir="auto"]')).filter(el => {
        if (el.closest('a') || el.closest('button') || el.closest('ul') || el.closest('span[role="button"]')) return false;
        if (el.closest('[role="textbox"]') || el.closest('textarea')) return false;
        return (el.innerText || el.textContent || "").trim().length > 15;
      });
      if (candidates.length > 0) {
        const text = candidates[0].innerText || candidates[0].textContent || "";
        return text.trim();
      }
      return '';
    });
  } catch (e) {
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
              const ext = mimeType === 'image/png' ? 'png' : 'jpg';
              const file = new File([blob], `image_${Date.now()}.${ext}`, { type: mimeType });
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

    const promptText = `${postText.trim()}\n(จงทำภาพ)`;
    const textInput = page.locator(inputSelector).first();
    await textInput.click();
    await sleep(300);
    await textInput.fill(promptText);
    console.log('Typed prompt text.');
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
    try {
      await page.locator('.fast-dl-button').first().waitFor({ state: 'visible', timeout: 90000 });
      console.log('[FastDL] Image ready, capturing via canvas...');
    } catch (e) {
      console.warn('[FastDL] Fast Download button not found, trying canvas anyway:', e.message);
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
    const composerSelectors = [
      'div[role="textbox"][contenteditable="true"]',
      'div[contenteditable="true"]',
      'textarea'
    ];
    let composer = null;
    for (const sel of composerSelectors) {
      const loc = article.locator(sel).first();
      if (await loc.count() > 0 && await loc.isVisible().catch(() => false)) {
        composer = loc;
        break;
      }
    }
    if (!composer) {
      const commentBtnSelectors = [
        'div[role="button"][aria-label*="Comment"]',
        'div[role="button"][aria-label*="comment"]',
        'div[role="button"][aria-label*="แสดงความคิดเห็น"]',
        'span[role="button"]:has-text("Comment")',
        'span[role="button"]:has-text("ความคิดเห็น")'
      ];
      let clicked = false;
      for (const sel of commentBtnSelectors) {
        try {
          const btn = article.locator(sel).first();
          if (await btn.count() > 0 && await btn.isVisible()) {
            await btn.click({ force: true });
            clicked = true;
            break;
          }
        } catch (e) { }
      }
      if (clicked) {
        await sleep(500);
        for (const sel of composerSelectors) {
          const loc = article.locator(sel).first();
          if (await loc.count() > 0 && await loc.isVisible().catch(() => false)) {
            composer = loc;
            break;
          }
        }
      }
    }
    if (!composer) {
      const startWait = Date.now();
      let composerEl = null;
      while (Date.now() - startWait < 15000) {
        for (const sel of composerSelectors) {
          const loc = article.locator(sel).first();
          if (await loc.count() > 0 && await loc.isVisible().catch(() => false)) {
            composerEl = loc;
            break;
          }
        }
        if (composerEl) break;
        for (const sel of composerSelectors) {
          const loc = page.locator(sel);
          const count = await loc.count();
          for (let i = 0; i < count; i++) {
            const c = loc.nth(i);
            if (await c.isVisible().catch(() => false)) {
              const aria = (await c.getAttribute('aria-label').catch(() => '')) || '';
              const text = (await c.innerText().catch(() => '')) || '';
              if (aria.toLowerCase().includes('comment') || aria.toLowerCase().includes('ความคิดเห็น') || text.includes('ตอบ') || text.includes('ความคิดเห็น')) {
                composerEl = c;
                break;
              }
            }
          }
          if (composerEl) break;
        }
        if (composerEl) break;
        await sleep(200);
      }
      if (!composerEl) {
        console.log('Comment composer not found.');
        return { success: false };
      }
      composer = composerEl;
    }
    let fileInputEl = null;
    const form = article.locator('form').first();
    if (await form.count() > 0) {
      const input = form.locator('input[type="file"]').first();
      if (await input.count() > 0) fileInputEl = input;
    }
    if (!fileInputEl) {
      const input = article.locator('input[type="file"]').first();
      if (await input.count() > 0) fileInputEl = input;
    }
    if (!fileInputEl) {
      const inputs = page.locator('input[type="file"]');
      const count = await inputs.count();
      for (let i = 0; i < count; i++) {
        const input = inputs.nth(i);
        if (await input.isVisible().catch(() => false)) {
          fileInputEl = input;
          break;
        }
      }
    }
    if (!fileInputEl) {
      console.log('File input for image upload not found.');
      return { success: false };
    }
    console.log('Uploading image to Facebook comment...');
    await fileInputEl.setInputFiles(imagePath);
    await sleep(2000);
    const promoMessages = [
      '\n\n🔮 ภาพนี้ถูกปรับปรุงโดย AI ที่ https://eworker.net',
      '\n\n✨ ได้ AI ช่วยทำภาพให้ชัดขึ้น',
      '\n\n✅ ภาพชัดขึ้นโดย AI จาก https://eworker.net'
    ];
    const promoText = promoMessages[Math.floor(Math.random() * promoMessages.length)];
    await composer.click();
    await sleep(300);
    await composer.fill(promoText);
    await sleep(500);
    await composer.press('Enter');
    await sleep(1000);
    const postBtnSelectors = [
      'div[role="button"][aria-label*="Post"]',
      'div[role="button"][aria-label*="โพสต์"]',
      'div[role="button"][aria-label*="Send"]',
      'div[role="button"][aria-label*="ส่ง"]'
    ];
    for (const sel of postBtnSelectors) {
      try {
        const postBtn = page.locator(sel).first();
        if (await postBtn.count() > 0 && await postBtn.isVisible()) {
          await postBtn.click({ force: true });
          break;
        }
      } catch (e) { }
    }
    await sleep(2000);
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
    for (const sel of likeSelectors) {
      try {
        const btn = article.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible()) {
          const ariaPressed = await btn.getAttribute('aria-pressed').catch(() => 'false');
          const ariaLabel = (await btn.getAttribute('aria-label').catch(() => '') || '').toLowerCase();
          const isPressed = ariaPressed === 'true' || ariaLabel.includes('unlike') || ariaLabel.includes('เลิก') || ariaLabel.includes('ลบ');
          if (isPressed) {
            console.log('Post already liked.');
            return true;
          }
          await btn.click({ force: true });
          await sleep(1000);
          console.log('Liked post.');
          return true;
        }
      } catch (e) { }
    }
    const globalBtns = page.locator('div[role="button"][aria-label*="Like"], div[role="button"][aria-label*="ถูกใจ"]');
    const count = await globalBtns.count();
    for (let i = 0; i < count; i++) {
      try {
        const btn = globalBtns.nth(i);
        if (await btn.isVisible().catch(() => false)) {
          const ariaPressed = await btn.getAttribute('aria-pressed').catch(() => 'false');
          if (ariaPressed !== 'true') {
            await btn.click({ force: true });
            await sleep(1000);
            console.log('Liked post (global).');
            return true;
          }
        }
      } catch (e) { }
    }
    return false;
  } catch (e) {
    console.error('Error liking post:', e.message || e);
    return false;
  }
}

async function closeFacebookModal(page) {
  try {
    const closeSelectors = [
      'div[role="button"][aria-label*="Close"]',
      'div[role="button"][aria-label*="close"]',
      'div[role="button"][aria-label*="ปิด"]',
      'button:has-text("Close")',
      'button:has-text("ปิด")'
    ];
    for (const sel of closeSelectors) {
      try {
        const btn = page.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible({ timeout: 500 }).catch(() => false)) {
          await btn.click({ force: true });
          await sleep(500);
          return true;
        }
      } catch (e) { }
    }
  } catch (e) { }
  return false;
}

async function sharePost(article, promoText, postUrl = null) {
  let sharePage = null;
  try {
    const page = article.page();
    const shareBtnSelectors = [
      'div[role="button"][aria-label*="Share"]',
      'div[role="button"][aria-label*="share"]',
      'div[role="button"][aria-label*="แชร์"]',
      'span[role="button"]:has-text("Share")',
      'span[role="button"]:has-text("แชร์")'
    ];
    let shareClicked = false;
    for (const sel of shareBtnSelectors) {
      try {
        const btn = article.locator(sel).first();
        if (await btn.count() > 0 && await btn.isVisible()) {
          await btn.click({ force: true });
          shareClicked = true;
          break;
        }
      } catch (e) { }
    }
    if (!shareClicked) return { success: false, reason: 'share_button_not_found' };
    await sleep(1500);
    const [newPage] = await Promise.all([
      page.context().waitForEvent('page', { timeout: 10000 }).catch(() => null),
      Promise.race([
        page.locator('div[role="button"]:has-text("Share to Feed"), div[role="button"]:has-text("แชร์ไปที่ฟีด"), div[role="button"]:has-text("Share Now")').first().click({ force: true }).catch(() => { }),
        page.locator('div[role="button"]:has-text("Write Post"), div[role="button"]:has-text("เขียนโพสต์")').first().click({ force: true }).catch(() => { })
      ])
    ]);
    if (newPage) {
      sharePage = newPage;
      await sharePage.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => { });
      await sleep(2000);
      const shareComposer = sharePage.locator('div[role="textbox"][contenteditable="true"], div[contenteditable="true"], textarea').first();
      if (await shareComposer.count() > 0 && await shareComposer.isVisible().catch(() => false)) {
        await shareComposer.click();
        await sleep(300);
        const shareText = postUrl ? `${promoText}\n\n🔗 ${postUrl}` : promoText;
        await shareComposer.fill(shareText);
        await sleep(500);
      }
      const postBtn = sharePage.locator('div[role="button"]:has-text("Post"), div[role="button"]:has-text("โพสต์"), div[role="button"]:has-text("Share"), div[role="button"]:has-text("แชร์")').first();
      if (await postBtn.count() > 0 && await postBtn.isVisible().catch(() => false)) {
        await postBtn.click({ force: true });
        await sleep(3000);
      } else {
        await shareComposer.press('Enter');
        await sleep(3000);
      }
      await sharePage.close().catch(() => { });
    }
    return { success: true, reason: 'shared' };
  } catch (e) {
    console.error('Error sharing post:', e.message || e);
    if (sharePage) await sharePage.close().catch(() => { });
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

    console.log('\nChecking Gemini accounts...');
    const cached = loadActiveAccounts();
    if (isDebugPause) {
      activeGeminiAccounts = cached || [];
      console.log(`DEBUG: Loaded ${activeGeminiAccounts.length} cached accounts (skip validation).`);
    } else if (cached && cached.length > 0 && !isReviewMode && !isLoginMode) {
      console.log(`Found ${cached.length} cached accounts, validating...`);
      for (const url of cached) {
        const index = parseInt(url.match(/\/u\/(\d+)/)?.[1] || '0', 10);
        const isLogged = await checkGeminiAccountLogged(context, index);
        if (isLogged) activeGeminiAccounts.push(url);
      }
      if (activeGeminiAccounts.length === 0) {
        console.log('All cached accounts expired, rescanning...');
        activeGeminiAccounts = await detectActiveGeminiAccounts(context);
      } else {
        console.log(`Validated ${activeGeminiAccounts.length} accounts.`);
      }
    } else if (!isLoginMode) {
      activeGeminiAccounts = await detectActiveGeminiAccounts(context);
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
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          const geminiUrl = getNextGeminiUrl();
          if (!geminiUrl) {
            console.error('No Gemini URL available.');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          geminiResult = await processWithGemini(geminiPage, tempInputPaths, postText, geminiUrl);
          if (!geminiResult) {
            console.error('Gemini processing failed.');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
          }

          pythonResult = await runPythonImageEditor(geminiResult);
          if (!pythonResult) {
            console.error('Python image editing failed.');
            await article.evaluate(el => {
              el.style.display = 'none';
              el.setAttribute('data-bot-processed', 'true');
            }).catch(() => { });
            continue;
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
            await sleep(500);
            await likePost(article);
            await sleep(3500);
            await sharePost(article, commentResult.promoText || '', postUrl);
            await closeFacebookModal(fbPage);
            postsProcessedCount++;
            processedPosts.add(postId);
            saveProcessedPosts();
            showWindowsNotification('Facebook Bot', `Task #${postsProcessedCount} completed!`);
            console.log(`Post #${postsProcessedCount} processed successfully!`);
          } else {
            console.log('Comment failed, marking as processed.');
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
          // ลบภาพ Desktop output
          try {
            const isBotMode = process.argv.includes('--bot');
            const outputName = isBotMode ? 'complete_bot.png' : 'complete.png';
            const desktopOutputPath = path.join(process.env.USERPROFILE, 'Desktop', outputName);
            if (fs.existsSync(desktopOutputPath)) fs.unlinkSync(desktopOutputPath);
          } catch (e) { }
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
