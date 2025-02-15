import requests
import os

# 服务器地址
SERVER_URL = "http://localhost:8091/api/files"

def upload_image(file_path):
    """上传图片到服务器"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return

    url = f"{SERVER_URL}/upload"
    files = {'file': open(file_path, 'rb')}

    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            data = response.json()
            print(f"上传成功: {data['message']}")
            print(f"文件名: {data['filename']}")
        else:
            print(f"上传失败: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"上传过程中发生错误: {e}")
    finally:
        files['file'].close()

def download_image(filename, save_path):
    """从服务器下载图片"""
    url = f"{SERVER_URL}/download/{filename}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, 'wb') as file:
                file.write(response.content)
            print(f"下载成功: 文件已保存到 {save_path}")
        else:
            print(f"下载失败: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"下载过程中发生错误: {e}")