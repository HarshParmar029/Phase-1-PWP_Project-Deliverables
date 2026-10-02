<div align="center">

# 🛡️ Tourist Safety Monitoring & Incident Response System
### using AI, Geo-Fencing and Blockchain-based Digital ID

**PWP – Programming with Python · Phase 1 Project Deliverables**
*Smart India Hackathon (SIH) Problem Statement*

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web%20API%20%26%20Dashboard-000000?logo=flask)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Isolation%20Forest-F7931E?logo=scikitlearn&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Incident%20Log-003B57?logo=sqlite&logoColor=white)
![Folium](https://img.shields.io/badge/Folium-Live%20Map-77B829)
![Status](https://img.shields.io/badge/Phase%201-Core%20Prototype%20(~60%25)-success)

**Marwadi University · Faculty of Engineering & Technology · B.Tech ICT · Rajkot, Gujarat**

🔗 **Repository:** [HarshParmar029/Phase-1-PWP_Project-Deliverables](https://github.com/HarshParmar029/Phase-1-PWP_Project-Deliverables)

</div>

---

## 📌 Table of Contents

1. [Project Overview](#-project-overview)
2. [Academic Details](#-academic-details)
3. [Problem Statement](#-problem-statement)
4. [Objectives & Results](#-objectives--results)
5. [Research Questions](#-research-questions)
6. [Key Features](#-key-features)
7. [System Architecture](#-system-architecture-five-layer-workflow)
8. [Algorithms & Models](#-algorithms--models)
9. [Tech Stack](#-tech-stack)
10. [Dataset](#-dataset--input-synthetic)
11. [Modules & Source Files](#-modules--source-files)
12. [Quick Start](#-quick-start)
13. [Evaluation Results](#-evaluation-results)
14. [Literature Review & Research Gap](#-literature-review--research-gap)
15. [Limitations](#-limitations)
16. [Roadmap – Phase 2](#-roadmap--phase-2-40-remaining)
17. [Submission Checklist](#-phase-1-submission-checklist)
18. [References](#-references)
19. [Credits](#-credits)

---

## 🌍 Project Overview

Tourists in unfamiliar, crowded or remote destinations face accidents, theft, harassment, medical emergencies and the risk of straying into unsafe or restricted zones. Existing safety arrangements rely on manual phone calls and fragmented channels, and panic-button / SOS apps react **only after** the tourist triggers them.

This project designs and prototypes **one integrated, proactive system** that:

- 📍 continuously monitors a tourist's location against **safe, caution and restricted zones** (geo-fencing),
- 🤖 uses **AI anomaly detection** to flag route deviation and prolonged inactivity *without any action from the tourist*,
- 🔐 issues a **tamper-evident, time-bound Digital Tourist ID** (SHA-256 hash chain + QR code) that stores **no raw passport number**,
- 🚨 automatically creates **severity-graded incidents** with live location and measured latency,
- 🖥️ shows everything on a live **authority dashboard**.

> All four components run together in a **single Python pipeline** and are **quantitatively evaluated** on labelled synthetic trajectories.

---

## 🎓 Academic Details

| Field | Details |
|---|---|
| **Subject** | PWP – Programming with Python |
| **Programme** | B.Tech – Information and Communication Technology (ICT) |
| **Class / Batch** | 3EK1-A · Batch 2025–2029 · Semester 3 |
| **Project Group No.** | 2 |
| **Submitted To** | Kawal Preet Kaur |
| **Submission** | Phase 1 – Problem Statement, Objectives, Research Questions, Previous Work, Research Gap, Methodology and Prototype |
| **Date** | September 2026 |
| **University** | Marwadi University, Rajkot, Gujarat |

**Registered group members (as per submission):**

| Sr. | Name | Enrollment No. | Class |
|---|---|---|---|
| 1 | Harsh Parmar | 92500133012 | 3EK1-A |
| 2 | Kakshil Adeshara | 92500133056 | 3EK1-A |

---

## ❗ Problem Statement

> There is no single, integrated system that continuously monitors a tourist's location against risk zones, uses artificial intelligence to detect abnormal behaviour or distress early, provides a tamper-proof and verifiable digital identity, and automatically alerts authorities and emergency contacts with live location. This project aims to design and prototype such a system.

**Who is affected?**

- **Tourists (domestic & international)** – especially solo travellers, women, senior citizens and visitors to remote or high-risk areas.
- **Families & emergency contacts** – uncertainty about whereabouts and wellbeing.
- **Police, tourism departments & emergency responders** – delayed, incomplete, unverified information slows response.
- **Tourism industry & local economy** – perceived lack of safety reduces traveller confidence.

**Why it is worth solving**

- Every minute of delay between an incident and first response reduces the chance of a good outcome.
- Proactive detection can *prevent* incidents rather than only respond to them.
- Paper/photo identity is easy to forge; a hash-chained, time-bound ID gives tamper evidence while limiting personal-data exposure.
- It is a Smart India Hackathon challenge, indicating national relevance, and combines AI, geospatial computing and blockchain.

---

## 🎯 Objectives & Results

| ID | Objective | Target | Result (synthetic tests) |
|---|---|---|---|
| **O1** | Geo-fencing engine for safe / caution / restricted zones with entry/exit detection | Detect within 5 s; 100% correct on test polygons | ✅ **100.0%** accuracy, precision, recall |
| **O2** | AI anomaly detection (location loss, prolonged inactivity, route deviation) | ≥ 90% detection, ≤ 10% false alerts | ✅ Met at **episode level** (100.0% episodes, 0.0% false alerts on normal walks). ⚠️ Window-level recall **0.84** is below 90% |
| **O3** | Blockchain-based, time-bound digital tourist ID | Tampering detected 100%; verification < 3 s | ✅ **100.0%** tamper detection; **0.63 ms** avg verification |
| **O4** | Automated incident-response workflow with live location | Alert with coordinates ≤ 10 s | ✅ **23 ms** (95th percentile) – *server-side processing only* |
| **O5** | Authority dashboard + end-to-end evaluation | All O1–O4 in one prototype | ✅ All modules run together on the dashboard |

---

## ❓ Research Questions

1. **RQ1** – How can geo-fencing and AI anomaly detection be combined in a single pipeline so a risk is identified *before* the tourist reports an incident?
2. **RQ2** – Can a hybrid of interpretable rules and an unsupervised ML model detect route deviation and prolonged inactivity with high precision and a low false-alarm rate on GPS trajectories?
3. **RQ3** – How can a lightweight, blockchain-inspired Digital Tourist ID (SHA-256 hash chain + QR) provide tamper-evident, quickly verifiable identity without storing raw personal identifiers?
4. **RQ4** – What alert latency can an automated pipeline achieve from receiving a location update to logging an incident, compared with manual reporting?
5. **RQ5** – Does fusing rules with an Isolation Forest reduce false alerts compared with the ML model alone, and reduce detection delay compared with rules alone?

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🆔 **Digital Tourist ID** | Time-bound ID with SHA-256 payload hash, hash-chained ledger, salted passport hash and QR code |
| ✅ **ID Verification** | Checks record existence, payload hash, full chain integrity and expiry |
| 🗺️ **Haversine Geo-Fencing** | Safe zone + restricted zones; edge-triggered `GEOFENCE_VIOLATION` (HIGH) and `LEFT_SAFE_ZONE` (LOW) |
| 🤖 **Hybrid Anomaly Detection** | Interpretable rules + Isolation Forest + spatial corroboration check |
| 🆘 **Manual SOS** | Creates a CRITICAL incident instantly |
| 📝 **Incident Logger** | Severity-graded incidents with type, location, time and measured latency in SQLite |
| 🖥️ **Authority Dashboard** | Live map, zones, planned route, incident markers, incident table and statistics, auto-refreshed |
| 🧪 **Simulator + Evaluator** | Synthetic labelled trajectories, metrics and charts |
| 🔒 **Privacy by design** | Raw passport number is **never stored** – only a salted SHA-256 hash |

---

## 🏗️ System Architecture (Five-Layer Workflow)

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1 · REGISTRATION LAYER                                  │
│ Name, nationality, passport no., emergency contact           │
│ → Digital ID module issues time-bound ID + QR code           │
└───────────────────────────────┬──────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 2 · TRACKING LAYER                                      │
│ Tourist device (simulated in Phase 1) sends GPS fix          │
│ (lat, lon, timestamp) every 30 seconds to the location API   │
└───────────────────────────────┬──────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 3 · ANALYSIS LAYER                                      │
│ Fix validated against ID ledger → Haversine geo-fence check  │
│ → appended to sliding window → anomaly detector              │
└───────────────────────────────┬──────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 4 · RESPONSE LAYER                                      │
│ Geo-fence violation / anomaly / manual SOS                   │
│ → severity-graded incident + location + latency → SQLite     │
└───────────────────────────────┬──────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 5 · PRESENTATION LAYER                                  │
│ Authority dashboard: live positions, zones, planned route,   │
│ incident markers and incident table (auto-refresh)           │
└──────────────────────────────────────────────────────────────┘
```

### Detailed processing steps

1. Tourist submits registration; passport number is salted and hashed.
2. Digital Tourist ID is generated; payload hashed with SHA-256, appended to the hash-chained ledger; QR code created.
3. Authorities verify the ID (record, hash, chain, expiry) via endpoint or QR code.
4. GPS fixes (simulated) are sent to the location API every 30 s with the tourist ID.
5. Each fix is accepted only if the ID is valid and unexpired, then stored.
6. Haversine engine evaluates the fix and generates zone entry/exit events.
7. Fix is added to the sliding window; features go to the rule layer and Isolation Forest.
8. Hybrid decision is made; duplicate alerts of the same active type are suppressed.
9. Incident with type, severity, location and latency is written to the incident log.
10. Dashboard displays the map marker, incident row and statistics within a few seconds.

---

## 🧠 Algorithms & Models

### (a) Blockchain-inspired Digital Tourist ID (SHA-256 + QR)

The ID payload (tourist ID, name, nationality, salted passport hash, emergency contact, validity period) is serialised as canonical JSON and hashed with SHA-256. Each ID is a block in a hash-chained ledger:

```
block_hash = SHA-256( index | payload_hash | previous_block_hash | timestamp | nonce )
```

Because every block contains the previous block's hash, changing any stored record or ledger entry **breaks the chain** and is detected. The QR code encodes the tourist ID, a hash prefix and a verification URL.

**Verification checks:** (i) record exists, (ii) recomputed payload hash equals ledger hash, (iii) whole chain intact, (iv) ID not expired.

> ⚠️ *Blockchain-inspired*: provides tamper evidence on a **single trusted node**, **not** distributed consensus.

### (b) Geo-Fencing – Haversine Formula

```
a = sin²(Δφ/2) + cos φ₁ · cos φ₂ · sin²(Δλ/2)
d = 2R · arcsin(√a),      R = 6,371,008.8 m
```

A fix is inside a circular zone if `d ≤ zone radius`. Events are **edge-triggered**: `GEOFENCE_VIOLATION` (HIGH) on entering a restricted zone, `LEFT_SAFE_ZONE` (LOW) on leaving the safe zone. The implementation was cross-checked against the `geopy` library.

### (c) AI Anomaly Detection – Route Deviation + Prolonged Inactivity

A sliding window of the **last 10 fixes (5 minutes)** is converted into **six features**: mean and max distance from the planned route, mean speed, net displacement, path length and heading variance.

| Layer | Logic |
|---|---|
| **Rule layer (interpretable)** | `ROUTE_DEVIATION` if the last 3 fixes are all > **250 m** from the planned route. `PROLONGED_INACTIVITY` if net displacement over a full window is < **20 m** and the tourist is not near a designated rest point |
| **ML layer** | **Isolation Forest** (scikit-learn, 100 trees, contamination 0.01) trained **only on normal trajectories** – needs no labelled anomalies |
| **Hybrid decision** | Alert if a rule fires, **or** if the Isolation Forest flags an outlier **and** max route deviation in the window exceeds **120 m** (corroboration added after experiments showed the model alone raised false alerts when tourists paused normally) |

---

## 🧰 Tech Stack

| Component | Library / Tool | Purpose |
|---|---|---|
| Hashing | `hashlib` | SHA-256 for payload hash, block hash, salted passport hash |
| QR code | `qrcode` (Pillow) | Digital ID QR with ID, hash prefix, verification URL |
| Distance / validation | `math`, `geopy` | Haversine implementation and cross-check |
| Machine learning | `scikit-learn`, `numpy`, `joblib` | Isolation Forest training, scoring, model storage |
| Data handling | `pandas`, `numpy` | Trajectory features and evaluation |
| Web / API | `Flask` | Registration, location API, verification, dashboard (FastAPI is an alternative) |
| Mapping | `folium` | Live map with zones, route, tourists, incidents |
| Database | `SQLite (sqlite3)` | Tourists, ledger, locations, incidents |
| Evaluation | `matplotlib`, `scikit-learn.metrics` | Metrics and charts |
| Diagram | `draw.io` | Methodology flowchart |

---

## 📊 Dataset / Input (Synthetic)

Phase 1 uses **synthetic data** generated by the simulator module so ground-truth labels are known exactly.

- **GPS trajectories:** a tourist walks a planned route near **Somnath, Gujarat** at ~**1.2 m/s**, one fix every **30 s**, Gaussian GPS noise (**σ = 6 m**), with random short pauses in normal walks.
- **Four scenarios:** `normal` · `route deviation` (~500 m perpendicular drift) · `prolonged inactivity` (~7 min without movement) · `geo-fence violation` (walk into a restricted zone).
- **Tourist profile data:** name, nationality, passport number (stored only as salted hash), emergency contact, ID validity period.
- **Zones & route:** 1 safe zone, 2 restricted zones, 5-waypoint itinerary in the config file (approximate coordinates, simulation only).
- **Split:** Isolation Forest trained on **150 normal trajectories (15,327 windows)**; testing uses separate random seeds.

> Validation on real trajectory datasets is planned for the next phase.

---

## 🗂️ Modules & Source Files

| Module | Status | What was implemented | Source file(s) |
|---|---|---|---|
| Digital Tourist ID + QR | ✅ Completed | SHA-256 payload hash, hash-chained ledger, salted passport hash, QR code, tamper & expiry verification | `digital_id.py` |
| Geo-fencing engine | ✅ Completed | Haversine distance, safe & restricted zones, edge-triggered events | `geofence.py` |
| AI anomaly detection | ✅ Completed (prototype) | Route-deviation & inactivity rules, Isolation Forest, hybrid decision, model training | `anomaly.py`, `train_model.py` |
| Incident logging + dashboard | ✅ Completed (basic) | SQLite incident log, severity levels, Flask dashboard with live map and demo buttons | `engine.py`, `app.py`, `database.py` |
| Simulation + evaluation | ✅ Completed | Synthetic trajectory generator, metrics and charts | `simulator.py`, `evaluate.py` |
| End-to-end prototype | 🎬 Ready for demo | Registration → tracking → alert → dashboard | `app.py` |

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/HarshParmar029/Phase-1-PWP_Project-Deliverables.git
cd Phase-1-PWP_Project-Deliverables

# 2. (Recommended) create a virtual environment
python -m venv venv
# Windows: venv\Scripts\activate      |  macOS/Linux: source venv/bin/activate

# 3. Install dependencies
pip install flask scikit-learn numpy pandas joblib folium qrcode pillow geopy matplotlib

# 4. Train the Isolation Forest on normal trajectories
python train_model.py

# 5. (Optional) reproduce the evaluation results
python evaluate.py

# 6. Run the web app (registration, Digital ID, authority dashboard)
python app.py
```

Then open the local URL printed in the terminal (Flask default: `http://127.0.0.1:5000`).

**Demo flow:** Register a tourist → view Digital ID + QR → open Authority Dashboard → trigger the geo-fence, deviation, inactivity and SOS demo scenarios → watch incidents appear on the map and incident log.

---

## 📈 Evaluation Results

Obtained by running `evaluate.py` on synthetic labelled trajectories: **60 trajectories per anomaly scenario (9,769 sliding windows)**, **240 trajectories** for geo-fencing, **200 IDs** for identity tests, **60 full end-to-end runs**. A window is labelled anomalous when at least half of its fixes belong to an injected anomaly.

### 10.1 Anomaly Detection

| Detector | Accuracy | Precision | Recall | F1 | Mean detection delay | False alerts on normal walks |
|---|---|---|---|---|---|---|
| Rules only | 0.95 | 1.00 | 0.65 | 0.79 | 240 s | 0.0% |
| Isolation Forest only | 0.97 | 0.86 | 0.98 | 0.91 | 81 s | 26.7% |
| **Hybrid (proposed)** | **0.97** | **0.95** | **0.84** | **0.89** | **158 s** | **0.0%** |

**Hybrid confusion matrix (window level):** TN = 8328 · FP = 61 · FN = 219 · TP = 1161

**Takeaways**
- Hybrid detected **100.0%** of injected anomaly episodes with **no false alert** on normal trajectories.
- Precision raised from **0.86 → 0.95** versus the model alone.
- Detection delay reduced from ~**240 s → ~158 s** versus rules alone.
- Window-level recall (0.84) is below the 90% target because early windows of an anomaly are not yet detectable; **episode-level detection meets the target**. To be improved in Phase 2.

### 10.2 Geo-fencing, Digital ID and End-to-End

| Component | Result |
|---|---|
| Geo-fencing (240 trajectories) | Accuracy / precision / recall **100.0%** (TP 120, FP 0, FN 0, TN 120) |
| Digital ID verification (200 IDs) | **100.0%** valid IDs accepted; avg verification **0.63 ms** |
| Tamper detection | **100.0%** of 50 tampered records detected; broken chain detected; expired ID rejected |
| Alert latency | Mean **17.5 ms**, 95th percentile **22.9 ms** (server-side processing) |
| End-to-end success | **100.0%** over 60 full runs (register → verify → track → alert → incident log) |

### Evaluation Metrics Used

Accuracy · Precision · Recall · F1-score · Alert latency (ms) · End-to-end success rate · Episode detection rate · Detection delay · False-alert rate on normal trajectories · ID tamper-detection rate

---

## 📚 Literature Review & Research Gap

**Search keywords:** tourist safety monitoring · geo-fencing · anomaly detection · blockchain digital identity · emergency SOS / panic alert.

**Sources searched:** Google Scholar, IEEE Xplore, ResearchGate, arXiv, and publisher platforms (Springer Nature, MDPI, Frontiers).

**Screening:** time window 2021–2026; skimmed Abstract/Introduction/Conclusion first; included works addressing tourist/personal safety, geo-fencing, AI anomaly detection, blockchain identity or SOS alerting. **12 works retained**; the 7 most relevant are compared in the report (Table 1).

**Repeating limitations found in prior work**

- ❌ **No quantitative evaluation** – accuracy, false-alert rate or latency are not reported.
- ❌ **Isolated components** – geo-fencing+ML (indoor/commercial), blockchain identity (border/IoT) or SOS apps studied separately.
- ❌ **Reactive alerting** – depends on the tourist pressing a button or gesture.
- ❌ **Domain mismatch** – anomaly detection + blockchain demonstrated for water infrastructure, not human safety.
- ❌ **Practical weaknesses** – false alerts, battery drain, no offline fallback; feature-heavy proposals without validation.

**🔎 The gap:** we did not find an **open, reproducible and quantitatively evaluated pipeline** that integrates (i) geo-fencing, (ii) interpretable + ML anomaly detection, (iii) a tamper-evident digital tourist identity and (iv) automated incident logging with **measured alert latency** in a single system.

**✅ How this project fills it:** one Python pipeline integrating all four components · proactive alerts without tourist action · hybrid detector with spatial corroboration · quantitative evaluation on labelled synthetic trajectories · reproducible source code · no raw passport number stored.

---

## ⚠️ Limitations

- All results are on **synthetic data** with simulated GPS noise – real-world performance may differ.
- Alert latency measures **server-side processing only**; it excludes network, SMS and push delivery time.
- The blockchain-inspired ledger runs on a **single node** – tamper evidence, **not** distributed consensus.
- Window-level recall (0.84) is below the 90% target set in Objective O2 (episode-level target is met).
- The dashboard capture in the report was rendered offline, so the map background shows zones and route without street tiles.

---

## 🛣️ Roadmap – Phase 2 (~40% remaining)

- [ ] Real GPS input from a mobile app
- [ ] Validation on real trajectory datasets
- [ ] SMS / push notifications to emergency contacts
- [ ] Offline caching
- [ ] Multilingual interface
- [ ] Distributed or permissioned blockchain
- [ ] Deployment hardening
- [ ] Improve window-level recall of the hybrid detector

**Phase 1 completion: ~60% of the planned project.**

---

## ✅ Phase 1 Submission Checklist

| # | Required item | Status |
|---|---|---|
| 1 | Methodology diagram | ✅ Done |
| 2 | Note on which part of the methodology is developed (with prototype screenshots) | ✅ Done |
| 3 | Problem Statement | ✅ Done |
| 4 | Objectives | ✅ Done |
| 5 | Research / Project Questions | ✅ Done |
| 6 | Previous Work comparison table | ✅ Done |
| 7 | Research Gap and Methodology | ✅ Done |

---

## 📖 References

1. S. Gunasree, A. Balu, K. Ashmith, G. J. V. S. S. Kumar and M. Venu, "Smart Tourist Safety Monitoring & Incident Response System using AI, Geo-Fencing & Blockchain using Digital ID," *Int. J. Eng. Res. Sci. Tech.*, vol. 22, no. 2, 2026. <https://ijerst.org/index.php/ijerst/article/view/3047>
2. "AI-Powered Smart Tourist Safety System with Geo-Fencing and Blockchain Identity (GuardianGo)," *IJSREM*, 2026. <https://ijsrem.com/download/ai-powered-smart-tourist-safety-system-with-geo-fencing-and-blockchain-identity/>
3. "Anomaly-resilient geofencing and predictive navigation in IoT environments using machine learning and federated learning for metaverse workplaces and smart shopping malls," *Scientific Reports*, 2026. <https://www.nature.com/articles/s41598-025-33856-0>
4. "Smart Water Security with AI and Blockchain-Enhanced Digital Twins," arXiv:2504.20275, 2025. <https://arxiv.org/pdf/2504.20275>
5. R. A. Pava-Díaz, J. Gil-Ruiz and D. A. López-Sarmiento, "Self-sovereign identity on the blockchain: contextual analysis and quantification of SSI principles implementation," *Frontiers in Blockchain*, vol. 2, art. 1443362, 2024. <https://doi.org/10.3389/fbloc.2024.1443362>
6. M. Naghmouchi, H. Kaffel and M. Laurent, "An automatized Identity and Access Management system for IoT combining Self-Sovereign Identity and smart contracts," arXiv:2201.00231, 2022. <https://arxiv.org/pdf/2201.00231>
7. "Cross-Border Digital Identity System Based on Ethereum Layer 2 Architecture," *Electronics*, vol. 15, no. 3, art. 708, 2026. <https://www.mdpi.com/2079-9292/15/3/708>
8. "Sensor-Driven Emergency SOS App with Real-Time Location Tracking," *IJERD*, vol. 21, no. 10, 2025. <https://ijerd.com/paper/vol21-issue10/2110147151.pdf>
9. K. B. Kavya, D. Sajankar, A. Pandey and R. Koranga, "Panic Button for Women Safety Using IoT and GPS," *IJCOPE*, vol. 2, no. 5, 2026. <https://ijcope.org/article/panic-button-for-women-safety-using-iot-and-gps/>
10. "Smart Tourist Safety Monitoring System," SIH 2025 presentation (SIH2025-002), Scribd. <https://www.scribd.com/presentation/951336094/SIH2025-002>

---

## 👨‍💻 Credits

### Developed by **Harsh Parmar**

> **Harsh Parmar built the entire project on his own** – the complete Phase 1 report (problem statement, objectives, literature review, research gap, methodology, evaluation) **and** the full working prototype and website (Digital Tourist ID, geo-fencing engine, anomaly detection, incident logging, Flask authority dashboard, simulator and evaluation).

| | |
|---|---|
| **Name** | Harsh Parmar |
| **Enrollment No.** | 92500133012 |
| **Class** | 3EK1-A · B.Tech ICT · Semester 3 · Marwadi University |
| **GitHub** | [github.com/HarshParmar029](https://github.com/HarshParmar029) |
| **Email** | hp259369@gmail.com |

*The group submission was officially registered under Project Group 2 with Kakshil Adeshara (92500133056, 3EK1-A).*

---

<div align="center">

**🛡️ Safer journeys through proactive, verifiable and measurable technology.**

*Marwadi University · Faculty of Engineering & Technology · Department of Information and Communication Technology*

⭐ If you find this project useful, consider starring the repository!

</div>
