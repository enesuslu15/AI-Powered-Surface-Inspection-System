#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLOv8 Surface Defect Model Training Pipeline
==============================================
Fine-tunes YOLOv8 on MVTec AD surface defect dataset.
"""

import os
import argparse
from ultralytics import YOLO


def train_mvtec_yolo(data_yaml, epochs=50, imgsz=640, batch=16, model_base="yolov8n.pt"):
    """Trains YOLOv8 on the prepared MVTec dataset."""
    print("=" * 60)
    print("   YOLOv8 MVTec AD Yuzey Kusuru Egitim Boru Hatti")
    print("=" * 60)
    print(f"Veri Yapılandırması : {data_yaml}")
    print(f"Epok / Resim / Batch: {epochs} / {imgsz} / {batch}")
    print(f"Temel Model         : {model_base}")

    if not os.path.exists(data_yaml):
        print(f"\nHATA: '{data_yaml}' dosyası bulunamadı!")
        print("Lütfen önce 'python src/prepare_mvtec.py --category leather' komutunu çalıştırın.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    runs_dir = os.path.join(project_root, "runs", "detect")

    model = YOLO(model_base)

    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=runs_dir,
        name="mvtec_surface_inspection",
        exist_ok=True,
        patience=15
    )

    best_weights = os.path.join(runs_dir, "mvtec_surface_inspection", "weights", "best.pt")
    print("\n" + "=" * 60)
    print("EGITIM BASARIYLA TAMAMLANDI!")
    print(f"En Iyi Model Agirligi: {best_weights}")
    print("Sonuclari 'runs/detect/mvtec_surface_inspection/results.png' dosyasindan inceleyebilirsiniz.")
    print("=" * 60)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    default_yaml = os.path.join(project_root, "datasets", "mvtec_leather_data.yaml")

    parser = argparse.ArgumentParser(description="Train YOLOv8 on MVTec Dataset")
    parser.add_argument("--data", type=str, default=default_yaml, help="Path to data.yaml file")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=16, help="Training batch size")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base model weights")

    args = parser.parse_args()

    # Robust path resolution (handles relative and absolute paths without bug)
    data_path = os.path.abspath(args.data)
    if not os.path.exists(data_path):
        candidates = [
            os.path.join(project_root, args.data),
            os.path.join(project_root, "datasets", os.path.basename(args.data)),
            os.path.join(project_root, "Polteks_Project", os.path.basename(args.data)),
            os.path.join(project_root, "Polteks_Project", args.data)
        ]
        for c in candidates:
            if os.path.exists(c):
                data_path = c
                break

    train_mvtec_yolo(
        data_yaml=data_path,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        model_base=args.model
    )


if __name__ == "__main__":
    main()
