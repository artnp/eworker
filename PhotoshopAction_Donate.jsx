#target photoshop

// สร้างฟังก์ชันหลัก
function runDonateAction() {
    try {
        var doc = app.activeDocument;
        var tempPath = Folder.temp.fsName;
        // เซฟลง Temp แทน เดสก์ท็อป เพื่อป้องกันปัญหา Photoshop ชอบลบไฟล์เดสก์ท็อปแล้วค่อยบันทึกใหม่จนหน้าจอเด้งแก้ไขตำแหน่งไอคอน!
        var saveFile = new File(tempPath + "/ps_export_temp.png");
        
        // กำหนดตัวเลือกสำหรับบันทึกเป็น PNG
        var pngSaveOptions = new PNGSaveOptions();
        pngSaveOptions.compression = 0; // ไม่บีบอัดมากเพื่อให้เซฟเร็ว
        pngSaveOptions.interlaced = false;

        // บันทึกชั่วคราว
        doc.saveAs(saveFile, pngSaveOptions, true, Extension.LOWERCASE);
        
        // พาธของไฟล์ VBScript ที่ต้องการรัน
        var vbsFile = new File("D:/model/secretSend/บริจาค.vbs");
        
        if (vbsFile.exists) {
            vbsFile.execute();
        } else {
            alert("ข้อผิดพลาด: ไม่พบไฟล์ VBScript ที่ D:/model/secretSend/บริจาค.vbs");
        }
    } catch (e) {
        alert("เกิดข้อผิดพลาด: โปรดเปิดรูปภาพใน Photoshop ก่อนรัน Action นี้\n" + e);
    }
}

// เรียกใช้งาน
runDonateAction();
