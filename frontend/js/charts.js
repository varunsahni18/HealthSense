/* charts.js — uPlot streaming waveform charts.
   We keep ~10 s of samples per channel and shift them left as new data arrives. */

const COLORS = {
  ecg: "#dc2626",  // red — heart
  ppg: "#ea580c",  // orange — pulse
  eeg: "#0891b2",  // teal — brain
  emg: "#7c3aed",  // violet — muscle
  imu: "#16a34a",  // green — motion
};

const SR = { ecg: 250, ppg: 100, eeg: 250, emg: 500, imu: 100 };
const WINDOW_S = 10;

class ModalityChart {
  constructor(elId, modality) {
    this.modality = modality;
    this.fs = SR[modality];
    this.maxLen = this.fs * WINDOW_S;
    this.samples = new Float64Array(this.maxLen);
    this.times = new Float64Array(this.maxLen);
    this.t = 0;
    const el = document.getElementById(elId);
    el.setAttribute("data-label", modality.toUpperCase());
    const opts = {
      width: el.clientWidth,
      height: 84,
      cursor: { show: false },
      legend: { show: false },
      scales: {
        x: { time: false, range: () => [Math.max(0, this.t - WINDOW_S), this.t] },
        y: { auto: true },
      },
      axes: [
        { show: false },
        { show: true, size: 32,
          stroke: "#94a3b8",
          font: "10px 'JetBrains Mono', monospace",
          ticks: { width: 0 },
          grid: { stroke: "#e2e8f0", width: 0.5 },
        },
      ],
      series: [
        {},
        {
          stroke: COLORS[modality],
          width: 1.4,
          paths: uPlot.paths.linear(),
        },
      ],
      padding: [4, 8, 4, 4],
    };
    this.plot = new uPlot(opts, [Array.from(this.times), Array.from(this.samples)], el);
    window.addEventListener("resize", () => {
      this.plot.setSize({ width: el.clientWidth, height: 84 });
    });
  }
  push(arr) {
    if (!arr || !arr.length) return;
    const dt = 1 / this.fs;
    const n = arr.length;
    // shift in-place
    if (n >= this.maxLen) {
      // unlikely but handle
      for (let i = 0; i < this.maxLen; i++) {
        this.samples[i] = arr[arr.length - this.maxLen + i];
        this.t += dt;
        this.times[i] = this.t;
      }
    } else {
      this.samples.copyWithin(0, n);
      this.times.copyWithin(0, n);
      for (let i = 0; i < n; i++) {
        this.t += dt;
        this.samples[this.maxLen - n + i] = arr[i];
        this.times[this.maxLen - n + i] = this.t;
      }
    }
  }
  redraw() {
    this.plot.setData([Array.from(this.times), Array.from(this.samples)]);
  }
}

const charts = {};
function initCharts() {
  charts.ecg = new ModalityChart("chart-ecg", "ecg");
  charts.ppg = new ModalityChart("chart-ppg", "ppg");
  charts.eeg = new ModalityChart("chart-eeg", "eeg");
  charts.emg = new ModalityChart("chart-emg", "emg");
  charts.imu = new ModalityChart("chart-imu", "imu");
}
function pushFrame(payload) {
  charts.ecg.push(payload.ecg);
  charts.ppg.push(payload.ppg);
  charts.eeg.push(payload.eeg);
  charts.emg.push(payload.emg);
  charts.imu.push(payload.imu);
}
function redrawAll() {
  for (const k of Object.keys(charts)) charts[k].redraw();
}

window.HealthSenseCharts = { initCharts, pushFrame, redrawAll };
