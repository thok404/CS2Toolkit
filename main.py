import sys
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

try:
    from ctypes import windll
    myappid = 'Moon4Quartz.cs2.toolkit'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

SERVER_NAME = "CS2ToolkitSingleInstanceServer_v1"

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 供打包验证使用：只解码指定图片，不加载用户配置或启动 GSI 服务。
    if len(sys.argv) > 1 and sys.argv[1] == "--probe-image":
        if len(sys.argv) != 4:
            sys.exit(2)
        from app.logic.image_loader import load_image
        decoded = load_image(sys.argv[2])
        result = {"valid": not decoded.isNull(), "width": decoded.width(),
                  "height": decoded.height(), "alpha": decoded.hasAlphaChannel()}
        with open(sys.argv[3], "w", encoding="utf-8") as stream:
            json.dump(result, stream)
        sys.exit(0 if result["valid"] else 1)
    
    # 检查是否已有实例运行
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(500):
        socket.write(b"WAKE_UP")
        socket.waitForBytesWritten(500)
        sys.exit(0)
        
    # 如果没有，则创建本地服务器监听
    server = QLocalServer()
    server.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)
    
    from app.main_window import CS2Tool
    window = CS2Tool()
    
    def on_new_connection():
        client = server.nextPendingConnection()
        client.waitForReadyRead(500)
        msg = client.readAll().data()
        if msg == b"WAKE_UP":
            if window.isHidden() or window.isMinimized():
                window.show_window()
            else:
                window.activateWindow()
                window.raise_()
        client.disconnectFromServer()
        
    server.newConnection.connect(on_new_connection)
    
    window.show()
    sys.exit(app.exec())
