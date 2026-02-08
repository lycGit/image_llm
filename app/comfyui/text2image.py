# 导入必要的库
import websocket
import uuid
import json
import urllib.request
import urllib.parse
from PIL import Image
import io
import os
import random
import base64
import requests

# 设置服务器地址和客户端
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())


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
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())


# 定义通过WebSocket接收消息并下载图像的函数
def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # 执行完成
        else:
            continue  # 预览是二进制数据

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images


# 上传图片到ComfyUI服务器
def upload_image(image_path):
    try:
        # 确保图片文件存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 使用表单数据方式上传图片
        url = f"http://{server_address}/upload/image"
        filename = os.path.basename(image_path)
        
        # 确保文件在上传前完全读取并关闭
        with open(image_path, "rb") as file:
            files = {'image': (filename, file.read())}
        
        response = requests.post(url, files=files)
        
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
        print(f"上传图片时HTTP错误: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"错误详情: {e.response.text}")
        raise
    except Exception as e:
        print(f"上传图片时出错: {str(e)}")
        raise


# 读取workflows文件夹下的工作流文件

def load_workflow_from_json(file_path, custom_prompt=None, negative_prompt=None, image_filename=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)
    
    # 创建提示对象（直接复制JSON内容）
    prompt = workflow_data.copy()
    
    # 处理提示语替换
    if custom_prompt:
        # 遍历所有节点
        for node_id, node in prompt.items():
            # 找到CLIPTextEncode节点
            if node['class_type'] == 'CLIPTextEncode':
                # 检查原始提示词内容
                original_text = node['inputs'].get('text', '')
                if 'watermark' in original_text or 'text' in original_text:
                    # 这是负面提示词节点，如果提供了自定义负面提示词则使用
                    if negative_prompt:
                        node['inputs']['text'] = negative_prompt
                else:
                    # 这是正面提示词节点，替换为自定义提示词
                    node['inputs']['text'] = custom_prompt
    
    # 处理参考图替换（仅当工作流包含LoadImage节点时）
    if image_filename:
        # 遍历所有节点
        for node_id, node in prompt.items():
            # 找到LoadImage节点
            if node['class_type'] == 'LoadImage':
                # 替换为上传的图片文件名
                node['inputs']['image'] = image_filename
    
    # 确保SaveImage节点有filename_prefix
    for node_id, node in prompt.items():
        if node['class_type'] == 'SaveImage' and 'filename_prefix' not in node['inputs']:
            node['inputs']['filename_prefix'] = "ComfyUI"
    
    return prompt


# 由外界传入提示词和图片URL生成图片的函数
def generate_image_from_url_and_prompt(prompt_text, image_url, workflow_path=None):
    """
    从给定的图片URL和提示词生成新图片
    
    参数:
        prompt_text (str): 提示词文本
        image_url (str): 图片的URL地址
        workflow_path (str, optional): 工作流文件路径，如果为None则使用默认路径
        
    返回:
        dict: 包含生成结果的字典
    """
    try:
        # 如果没有提供工作流路径，使用默认路径
        if workflow_path is None:
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'generate_image2.json')
            
        # 1. 从URL下载图片到临时文件
        print(f"正在从URL下载图片: {image_url}")
        temp_image_path = download_image_from_url(image_url)
        
        try:
            # 2. 上传图片到ComfyUI服务器
            image_filename = upload_image(temp_image_path)
            
            # 3. 使用提示词和上传的图片加载工作流
            prompt = load_workflow_from_json(workflow_path, custom_prompt=prompt_text, image_filename=image_filename)
            
            # 4. 创建WebSocket连接到服务器
            ws = websocket.create_connection(f"ws://{server_address}/ws?clientId={client_id}")
            
            # 5. 获取生成的图像
            images = get_images(ws, prompt)
            
            # 6. 处理生成的图像
            results = []
            for node_id in images:
                for image_data in images[node_id]:
                    image = Image.open(io.BytesIO(image_data))
                    # 7. 上传图像到远程服务器
                    upload_result = uploadImage(image)
                    results.append({
                        'image_data': image_data,
                        'upload_result': upload_result
                    })
            
            return {
                'success': True,
                'results': results,
                'message': '图片生成和上传成功'
            }
        finally:
            # 清理临时文件
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
    except Exception as e:
        print(f"图片生成过程中出错: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': '图片生成失败'
        }


# 由外界传入提示词生成图片的函数（纯文生图）
def generate_image_from_prompt(prompt_text, negative_prompt=None, workflow_path=None):
    """
    从给定的提示词生成新图片（纯文生图）
    
    参数:
        prompt_text (str): 提示词文本
        negative_prompt (str, optional): 负面提示词文本
        workflow_path (str, optional): 工作流文件路径，如果为None则使用默认路径
        
    返回:
        dict: 包含生成结果的字典
    """
    try:
        # 如果没有提供工作流路径，使用默认路径
        if workflow_path is None:
            workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'generate_image2.json')
            
        # 1. 使用提示词加载工作流
        prompt = load_workflow_from_json(workflow_path, custom_prompt=prompt_text, negative_prompt=negative_prompt)
        
        # 2. 创建WebSocket连接到服务器
        ws = websocket.create_connection(f"ws://{server_address}/ws?clientId={client_id}")
        
        # 3. 获取生成的图像
        images = get_images(ws, prompt)
        
        # 4. 处理生成的图像
        results = []
        for node_id in images:
            for image_data in images[node_id]:
                image = Image.open(io.BytesIO(image_data))
                # 5. 上传图像到远程服务器
                upload_result = uploadImage(image)
                results.append({
                    'image_data': image_data,
                    'upload_result': upload_result
                })
        
        return {
            'success': True,
            'results': results,
            'message': '图片生成和上传成功'
        }
    except Exception as e:
        print(f"图片生成过程中出错: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': '图片生成失败'
        }

# 辅助函数：从URL下载图片

def download_image_from_url(image_url):
    """
    从URL下载图片并保存到临时文件
    
    参数:
        image_url (str): 图片的URL地址
        
    返回:
        str: 临时文件的路径
    """
    import tempfile
    import urllib.request
    
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    temp_file_path = temp_file.name
    temp_file.close()
    
    # 下载图片到临时文件
    try:
        urllib.request.urlretrieve(image_url, temp_file_path)
        return temp_file_path
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise Exception(f"下载图片失败: {str(e)}")

# 修改现有的uploadImage函数，使其返回上传结果
def uploadImage(image):
    import tempfile
    
    # 保存 image 到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
        image.save(tmp_file)
        tmp_file_path = tmp_file.name
    
    # 确保文件在上传前完全读取并关闭
    file_data = None
    try:
        # 先读取文件内容到内存
        with open(tmp_file_path, 'rb') as file:
            file_data = file.read()
        
        # 此时文件已经关闭，不再持有文件句柄
        files = {'file': ('temp_image.png', file_data)}
        data = {
            'description': "自动生成的图片",
            'category': '',  # 可根据实际情况修改
            'tags': ''  # 可根据实际情况修改
        }
        
        response = requests.post('http://120.27.130.190:8091/api/files/upload', files=files, data=data)
        response.raise_for_status()
        result = response.json()
        print('文件上传成功，响应结果:', result)
        
        # 保存结果到文件
        with open('result.txt', 'w') as f:
            f.write(json.dumps(result))
            
        return result  # 返回上传结果
    except requests.RequestException as e:
        print(f'文件上传失败: {e}')
        return {'error': str(e)}
    finally:
        # 确保清理临时文件
        import os
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


def main():
    # 定义默认提示语
    default_prompt = "outdoor portrait photography, beautiful woman in natural setting, golden hour sunlight, dappled light through leaves, garden background with blooming flowers, wind-blown hair, natural makeup, joyful expression, cinematic lighting, high dynamic range, professional color grading"
    
    # 定义默认负面提示语
    default_negative_prompt = "text, watermark, low quality, blurry, distorted, ugly"
    
    # 加载workflow文件
    workflow_path = os.path.join(os.path.dirname(__file__), 'workflows', 'generate_image2.json')
    
    try:
        # 使用默认提示语加载工作流并生成图像
        result = generate_image_from_prompt(
            prompt_text=default_prompt,
            negative_prompt=default_negative_prompt,
            workflow_path=workflow_path
        )
        
        if result['success']:
            # 显示生成的图片
            for i, item in enumerate(result['results']):
                image_data = item['image_data']
                image = Image.open(io.BytesIO(image_data))
                image.show()
                print(f"图片 {i+1} 显示完成")
                input("按回车继续...")
        else:
            print(f"图片生成失败: {result['error']}")

    except Exception as e:
        print(f"程序执行出错: {str(e)}")


# 使用示例
def example_usage():
    # 提示词
    prompt = "beautiful scenery nature glass bottle landscape, purple galaxy bottle, intricate details, vibrant colors, 8K resolution"
    
    # 负面提示词
    negative_prompt = "text, watermark, low quality, blurry, distorted, ugly, noise"
    
    # 调用纯文本生图函数
    result = generate_image_from_prompt(prompt, negative_prompt)
    
    if result['success']:
        print("图片生成成功!")
        # 访问结果
        for i, item in enumerate(result['results']):
            print(f"结果 {i+1}: {item['upload_result']}")
    else:
        print(f"图片生成失败: {result['error']}")

if __name__ == "__main__":
    # main()
    example_usage()