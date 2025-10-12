import json
import requests
import websocket
import uuid
import urllib.request
import urllib.parse
import os
import tempfile
import signal
import sys
import time

# 设置服务器地址
COMFYUI_SERVER_URL = "http://127.0.0.1:8188"
WEBSOCKET_URL = "ws://127.0.0.1:8188/ws"

# 标志变量，用于控制程序是否继续运行
should_continue = True

# 信号处理函数，用于优雅地处理中断
def signal_handler(sig, frame):
    global should_continue
    print('\n程序被中断，正在清理资源...')
    should_continue = False

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)

# 下载图片的辅助函数
def download_image_from_url(image_url):
    """从URL下载图片并保存到临时文件"""
    try:
        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        temp_filename = f"temp_image_{uuid.uuid4().hex}.png"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        print(f"正在从URL下载图片: {image_url}")
        
        # 使用urllib或requests下载图片
        try:
            # 优先使用requests
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()  # 如果响应状态码不是200，抛出异常
            
            # 保存图片
            with open(temp_path, 'wb') as f:
                f.write(response.content)
        except ImportError:
            # 如果没有requests库，使用urllib
            urllib.request.urlretrieve(image_url, temp_path)
        
        print(f"图片下载成功，保存至: {temp_path}")
        return temp_path
    except Exception as e:
        print(f"下载图片失败: {str(e)}")
        # 尝试使用本地默认图片
        default_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'images', 'girl.png')
        if os.path.exists(default_image_path):
            print(f"使用默认图片: {default_image_path}")
            return default_image_path
        else:
            raise Exception(f"下载图片失败且找不到默认图片: {str(e)}")

# 设置服务器地址和客户端
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

# 标志变量，用于控制程序是否继续运行
should_continue = True

# 信号处理函数，用于优雅地处理中断
def signal_handler(sig, frame):
    global should_continue
    print('\n程序被中断，正在清理资源...')
    should_continue = False

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)

# 下载图片的辅助函数
def download_image_from_url(image_url):
    """从URL下载图片并保存到临时文件"""
    try:
        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        temp_filename = f"temp_image_{uuid.uuid4().hex}.png"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        print(f"正在从URL下载图片: {image_url}")
        
        # 使用urllib或requests下载图片
        try:
            # 优先使用requests
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()  # 如果响应状态码不是200，抛出异常
            
            # 保存图片
            with open(temp_path, 'wb') as f:
                f.write(response.content)
        except ImportError:
            # 如果没有requests库，使用urllib
            urllib.request.urlretrieve(image_url, temp_path)
        
        print(f"图片下载成功，保存至: {temp_path}")
        return temp_path
    except Exception as e:
        print(f"下载图片失败: {str(e)}")
        # 尝试使用本地默认图片
        default_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'images', 'girl.png')
        if os.path.exists(default_image_path):
            print(f"使用默认图片: {default_image_path}")
            return default_image_path
        else:
            raise Exception(f"下载图片失败且找不到默认图片: {str(e)}")

# 定义向服务器发送提示的函数
def queue_prompt(prompt):
    try:
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(
            "http://{}/prompt".format(server_address),
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP错误: {e.code} - {e.reason}")
        print(f"错误详情: {e.read().decode()}")
        raise
    except Exception as e:
        print(f"请求出错: {str(e)}")
        raise

# 定义从服务器下载图像数据的函数
def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

# 定义获取历史记录的函数
def get_history(prompt_id):
    try:
        with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP错误: {e.code} - {e.reason}")
        print(f"错误详情: {e.read().decode()}")
        raise
    except Exception as e:
        print(f"获取历史记录出错: {str(e)}")
        raise

# 定义通过WebSocket接收消息并下载图像的函数
def get_images(ws, prompt):
    global should_continue
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}

    # 等待任务完成
    while should_continue:
        try:
            result = ws.recv()
            if not result:
                continue
            message = json.loads(result)
            
            # 处理进度消息
            if message['type'] == 'progress':
                data = message.get('data', {})
                if 'value' in data and 'max' in data:
                    progress = data['value'] / data['max'] * 100
                    node_id = data.get('node_id', 'unknown')
                    print(f"正在执行节点: {node_id} ({progress:.1f}%)", end="\r")
            
            # 处理执行状态消息
            elif message['type'] == 'execution_state' and message['data'] == 'idle':
                print("\n视频生成完成")
                break
            
            # 处理执行错误消息
            elif message['type'] == 'execution_error':
                error_msg = message.get('data', {}).get('error', '未知错误')
                print(f"\n执行错误: {error_msg}")
                raise Exception(f"执行错误: {error_msg}")
        except websocket.WebSocketConnectionClosedException:
            print("\nWebSocket连接已关闭")
            break
        except Exception as e:
            print(f"\nWebSocket接收消息出错: {str(e)}")
            break

    # 获取历史记录
    history = get_history(prompt_id)
    if prompt_id in history:
        outputs = history[prompt_id].get('outputs', {})
        
        # 遍历所有输出节点
        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                output_images[node_id] = []
                for image_info in node_output['images']:
                    # 下载图像数据
                    image_data = get_image(
                        image_info['filename'], 
                        image_info['subfolder'], 
                        image_info['type']
                    )
                    output_images[node_id].append(image_data)
    
    return output_images

# ComfyUIVideoGenerator类
class ComfyUIVideoGenerator:
    def __init__(self, server_url="http://127.0.0.1:8188"):
        """初始化ComfyUIVideoGenerator"""
        self.server_url = server_url
        self.client_id = str(uuid.uuid4())
        
    def _handle_http_exception(self, e):
        """处理HTTP异常，提取详细的错误信息"""
        try:
            # 尝试获取错误代码
            status_code = e.code if hasattr(e, 'code') else "未知"
            
            # 尝试获取错误原因
            reason = e.reason if hasattr(e, 'reason') else "未知"
            
            # 尝试获取错误详情
            error_text = ""
            try:
                if hasattr(e, 'read'):
                    error_content = e.read().decode('utf-8')
                    # 尝试解析JSON格式的错误信息
                    try:
                        error_json = json.loads(error_content)
                        error_text = json.dumps(error_json, ensure_ascii=False, indent=2)
                    except json.JSONDecodeError:
                        error_text = error_content
            except Exception:
                error_text = "无法读取错误详情"
            
            return {
                'status_code': status_code,
                'reason': reason,
                'error_text': error_text
            }
        except Exception:
            return {
                'status_code': "未知",
                'reason': "未知",
                'error_text': str(e)
            }
    
    def load_workflow(self, workflow_path):
        """加载工作流配置"""
        try:
            if not os.path.exists(workflow_path):
                raise FileNotFoundError(f"工作流文件不存在: {workflow_path}")
            
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            return workflow_data
        except json.JSONDecodeError as e:
            print(f"解析工作流文件失败: {str(e)}")
            raise
        except Exception as e:
            print(f"加载工作流失败: {str(e)}")
            raise
    
    def prepare_prompt(self, workflow_data, custom_prompt=None, image_filename=None, negative_prompt=None):
        """准备用于提交的提示词和工作流配置"""
        # 创建提示对象
        prompt = {}
        
        # 处理不同格式的工作流数据
        # 检查是否是以节点ID为键的字典格式（如video_wan2_2_14B_i2v.json）
        if isinstance(workflow_data, dict) and all(key.isdigit() for key in workflow_data.keys()):
            print("检测到节点ID为键的工作流格式，使用直接转换模式...")
            # 直接处理每个节点
            for node_id, node_data in workflow_data.items():
                # 跳过注释节点
                if node_data.get('class_type') in ['MarkdownNote', 'Note']:
                    continue
                
                # 创建节点基本结构
                prompt[node_id] = {
                    "inputs": {}
                }
                
                # 复制class_type
                if 'class_type' in node_data:
                    prompt[node_id]["class_type"] = node_data['class_type']
                
                # 复制inputs
                if 'inputs' in node_data:
                    prompt[node_id]["inputs"] = node_data['inputs'].copy()
                
                # 特殊处理某些节点
                node_type = node_data.get('class_type', '')
                
                # 处理图片加载节点
                if node_type == 'LoadImage' and image_filename:
                    prompt[node_id]["inputs"]["image"] = image_filename
                
                # 处理KSamplerAdvanced节点的type参数
                elif node_type == 'KSamplerAdvanced' and node_id == '38':
                    if 'type' not in prompt[node_id]["inputs"]:
                        prompt[node_id]["inputs"]["type"] = "stable_diffusion"
                
                # 处理CreateVideo节点的fps参数
                elif node_type == 'CreateVideo':
                    if 'fps' not in prompt[node_id]["inputs"]:
                        prompt[node_id]["inputs"]["fps"] = 24
                
                # 为保存类节点添加必要的参数
                self._add_required_parameters(node_id, node_type, prompt)
                
            # 不需要额外处理链接，因为已经在inputs中处理了
        else:
            # 原始的处理逻辑，用于兼容nodes和links格式的工作流
            # 过滤掉MarkdownNote和Note节点
            valid_nodes = [node for node in workflow_data.get('nodes', []) 
                          if node.get('type') not in ['MarkdownNote', 'Note']]
            
            # 为每个有效节点创建基本结构
            for node in valid_nodes:
                node_id = str(node.get('id', ''))
                if node_id:
                    prompt[node_id] = {
                        "inputs": {},
                        "class_type": node.get('type', '')
                    }
            
            # 处理每个有效节点的widgets_values和输入参数
            for node in valid_nodes:
                node_id = str(node.get('id', ''))
                if node_id not in prompt:
                    continue
                
                node_type = node.get('type', '')
                
                # 处理节点参数
                if 'widgets_values' in node:
                    # 根据节点类型进行特殊处理
                    self._process_node_parameters(node, node_id, node_type, prompt, 
                                               custom_prompt, image_filename, negative_prompt)
            
            # 处理节点链接
            self._process_node_links(workflow_data, prompt, valid_nodes)
        
        # 确保有输出节点
        self._ensure_has_output_nodes(prompt)
        
        return prompt
        
    def _ensure_has_output_nodes(self, prompt):
        """确保提示词中包含输出节点, 防止出现'Prompt has no outputs'错误"""
        # 检查是否已经包含SaveImage、SaveVideo或其他输出类型的节点
        has_output_node = False
        
        for node_id, node_data in prompt.items():
            node_type = node_data.get('class_type', '')
            if node_type in ['SaveImage', 'SaveVideo']:
                has_output_node = True
                break
        
        # 如果没有输出节点，添加一个输出节点（根据工作流类型选择合适的输出节点）
        if not has_output_node:
            # 查找最后一个可能产生输出的节点
            last_output_node = None
            last_output_node_id = None
            
            for node_id, node_data in prompt.items():
                node_type = node_data.get('class_type', '')
                if node_type in ['VAEDecode', 'CreateVideo', 'WanImageToVideo']:
                    last_output_node = node_data
                    last_output_node_id = node_id
            
            if last_output_node and last_output_node_id:
                # 根据最后一个输出节点的类型添加对应的保存节点
                if last_output_node.get('class_type') == 'CreateVideo':
                    # 添加SaveVideo节点
                    new_node_id = str(len(prompt) + 1)
                    prompt[new_node_id] = {
                        "inputs": {
                            "video": [last_output_node_id, 0],
                            "filename_prefix": "ComfyUI_video",
                            "format": "mp4",
                            "codec": "h264"
                        },
                        "class_type": "SaveVideo"
                    }
                    print(f"添加了SaveVideo输出节点: {new_node_id}")
                else:
                    # 添加SaveImage节点
                    new_node_id = str(len(prompt) + 1)
                    prompt[new_node_id] = {
                        "inputs": {
                            "images": [last_output_node_id, 0],
                            "filename_prefix": "ComfyUI"
                        },
                        "class_type": "SaveImage"
                    }
                    print(f"添加了SaveImage输出节点: {new_node_id}")

    def _process_node_parameters(self, node, node_id, node_type, prompt, 
                               custom_prompt, image_filename, negative_prompt):
        """处理不同类型节点的参数"""
        # 获取所有带widget的输入参数名称
        widget_inputs = [input.get('name', '') for input in node.get('inputs', []) if 'widget' in input]
        
        if node_type == 'KSamplerAdvanced':
            # 处理KSamplerAdvanced节点
            if len(node['widgets_values']) >= 5:
                try:
                    # 处理seed
                    if len(node['widgets_values']) > 1 and node['widgets_values'][1] == 'randomize':
                        prompt[node_id]["inputs"]["seed"] = uuid.uuid4().int % (2**32)
                    elif len(node['widgets_values']) > 1:
                        try:
                            prompt[node_id]["inputs"]["seed"] = int(node['widgets_values'][1])
                        except (ValueError, TypeError):
                            prompt[node_id]["inputs"]["seed"] = uuid.uuid4().int % (2**32)
                    # 设置type参数为有效值
                    if node_id == '38' and 'type' not in prompt[node_id]["inputs"]:
                        prompt[node_id]["inputs"]["type"] = "stable_diffusion"
                except Exception as e:
                    print(f"处理KSampler参数时出错: {str(e)}")
                    prompt[node_id]["inputs"]["seed"] = uuid.uuid4().int % (2**32)
                    if node_id == '38':
                        prompt[node_id]["inputs"]["type"] = "stable_diffusion"
        
        elif node_type == 'CLIPTextEncode':
            # 处理文本编码节点
            if len(node['widgets_values']) > 0:
                original_prompt = node['widgets_values'][0]
                # 判断是否是正面提示节点
                is_positive = False
                node_title = node.get('_meta', {}).get('title', '')
                if node_title and "Positive" in node_title:
                    is_positive = True
                elif "white dragon warrior" in original_prompt and not "色调艳丽" in original_prompt:
                    is_positive = True
                
                if is_positive:
                    # 使用自定义提示语或原始提示语
                    prompt[node_id]["inputs"]["text"] = custom_prompt if custom_prompt else original_prompt
                elif node_title and "Negative" in node_title or "色调艳丽" in original_prompt:
                    # 处理负面提示语
                    prompt[node_id]["inputs"]["text"] = negative_prompt if negative_prompt else original_prompt
                else:
                    # 其他文本节点保持原样
                    prompt[node_id]["inputs"]["text"] = original_prompt
        
        elif node_type == 'LoadImage':
            # 处理图片加载节点
            if image_filename:
                prompt[node_id]["inputs"]["image"] = image_filename
            elif len(node['widgets_values']) > 0:
                prompt[node_id]["inputs"]["image"] = node['widgets_values'][0]
        
        elif node_type == 'WanImageToVideo':
            # 处理图像转视频节点
            if len(node['widgets_values']) >= 4:
                try:
                    prompt[node_id]["inputs"]["width"] = node['widgets_values'][0]  # 宽度
                    prompt[node_id]["inputs"]["height"] = node['widgets_values'][1]  # 高度
                    prompt[node_id]["inputs"]["seed"] = node['widgets_values'][2]  # 种子
                    prompt[node_id]["inputs"]["motion_strength"] = node['widgets_values'][3]  # 运动强度
                except (IndexError, ValueError, TypeError):
                    print("WanImageToVideo节点参数设置失败，使用默认值")
        
        else:
            # 处理其他类型的节点
            for i, value in enumerate(node['widgets_values']):
                if i < len(widget_inputs):
                    input_name = widget_inputs[i]
                    prompt[node_id]["inputs"][input_name] = value
        
        # 为保存类节点添加必要的参数
        self._add_required_parameters(node_id, node_type, prompt)
    
    def _add_required_parameters(self, node_id, node_type, prompt):
        """为节点添加必要的参数"""
        # 为保存类节点添加必要的参数
        if node_type == 'SaveVideo':
            # 确保SaveVideo节点有必要的参数
            if 'filename_prefix' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI_video"
            if 'format' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["format"] = "mp4"
            if 'codec' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["codec"] = "h264"
        elif node_type == 'SaveImage':
            # 确保SaveImage节点有必要的参数
            if 'filename_prefix' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI"
    
    def _process_node_links(self, workflow_data, prompt, valid_nodes):
        """处理节点之间的链接"""
        # 创建节点ID到节点对象的映射
        node_id_map = {str(node.get('id', '')): node for node in valid_nodes}
        
        # 处理链接
        links = workflow_data.get('links', [])
        for link in links:
            # 链接格式：[源节点ID, 源节点输出索引, 目标节点ID, 目标节点输入索引, 链接类型]
            if len(link) < 4:
                continue
            
            source_node_id = str(link[0])
            source_output_idx = link[1]
            target_node_id = str(link[2])
            target_input_idx = link[3]
            
            # 确保源节点和目标节点都在prompt中
            if source_node_id not in prompt or target_node_id not in prompt:
                continue
            
            # 获取目标节点的输入名称
            target_node = node_id_map.get(target_node_id)
            if not target_node:
                continue
            
            # 获取目标节点的输入列表
            target_inputs = target_node.get('inputs', [])
            if target_input_idx < 0 or target_input_idx >= len(target_inputs):
                continue
            
            target_input_name = target_inputs[target_input_idx].get('name', '')
            if target_input_name:
                # 设置链接：[源节点ID, 源节点输出索引]
                prompt[target_node_id]["inputs"][target_input_name] = [source_node_id, source_output_idx]
    
    def upload_image(self, image_path):
        """上传图片到ComfyUI服务器"""
        try:
            # 检查图片是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 准备上传请求 - 使用multipart/form-data格式
            url = f"{self.server_url}/upload/image"
            
            # 获取文件名
            image_filename = os.path.basename(image_path)
            
            # 使用files参数上传图片（requests会自动设置multipart/form-data格式）
            with open(image_path, 'rb') as f:
                files = {'image': (image_filename, f, 'image/png')}
                response = requests.post(url, files=files)
                
            response.raise_for_status()  # 如果响应状态码不是200，抛出异常
            
            # 解析响应
            response_json = response.json()
            image_filename = response_json.get('name')
            
            if not image_filename:
                # 如果没有返回name字段，尝试使用原始文件名
                image_filename = image_filename
                print(f"警告：服务器未返回图片名称，使用原始文件名: {image_filename}")
            
            print(f"图片上传成功: {image_filename}")
            return image_filename
        except requests.exceptions.HTTPError as e:
            # 处理HTTP错误
            error_info = self._handle_http_exception(e)
            print(f"上传图片HTTP错误: {error_info['status_code']} - {error_info['reason']}")
            print(f"错误详情: {error_info['error_text']}")
            raise
        except Exception as e:
            print(f"上传图片失败: {str(e)}")
            raise
    
    def queue_prompt(self, prompt):
        """提交提示词到ComfyUI服务器"""
        try:
            # 准备请求数据
            payload = {
                "prompt": prompt,
                "client_id": self.client_id
            }
            
            # 发送POST请求
            url = f"{self.server_url}/prompt"
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()  # 如果响应状态码不是200，抛出异常
            
            # 解析响应
            response_json = response.json()
            return response_json
        except requests.exceptions.HTTPError as e:
            # 处理HTTP错误
            error_info = self._handle_http_exception(e)
            print(f"提交提示词HTTP错误: {error_info['status_code']} - {error_info['reason']}")
            print(f"错误详情: {error_info['error_text']}")
            raise
        except Exception as e:
            print(f"提交提示词失败: {str(e)}")
            raise
    
    def get_history(self, prompt_id):
        """获取提示词执行历史"""
        try:
            # 发送GET请求
            url = f"{self.server_url}/history/{prompt_id}"
            response = requests.get(url)
            response.raise_for_status()  # 如果响应状态码不是200，抛出异常
            
            # 解析响应
            response_json = response.json()
            return response_json
        except requests.exceptions.HTTPError as e:
            # 处理HTTP错误
            error_info = self._handle_http_exception(e)
            print(f"获取历史记录HTTP错误: {error_info['status_code']} - {error_info['reason']}")
            print(f"错误详情: {error_info['error_text']}")
            raise
        except Exception as e:
            print(f"获取历史记录失败: {str(e)}")
            raise
    
    def track_progress(self, prompt_id):
        """通过WebSocket跟踪任务执行进度"""
        global should_continue
        
        try:
            # 创建WebSocket连接
            ws_url = f"ws://{self.server_url.split('//')[-1]}/ws?clientId={self.client_id}"
            ws = websocket.WebSocket()
            ws.connect(ws_url)
            
            # 等待任务完成或被中断
            while should_continue:
                try:
                    # 接收WebSocket消息
                    message = ws.recv()
                    if not message:
                        continue
                    
                    # 解析消息
                    message_data = json.loads(message)
                    
                    # 处理进度消息
                    if message_data.get('type') == 'progress':
                        progress_data = message_data.get('data', {})
                        if 'value' in progress_data and 'max' in progress_data:
                            progress_percent = (progress_data['value'] / progress_data['max']) * 100
                            node_id = progress_data.get('node_id', '未知')
                            print(f"正在执行节点: {node_id} ({progress_percent:.1f}%)", end="\r")
                    
                    # 处理执行状态消息
                    elif message_data.get('type') == 'execution_state':
                        if message_data.get('data') == 'idle':
                            print("\n视频生成完成")
                            break
                    
                    # 处理错误消息
                    elif message_data.get('type') == 'execution_error':
                        error_msg = message_data.get('data', {}).get('error', '未知错误')
                        print(f"\n执行错误: {error_msg}")
                        raise Exception(f"执行错误: {error_msg}")
                except websocket.WebSocketTimeoutException:
                    # WebSocket超时，继续等待
                    continue
                except websocket.WebSocketConnectionClosedException:
                    print("\nWebSocket连接已关闭")
                    break
                except json.JSONDecodeError:
                    # 消息不是有效的JSON，忽略
                    continue
        except Exception as e:
            print(f"跟踪进度出错: {str(e)}")
        finally:
            # 关闭WebSocket连接
            try:
                if 'ws' in locals() and ws.connected:
                    ws.close()
            except:
                pass
    
    def download_video(self, video_url, save_directory=None, filename=None):
        """下载视频文件并保存到本地"""
        try:
            # 确定保存目录
            if save_directory is None:
                # 默认保存到当前工作目录的output_videos子目录
                save_directory = os.path.join(os.getcwd(), 'output_videos')
                
            # 确保保存目录存在
            os.makedirs(save_directory, exist_ok=True)
            
            # 确定文件名
            if filename is None:
                # 从URL或当前时间生成文件名
                if 'filename=' in video_url:
                    # 尝试从URL中提取文件名
                    url_filename = urllib.parse.unquote(video_url.split('filename=')[1].split('&')[0])
                    filename = url_filename
                else:
                    # 使用时间戳生成唯一文件名
                    timestamp = time.strftime('%Y%m%d_%H%M%S')
                    filename = f"comfyui_video_{timestamp}.mp4"
            
            # 构建完整的保存路径
            save_path = os.path.join(save_directory, filename)
            
            print(f"正在下载视频到本地: {save_path}")
            
            # 发送GET请求下载视频
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            # 写入文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"视频已成功保存到: {save_path}")
            return save_path
        except Exception as e:
            print(f"下载视频失败: {str(e)}")
            raise

    def generate_video(self, workflow_path, image_path, custom_prompt=None, negative_prompt=None, save_to_local=True, save_directory=None):
        """生成视频的主函数"""
        global should_continue
        
        try:
            # 1. 加载工作流
            print(f"正在加载工作流文件: {workflow_path}")
            workflow_data = self.load_workflow(workflow_path)
            
            # 2. 上传图片
            image_filename = self.upload_image(image_path)
            
            # 3. 准备提示词
            print("正在准备提示词配置...")
            prompt = self.prepare_prompt(
                workflow_data, 
                custom_prompt=custom_prompt, 
                image_filename=image_filename,
                negative_prompt=negative_prompt
            )
            
            # 检查是否被中断
            if not should_continue:
                return {
                    'success': False,
                    'error': '程序被用户中断',
                    'message': '视频生成被用户中断'
                }
            
            # 4. 提交提示词到服务器
            print("正在提交视频生成任务...")
            queue_response = self.queue_prompt(prompt)
            prompt_id = queue_response.get('prompt_id')
            
            if not prompt_id:
                raise Exception(f"提交任务失败，响应: {queue_response}")
            
            print(f"任务ID: {prompt_id}")
            
            # 5. 跟踪生成进度
            self.track_progress(prompt_id)
            
            # 检查是否被中断
            if not should_continue:
                return {
                    'success': False,
                    'error': '程序被用户中断',
                    'message': '视频生成被用户中断'
                }
            
            # 6. 获取生成历史
            print("正在获取视频生成结果...")
            history = self.get_history(prompt_id)
            
            # 检查历史记录是否包含prompt_id
            if prompt_id not in history:
                print(f"警告: 历史记录中未找到任务ID {prompt_id}")
                print(f"历史记录内容: {history}")
                return {
                    'success': False,
                    'error': '任务未在历史记录中找到',
                    'message': '视频生成可能未完成',
                    'frames_count': 0,
                    'prompt_id': prompt_id
                }
            
            prompt_history = history.get(prompt_id, {})
            
            # 7. 解析结果
            frames_count = 0
            video_info = None
            has_output = False
            
            # 计算生成的帧数并查找视频信息
            outputs = prompt_history.get('outputs', {})
            if not outputs:
                print("警告: 任务历史记录中没有输出")
            else:
                print(f"找到 {len(outputs)} 个输出节点")
                
                for node_id, node_output in outputs.items():
                    print(f"检查节点 {node_id} (类型: {node_output.get('class_type', '未知')})")
                    
                    # 标记有输出
                    has_output = True
                    
                    # 计算帧数
                    if 'images' in node_output:
                        node_frames = len(node_output['images'])
                        frames_count += node_frames
                        print(f"节点 {node_id} 生成了 {node_frames} 帧")
                    
                    # 查找视频输出信息
                    if 'videos' in node_output:
                        print(f"节点 {node_id} 包含视频输出")
                        video_info = node_output['videos'][0]  # 假设只有一个视频输出
                        break
                    elif 'ui' in node_output:
                        ui_output = node_output['ui']
                        if 'videos' in ui_output:
                            print(f"节点 {node_id} 的UI输出包含视频")
                            video_info = ui_output['videos'][0]
                            break
                    elif 'images' in node_output and len(node_output['images']) > 0:
                        # 即使没有视频，有图像也表示部分成功
                        print(f"节点 {node_id} 生成了图像但没有视频")
            
            # 根据实际结果判断是否成功
            if not has_output:
                return {
                    'success': False,
                    'error': '没有生成任何输出',
                    'message': '视频生成失败: 没有生成任何内容',
                    'frames_count': frames_count,
                    'prompt_id': prompt_id
                }
            
            # 构建结果对象
            result = {
                'success': video_info is not None,  # 只有生成了视频才算真正成功
                'prompt_id': prompt_id,
                'frames_count': frames_count,
                'has_output': has_output
            }
            
            # 根据结果设置消息
            if video_info:
                result['message'] = '视频生成成功'
                result['video_info'] = video_info
                
                # 构建视频下载URL
                if 'filename' in video_info and 'subfolder' in video_info and 'type' in video_info:
                    # 使用urllib.parse.quote来编码URL参数
                    filename = urllib.parse.quote(video_info['filename'])
                    subfolder = urllib.parse.quote(video_info['subfolder'])
                    type_ = urllib.parse.quote(video_info['type'])
                    
                    video_url = f"{self.server_url}/view?filename={filename}&subfolder={subfolder}&type={type_}"
                    result['video_url'] = video_url
                    print(f"视频生成成功，下载地址: {video_url}")
                    
                    # 如果需要保存到本地
                    if save_to_local:
                        try:
                            local_video_path = self.download_video(video_url, save_directory=save_directory, filename=video_info['filename'])
                            result['local_video_path'] = local_video_path
                        except Exception as e:
                            print(f"保存视频到本地失败，但视频生成成功: {str(e)}")
                            result['local_video_save_error'] = str(e)
            elif frames_count > 0:
                result['success'] = False
                result['error'] = '只生成了图像帧但没有视频'
                result['message'] = f'视频生成部分成功: 生成了 {frames_count} 帧但没有合成视频'
            else:
                result['success'] = False
                result['error'] = '没有生成视频或图像帧'
                result['message'] = '视频生成失败: 没有生成视频或图像帧'
            
            return result
        except Exception as e:
            print(f"视频生成过程中出错: {str(e)}")
            import traceback
            traceback.print_exc()  # 打印详细的错误栈
            return {
                'success': False,
                'error': str(e),
                'message': '视频生成失败'
            }

# 视频生成示例函数
def generate_video_example():
    """视频生成示例"""
    # 创建视频生成器实例
    video_generator = ComfyUIVideoGenerator()
    
    # 工作流文件路径
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'video_wan2_2_14B_i2v.json')
    
    # 图片路径 - 可以是本地路径或URL
    # 本地图片示例
    # image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'images', 'girl.png')
    
    # 从URL下载图片示例
    image_url = "http://120.27.130.190:8091/api/files/download/14d1ea3f-07ea-4302-afff-adc3e6d03c0e_tmpx4_5ndmd.png"
    image_path = download_image_from_url(image_url)
    
    try:
        # 自定义提示词
        prompt = "A beautiful landscape with mountains and lake, clouds moving slowly across the sky"
        
        # 负面提示词
        negative_prompt = "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止"
        
        # 生成视频
        result = video_generator.generate_video(
            workflow_path=workflow_path,
            image_path=image_path,
            custom_prompt=prompt,
            negative_prompt=negative_prompt
        )
        
        # 打印结果
        print("\n===== 视频生成结果 =====")
        if result['success']:
            print("✅ 视频生成成功!")
            print(f"生成的帧数: {result['frames_count']}")
            if 'video_url' in result:
                print(f"视频下载链接: {result['video_url']}")
        else:
            print(f"❌ 视频生成失败")
            print(f"错误信息: {result.get('error', '未知错误')}")
            print(f"详细信息: {result.get('message', '')}")
            print(f"生成的帧数: {result.get('frames_count', 0)}")
            print(f"是否有输出: {result.get('has_output', False)}")
        print("======================")
    except Exception as e:
        print(f"示例执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理临时文件
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass

# 从URL和提示词生成视频的函数
def generate_video_from_url_and_prompt(prompt, image_url, negative_prompt=None):
    """从URL和提示词生成视频"""
    # 创建视频生成器实例
    video_generator = ComfyUIVideoGenerator()
    
    # 工作流文件路径
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'video_wan2_2_14B_i2v.json')
    
    # 下载图片
    image_path = download_image_from_url(image_url)
    
    try:
        # 生成视频
        result = video_generator.generate_video(
            workflow_path=workflow_path,
            image_path=image_path,
            custom_prompt=prompt,
            negative_prompt=negative_prompt
        )
        
        return result
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': '视频生成失败'
        }
    finally:
        # 清理临时文件
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass

# 使用本地图片生成视频的函数
def generate_video_from_local_image(image_path, prompt, negative_prompt=None):
    """从本地图片生成视频"""
    # 创建视频生成器实例
    video_generator = ComfyUIVideoGenerator()
    
    # 工作流文件路径
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'video_wan2_2_14B_i2v.json')
    
    try:
        # 检查图片文件是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 生成视频
        result = video_generator.generate_video(
            workflow_path=workflow_path,
            image_path=image_path,
            custom_prompt=prompt,
            negative_prompt=negative_prompt
        )
        
        return result
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': '视频生成失败'
        }

if __name__ == "__main__":
    # 运行示例
    generate_video_example()