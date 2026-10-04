# Tourist Safety Monitoring & Incident Response System
### AI anomaly detection + Geo-fencing + Blockchain-based Digital ID  |  PWP Python project, Group 2
Harsh Parmar (92500133012) | 3EK1-A | Marwadi University

## Quick start
```bash
pip install -r requirements.txt
python train_model.py            # optional - trains the Isolation Forest (auto-runs on first use)
python app.py                    # open http://127.0.0.1:5000
python evaluate.py               # reproduces EVERY number of the report (about 1-3 min) -> results/
python -m unittest discover -s tests -v   # 22 automated tests
```

## What is implemented
| Module | File | Highlights |
|---|---|---|
| Digital Tourist ID | `digital_id.py`, `ledger_network.py` | per-record salted passport hash, canonical-JSON SHA-256, **proof-of-work** hash-chained blocks, **3-node validator network with majority consensus**, HMAC-signed QR, 7-check verification, revocation, full ledger audit |
| Geo-fencing | `geofence.py` | Haversine circles **and polygons**, safe / caution / restricted zones, hysteresis (no GPS-noise flapping), **proactive "approaching restricted zone" warning** |
| AI anomaly detection | `anomaly.py`, `train_model.py` | rules (route deviation via point-to-polyline, inactivity with rest-point exemption, signal loss) + Isolation Forest on 6 window features + spatial corroboration (hybrid) |
| Incident response | `engine.py`, `notifier.py` | one pipeline: fix -> geofence -> anomaly -> dedupe -> incident (latency measured) -> SMS/dashboard notification; manual SOS; silent-device watchdog; incident Ack/Resolve |
| Web app | `app.py`, `templates/`, `static/` | registration, ID card, verification, **authority dashboard** (live SVG map, tracks, zones, route, heat-map, risk score, incident log, notifications, ledger network panel, scenario player), **tourist phone view** (3-second long-press SOS, live GPS, offline queue, English/Hindi/Gujarati) |
| Simulation | `simulator.py` | ground-truth labelled trajectories: normal (pauses, rest stops, side-trips), route deviation, prolonged inactivity, lost/wandering, geo-fence violation, signal loss |
| Evaluation | `evaluate.py` | 5 seeds, three-detector ablation, per-anomaly-type table, operating-point sweep on a separate validation seed, geo-fence / ID / tamper / end-to-end tests through the real Flask app, charts + `results/REPORT.md` |

## Demo script (screen recording)
1. `python app.py` -> Register a tourist -> Digital ID + QR -> **Verify ID** (7 checks pass).
2. **Dashboard** -> pick the tourist -> press *Geo-fence violation*: watch the marker walk, the approach warning, then the HIGH incident + SMS notification.
3. Press *Lost / wandering* (only the AI layer catches this), *Route deviation*, *Prolonged inactivity*, *Signal loss*, then **SOS**.
4. Acknowledge / Resolve incidents; open the heat-map layer.
5. *Ledger network*: **Tamper Node-2** -> node turns TAMPERED but consensus stays OK -> *Run audit* -> *Heal*. Tamper two nodes to show consensus is lost.
6. Open the Tourist app view (link on the ID page) on a phone: hold SOS for 3 s.

## Viva notes (be ready to say these honestly)
* The ledger is a **simulated permissioned network in one process** (majority validation + proof-of-work), not a public blockchain.
* All accuracy numbers are on **synthetic** trajectories (noise sigma 6 m, 1.2 m/s). Real-dataset validation is future work.
* Alert latency is **server-side processing**; the SMS channel is simulated unless Twilio environment variables are set.
* Window-level recall is lower than episode-level detection because the first windows of an anomaly are not yet distinguishable; the report shows both.
* Isolation Forest cannot extrapolate beyond the range it saw; that is why the rules exist and why the hybrid is better than either alone (see the per-anomaly-type table).
* Passport number is never stored: per-record random salt + server pepper + SHA-256.
