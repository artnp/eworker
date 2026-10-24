#target photoshop
app.displayDialogs = DialogModes.NO;

// Text-Retouch: Auto-open patch #1
var patchFile = new File("D:/Github/eworker/cache/text_retouch/p_mvm4s4pww2p2.png");
var doc = app.open(patchFile);

// สร้าง Text Layer แยกสำหรับข้อความที่จะแก้ (ขนาด Canvas คงเดิม 100% ไม่สร้างแถบสี)
try {
    var textLayer = doc.artLayers.add();
    textLayer.kind = LayerKind.TEXT;
    textLayer.name = "📝 #1: ทดสอบเปิด Photoshop เร็ว";
    var txt = textLayer.textItem;
    txt.contents = "ทดสอบเปิด Photoshop เร็ว";
    txt.size = Math.min(Math.max(doc.height * 0.4, 14), 60);
    txt.position = [10, Math.min(doc.height * 0.75, doc.height - 5)];
    txt.color.rgb.hexValue = "000000";

    
} catch(e) {}

// Active layer = Background (สำหรับรีทัชภาพ)
try {
    doc.activeLayer = doc.layers[doc.layers.length - 1];
} catch(e) {}

// Save result path for submit
try {
    app.putCustomOptions("TextRetouchResultPath", new ActionDescriptor(), true);
    var desc = new ActionDescriptor();
    desc.putString(app.stringIDToTypeID("resultPath"), "D:/Github/eworker/cache/text_retouch/p_mvm4s4pww2p2_result.png");
    app.putCustomOptions("TextRetouchResultPath", desc, true);
} catch(e) {}

// ดึง Photoshop ขึ้นมาบนหน้าจอหลัก
try {
    app.bringToFront();
} catch(e) {}
