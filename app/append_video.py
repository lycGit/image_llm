import cv2
import os
import re


def extract_number_from_filename(filename):
    """
    从文件名中提取 episode 后面的数字部分
    
    参数:
        filename: 文件名
        
    返回:
        int: 提取的数字，如果没有数字则返回 999999
    """
    # 匹配 episode 后面的数字
    match = re.search(r'episode(\d+)', filename, re.IGNORECASE)
    
    if match:
        return int(match.group(1))
    else:
        # 如果没有找到 episode，尝试提取所有数字中的最后一个
        numbers = re.findall(r'\d+', filename)
        if numbers:
            return int(numbers[-1])
        else:
            return 999999


def get_video_files(directory):
    """
    获取目录中所有视频文件，并按文件名最后的数字排序
    
    参数:
        directory: 目录路径
        
    返回:
        list: 排序后的视频文件路径列表
    """
    video_files = []
    
    if not os.path.exists(directory):
        print(f"目录不存在: {directory}")
        return video_files
    
    # 支持的视频格式
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext in video_extensions:
                video_files.append(file_path)
    
    # 按文件名最后的数字排序
    video_files.sort(key=lambda x: extract_number_from_filename(os.path.basename(x)))
    
    return video_files


def get_video_properties(video_path):
    """
    获取视频的属性（分辨率、帧率等）
    
    参数:
        video_path: 视频文件路径
        
    返回:
        dict: 视频属性字典
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        return None
    
    properties = {
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        'fps': cap.get(cv2.CAP_PROP_FPS),
        'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    }
    
    cap.release()
    return properties


def append_videos(directory, output_path):
    """
    将目录中的所有视频文件按顺序拼接成一个视频
    
    参数:
        directory: 包含视频文件的目录
        output_path: 输出视频路径
        
    返回:
        bool: 成功返回 True，失败返回 False
    """
    # 获取所有视频文件
    video_files = get_video_files(directory)
    
    if not video_files:
        print(f"在目录 {directory} 中没有找到视频文件")
        return False
    
    print(f"找到 {len(video_files)} 个视频文件，按顺序拼接...")
    
    # 获取第一个视频的属性作为输出视频的属性
    first_video_props = get_video_properties(video_files[0])
    
    if not first_video_props:
        print("无法获取视频属性")
        return False
    
    # 创建输出视频写入器
    # 使用更兼容的 H.264 编码器
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(
        output_path,
        fourcc,
        first_video_props['fps'],
        (first_video_props['width'], first_video_props['height'])
    )
    
    if not out.isOpened():
        print("无法创建输出视频文件，尝试使用其他编码器...")
        # 如果 avc1 失败，尝试使用 H264
        fourcc = cv2.VideoWriter_fourcc(*'H264')
        out = cv2.VideoWriter(
            output_path,
            fourcc,
            first_video_props['fps'],
            (first_video_props['width'], first_video_props['height'])
        )
        
        if not out.isOpened():
            print("H264 编码器也失败，尝试使用 MJPG...")
            # 如果 H264 也失败，使用 MJPG
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            out = cv2.VideoWriter(
                output_path,
                fourcc,
                first_video_props['fps'],
                (first_video_props['width'], first_video_props['height'])
            )
            
            if not out.isOpened():
                print("无法创建输出视频文件")
                return False
    
    try:
        # 逐个读取视频并写入
        for i, video_path in enumerate(video_files, 1):
            filename = os.path.basename(video_path)
            print(f"[{i}/{len(video_files)}] 处理: {filename}")
            
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                print(f"  ✗ 无法打开视频: {filename}")
                continue
            
            # 读取每一帧并写入输出视频
            frame_count = 0
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # 如果分辨率不匹配，调整帧大小
                if frame.shape[1] != first_video_props['width'] or frame.shape[0] != first_video_props['height']:
                    frame = cv2.resize(frame, (first_video_props['width'], first_video_props['height']))
                
                out.write(frame)
                frame_count += 1
            
            print(f"  ✓ 已处理 {frame_count} 帧")
            cap.release()
        
        out.release()
        print(f"\n拼接完成！输出视频: {output_path}")
        return True
        
    except Exception as e:
        print(f"拼接视频时出错: {str(e)}")
        out.release()
        return False


def main():
    """
    主函数：示例用法
    """
    # 配置参数
    directory = "/Users/lyc/Desktop/shortplays/video"
    output_path = "/Users/lyc/Desktop/shortplays/result/merged_video.mp4"
    
    # 拼接视频
    success = append_videos(directory, output_path)
    
    if success:
        print("成功！")
    else:
        print("失败！")


if __name__ == '__main__':
    import sys
    
    # 如果通过命令行参数传入路径
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else "merged_video.mp4"
        append_videos(directory, output_path)
    else:
        main()
