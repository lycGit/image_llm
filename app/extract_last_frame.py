import cv2
import os


def extract_last_frame(video_path, output_path=None):
    if not os.path.exists(video_path):
        print(f"视频文件不存在: {video_path}")
        return None
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return None
    
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames == 0:
            print("视频文件没有帧")
            return None
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
        
        ret, frame = cap.read()
        
        if not ret:
            print("无法读取最后一帧")
            return None
        
        if output_path is None:
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(video_dir, f"{video_name}_last_frame.jpg")
        
        success = cv2.imwrite(output_path, frame)
        
        if success:
            print(f"最后一帧已保存到: {output_path}")
            return output_path
        else:
            print(f"保存图片失败: {output_path}")
            return None
            
    except Exception as e:
        print(f"提取最后一帧时出错: {str(e)}")
        return None
    finally:
        cap.release()


def main():
    video_path = "/Users/lyc/Downloads/video_short.mp4"
    output_path = "/Users/lyc/Downloads/video_short_last.jpg"
    
    result = extract_last_frame(video_path, output_path)
    
    if result:
        print(f"成功！图片已保存到: {result}")
    else:
        print("失败！无法提取最后一帧")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        extract_last_frame(video_path, output_path)
    else:
        main()
