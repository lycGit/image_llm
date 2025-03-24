import websocket
import threading
import time

# WebSocket 服务器地址
WEBSOCKET_URL = "ws://localhost:8080/ws"


# 收到消息时的回调函数
def on_message(ws, message):
    print(f"Received: {message}")


# 发生错误时的回调函数
def on_error(ws, error):
    print(f"Error: {error}")


# 连接关闭时的回调函数
def on_close(ws, close_status_code, close_msg):
    print("Connection closed")


# 连接成功时的回调函数
def on_open(ws):
    print("Connection opened")

    # 发送消息
    def send_message():
        while True:
            message = input("Enter a message: ")
            ws.send(message)
            time.sleep(1)  # 避免频繁发送

    # 启动一个线程发送消息
    threading.Thread(target=send_message).start()


def start_websocket():
    # 创建 WebSocket 连接
    ws = websocket.WebSocketApp(
        WEBSOCKET_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    # 设置连接成功时的回调
    ws.on_open = on_open

    # 启动 WebSocket 客户端
    ws.run_forever()