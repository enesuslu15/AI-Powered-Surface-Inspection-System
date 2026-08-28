#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLOv8 Stitching Defect Training Script
=======================================
"""

import os
import argparse
from ultralytics import YOLO


def train_stitching(data_yaml, epochs=50, imgsz=640, batch=16, model_base="yolov8n.pt"):
    print("=" * 60)
    print("   YOLOv8 Kumas Dikis Hatasi Egitim Pipeline")
    print("=" * 60)

    if not os.path.exists(data_yaml):
        print(f"HATA: '{data_yaml}' bulunamadi!")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    runs_dir = os.path.join(project_root, "runs", "detect")

    model = YOLO(model_base)
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=runs_dir,
        name="stitching_inspection",
        exist_ok=True,
        patience=15
    )


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    default_yaml = os.path.join(project_root, "datasets", "stitchingnet_data.yaml")

    parser = argparse.ArgumentParser(description="Train YOLOv8 Stitching Model")
    parser.add_argument("--data", type=str, default=default_yaml, help="Path to stitchingnet_data.yaml")
    parser.add_argument("--epochs", type=int, default=50, help="Epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base weights")
    args = parser.parse_args()

    data_path = os.path.abspath(args.data)
    if not os.path.exists(data_path):
        alt = os.path.join(project_root, args.data)
        if os.path.exists(alt):
            data_path = alt

    train_stitching(data_path, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, model_base=args.model)


if __name__ == "__main__":
    main()

