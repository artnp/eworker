#target photoshop
// ==============================================================
// auto_text_touch_from_Photoshop.jsx
// สคริปต์ส่งออกภาพ Text-Touch พาดลายน้ำและอัปเดตสถานะให้ลูกค้า
// ==============================================================

var desktop = Folder.desktop;
var pngFile = new File(desktop + '/text_touch_complete.png');

var win = new Window('palette', 'Text-Touch Export', undefined);
win.alignChildren = 'left';
var progressBar = win.add('progressbar', undefined, 0, 100);
progressBar.preferredSize.width = 320;
var statusText = win.add('statictext', undefined, 'กำลังเริ่มส่งออก...');
statusText.preferredSize.width = 320;
win.show();

function setProgress(v, t) {
    progressBar.value = v;
    statusText.text = t;
    win.update();
}

if (!app.documents.length) {
    alert("กรุณาเปิดภาพงานที่กำลังแก้อยู่ก่อนครับ!");
} else {
    var doc = app.activeDocument;

    setProgress(20, 'กำลังส่งออก PNG ไปยัง Desktop...');

    var opts = new ExportOptionsSaveForWeb();
    opts.format = SaveDocumentType.PNG;
    opts.PNG8 = false;
    opts.transparency = true;

    doc.exportDocument(pngFile, ExportType.SAVEFORWEB, opts);

    setProgress(60, 'ส่งออก PNG สำเร็จ กำลังพาดลายน้ำและอัปเดต...');

    var scriptDir = decodeURI($.fileName).replace(/\/[^\/]+$/, '');
    var batFile = new File(scriptDir + "/auto_text_touch_submit.bat");

    if (batFile.exists) {
        setProgress(90, 'กำลังส่งงานขึ้นคลาวด์...');
        batFile.execute();
        setProgress(100, '✅ ส่งงานจุดนี้ให้ลูกค้าเรียบร้อยแล้ว!');
        $.sleep(1200);
        win.close();
    } else {
        alert("ไม่พบไฟล์: " + batFile.fsName);
        win.close();
    }
}
