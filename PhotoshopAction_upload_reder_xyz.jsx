#target photoshop
var batFile = new File("D:/model/secretSend/upload_reder_xyz.bat");  // เปลี่ยนเป็น path จริงของ .bat คุณ
if (batFile.exists) {
    batFile.execute();
} else {
    alert("ไม่พบไฟล์ .bat!");
}