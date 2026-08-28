# 🔍 AI-Powered Surface Inspection System — System Specification

---

## 1. Executive Summary

To automate and digitize quality control in industrial roller and calender machine manufacturing, this project implements a high-speed, edge-capable **AI-Powered Surface Inspection System**.

The system detects anomalies and surface flaws (scratches, holes, stitching issues, stains) in real-time using deep learning (YOLOv8) and communicates decision codes **directly to Siemens S7-1200 / S7-1500 PLCs** over the native S7 Communication protocol (via Snap7), eliminating the need for complex middleware or OPC UA licensing.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  [Industrial Camera / RTSP Feed]                             │
│       │                                                      │
│       ▼                                                      │
│  [PC / Edge Python Server]  ──── S7 Protocol (Snap7) ──►  [PLC]│
│   YOLOv8 Real-Time Inference                         S7-1200 │
│   Defect Snapshot & CSV Logger                       TIA V17 │
│       │                                                  │   │
│       ▼                                                  ▼   │
│  [Real-Time OSD Display]                         [Tower Lamp]│
│  Defect type + confidence + motor status         OK / FAULT  │
└──────────────────────────────────────────────────────────────┘
```

### Layer 1 — Vision & AI Engine
- **Framework:** Ultralytics YOLOv8 (Nano / Custom fine-tuned weights)
- **Dataset:** MVTec Anomaly Detection (Leather & Industrial Surfaces)
- **Features:** Real-time bounding box extraction, confidence thresholding, defect image logging (`defects/` folder) with timestamps.

### Layer 2 — Industrial Communication (Snap7 / S7 Protocol)
- Direct memory block read/write (`DB_AI_Communication` DB1)
- State-change optimization to reduce network bandwidth and PLC cycle overhead.
- Automatic reconnection engine on link failure.
- Handshake & latching logic for fault acknowledge and motor restart pulses.

### Layer 3 — PLC Automation & Machine Control (TIA Portal V17)
- **FB_Machine_Control:** Instantaneous motor contactor cutoff (`%Q0.0`) on `AI_Result_Code = 2`.
- **Analog Output (%QW96):** 0-10V / 27648 speed reference control for inverter drives.
- **Safety Interlock:** Latching fault memory prevents automatic restart until operator reset.

---

## 3. Memory Mapping (DB_AI_Communication - DB1)

| Offset | Variable Name | Data Type | Description |
|--------|---------------|-----------|-------------|
| `0.0` | `AI_Result_Code` | `Int` | `0`: Idle, `1`: OK (Pass), `2`: NOK (Defect Found) |
| `2.0` | `Defect_Type` | `Int` | `0`: None, `1`: Surface Defect (or 1..5 for Stitching) |
| `4.0` | `Restart_Cmd` | `Int` | `0`: Normal, `1`: Restart Request from Python UI |

---

## 4. Performance Metrics

| Metric | Measured / Projected Value |
|--------|----------------------------|
| Inference Latency (YOLOv8n GPU/CPU) | **15 - 35 ms** |
| PLC Communication Latency (Snap7 Ethernet) | **< 5 ms** |
| Total Detection-to-Action Response Time | **< 50 ms** (Sub-second emergency stop) |
| Model Accuracy (MVTec Leather) | **79.7% mAP50** |

