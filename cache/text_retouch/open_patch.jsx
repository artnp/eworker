// Text-Retouch: Auto-open patch #1
var patchFile = new File("D:/Github/eworker/cache/text_retouch/p_mvlzgf06ms2j.png");
var doc = app.open(patchFile);

// สร้าง Text Layer แยกสำหรับข้อความที่จะแก้ (ขนาด Canvas คงเดิม 100% ไม่สร้างแถบสี)
var textLayer = doc.artLayers.add();
textLayer.kind = LayerKind.TEXT;
textLayer.name = "📝 #1: ลบ";
var txt = textLayer.textItem;
txt.contents = "ลบ";
txt.size = Math.min(Math.max(doc.height * 0.4, 14), 60);
txt.position = [10, Math.min(doc.height * 0.75, doc.height - 5)];
txt.color.rgb.hexValue = "000000";
textLayer.visible = false;

// Active layer = Background (สำหรับรีทัชภาพ)
doc.activeLayer = doc.layers[doc.layers.length - 1];

// Save result path for submit
app.putCustomOptions("TextRetouchResultPath", new ActionDescriptor(), true);
var desc = new ActionDescriptor();
desc.putString(app.stringIDToTypeID("resultPath"), "D:/Github/eworker/cache/text_retouch/p_mvlzgf06ms2j_result.png");
app.putCustomOptions("TextRetouchResultPath", desc, true);
