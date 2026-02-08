import requests
from typing import Optional

class FileUploader:
    def __init__(self, upload_url: str = "http://localhost:8091/api/files/upload"):
        self.upload_url = upload_url

    def upload_file(self, file_path: str) -> Optional[str]:
        """
        上传文件到指定服务器
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 如果上传成功返回服务器响应，失败返回 None
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(self.upload_url, files=files)
                response.raise_for_status()
                return response.text
        except Exception as e:
            print(f"上传文件失败: {str(e)}")
            return None