#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polteks AI Surface Inspection System (MVTec AD & YOLOv8)
=========================================================
Real-time defect detection and Siemens S7-1200/1500 PLC integration.

Features:
- YOLOv8 inference for industrial surface defect detection.
- S7 communication via Snap7 (Auto-reconnect, state-change writing).
- Latching fault memory & Motor Restart command handshake.
- Defect snapshot recording & CSV logging for traceability.
- Interactive keyboard controls: [Q] Quit, [R] Motor Restart, [S] Test Defect.
"""

import os
import sys
import time
import argparse
import logging
import csv
from datetime import datetime
import cv2
import snap7
from snap7.util import set_int, get_int
from ultralytics import YOLO

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SurfaceInspectionAI")

# PLC DB Offsets (Matching TIA Portal DB_AI_Communication)
OFFSET_RESULT = 0   # Int @ Byte 0 -> 0: Idle, 1: OK (Clean), 2: NOK (Defect)
OFFSET_DEFECT = 2   # Int @ Byte 2 -> Defect Type ID (1: Surface Defect)
OFFSET_RESTART = 4  # Int @ Byte 4 -> Restart Command (0: Idle, 1: Request Restart)


class PLCController:
    """Manages Siemens S7 PLC communication with reconnection and safe writes."""

    def __init__(self, ip="192.168.1.20", rack=0, slot=1, db_number=1, mock_mode=False):
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.db_number = db_number
        self.mock_mode = mock_mode
        self.client = None
        self.connected = False
        self.last_reconnect_attempt = 0
        self.last_written_state = None  # (result_code, defect_type, restart_cmd)

        if not self.mock_mode:
            self.connect()

    def connect(self):
        """Attempts to establish connection to the Siemens PLC."""
        if self.mock_mode:
            return False

        try:
            self.client = snap7.client.Client()
            self.client.connect(self.ip, self.rack, self.slot)
            self.connected = self.client.get_connected()

            if self.connected:
                logger.info(f"Connected to Siemens S7 PLC at {self.ip} (Rack: {self.rack}, Slot: {self.slot})")
                # Verification read
                try:
                    data = self.client.db_read(self.db_number, 0, 6)
                    logger.info(f"PLC DB{self.db_number} read test OK: {list(data)}")
                except Exception as read_err:
                    logger.warning(f"DB{self.db_number} read test failed (Check PUT/GET permission): {read_err}")
                return True
        except Exception as err:
            logger.warning(f"Could not connect to PLC at {self.ip}: {err}")
            self.connected = False
            self.client = None
            return False

    def check_connection(self):
        """Checks and reconnects if connection was lost."""
        if self.mock_mode:
            return False

        if self.client and self.client.get_connected():
            self.connected = True
            return True

        self.connected = False
        current_time = time.time()
        # Retry connection every 5 seconds
        if current_time - self.last_reconnect_attempt > 5.0:
            self.last_reconnect_attempt = current_time
            logger.info(f"Attempting to reconnect to PLC ({self.ip})...")
            return self.connect()
        return False

    def write_result(self, result_code: int, defect_type: int = 0, force: bool = False):
        """Writes AI result to PLC DB if state changed or forced."""
        new_state = (result_code, defect_type, 0)
        if not force and self.last_written_state == new_state:
            return  # Avoid redundant network traffic

        if not self.check_connection():
            return

        try:
            data = bytearray(6)
            set_int(data, OFFSET_RESULT, result_code)
            set_int(data, OFFSET_DEFECT, defect_type)
            set_int(data, OFFSET_RESTART, 0)
            self.client.db_write(self.db_number, 0, data)
            self.last_written_state = new_state
        except Exception as err:
            logger.error(f"PLC write error: {err}")
            self.connected = False

    def send_restart(self):
        """Sends motor restart pulse to PLC DB."""
        if not self.check_connection():
            logger.info("[MOCK] Motor Restart signal triggered in simulation.")
            return

        try:
            data = bytearray(6)
            set_int(data, OFFSET_RESULT, 0)
            set_int(data, OFFSET_DEFECT, 0)
            set_int(data, OFFSET_RESTART, 1)
            self.client.db_write(self.db_number, 0, data)
            self.last_written_state = (0, 0, 1)
            logger.info(">>> RESTART command successfully sent to PLC!")
        except Exception as err:
            logger.error(f"PLC Restart command write error: {err}")
            self.connected = False

    def disconnect(self):
        """Disconnects the Snap7 client safely."""
        if self.client and self.connected:
            try:
                self.client.disconnect()
                logger.info("PLC disconnected safely.")
            except Exception:
                pass


def find_model_weights(custom_path=None):
    """Finds best available YOLO model weights from potential locations."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    # Potential search paths in order of preference
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    search_paths = [
        os.path.join(project_root, "weights", "best.pt"),
        os.path.join(project_root, "Polteks_Project", "mvtec_surface_inspection", "weights", "best.pt"),
        os.path.join(project_root, "mvtec_surface_inspection", "weights", "best.pt"),
        os.path.join(project_root, "runs", "detect", "mvtec_surface_inspection", "weights", "best.pt"),
        os.path.join(project_root, "Polteks_Project", "yolov8n.pt"),
        os.path.join(project_root, "weights", "yolov8n.pt"),
        os.path.join(project_root, "yolov8n.pt"),
        "yolov8n.pt"
    ]

    for path in search_paths:
        if os.path.exists(path):
            return path

    return "yolov8n.pt"


def save_defect_snapshot(frame, defect_info, output_dir="defects"):
    """Saves defect snapshot image and logs details to CSV."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    img_filename = f"defect_{timestamp_str}.jpg"
    img_path = os.path.join(output_dir, img_filename)
    cv2.imwrite(img_path, frame)

    csv_path = os.path.join(output_dir, "defect_log.csv")
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Image File", "Defect Type", "Confidence", "Boxes Count"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            img_filename,
            defect_info.get("type", "Surface Defect"),
            f"{defect_info.get('conf', 0.0):.2f}",
            defect_info.get("count", 1)
        ])


def draw_hud(frame, motor_stopped, defect_detected, fps, plc_controller, conf_val=0.0):
    """Renders professional Heads-Up Display (HUD) overlay on the video feed."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    # Top Status Bar
    bar_height = 80
    bg_color = (0, 0, 140) if motor_stopped else (0, 100, 0)
    cv2.rectangle(overlay, (0, 0), (w, bar_height), bg_color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Status Borders
    border_color = (0, 0, 255) if motor_stopped else (0, 255, 0)
    border_thickness = 8 if motor_stopped else 4
    cv2.rectangle(frame, (2, 2), (w - 2, h - 2), border_color, border_thickness)

    # Status Texts
    if motor_stopped:
        status_text = "HATA: YUZEY KUSURU TESPIT EDILDI -> MOTOR DURDU!"
        sub_text = "DIKKAT: Hata Kilidi Aktif. Motoru Yeniden Baslatmak Icin [R] Tusuna Basin."
    else:
        status_text = "URUN SAGLAM - HURA YOK -> MOTOR CALISIYOR"
        sub_text = f"Gercek Zamanli AI Denetimi Aktif | FPS: {fps:.1f} | Guven: {conf_val:.2f}"

    cv2.putText(frame, status_text, (20, 35), cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 2)
    cv2.putText(frame, sub_text, (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)

    # Bottom Status Bar
    cv2.rectangle(frame, (0, h - 35), (w, h), (25, 25, 25), -1)
    plc_status = f"PLC: {plc_controller.ip} (Bagli)" if plc_controller.connected else "PLC: BAGLANTI YOK (Simulasyon)"
    controls_hint = "[R] Restart  [S] Hata Simule Et  [Q] Cikis"
    cv2.putText(frame, f"{plc_status} | {controls_hint}", (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1)

    return frame


def parse_args():
    parser = argparse.ArgumentParser(description="Polteks AI Surface Inspection System")
    parser.add_argument("--source", type=str, default="0", help="Camera index (e.g. 0) or video file path")
    parser.add_argument("--weights", type=str, default=None, help="Path to trained YOLOv8 model weights (.pt)")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold for defect detection")
    parser.add_argument("--ip", type=str, default="192.168.1.20", help="Siemens S7 PLC IP Address")
    parser.add_argument("--rack", type=int, default=0, help="PLC Rack Number (default: 0)")
    parser.add_argument("--slot", type=int, default=1, help="PLC Slot Number (default: 1 for S7-1200/1500)")
    parser.add_argument("--db", type=int, default=1, help="TIA Portal DB Number (default: 1)")
    parser.add_argument("--mock-plc", action="store_true", help="Run without physical PLC connection")
    parser.add_argument("--save-defects", action="store_true", default=True, help="Save defect snapshots and CSV log")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 65)
    print("   POLTEKS AI - YUZEY KUSUR DENETIMI VE PLC ENTEGRASYONU")
    print("=" * 65)

    # PLC Controller Init
    plc = PLCController(
        ip=args.ip,
        rack=args.rack,
        slot=args.slot,
        db_number=args.db,
        mock_mode=args.mock_plc
    )

    # YOLO Model Loading
    weights_path = find_model_weights(args.weights)
    logger.info(f"Loading YOLO Model Weights: {weights_path}")
    try:
        model = YOLO(weights_path)
    except Exception as e:
        logger.error(f"Failed to load model from {weights_path}: {e}")
        logger.info("Falling back to standard yolov8n.pt")
        model = YOLO("yolov8n.pt")

    # Video Capture Source
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error(f"Could not open video source: {args.source}")
        return

    print("\nKontroller:")
    print("  [Q] -> Programdan Cikis")
    print("  [R] -> Motor RESTART (Hata sonrasi sistemi yeniden baslat)")
    print("  [S] -> Hata SIMULASYONU (Kusursuz test amacli yapay arıza tetikle)")
    print("-" * 65)

    motor_stopped_by_fault = False
    simulated_defect_active = False
    prev_time = time.time()
    last_defect_saved_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.info("Video feed ended or camera disconnected.")
            break

        current_time = time.time()
        fps = 1.0 / max(current_time - prev_time, 0.001)
        prev_time = current_time

        # YOLO Inference
        results = model(frame, conf=args.conf, verbose=False)
        result = results[0]

        has_defect = (len(result.boxes) > 0) or simulated_defect_active
        best_conf = 0.0

        if has_defect:
            if len(result.boxes) > 0:
                best_box = max(result.boxes, key=lambda b: b.conf[0])
                best_conf = float(best_box.conf[0].item())
            else:
                best_conf = 0.99

            if not motor_stopped_by_fault:
                motor_stopped_by_fault = True
                logger.warning(f"!!! YUZEY KUSURU TESPIT EDILDI (Guven: {best_conf:.2f}) -> MOTOR DURDURULDU !!!")

                # Save defect image & CSV log (rate limited to 1 per 2 seconds)
                if args.save_defects and (current_time - last_defect_saved_time > 2.0):
                    last_defect_saved_time = current_time
                    annotated_snapshot = result.plot() if len(result.boxes) > 0 else frame
                    save_defect_snapshot(annotated_snapshot, {
                        "type": "Surface Defect (MVTec)",
                        "conf": best_conf,
                        "count": len(result.boxes) or 1
                    })
                    logger.info("Kusurlu urun gorseli ve CSV kaydi 'defects/' dizinine kaydedildi.")

            display_frame = result.plot() if len(result.boxes) > 0 else frame
        else:
            display_frame = frame

        # PLC Communication
        if motor_stopped_by_fault:
            # Keep sending NOK (2) until operator resets with [R]
            plc.write_result(result_code=2, defect_type=1)
        else:
            # Send OK (1)
            plc.write_result(result_code=1, defect_type=0)

        # Render HUD Overlay
        output_frame = draw_hud(
            display_frame,
            motor_stopped=motor_stopped_by_fault,
            defect_detected=has_defect,
            fps=fps,
            plc_controller=plc,
            conf_val=best_conf
        )

        cv2.imshow("Polteks AI - Yuzey Kusur Denetim Sistemi", output_frame)

        # OpenCV GUI Events & Keyboard Handling (Placed after imshow for smooth rendering)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), ord('Q')):
            logger.info("Operator exited the program.")
            break

        elif key in (ord('r'), ord('R')):
            if motor_stopped_by_fault:
                plc.send_restart()
                motor_stopped_by_fault = False
                simulated_defect_active = False
                logger.info(">>> RESTART KOMUTU ILETILDI -> Motor Yeniden Calisiyor.")
            else:
                print("(Aktif hata yok, restart gerekmez.)")

        elif key in (ord('s'), ord('S')):
            if not motor_stopped_by_fault:
                simulated_defect_active = True
                logger.warning("[SIMULASYON] Test amacli yapay yuzey kusuru tetiklendi!")

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    plc.disconnect()


if __name__ == "__main__":
    main()
