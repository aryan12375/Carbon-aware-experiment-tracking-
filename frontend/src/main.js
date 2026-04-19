import './styles.css'
import { createIcons, LayoutDashboard, Calculator, TrendingUp, Cpu, CalendarClock, ShieldCheck, History, Plus, Zap, Smartphone, TreeDeciduous, Car, Info, AlertTriangle, CheckCircle2, Tag, GitMerge } from 'lucide'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

// ── State Management ───────────────────────────────────────────────────────
const state = {
  currentPage: 'dashboard',
  projects: [],
  runs: [],
  stats: {
    total_runs: 0,
    total_co2_kg: 0,
    total_energy_kwh: 0,
    avg_accuracy: 0,
    gate_pass_rate: 0,
    human_total_co2: '≈ 0 smartphone charges'
  }
}

// ── Icons ──────────────────────────────────────────────────────────────────
const initIcons = () => {
  createIcons({
    icons: {
      LayoutDashboard, Calculator, TrendingUp, Cpu, CalendarClock, ShieldCheck, History, Plus, Zap, Smartphone, TreeDeciduous, Car, Info, AlertTriangle, CheckCircle2, Tag, GitMerge
    }
  })
}

// ── Routing ────────────────────────────────────────────────────────────────
const routes = {
  dashboard: {
    title: 'Dashboard',
    subtitle: 'Real-time carbon footprint of your ML experiments.',
    render: renderDashboard
  },
  'pre-flight': {
    title: 'Pre-flight Estimator',
    subtitle: 'Predict carbon emissions before you hit "Train".',
    render: renderPreFlight
  },
  'frontier': {
    title: 'Efficiency Frontier',
    subtitle: 'Visualization of the accuracy vs. carbon cost balance.',
    render: renderFrontier
  },
  'gpu-compare': {
    title: 'GPU Comparison',
    subtitle: 'Benchmark hardware efficiency on the Karnataka grid.',
    render: renderGpuComparison
  },
  'scheduler': {
    title: 'Smart Scheduler',
    subtitle: 'Run jobs when the grid is cleanest.',
    render: renderScheduler
  },
  'green-gate': {
    title: 'Green Gate CI',
    subtitle: 'Integrate carbon ethics into your CI/CD pipeline.',
    render: renderGreenGate
  },
  'run-history': {
    title: 'Run History',
    subtitle: 'Complete audit trail of all experiment emissions.',
    render: renderRunHistory
  },
  'nutrition-label': {
    title: 'AI Nutrition Label',
    subtitle: 'Carbon label baked into every model — SEBI BRSR & EU CSRD compliant.',
    render: renderNutritionLabel
  },
  'quant-gate': {
    title: 'Quantization Gate',
    subtitle: 'Automatically enforce lighter models when accuracy is preserved.',
    render: renderQuantGate
  },
  'matchmaker': {
    title: 'Transfer Learning Matchmaker',
    subtitle: 'Stop training from scratch. Find a model you already have.',
    render: renderMatchmaker
  }
}

function handleRoute() {
  const hash = window.location.hash.replace('#', '') || 'dashboard'
  const route = routes[hash] || routes.dashboard
  
  state.currentPage = hash
  
  // Update header
  document.getElementById('page-title').textContent = route.title
  document.getElementById('page-subtitle').textContent = route.subtitle
  
  // Update active nav
  document.querySelectorAll('.nav-item').forEach(nav => {
    nav.classList.toggle('active', nav.dataset.page === hash)
  })
  
  // Render page
  const mount = document.getElementById('content-mount')
  mount.innerHTML = route.render()
  
  // Initialize lucide icons for new content
  initIcons()
  
  // Page specific logic (charts, listeners)
  if (hash === 'dashboard') initDashboardCharts()
  if (hash === 'frontier') initFrontierCharts()
  if (hash === 'gpu-compare') initGpuCharts()
  if (hash === 'scheduler') initSchedulerLive()
  if (hash === 'nutrition-label') initNutritionLabel()
  if (hash === 'quant-gate') initQuantGate()
  if (hash === 'matchmaker') initMatchmaker()
}

window.addEventListener('hashchange', handleRoute)
window.addEventListener('DOMContentLoaded', () => {
  handleRoute()
  initIcons()
})

// ── Page Templates ─────────────────────────────────────────────────────────

function renderDashboard() {
  return `
    <div class="stats-grid">
      <div class="card kpi-card">
        <div class="icon-box" style="background: rgba(168, 230, 207, 0.4)">
          <i data-lucide="zap" style="color: #2D4038"></i>
        </div>
        <h3>Total Energy</h3>
        <div class="value">42.8 <span style="font-size: 1rem">kWh</span></div>
        <div class="delta positive">↑ 12% vs last month</div>
      </div>
      
      <div class="card kpi-card">
        <div class="icon-box" style="background: rgba(45, 64, 56, 0.1)">
          <i data-lucide="tree-deciduous" style="color: #2D4038"></i>
        </div>
        <h3>Total Carbon</h3>
        <div class="value">14.2 <span style="font-size: 1rem">kg CO₂e</span></div>
        <div class="human-equiv">
          <i data-lucide="smartphone"></i> ≈ 1,720 smartphone charges
        </div>
      </div>
      
      <div class="card kpi-card">
        <div class="icon-box" style="background: rgba(168, 230, 207, 0.4)">
          <i data-lucide="shield-check" style="color: #2D4038"></i>
        </div>
        <h3>Gate Pass Rate</h3>
        <div class="value">92.5%</div>
        <div class="delta positive">↑ 4.2% improvement</div>
      </div>
      
      <div class="card kpi-card">
        <div class="icon-box" style="background: rgba(233, 150, 122, 0.2)">
          <i data-lucide="trending-up" style="color: #E9967A"></i>
        </div>
        <h3>Avg. Accuracy</h3>
        <div class="value">88.4%</div>
        <div class="delta positive">↑ 2.1% improvement</div>
      </div>
    </div>

    <div class="dashboard-main">
      <div class="card">
        <div class="section-title">
          <h2>Accuracy vs Carbon Frontier</h2>
          <button class="btn btn-text"><i data-lucide="info"></i> Details</button>
        </div>
        <div class="chart-container">
          <canvas id="frontier-chart-summary"></canvas>
        </div>
      </div>
      
      <div class="card">
        <div class="section-title">
          <h2>Carbon Debt</h2>
        </div>
        <div class="chart-container">
          <canvas id="debt-donut"></canvas>
        </div>
        <div style="margin-top: 20px">
          <p style="font-size: 0.8125rem; color: var(--text-secondary); line-height: 1.5">
            Model <strong>ResNet-101</strong> accounts for 42% of your monthly carbon budget. Consider pruning.
          </p>
        </div>
      </div>
    </div>

    <div class="table-container card">
      <div class="section-title" style="padding: 0 20px">
        <h2>Recent Run History</h2>
        <a href="#run-history" class="btn btn-text">View All</a>
      </div>
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Project</th>
            <th>Model</th>
            <th>CO₂ (g)</th>
            <th>Accuracy</th>
            <th>Gate Status</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>f7a2d8</code></td>
            <td>ResNet-FineTune</td>
            <td>ResNet-50</td>
            <td>142.5</td>
            <td>94.2%</td>
            <td><span class="badge badge-pass">Pass</span></td>
            <td>2h ago</td>
          </tr>
          <tr>
            <td><code>b2c4e9</code></td>
            <td>NLP-BERT</td>
            <td>BERT-Large</td>
            <td>1,240.2</td>
            <td>91.3%</td>
            <td><span class="badge badge-fail">Fail</span></td>
            <td>5h ago</td>
          </tr>
          <tr>
            <td><code>d9e1f2</code></td>
            <td>ViT-Training</td>
            <td>ViT-Base</td>
            <td>450.8</td>
            <td>89.1%</td>
            <td><span class="badge badge-warn">Warn</span></td>
            <td>Yesterday</td>
          </tr>
        </tbody>
      </table>
    </div>
  `
}

function renderPreFlight() {
  return `
    <div class="dashboard-main" style="grid-template-columns: 1fr 1fr">
      <div class="card">
        <h2 style="margin-bottom: 24px">Job Parameters</h2>
        <form id="preflight-form" style="display: flex; flex-direction: column; gap: 20px">
          <div class="form-group">
            <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Model Architecture</label>
            <select style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit">
              <option>ResNet-50</option>
              <option>BERT-Base</option>
              <option>Vision Transformer (ViT)</option>
              <option>Llama-2-7B</option>
            </select>
          </div>
          <div class="form-group">
            <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Dataset Size (Million Samples)</label>
            <input type="number" placeholder="1.2" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
          </div>
          <div class="form-group">
            <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Target Epochs</label>
            <input type="number" placeholder="50" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
          </div>
          <div class="form-group">
            <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">GPU Hardware</label>
            <div style="display: flex; gap: 12px">
              <label style="flex: 1; padding: 12px; border: 1px solid var(--neo-mint-dark); border-radius: 8px; text-align: center; cursor: pointer; background: var(--neo-mint)">
                <input type="radio" name="gpu" checked style="display: none" /> T4
              </label>
              <label style="flex: 1; padding: 12px; border: 1px solid var(--warm-stone-dark); border-radius: 8px; text-align: center; cursor: pointer">
                <input type="radio" name="gpu" style="display: none" /> A100
              </label>
              <label style="flex: 1; padding: 12px; border: 1px solid var(--warm-stone-dark); border-radius: 8px; text-align: center; cursor: pointer">
                <input type="radio" name="gpu" style="display: none" /> V100
              </label>
            </div>
          </div>
          <button type="button" class="btn btn-pill" style="width: 100%; justify-content: center; padding: 16px">Estimate Footprint</button>
        </form>
      </div>
      
      <div style="display: flex; flex-direction: column; gap: 24px">
        <div class="card kpi-card" style="background: var(--neo-mint)">
          <h3 style="color: var(--forest-green)">Predicted Emission</h3>
          <div class="value" style="font-size: 3rem">840 <span style="font-size: 1.25rem">g CO₂e</span></div>
          <div class="human-equiv" style="background: rgba(255,255,255,0.4)">
            <i data-lucide="car"></i> ≈ 5.2 km driven in a petrol car
          </div>
        </div>
        
        <div class="ai-box">
          <div class="ai-header">
            <i data-lucide="zap"></i>
            <strong>AI Optimization Pilot</strong>
          </div>
          <p style="font-size: 0.875rem; line-height: 1.6; color: var(--text-secondary)">
            Based on your architecture, switching to <strong>Mixed Precision (FP16)</strong> training could reduce your predicted CO₂ by 28% without impacting accuracy.
          </p>
          <ul style="margin-top: 16px; font-size: 0.8125rem; color: var(--text-secondary); list-style: none; display: flex; flex-direction: column; gap: 8px">
            <li><i data-lucide="check-circle-2" style="width: 14px; color: #52C41A"></i> Enable <code>torch.cuda.amp</code></li>
            <li><i data-lucide="check-circle-2" style="width: 14px; color: #52C41A"></i> Run job at 02:00 AM (Clean grid)</li>
          </ul>
        </div>
      </div>
    </div>
  `
}

function renderFrontier() {
  return `
    <div class="card">
      <div class="section-title">
        <h2>The Efficiency Frontier</h2>
        <div style="display: flex; gap: 12px">
          <span class="badge badge-pass">Gold Zone</span>
          <span class="badge badge-warn">Debt Zone</span>
        </div>
      </div>
      <div class="chart-container" style="height: 500px">
        <canvas id="frontier-chart-full"></canvas>
      </div>
    </div>
  `
}

function renderGpuComparison() {
  return `
    <div class="dashboard-main" style="grid-template-columns: 1fr 1fr">
      <div class="card">
        <h2>Carbon per FLOP</h2>
        <div class="chart-container">
          <canvas id="gpu-carbon-chart"></canvas>
        </div>
      </div>
      <div class="card">
        <h2>Accuracy per Gram CO₂</h2>
        <div class="chart-container">
          <canvas id="gpu-efficiency-chart"></canvas>
        </div>
      </div>
    </div>
    <div class="table-container card">
      <table>
        <thead>
          <tr>
            <th>GPU Model</th>
            <th>TDP (W)</th>
            <th>Training Time (Avg)</th>
            <th>Efficiency Score</th>
            <th>Karnataka Grid Rating</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>NVIDIA T4</td>
            <td>70W</td>
            <td>4.2h</td>
            <td>8.4</td>
            <td>⭐⭐⭐⭐⭐</td>
          </tr>
          <tr>
            <td>NVIDIA A100</td>
            <td>400W</td>
            <td>1.1h</td>
            <td>7.2</td>
            <td>⭐⭐⭐</td>
          </tr>
          <tr>
            <td>NVIDIA V100</td>
            <td>250W</td>
            <td>1.8h</td>
            <td>6.8</td>
            <td>⭐⭐⭐</td>
          </tr>
        </tbody>
      </table>
    </div>
  `
}

function renderScheduler() {
  return `
    <div class="scheduler-grid">
      <div class="card">
        <div class="section-title">
          <h2>Karnataka Grid Intensity (Live Forecast)</h2>
          <span class="badge" id="current-intensity-badge" style="background: var(--neo-mint)">Loading...</span>
        </div>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 16px">Green = clean ☀️ · Orange = moderate · Red = dirty 🏭. Train during green windows.</p>
        
        <div class="heatmap" id="live-heatmap">
          ${Array.from({length: 24}).map((_, i) => `
            <div class="heatmap-cell" id="hm-${i}" title="${i}:00 — loading..." style="background: var(--warm-stone-dark)">
              <div style="font-size:0.45rem; text-align:center; padding-top:4px; color:#fff; font-weight:700">${i}</div>
            </div>`).join('')}
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 0.625rem; color: var(--text-secondary)">
          <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
        </div>

        <div id="optimal-windows-list" style="margin-top: 24px; display: flex; gap: 8px; flex-wrap: wrap"></div>

        <div style="margin-top: 32px">
          <h2>Projected Savings Chart</h2>
          <div class="chart-container" style="height: 220px">
            <canvas id="scheduler-savings-chart"></canvas>
          </div>
        </div>
      </div>
      
      <div style="display: flex; flex-direction: column; gap: 24px">
        <div class="card" style="border: 2px solid var(--neo-mint-dark)">
          <h3 style="margin-bottom: 12px">Auto-Pause Threshold</h3>
          <label style="font-size: 0.875rem; font-weight: 600; display: block; margin-bottom: 8px">Pause if intensity exceeds:</label>
          <input type="range" id="threshold-slider" min="200" max="750" value="450" style="width: 100%; accent-color: var(--forest-green)">
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary)">
            <span>200 g/kWh 🟢</span>
            <span id="threshold-val" style="font-weight: 700; color: var(--forest-green)">450 g/kWh</span>
            <span>750 g/kWh 🔴</span>
          </div>
          <p style="margin-top: 12px; font-size: 0.8125rem; color: var(--text-secondary)">
            GreenPauseContext will auto-pause your CUDA job when grid exceeds this value and resume when it cleans.
          </p>
          <pre style="background:#1e1e1e;color:#a8e6cf;padding:12px;border-radius:8px;font-size:0.7rem;margin-top:12px;overflow:auto">with GreenPauseContext(
  threshold_g_kwh=<span id="code-threshold">450</span>,
  region="IN-SO"
) as ctx:
    train_model()</pre>
        </div>
        
        <div class="card kpi-card" id="saving-card">
          <h3>Potential Saving Today</h3>
          <div class="value" style="color: #52C41A" id="saving-value">--</div>
          <p style="font-size: 0.75rem" id="saving-desc">Loading grid data...</p>
        </div>

        <div class="card kpi-card">
          <h3>Source</h3>
          <div style="font-size: 0.875rem" id="grid-source">Initialising...</div>
        </div>
      </div>
    </div>
  `
}

function renderGreenGate() {
  return `
    <div class="dashboard-main" style="grid-template-columns: 3fr 2fr">
      <div class="card">
        <h2>Gate Logic Configuration</h2>
        <div style="background: #1E1E1E; padding: 20px; border-radius: 8px; margin-top: 20px; font-family: 'Fira Code', monospace; color: #D4D4D4; line-height: 1.6; font-size: 0.875rem">
          <span style="color: #569CD6">if</span> (delta_acc < <span style="color: #B5CEA8">0.5</span> && delta_co2 > <span style="color: #B5CEA8">0.20</span>):<br />
          &nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #CE9178">return</span> <span style="color: #D16969">GATE_FAIL</span><br /><br />
          <span style="color: #569CD6">elif</span> (delta_co2 > <span style="color: #B5CEA8">0.40</span>):<br />
          &nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #CE9178">return</span> <span style="color: #D7BA7D">GATE_WARN</span><br /><br />
          <span style="color: #569CD6">else</span>:<br />
          &nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #CE9178">return</span> <span style="color: #6A9955">GATE_PASS</span>
        </div>
        
        <h2 style="margin-top: 40px">GitHub Action Setup</h2>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 16px">Drop this into <code>.github/workflows/ecotrack.yml</code></p>
        <div style="background: #1E1E1E; padding: 20px; border-radius: 8px; font-family: 'Fira Code', monospace; color: #D4D4D4; line-height: 1.6; font-size: 0.8125rem">
          <span style="color: #9CDCFE">steps</span>:<br />
          &nbsp;&nbsp;- <span style="color: #9CDCFE">uses</span>: <span style="color: #CE9178">actions/checkout@v4</span><br />
          &nbsp;&nbsp;- <span style="color: #9CDCFE">name</span>: <span style="color: #CE9178">Green Gate</span><br />
          &nbsp;&nbsp;&nbsp;&nbsp;<span style="color: #9CDCFE">run</span>: <span style="color: #CE9178">python tracker/check_gate.py --dir ./emissions</span>
        </div>
      </div>
      
      <div class="card">
        <h2>Gate Metrics</h2>
        <div style="display: flex; flex-direction: column; gap: 20px; margin-top: 24px">
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--warm-stone); padding-bottom: 12px">
             <span>PRs Blocked</span>
             <span style="font-weight: 700">12</span>
          </div>
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--warm-stone); padding-bottom: 12px">
             <span>Efficiency Gain</span>
             <span style="font-weight: 700; color: #52C41A">+18.2%</span>
          </div>
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--warm-stone); padding-bottom: 12px">
             <span>Carbon Avoided</span>
             <span style="font-weight: 700; color: #52C41A">4.2 kg</span>
          </div>
        </div>
        <div class="ai-box" style="margin-top: 32px">
           <div class="ai-header"><i data-lucide="info"></i> <strong>What is the Green Gate?</strong></div>
           <p style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.5">
             A CI/CD unit that blocks "over-training" — when massive energy is spent for negligible accuracy gain.
           </p>
        </div>
      </div>
    </div>
  `
}

function renderRunHistory() {
  return `
    <div class="card table-container">
      <div class="section-title" style="padding: 0 20px">
        <h2>Run History Full Audit</h2>
        <div style="display: flex; gap: 12px">
           <button class="btn btn-pill" style="background: var(--warm-stone); color: var(--forest-green); padding: 6px 16px"><i data-lucide="plus"></i> Export BRSR</button>
           <button class="btn btn-pill"><i data-lucide="plus"></i> Filter</button>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Project</th>
            <th>Model</th>
            <th>CO₂ (g)</th>
            <th>Energy (kWh)</th>
            <th>Region</th>
            <th>Accuracy</th>
            <th>Gate</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          ${Array.from({length: 10}).map((_, i) => `
            <tr>
              <td><code>run_${Math.random().toString(36).substr(2, 6)}</code></td>
              <td>EcoProject-${i}</td>
              <td>Model-X</td>
              <td>${(Math.random() * 500).toFixed(1)}</td>
              <td>${(Math.random() * 2).toFixed(3)}</td>
              <td>IN-SO</td>
              <td>${(80 + Math.random() * 15).toFixed(1)}%</td>
              <td><span class="badge badge-${['pass', 'fail', 'warn'][i % 3]}">${['pass', 'fail', 'warn'][i % 3]}</span></td>
              <td>Apr 1${i}, 2026</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
}

// ── Chart initializers ─────────────────────────────────────────────────────

function initDashboardCharts() {
  const ctx = document.getElementById('frontier-chart-summary').getContext('2d')
  new Chart(ctx, {
    type: 'bubble',
    data: {
      datasets: [{
        label: 'Runs',
        data: [
          { x: 100, y: 92, r: 10 },
          { x: 250, y: 94, r: 15 },
          { x: 400, y: 94.5, r: 20 },
          { x: 800, y: 95, r: 35 },
          { x: 120, y: 88, r: 8 }
        ],
        backgroundColor: '#A8E6CF',
        borderColor: '#2D4038',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: 'CO₂ (g)' } },
        y: { title: { display: true, text: 'Accuracy (%)' }, min: 80 }
      }
    }
  })

  const donutCtx = document.getElementById('debt-donut').getContext('2d')
  new Chart(donutCtx, {
    type: 'doughnut',
    data: {
      labels: ['ResNet-101', 'BERT-Large', 'Stable-Diff', 'Others'],
      datasets: [{
        data: [42, 28, 20, 10],
        backgroundColor: ['#2D4038', '#A8E6CF', '#E9967A', '#F2F0EB'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  })
}

async function initFrontierCharts() {
  const canvas = document.getElementById('frontier-chart-full')
  if (!canvas) return
  const ctx = canvas.getContext('2d')

  try {
    const res = await fetch(`${API}/analytics/frontier`)
    if (!res.ok) throw new Error('API offline')
    const data = await res.json()

    new Chart(ctx, {
      type: 'bubble',
      data: {
        datasets: [{
          label: 'Your Runs',
          data: data.runs.map(r => ({ x: r.co2_kg, y: r.accuracy, r: 10 })),
          backgroundColor: '#A8E6CF',
          borderColor: '#2D4038',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => `Run: ${data.runs[ctx.dataIndex].model_name} | Acc: ${ctx.raw.y}% | CO2: ${ctx.raw.x}kg`
            }
          }
        },
        scales: {
          x: { title: { display: true, text: 'CO₂ Emissions (kg)' }, beginAtZero: true },
          y: { title: { display: true, text: 'Accuracy (%)' }, min: 80, max: 100 }
        }
      }
    })
  } catch (e) {
    // Demo data for frontier
    new Chart(ctx, {
      type: 'bubble',
      data: {
        datasets: [{
          label: 'Runs (Demo)',
          data: [
            { x: 0.1, y: 88, r: 10 }, { x: 0.4, y: 92, r: 15 }, { x: 0.8, y: 94, r: 20 },
            { x: 1.2, y: 95, r: 25 }, { x: 5.8, y: 85, r: 40 }
          ],
          backgroundColor: '#E9967A88',
          borderColor: '#E9967A',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: 'CO₂ (kg)' } },
          y: { title: { display: true, text: 'Accuracy (%)' }, min: 80 }
        }
      }
    })
  }
}

function initGpuCharts() {
  const ctx1 = document.getElementById('gpu-carbon-chart')?.getContext('2d')
  if (ctx1) {
    new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: ['T4', 'A100', 'V100', 'RTX 3090'],
        datasets: [{
          label: 'g CO₂ per 1e12 FLOPs',
          data: [4.2, 7.8, 6.5, 9.1],
          backgroundColor: '#A8E6CF'
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    })
  }

  const ctx2 = document.getElementById('gpu-efficiency-chart')?.getContext('2d')
  if (ctx2) {
    new Chart(ctx2, {
      type: 'line',
      data: {
        labels: ['T4', 'V100', 'A100'],
        datasets: [{
          label: 'Accuracy % per 10g CO₂',
          data: [12.4, 9.2, 8.1],
          borderColor: '#2D4038',
          backgroundColor: '#A8E6CF',
          tension: 0.3,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true } }
      }
    })
  }
}

// ── Feature 1: Scheduler Live Data ─────────────────────────────────────────

const API = 'http://localhost:8000/api/v1'

async function initSchedulerLive() {
  const slider = document.getElementById('threshold-slider')
  const thresholdVal = document.getElementById('threshold-val')
  const codeThreshold = document.getElementById('code-threshold')
  if (slider) {
    slider.addEventListener('input', () => {
      thresholdVal.textContent = slider.value + ' g/kWh'
      codeThreshold.textContent = slider.value
    })
  }

  try {
    const res = await fetch(`${API}/scheduler/grid-intensity?region=IN-SO`)
    if (!res.ok) throw new Error('API offline')
    const data = await res.json()

    // Update badge
    const badge = document.getElementById('current-intensity-badge')
    if (badge) {
      const label = data.current_label
      const colors = { clean: 'var(--neo-mint)', moderate: '#FFF3CD', dirty: '#FFE4E1' }
      badge.textContent = `${data.current_intensity.toFixed(0)} g/kWh — ${label}`
      badge.style.background = colors[label] || 'var(--warm-stone)'
    }

    // Update heatmap cells
    const maxIntensity = Math.max(...data.forecast.map(p => p.intensity_g_kwh))
    const minIntensity = Math.min(...data.forecast.map(p => p.intensity_g_kwh))
    data.forecast.forEach(point => {
      const cell = document.getElementById(`hm-${point.hour}`)
      if (!cell) return
      const norm = (point.intensity_g_kwh - minIntensity) / (maxIntensity - minIntensity)
      // Green (clean) to Red (dirty)
      const r = Math.round(norm * 233)
      const g = Math.round((1 - norm) * 200 + 70)
      const b = Math.round((1 - norm) * 100)
      cell.style.background = `rgb(${r},${g},${b})`
      cell.title = `${point.hour}:00 — ${point.intensity_g_kwh.toFixed(0)} g/kWh (${point.label})`
      cell.style.opacity = point.is_optimal ? '1' : '0.75'
      cell.style.boxShadow = point.is_optimal ? '0 0 6px rgba(168,230,207,0.8)' : 'none'
    })

    // Optimal windows badges
    const windowList = document.getElementById('optimal-windows-list')
    if (windowList) {
      windowList.innerHTML = '<span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary);margin-right:8px">Best windows:</span>'
      data.optimal_windows.forEach(w => {
        windowList.innerHTML += `<span class="badge badge-pass" style="font-size:0.8rem">${w}</span>`
      })
    }

    // Saving card
    const savingVal = document.getElementById('saving-value')
    const savingDesc = document.getElementById('saving-desc')
    if (savingVal) savingVal.textContent = `${data.potential_saving_pct.toFixed(1)}%`
    if (savingDesc) savingDesc.textContent = `By shifting to cleanest window vs current hour. Source: ${data.source}`

    // Source
    const srcEl = document.getElementById('grid-source')
    if (srcEl) {
      const sourceLabels = {
        co2signal: '🌐 CO2Signal API (live)',
        electricitymaps: '🌐 ElectricityMaps API (live)',
        heuristic_model: '📐 EcoTrack Heuristic Model (India solar curve)'
      }
      srcEl.textContent = sourceLabels[data.source] || data.source
    }

    // Chart
    const chartCtx = document.getElementById('scheduler-savings-chart')
    if (chartCtx) {
      new Chart(chartCtx.getContext('2d'), {
        type: 'bar',
        data: {
          labels: data.forecast.map(p => `${p.hour}:00`),
          datasets: [{
            label: 'gCO₂/kWh',
            data: data.forecast.map(p => p.intensity_g_kwh),
            backgroundColor: data.forecast.map(p => {
              if (p.label === 'clean') return 'rgba(168,230,207,0.8)'
              if (p.label === 'moderate') return 'rgba(250,173,20,0.6)'
              return 'rgba(233,150,122,0.8)'
            }),
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { title: { display: true, text: 'gCO₂/kWh' }, beginAtZero: false }
          }
        }
      })
    }

  } catch (e) {
    // API not running — show demo data
    const badge = document.getElementById('current-intensity-badge')
    if (badge) badge.textContent = 'API offline — demo mode'
    const srcEl = document.getElementById('grid-source')
    if (srcEl) srcEl.textContent = '📐 EcoTrack Heuristic Model (start backend for live data)'

    // Render demo heatmap
    const demoIntensities = [580,550,520,500,490,510,540,580,600,560,480,420,390,400,440,500,620,680,700,690,660,640,610,590]
    demoIntensities.forEach((intensity, i) => {
      const cell = document.getElementById(`hm-${i}`)
      if (!cell) return
      const norm = (intensity - 380) / 330
      const r = Math.round(norm * 233)
      const g = Math.round((1-norm)*200+70)
      cell.style.background = `rgb(${r},${g},80)`
      cell.title = `${i}:00 — ${intensity} g/kWh`
    })
    const savingVal = document.getElementById('saving-value')
    if (savingVal) {
      savingVal.textContent = '31.6%'
      document.getElementById('saving-desc').textContent = 'By shifting to 12:00-14:00 clean window'
    }
    const windowList = document.getElementById('optimal-windows-list')
    if (windowList) {
      windowList.innerHTML = '<span style="font-size:0.8rem;font-weight:600;color:var(--text-secondary);margin-right:8px">Best windows:</span><span class="badge badge-pass" style="font-size:0.8rem">11:00–14:00</span><span class="badge badge-pass" style="font-size:0.8rem">02:00–05:00</span>'
    }
  }
}

// ── Feature 2: Nutrition Label ──────────────────────────────────────────────

function renderNutritionLabel() {
  return `
  <div class="dashboard-main" style="grid-template-columns: 1fr 1fr">
    <div class="card">
      <h2 style="margin-bottom: 20px">Look Up Run</h2>
      <div style="display: flex; flex-direction: column; gap: 16px">
        <div class="form-group">
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Run ID</label>
          <input id="nl-run-id" type="text" placeholder="e.g. f7a2d8" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit; font-size: 0.875rem" />
        </div>
        <div style="display: flex; gap: 12px">
          <button id="nl-fetch-btn" class="btn btn-pill" style="flex: 1; justify-content: center; padding: 14px">Generate Label</button>
          <button id="nl-pdf-btn" class="btn" style="background: var(--warm-stone); color: var(--forest-green); border-radius: 100px; padding: 12px 20px">⬇ PDF</button>
        </div>
      </div>

      <div id="nl-result" style="margin-top: 24px"></div>
    </div>

    <div class="card" style="background: linear-gradient(135deg, #1a2920 0%, #2d4038 100%); color: white">
      <div style="border: 3px solid #A8E6CF; border-radius: 12px; padding: 24px; font-family: 'Courier New', monospace">
        <div style="text-align: center; margin-bottom: 16px">
          <div style="font-size: 1.5rem; font-weight: 900; letter-spacing: 2px">NUTRITION FACTS</div>
          <div style="font-size: 0.75rem; color: #A8E6CF">AI Carbon Label · EcoTrack v1.0</div>
          <div style="border-top: 8px solid #A8E6CF; margin: 12px 0"></div>
        </div>

        <div id="nl-label-preview">
          <div style="color: #A8E6CF; font-size: 0.8rem; text-align: center; opacity: 0.7">
            Enter a Run ID and click Generate Label
          </div>
        </div>

        <div style="border-top: 4px solid #A8E6CF; margin-top: 16px; padding-top: 12px; font-size: 0.65rem; color: #A8E6CF; opacity: 0.8">
          SEBI BRSR Scope 2 · EU CSRD ESRS E1 · EcoTrack Green MLOps
        </div>
      </div>

      <div class="ai-box" style="margin-top: 20px; background: rgba(168,230,207,0.1); border-color: rgba(168,230,207,0.3)">
        <div class="ai-header" style="color: #A8E6CF">
          <i data-lucide="info"></i>
          <strong>How to embed in your model file</strong>
        </div>
        <pre style="font-size: 0.7rem; color: #A8E6CF; white-space: pre-wrap; line-height: 1.6">import torch
torch.save(
  {'state_dict': model.state_dict()},
  'model.pt',
  _extra_files={'ecotrack_label.json': label_json}
)</pre>
      </div>
    </div>
  </div>
  `
}

async function initNutritionLabel() {
  const fetchBtn = document.getElementById('nl-fetch-btn')
  const pdfBtn = document.getElementById('nl-pdf-btn')
  const runIdInput = document.getElementById('nl-run-id')
  const resultEl = document.getElementById('nl-result')
  const preview = document.getElementById('nl-label-preview')

  const ratingColors = { A: '#52C41A', B: '#73D13D', C: '#FAAD14', D: '#FF7A45', F: '#E9967A' }

  const fetchLabel = async () => {
    const runId = runIdInput?.value?.trim()
    if (!runId) { alert('Please enter a Run ID'); return }
    if (resultEl) resultEl.innerHTML = '<p style="color: var(--text-secondary)">Fetching...</p>'

    try {
      const res = await fetch(`${API}/nutrition/${encodeURIComponent(runId)}`)
      if (!res.ok) throw new Error(await res.text())
      const label = await res.json()

      const ratingColor = ratingColors[label.carbon_rating] || '#999'
      if (resultEl) resultEl.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 12px">
          <div style="background: var(--warm-stone); border-radius: 12px; padding: 16px">
            <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 8px">CARBON DEBT</div>
            <div style="font-size: 2rem; font-weight: 900; color: var(--forest-green)">${(label.total_co2_kg * 1000).toFixed(2)} g</div>
            <div style="font-size: 0.875rem; color: var(--text-secondary)">${label.human_co2}</div>
          </div>
          <div class="stats-grid" style="grid-template-columns: 1fr 1fr; gap: 12px; margin: 0">
            <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
              <div style="font-size: 0.7rem; font-weight: 600; color: var(--text-secondary)">HARDWARE</div>
              <div style="font-size: 0.875rem; font-weight: 600; margin-top: 4px">${label.gpu_model}</div>
              <div style="font-size: 0.75rem; color: var(--text-secondary)">${label.training_duration_hours.toFixed(2)}h · ${label.gpu_count} GPU</div>
            </div>
            <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
              <div style="font-size: 0.7rem; font-weight: 600; color: var(--text-secondary)">EFFICIENCY</div>
              <div style="font-size: 0.875rem; font-weight: 600; margin-top: 4px">${label.efficiency_score ? label.efficiency_score.toFixed(1) + ' acc/kg' : 'N/A'}</div>
              <div style="font-size: 0.75rem; color: var(--text-secondary)">${label.accuracy ? label.accuracy.toFixed(1) + '% accuracy' : 'No accuracy data'}</div>
            </div>
          </div>
        </div>
      `

      if (preview) preview.innerHTML = `
        <div style="font-size: 2.5rem; font-weight: 900; text-align: center; color: ${ratingColor}">Grade: ${label.carbon_rating}</div>
        <div style="border-bottom: 2px solid rgba(168,230,207,0.3); margin: 12px 0"></div>
        <div style="display: grid; grid-template-columns: 1fr auto; gap: 6px; font-size: 0.8rem">
          <span style="color: #A8E6CF">Model</span><span style="text-align:right">${label.model_name}</span>
          <span style="color: #A8E6CF">Total CO₂</span><span style="text-align:right; font-weight:700">${(label.total_co2_kg * 1000).toFixed(2)}g</span>
          <span style="color: #A8E6CF">Energy</span><span style="text-align:right">${label.total_energy_kwh.toFixed(4)} kWh</span>
          <span style="color: #A8E6CF">Grid</span><span style="text-align:right">${label.grid_region}</span>
          <span style="color: #A8E6CF">Duration</span><span style="text-align:right">${label.training_duration_hours.toFixed(2)}h</span>
          <span style="color: #A8E6CF">GPU</span><span style="text-align:right">${label.gpu_model}</span>
          <span style="color: #A8E6CF">Accuracy</span><span style="text-align:right">${label.accuracy ? label.accuracy.toFixed(1) + '%' : 'N/A'}</span>
          <span style="color: #A8E6CF">Efficiency</span><span style="text-align:right">${label.efficiency_score ? label.efficiency_score.toFixed(1) : 'N/A'}</span>
        </div>
        <div style="border-bottom: 2px solid rgba(168,230,207,0.3); margin: 12px 0"></div>
        <div style="font-size: 0.7rem; color: #A8E6CF">
          ${label.human_co2}<br>
          ≈ ${label.smartphone_charges} 📱 · ≈ ${label.km_driven} km 🚗
        </div>
      `
    } catch (e) {
      if (resultEl) resultEl.innerHTML = `<div class="ai-box"><p style="color: var(--muted-coral)">Error: ${e.message}<br><small>Start the backend server to generate live labels.</small></p></div>`
      if (preview) preview.innerHTML = `<div style="color: var(--muted-coral); font-size: 0.8rem; text-align: center">Backend offline — start with uvicorn app.main:app</div>`
    }
  }

  if (fetchBtn) fetchBtn.addEventListener('click', fetchLabel)
  if (pdfBtn) pdfBtn.addEventListener('click', async () => {
    const runId = runIdInput?.value?.trim()
    if (!runId) { alert('Enter a Run ID first'); return }
    window.open(`${API}/nutrition/${encodeURIComponent(runId)}/pdf`, '_blank')
  })
}

// ── Feature 3: Quantization Gate ──────────────────────────────────────────

function renderQuantGate() {
  return `
  <div class="dashboard-main" style="grid-template-columns: 1fr 1fr">
    <div class="card">
      <h2 style="margin-bottom: 20px">Quantization Analysis</h2>
      <div style="display: flex; flex-direction: column; gap: 16px">
        <div>
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Run ID to analyze</label>
          <input id="qg-run-id" type="text" placeholder="e.g. f7a2d8" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
        </div>
        <div>
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Target Precision</label>
          <div style="display: flex; gap: 12px">
            <label id="qg-label-int8" style="flex: 1; padding: 12px; border: 2px solid var(--forest-green); border-radius: 8px; text-align: center; cursor: pointer; background: var(--neo-mint)">
              <input type="radio" name="precision" value="INT8" checked style="display: none" /> INT8
            </label>
            <label id="qg-label-int4" style="flex: 1; padding: 12px; border: 1px solid var(--warm-stone-dark); border-radius: 8px; text-align: center; cursor: pointer">
              <input type="radio" name="precision" value="INT4" style="display: none" /> INT4
            </label>
            <label id="qg-label-fp16" style="flex: 1; padding: 12px; border: 1px solid var(--warm-stone-dark); border-radius: 8px; text-align: center; cursor: pointer">
              <input type="radio" name="precision" value="FP16" style="display: none" /> FP16
            </label>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <div>
            <label style="display: block; font-size: 0.8rem; font-weight: 600; margin-bottom: 6px">Min Accuracy Retention (%)</label>
            <input id="qg-acc-threshold" type="number" value="98" min="90" max="100" step="0.5" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
          </div>
          <div>
            <label style="display: block; font-size: 0.8rem; font-weight: 600; margin-bottom: 6px">Min Energy Saving (%)</label>
            <input id="qg-energy-threshold" type="number" value="40" min="10" max="90" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
          </div>
        </div>
        <button id="qg-analyze-btn" class="btn btn-pill" style="width: 100%; justify-content: center; padding: 14px">⚡ Analyze Quantization</button>
      </div>

      <div id="qg-result" style="margin-top: 24px"></div>
    </div>

    <div class="card">
      <h2 style="margin-bottom: 16px">How It Works</h2>
      <div style="display: flex; flex-direction: column; gap: 16px">
        <div style="display: grid; grid-template-columns: 40px 1fr; gap: 12px; align-items: start">
          <div style="width:40px;height:40px;border-radius:50%;background:var(--neo-mint);display:flex;align-items:center;justify-content:center;font-weight:700;color:var(--forest-green)">1</div>
          <div><strong>FP32 Baseline</strong><br><span style="font-size:0.8rem;color:var(--text-secondary)">Your model trains at full 32-bit precision. High accuracy, high energy cost.</span></div>
        </div>
        <div style="display: grid; grid-template-columns: 40px 1fr; gap: 12px; align-items: start">
          <div style="width:40px;height:40px;border-radius:50%;background:var(--neo-mint);display:flex;align-items:center;justify-content:center;font-weight:700;color:var(--forest-green)">2</div>
          <div><strong>Quant Gate Analyzes</strong><br><span style="font-size:0.8rem;color:var(--text-secondary)">EcoTrack checks if INT8/INT4 quantization maintains >98% accuracy (architecture-specific).</span></div>
        </div>
        <div style="display: grid; grid-template-columns: 40px 1fr; gap: 12px; align-items: start">
          <div style="width:40px;height:40px;border-radius:50%;background:var(--neo-mint);display:flex;align-items:center;justify-content:center;font-weight:700;color:var(--forest-green)">3</div>
          <div><strong>Auto-Gate Decision</strong><br><span style="font-size:0.8rem;color:var(--text-secondary)">FORCE_QUANTIZED blocks FP32 deployment. RECOMMEND suggests it. KEEP_FP32 passes through.</span></div>
        </div>

        <div class="ai-box" style="margin-top: 8px">
          <div class="ai-header"><i data-lucide="zap"></i><strong>Architecture Sensitivity</strong></div>
          <table style="width: 100%; font-size: 0.8rem">
            <tr><th style="text-align:left">Architecture</th><th>Sensitivity</th><th>Recommended</th></tr>
            <tr><td>ResNet, EfficientNet</td><td>🟢 Low</td><td>INT8</td></tr>
            <tr><td>ViT, BERT</td><td>🟡 Medium</td><td>INT8/FP16</td></tr>
            <tr><td>GPT, LLaMA, Diffusion</td><td>🔴 High</td><td>INT4 (AutoGPTQ)</td></tr>
          </table>
        </div>
      </div>
    </div>
  </div>
  `
}

async function initQuantGate() {
  document.querySelectorAll('input[name="precision"]').forEach(radio => {
    radio.addEventListener('change', () => {
      ['int8','int4','fp16'].forEach(p => {
        const el = document.getElementById(`qg-label-${p}`)
        if (el) { el.style.border = '1px solid var(--warm-stone-dark)'; el.style.background = '' }
      })
      const sel = document.getElementById(`qg-label-${radio.value.toLowerCase()}`)
      if (sel) { sel.style.border = '2px solid var(--forest-green)'; sel.style.background = 'var(--neo-mint)' }
    })
  })

  const analyzeBtn = document.getElementById('qg-analyze-btn')
  if (!analyzeBtn) return

  analyzeBtn.addEventListener('click', async () => {
    const runId = document.getElementById('qg-run-id')?.value?.trim()
    if (!runId) { alert('Enter a Run ID'); return }
    const precision = document.querySelector('input[name="precision"]:checked')?.value || 'INT8'
    const accThreshold = parseFloat(document.getElementById('qg-acc-threshold')?.value || 98)
    const energyThreshold = parseFloat(document.getElementById('qg-energy-threshold')?.value || 40)
    const resultEl = document.getElementById('qg-result')
    if (resultEl) resultEl.innerHTML = '<p style="color:var(--text-secondary)">Analyzing...</p>'

    try {
      const res = await fetch(`${API}/quantization/analyze?target_precision=${precision}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId, accuracy_retention_threshold: accThreshold, energy_reduction_threshold: energyThreshold })
      })
      if (!res.ok) throw new Error(await res.text())
      const analysis = await res.json()

      const verdictColors = { FORCE_QUANTIZED: '#52C41A', RECOMMEND_QUANTIZED: '#FAAD14', KEEP_FP32: '#E9967A' }
      const verdictIcons = { FORCE_QUANTIZED: '✅', RECOMMEND_QUANTIZED: '⚡', KEEP_FP32: '⚠️' }
      const vColor = verdictColors[analysis.verdict] || '#999'

      if (resultEl) resultEl.innerHTML = `
        <div style="background: ${vColor}20; border: 2px solid ${vColor}; border-radius: 12px; padding: 20px; margin-bottom: 16px">
          <div style="font-size: 1.25rem; font-weight: 800; color: ${vColor}">${verdictIcons[analysis.verdict]} ${analysis.verdict}</div>
          <p style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 8px; line-height: 1.5">${analysis.reason}</p>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
            <div style="font-size: 0.7rem; font-weight: 700; color: var(--text-secondary)">ACCURACY RETENTION</div>
            <div style="font-size: 1.5rem; font-weight: 800; color: ${analysis.passes_threshold ? '#52C41A' : '#E9967A'}">${analysis.accuracy_retention_pct.toFixed(1)}%</div>
            <div style="font-size: 0.75rem; color: var(--text-secondary)">threshold: ${accThreshold}%</div>
          </div>
          <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
            <div style="font-size: 0.7rem; font-weight: 700; color: var(--text-secondary)">ENERGY SAVING</div>
            <div style="font-size: 1.5rem; font-weight: 800; color: #52C41A">${analysis.energy_reduction_pct.toFixed(1)}%</div>
            <div style="font-size: 0.75rem; color: var(--text-secondary)">Model size ↓ ${analysis.model_size_reduction_pct.toFixed(0)}%</div>
          </div>
          <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
            <div style="font-size: 0.7rem; font-weight: 700; color: var(--text-secondary)">CO₂ SAVED</div>
            <div style="font-size: 1.5rem; font-weight: 800; color: #52C41A">${analysis.estimated_co2_saved_kg.toFixed(4)} kg</div>
          </div>
          <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
            <div style="font-size: 0.7rem; font-weight: 700; color: var(--text-secondary)">TOOL</div>
            <div style="font-size: 1rem; font-weight: 700; color: var(--forest-green)">${analysis.recommended_tool}</div>
          </div>
        </div>
        <button id="qg-code-btn" class="btn btn-pill" style="width: 100%; justify-content: center; padding: 12px; margin-top: 12px">📋 Get Code Snippet</button>
        <div id="qg-code-out" style="margin-top: 12px"></div>
      `

      document.getElementById('qg-code-btn')?.addEventListener('click', async () => {
        try {
          const cRes = await fetch(`${API}/quantization/code/${encodeURIComponent(runId)}?target_precision=${precision}`)
          const cData = await cRes.json()
          const codeEl = document.getElementById('qg-code-out')
          if (codeEl) codeEl.innerHTML = `<pre style="background:#1e1e1e;color:#a8e6cf;padding:16px;border-radius:8px;font-size:0.75rem;overflow:auto;white-space:pre-wrap">${cData.code_snippet}</pre>`
        } catch {}
      })
    } catch (e) {
      if (resultEl) resultEl.innerHTML = `
        <div class="ai-box">
          <strong style="color: var(--forest-green)">Demo Mode — Backend Offline</strong>
          <p style="font-size:0.875rem;margin-top:8px;line-height:1.5">Start the API server and enter a real Run ID to get live analysis.<br>Schema: ResNets → INT8 ✅ · BERT → INT8/FP16 ✅ · LLaMA → INT4 (AutoGPTQ)</p>
        </div>`
    }
  })
}

// ── Feature 4: Transfer Learning Matchmaker ───────────────────────────────

function renderMatchmaker() {
  return `
  <div class="dashboard-main" style="grid-template-columns: 1fr 1fr">
    <div class="card">
      <h2 style="margin-bottom: 20px">Dataset Profiler</h2>
      <div style="display: flex; flex-direction: column; gap: 16px">
        <div>
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Task Type</label>
          <select id="mm-task" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit">
            <option value="image_classification">Image Classification</option>
            <option value="object_detection">Object Detection</option>
            <option value="nlp_classification">NLP Classification</option>
            <option value="text_generation">Text Generation</option>
            <option value="image_generation">Image Generation</option>
            <option value="speech">Speech Recognition</option>
          </select>
        </div>
        <div>
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Dataset Size (Million Samples)</label>
          <input id="mm-dataset" type="number" placeholder="1.2" step="0.1" min="0.001" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
        </div>
        <div>
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Target Accuracy (%)</label>
          <input id="mm-accuracy" type="number" placeholder="92.0" step="0.5" min="0" max="100" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
        </div>
        <div>
          <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 8px">Your planned model (optional)</label>
          <input id="mm-model" type="text" placeholder="e.g. ResNet-50" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--warm-stone-dark); font-family: inherit" />
        </div>
        <button id="mm-find-btn" class="btn btn-pill" style="width: 100%; justify-content: center; padding: 14px">🔗 Find Match in Zoo</button>
      </div>
    </div>

    <div class="card">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px">
        <h2>Match Result</h2>
        <button id="mm-zoo-btn" class="btn" style="background: var(--warm-stone); color: var(--forest-green); border-radius: 8px; padding: 6px 14px; font-size: 0.8rem; margin-left: auto">Browse Zoo</button>
      </div>
      <div id="mm-result">
        <div class="ai-box">
          <div class="ai-header"><i data-lucide="git-merge"></i><strong>How it works</strong></div>
          <p style="font-size: 0.875rem; line-height: 1.6; color: var(--text-secondary)">
            EcoTrack scans your model history and scores each run by
            <strong>task similarity</strong> + <strong>accuracy proximity</strong>.
            If a good match is found, fine-tuning it typically costs
            <strong>~20% of the CO₂</strong> of training from scratch.
          </p>
          <ul style="margin-top: 12px; font-size: 0.8125rem; color: var(--text-secondary); list-style: none; display: flex; flex-direction: column; gap: 6px">
            <li><i data-lucide="check-circle-2" style="width:14px;color:#52C41A"></i> Infers task type from model names automatically</li>
            <li><i data-lucide="check-circle-2" style="width:14px;color:#52C41A"></i> Calculates projected CO₂ saving in kg</li>
            <li><i data-lucide="check-circle-2" style="width:14px;color:#52C41A"></i> Works on your real run history (no external data)</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
  `
}

async function initMatchmaker() {
  const findBtn = document.getElementById('mm-find-btn')
  const zooBtn = document.getElementById('mm-zoo-btn')
  const resultEl = document.getElementById('mm-result')

  if (findBtn) findBtn.addEventListener('click', async () => {
    const task = document.getElementById('mm-task')?.value
    const dataset = parseFloat(document.getElementById('mm-dataset')?.value || 1)
    const accuracy = parseFloat(document.getElementById('mm-accuracy')?.value || 90)
    const model = document.getElementById('mm-model')?.value?.trim()
    if (resultEl) resultEl.innerHTML = '<p style="color:var(--text-secondary)">Scanning model zoo...</p>'

    try {
      const body = { task_type: task, dataset_size_millions: dataset, target_accuracy: accuracy }
      if (model) body.current_model_name = model
      const res = await fetch(`${API}/matchmaker/find`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      })
      if (!res.ok) throw new Error(await res.text())
      const match = await res.json()

      if (match.match_found) {
        const color = match.similarity_score >= 0.8 ? '#52C41A' : match.similarity_score >= 0.5 ? '#FAAD14' : '#E9967A'
        if (resultEl) resultEl.innerHTML = `
          <div style="background: ${color}15; border: 2px solid ${color}; border-radius: 12px; padding: 20px; margin-bottom: 16px">
            <div style="font-size: 1.25rem; font-weight: 800; color: ${color}">🎯 Match Found!</div>
            <div style="font-size: 1.1rem; font-weight: 700; margin-top: 8px">${match.existing_model_name}</div>
            <div style="margin-top: 4px; font-size: 0.8rem; color: var(--text-secondary)">Run: <code>${match.existing_run_id}</code> · Similarity: ${(match.similarity_score * 100).toFixed(0)}%</div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px">
            <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
              <div style="font-size: 0.7rem; font-weight: 700; color: var(--text-secondary)">MODEL ACCURACY</div>
              <div style="font-size: 1.5rem; font-weight: 800; color: var(--forest-green)">${match.existing_accuracy ? match.existing_accuracy.toFixed(1) + '%' : 'N/A'}</div>
            </div>
            <div style="background: var(--warm-stone); border-radius: 8px; padding: 12px">
              <div style="font-size: 0.7rem; font-weight: 700; color: var(--text-secondary)">CO₂ SAVED</div>
              <div style="font-size: 1.5rem; font-weight: 800; color: #52C41A">${match.potential_carbon_saving_kg?.toFixed(3)} kg</div>
              <div style="font-size: 0.75rem; color: var(--text-secondary)">${match.potential_saving_pct?.toFixed(0)}% saving</div>
            </div>
          </div>
          <div class="ai-box">
            <div class="ai-header"><i data-lucide="zap"></i><strong>Recommendation</strong></div>
            <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.6">${match.recommendation}</p>
          </div>
        `
      } else {
        if (resultEl) resultEl.innerHTML = `
          <div class="ai-box">
            <div class="ai-header"><i data-lucide="info"></i><strong>No Strong Match Found</strong></div>
            <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.6; margin-top: 8px">${match.recommendation}</p>
          </div>`
      }
    } catch (e) {
      if (resultEl) resultEl.innerHTML = `
        <div class="ai-box">
          <strong>Demo Mode — Backend Offline</strong>
          <p style="font-size:0.875rem;color:var(--text-secondary);margin-top:8px">Start the backend to use the matchmaker on your real model history.</p>
          <p style="font-size:0.8rem;color:var(--text-secondary);margin-top:8px"><strong>How it would work:</strong> EcoTrack scans your ${task} runs, finds the closest model by accuracy and task type, and estimates 80% CO₂ savings from fine-tuning.</p>
        </div>`
    }
  })

  if (zooBtn) zooBtn.addEventListener('click', async () => {
    if (!resultEl) return
    try {
      const res = await fetch(`${API}/matchmaker/zoo?limit=20`)
      if (!res.ok) throw new Error('API offline')
      const zoo = await res.json()
      if (!zoo.length) { resultEl.innerHTML = '<p style="color:var(--text-secondary)">No models in zoo yet. Run some training jobs first.</p>'; return }
      resultEl.innerHTML = `
        <table style="width:100%; border-collapse: collapse; font-size: 0.8rem">
          <thead><tr>
            <th style="text-align:left;padding:8px;background:#fafafa;border-bottom:1px solid var(--warm-stone-dark)">Model</th>
            <th style="text-align:left;padding:8px;background:#fafafa;border-bottom:1px solid var(--warm-stone-dark)">Task</th>
            <th style="text-align:left;padding:8px;background:#fafafa;border-bottom:1px solid var(--warm-stone-dark)">Accuracy</th>
            <th style="text-align:left;padding:8px;background:#fafafa;border-bottom:1px solid var(--warm-stone-dark)">CO₂ (kg)</th>
          </tr></thead>
          <tbody>${zoo.map(m => `<tr>
            <td style="padding:8px;border-bottom:1px solid var(--warm-stone)">${m.model_name}</td>
            <td style="padding:8px;border-bottom:1px solid var(--warm-stone)">${m.task_type_guess}</td>
            <td style="padding:8px;border-bottom:1px solid var(--warm-stone)">${m.accuracy ? m.accuracy.toFixed(1) + '%' : 'N/A'}</td>
            <td style="padding:8px;border-bottom:1px solid var(--warm-stone);color:#52C41A">${m.co2_kg.toFixed(4)}</td>
          </tr>`).join('')}</tbody>
        </table>`
    } catch {
      resultEl.innerHTML = '<p style="color:var(--text-secondary)">Start the backend server to browse the zoo.</p>'
    }
  })
}
