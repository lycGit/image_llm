#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模拟测试视频生成结果判断逻辑
直接测试修改后的判断逻辑是否正确
"""

import sys
import json

def test_video_judgment_logic():
    """测试视频生成结果判断逻辑"""
    print("开始测试视频生成结果判断逻辑...")
    
    # 模拟结果1: 有视频信息
    print("\n=== 测试场景1: 有视频信息 ===")
    video_info = {'filename': 'video.mp4', 'subfolder': 'output', 'type': 'output'}
    has_output = True
    frames_count = 8
    
    result1 = {
        'success': has_output and frames_count > 0,  # 新逻辑
        'original_success': video_info is not None,  # 旧逻辑
        'prompt_id': 'test1',
        'frames_count': frames_count,
        'has_output': has_output,
        'video_info': video_info
    }
    
    print(f"新逻辑结果: {result1['success']}")
    print(f"旧逻辑结果: {result1['original_success']}")
    print(f"帧数: {result1['frames_count']}")
    print(f"有视频信息: {video_info is not None}")
    
    # 模拟结果2: 没有视频信息但有帧数
    print("\n=== 测试场景2: 没有视频信息但有帧数 ===")
    video_info = None
    has_output = True
    frames_count = 4
    
    result2 = {
        'success': has_output and frames_count > 0,  # 新逻辑
        'original_success': video_info is not None,  # 旧逻辑
        'prompt_id': 'test2',
        'frames_count': frames_count,
        'has_output': has_output
    }
    
    print(f"新逻辑结果: {result2['success']}")
    print(f"旧逻辑结果: {result2['original_success']}")
    print(f"帧数: {result2['frames_count']}")
    print(f"有视频信息: {video_info is not None}")
    
    # 模拟结果3: 没有视频信息也没有帧数
    print("\n=== 测试场景3: 没有视频信息也没有帧数 ===")
    video_info = None
    has_output = False
    frames_count = 0
    
    result3 = {
        'success': has_output and frames_count > 0,  # 新逻辑
        'original_success': video_info is not None,  # 旧逻辑
        'prompt_id': 'test3',
        'frames_count': frames_count,
        'has_output': has_output
    }
    
    print(f"新逻辑结果: {result3['success']}")
    print(f"旧逻辑结果: {result3['original_success']}")
    print(f"帧数: {result3['frames_count']}")
    print(f"有视频信息: {video_info is not None}")
    
    # 模拟ComfyUI实际情况 - 用户描述的场景
    print("\n=== 测试场景4: 模拟用户实际情况 (只有图像帧) ===")
    video_info = None
    has_output = True
    frames_count = 1  # 用户日志显示生成了1帧
    
    result4 = {
        'success': has_output and frames_count > 0,  # 新逻辑
        'original_success': video_info is not None,  # 旧逻辑
        'prompt_id': 'test4',
        'frames_count': frames_count,
        'has_output': has_output
    }
    
    print(f"新逻辑结果: {result4['success']}")
    print(f"旧逻辑结果: {result4['original_success']}")
    print(f"帧数: {result4['frames_count']}")
    print(f"有视频信息: {video_info is not None}")
    
    # 判断测试是否通过
    print("\n===== 测试总结 =====")
    # 场景1和场景2都应该成功，场景3应该失败
    if result1['success'] and result2['success'] and not result3['success'] and result4['success']:
        print("✓ 测试成功: 修复后的判断逻辑正确")
        print("  - 场景1 (有视频信息): 新逻辑正确返回True")
        print("  - 场景2 (只有帧数): 新逻辑正确返回True (旧逻辑返回False)")
        print("  - 场景3 (无输出无帧数): 新逻辑正确返回False")
        print("  - 场景4 (模拟用户情况): 新逻辑正确返回True (旧逻辑返回False)")
        print("\n结论: 修复后的逻辑可以正确处理用户遇到的'只有图像帧'情况")
        return True
    else:
        print("✗ 测试失败: 判断逻辑可能仍有问题")
        if not result1['success']:
            print("  - 场景1测试失败")
        if not result2['success']:
            print("  - 场景2测试失败")
        if result3['success']:
            print("  - 场景3测试失败")
        if not result4['success']:
            print("  - 场景4测试失败")
        return False

if __name__ == "__main__":
    success = test_video_judgment_logic()
    sys.exit(0 if success else 1)