# EcoTrack — Advanced Sustainability Framework for Green MLOps

**EcoTrack** is a production-grade experiment tracking and compliance framework designed to treat carbon as a primary hyperparameter. It goes beyond passive tracking by integrating real-time carbon-aware scheduling, automated quantization gating, and regulatory compliance reporting (SEBI BRSR / EU CSRD).

---

## 🌟 Key Features

### 🟢 1. "Green-Pause" Scheduler
Carbon-aware training controller that monitors live grid intensity via **ElectricityMaps API**.
- **Auto-Pause**: Automatically pauses CUDA training jobs when the grid exceeds a dirty intensity threshold.
- **Auto-Resume**: Resumes training when renewable energy peaks (e.g., solar midday).
- **Cross-Platform**: Thread-safe implementation with SIGSTOP/SIGCONT support.

### 🏷️ 2. AI Nutrition Label (Compliance)
Standardized sustainability metadata "baked" into model files.
- **Reporting**: Generates professional PDF labels aligned with **SEBI BRSR Principle 6** and **EU CSRD ESRS E1**.
- **Metadata**: Embeds carbon ratings (A–F), GPU ancestry, and energy debt directly into `.pt` or `.safetensors` files.

### ⚡ 3. Automatic Quantization Gating
Enforces energy-efficient model deployments in CI/CD.
- **Architecture Probing**: Automatically determines if INT8 or INT4 quantization preserves accuracy (ResNet vs Transformer).
- **Verdict Engine**: Forces quantization gating if energy savings >40% and accuracy retention >98%.

### 🔗 4. Transfer Learning Matchmaker
Prevents compute waste by suggesting fine-tuning over training from scratch.
- **Model Zoo Matching**: Semantic search across experiment history to find model "twins".
- **Carbon Saving**: Estimates up to 80% CO₂ reduction by reusing weights.

---

## 🛠️ Project Structure

```
Carbon-aware-experiment-tracking/
├── backend/                  # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── services/         # Scheduler, Nutrition, Quantization logic
│   │   ├── api/v1/           # High-precision endpoints
│   │   └── models/           # SQLite / Postgres ORM
│   └── seed_db.py            # Demo data generation script
├── frontend/                 # Vite + Chart.js + Lucide
│   └── src/                  # Dark-mode sustainability dashboard
├── tracker/                  # Python Client
│   └── tracker_utils.py      # GreenPauseContext & CodeCarbon wrapper
└── .gitignore                # Security-first excludes
```

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Activate venv: .\venv\Scripts\activate (Windows) or source venv/bin/activate (Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
> **Seed Demo Data**: Run `python seed_db.py` to populate your dashboard with high-quality experiment data.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
👉 Access Dashboard: [http://localhost:5173](http://localhost:5173)

---

## 📊 Compliance Standards
EcoTrack is built to satisfy international sustainability disclosure requirements:
- **Scope 2 Reporting**: Indirect emissions from purchased electricity for compute.
- **SEBI BRSR**: Principle 6 Section C (Environment).
- **EU CSRD**: ESRS E1 Climate Change requirements for Scope 2 reporting.

---

## 👨‍💻 Developer
**Aryan** ([@aryan12375](https://github.com/aryan12375))
MIT Manipal, Karnataka
MIT Licensed
