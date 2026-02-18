"""
Trella - Proof of Delivery (POD) Capture App
=============================================
Driver-facing Streamlit app for capturing POD documents at drop-off points.

Usage:
    streamlit run app.py
    
    Driver link format:
    https://trella-driver.streamlit.app/?shipment=<shipment_key>
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from datetime import datetime
import os
import json
import base64

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
REDASH_API_URL = (
    "https://redash.trella.co/api/queries/4922/results.csv"
    "?api_key=TX9ND3NoDL0xHNFcbFKvWwPMQAnouCXcywp1tAdz"
)
POD_STORAGE_DIR = "pod_uploads"
MAX_QUALITY_ATTEMPTS = 3
BLUR_THRESHOLD = 80.0
DARK_THRESHOLD = 40.0
BRIGHT_THRESHOLD = 240.0
MIN_EDGE_RATIO = 0.02
MIN_RESOLUTION = (640, 480)

# ─────────────────────────────────────────────
# TRANSLATIONS
# ─────────────────────────────────────────────
TRANSLATIONS = {
    "en": {
        "confirm_details": "Shipment Details",
        "driver_name": "Driver",
        "phone_number": "Phone",
        "license_plate": "Plate",
        "pickup": "From",
        "destination": "To",
        "commodity": "Cargo",
        "shipper": "Shipper",
        "shipment_ref": "Shipment",
        "confirm_checkbox": "I confirm these are my details and I am at the drop-off location",
        "proceed": "Continue to Upload",
        "upload_title": "Upload Proof of Delivery",
        "tip_surface": "Flat, well-lit surface",
        "tip_steady": "Hold phone steady & parallel",
        "tip_edges": "All document edges visible",
        "tip_glare": "No shadows or glare",
        "tip_lens": "Clean camera lens first",
        "tip_light": "Use natural daylight",
        "take_photo": "Open Camera",
        "upload_file": "Choose from Gallery",
        "analyzing": "Checking image quality...",
        "quality_passed": "Image quality looks good!",
        "quality_failed": "Image quality issue:",
        "reason_blurry": "Image is blurry — hold steady and tap to focus",
        "reason_dark": "Too dark — move to a brighter area",
        "reason_bright": "Too bright — avoid direct light on the document",
        "reason_low_res": "Resolution too low — move closer to the document",
        "reason_no_document": "No document detected — make sure it's fully visible",
        "attempts_remaining": "{} attempts remaining",
        "retake": "Please retake the photo",
        "fallback_title": "Upload 3 Photos Instead",
        "fallback_message": "We couldn't get a clear single photo. Please upload 3 photos from different angles.",
        "fallback_photo": "Photo {}",
        "submit_pod": "Submit POD",
        "submit_fallback": "Submit All Photos",
        "success_title": "POD Submitted!",
        "success_message": "Your proof of delivery has been recorded. You may close this page.",
        "at_dropoff": "At Drop-off",
        "upload_all_three": "Please upload all 3 photos.",
        "weight": "Weight",
        "already_submitted_title": "Already Submitted",
        "already_submitted_msg": "POD was uploaded on {}",
        "already_submitted_note": "Need to re-upload? Contact dispatch.",
        "distance": "Distance",
        "upload_hint": "Tap above to take a photo or choose from gallery",
    },
    "ar": {
        "confirm_details": "تفاصيل الشحنة",
        "driver_name": "السائق",
        "phone_number": "الهاتف",
        "license_plate": "اللوحة",
        "pickup": "من",
        "destination": "إلى",
        "commodity": "البضاعة",
        "shipper": "الشاحن",
        "shipment_ref": "الشحنة",
        "confirm_checkbox": "أؤكد أن هذه بياناتي وأنا في موقع التفريغ",
        "proceed": "المتابعة للتحميل",
        "upload_title": "تحميل إثبات التسليم",
        "tip_surface": "سطح مستوٍ ومضاء جيداً",
        "tip_steady": "أمسك الهاتف بثبات وبشكل موازٍ",
        "tip_edges": "جميع حواف المستند ظاهرة",
        "tip_glare": "بدون ظلال أو انعكاسات",
        "tip_lens": "نظّف العدسة أولاً",
        "tip_light": "استخدم ضوء النهار الطبيعي",
        "take_photo": "فتح الكاميرا",
        "upload_file": "اختر من المعرض",
        "analyzing": "...جاري فحص جودة الصورة",
        "quality_passed": "!جودة الصورة جيدة",
        "quality_failed": ":مشكلة في جودة الصورة",
        "reason_blurry": "الصورة ضبابية — ثبّت الهاتف وانقر للتركيز",
        "reason_dark": "مظلمة جداً — انتقل لمكان أفضل إضاءة",
        "reason_bright": "ساطعة جداً — تجنب الضوء المباشر",
        "reason_low_res": "الدقة منخفضة — اقترب من المستند",
        "reason_no_document": "لم يُكتشف مستند — تأكد من ظهوره بالكامل",
        "attempts_remaining": "{} محاولات متبقية",
        "retake": "يرجى إعادة التصوير",
        "fallback_title": "ارفع ٣ صور بدلاً من ذلك",
        "fallback_message": "لم نتمكن من الحصول على صورة واحدة واضحة. يرجى رفع ٣ صور من زوايا مختلفة.",
        "fallback_photo": "صورة {}",
        "submit_pod": "إرسال إثبات التسليم",
        "submit_fallback": "إرسال جميع الصور",
        "success_title": "!تم الإرسال بنجاح",
        "success_message": "تم تسجيل إثبات التسليم. يمكنك إغلاق هذه الصفحة.",
        "at_dropoff": "في موقع التفريغ",
        "upload_all_three": "يرجى رفع الصور الثلاث.",
        "weight": "الوزن",
        "already_submitted_title": "تم الإرسال مسبقاً",
        "already_submitted_msg": "تم رفع إثبات التسليم بتاريخ {}",
        "already_submitted_note": "تحتاج إعادة الرفع؟ تواصل مع فريق التشغيل.",
        "distance": "المسافة",
        "upload_hint": "انقر أعلاه لالتقاط صورة أو الاختيار من المعرض",
    },
    "ur": {
        "confirm_details": "شپمنٹ کی تفصیلات",
        "driver_name": "ڈرائیور",
        "phone_number": "فون",
        "license_plate": "پلیٹ",
        "pickup": "سے",
        "destination": "تک",
        "commodity": "سامان",
        "shipper": "شپر",
        "shipment_ref": "شپمنٹ",
        "confirm_checkbox": "میں تصدیق کرتا ہوں کہ یہ میری تفصیلات ہیں اور میں ڈراپ آف مقام پر ہوں",
        "proceed": "اپ لوڈ جاری رکھیں",
        "upload_title": "ڈیلیوری کا ثبوت اپ لوڈ کریں",
        "tip_surface": "ہموار، روشن سطح پر رکھیں",
        "tip_steady": "فون مستحکم اور متوازی رکھیں",
        "tip_edges": "دستاویز کے تمام کنارے نظر آئیں",
        "tip_glare": "سائے اور چمک سے بچیں",
        "tip_lens": "پہلے لینز صاف کریں",
        "tip_light": "قدرتی روشنی استعمال کریں",
        "take_photo": "کیمرا کھولیں",
        "upload_file": "گیلری سے منتخب کریں",
        "analyzing": "...تصویر کا معیار جانچ رہے ہیں",
        "quality_passed": "!تصویر کا معیار اچھا ہے",
        "quality_failed": ":تصویر کے معیار میں مسئلہ",
        "reason_blurry": "تصویر دھندلی ہے — فون مستحکم رکھیں",
        "reason_dark": "بہت اندھیری — روشن جگہ پر جائیں",
        "reason_bright": "بہت روشن — براہ راست روشنی سے بچیں",
        "reason_low_res": "ریزولیوشن کم — دستاویز کے قریب جائیں",
        "reason_no_document": "دستاویز نہیں ملی — پوری دستاویز دکھائیں",
        "attempts_remaining": "{} کوششیں باقی",
        "retake": "دوبارہ تصویر لیں",
        "fallback_title": "اس کے بجائے ٣ تصاویر اپ لوڈ کریں",
        "fallback_message": "ہم واضح تصویر حاصل نہیں کر سکے۔ براہ کرم مختلف زاویوں سے ٣ تصاویر اپ لوڈ کریں۔",
        "fallback_photo": "تصویر {}",
        "submit_pod": "POD جمع کرائیں",
        "submit_fallback": "تمام تصاویر جمع کرائیں",
        "success_title": "!کامیابی سے جمع ہو گیا",
        "success_message": "ڈیلیوری کا ثبوت ریکارڈ ہو گیا۔ آپ یہ صفحہ بند کر سکتے ہیں۔",
        "at_dropoff": "ڈراپ آف مقام پر",
        "upload_all_three": "تینوں تصاویر اپ لوڈ کریں۔",
        "weight": "وزن",
        "already_submitted_title": "پہلے سے جمع ہو چکا",
        "already_submitted_msg": "POD {} کو اپ لوڈ ہو چکا ہے",
        "already_submitted_note": "دوبارہ اپ لوڈ کرنا ہے؟ ڈسپیچ سے رابطہ کریں۔",
        "distance": "فاصلہ",
        "upload_hint": "اوپر ٹیپ کریں تصویر لینے یا گیلری سے منتخب کرنے کے لیے",
    },
}


def t(key: str) -> str:
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


def is_rtl() -> bool:
    return st.session_state.get("language", "en") in ("ar", "ur")


# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');

:root {
    --trella-blue: #0B4F8A;
    --trella-light: #E8F1FA;
    --trella-accent: #14A583;
    --trella-accent-light: #E6F7F3;
    --trella-orange: #F5921B;
    --trella-red: #DC3545;
    --trella-gray: #6B7280;
    --trella-border: #E5E7EB;
    --trella-bg: #F8FAFB;
    --radius: 12px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
}

#MainMenu, footer, header { visibility: hidden !important; height: 0 !important; }
section[data-testid="stSidebar"] { display: none; }
div[data-testid="stToolbar"] { display: none; }
div[data-testid="stDecoration"] { display: none; }
div[data-testid="stStatusWidget"] { display: none; }

.stApp {
    background: var(--trella-bg) !important;
    font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif !important;
}
.block-container {
    padding: 1rem 1rem 5rem 1rem !important;
    max-width: 480px !important;
    margin: 0 auto;
}
h1, h2, h3, h4, p, span, label, div {
    font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif !important;
}

/* ── Cards ── */
.pod-card {
    background: #fff;
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--trella-border);
}
.pod-card-accent { border-left: 4px solid var(--trella-accent); }
.pod-card-accent.rtl { border-left: none; border-right: 4px solid var(--trella-accent); }
.pod-card-blue { border-left: 4px solid var(--trella-blue); }
.pod-card-blue.rtl { border-left: none; border-right: 4px solid var(--trella-blue); }

/* ── Detail rows ── */
.detail-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.5rem 0;
    border-bottom: 1px solid #F3F4F6;
}
.detail-row:last-child { border-bottom: none; }
.detail-label {
    font-size: 0.8rem; font-weight: 500; color: var(--trella-gray);
    text-transform: uppercase; letter-spacing: 0.03em;
}
.detail-value {
    font-size: 0.95rem; font-weight: 600; color: #1F2937; text-align: right;
}
.rtl .detail-value { text-align: left; }

/* ── Route card ── */
.route-card {
    background: linear-gradient(135deg, var(--trella-light) 0%, #fff 100%);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--trella-border);
}
.route-point { display: flex; align-items: center; gap: 0.75rem; }
.route-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.route-dot.origin { background: var(--trella-blue); }
.route-dot.dest { background: var(--trella-accent); }
.route-line {
    width: 2px; height: 28px; margin-left: 5px; opacity: 0.4;
    background: repeating-linear-gradient(to bottom, var(--trella-gray) 0px, var(--trella-gray) 4px, transparent 4px, transparent 8px);
}
.rtl .route-line { margin-left: 0; margin-right: 5px; }
.route-city { font-size: 1rem; font-weight: 600; color: #1F2937; }
.route-name { font-size: 0.8rem; color: var(--trella-gray); margin-top: 1px; }

/* ── Badges ── */
.status-badge {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.3rem 0.75rem; border-radius: 2rem;
    font-size: 0.75rem; font-weight: 600;
}
.status-dropoff { background: var(--trella-accent-light); color: #0D7A60; }

/* ── Tips ── */
.tips-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.75rem 0; }
.tip-pill {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.4rem 0.75rem; background: var(--trella-light);
    border-radius: 2rem; font-size: 0.78rem; color: var(--trella-blue); font-weight: 500;
}

/* ── Quality feedback ── */
.quality-pass {
    background: var(--trella-accent-light); color: #0D7A60;
    padding: 0.75rem 1rem; border-radius: var(--radius);
    font-weight: 600; display: flex; align-items: center; gap: 0.5rem; margin: 0.75rem 0;
}
.quality-fail {
    background: #FEF2F2; color: #991B1B;
    padding: 0.75rem 1rem; border-radius: var(--radius);
    font-weight: 500; margin: 0.75rem 0; border-left: 3px solid var(--trella-red);
}
.quality-fail.rtl { border-left: none; border-right: 3px solid var(--trella-red); }
.attempts-badge {
    background: #FEF3C7; color: #92400E;
    padding: 0.4rem 0.75rem; border-radius: 2rem;
    font-size: 0.8rem; font-weight: 600; display: inline-block; margin: 0.5rem 0;
}

/* ── Buttons ── */
.stButton > button {
    width: 100%; padding: 0.85rem 1.5rem !important;
    font-size: 1rem !important; font-weight: 600 !important;
    border-radius: var(--radius) !important; min-height: 3rem;
    font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--trella-accent) 0%, #0D9B78 100%) !important;
    border: none !important; color: #fff !important; box-shadow: var(--shadow-md) !important;
}
.stCheckbox > label { font-size: 0.9rem !important; padding: 0.75rem 0 !important; line-height: 1.5 !important; }

/* ── Success ── */
.success-container { text-align: center; padding: 3rem 1rem; }
.success-check {
    width: 80px; height: 80px; background: var(--trella-accent-light);
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    margin: 0 auto 1.5rem;
    animation: pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes pop { 0% { transform: scale(0); } 100% { transform: scale(1); } }
.success-check svg { width: 40px; height: 40px; stroke: var(--trella-accent); }
.success-title { font-size: 1.5rem; font-weight: 700; color: #1F2937; margin-bottom: 0.5rem; }
.success-msg { font-size: 0.95rem; color: var(--trella-gray); line-height: 1.6; }

/* ── Header ── */
.app-header { text-align: center; padding: 1.5rem 0 0.5rem; }
.app-logo { font-size: 1.5rem; font-weight: 700; color: var(--trella-blue); letter-spacing: -0.02em; }
.app-logo span { color: var(--trella-accent); }
.app-subtitle { font-size: 0.85rem; color: var(--trella-gray); margin-top: 0.25rem; }

/* ── Steps ── */
.steps { display: flex; justify-content: center; gap: 0.5rem; margin: 1rem 0 1.5rem; }
.step-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--trella-border); transition: all 0.3s ease;
}
.step-dot.active { background: var(--trella-blue); width: 24px; border-radius: 4px; }
.step-dot.done { background: var(--trella-accent); }

.divider { height: 1px; background: var(--trella-border); margin: 1rem 0; }

/* RTL */
.rtl { direction: rtl; text-align: right; }

/* File uploader styling */
.stFileUploader > div > div { border-radius: var(--radius) !important; }
div[data-testid="stFileUploader"] > section > button {
    font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif !important;
}
</style>
"""

RTL_CSS = """
<style>
.stApp { direction: rtl; text-align: right; }
.stMarkdown, .stText { direction: rtl; text-align: right; }
.stCheckbox > label { direction: rtl; }
div[data-testid="stMetricValue"] { direction: ltr; }
</style>
"""


# ─────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_shipment_data() -> pd.DataFrame:
    try:
        resp = requests.get(REDASH_API_URL, timeout=30)
        resp.raise_for_status()
        return pd.read_csv(BytesIO(resp.content))
    except Exception:
        return pd.DataFrame()


def get_shipment(shipment_key: str) -> dict | None:
    df = fetch_shipment_data()
    if df.empty:
        return None
    match = df[df["key"] == shipment_key]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


# ─────────────────────────────────────────────
# IMAGE QUALITY ANALYSIS
# ─────────────────────────────────────────────
def analyze_image_quality(image_bytes: bytes) -> dict:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"passed": False, "reasons": ["reason_no_document"], "scores": {}}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]
    reasons = []
    scores = {}

    scores["resolution"] = f"{w}x{h}"
    if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
        reasons.append("reason_low_res")

    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    scores["sharpness"] = round(laplacian_var, 1)
    if laplacian_var < BLUR_THRESHOLD:
        reasons.append("reason_blurry")

    mean_brightness = np.mean(gray)
    scores["brightness"] = round(mean_brightness, 1)
    if mean_brightness < DARK_THRESHOLD:
        reasons.append("reason_dark")
    elif mean_brightness > BRIGHT_THRESHOLD:
        reasons.append("reason_bright")

    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = np.count_nonzero(edges) / (h * w)
    scores["edge_ratio"] = round(edge_ratio, 4)
    if edge_ratio < MIN_EDGE_RATIO:
        reasons.append("reason_no_document")

    block_size = 4
    bh, bw = h // block_size, w // block_size
    blurry_blocks = 0
    total_blocks = block_size * block_size
    for i in range(block_size):
        for j in range(block_size):
            block = gray[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw]
            if cv2.Laplacian(block, cv2.CV_64F).var() < BLUR_THRESHOLD * 0.5:
                blurry_blocks += 1
    if blurry_blocks > total_blocks * 0.6 and "reason_blurry" not in reasons:
        reasons.append("reason_blurry")

    return {"passed": len(reasons) == 0, "reasons": reasons, "scores": scores}


# ─────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────
def save_pod_image(shipment_key: str, image_bytes: bytes, index: int = 0) -> str:
    shipment_dir = os.path.join(POD_STORAGE_DIR, shipment_key)
    os.makedirs(shipment_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(shipment_dir, f"pod_{index}_{timestamp}.jpg")
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filepath


def save_pod_metadata(shipment_key: str, shipment_data: dict, file_paths: list, mode: str):
    shipment_dir = os.path.join(POD_STORAGE_DIR, shipment_key)
    os.makedirs(shipment_dir, exist_ok=True)
    metadata = {
        "shipment_key": shipment_key,
        "job_key": shipment_data.get("job_key", ""),
        "carrier": shipment_data.get("carrier", ""),
        "carrier_mobile": shipment_data.get("carrier_mobile", ""),
        "vehicle_plate": shipment_data.get("vehicle_plate", ""),
        "shipper": shipment_data.get("shipper", ""),
        "entity": shipment_data.get("entity", ""),
        "pickup_city": shipment_data.get("pickup_city", ""),
        "destination_city": shipment_data.get("destination_city", ""),
        "commodity": shipment_data.get("commodity", ""),
        "upload_mode": mode,
        "file_paths": file_paths,
        "uploaded_at": datetime.now().isoformat(),
        "language": st.session_state.get("language", "en"),
    }
    meta_path = os.path.join(shipment_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return meta_path


def get_existing_submission(shipment_key: str) -> dict | None:
    meta_path = os.path.join(POD_STORAGE_DIR, shipment_key, "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────
def render_header():
    st.markdown("""
    <div class="app-header">
        <div class="app-logo">trella<span>.</span></div>
        <div class="app-subtitle">Proof of Delivery</div>
    </div>
    """, unsafe_allow_html=True)


def render_steps(current: int):
    dots = []
    for i in range(1, 4):
        if i < current:
            dots.append('<div class="step-dot done"></div>')
        elif i == current:
            dots.append('<div class="step-dot active"></div>')
        else:
            dots.append('<div class="step-dot"></div>')
    st.markdown(f'<div class="steps">{"".join(dots)}</div>', unsafe_allow_html=True)


def apply_rtl():
    if is_rtl():
        st.markdown(RTL_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# STEP 1 — LANGUAGE
# ─────────────────────────────────────────────
def render_language_selection():
    render_header()
    render_steps(1)

    st.markdown("""
    <p style="text-align:center; color: #6B7280; font-size: 0.95rem; margin-bottom: 0.25rem;">
        Select your language
    </p>
    <p style="text-align:center; color: #6B7280; font-size: 0.95rem;">
        اختر لغتك &nbsp;|&nbsp; اپنی زبان منتخب کریں
    </p>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        if st.button("🇬🇧\n\nEnglish", use_container_width=True, key="btn_en"):
            st.session_state.language = "en"
            st.session_state.step = "confirm"
            st.rerun()
    with col2:
        if st.button("🇸🇦\n\nالعربية", use_container_width=True, key="btn_ar"):
            st.session_state.language = "ar"
            st.session_state.step = "confirm"
            st.rerun()
    with col3:
        if st.button("🇵🇰\n\nاردو", use_container_width=True, key="btn_ur"):
            st.session_state.language = "ur"
            st.session_state.step = "confirm"
            st.rerun()


# ─────────────────────────────────────────────
# STEP 2 — CONFIRM DETAILS
# ─────────────────────────────────────────────
def render_confirmation(shipment: dict):
    apply_rtl()
    render_header()
    render_steps(2)

    rtl_class = "rtl" if is_rtl() else ""
    carrier = shipment.get("carrier", "N/A")
    mobile = shipment.get("carrier_mobile", "N/A")
    plate = shipment.get("vehicle_plate", "N/A")

    # Driver card
    st.markdown(f"""
    <div class="pod-card pod-card-blue {rtl_class}">
        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.75rem;">
            <div style="width:44px;height:44px;border-radius:50%;background:var(--trella-light);
                display:flex;align-items:center;justify-content:center;font-size:1.3rem;flex-shrink:0;">🚛</div>
            <div>
                <div style="font-size:1.1rem;font-weight:700;color:#1F2937;">{carrier}</div>
                <div style="font-size:0.8rem;color:var(--trella-gray);">{mobile} &nbsp;·&nbsp; {plate}</div>
            </div>
        </div>
        <span class="status-badge status-dropoff">● {t('at_dropoff')}</span>
    </div>
    """, unsafe_allow_html=True)

    # Route card
    pickup_city = shipment.get("pickup_city", "")
    pickup_name = shipment.get("pickup_name", "")
    dest_city = shipment.get("destination_city", "")
    dest_name = shipment.get("destination_name", "")

    st.markdown(f"""
    <div class="route-card {rtl_class}">
        <div class="route-point">
            <div class="route-dot origin"></div>
            <div>
                <div class="route-city">{pickup_city}</div>
                <div class="route-name">{pickup_name}</div>
            </div>
        </div>
        <div class="route-line"></div>
        <div class="route-point">
            <div class="route-dot dest"></div>
            <div>
                <div class="route-city">{dest_city}</div>
                <div class="route-name">{dest_name}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Details card
    entity = shipment.get("entity", "N/A")
    commodity = shipment.get("commodity", "N/A")
    weight = shipment.get("weight", 0)
    distance = shipment.get("distance", 0)
    try:
        distance = f"{float(distance):,.0f} km"
    except (ValueError, TypeError):
        distance = str(distance)

    st.markdown(f"""
    <div class="pod-card {rtl_class}">
        <div class="detail-row">
            <span class="detail-label">{t('shipper')}</span>
            <span class="detail-value">{entity}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">{t('commodity')}</span>
            <span class="detail-value">{commodity}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">{t('weight')}</span>
            <span class="detail-value">{weight} t</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">{t('distance')}</span>
            <span class="detail-value">{distance}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">{t('shipment_ref')}</span>
            <span class="detail-value" style="font-size:0.8rem;font-family:monospace;">{shipment.get('key', 'N/A')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    confirmed = st.checkbox(t("confirm_checkbox"), key="details_confirmed")
    if confirmed:
        if st.button(t("proceed"), type="primary", use_container_width=True):
            st.session_state.step = "upload"
            st.rerun()


# ─────────────────────────────────────────────
# STEP 3 — POD UPLOAD (native camera)
# ─────────────────────────────────────────────
def render_upload(shipment: dict):
    apply_rtl()
    render_header()
    render_steps(3)

    rtl_class = "rtl" if is_rtl() else ""

    if "quality_attempts" not in st.session_state:
        st.session_state.quality_attempts = 0
    if "in_fallback_mode" not in st.session_state:
        st.session_state.in_fallback_mode = False

    if st.session_state.in_fallback_mode:
        render_fallback_upload(shipment)
        return

    st.markdown(f'<h3 style="margin:0 0 0.25rem;">{t("upload_title")}</h3>', unsafe_allow_html=True)

    # Tips as compact pills
    tips = ["tip_surface", "tip_steady", "tip_edges", "tip_glare", "tip_lens", "tip_light"]
    icons = ["☀️", "📐", "📄", "🚫", "🔍", "🌤️"]
    pills = "".join(f'<span class="tip-pill">{icons[i]} {t(tip)}</span>' for i, tip in enumerate(tips))
    st.markdown(f'<div class="tips-grid">{pills}</div>', unsafe_allow_html=True)

    # Attempts remaining
    remaining = MAX_QUALITY_ATTEMPTS - st.session_state.quality_attempts
    if st.session_state.quality_attempts > 0:
        st.markdown(
            f'<span class="attempts-badge">⚠️ {t("attempts_remaining").format(remaining)}</span>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── File uploader (triggers native camera on mobile via OS file picker) ──
    uploaded_file = st.file_uploader(
        t("take_photo"),
        type=["jpg", "jpeg", "png", "heic", "heif"],
        key=f"pod_upload_{st.session_state.quality_attempts}",
        help=t("upload_hint"),
    )

    st.markdown(f"""
    <p style="text-align:center; font-size:0.82rem; color:var(--trella-gray); margin-top:0.25rem;">
        📷 {t('upload_hint')}
    </p>
    """, unsafe_allow_html=True)

    if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        st.image(image_bytes, use_container_width=True)

        with st.spinner(t("analyzing")):
            result = analyze_image_quality(image_bytes)

        if result["passed"]:
            st.markdown(f"""
            <div class="quality-pass">
                <span style="font-size:1.2rem;">✅</span> {t('quality_passed')}
            </div>
            """, unsafe_allow_html=True)

            if st.button(t("submit_pod"), type="primary", use_container_width=True):
                with st.spinner("..."):
                    filepath = save_pod_image(shipment["key"], image_bytes, index=0)
                    save_pod_metadata(shipment["key"], shipment, [filepath], mode="single")
                    st.session_state.step = "success"
                    st.rerun()
        else:
            reasons_html = "".join(f"<div>⚠️ {t(r)}</div>" for r in result["reasons"])
            st.markdown(f"""
            <div class="quality-fail {rtl_class}">
                <div style="font-weight:700; margin-bottom:0.5rem;">❌ {t('quality_failed')}</div>
                {reasons_html}
            </div>
            """, unsafe_allow_html=True)

            st.session_state.quality_attempts += 1
            if st.session_state.quality_attempts >= MAX_QUALITY_ATTEMPTS:
                st.session_state.in_fallback_mode = True
                st.rerun()
            else:
                st.markdown(f'<span class="attempts-badge">🔄 {t("retake")}</span>', unsafe_allow_html=True)


def render_fallback_upload(shipment: dict):
    apply_rtl()
    rtl_class = "rtl" if is_rtl() else ""

    st.markdown(f"""
    <div class="quality-fail {rtl_class}" style="border-color: var(--trella-orange); background: #FFFBEB;">
        <div style="font-weight:700; font-size:1.05rem; margin-bottom:0.35rem; color: #92400E;">
            📸 {t('fallback_title')}
        </div>
        <div style="color: #78350F;">{t('fallback_message')}</div>
    </div>
    """, unsafe_allow_html=True)

    photos = []
    for i in range(1, 4):
        label = f"{t('fallback_photo').format(i)} / 3"
        photo = st.file_uploader(label, type=["jpg", "jpeg", "png", "heic", "heif"], key=f"fallback_{i}")
        if photo:
            photos.append(photo)
            st.image(photo, caption=label, use_container_width=True)

    if len(photos) == 3:
        if st.button(t("submit_fallback"), type="primary", use_container_width=True):
            with st.spinner("..."):
                file_paths = []
                for idx, photo in enumerate(photos):
                    filepath = save_pod_image(shipment["key"], photo.getvalue(), index=idx)
                    file_paths.append(filepath)
                save_pod_metadata(shipment["key"], shipment, file_paths, mode="fallback_triple")
                st.session_state.step = "success"
                st.rerun()
    elif len(photos) > 0:
        st.markdown(f'<span class="attempts-badge">{t("upload_all_three")}</span>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ALREADY SUBMITTED
# ─────────────────────────────────────────────
def render_already_submitted(submission: dict, shipment: dict):
    if "language" not in st.session_state:
        render_language_selection()
        return

    apply_rtl()
    render_header()

    uploaded_at = submission.get("uploaded_at", "unknown")
    try:
        dt = datetime.fromisoformat(uploaded_at)
        formatted_date = dt.strftime("%Y-%m-%d  %H:%M")
    except (ValueError, TypeError):
        formatted_date = uploaded_at

    file_count = len(submission.get("file_paths", []))
    rtl_class = "rtl" if is_rtl() else ""

    st.markdown(f"""
    <div class="success-container">
        <div class="success-check">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
                 stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <div class="success-title">{t('already_submitted_title')}</div>
        <div class="success-msg">{t('already_submitted_msg').format(formatted_date)}</div>
        <div style="margin-top:0.5rem;">
            <span class="status-badge status-dropoff">{file_count} photo{'s' if file_count != 1 else ''}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    file_paths = submission.get("file_paths", [])
    if file_paths:
        cols = st.columns(min(len(file_paths), 3))
        for idx, fp in enumerate(file_paths):
            if os.path.exists(fp):
                with cols[idx % 3]:
                    st.image(fp, use_container_width=True)

    st.markdown(f"""
    <div class="pod-card pod-card-accent {rtl_class}" style="margin-top:1rem;">
        <div class="detail-row">
            <span class="detail-label">{t('driver_name')}</span>
            <span class="detail-value">{shipment.get('carrier', 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">{t('destination')}</span>
            <span class="detail-value">{shipment.get('destination_city', '')}</span>
        </div>
    </div>
    <p style="text-align:center; font-size:0.85rem; color:var(--trella-gray); margin-top:1rem;">
        {t('already_submitted_note')}
    </p>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SUCCESS
# ─────────────────────────────────────────────
def render_success():
    apply_rtl()
    render_header()

    st.markdown(f"""
    <div class="success-container">
        <div class="success-check">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
                 stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <div class="success-title">{t('success_title')}</div>
        <div class="success-msg">{t('success_message')}</div>
    </div>
    """, unsafe_allow_html=True)
    st.balloons()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Trella POD",
        page_icon="🚛",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    params = st.query_params
    shipment_key = params.get("shipment", None)

    if not shipment_key:
        render_header()
        st.markdown("""
        <div class="pod-card" style="text-align:center; padding:2rem;">
            <div style="font-size:2.5rem; margin-bottom:1rem;">🔗</div>
            <div style="font-weight:600; color:#1F2937; margin-bottom:0.5rem;">No shipment link found</div>
            <div style="color:var(--trella-gray); font-size:0.9rem;">
                Please use the link sent to your phone.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    shipment = get_shipment(shipment_key)
    if shipment is None:
        st.cache_data.clear()
        shipment = get_shipment(shipment_key)

    if shipment is None:
        render_header()
        st.markdown(f"""
        <div class="pod-card" style="text-align:center; padding:2rem;">
            <div style="font-size:2.5rem; margin-bottom:1rem;">⚠️</div>
            <div style="font-weight:600; color:#1F2937; margin-bottom:0.5rem;">Shipment not found</div>
            <div style="color:var(--trella-gray); font-size:0.9rem;">
                This shipment may have been completed or is not at drop-off status.<br>
                <span style="font-family:monospace; font-size:0.8rem;">{shipment_key}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    existing = get_existing_submission(shipment_key)
    if existing and st.session_state.get("step") != "success":
        render_already_submitted(existing, shipment)
        st.stop()

    if "step" not in st.session_state:
        st.session_state.step = "language"

    step = st.session_state.step
    if step == "language":
        render_language_selection()
    elif step == "confirm":
        render_confirmation(shipment)
    elif step == "upload":
        render_upload(shipment)
    elif step == "success":
        render_success()
    else:
        st.session_state.step = "language"
        st.rerun()


if __name__ == "__main__":
    main()
