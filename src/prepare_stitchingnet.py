#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StitchingNet Dataset Preparation for YOLOv8
============================================
Converts raw fabric stitching defect images into YOLO format.
"""

import os
import cv2
import glob
import shutil
import random
import argparse

DEFECT_CLASSES = {
    "skipped_stitch": 0,
    "broken_stitch": 1,
    "crooked_seam": 2,
    "thread_sagging": 3,
    "needle_damage": 4
}


def apply_clahe_enhancement(img_path, output_path):
    img = cv2.imread(img_path)
    if img is None:
        return False
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    merged = cv2.merge((cl, a, b))
    enhanced_img = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    cv2.imwrite(output_path, enhanced_img)
    return True


def create_yolo_directories(yolo_dir):
    subdirs = [
        "images/train", "images/val", "images/test",
        "labels/train", "labels/val", "labels/test"
    ]
    for sub in subdirs:
        os.makedirs(os.path.join(yolo_dir, sub), exist_ok=True)


def process_and_convert_dataset(raw_dir, yolo_dir, split_ratio=0.8, use_clahe=False):
    create_yolo_directories(yolo_dir)
    print(f"\n--- Veri Isleme Basliyor -> {raw_dir} ---")

    image_extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff")
    all_images = []
    for ext in image_extensions:
        all_images.extend(glob.glob(os.path.join(raw_dir, "**", ext), recursive=True))

    if not all_images:
        print(f"HATA: '{raw_dir}' icinde gorsel bulunamadi!")
        return False

    print(f"Toplam {len(all_images)} ham gorsel tespit edildi.")
    random.seed(42)
    random.shuffle(all_images)

    split_idx = int(len(all_images) * split_ratio)
    train_imgs = all_images[:split_idx]
    val_imgs = all_images[split_idx:]

    def process_split(img_list, split_name):
        for idx, img_path in enumerate(img_list):
            ext = os.path.splitext(img_path)[1]
            new_filename = f"stitch_{split_name}_{idx:05d}"
            dest_img = os.path.join(yolo_dir, "images", split_name, f"{new_filename}{ext}")
            dest_lbl = os.path.join(yolo_dir, "labels", split_name, f"{new_filename}.txt")

            if use_clahe:
                if not apply_clahe_enhancement(img_path, dest_img):
                    shutil.copy(img_path, dest_img)
            else:
                shutil.copy(img_path, dest_img)

            # Check if matching label exists
            txt_partner = os.path.splitext(img_path)[0] + ".txt"
            if os.path.exists(txt_partner):
                shutil.copy(txt_partner, dest_lbl)
            else:
                open(dest_lbl, "w").close()

    process_split(train_imgs, "train")
    process_split(val_imgs, "val")
    return True


def generate_yaml_config(output_yaml_path, yolo_dir):
    clean_yolo_dir = os.path.abspath(yolo_dir).replace("\\", "/")
    content = f"""path: {clean_yolo_dir}
train: images/train
val: images/val
test: images/test

names:
  0: skipped_stitch
  1: broken_stitch
  2: crooked_seam
  3: thread_sagging
  4: needle_damage
"""
    with open(output_yaml_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"YAML konfigürasyonu oluşturuldu: {output_yaml_path}")


def main():
    parser = argparse.ArgumentParser(description="Stitching Dataset Preparer")
    parser.add_argument("--clahe", action="store_true", help="Apply CLAHE filter")
    parser.add_argument("--raw-dir", type=str, default="datasets/stitchingnet", help="Raw data directory")
    parser.add_argument("--output-dir", type=str, default="datasets/stitchingnet_yolo", help="YOLO output dir")
    parser.add_argument("--split-ratio", type=float, default=0.8, help="Train/val split ratio")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    raw_path = os.path.join(project_root, args.raw_dir)
    yolo_path = os.path.join(project_root, args.output_dir)
    yaml_path = os.path.join(project_root, "datasets", "stitchingnet_data.yaml")

    if os.path.exists(raw_path):
        process_and_convert_dataset(raw_path, yolo_path, split_ratio=args.split_ratio, use_clahe=args.clahe)
    generate_yaml_config(yaml_path, yolo_path)


if __name__ == "__main__":
    main()

