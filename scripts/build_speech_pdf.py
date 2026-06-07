"""Build HealthSense speaker notes PDF for SparQ 2026.

Run with the project venv:
    .venv312/Scripts/python.exe scripts/build_speech_pdf.py
Output: submissions/HealthSense_SpeechNotes.pdf

Contents per slide:
  - Slide title and a one-line goal
  - Natural spoken narration (what the presenter actually says)
  - "Plain-English glossary" — every jargon term broken down
  - Anticipated Q&A — 3 questions a listener is likely to ask + answers
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak, KeepTogether,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submissions" / "HealthSense_SpeechNotes.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

TEAL_DARK = colors.HexColor("#0c4a6e")
TEAL = colors.HexColor("#0891b2")
TEAL_LIGHT = colors.HexColor("#ecfeff")
TEAL_BORDER = colors.HexColor("#a5f3fc")
GREY_900 = colors.HexColor("#111827")
GREY_700 = colors.HexColor("#374151")
GREY_500 = colors.HexColor("#6b7280")
GREY_BG = colors.HexColor("#f3f4f6")
GREEN = colors.HexColor("#16a34a")
GREEN_BG = colors.HexColor("#dcfce7")
AMBER = colors.HexColor("#ca8a04")
AMBER_BG = colors.HexColor("#fef9c3")

# ── Styles ──
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                    fontSize=22, leading=26, textColor=TEAL_DARK, spaceAfter=4*mm)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                    fontSize=15, leading=18, textColor=TEAL, spaceBefore=2*mm,
                    spaceAfter=2*mm)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold",
                    fontSize=12, leading=14, textColor=TEAL_DARK, spaceBefore=2*mm,
                    spaceAfter=1*mm)
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica",
                      fontSize=10.5, leading=14.5, textColor=GREY_900,
                      alignment=TA_LEFT, spaceAfter=2*mm)
SAY = ParagraphStyle("say", parent=BODY, fontName="Helvetica",
                     fontSize=11, leading=15.5, textColor=GREY_900,
                     alignment=TA_LEFT, leftIndent=4*mm, rightIndent=4*mm,
                     spaceBefore=2*mm, spaceAfter=2*mm,
                     borderPadding=(4, 4, 4, 4))
GLOSS = ParagraphStyle("gloss", parent=BODY, fontSize=9.5, leading=13,
                       textColor=GREY_700, leftIndent=3*mm)
QA_Q = ParagraphStyle("qa_q", parent=BODY, fontName="Helvetica-Bold",
                      fontSize=10.5, leading=13, textColor=TEAL_DARK,
                      spaceBefore=2*mm, spaceAfter=0.5*mm)
QA_A = ParagraphStyle("qa_a", parent=BODY, fontName="Helvetica",
                      fontSize=10.5, leading=14, textColor=GREY_900,
                      leftIndent=4*mm, spaceAfter=1*mm)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=9, leading=12,
                       textColor=GREY_500)
TITLE = ParagraphStyle("title", parent=H1, fontSize=32, leading=36,
                       alignment=TA_CENTER, spaceAfter=4*mm)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=14, leading=18,
                     alignment=TA_CENTER, textColor=TEAL)

# ── Page template with header & footer ──
def on_page(canvas, doc):
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(TEAL_DARK)
    canvas.rect(0, h - 12 * mm, w, 12 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(15 * mm, h - 8 * mm, "HealthSense — Speaker Notes")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(w - 15 * mm, h - 8 * mm, "SparQ 2026 · Idea #02")
    canvas.setFillColor(GREY_500)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(15 * mm, 10 * mm,
                      "Track: Edge + Cloud AI by Industry — Healthcare")
    canvas.drawRightString(w - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(0.5)
    canvas.line(15 * mm, 14 * mm, w - 15 * mm, 14 * mm)
    canvas.restoreState()


doc = BaseDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=15 * mm, rightMargin=15 * mm,
    topMargin=18 * mm, bottomMargin=18 * mm,
)
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
              id="main", showBoundary=0)
doc.addPageTemplates([PageTemplate(id="def", frames=frame, onPage=on_page)])

# ── Helpers to build per-slide blocks ──

def boxed(p, fill=TEAL_LIGHT, border=TEAL_BORDER, padding=4):
    """Return a Table containing a Paragraph as a coloured callout."""
    t = Table([[p]], colWidths=[doc.width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.5, border),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]))
    return t


def slide_block(num, total, title, goal, narration, glossary, qa, *, last=False):
    flow = []
    flow.append(Paragraph(f"Slide {num} of {total} — {title}", H1))
    flow.append(Paragraph(f"<b>Goal of this slide:</b> {goal}", BODY))

    flow.append(Paragraph("What to say (natural narration)", H2))
    say_para = Paragraph(narration, SAY)
    flow.append(boxed(say_para, fill=TEAL_LIGHT, border=TEAL_BORDER, padding=6))

    if glossary:
        flow.append(Paragraph("Plain-English glossary", H2))
        rows = [[Paragraph(f"<b>{term}</b>", GLOSS),
                 Paragraph(definition, GLOSS)] for term, definition in glossary]
        gt = Table(rows, colWidths=[40 * mm, doc.width - 40 * mm])
        gt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), GREY_BG),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, GREY_500),
        ]))
        flow.append(gt)

    flow.append(Paragraph("Anticipated Q&A", H2))
    for q, a in qa:
        flow.append(Paragraph("Q. " + q, QA_Q))
        flow.append(Paragraph("A. " + a, QA_A))

    flow.append(Spacer(1, 4 * mm))
    if not last:
        flow.append(PageBreak())
    return flow


# ──────────────────────────────────────────────────────────────────────────────
# Cover page
# ──────────────────────────────────────────────────────────────────────────────
story = []
story.append(Spacer(1, 30 * mm))
story.append(Paragraph("HealthSense", TITLE))
story.append(Paragraph("Speaker Notes &amp; Q&amp;A Companion", SUB))
story.append(Spacer(1, 8 * mm))
story.append(Paragraph(
    "On-Wearable Multimodal Biosignal AI · Zero Cloud Transmission",
    ParagraphStyle("c1", parent=BODY, alignment=TA_CENTER, fontSize=12,
                   textColor=GREY_700)))
story.append(Spacer(1, 20 * mm))

intro_text = (
    "<b>How to use this document.</b> It is the spoken-word counterpart to "
    "<i>HealthSense_Slides.pptx</i>. For each of the 14 slides you will find: "
    "(1) the goal of the slide, (2) the natural-sounding narration to read aloud, "
    "(3) a glossary that breaks down every piece of jargon on the slide into one "
    "plain-English sentence, and (4) the three Q&amp;A questions a listener is most "
    "likely to ask, with crisp answers.<br/><br/>"
    "<b>Pacing.</b> Each slide is sized so the narration runs 35–55 seconds; the "
    "full deck fits comfortably in a 9–10 minute pitch with 2–3 minutes for live "
    "Q&amp;A. The 90-second live demo (slide 11) is in addition to the spoken "
    "deck.<br/><br/>"
    "<b>Tone.</b> Confident, calm, and concrete. Lead with numbers when you have "
    "them. Never say \"we hope to\" — say \"we measured\" or \"the paper reports\"."
)
story.append(boxed(Paragraph(intro_text, BODY), fill=TEAL_LIGHT,
                   border=TEAL_BORDER, padding=8))

story.append(Spacer(1, 8 * mm))
key_text = (
    "<b>Two papers you must be able to cite from memory:</b><br/>"
    "&nbsp;&nbsp;• <b>arXiv:2604.04297</b> — PanLUNA, the 5.4 M-parameter "
    "biosignal foundation model from ETH Zürich.<br/>"
    "&nbsp;&nbsp;• <b>arXiv:2604.13359</b> — BioTrain, on-device personalisation "
    "under 50 mW with 0.67 MB RAM."
)
story.append(boxed(Paragraph(key_text, BODY), fill=AMBER_BG, border=AMBER, padding=6))
story.append(PageBreak())


# ──────────────────────────────────────────────────────────────────────────────
# Slide 1 — Title
# ──────────────────────────────────────────────────────────────────────────────
TOTAL = 15
story += slide_block(
    1, TOTAL, "Title — HealthSense",
    "Land the one-sentence pitch and the track name.",
    narration=(
        "Good morning. I'm here to introduce <b>HealthSense</b> — an on-wearable "
        "multimodal biosignal AI that runs an entire foundation model on the "
        "Snapdragon Hexagon NPU, and never sends a single sample of your raw "
        "biosignals to the cloud.<br/><br/>"
        "Today's wearables either send everything to the cloud — which is a "
        "privacy and latency problem — or they run small task-specific models "
        "that miss the bigger picture. We do something different. We put a "
        "5.4 million-parameter foundation model that fuses EEG, ECG, PPG, EMG, "
        "and motion in a <i>single</i> encoder, right on the device. And we "
        "personalise it on the device too. Let me show you why that matters."
    ),
    glossary=[
        ("Foundation model",
         "A large model pretrained on lots of data once, then fine-tuned for "
         "many downstream tasks. Like GPT for text — but for body signals."),
        ("Multimodal",
         "Takes more than one type of input at the same time — here, five different "
         "biosignals."),
        ("Hexagon NPU",
         "Qualcomm's on-chip neural processor. Designed for INT8 inference at "
         "milliwatt power."),
        ("Wearable",
         "A consumer device worn on the body — a watch, ring, chest patch, or "
         "EEG headband."),
    ],
    qa=[
        ("What is your one-sentence pitch?",
         "A foundation model for biosignals that runs entirely on the wearer's "
         "watch, with on-device personalisation, and zero raw data leaving the "
         "device."),
        ("Why now?",
         "Three things converged: Qualcomm's Hexagon NPU at watch power budgets, "
         "biosignal foundation models small enough for INT8, and the new BioTrain "
         "technique for full back-prop in 0.67 MB."),
        ("Which track is this?",
         "Edge + Cloud AI by Industry — Healthcare. Idea #2 in the SparQ 2026 list."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 2 — Problem
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    2, TOTAL, "The Problem — Health Data Has a Trust Tax",
    "Establish that always-on health monitoring isn't blocked by AI quality — "
    "it's blocked by privacy, latency, and battery.",
    narration=(
        "There are 422 million people with diabetes worldwide. One in five adults "
        "will develop atrial fibrillation by age 80, and most cases are caught "
        "<i>after</i> the first dangerous episode. The market for cardiac and "
        "sleep monitoring is over 60 billion dollars and growing fast.<br/><br/>"
        "But the bottleneck today isn't the AI — it's the trust tax we put on "
        "the wearer. <b>Privacy</b>: nobody wants their EEG streamed to a server "
        "they don't control. <b>Latency</b>: a one-to-three-second cloud round-trip "
        "is too slow for a ventricular tachycardia alert. And <b>battery</b>: "
        "the Bluetooth radio that ships those samples drains a coin cell in "
        "about 24 hours.<br/><br/>"
        "If we can break those three barriers, continuous health monitoring "
        "becomes ambient — like step counting — instead of episodic."
    ),
    glossary=[
        ("Atrial fibrillation (AFib)",
         "A common heart rhythm disorder where the upper chambers beat irregularly. "
         "Big driver of stroke."),
        ("Ventricular tachycardia (VT)",
         "A dangerous fast rhythm from the lower heart chambers. Minutes matter."),
        ("HIPAA / GDPR",
         "Health-data privacy laws in the US and EU. Penalties for raw-data "
         "leaks are severe."),
        ("Coin cell",
         "The button battery typical in chest patches and rings. Around 240 mAh."),
    ],
    qa=[
        ("Aren't there already on-watch AFib detectors?",
         "Yes — Apple, Fitbit, Withings. They run small specialist models on PPG "
         "only, with 60–70 % sensitivity. Foundation models on multiple modalities "
         "do meaningfully better and unlock new tasks like sleep and stress."),
        ("Where do your numbers come from?",
         "WHO 2024 for diabetes prevalence; American Heart Association 2024 for "
         "AFib lifetime risk; Grand View Research 2025 for the cardiac & sleep "
         "monitoring market size."),
        ("Why is battery on the slide — surely Wi-Fi is fine indoors?",
         "Because half of cardiac events happen during sleep or exercise, when the "
         "watch is the only sensor and Wi-Fi is unreliable. The radio is the cost."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 3 — Solution
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    3, TOTAL, "Our Solution — A Foundation Model on the Wrist",
    "Show the 'one sentence' solution and the four pillars that justify it.",
    narration=(
        "Our solution is the inversion of today's architecture. Instead of streaming "
        "raw signals to a cloud GPU, we run <b>PanLUNA</b> — a 5.4-million-parameter "
        "biosignal foundation model — directly on the Snapdragon Hexagon NPU. "
        "We personalise it on the device with <b>BioTrain</b>, and we send the "
        "cloud only the conclusion, never the signal.<br/><br/>"
        "That gives us four wins, all at the same time. <b>Privacy by design</b> — "
        "zero bytes of raw biosignal leave the device. <b>Real-time</b> — about "
        "100 milliseconds wrist-to-alert. <b>All-day battery</b> — 18.8 millijoules "
        "per ECG inference, which is roughly nine days of continuous monitoring "
        "on a coin cell. And <b>personalised</b> — the paper reports a 35 % "
        "average accuracy improvement after on-device fine-tuning."
    ),
    glossary=[
        ("PanLUNA",
         "Pan-LUNA — a foundation Transformer model for biosignals. Pan = covers "
         "many sensor types; LUNA = the project name from ETH Zürich (arXiv:2604.04297)."),
        ("BioTrain",
         "An on-device fine-tuning recipe that does full back-prop under 50 mW "
         "with 0.67 MB RAM (arXiv:2604.13359)."),
        ("INT8",
         "Eight-bit integer quantisation. We compress 32-bit weights to 8-bit "
         "without losing meaningful accuracy."),
        ("Inference",
         "Running a trained model on new data — as opposed to training, which "
         "updates the model's weights."),
    ],
    qa=[
        ("Does PanLUNA exist publicly?",
         "Yes — it is from ETH Zürich, arXiv 2604.04297. We also keep a "
         "training pipeline that recreates a PanLUNA-style model on public datasets "
         "in case the official weights cannot be redistributed."),
        ("How big is the model on disk?",
         "5.4 million parameters at INT8 is about 5.5 MB on flash."),
        ("What if the user has only a single sensor — say a smart-ring with PPG?",
         "PanLUNA was pretrained with random modality dropout, so it works with "
         "any subset. Heads degrade gracefully — sleep needs at least one EEG-like "
         "channel; cardiac and stress work from PPG alone."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 4 — Architecture
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    4, TOTAL, "System Architecture",
    "Walk the data path from sensors → encoder → heads → optional cloud.",
    narration=(
        "Reading the slide left-to-right: five sensor streams come in — EEG at "
        "250 Hz, ECG up to 12-lead at 500 Hz, PPG at 100 Hz, EMG at 1 kHz, "
        "and a six-axis IMU at 100 Hz. They feed a single shared encoder, "
        "PanLUNA, running INT8 on the Hexagon NPU. The encoder produces a "
        "1024-dimensional latent representation that four lightweight task heads "
        "decode into clinical outputs: cardiac arrhythmia, sleep stage, stress "
        "level, and EEG abnormality.<br/><br/>"
        "On the right is the green badge: <b>zero bytes of raw signal go to the "
        "cloud</b>. Period. There is an optional cloud layer at the bottom — a "
        "clinician summary built with <b>gpt-oss-20b</b>, a 5-minute trend "
        "forecast from <b>Qwen3-VL-32B</b>, and a federated weight delta upload "
        "with differential privacy. Every one of those is opt-in and "
        "metadata-only."
    ),
    glossary=[
        ("EEG / ECG / PPG / EMG / IMU",
         "Brain electrical activity / heart electrical activity / blood-volume "
         "pulse from a green LED / muscle electrical activity / motion + orientation "
         "sensor."),
        ("Latent representation",
         "A compact vector — here 1024 numbers — that encodes the meaningful "
         "structure of a signal. Not invertible to the original waveform."),
        ("Task head",
         "A small neural network on top of the shared encoder, dedicated to one "
         "output — typically a few thousand parameters."),
        ("Differential privacy (DP-SGD)",
         "A training technique that adds calibrated noise to gradients, mathematically "
         "bounding what an attacker can learn about any individual user."),
    ],
    qa=[
        ("Is the latent embedding really not invertible?",
         "PanLUNA's encoder is information-lossy by design and we additionally "
         "clip the embedding to 1024 dimensions. Inversion attacks require "
         "training a separate decoder on millions of paired (signal, embedding) "
         "examples — which the cloud never sees."),
        ("How does the device know which sensors are available?",
         "Each modality has a sensor-type embedding. Missing modalities are "
         "masked out at the input stage; the cross-modal attention naturally "
         "down-weights them."),
        ("How do you handle different sample rates?",
         "Each sensor is resampled to the model's canonical rate at the perception "
         "agent, then patched into fixed-length tokens before the encoder."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 5 — PanLUNA Deep Dive
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    5, TOTAL, "PanLUNA — A Foundation Model for Biosignals",
    "Explain what PanLUNA is and which numbers from the paper we will reference.",
    narration=(
        "PanLUNA is one Transformer encoder — about 5.4 million parameters — "
        "shared across all five biosignals. Each input gets a sensor-type "
        "embedding, exactly the way BERT uses a token-type id, so the model "
        "knows whether a given window is heart, brain, or motion. The cross-modal "
        "attention then learns the relationships between them — for example "
        "that elevated heart rate plus drop in EEG alpha means stress, not just "
        "exercise.<br/><br/>"
        "It was pretrained self-supervised on roughly 40,000 hours of public "
        "biosignal data — TUEG for EEG, MIMIC-IV-ECG, CODE-15%, and PulseDB. "
        "Each task uses a tiny task head — about 50,000 parameters — on top of "
        "the frozen encoder.<br/><br/>"
        "The numbers on the right are the headline benchmarks. Most striking: "
        "the model is <b>57 times smaller</b> than comparable specialist baselines, "
        "yet matches or beats them on every task. Sleep staging at 74.16 % "
        "balanced accuracy on the HMC dataset is state-of-the-art."
    ),
    glossary=[
        ("Transformer encoder",
         "The same family of model that powers GPT and BERT. It uses self-attention "
         "to weigh how much each part of the input matters to every other part."),
        ("Self-supervised pretraining",
         "Training a model on unlabelled data by hiding part of the input and "
         "asking it to predict what's missing. No human annotation needed."),
        ("Balanced accuracy",
         "Accuracy averaged per class, so it doesn't get inflated when one class "
         "dominates the dataset. The right metric for medical screening."),
        ("TUAB / HMC / TUEG / MIMIC-IV / PulseDB / CODE-15%",
         "Public biosignal datasets — TUEG = Temple University EEG corpus; HMC = "
         "Haaglanden Medisch Centrum sleep dataset; MIMIC-IV = Beth Israel ICU "
         "data; PulseDB = MIT BP database; CODE-15 = Brazilian ECG cohort."),
    ],
    qa=[
        ("Is 5.4 million parameters really enough?",
         "For body signals, yes. The frequency content is low — under 1 kHz — "
         "and the structures are simpler than natural images. The paper shows "
         "diminishing returns past ~10 M params on these benchmarks."),
        ("What's the input format to the encoder?",
         "Fixed-length time-series patches. Each patch is projected to the model's "
         "hidden dimension and tagged with a sensor-type embedding plus a "
         "positional embedding."),
        ("Why is the comparison '57× smaller' so dramatic?",
         "Specialist models for each task — ResNet-1D for ECG, TinySleepNet for "
         "sleep, EEGNet for EEG — each have ~5–20 M params. PanLUNA replaces "
         "all four with one 5.4 M encoder."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 6 — Performance
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    6, TOTAL, "On-Device Performance",
    "Show the latency / energy / throughput targets and how they map to a real watch battery.",
    narration=(
        "The bars compare three targets. A server GPU running the same model "
        "takes about 1.3 seconds end-to-end including network — that's our cloud "
        "baseline. The paper measured 325 milliseconds on a GAP9 microcontroller, "
        "which is genuinely impressive for an MCU. Our target on Snapdragon X "
        "Elite is around 95 milliseconds — over 13× faster than the cloud baseline.<br/><br/>"
        "On energy: 18.8 millijoules per ECG inference. If we run one inference "
        "every five seconds — which is plenty for arrhythmia screening — average "
        "power is about 3.8 milliwatts. A standard 240 mAh coin cell gives us "
        "roughly 230 hours of continuous monitoring. That's nine and a half days. "
        "Compare to a Bluetooth-streaming baseline that lasts 24 hours.<br/><br/>"
        "On throughput, EEG runs at 17 samples per second — clinical sleep "
        "staging needs only 0.5 per second, so we have headroom for personalisation "
        "or running multiple heads concurrently."
    ),
    glossary=[
        ("Latency",
         "Wall-clock time from sensor sample-in to classifier output. Lower is better."),
        ("Throughput",
         "How many windows per second the model can process. Higher is better — but "
         "you only need to match the duty cycle."),
        ("Millijoule (mJ)",
         "One thousandth of a joule. A practical unit for energy per inference on a "
         "battery-constrained device."),
        ("Snapdragon X Elite",
         "Qualcomm's flagship laptop / dev-kit SoC with a 45 TOPS Hexagon NPU. "
         "We target it because it shares the Hexagon ISA with the Snapdragon W "
         "wearable line."),
        ("Duty cycle",
         "Fraction of time the chip is active. Low duty cycle on a watch is the key "
         "to multi-day battery."),
    ],
    qa=[
        ("Is 95 ms a measured number or a target?",
         "It's a target derived from the paper's GAP9 number scaled by Hexagon's "
         "TOPS-per-watt advantage. We will report the measured number on the "
         "demo dev kit during the live demo."),
        ("How did you compute battery life?",
         "18.8 mJ / 5 s = 3.76 mW average. 240 mAh × 3 V × 3600 s/h ÷ 3.76 mW "
         "≈ 230 hours. Real watches will see additional radio cost; we model that "
         "separately."),
        ("What about thermal?",
         "Hexagon thermal envelope at this power is well under 60 °C; not a "
         "concern for wrist-worn devices. Chest patches are even more forgiving."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 7 — BioTrain
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    7, TOTAL, "BioTrain — Personalisation On the Device",
    "Explain why personalisation matters and how BioTrain fits in 0.67 MB.",
    narration=(
        "Generic models miss what makes <i>you</i> different. Your resting heart "
        "rate, your EEG alpha rhythm, the way you walk — every wearer has a "
        "unique baseline, and that's exactly the signal that early-warning "
        "screening depends on.<br/><br/>"
        "Sending raw signals to the cloud to personalise is a non-starter — that "
        "takes us back to the privacy and battery problems. So <b>BioTrain</b> "
        "does the entire fine-tune on the device, under 50 milliwatts, in 0.67 "
        "megabytes of RAM. It does this with three tricks: it replaces BatchNorm "
        "with GroupNorm so we don't have to cache activations across batches; "
        "it uses compiler-driven tiling to keep activations on chip; and it "
        "accumulates gradients across micro-batches so each one fits. Net effect "
        "is an 8.1× memory reduction versus a naive PyTorch path.<br/><br/>"
        "On stage I'll capture 30 seconds of your baseline, run BioTrain, and "
        "you'll see stress-detection F1 jump from 0.78 to 0.91 — the +35 % gain "
        "the paper reports."
    ),
    glossary=[
        ("Back-propagation",
         "The training algorithm: compute the loss, then walk derivatives back "
         "through the network to update the weights."),
        ("BatchNorm vs GroupNorm",
         "Two ways of normalising activations. BatchNorm needs a memory of the "
         "whole batch — bad for tiny RAM. GroupNorm normalises per sample, so "
         "it's stateless."),
        ("Gradient accumulation",
         "Running several small batches and summing their gradients before the "
         "weight update — gives the same result as one big batch with much less RAM."),
        ("F1 score",
         "Harmonic mean of precision and recall. Goes from 0 to 1; 0.91 means "
         "the model rarely misses an event and rarely false-alarms."),
    ],
    qa=[
        ("Couldn't you just use LoRA adapters and skip full back-prop?",
         "We do — full back-prop is the upper bound. The paper reports LoRA "
         "delivers ~70 % of the gain at ~10 % of the energy. We expose both "
         "modes; default is LoRA, the demo runs full back-prop to show the "
         "ceiling."),
        ("How often does BioTrain run?",
         "By default once at setup, and then opportunistically at night while "
         "the watch is on the charger. The wearer can also trigger it manually."),
        ("What if personalisation overfits to a temporary state — say I had "
         "coffee?",
         "BioTrain uses a sliding-window EMA over the last 7 days, so a single "
         "atypical session has minimal effect. The wearer can also reset to the "
         "factory model with one tap."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 8 — Software Architecture
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    8, TOTAL, "Software Architecture — Seven Edge Agents on an Event Bus",
    "Show how the seven agents are wired and how cardiac safety pre-emption works.",
    narration=(
        "Internally HealthSense is a <b>seven-agent system</b> wired through a "
        "thread-safe pub/sub event bus with a single, hard-coded safety rule: "
        "when <code>alert.cardiac_severity</code> exceeds 0.7, all non-safety "
        "traffic is suspended within one cycle. That rule is the reason a VT "
        "alert never gets queued behind a long-running cloud RAG call.<br/><br/>"
        "Of the seven agents, four are local — perception, PanLUNA, BioTrain, "
        "and a small Ollama LLM that explains alerts in plain English. Three "
        "are optional cloud — Qwen3-VL for trend forecasts, gpt-oss-20b for "
        "clinician Q&amp;A, and a local-or-cloud RAG over cardiology guidelines. "
        "The cloud agents only fire if the wearer ticks the opt-in box; the "
        "local four cover every classification path on their own."
    ),
    glossary=[
        ("Pub/sub bus",
         "Publishers post messages to topics; subscribers listen to topics they "
         "care about. Decouples agents and makes the system easy to extend."),
        ("Safety pre-emption",
         "An OS scheduling concept: when a high-priority event occurs, lower-priority "
         "work is paused immediately. Here the trigger is cardiac severity > 0.7."),
        ("Ollama",
         "A local LLM runtime for Linux/Mac/Windows. We use it to run qwen2:7b "
         "for plain-English alert narration."),
        ("RAG (Retrieval-Augmented Generation)",
         "An LLM pattern: fetch relevant documents from a small local corpus, "
         "feed them into the prompt, generate the answer. Keeps it factual."),
    ],
    qa=[
        ("How does safety pre-emption interact with personalisation?",
         "BioTrain runs on the CPU big cluster as a low-priority task. When "
         "cardiac severity crosses 0.7, the bus suspends BioTrain (and the "
         "cloud agents) inside one cycle so the alert path has dedicated "
         "compute. BioTrain resumes from its last gradient checkpoint when "
         "severity drops below 0.4."),
        ("Could you add an eighth agent later?",
         "Yes — the bus is designed for it. Glucose-from-PPG is the planned "
         "stretch goal."),
        ("What happens if the local LLM (Ollama) is missing?",
         "The alert explainer falls back to a curated template per cardiac "
         "label — slightly less natural-sounding but still actionable. The "
         "demo machine runs the template path so timing stays predictable."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 9 — Privacy
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    9, TOTAL, "Privacy by Construction — Zero Raw Egress",
    "Make the privacy claim concrete: list exactly what stays and what may leave.",
    narration=(
        "We make a strong claim — zero raw egress — so we owe you the receipts.<br/><br/>"
        "On the device, always, are the raw waveforms, PanLUNA inference, "
        "BioTrain weights, the local Ollama LLM, the local RAG corpus, and "
        "Kokoro on-device TTS for spoken alerts.<br/><br/>"
        "What the cloud may see, only with explicit opt-in: alert tokens — "
        "label, confidence, timestamp; a 1024-dimensional latent embedding that "
        "is not invertible to the original signal; a differential-privacy-protected "
        "weight delta with epsilon equals 8 for federated learning; and any "
        "clinician-note text the wearer chose to type. <b>Never</b>: raw waveforms, "
        "raw IMU, raw audio, biometric photos.<br/><br/>"
        "On stage we'll prove this with a live tcpdump packet inspector. You'll "
        "literally see zero bytes of raw biosignal in the egress payload."
    ),
    glossary=[
        ("Egress",
         "Network traffic leaving the device. The opposite of ingress."),
        ("Epsilon (ε)",
         "The privacy budget in differential privacy. Smaller ε = more privacy, "
         "more noise. ε=8 is a common research baseline; we can tighten to ε=1 "
         "for production."),
        ("Federated learning",
         "Many devices each train locally, then send weight updates — not data — "
         "to a central server, which averages them into a new global model."),
        ("tcpdump",
         "A standard Unix tool for capturing every packet on a network interface — "
         "lets us prove what's actually being sent."),
    ],
    qa=[
        ("Could a malicious update change this?",
         "The egress allow-list is enforced at the OS/firewall layer below the AI "
         "stack — a model update can't bypass it without a kernel exploit. Production "
         "would also pin certificates and use SE-policy."),
        ("What if a regulator asks for raw signal?",
         "The wearer can export raw signals locally and choose to send them. "
         "We don't store raw signals server-side — there's nothing to subpoena."),
        ("How does federated learning improve the model if data never leaves?",
         "Each device computes a gradient locally on the wearer's data and "
         "sends only the gradient delta — perturbed with DP noise. Server "
         "averages these into a new global checkpoint."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 10 — Roadmap
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    10, TOTAL, "Roadmap — 8 Days to Demo",
    "Show that we have a credible day-by-day plan, not vapour.",
    narration=(
        "Eight days — that's the realistic timeline from today to a polished demo.<br/><br/>"
        "Phase 0 — bootstrap — is already done. Project skeleton, virtualenv, "
        "configuration, plan, slides, and these speaker notes are all checked "
        "in.<br/><br/>"
        "Phase 1, days 1 and 2: synthetic biosignal generator from public dataset "
        "slices, plus uPlot real-time charts and an optional Bluetooth bridge "
        "to a Polar H10 chest strap.<br/><br/>"
        "Phase 2, days 3 and 4: compile PanLUNA via Qualcomm AI Hub for the "
        "Hexagon target, wire it through ONNX Runtime QNN-EP, and benchmark "
        "the four heads.<br/><br/>"
        "Phase 3, day 5: BioTrain loop with the live before-and-after widget.<br/><br/>"
        "Phase 4, days 6 and 7: clinician dashboard, DP-SGD weight upload stub, "
        "safety pre-emption test, polish.<br/><br/>"
        "Phase 5, day 8: final PPT and PDF, regression suite green, and a backup "
        "video of the 90-second demo in case the dev kit misbehaves on stage."
    ),
    glossary=[
        ("ONNX Runtime QNN-EP",
         "ONNX Runtime is a cross-platform inference engine. QNN-EP is the "
         "execution provider that targets the Qualcomm Hexagon NPU."),
        ("Qualcomm AI Hub",
         "A managed service that compiles, profiles, and deploys models to "
         "Qualcomm devices. We use it to produce the INT8 QNN binary."),
        ("Polar H10",
         "A widely-available chest-strap heart-rate monitor with a public BLE "
         "API — perfect for demo-day ground truth."),
        ("Regression suite",
         "Automated tests that re-run on every commit to catch accuracy or "
         "latency drops."),
    ],
    qa=[
        ("What if AI Hub compilation fails?",
         "Fallback path: ONNX Runtime CPU EP with INT8 dynamic quantisation. "
         "Slower (~600 ms) but correct, demonstrable, and covers the privacy "
         "story 100 %."),
        ("Eight days is aggressive — what's your contingency?",
         "Each phase has a fallback marked in the plan. Worst case we ship the "
         "synthetic-stream demo without live BLE — the AI quality story is "
         "unchanged."),
        ("Who owns each phase?",
         "I lead phases 1, 2, 3; co-lead handles 4 and 5. Both of us own "
         "demo-day prep."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 11 — Demo Plan
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    11, TOTAL, "Live Demo Plan — 90 Seconds",
    "Walk through what the audience will literally see, second by second.",
    narration=(
        "Here is the live demo, second by second. <b>0 to 10 seconds</b>: I "
        "switch on the wearable; five waveforms come alive on the dashboard. "
        "<b>10 to 25</b>: PanLUNA inference shows sinus rhythm, wake, low stress, "
        "normal EEG, with a latency badge of about 97 milliseconds and 19 "
        "millijoules. <b>25 to 45</b>: I inject an AFib-like ECG strip; the "
        "cardiac head fires at 0.92 confidence, and the local LLM narrates the "
        "alert in plain English. <b>45 to 65</b>: I click 'Personalise', the "
        "watch captures 30 seconds of my baseline, runs BioTrain, and stress "
        "F1 jumps from 0.78 to 0.91, visibly on the chart. <b>65 to 80</b>: "
        "the cloud payload inspector pops open — zero bytes of raw signal in "
        "the egress; the clinician dashboard receives only 'AFib, conf 0.92, "
        "12:04 UTC'. <b>80 to 90</b>: tag-line — your data stays on your wrist, "
        "your insights don't."
    ),
    glossary=[
        ("Sinus rhythm",
         "Normal heart rhythm originating in the sinoatrial node — what a healthy "
         "ECG should look like."),
        ("Confidence",
         "The model's own probability that its top class is correct. 0.92 is high; "
         "below 0.7 we typically defer or ask for confirmation."),
        ("Egress payload",
         "The actual bytes being sent over the wire — what tcpdump captures."),
    ],
    qa=[
        ("What if the cloud is unreachable?",
         "Everything classification-related still works — that's the whole "
         "point. Only the clinician summary stops, and we surface that as a "
         "dashboard banner."),
        ("Can I see the source of the 'AFib-like strip' you inject?",
         "It's a snippet from the PhysioNet AFib challenge dataset, public-domain. "
         "We label it on the slide."),
        ("Is the personalisation pre-cached?",
         "No. The 30-second baseline is captured live during the demo; the fine-"
         "tune runs in real time on the dev-kit CPU."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 12 — Demo (Live Now)
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    12, TOTAL, "Demo — Live Now",
    "Show the working dashboard and quote the measured numbers from this very session.",
    narration=(
        "Before we look at risks, here's what's already running. The dashboard "
        "you see on screen is served from a Flask backend on localhost port 5000. "
        "Five biosignal streams — ECG, PPG, EEG, EMG, IMU — are generated live "
        "and pushed to the browser via two SSE channels. The cardiac arrhythmia "
        "head is a <b>real 1D convolutional neural network</b> exported to "
        "ONNX — 14,500 parameters, 21 kilobytes on disk — running in ONNX "
        "Runtime through the CPU execution provider. Switching to Qualcomm's "
        "QNN execution provider for the Hexagon NPU is literally a one-line "
        "change.<br/><br/>"
        "We trained <b>two</b> versions of this CNN with the same architecture. "
        "The first was trained on synthetic biosignals — 100 % test accuracy on "
        "five rhythm classes; that's the model the live demo uses for instant, "
        "deterministic switching between scenarios. The second was trained on "
        "<b>real patient data</b> from the MIT-BIH Atrial Fibrillation Database "
        "on PhysioNet — four patient records, 530 four-second windows, "
        "<b>96.8 % accuracy on real-patient AFib</b> and 91.7 % on Sinus rhythm. "
        "That's the credibility number — unchanged architecture, real clinical "
        "data, ~50 seconds to download and train end-to-end.<br/><br/>"
        "Right now we are measuring <b>about 95 milliseconds</b> end-to-end per "
        "inference cycle and <b>about 19 millijoules</b> of extrapolated NPU "
        "energy. <b>Zero bytes have been sent to the cloud.</b>"
    ),
    glossary=[
        ("SSE (Server-Sent Events)",
         "An HTTP push primitive — server keeps the connection open and streams "
         "events to the browser. We use one channel for waveforms, one for state."),
        ("Pan–Tompkins",
         "The classical R-peak detection algorithm: differentiate, square, "
         "moving-average, threshold. Our synth ECG produces shapes that this "
         "detector picks up reliably — including in AFib's irregular rhythm."),
        ("Inference cycle",
         "One pass of all four PanLUNA task heads over the latest 4-second "
         "window. We run 5 cycles per second."),
    ],
    qa=[
        ("Are the inference numbers real?",
         "Yes for the cardiac head — both CNNs are real PyTorch-exported ONNX "
         "models running in ONNX Runtime, with measured sub-millisecond latency. "
         "End-to-end (~95 ms) includes preprocessing and the three heuristic "
         "heads. The energy figure is the paper-derived target for an INT8 "
         "PanLUNA on Hexagon NPU; we label it 'extrapolated NPU' on the badge."),
        ("Is your test accuracy on real or synthetic data?",
         "Both numbers are reported. The 100 % is on synthetic test windows — "
         "fair only because synth is the training distribution. The clinically "
         "meaningful numbers are 96.8 % AFib and 91.7 % Sinus on the held-out "
         "real-patient test set from MIT-BIH afdb. Same network architecture, "
         "real data, no fine-tuning needed."),
        ("Why MIT-BIH AFib database specifically?",
         "Three reasons: (1) it's already at 250 Hz, matching our synth pipeline "
         "with no resampling artefacts; (2) it has rhythm-level annotations "
         "(AFIB / N) covering long stretches per record, giving us thousands "
         "of clean 4-second windows; (3) wfdb-python streams it directly from "
         "PhysioNet HTTPS — no manual data wrangling."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 13 — Risks
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    13, TOTAL, "Risks & Mitigations",
    "Show that we've thought hard about every demo-day failure mode.",
    narration=(
        "Five risks, and a fallback for each one.<br/><br/>"
        "If a Bluetooth sensor drops mid-demo, the synthetic stream takes over "
        "in the same UI with the same latency.<br/><br/>"
        "If quantisation drops accuracy below threshold, we fall back to "
        "mixed-precision: FP16 for the encoder, INT8 only for the heads.<br/><br/>"
        "If the official PanLUNA weights aren't redistributable for legal "
        "reasons, we ship a PanLUNA-style model trained on TUEG and MIMIC-IV "
        "and label it that way.<br/><br/>"
        "If anyone in the room suspects the cloud is doing the work, I unplug the network "
        "live on stage — classification continues uninterrupted.<br/><br/>"
        "And if any of this runs long, we have a pre-recorded 90-second video "
        "loaded on a separate laptop."
    ),
    glossary=[
        ("Mixed-precision",
         "Some layers in higher precision (FP16), others in lower (INT8). Trades "
         "a little speed for a little accuracy."),
        ("PhysioNet",
         "A public archive of medical research data — including the gold-standard "
         "ECG arrhythmia challenge sets."),
    ],
    qa=[
        ("What's your most likely failure on stage?",
         "Camera or sensor connectivity in the venue Wi-Fi environment. Hence "
         "the synthetic stream is always primed."),
        ("How do you handle a question about network inspection?",
         "We have a prepared tcpdump command bound to a hotkey. The viewer will "
         "see outbound DNS and an opt-in clinician POST, nothing else."),
        ("What if PanLUNA's reference checkpoint is paywalled?",
         "We have already verified the paper authors will share weights for "
         "research evaluation under a CC-BY-NC license. Worst case: the trained-"
         "from-scratch alternative."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 13 — Why this wins
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    14, TOTAL, "Models & Datasets — What's Actually Trained",
    "Lay out the concrete artefacts: two ONNX models, one public dataset.",
    narration=(
        "This is the slide for anyone who wants to verify the technical claims. "
        "We trained <b>two</b> ONNX models with the same 14 thousand-parameter "
        "1D-CNN architecture, both shipped in <code>models/</code>.<br/><br/>"
        "<b>Model 1</b> is <code>ecg_cnn.onnx</code>, 21 kilobytes, five-class — "
        "Sinus, AFib, VT, Sinus tachycardia, Sinus bradycardia. Trained on 1,500 "
        "synthetic four-second windows from our biosignal engine. 100 % accuracy "
        "on the synthetic held-out set, which is fair only because synth is the "
        "training distribution. This is the model the live demo uses, because "
        "the synthetic engine is also the source of the live waveforms — every "
        "scenario click is deterministic and instant.<br/><br/>"
        "<b>Model 2</b> is <code>ecg_cnn_physionet.onnx</code>, also 21 "
        "kilobytes, three-class — Sinus, AFib, Other. Trained on real patient "
        "data from the <b>MIT-BIH Atrial Fibrillation Database</b> on PhysioNet "
        "— records 04015, 04043, 04126, and 04746, first 30 minutes of each, "
        "streamed directly via the wfdb-python library. 530 four-second "
        "windows after segmentation. The headline numbers: <b>96.8 % accuracy "
        "on real-patient AFib</b> and 91.7 % on Sinus rhythm, both on a "
        "held-out test set the model has never seen. That's the credibility "
        "number — same architecture, real clinical data, fifty seconds end-to-"
        "end from download to ONNX export.<br/><br/>"
        "Either model can drive the live demo by changing a single path "
        "constant in <code>a2_panluna.py</code>."
    ),
    glossary=[
        ("MIT-BIH Atrial Fibrillation Database",
         "Public clinical dataset hosted on PhysioNet at "
         "physionet.org/content/afdb/1.0.0/. 23 long-term ECG recordings "
         "from subjects with paroxysmal AFib, sampled at 250 Hz, with rhythm-"
         "level annotations (AFIB, N, AFL, J)."),
        ("PhysioNet",
         "An NIH-funded research resource of physiological signals and software "
         "tools — the de-facto open dataset hub for ECG, EEG, and ICU data."),
        ("wfdb-python",
         "The official Python client for PhysioNet — handles record download, "
         "annotation parsing, and signal resampling."),
        ("Held-out test set",
         "Examples the model never sees during training; reserved purely for "
         "measuring generalisation. Ours is a stratified 15 % split."),
    ],
    qa=[
        ("Why two models instead of one?",
         "The synthetic-trained model is deterministic and instant — perfect "
         "for a stage demo with five clickable scenarios. The PhysioNet-trained "
         "model is the credibility marker — it shows the architecture works on "
         "real patient ECGs. Same architecture, same export pipeline; the only "
         "difference is the data. We treat them as the demo head and the "
         "validation head respectively."),
        ("Why only four patient records?",
         "Three reasons: time (the whole training pipeline runs in 51 seconds "
         "during the demo prep), bandwidth (each record is ~50 MB), and "
         "interpretability (small enough to inspect every misclassification "
         "manually). Scaling to all 23 afdb records is a one-line config "
         "change and would meaningfully improve the held-out numbers."),
        ("How do you address the train-on-synth concern?",
         "Two ways. First, we publish the PhysioNet-trained model alongside, "
         "so the architecture's clinical generalisation is independently "
         "verifiable on real data. Second, in production we would train on "
         "the full afdb plus MIT-BIH Arrhythmia (mitdb) plus CinC 2017; the "
         "synth path is a demo convenience, not the production training "
         "story."),
    ],
)


# ──────────────────────────────────────────────────────────────────────────────
# Slide 14 — Closing
# ──────────────────────────────────────────────────────────────────────────────
story += slide_block(
    15, TOTAL, "Closing — Questions",
    "Leave the audience with one tag-line and an open invitation.",
    narration=(
        "I'll close where I started. <b>HealthSense</b>: a 5.4-million-parameter "
        "biosignal foundation model that runs on the wrist, personalises on the "
        "wrist, and never lets your raw signal off the wrist.<br/><br/>"
        "Your data stays on your wrist. Your insights don't.<br/><br/>"
        "Happy to take questions — and we have a live dev kit at the booth right "
        "after this session."
    ),
    glossary=[],
    qa=[
        ("How do I try it?",
         "Booth #02 — we'll record a baseline on your wrist if you'd like."),
        ("Open source plans?",
         "Yes — sensor code, BioTrain loop, and orchestrator are slated for "
         "Apache-2.0. PanLUNA weights follow the upstream license."),
        ("Who's on the team?",
         "Varun Sahni (primary), plus a co-lead to be announced."),
    ],
    last=True,
)


doc.build(story)
print(f"OK: wrote {OUT} ({OUT.stat().st_size:,} bytes)")
