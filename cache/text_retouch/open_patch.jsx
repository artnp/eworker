
// Text-Retouch: Auto-open patch #1
var patchFile = new File("D:/Github/eworker/cache/text_retouch/p_mvlzgf06ms2j.png");
var doc = app.open(patchFile);
doc.resizeCanvas(doc.width, doc.height + 60, AnchorPosition.TOPCENTER);

// Add note text layer
var textLayer = doc.artLayers.add();
textLayer.kind = LayerKind.TEXT;
textLayer.name = "📝 โน้ต #1";
var txt = textLayer.textItem;
txt.contents = "#1: ลบ";
txt.size = 18;
txt.color.rgb.hexValue = "FFDD00";
txt.position = [10, doc.height - 40];

// Active layer = Background (for editing)
doc.activeLayer = doc.layers[doc.layers.length - 1];

// Save result path for submit
app.putCustomOptions("TextRetouchResultPath", new ActionDescriptor(), true);
var desc = new ActionDescriptor();
desc.putString(app.stringIDToTypeID("resultPath"), "D:/Github/eworker/cache/text_retouch/p_mvlzgf06ms2j_result.png");
app.putCustomOptions("TextRetouchResultPath", desc, true);

