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

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['COMFYUI_API_URL'] = 'http://localhost:8188'

# 创建上传目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 将图像转换为base64
def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# 执行ComfyUI工作流
def run_comfyui_workflow(workflow_path, prompt, image_path=None):
    try:
        # 读取工作流JSON文件
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        # 更新工作流中的提示词
        for node_id, node_data in workflow.items():
            if 'inputs' in node_data and 'prompt' in node_data['inputs']:
                node_data['inputs']['prompt'] = prompt
            # 如果有图像输入且提供了图像，更新图像输入
            if image_path and 'inputs' in node_data and 'image' in node_data['inputs']:
                node_data['inputs']['image'] = image_to_base64(image_path)
        
        # 创建任务ID
        task_id = str(uuid.uuid4())
        
        # 发送工作流到ComfyUI API
        response = requests.post(
            f"{app.config['COMFYUI_API_URL']}/prompt",
            json={'prompt': workflow, 'client_id': task_id}
        )
        
        if response.status_code == 200:
            prompt_id = response.json()['prompt_id']
            return {'success': True, 'prompt_id': prompt_id, 'task_id': task_id}
        else:
            return {'success': False, 'error': f"ComfyUI API error: {response.text}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# 获取生成进度
def get_progress(prompt_id):
    try:
        response = requests.get(f"{app.config['COMFYUI_API_URL']}/prompt/{prompt_id}")
        if response.status_code == 200:
            data = response.json()
            if 'progress' in data:
                return {'success': True, 'progress': data['progress'], 'completed': data['status'] == 'completed'}
            else:
                return {'success': True, 'progress': 0, 'completed': False}
        return {'success': False, 'error': f"API error: {response.text}"}
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
            return {'success': False, 'error': "No image found in generation results"}
        return {'success': False, 'error': f"API error: {response.text}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# 主页面
def index():
    html = '''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ComfyUI 图像生成工具</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { text-align: center; }
            form { margin-bottom: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; }
            input[type="text"], textarea, input[type="file"] { width: 100%; padding: 8px; box-sizing: border-box; }
            button { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
            button:hover { background-color: #45a049; }
            #progress-container { margin-top: 20px; width: 100%; background-color: #f1f1f1; border-radius: 5px; display: none; }
            #progress-bar { width: 0%; height: 30px; background-color: #4CAF50; text-align: center; line-height: 30px; color: white; border-radius: 5px; }
            #result-container { margin-top: 20px; display: none; }
            #result-image { max-width: 100%; height: auto; }
            #error-message { color: red; margin-top: 10px; display: none; }
        </style>
    </head>
    <body>
        <h1>ComfyUI 图像生成工具</h1>
        
        <form id="generation-form">
            <div class="form-group">
                <label for="workflow-path">工作流文件路径:</label>
                <input type="text" id="workflow-path" name="workflow_path" placeholder="输入工作流JSON文件路径" value="workflow.json">
            </div>
            
            <div class="form-group">
                <label for="prompt">提示词:</label>
                <textarea id="prompt" name="prompt" rows="4" placeholder="请输入图像生成的提示词"></textarea>
            </div>
            
            <div class="form-group">
                <label for="image">上传图片 (可选):</label>
                <input type="file" id="image" name="image">
            </div>
            
            <button type="submit">生成图像</button>
        </form>
        
        <div id="error-message"></div>
        
        <div id="progress-container">
            <div id="progress-bar">0%</div>
        </div>
        
        <div id="result-container">
            <h2>生成结果:</h2>
            <img id="result-image" src="" alt="生成的图像">
        </div>
        
        <script>
            document.getElementById('generation-form').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = new FormData();
                formData.append('workflow_path', document.getElementById('workflow-path').value);
                formData.append('prompt', document.getElementById('prompt').value);
                
                const imageFile = document.getElementById('image').files[0];
                if (imageFile) {
                    formData.append('image', imageFile);
                }
                
                // 隐藏之前的结果和错误
                document.getElementById('result-container').style.display = 'none';
                document.getElementById('error-message').style.display = 'none';
                
                // 显示进度条
                document.getElementById('progress-container').style.display = 'block';
                document.getElementById('progress-bar').style.width = '0%';
                document.getElementById('progress-bar').textContent = '0%';
                
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
                        const checkProgress = setInterval(() => {
                            fetch(`/progress/${promptId}`)
                            .then(response => response.json())
                            .then(progressData => {
                                if (progressData.success) {
                                    const progress = Math.round(progressData.progress * 100);
                                    document.getElementById('progress-bar').style.width = `${progress}%`;
                                    document.getElementById('progress-bar').textContent = `${progress}%`;
                                    
                                    if (progressData.completed) {
                                        clearInterval(checkProgress);
                                        // 获取生成的图像
                                        fetch(`/get_image/${promptId}`)
                                        .then(response => response.blob())
                                        .then(blob => {
                                            const imageUrl = URL.createObjectURL(blob);
                                            document.getElementById('result-image').src = imageUrl;
                                            document.getElementById('result-container').style.display = 'block';
                                        })
                                        .catch(error => {
                                            document.getElementById('error-message').textContent = '获取图像失败: ' + error;
                                            document.getElementById('error-message').style.display = 'block';
                                        });
                                    }
                                } else {
                                    clearInterval(checkProgress);
                                    document.getElementById('error-message').textContent = '获取进度失败: ' + progressData.error;
                                    document.getElementById('error-message').style.display = 'block';
                                }
                            })
                            .catch(error => {
                                clearInterval(checkProgress);
                                document.getElementById('error-message').textContent = '获取进度失败: ' + error;
                                document.getElementById('error-message').style.display = 'block';
                            });
                        }, 1000);
                    } else {
                        document.getElementById('error-message').textContent = '生成失败: ' + data.error;
                        document.getElementById('error-message').style.display = 'block';
                        document.getElementById('progress-container').style.display = 'none';
                    }
                })
                .catch(error => {
                    document.getElementById('error-message').textContent = '请求失败: ' + error;
                    document.getElementById('error-message').style.display = 'block';
                    document.getElementById('progress-container').style.display = 'none';
                });
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

# 生成图像的API端点
@app.route('/generate', methods=['POST'])
def generate():
    try:
        workflow_path = request.form.get('workflow_path')
        prompt = request.form.get('prompt')
        
        if not workflow_path or not prompt:
            return jsonify({'success': False, 'error': '工作流路径和提示词是必需的'})
        
        # 检查工作流文件是否存在
        if not os.path.exists(workflow_path):
            # 尝试在comfyui目录下查找
            comfyui_workflow_path = os.path.join(os.path.dirname(__file__), workflow_path)
            if not os.path.exists(comfyui_workflow_path):
                return jsonify({'success': False, 'error': f'工作流文件不存在: {workflow_path}'})
            workflow_path = comfyui_workflow_path
        
        image_path = None
        # 处理上传的图片
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(image_path)
        
        # 运行ComfyUI工作流
        result = run_comfyui_workflow(workflow_path, prompt, image_path)
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

# 设置路由
app.add_url_rule('/', 'index', index)

if __name__ == '__main__':
    print("启动ComfyUI Web界面...")
    print("请确保ComfyUI服务已在 http://localhost:8188 启动")
    app.run(host='0.0.0.0', port=5002, debug=True)