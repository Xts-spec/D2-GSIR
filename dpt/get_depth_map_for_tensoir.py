import cv2
import torch

# import matplotlib.pyplot as plt
import utils_io

import numpy as np
import os
import argparse
import glob

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--root_path', type=str)
args = parser.parse_args()



model_type = "DPT_Large"     # MiDaS v3 - Large     (highest accuracy, slowest inference speed)
# model_type = "DPT_Hybrid"   # MiDaS v3 - Hybrid    (medium accuracy, medium inference speed)
# model_type = "MiDaS_small"  # MiDaS v2.1 - Small   (lowest accuracy, highest inference speed)
# model_type = "DPT_BEiT_L_384"

midas = torch.hub.load("intel-isl/MiDaS", model_type)
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
midas.to(device)
midas.eval()

midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")

if "DPT" in model_type:
    transform = midas_transforms.dpt_transform
else:
    transform = midas_transforms.small_transform

def get_all_train_test_folders(scene_path):#新增
    """获取某个scene下所有train_xxx和test_xxx文件夹"""
    train_folders = sorted(glob.glob(os.path.join(scene_path, "train_*")))
    test_folders = sorted(glob.glob(os.path.join(scene_path, "test_*")))
    return train_folders + test_folders  # 合并训练和测试文件夹


# 处理逻辑
if args.root_path[-1] != "/":
    root_path = args.root_path + '/'
else:
    root_path = args.root_path

# 获取root_path下的所有scene名称（每个scene是一个独立文件夹）
# scenes = [d for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
# scenes = ["lego"]
scenes = ["armadillo"]
print(f"发现场景: {scenes}")

downsampling = 1  # 深度图下采样倍数（保持原逻辑）

for scene_name in scenes:
    scene_path = os.path.join(root_path, scene_name)
    print(f"\n处理场景: {scene_path}")
    
    # 获取当前scene下所有train_xxx和test_xxx文件夹
    folders = get_all_train_test_folders(scene_path)
    if not folders:
        print(f"警告：场景{scene_name}下未找到train_xxx或test_xxx文件夹，跳过")
        continue
    
    for folder in folders:
        # 检查当前文件夹下是否存在rgba.png
        img_path = os.path.join(folder, "rgba.png")
        if not os.path.exists(img_path):
            print(f"警告：{folder}下未找到rgba.png，跳过")
            continue
        
        # 创建输出目录（当前文件夹下的depth_maps）
        output_dir = os.path.join(folder, "depth_maps")
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取并预处理图像
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # 转换为RGB格式
        h, w = img.shape[:2]
        print(f"处理图像: {img_path}，尺寸: ({h}, {w})")
        
        input_batch = transform(img).to(device)
        
        # 深度预测
        with torch.no_grad():
            prediction = midas(input_batch)
            # 下采样到原尺寸的1/downsampling
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=(h // downsampling, w // downsampling),
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        
        output = prediction.cpu().numpy()
        
        # 保存深度图（命名为depth_rgba.png及对应pfm文件）
        output_filename = os.path.join(output_dir, "depth_rgba")
        utils_io.write_depth(output_filename, output, bits=2)
        print(f"深度图已保存至: {output_dir}")