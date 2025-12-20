import websocket
import threading
import json

from comfyui.image2image import generate_image_from_url_and_prompt
from comfyui.image2video_official_api import generate_video_from_prompt_and_url


class WebSocketClient:
    # def __init__(self, url="ws://127.0.0.1:8092/webSocket/user_py_llm"):
    def __init__(self, url="ws://120.27.130.190:8092/webSocket/user_py_llm"):
        self.url = url
        self.ws = None
        self.is_connected = False
    def on_message(self, ws, message):
        import subprocess
        import asyncio
        print(f"收到服务器消息: {message}")

        try:
            json_data = json.loads(message)
            print("成功解析为JSON对象:", json_data)
            discribe_msg = json_data["msg"]
            # 只有当JSON中有特定指令时才执行
            if json_data.get('action') == 'isLLMOnLine':
                data = {
                    'targetUserId': json_data.get('userId'),
                    "userId": json_data.get('userId'),
                    "msg": "pong",
                    "imageUrl": "",
                }
                json_str = json.dumps(data, ensure_ascii=False, indent=4)
                self.send_message(json_str)

            elif json_data.get('action') == 'image2image':
                # 提示词
                prompt = discribe_msg

                # 图片URL
                image_url = json_data["imageUrl"]

                # 调用图片生成函数
                result = generate_image_from_url_and_prompt(prompt, image_url)

                if result['success']:
                    print("图片生成成功!")
                    # 访问结果
                    for i, item in enumerate(result['results']):
                        print(f"结果 {i + 1}: {item['upload_result']}")
                        data = {
                            'targetUserId': json_data.get('userId'),
                            "userId": json_data.get('userId'),
                            "msg": "图片已创建完成",
                            "imageUrl": item['upload_result'].get('imageUrl1'),
                        }
                        json_str = json.dumps(data, ensure_ascii=False, indent=4)
                        self.send_message(json_str)
                else:
                    print(f"图片生成失败: {result['error']}")
            if json_data.get('action') == 'image2video':
                # 提示词
                prompt = discribe_msg

                # 图片URL
                image_url = json_data["imageUrl"]

                # 调用视频生成函数
                result = generate_video_from_prompt_and_url(prompt, image_url)

                if result['success']:
                    print("视频生成成功!")
                    # 直接使用upload_result
                    if 'upload_result' in result and result['upload_result'].get('success'):
                        print(f"上传结果: {result['upload_result']}")
                        # 尝试获取视频URL
                        video_url = ""
                        # 从response字典中直接提取imageUrl1字段
                        if 'response' in result['upload_result']:
                            response_data = result['upload_result']['response']
                            # 确保response_data是字典格式
                            if isinstance(response_data, dict):
                                video_url = response_data.get('imageUrl1', '')
                                # 清理可能的空格和反引号
                                if video_url:
                                    video_url = video_url.strip().strip('`')
                            print(f"从响应中提取的视频URL: {video_url}")
                        
                        data = {
                            'targetUserId': json_data.get('userId'),
                            "userId": json_data.get('userId'),
                            "msg": "视频已创建完成",
                            "videoUrl": video_url,
                        }
                        json_str = json.dumps(data, ensure_ascii=False, indent=4)
                        self.send_message(json_str)
                    else:
                        print("视频上传失败或未找到上传结果")
                        # 即使上传失败也发送成功消息
                        data = {
                            'targetUserId': json_data.get('userId'),
                            "userId": json_data.get('userId'),
                            "msg": "视频已创建完成，但上传失败",
                            "videoUrl": "",
                        }
                        json_str = json.dumps(data, ensure_ascii=False, indent=4)
                        self.send_message(json_str)
                else:
                    print(f"视频生成失败: {result.get('error', '未知错误')}")
                    # 发送失败消息
                    data = {
                        'targetUserId': json_data.get('userId'),
                        "userId": json_data.get('userId'),
                        "msg": "视频生成失败",
                        "error": result.get('error', '未知错误'),
                    }
                    json_str = json.dumps(data, ensure_ascii=False, indent=4)
                    self.send_message(json_str)
            elif json_data.get('action') == 'IPAdapterFaceIDPortrait':
                process = subprocess.Popen(['python3', 'IPAdapterFaceIDPortrait.py', '--discribe' ,discribe_msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    try:
                        # result = json.loads(stdout)
                        with open('result.txt', 'r') as f:
                            result = f.read()
                            image_json = json.loads(result)
                        print('脚本执行成功，结果:', result)
                        data = {
                            'targetUserId': json_data.get('userId'),
                            "userId": json_data.get('userId'),
                            "msg": "图片已创建完成",
                            "imageUrl": image_json.get('imageUrl'),
                        }
                        json_str = json.dumps(data, ensure_ascii=False, indent=4)
                        self.send_message(json_str)
                    except json.JSONDecodeError:
                        print('解析结果失败，原始输出:', stdout)
                else:
                    print('脚本执行失败，错误信息:', stderr)

            elif json_data.get('action') == 'flux-midjourney-mix2-lora':

                # data = {
                #     'targetUserId': json_data.get('userId'),
                #     "userId": json_data.get('userId'),
                #     "msg": "图片已创建完成",
                #     "imageUrl": "http://120.27.130.190:8091/api/files/download/efc4c43c-614c-400d-960f-06751786f65c_tmpdvgp7yf0.png",
                # }
                # json_str = json.dumps(data, ensure_ascii=False, indent=4)
                # self.send_message(json_str)

                # subprocess.run(['python3', 'flux-midjourney-mix2-lora.py'], check=True)
                process = subprocess.Popen(['python3', 'flux-midjourney-mix2-lora.py', '--discribe' ,discribe_msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    try:
                        # result = json.loads(stdout)
                        with open('result.txt', 'r') as f:
                            result = f.read()
                            image_json = json.loads(result)
                        print('脚本执行成功，结果:', result)
                        data = {
                            'targetUserId': json_data.get('userId'),
                            "userId": json_data.get('userId'),
                            "msg": "图片已创建完成",
                            "imageUrl": image_json.get('imageUrl'),
                        }
                        json_str = json.dumps(data, ensure_ascii=False, indent=4)
                        self.send_message(json_str)
                    except json.JSONDecodeError:
                        print('解析结果失败，原始输出:', stdout)
                else:
                    print('脚本执行失败，错误信息:', stderr)
               # 可以实现异步执行，但是速度太慢了
               #  async def run_script():
               #      try:
               #          process = await asyncio.create_subprocess_exec(
               #              'python3',
               #              'flux-midjourney-mix2-lora.py',
               #              stdout=asyncio.subprocess.PIPE,
               #              stderr=asyncio.subprocess.PIPE
               #          )
               #          stdout, stderr = await process.communicate()
               #          if process.returncode != 0:
               #              raise Exception(stderr.decode())
               #      except Exception as e:
               #          print(f"执行脚本时出错: {e}")
               #
               #  asyncio.run(run_script())
            else:
                print("无效请求", json_data)

        except json.JSONDecodeError:
            print("消息不是JSON格式，按原样处理")
            # 非JSON消息的默认处理
            # subprocess.run(['python3', 'flux-midjourney-mix2-lora.py'], check=True)
        # except subprocess.CalledProcessError as e:
        #     print(f'执行失败: {e}')

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