import websocket
import threading
import json

class WebSocketClient:
    # def __init__(self, url="ws://127.0.0.1:8092/webSocket"):
    def __init__(self, url="ws://120.27.130.190:8092/webSocket"):
        self.url = url
        self.ws = None
        self.is_connected = False

    def on_message(self, ws, message):
        import subprocess
        print(f"收到服务器消息: {message}")
        try:
            subprocess.run(['python3', 'flux-midjourney-mix2-lora.py'],
                           check=True)
        except subprocess.CalledProcessError as e:
            print(f'执行 flux-midjourney-mix2-lora.py 失败: {e}')

    def on_error(self, ws, error):
        print(f"连接错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket连接已关闭")
        self.is_connected = False

    def on_open(self, ws):
        print("WebSocket连接已建立")
        self.is_connected = True

    def send_message(self, message):
        if self.ws and self.is_connected:
            try:
                self.ws.send(message)
                print(f"发送消息: {message}")
                return True
            except Exception as e:
                print(f"发送消息失败: {str(e)}")
                return False
        else:
            print("WebSocket未连接")
            return False

    def connect(self):
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # 在新线程中运行WebSocket连接
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

    def close(self):
        if self.ws:
            self.ws.close()

def main():
    # 创建WebSocket客户端实例
    client = WebSocketClient()
    
    try:
        # 连接到服务器
        client.connect()
        
        # 主循环，接收用户输入并发送消息
        while True:
            message = input("请输入要发送的消息（输入'quit'退出）: ")
            if message.lower() == 'quit':
                break
            client.send_message(message)
            
    except KeyboardInterrupt:
        print("\n程序已终止")
    finally:
        client.close()

if __name__ == "__main__":
    main()