#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polteks AI Fabric Stitching Inspection System (Experimental Module)
====================================================================
5-Class Fabric Stitching Defect Detection with S7-1200 PLC Integration.

Defect Classes:
- 0: Normal / Solid Stitching (OK)
- 1: Skipped Stitching (Atlamalı Dikiş)
- 2: Broken Stitching (Kopuk Dikiş)
- 3: Crooked Stitching (Eğri Dikiş)
- 4: Loose Thread / Sagging (Gevşek İplik)
- 5: Needle Damage (İğne Hasarı)
"""

import os
import sys
import time
import argparse
import logging
import random
import csv
from datetime import datetime
import cv2
import snap7
from snap7.util import set_int
from ultralytics import YOLO

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("StitchingAI")

# PLC Offsets
OFFSET_RESULT = 0   # Int @ Byte 0 -> 1: OK, 2: NOK
OFFSET_DEFECT = 2   # Int @ Byte 2 -> Defect Class ID (1..5)
OFFSET_RESTART = 4  # Int @ Byte 4 -> Restart Command (1: Restart)

DEFECT_INFO = {
    0: {"name": "NORMAL / SAGLAM DIKIS", "plc_id": 0, "color": (0, 255, 0), "bg": (0, 80, 0)},
    1: {"name": "1: ATLAMALI DIKIS (Skipped)", "plc_id": 1, "color": (255, 0, 255), "bg": (80, 0, 80)},
    2: {"name": "2: KOPUK DIKIS (Broken)", "plc_id": 2, "color": (0, 0, 255), "bg": (0, 0, 80)},
    3: {"name": "3: EGRI DIKIS (Crooked)", "plc_id": 3, "color": (0, 140, 255), "bg": (0, 40, 80)},
    4: {"name": "4: GEVSEK IPLIK (Sagging)", "plc_id": 4, "color": (255, 255, 0), "bg": (80, 80, 0)},
    5: {"name": "5: IGNE HASARI (Needle/Other)", "plc_id": 5, "color": (0, 255, 255), "bg": (0, 80, 80)}
}


class StitchingPLCController:
    """Handles S7-1200 communication for stitching quality control."""

    def __init__(self, ip="192.168.1.20", rack=0, slot=1, db_number=1, mock_mode=False):
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.db_number = db_number
        self.mock_mode = mock_mode
        self.client = None
        self.connected = False
        self.last_written = None

        if not self.mock_mode:
            self.connect()

    def connect(self):
        if self.mock_mode:
            return False
        try:
            self.client = snap7.client.Client()
            self.client.connect(self.ip, self.rack, self.slot)
            self.connected = self.client.get_connected()
            if self.connected:
                logger.info(f"Connected to Stitching PLC ({self.ip}) DB{self.db_number}")
            return self.connected
        except Exception as e:
            logger.warning(f"PLC connection failed: {e}")
            self.connected = False
            return False

    def write_defect(self, result_code, defect_type):
        new_state = (result_code, defect_type)
        if self.last_written == new_state:
            return

        if not self.mock_mode and self.client and self.client.get_connected():
            try:
                data = bytearray(6)
                set_int(data, OFFSET_RESULT, result_code)
                set_int(data, OFFSET_DEFECT, defect_type)
                set_int(data, OFFSET_RESTART, 0)
                self.client.db_write(self.db_number, 0, data)
                self.last_written = new_state
            except Exception as e:
                logger.error(f"PLC write error: {e}")
        elif self.mock_mode:
            self.last_written = new_state

    def send_restart(self):
        if not self.mock_mode and self.client and self.client.get_connected():
            try:
                data = bytearray(6)
                set_int(data, OFFSET_RESULT, 0)
                set_int(data, OFFSET_DEFECT, 0)
                set_int(data, OFFSET_RESTART, 1)
                self.client.db_write(self.db_number, 0, data)
                self.last_written = (0, 0)
                logger.info(">>> RESTART sent to PLC!")
            except Exception as e:
                logger.error(f"PLC restart error: {e}")
        else:
            logger.info("[MOCK] Stitching Motor Restart pulse sent.")

    def disconnect(self):
        if self.client and self.connected:
            try:
                self.client.disconnect()
            except Exception:
                pass


def draw_osd(frame, is_fault, defect_id, fps, motor_stopped, plc_controller):
    h, w, _ = frame.shape
    info = DEFECT_INFO.get(defect_id, DEFECT_INFO[0])
    main_color = info["color"]
    bg_color = info["bg"]

    border_thickness = 8 if motor_stopped else 4
    cv2.rectangle(frame, (4, 4), (w - 4, h - 4), main_color, border_thickness)

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 100), bg_color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.rectangle(frame, (0, 100), (w, 102), main_color, 2)

    if not motor_stopped:
        title_str = f"URUN: {info['name']} -> MOTOR CALISIYOR"
        sub_str = f"Canli Izleme Aktif | FPS: {fps:.1f} | [S]: Hata Simule Et  [Q]: Cikis"
    else:
        title_str = f"HATA KILIDI AKTIF: {info['name']} -> MOTOR DURDU!"
        sub_str = "DIKKAT: Hat Durduruldu. Sifirlamak ve Baslatmak Icin [R] Tusuna Basin."

    cv2.putText(frame, title_str, (20, 40), cv2.FONT_HERSHEY_DUPLEX, 0.75, main_color, 2)
    cv2.putText(frame, sub_str, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)

    cv2.rectangle(frame, (0, h - 35), (w, h), (25, 25, 25), -1)
    status_text = f"PLC: {plc_controller.ip} | Defect Type sent: {info['plc_id']} | [R] Restart [S] Test Hatasi [Q] Cikis"
    cv2.putText(frame, status_text, (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1)

    return frame


def parse_args():
    parser = argparse.ArgumentParser(description="Polteks AI Fabric Stitching Inspection System")
    parser.add_argument("--source", type=str, default="0", help="Camera index or video file")
    parser.add_argument("--weights", type=str, default=None, help="Trained model path (.pt)")
    parser.add_argument("--ip", type=str, default="192.168.1.20", help="PLC IP address")
    parser.add_argument("--mock-plc", action="store_true", help="Run in simulation mode without physical PLC")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("   POLTEKS AI - KUMAS DIKIS HATA ANALIZI VE KALITE KONTROL")
    print("=" * 70)

    plc = StitchingPLCController(ip=args.ip, mock_mode=args.mock_plc)

    # Model Search
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    model_paths = [
        args.weights if args.weights else "",
        os.path.join(project_root, "weights", "stitching_best.pt"),
        os.path.join(project_root, "weights", "best.pt"),
        os.path.join(project_root, "runs", "detect", "stitching_inspection", "weights", "best.pt"),
        os.path.join(project_root, "weights", "yolov8n.pt"),
        "yolov8n.pt"
    ]

    chosen_model = next((p for p in model_paths if p and os.path.exists(p)), "yolov8n.pt")
    logger.info(f"Loading Stitching Model: {chosen_model}")
    model = YOLO(chosen_model)

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error(f"Could not open camera/video source: {args.source}")
        return

    motor_stopped_by_fault = False
    latched_defect_id = 0
    simulated_defect_trigger = False
    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()
        fps = 1.0 / max(current_time - prev_time, 0.001)
        prev_time = current_time

        # Model Inference
        results = model(frame, verbose=False)
        result = results[0]

        if len(result.boxes) > 0 and not simulated_defect_trigger:
            best_box = max(result.boxes, key=lambda b: b.conf[0])
            yolo_class = int(best_box.cls[0].item())
            detected_defect_id = min(max(yolo_class + 1, 1), 5)

            if not motor_stopped_by_fault:
                motor_stopped_by_fault = True
                latched_defect_id = detected_defect_id
                logger.warning(f"!!! DIKIS KUSURU TESPIT EDILDI: {DEFECT_INFO[latched_defect_id]['name']} -> MOTOR DURDURULDU !!!")

            display_frame = result.plot()
        else:
            display_frame = frame

        # PLC Handling
        if motor_stopped_by_fault:
            active_defect = latched_defect_id if latched_defect_id != 0 else 1
            plc.write_defect(result_code=2, defect_type=active_defect)
            frame_to_show = draw_osd(display_frame, is_fault=True, defect_id=active_defect, fps=fps, motor_stopped=True, plc_controller=plc)
        else:
            plc.write_defect(result_code=1, defect_type=0)
            frame_to_show = draw_osd(display_frame, is_fault=False, defect_id=0, fps=fps, motor_stopped=False, plc_controller=plc)

        cv2.imshow("Polteks AI - Kumas Dikis Kalite Kontrol Sistemi", frame_to_show)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q')):
            break
        elif key in (ord('r'), ord('R')):
            if motor_stopped_by_fault:
                plc.send_restart()
                motor_stopped_by_fault = False
                latched_defect_id = 0
                simulated_defect_trigger = False
                logger.info(">>> RESTART: Arıza kilidi kaldırıldı, motor başlatıldı.")
        elif key in (ord('s'), ord('S')):
            if not motor_stopped_by_fault:
                simulated_defect_trigger = True
                sim_class = random.randint(1, 5)
                latched_defect_id = sim_class
                motor_stopped_by_fault = True
                logger.warning(f"[SIMULASYON] Test Kusuru Tetiklendi -> {DEFECT_INFO[sim_class]['name']}")

    cap.release()
    cv2.destroyAllWindows()
    plc.disconnect()


if __name__ == "__main__":
    main()

