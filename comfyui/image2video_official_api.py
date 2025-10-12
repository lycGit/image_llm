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

class ComfyUIVideoGenerator:
    """\使用ComfyUI官方API生成视频的类"""
    
    def __init__(self, server_url=COMFYUI_SERVER_URL, websocket_url=WEBSOCKET_URL):
        self.server_url = server_url
        self.websocket_url = websocket_url
        self.client_id = str(uuid.uuid4())
        
    def load_workflow(self, workflow_path):
        """从文件加载工作流配置"""
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
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
        """确保提示词中包含输出节点，防止出现'Prompt has no outputs'错误"""
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
        # 为SaveImage节点确保有filename_prefix
        if node_type == 'SaveImage' and 'filename_prefix' not in prompt[node_id]["inputs"]:
            prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI"
            
        # 为CreateVideo节点确保有必要的参数
        elif node_type == 'CreateVideo' or node_type == 'SaveVideo':
            if 'filename_prefix' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI_video"
            if 'format' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["format"] = "mp4"
            if 'codec' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["codec"] = "h264"
            # 为CreateVideo节点添加fps参数
            if node_type == 'CreateVideo' and 'fps' not in prompt[node_id]["inputs"]:
                prompt[node_id]["inputs"]["fps"] = 24
    
    def _process_node_links(self, workflow_data, prompt, valid_nodes):
        """处理节点之间的链接"""
        if 'links' in workflow_data:
            for link in workflow_data['links']:
                if len(link) >= 5:
                    link_id, source_node_id, source_output_idx, target_node_id, target_input_idx = link[:5]
                    
                    source_node_str = str(source_node_id)
                    target_node_str = str(target_node_id)
                    
                    # 确保源节点和目标节点都在有效节点列表中
                    if source_node_str not in prompt or target_node_str not in prompt:
                        continue
                    
                    # 找到目标节点中对应索引的输入参数名称
                    target_node = next((n for n in valid_nodes if str(n.get('id', '')) == target_node_str), None)
                    if target_node is None or target_input_idx >= len(target_node.get('inputs', [])):
                        continue
                    
                    target_input_name = target_node.get('inputs', [{}])[target_input_idx].get('name', '')
                    if target_input_name:
                        # 设置链接值，格式为[源节点ID, 输出索引]
                        prompt[target_node_str]["inputs"][target_input_name] = [source_node_str, source_output_idx]
    
    def upload_image(self, image_path):
        """上传图片到ComfyUI服务器"""
        try:
            # 确保图片文件存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 构建上传URL
            upload_url = f"{self.server_url}/upload/image"
            filename = os.path.basename(image_path)
            
            # 使用multipart/form-data格式上传图片
            with open(image_path, "rb") as f:
                files = {'image': (filename, f)}
                response = requests.post(upload_url, files=files)
            
            # 检查响应状态
            response.raise_for_status()
            result = response.json()
            
            # 检查上传是否成功
            if "name" in result:
                print(f"图片上传成功: {result['name']}")
                return result['name']
            else:
                raise Exception(f"图片上传失败: {result}")
        except requests.exceptions.HTTPError as e:
            self._handle_http_exception(e, "上传图片")
        except Exception as e:
            print(f"上传图片时出错: {str(e)}")
            raise
    
    def queue_prompt(self, prompt):
        """使用官方API提交提示词"""
        try:
            # 构建请求数据
            data = {
                "prompt": prompt,
                "client_id": self.client_id
            }
            
            # 发送POST请求到/prompt端点
            response = requests.post(
                f"{self.server_url}/prompt",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            
            # 检查响应状态
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            self._handle_http_exception(e, "提交提示词")
        except Exception as e:
            print(f"提交提示词时出错: {str(e)}")
            raise
    
    def get_history(self, prompt_id):
        """获取生成历史记录"""
        try:
            response = requests.get(f"{self.server_url}/history/{prompt_id}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            self._handle_http_exception(e, "获取历史记录")
        except Exception as e:
            print(f"获取历史记录时出错: {str(e)}")
            raise
    
    def track_progress(self, prompt_id):
        """使用WebSocket跟踪生成进度"""
        global should_continue
        
        # 构建WebSocket URL
        ws_url = f"{self.websocket_url}?clientId={self.client_id}"
        
        # 创建WebSocket连接
        ws = websocket.WebSocket()
        
        try:
            # 连接到WebSocket
            ws.connect(ws_url)
            
            print("已连接到WebSocket，正在跟踪视频生成进度...")
            
            # 监听进度消息
            while should_continue:
                try:
                    # 接收消息
                    message = ws.recv()
                    
                    if isinstance(message, str):
                        # 解析JSON消息
                        data = json.loads(message)
                        
                        # 检查消息类型
                        if data.get('type') == 'executing' and data.get('data'):
                            execution_data = data['data']
                            
                            # 显示节点执行进度
                            if execution_data.get('node') is not None:
                                progress = execution_data.get('progress', 0)
                                print(f"\r正在执行节点: {execution_data['node']} ({progress*100:.1f}%)", end="", flush=True)
                            
                            # 检查是否执行完成
                            if execution_data.get('node') is None and execution_data.get('prompt_id') == prompt_id:
                                print()  # 换行
                                print("视频生成完成")
                                break
                except websocket.WebSocketConnectionClosedException:
                    print("WebSocket连接已关闭")
                    break
                except Exception as e:
                    print(f"接收WebSocket消息时出错: {str(e)}")
                    break
        finally:
            # 关闭WebSocket连接
            try:
                ws.close()
            except:
                pass
    
    def _handle_http_exception(self, e, action_description):
        """处理HTTP异常并打印详细信息"""
        status_code = None
        reason = None
        error_text = None
        
        # 尝试从异常对象中获取详细信息
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            reason = e.response.reason
            
            if hasattr(e.response, 'text'):
                error_text = e.response.text
        
        # 打印错误信息
        if status_code and reason:
            print(f"{action_description}时HTTP错误: {status_code} - {reason}")
        else:
            print(f"{action_description}时HTTP错误: {str(e)}")
            
        if error_text:
            print(f"错误详情: {error_text}")
        
        # 重新抛出异常
        raise
    
    def generate_video(self, workflow_path, image_path, custom_prompt=None, negative_prompt=None):
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
            history = self.get_history(prompt_id).get(prompt_id, {})
            
            # 7. 解析结果
            frames_count = 0
            video_info = None
            
            # 计算生成的帧数
            for node_id, node_output in history.get('outputs', {}).items():
                if 'images' in node_output:
                    frames_count += len(node_output['images'])
                
                # 查找视频输出信息
                if 'videos' in node_output:
                    video_info = node_output['videos'][0]  # 假设只有一个视频输出
                    break
                elif 'ui' in node_output and 'videos' in node_output['ui']:
                    video_info = node_output['ui']['videos'][0]
                    break
            
            # 返回结果
            result = {
                'success': True,
                'prompt_id': prompt_id,
                'frames_count': frames_count,
                'message': '视频生成成功'
            }
            
            # 如果找到了视频信息，添加到结果中
            if video_info:
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
            
            return result
        except Exception as e:
            print(f"视频生成过程中出错: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': '视频生成失败'
            }

# 从URL下载图片到临时文件
def download_image_from_url(image_url):
    """从URL下载图片并保存到临时文件"""
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    temp_file_path = temp_file.name
    temp_file.close()
    
    # 下载图片到临时文件
    try:
        print(f"开始下载图片到临时文件: {temp_file_path}")
        urllib.request.urlretrieve(image_url, temp_file_path)
        print(f"图片下载完成，大小: {os.path.getsize(temp_file_path)} 字节")
        return temp_file_path
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise Exception(f"下载图片失败: {str(e)}")

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
        if result['success']:
            print("视频生成成功!")
            print(f"生成的帧数: {result['frames_count']}")
            if 'video_url' in result:
                print(f"视频下载链接: {result['video_url']}")
        else:
            print(f"视频生成失败: {result['error']}")
    finally:
        # 清理临时文件
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass

if __name__ == "__main__":
    # 运行视频生成示例
    generate_video_example()