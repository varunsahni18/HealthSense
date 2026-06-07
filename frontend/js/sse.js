/* sse.js — two SSE channels:
   /api/events  — bus events (state changes, alerts)
   /api/stream  — high-rate waveform slices */

class HSStreamCls {
  constructor() {
    this.handlers = {};
    this.evt = null;
    this.wf  = null;
    this.lastEventTs = 0;
    this.lastWfTs = 0;
  }
  on(name, fn) { (this.handlers[name] ||= []).push(fn); return this; }
  emit(name, data) { (this.handlers[name] || []).forEach(fn => fn(data)); }

  start() {
    console.log("[HSStream] starting EventSources to /api/events and /api/stream");
    try {
      this.evt = new EventSource("/api/events");
      this.evt.onopen   = () => { console.log("[HSStream] /api/events open"); this.emit("conn", "events"); };
      this.evt.onerror  = (e) => { console.warn("[HSStream] /api/events error", e); this.emit("error", "events"); };
      this.evt.onmessage = (e) => {
        this.lastEventTs = Date.now();
        this.emit("conn", "events");          // ALSO emit on first message (covers onopen-race)
        try {
          const msg = JSON.parse(e.data);
          this.emit(msg.event, msg.data);
          this.emit("any", msg);
        } catch (err) { console.warn("[HSStream] events parse", err); }
      };
    } catch (e) { console.error("[HSStream] events failed", e); }

    try {
      this.wf = new EventSource("/api/stream");
      this.wf.onopen  = () => { console.log("[HSStream] /api/stream open"); this.emit("conn", "stream"); };
      this.wf.onerror = (e) => { console.warn("[HSStream] /api/stream error", e); this.emit("error", "stream"); };
      this.wf.onmessage = (e) => {
        this.lastWfTs = Date.now();
        this.emit("conn", "stream");
        try {
          const msg = JSON.parse(e.data);
          this.emit("waveform", msg);
        } catch (err) { console.warn("[HSStream] waveform parse", err); }
      };
    } catch (e) { console.error("[HSStream] stream failed", e); }
  }

  // Periodic check: if either stream has been silent for >5 s, mark error.
  watchdog() {
    const now = Date.now();
    if (this.lastEventTs && (now - this.lastEventTs) > 5000) this.emit("error", "events-stale");
    if (this.lastWfTs    && (now - this.lastWfTs)    > 5000) this.emit("error", "stream-stale");
  }
}

window.HSStream = new HSStreamCls();
setInterval(() => window.HSStream.watchdog(), 2000);
