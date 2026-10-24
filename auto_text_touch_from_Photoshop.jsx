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

        if (resultMatch) resultPath = resultMatch[1].replace(/\\\//g, "/");
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

    // 2. ส่งสัญญาณไปยัง local server
    try {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", ENGINE_URL, false); // synchronous
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify({
            resultPath: resultPath,
            sessionId: sessionId,
            patchId: patchId,
            patchNum: parseInt(patchNum) || 1
        }));

        if (xhr.status === 200) {
            var resp = eval("(" + xhr.responseText + ")");
            if (resp.ok) {
                alert("✅ ส่งงานจุดที่ " + (patchNum || "?") + " ให้ลูกค้าแล้ว!\n\nส่งผลลัพธ์แบบคมชัด (ไม่มีลายน้ำ) ตรงเข้าเครื่องลูกค้าเรียบร้อย");
            } else {
                alert("❌ ส่งงานไม่สำเร็จ: " + (resp.error || "unknown error"));
            }
        } else {
            alert("⚠️ Server ไม่ตอบสนอง (status " + xhr.status + ")\n\nกรุณาตรวจสอบว่า auto_donate_watcher.py รันอยู่");
        }
    } catch (e) {
        // Fallback: เปิดหน้าต่าง submit แทน
        alert("⚠️ ไม่สามารถเชื่อมต่อ local server ได้\n\nบันทึกไฟล์แล้วที่:\n" + resultPath + "\n\nกรุณารัน auto_text_retouch_submit.bat เพื่อส่งงาน");
    }
}
