// auto_text_retouch_from_Photoshop.jsx
// กด F12 ใน Photoshop เพื่อส่งผลลัพธ์กลับให้ลูกค้า
// ──────────────────────────────────────────────────

var ENGINE_URL = "http://localhost:37791/text-retouch-submit";

// 1. Save as PNG ไปยัง result path
var doc = app.activeDocument;
if (!doc) {
    alert("❌ ไม่มี document ที่เปิดอยู่!");
} else {
    // Flatten ก่อน save
    doc.flatten();

    // หา result path จาก active state
    var stateFile = new File("D:/Github/eworker/cache/text_retouch/active_patch.json");
    var resultPath = "";
    var patchNum = "";
    var sessionId = "";
    var patchId = "";

    if (stateFile.exists) {
        stateFile.open("r");
        var stateJson = stateFile.read();
        stateFile.close();

        // Parse JSON manually (no JSON.parse in old ExtendScript)
        var resultMatch = stateJson.match(/"result_path":\s*"([^"]+)"/);
        var numMatch = stateJson.match(/"patch_num":\s*(\d+)/);
        var sidMatch = stateJson.match(/"session_id":\s*"([^"]+)"/);
        var pidMatch = stateJson.match(/"patch_id":\s*"([^"]+)"/);

        if (resultMatch) resultPath = resultMatch[1].replace(/\\\\/g, "/").replace(/\\/g, "/");
        if (numMatch) patchNum = numMatch[1];
        if (sidMatch) sessionId = sidMatch[1];
        if (pidMatch) patchId = pidMatch[1];
    }

    if (!resultPath) {
        // Fallback: save to Desktop
        resultPath = Folder.desktop.absoluteURI + "/text_retouch_result.png";
    }

    // Save PNG
    var saveFile = new File(resultPath);
    var opts = new PNGSaveOptions();
    opts.compression = 6;
    doc.saveAs(saveFile, opts, true, Extension.LOWERCASE);

    // 2. ส่งงานขึ้น Firebase ผ่าน Python CLI
    try {
        var submitCode = app.system('cmd /c python "D:\\Github\\eworker\\text_retouch_engine.py" --submit');
        if (submitCode === 0) {
            alert("✅ ส่งงานจุดที่ " + (patchNum || "1") + " ให้ลูกค้าแล้ว!\n\nส่งผลลัพธ์แบบคมชัด (ไม่มีลายน้ำ) เรียบร้อย");
        } else {
            var submitBat = new File("D:/Github/eworker/auto_text_touch_submit.bat");
            if (submitBat.exists) {
                submitBat.execute();
                alert("🚀 กำลังส่งงานจุดที่ " + (patchNum || "1") + " ให้ลูกค้า...");
            } else {
                alert("⚠️ ส่งงานไม่สำเร็จ (Code: " + submitCode + ")");
            }
        }
    } catch (e) {
        var submitBat2 = new File("D:/Github/eworker/auto_text_touch_submit.bat");
        if (submitBat2.exists) {
            submitBat2.execute();
            alert("🚀 กำลังส่งงานจุดที่ " + (patchNum || "1") + " ให้ลูกค้า...");
        } else {
            alert("❌ ส่งงานล้มเหลว: " + e.toString());
        }
    }
}
