#target photoshop
var desktop = Folder.desktop;
var pngFile = new File(desktop + '/complete.png');

var win = new Window('palette', 'Alert Save', undefined);
win.alignChildren = 'left';
var progressBar = win.add('progressbar', undefined, 0, 100);
progressBar.preferredSize.width = 350;
var statusText = win.add('statictext', undefined, '');
statusText.preferredSize.width = 350;
win.show();

function setProgress(v, t) {
    progressBar.value = v;
    statusText.text = t;
    win.update();
}

var doc = app.activeDocument;

setProgress(10, 'กำลังส่งออก PNG...');

var opts = new ExportOptionsSaveForWeb();
opts.format = SaveDocumentType.PNG;
opts.PNG8 = false;
opts.transparency = true;

doc.exportDocument(pngFile, ExportType.SAVEFORWEB, opts);

setProgress(50, 'ส่งออกเสร็จ กำลังล้าง metadata...');

var scriptDir = decodeURI($.fileName).replace(/\/[^\/]+$/, '');
app.system('python "' + scriptDir + '/clean_metadata.py" "' + pngFile.fsName + '"');

setProgress(90, 'ล้าง metadata เสร็จ');
setProgress(100, 'บันทึก complete.png สำเร็จ');




var batFile = new File("D:/Github/eworker/auto_private_upload_from_Photoshop.bat");  // เปลี่ยนเป็น path จริงของ .bat คุณ
if (batFile.exists) {
    batFile.execute();
} else {
    alert("ไม่พบไฟล์ .bat!");
}