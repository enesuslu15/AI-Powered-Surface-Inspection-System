#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVTec AD Dataset to YOLO Format Converter
==========================================
Converts MVTec Anomaly Detection dataset ground truth masks into normalized
YOLO format bounding boxes (class_id x_center y_center width height).
"""

import os
import cv2
import glob
import shutil
import random
import urllib.request
import tarfile
import argparse


def download_and_extract(url, extract_to):
    """Downloads and extracts the MVTec AD dataset archive."""
    os.makedirs(extract_to, exist_ok=True)
    filename = url.split('/')[-1]
    filepath = os.path.join(extract_to, filename)

    if not os.path.exists(filepath):
        print(f"[{filename}] indiriliyor... Bu işlem internet hızınıza bağlı olarak biraz vakit alabilir.")

        def report(count, block_size, total_size):
            percent = int(count * block_size * 100 / max(total_size, 1))
            print(f"\rİndiriliyor: %{percent} - {filepath}", end="")

        urllib.request.urlretrieve(url, filepath, reporthook=report)
        print("\nİndirme tamamlandı.")
    else:
        print(f"[{filename}] zaten mevcut, indirme atlandı.")

    folder_name = filename.split('.')[0]
    category_path = os.path.join(extract_to, folder_name)

    if not os.path.exists(category_path):
        print(f"[{filename}] çıkartılıyor...")
        with tarfile.open(filepath) as tar:
            tar.extractall(path=extract_to)
        print("Çıkarma işlemi tamamlandı.")
    else:
        print(f"[{folder_name}] klasörü zaten mevcut, çıkarma atlandı.")


def create_yolo_directories(base_dir):
    """Creates the standard YOLO dataset directory hierarchy."""
    dirs = [
        os.path.join(base_dir, "images", "train"),
        os.path.join(base_dir, "images", "val"),
        os.path.join(base_dir, "labels", "train"),
        os.path.join(base_dir, "labels", "val")
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def process_mvtec_category(category_path, yolo_dir, split_ratio=0.8):
    """Converts MVTec anomaly ground truth masks to YOLO bounding box format."""
    class_id = 0  # 0: Defect
    dataset_items = []

    # 1. Train Good images (No defects)
    train_good_dir = os.path.join(category_path, "train", "good")
    if os.path.exists(train_good_dir):
        for img_path in glob.glob(os.path.join(train_good_dir, "*.png")):
            dataset_items.append({
                "img": img_path,
                "mask": None,
                "is_defect": False
            })

    # 2. Test images (Good and various Defect categories)
    test_dir = os.path.join(category_path, "test")
    gt_dir = os.path.join(category_path, "ground_truth")

    if os.path.exists(test_dir):
        for defect_type in os.listdir(test_dir):
            defect_img_dir = os.path.join(test_dir, defect_type)
            if not os.path.isdir(defect_img_dir):
                continue

            for img_path in glob.glob(os.path.join(defect_img_dir, "*.png")):
                img_name = os.path.basename(img_path)

                if defect_type == "good":
                    dataset_items.append({
                        "img": img_path,
                        "mask": None,
                        "is_defect": False
                    })
                else:
                    mask_name = img_name.replace(".png", "_mask.png")
                    mask_path = os.path.join(gt_dir, defect_type, mask_name)
                    if os.path.exists(mask_path):
                        dataset_items.append({
                            "img": img_path,
                            "mask": mask_path,
                            "is_defect": True
                        })
                    else:
                        print(f"Uyarı: Maske dosyası bulunamadı: {mask_path}")

    # Shuffle and split
    random.seed(42)
    random.shuffle(dataset_items)

    split_index = int(len(dataset_items) * split_ratio)
    train_items = dataset_items[:split_index]
    val_items = dataset_items[split_index:]

    def process_split(items, split_name):
        print(f"--> {split_name} veri seti oluşturuluyor ({len(items)} görsel)...")
        for idx, item in enumerate(items):
            img_path = item["img"]
            mask_path = item["mask"]

            base_name = f"{split_name}_{idx:04d}"
            dest_img = os.path.join(yolo_dir, "images", split_name, f"{base_name}.png")
            dest_txt = os.path.join(yolo_dir, "labels", split_name, f"{base_name}.txt")

            shutil.copy(img_path, dest_img)

            with open(dest_txt, "w") as f:
                if item["is_defect"] and mask_path:
                    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
                    if mask is not None:
                        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        img_h, img_w = mask.shape
                        for cnt in contours:
                            x, y, w, h = cv2.boundingRect(cnt)
                            if w < 5 or h < 5:
                                continue  # Ignore microscopic noise

                            x_center = (x + w / 2.0) / img_w
                            y_center = (y + h / 2.0) / img_h
                            n_w = w / float(img_w)
                            n_h = h / float(img_h)

                            f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {n_w:.6f} {n_h:.6f}\n")

    process_split(train_items, "train")
    process_split(val_items, "val")
    print(f"Veri seti YOLO formatına dönüştürüldü! Çıkış dizini: {yolo_dir}")


def main():
    parser = argparse.ArgumentParser(description="MVTec to YOLO format converter")
    parser.add_argument("--category", type=str, default="leather", help="MVTec category to process (e.g. leather, wood)")
    parser.add_argument("--split", type=float, default=0.8, help="Train/Val split ratio (default: 0.8)")
    args = parser.parse_args()

    category = args.category
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    mvtec_base = os.path.join(project_root, "mvtec_anomaly_detection")
    if not os.path.exists(os.path.join(mvtec_base, category)):
        alt_mvtec = os.path.join(project_root, "Polteks_Project", "mvtec_anomaly_detection")
        if os.path.exists(os.path.join(alt_mvtec, category)):
            mvtec_base = alt_mvtec

    yolo_base = os.path.join(project_root, "datasets", f"mvtec_{category}_yolo")
    category_path = os.path.join(mvtec_base, category)

    if not os.path.exists(category_path):
        print(f"HATA: '{category_path}' klasörü bulunamadı!")
        print(f"\nLütfen MVTec AD veri setinden '{category}' kategorisini indirin:")
        print("İndirme linki: https://www.mvtec.com/company/research/datasets/mvtec-ad")
        print(f"İndirilen arşivi {os.path.abspath(mvtec_base)} dizinine '{category}' adıyla çıkartınız.\n")
        return

    create_yolo_directories(yolo_base)
    print(f"MVTec ({category}) -> YOLO dönüşümü başlatılıyor...")
    process_mvtec_category(category_path, yolo_base, split_ratio=args.split)

    # Generate YOLO YAML config
    yaml_path = os.path.join(project_root, "datasets", f"mvtec_{category}_data.yaml")
    yaml_content = f"""path: {os.path.abspath(yolo_base)}
train: images/train
val: images/val
test:

names:
  0: defect
"""
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"Eğitim yapılandırması oluşturuldu: {yaml_path}")


if __name__ == "__main__":
    main()
