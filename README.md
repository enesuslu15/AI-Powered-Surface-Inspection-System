# 🔍 AI-Powered Surface Inspection System 

---

## 1. Executive Summary

This proposal introduces an **"Image Processing-Based Surface Inspection System."**

The system detects defects on manufactured rollers using AI, communicates those results **directly to the Siemens PLC infrastructure**, and manages production in real time — without manual operator intervention.

---

## 2. Problem Statement

Current quality control relies entirely on operator attention, which introduces:

| Risk | Impact |
|------|--------|
| Eye fatigue → missed defects | Defective products reaching customers |
| No historical data logging | Root-cause analysis is impossible |
| Inconsistent inspection speed | Quality variance between operators / shifts |

---

## 3. Proposed Solution

An automated inspection station using high-resolution industrial cameras and AI algorithms.

### 3.1 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  [Industrial Camera]                                         │
│       │                                                      │
│       ▼                                                      │
│  [PC / Python Server]  ──── S7 Protocol (Snap7) ────►  [PLC]│
│   YOLOv8 / OpenCV                                    S7-1200 │
│   Defect Classification                              TIA V17 │
│       │                                                  │   │
│       ▼                                                  ▼   │
│  [HMI Display]                                   [Tower Lamp]│
│  Defect type + location                          OK / FAULT  │
└──────────────────────────────────────────────────────────────┘
```

**Layer 1 — Vision (PC/Server):**
- Python analyzes the moving product image using open-source libraries
- Classifies defects: scratch, hole, stain

**Layer 2 — Communication (S7 Protocol via Snap7):**
- The PC communicates with the PLC using Siemens's native **S7 Communication** protocol
- The Python software writes the analysis result (OK / NOK) **directly into PLC memory (Data Block)** — faster and more reliable than Modbus

**Layer 3 — Action (PLC — TIA Portal):**
- When `STATUS = FAULT(2)`, the PLC brings the machine to a safe stop
- Defect type is displayed on the HMI panel
- Audible/visual tower lamp alerts the operator

### 3.2 Prototype Approach (Color-Based Detection)
As a proof-of-concept for AI integration, the prototype uses **color-based defect detection**:

- **RED (Defect):** If high red intensity is detected, the system classifies it as "Surface Defect" → sends stop signal to PLC → **Red light** activates
- **GREEN (OK):** No defect → production continues → **Green light** active

---

## 4. Technical Specifications

| Component | Specification |
|-----------|--------------|
| PLC | Siemens S7-1200 / S7-1500 Series |
| PLC Software | TIA Portal V16/V17 (SCL + Ladder) |
| Vision Language | Python 3.9 (OpenCV, `python-snap7`, NumPy) |
| AI Model | YOLOv8 (planned upgrade from color-based PoC) |
| Protocol | S7 Communication — Ethernet/TCP Direct Put/Get |

---

## 5. Expected Benefits

| Benefit | Details |
|---------|---------|
| **Near-Zero Defect Escape** | ~100% quality assurance on outbound products |
| **Efficiency** | Early defect detection prevents raw material and time waste |
| **Data-Driven** | Every defect is logged with timestamp and image for traceability |

---

## 6. Project Timeline

| Week | Milestone | Status |
|------|-----------|--------|
| 1 | System design and simulation | ✅ Done |
| 2 | TIA Portal SCL programming | ✅ Done |
| 3 | Physical PLC + Snap7 integration | ✅ Done |
| 4 | Final testing and presentation | ✅ Done |

---

## 7. Performance Projections

| Metric | Value |
|--------|-------|
| Total response time (camera → PLC signal) | **< 100 ms** |
| Prototype detection accuracy (color/contrast) | **~99.9%** (for visible defects) |
| Deep learning model accuracy (planned) | **> 95%** (micro-scratches + complex textures) |
| PLC reaction time (trigger → machine stop) | **< 10 ms** (within one PLC scan cycle) |
| Communication stability | Direct DB memory access via Snap7 — no middleware delays |

---

## 8. Roadmap

| Priority | Feature |
|----------|---------|
| 🔴 High | Replace color PoC with trained YOLOv8 model on real defect dataset |
| 🟡 Medium | Add defect image archiving (timestamp + crop saved to disk) |
| 🟡 Medium | Integrate with MES/SCADA for production analytics |
| 🟢 Low | Multi-camera head for wider inspection coverage |
| 🟢 Low | Edge deployment (Raspberry Pi / Jetson Nano) to eliminate PC dependency |

---

