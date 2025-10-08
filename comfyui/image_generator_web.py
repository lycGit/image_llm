import os
import json
import requests
import base64
from flask import Flask, request, render_template_string, jsonify, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import io
import time
import uuid
import websocket
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['COMFYUI_API_URL'] = 'http://localhost:8188'
app.config['SECRET_KEY'] = str(uuid.uuid4())  # 用于会话管理

# 创建上传目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 上传图片到ComfyUI服务器
def upload_image_to_comfyui(image_path):
    try:
        # 使用表单数据方式上传图片
        url = f"{app.config['COMFYUI_API_URL']}/upload/image"
        filename = os.path.basename(image_path)
        
        with open(image_path, "rb") as f:
            files = {'image': (filename, f)}
            response = requests.post(url, files=files)
            
        response.raise_for_status()
        result = response.json()
        
        if "name" in result:
            return result['name']
        else:
            raise Exception(f"图片上传失败: {result}")
    except Exception as e:
        raise Exception(f"上传图片时出错: {str(e)}")

# 加载并处理工作流JSON文件
def load_workflow_from_json(file_path, custom_prompt=None, image_filename=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)
    
    prompt = {}
    
    # 过滤掉MarkdownNote节点
    valid_nodes = [node for node in workflow_data['nodes'] if node['type'] != 'MarkdownNote']
    
    # 为每个有效节点创建基本结构
    for node in valid_nodes:
        node_id = str(node['id'])
        prompt[node_id] = {
            "inputs": {},
            "class_type": node['type']
        }
    
    # 处理每个有效节点的widgets_values和输入参数
    for node in valid_nodes:
        node_id = str(node['id'])
        node_type = node['type']
        
        # 获取所有带widget的输入参数名称
        widget_inputs = [input['name'] for input in node['inputs'] if 'widget' in input]
        
        # 如果有widgets_values，将其映射到对应的输入参数
        if 'widgets_values' in node:
            # 特殊处理KSampler节点
            if node_type == 'KSampler':
                if len(node['widgets_values']) >= 6:
                    # 处理seed
                    try:
                        prompt[node_id]["inputs"]["seed"] = int(node['widgets_values'][0])
                    except (ValueError, TypeError):
                        prompt[node_id]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
                    
                    # 处理steps
                    steps_value = node['widgets_values'][1]
                    if isinstance(steps_value, str) and steps_value == 'randomize':
                        prompt[node_id]["inputs"]["steps"] = 20
                    else:
                        try:
                            prompt[node_id]["inputs"]["steps"] = int(steps_value)
                        except (ValueError, TypeError):
                            prompt[node_id]["inputs"]["steps"] = 20
                    
                    # 处理cfg
                    try:
                        prompt[node_id]["inputs"]["cfg"] = float(node['widgets_values'][2])
                    except (ValueError, TypeError):
                        prompt[node_id]["inputs"]["cfg"] = 8.0
                    
                    # 设置采样器和调度器
                    if len(node['widgets_values']) >= 4:
                        sampler_name = node['widgets_values'][3] if isinstance(node['widgets_values'][3], str) else "dpmpp_2m"
                        prompt[node_id]["inputs"]["sampler_name"] = sampler_name
                    else:
                        prompt[node_id]["inputs"]["sampler_name"] = "dpmpp_2m"
                    
                    if len(node['widgets_values']) >= 5:
                        # 修复这里，将'normal'设为默认调度器
                        scheduler = "normal"  # 直接使用有效的调度器值
                        prompt[node_id]["inputs"]["scheduler"] = scheduler
                    else:
                        prompt[node_id]["inputs"]["scheduler"] = "normal"
                    
                    # 处理denoise
                    if len(node['widgets_values']) >= 6:
                        try:
                            prompt[node_id]["inputs"]["denoise"] = float(node['widgets_values'][5])
                        except (ValueError, TypeError):
                            prompt[node_id]["inputs"]["denoise"] = 0.87
                    else:
                        prompt[node_id]["inputs"]["denoise"] = 0.87
            elif node_type == 'CLIPTextEncode':
                # 处理文本编码节点
                if len(node['widgets_values']) > 0:
                    if custom_prompt:
                        prompt[node_id]["inputs"]["text"] = custom_prompt
                    else:
                        prompt[node_id]["inputs"]["text"] = node['widgets_values'][0]
            elif node_type == 'LoadImage':
                # 处理图片加载节点
                if image_filename:
                    prompt[node_id]["inputs"]["image"] = image_filename
                else:
                    if len(node['widgets_values']) > 0:
                        prompt[node_id]["inputs"]["image"] = node['widgets_values'][0]
            else:
                # 普通节点的处理逻辑
                for i, value in enumerate(node['widgets_values']):
                    if i < len(widget_inputs):
                        input_name = widget_inputs[i]
                        prompt[node_id]["inputs"][input_name] = value
        
        # 为SaveImage节点确保有filename_prefix
        if node_type == 'SaveImage' and 'filename_prefix' not in prompt[node_id]["inputs"]:
            prompt[node_id]["inputs"]["filename_prefix"] = "ComfyUI"
    
    # 处理节点之间的链接
    for link in workflow_data['links']:
        link_id, source_node_id, source_output_idx, target_node_id, target_input_idx, link_type = link
        
        source_node_str = str(source_node_id)
        target_node_str = str(target_node_id)
        
        # 确保源节点和目标节点都在有效节点列表中
        if source_node_str not in prompt or target_node_str not in prompt:
            continue
        
        # 找到目标节点中对应索引的输入参数名称
        target_node = next((n for n in valid_nodes if str(n['id']) == target_node_str), None)
        if target_node is None or target_input_idx >= len(target_node['inputs']):
            continue
        
        target_input_name = target_node['inputs'][target_input_idx]['name']
        
        # 设置链接值
        prompt[target_node_str]["inputs"][target_input_name] = [source_node_str, source_output_idx]
    
    return prompt

# 执行ComfyUI工作流
def run_comfyui_workflow(workflow_type, prompt_text, image_path=None):
    try:
        # 根据工作流类型选择对应的JSON文件
        if workflow_type == 'image2image':
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'image2image.json')
        else:
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'generate_image.json')
        
        # 检查工作流文件是否存在
        if not os.path.exists(workflow_path):
            raise Exception(f'工作流文件不存在: {workflow_path}')
        
        # 上传图片到ComfyUI(如果提供了图片)
        image_filename = None
        if image_path and os.path.exists(image_path):
            image_filename = upload_image_to_comfyui(image_path)
        
        # 加载并处理工作流
        prompt = load_workflow_from_json(workflow_path, custom_prompt=prompt_text, image_filename=image_filename)
        
        # 创建客户端ID
        client_id = str(uuid.uuid4())
        
        # 发送工作流到ComfyUI API
        response = requests.post(
            f"{app.config['COMFYUI_API_URL']}/prompt",
            json={'prompt': prompt, 'client_id': client_id}
        )
        
        if response.status_code == 200:
            prompt_id = response.json()['prompt_id']
            return {'success': True, 'prompt_id': prompt_id, 'client_id': client_id, 'api_url': app.config['COMFYUI_API_URL']}
        else:
            error_details = response.text if response.text else '未知错误'
            raise Exception(f"ComfyUI API错误: {error_details}")
    except Exception as e:
        return {'success': False, 'error': str(e)}

# 获取生成进度
def get_progress(prompt_id):
    try:
        # 确保COMFYUI_API_URL配置正确且不以斜杠结尾
        api_url = app.config['COMFYUI_API_URL'].rstrip('/')
        
        # 首先尝试检查历史记录，这是判断任务是否完成的最可靠方法
        history_url = f"{api_url}/history/{prompt_id}"
        history_response = requests.get(history_url, timeout=5)
        
        if history_response.status_code == 200:
            history_data = history_response.json()
            # 如果prompt_id在历史记录中，说明任务已完成
            if prompt_id in history_data:
                return {'success': True, 'progress': 1.0, 'completed': True}
        
        # 尝试使用queue API作为备选的进度查询方法
        queue_url = f"{api_url}/queue"
        queue_response = requests.get(queue_url, timeout=5)
        
        if queue_response.status_code == 200:
            try:
                queue_data = queue_response.json()
                # 检查队列状态
                if isinstance(queue_data, dict):
                    # 返回一个估计的进度值，实际应用中可能需要根据队列长度调整
                    if queue_data.get('status') == 'idle':
                        return {'success': True, 'progress': 0.9, 'completed': False}
                    else:
                        return {'success': True, 'progress': 0.5, 'completed': False}
            except json.JSONDecodeError:
                pass
        
        # 如果以上方法都失败，返回一个默认的进行中状态
        return {'success': True, 'progress': 0.3, 'completed': False}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': f'无法连接到ComfyUI服务: {app.config["COMFYUI_API_URL"]}\n请确保ComfyUI服务已启动'}
    except requests.exceptions.Timeout:
        return {'success': False, 'error': '请求ComfyUI API超时'}
    except Exception as e:
        return {'success': False, 'error': f'获取进度异常: {str(e)}'}

# 获取生成的图像
def get_generated_image(prompt_id):
    try:
        # 获取历史记录以获取图像
        response = requests.get(f"{app.config['COMFYUI_API_URL']}/history/{prompt_id}")
        if response.status_code == 200:
            history = response.json()
            if prompt_id in history and 'outputs' in history[prompt_id]:
                outputs = history[prompt_id]['outputs']
                # 查找包含图像的节点
                for node_id, node_outputs in outputs.items():
                    if 'images' in node_outputs:
                        for image_data in node_outputs['images']:
                            # 从ComfyUI获取图像
                            image_url = f"{app.config['COMFYUI_API_URL']}/view?filename={image_data['filename']}&subfolder={image_data['subfolder']}&type={image_data['type']}"
                            img_response = requests.get(image_url)
                            if img_response.status_code == 200:
                                # 保存图像到临时位置
                                img = Image.open(io.BytesIO(img_response.content))
                                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"generated_{prompt_id}.png")
                                img.save(temp_path)
                                return {'success': True, 'image_path': temp_path}
            return {'success': False, 'error': "生成结果中未找到图像"}
        return {'success': False, 'error': f"API错误: {response.text}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}



# 检查任务是否完成（更可靠的方法）
def is_task_completed(prompt_id):
    try:
        api_url = app.config['COMFYUI_API_URL'].rstrip('/')
        history_url = f"{api_url}/history/{prompt_id}"
        
        response = requests.get(history_url, timeout=5)
        if response.status_code == 200:
            history_data = response.json()
            return prompt_id in history_data
        return False
    except:
        return False

# 在run_comfyui_workflow函数中，修改返回值以包含更详细信息
def run_comfyui_workflow(workflow_type, prompt_text, image_path=None):
    try:
        # 根据工作流类型选择对应的JSON文件
        if workflow_type == 'image2image':
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'image2image.json')
        else:
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'generate_image.json')
        
        # 检查工作流文件是否存在
        if not os.path.exists(workflow_path):
            raise Exception(f'工作流文件不存在: {workflow_path}')
        
        # 上传图片到ComfyUI(如果提供了图片)
        image_filename = None
        if image_path and os.path.exists(image_path):
            image_filename = upload_image_to_comfyui(image_path)
        
        # 加载并处理工作流
        prompt = load_workflow_from_json(workflow_path, custom_prompt=prompt_text, image_filename=image_filename)
        
        # 创建客户端ID
        client_id = str(uuid.uuid4())
        
        # 发送工作流到ComfyUI API
        response = requests.post(
            f"{app.config['COMFYUI_API_URL']}/prompt",
            json={'prompt': prompt, 'client_id': client_id}
        )
        
        if response.status_code == 200:
            prompt_id = response.json()['prompt_id']
            return {'success': True, 'prompt_id': prompt_id, 'client_id': client_id, 'api_url': app.config['COMFYUI_API_URL']}
        else:
            error_details = response.text if response.text else '未知错误'
            raise Exception(f"ComfyUI API错误: {error_details}")
    except Exception as e:
        return {'success': False, 'error': str(e)}

# 获取生成的图像
def get_generated_image(prompt_id):
    try:
        # 获取历史记录以获取图像
        response = requests.get(f"{app.config['COMFYUI_API_URL']}/history/{prompt_id}")
        if response.status_code == 200:
            history = response.json()
            if prompt_id in history and 'outputs' in history[prompt_id]:
                outputs = history[prompt_id]['outputs']
                # 查找包含图像的节点
                for node_id, node_outputs in outputs.items():
                    if 'images' in node_outputs:
                        for image_data in node_outputs['images']:
                            # 从ComfyUI获取图像
                            image_url = f"{app.config['COMFYUI_API_URL']}/view?filename={image_data['filename']}&subfolder={image_data['subfolder']}&type={image_data['type']}"
                            img_response = requests.get(image_url)
                            if img_response.status_code == 200:
                                # 保存图像到临时位置
                                img = Image.open(io.BytesIO(img_response.content))
                                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"generated_{prompt_id}.png")
                                img.save(temp_path)
                                return {'success': True, 'image_path': temp_path}
            return {'success': False, 'error': "生成结果中未找到图像"}
        return {'success': False, 'error': f"API错误: {response.text}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# 主页面
@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI图像生成工具</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }
            .container {
                background-color: white;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                padding: 30px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #555;
            }
            select,
            input[type="text"],
            textarea {
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
                box-sizing: border-box;
                transition: border-color 0.3s;
            }
            select:focus,
            input[type="text"]:focus,
            textarea:focus {
                outline: none;
                border-color: #4CAF50;
            }
            textarea {
                resize: vertical;
                min-height: 100px;
            }
            .image-preview {
                margin-top: 10px;
                max-width: 100%;
                height: auto;
                border-radius: 5px;
                display: none;
                border: 1px solid #ddd;
            }
            .button-group {
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }
            button {
                padding: 12px 20px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                transition: background-color 0.3s;
                flex: 1;
            }
            button:hover {
                background-color: #45a049;
            }
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            #progress-container {
                margin-top: 20px;
                width: 100%;
                background-color: #f1f1f1;
                border-radius: 5px;
                display: none;
                position: relative;
                overflow: hidden;
            }
            #progress-bar {
                width: 0%;
                height: 30px;
                background-color: #4CAF50;
                text-align: center;
                line-height: 30px;
                color: white;
                border-radius: 5px;
                transition: width 0.3s ease;
            }
            #progress-text {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #333;
                font-weight: bold;
            }
            #result-container {
                margin-top: 30px;
                display: none;
            }
            #result-image {
                max-width: 100%;
                height: auto;
                border-radius: 5px;
                border: 1px solid #ddd;
            }
            #error-message {
                color: #d32f2f;
                margin-top: 15px;
                padding: 10px;
                background-color: #ffebee;
                border-radius: 5px;
                display: none;
                border-left: 4px solid #d32f2f;
            }
            .history-item {
                margin-top: 15px;
                padding: 10px;
                background-color: #f9f9f9;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }
            .history-item:hover {
                background-color: #f1f1f1;
            }
            @media (max-width: 600px) {
                body {
                    padding: 10px;
                }
                .container {
                    padding: 20px;
                }
                .button-group {
                    flex-direction: column;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AI图像生成工具</h1>
            
            <form id="generation-form">
                <div class="form-group">
                    <label for="workflow-type">生成类型:</label>
                    <select id="workflow-type" name="workflow_type">
                        <option value="text2image">文本生成图像</option>
                        <option value="image2image">图像生成图像</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="prompt">提示词:</label>
                    <textarea id="prompt" name="prompt" rows="4" placeholder="请输入图像生成的提示词"></textarea>
                </div>
                
                <div class="form-group" id="image-upload-group">
                    <label for="image">上传图片:</label>
                    <input type="file" id="image" name="image" accept=".png, .jpg, .jpeg, .gif">
                    <img id="image-preview" class="image-preview" src="" alt="预览图">
                </div>
                
                <div class="button-group">
                    <button type="submit" id="generate-button">生成图像</button>
                    <button type="button" id="cancel-button" disabled>取消</button>
                </div>
            </form>
            
            <div id="error-message"></div>
            
            <div id="progress-container">
                <div id="progress-bar"></div>
                <div id="progress-text">0%</div>
            </div>
            
            <div id="result-container">
                <h2>生成结果:</h2>
                <img id="result-image" src="" alt="生成的图像">
            </div>
        </div>
        
        <script>
            // 监听工作流类型变化
            document.getElementById('workflow-type').addEventListener('change', function() {
                const imageUploadGroup = document.getElementById('image-upload-group');
                if (this.value === 'image2image') {
                    imageUploadGroup.style.display = 'block';
                } else {
                    imageUploadGroup.style.display = 'none';
                    document.getElementById('image').value = '';
                    document.getElementById('image-preview').style.display = 'none';
                }
            });
            
            // 显示图片预览
            document.getElementById('image').addEventListener('change', function(e) {
                const preview = document.getElementById('image-preview');
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        preview.src = event.target.result;
                        preview.style.display = 'block';
                    };
                    reader.readAsDataURL(file);
                } else {
                    preview.style.display = 'none';
                }
            });
            
            let progressInterval;
            
            // 取消按钮事件
            document.getElementById('cancel-button').addEventListener('click', function() {
                if (progressInterval) {
                    clearInterval(progressInterval);
                    progressInterval = null;
                }
                document.getElementById('generate-button').disabled = false;
                document.getElementById('cancel-button').disabled = true;
                document.getElementById('progress-container').style.display = 'none';
            });
            
            // 表单提交事件
            document.getElementById('generation-form').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const workflowType = document.getElementById('workflow-type').value;
                const prompt = document.getElementById('prompt').value;
                const imageFile = document.getElementById('image').files[0];
                
                // 验证表单
                if (!prompt.trim()) {
                    showError('请输入提示词');
                    return;
                }
                
                if (workflowType === 'image2image' && !imageFile) {
                    showError('图像生成图像模式下必须上传图片');
                    return;
                }
                
                // 隐藏之前的结果和错误
                document.getElementById('result-container').style.display = 'none';
                document.getElementById('error-message').style.display = 'none';
                
                // 显示进度条
                document.getElementById('progress-container').style.display = 'block';
                document.getElementById('progress-bar').style.width = '0%';
                document.getElementById('progress-text').textContent = '0%';
                
                // 禁用生成按钮，启用取消按钮
                document.getElementById('generate-button').disabled = true;
                document.getElementById('cancel-button').disabled = false;
                
                // 准备表单数据
                const formData = new FormData();
                formData.append('workflow_type', workflowType);
                formData.append('prompt', prompt);
                
                if (imageFile) {
                    formData.append('image', imageFile);
                }
                
                // 提交表单
                fetch('/generate', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const promptId = data.prompt_id;
                        
                        // 轮询获取进度
                        progressInterval = setInterval(() => {
                            fetch(`/progress/${promptId}`)
                            .then(response => response.json())
                            .then(progressData => {
                                if (progressData.success) {
                                    const progress = Math.round(progressData.progress * 100);
                                    document.getElementById('progress-bar').style.width = `${progress}%`;
                                    document.getElementById('progress-text').textContent = `${progress}%`;
                                    
                                    if (progressData.completed) {
                                        clearInterval(progressInterval);
                                        progressInterval = null;
                                        
                                        // 获取生成的图像
                                        fetch(`/get_image/${promptId}`)
                                        .then(response => {
                                            if (response.ok) {
                                                return response.blob();
                                            } else {
                                                throw new Error('获取图像失败');
                                            }
                                        })
                                        .then(blob => {
                                            const imageUrl = URL.createObjectURL(blob);
                                            document.getElementById('result-image').src = imageUrl;
                                            document.getElementById('result-container').style.display = 'block';
                                            document.getElementById('generate-button').disabled = false;
                                            document.getElementById('cancel-button').disabled = true;
                                        })
                                        .catch(error => {
                                            showError('获取图像失败: ' + error.message);
                                            document.getElementById('generate-button').disabled = false;
                                            document.getElementById('cancel-button').disabled = true;
                                        });
                                    }
                                } else {
                                    clearInterval(progressInterval);
                                    progressInterval = null;
                                    showError('获取进度失败: ' + progressData.error);
                                    document.getElementById('generate-button').disabled = false;
                                    document.getElementById('cancel-button').disabled = true;
                                }
                            })
                            .catch(error => {
                                clearInterval(progressInterval);
                                progressInterval = null;
                                showError('获取进度失败: ' + error.message);
                                document.getElementById('generate-button').disabled = false;
                                document.getElementById('cancel-button').disabled = true;
                            });
                        }, 1000);
                    } else {
                        showError('生成失败: ' + data.error);
                        document.getElementById('generate-button').disabled = false;
                        document.getElementById('cancel-button').disabled = true;
                        document.getElementById('progress-container').style.display = 'none';
                    }
                })
                .catch(error => {
                    showError('请求失败: ' + error.message);
                    document.getElementById('generate-button').disabled = false;
                    document.getElementById('cancel-button').disabled = true;
                    document.getElementById('progress-container').style.display = 'none';
                });
            });
            
            // 显示错误信息
            function showError(message) {
                const errorElement = document.getElementById('error-message');
                errorElement.textContent = message;
                errorElement.style.display = 'block';
                
                // 5秒后自动隐藏错误信息
                setTimeout(() => {
                    errorElement.style.display = 'none';
                }, 5000);
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

# 生成图像的API端点
@app.route('/generate', methods=['POST'])
def generate():
    try:
        workflow_type = request.form.get('workflow_type', 'text2image')
        prompt = request.form.get('prompt')
        
        if not prompt:
            return jsonify({'success': False, 'error': '提示词是必需的'})
        
        image_path = None
        # 处理上传的图片
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(image_path)
            else:
                return jsonify({'success': False, 'error': '不支持的图片格式'})
        
        # 运行ComfyUI工作流
        result = run_comfyui_workflow(workflow_type, prompt, image_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 获取进度的API端点
@app.route('/progress/<prompt_id>')
def progress(prompt_id):
    return jsonify(get_progress(prompt_id))

# 获取生成图像的API端点
@app.route('/get_image/<prompt_id>')
def get_image(prompt_id):
    result = get_generated_image(prompt_id)
    if result['success']:
        return send_file(result['image_path'], mimetype='image/png')
    else:
        return jsonify(result), 400

# 随机模块用于生成种子
import random

if __name__ == '__main__':
    print("启动AI图像生成Web界面...")
    print(f"请确保ComfyUI服务已在 {app.config['COMFYUI_API_URL']} 启动")
    print("访问 http://localhost:5002 开始使用图像生成工具")
    app.run(host='0.0.0.0', port=5002, debug=True)