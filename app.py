"""
Trella - Proof of Delivery (POD) Capture App
=============================================
Driver-facing Streamlit app for capturing POD documents at drop-off points.

Usage:
    streamlit run app.py
    
    Driver link format:
    https://<app-url>/?shipment=<shipment_key>
    
    Example:
    https://<app-url>/?shipment=shp51018426a3d0d370
"""

import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from datetime import datetime
import os
import json
import hashlib

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
REDASH_API_URL = (
    "https://redash.trella.co/api/queries/4922/results.csv"
    "?api_key=TX9ND3NoDL0xHNFcbFKvWwPMQAnouCXcywp1tAdz"
)
POD_STORAGE_DIR = "pod_uploads"  # Local storage; replace with S3/GCS in production
MAX_QUALITY_ATTEMPTS = 3
BLUR_THRESHOLD = 80.0         # Laplacian variance below this = blurry
DARK_THRESHOLD = 40.0         # Mean brightness below this = too dark
BRIGHT_THRESHOLD = 240.0      # Mean brightness above this = overexposed
MIN_EDGE_RATIO = 0.02         # Minimum edge pixel ratio (document detection)
MIN_RESOLUTION = (640, 480)   # Minimum acceptable resolution

# ─────────────────────────────────────────────
# TRANSLATIONS
# ─────────────────────────────────────────────
TRANSLATIONS = {
    "en": {
        "app_title": "📄 Proof of Delivery",
        "welcome": "Welcome, Driver!",
        "select_language": "Select your language",
        "confirm_details": "Your Shipment Details",
        "driver_name": "Driver Name",
        "phone_number": "Phone Number",
        "license_plate": "License Plate",
        "pickup": "Pickup",
        "destination": "Destination",
        "commodity": "Commodity",
        "shipper": "Shipper",
        "shipment_ref": "Shipment Reference",
        "confirm_checkbox": "I confirm these are my details and I am at the drop-off location",
        "proceed": "Proceed to POD Upload",
        "upload_title": "Upload Proof of Delivery",
        "upload_instructions": "📸 **Photo Instructions for Best Quality:**",
        "instruction_1": "Place the document on a flat, well-lit surface",
        "instruction_2": "Hold your phone steady and parallel to the document",
        "instruction_3": "Make sure all edges of the document are visible",
        "instruction_4": "Avoid shadows, glare, and reflections",
        "instruction_5": "Clean your camera lens before taking the photo",
        "instruction_6": "Use natural daylight if possible",
        "take_photo": "📷 Take Photo",
        "upload_file": "Or upload from gallery",
        "analyzing": "Analyzing image quality...",
        "quality_passed": "✅ Image quality is good!",
        "quality_failed": "❌ Image quality issue detected:",
        "reason_blurry": "The image is blurry. Please hold your phone steady and tap to focus.",
        "reason_dark": "The image is too dark. Please move to a better-lit area.",
        "reason_bright": "The image is overexposed. Please avoid direct light/glare on the document.",
        "reason_low_res": "The image resolution is too low. Please move closer to the document.",
        "reason_no_document": "No document detected. Please ensure the entire document is visible.",
        "attempts_remaining": "Attempts remaining: {}",
        "retake": "Please retake the photo",
        "fallback_title": "📸 Camera Quality Issue - Upload 3 Photos",
        "fallback_message": "We're having trouble getting a clear single photo. Please upload **3 different photos** of your POD document from different angles to ensure we capture all details.",
        "fallback_photo": "Photo {} of 3",
        "submit_pod": "✅ Submit POD",
        "submit_fallback": "✅ Submit All 3 Photos",
        "success_title": "🎉 POD Submitted Successfully!",
        "success_message": "Your proof of delivery has been recorded. You may close this page.",
        "error_no_shipment": "⚠️ No shipment reference found. Please use the link sent to your phone.",
        "error_not_found": "⚠️ Shipment not found or not at drop-off status.",
        "error_api": "⚠️ Could not connect to the server. Please check your internet connection and try again.",
        "status": "Status",
        "at_dropoff": "At Drop-off Location",
        "upload_all_three": "Please upload all 3 photos before submitting.",
        "weight": "Weight (tons)",
        "already_submitted_title": "✅ POD Already Submitted",
        "already_submitted_msg": "A Proof of Delivery was already uploaded for this shipment on **{}**.",
        "already_submitted_mode": "Upload type: **{}**",
        "already_submitted_count": "Photos uploaded: **{}**",
        "already_submitted_note": "If you need to re-upload, please contact dispatch.",
    },
    "ar": {
        "app_title": "📄 إثبات التسليم",
        "welcome": "!مرحباً أيها السائق",
        "select_language": "اختر لغتك",
        "confirm_details": "تفاصيل شحنتك",
        "driver_name": "اسم السائق",
        "phone_number": "رقم الهاتف",
        "license_plate": "رقم اللوحة",
        "pickup": "نقطة التحميل",
        "destination": "نقطة التفريغ",
        "commodity": "نوع البضاعة",
        "shipper": "الشاحن",
        "shipment_ref": "رقم الشحنة",
        "confirm_checkbox": "أؤكد أن هذه بياناتي وأنا في موقع التفريغ",
        "proceed": "المتابعة لتحميل إثبات التسليم",
        "upload_title": "تحميل إثبات التسليم",
        "upload_instructions": "📸 **تعليمات التصوير للحصول على أفضل جودة:**",
        "instruction_1": "ضع المستند على سطح مستوٍ ومضاء جيداً",
        "instruction_2": "أمسك هاتفك بثبات وبشكل موازٍ للمستند",
        "instruction_3": "تأكد من ظهور جميع حواف المستند",
        "instruction_4": "تجنب الظلال والوهج والانعكاسات",
        "instruction_5": "نظّف عدسة الكاميرا قبل التصوير",
        "instruction_6": "استخدم ضوء النهار الطبيعي إن أمكن",
        "take_photo": "📷 التقط صورة",
        "upload_file": "أو ارفع من المعرض",
        "analyzing": "...جاري تحليل جودة الصورة",
        "quality_passed": "✅ !جودة الصورة جيدة",
        "quality_failed": "❌ :تم اكتشاف مشكلة في جودة الصورة",
        "reason_blurry": "الصورة ضبابية. يرجى تثبيت هاتفك والنقر للتركيز.",
        "reason_dark": "الصورة مظلمة جداً. يرجى الانتقال إلى مكان أفضل إضاءة.",
        "reason_bright": "الصورة ساطعة جداً. يرجى تجنب الضوء المباشر على المستند.",
        "reason_low_res": "دقة الصورة منخفضة جداً. يرجى الاقتراب من المستند.",
        "reason_no_document": "لم يتم اكتشاف مستند. يرجى التأكد من ظهور المستند بالكامل.",
        "attempts_remaining": "المحاولات المتبقية: {}",
        "retake": "يرجى إعادة التقاط الصورة",
        "fallback_title": "📸 مشكلة في جودة الكاميرا - ارفع ٣ صور",
        "fallback_message": "نواجه صعوبة في الحصول على صورة واحدة واضحة. يرجى رفع **٣ صور مختلفة** لمستند إثبات التسليم من زوايا مختلفة.",
        "fallback_photo": "الصورة {} من ٣",
        "submit_pod": "✅ إرسال إثبات التسليم",
        "submit_fallback": "✅ إرسال الصور الثلاث",
        "success_title": "🎉 !تم إرسال إثبات التسليم بنجاح",
        "success_message": "تم تسجيل إثبات التسليم الخاص بك. يمكنك إغلاق هذه الصفحة.",
        "error_no_shipment": "⚠️ لم يتم العثور على رقم الشحنة. يرجى استخدام الرابط المرسل إلى هاتفك.",
        "error_not_found": "⚠️ لم يتم العثور على الشحنة أو أنها ليست في حالة التفريغ.",
        "error_api": "⚠️ تعذر الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت والمحاولة مرة أخرى.",
        "status": "الحالة",
        "at_dropoff": "في موقع التفريغ",
        "upload_all_three": "يرجى رفع الصور الثلاث قبل الإرسال.",
        "weight": "الوزن (طن)",
        "already_submitted_title": "✅ تم إرسال إثبات التسليم مسبقاً",
        "already_submitted_msg": "تم رفع إثبات التسليم لهذه الشحنة بتاريخ **{}**.",
        "already_submitted_mode": "نوع الرفع: **{}**",
        "already_submitted_count": "عدد الصور المرفوعة: **{}**",
        "already_submitted_note": "إذا كنت بحاجة إلى إعادة الرفع، يرجى التواصل مع فريق التشغيل.",
    },
    "ur": {
        "app_title": "📄 ڈیلیوری کا ثبوت",
        "welcome": "!خوش آمدید، ڈرائیور",
        "select_language": "اپنی زبان منتخب کریں",
        "confirm_details": "آپ کی شپمنٹ کی تفصیلات",
        "driver_name": "ڈرائیور کا نام",
        "phone_number": "فون نمبر",
        "license_plate": "نمبر پلیٹ",
        "pickup": "پک اپ",
        "destination": "منزل",
        "commodity": "سامان کی قسم",
        "shipper": "شپر",
        "shipment_ref": "شپمنٹ حوالہ",
        "confirm_checkbox": "میں تصدیق کرتا ہوں کہ یہ میری تفصیلات ہیں اور میں ڈراپ آف مقام پر ہوں",
        "proceed": "POD اپ لوڈ کریں",
        "upload_title": "ڈیلیوری کا ثبوت اپ لوڈ کریں",
        "upload_instructions": "📸 **بہترین معیار کے لیے تصویر کی ہدایات:**",
        "instruction_1": "دستاویز کو ایک ہموار، روشن سطح پر رکھیں",
        "instruction_2": "اپنا فون مستحکم اور دستاویز کے متوازی رکھیں",
        "instruction_3": "یقینی بنائیں کہ دستاویز کے تمام کنارے نظر آ رہے ہیں",
        "instruction_4": "سائے، چمک اور عکس سے بچیں",
        "instruction_5": "تصویر لینے سے پہلے کیمرے کا لینز صاف کریں",
        "instruction_6": "اگر ممکن ہو تو قدرتی دن کی روشنی استعمال کریں",
        "take_photo": "📷 تصویر لیں",
        "upload_file": "یا گیلری سے اپ لوڈ کریں",
        "analyzing": "...تصویر کے معیار کا تجزیہ ہو رہا ہے",
        "quality_passed": "✅ !تصویر کا معیار اچھا ہے",
        "quality_failed": "❌ :تصویر کے معیار میں مسئلہ پایا گیا",
        "reason_blurry": "تصویر دھندلی ہے۔ براہ کرم اپنا فون مستحکم رکھیں اور فوکس کے لیے ٹیپ کریں۔",
        "reason_dark": "تصویر بہت اندھیری ہے۔ براہ کرم بہتر روشنی والی جگہ پر جائیں۔",
        "reason_bright": "تصویر بہت زیادہ روشن ہے۔ براہ کرم دستاویز پر براہ راست روشنی سے بچیں۔",
        "reason_low_res": "تصویر کی ریزولیوشن بہت کم ہے۔ براہ کرم دستاویز کے قریب جائیں۔",
        "reason_no_document": "کوئی دستاویز نہیں ملی۔ براہ کرم یقینی بنائیں کہ پوری دستاویز نظر آ رہی ہے۔",
        "attempts_remaining": "باقی کوششیں: {}",
        "retake": "براہ کرم دوبارہ تصویر لیں",
        "fallback_title": "📸 کیمرے کے معیار کا مسئلہ - ٣ تصاویر اپ لوڈ کریں",
        "fallback_message": "ہمیں ایک واضح تصویر حاصل کرنے میں دشواری ہو رہی ہے۔ براہ کرم اپنی POD دستاویز کی **٣ مختلف تصاویر** مختلف زاویوں سے اپ لوڈ کریں۔",
        "fallback_photo": "٣ میں سے {} تصویر",
        "submit_pod": "✅ POD جمع کرائیں",
        "submit_fallback": "✅ تینوں تصاویر جمع کرائیں",
        "success_title": "🎉 !ڈیلیوری کا ثبوت کامیابی سے جمع ہو گیا",
        "success_message": "آپ کا ڈیلیوری کا ثبوت ریکارڈ ہو گیا ہے۔ آپ یہ صفحہ بند کر سکتے ہیں۔",
        "error_no_shipment": "⚠️ شپمنٹ حوالہ نہیں ملا۔ براہ کرم اپنے فون پر بھیجا گیا لنک استعمال کریں۔",
        "error_not_found": "⚠️ شپمنٹ نہیں ملی یا ڈراپ آف حالت میں نہیں ہے۔",
        "error_api": "⚠️ سرور سے رابطہ نہیں ہو سکا۔ براہ کرم اپنا انٹرنیٹ کنکشن چیک کریں اور دوبارہ کوشش کریں۔",
        "status": "حالت",
        "at_dropoff": "ڈراپ آف مقام پر",
        "upload_all_three": "براہ کرم جمع کرانے سے پہلے تینوں تصاویر اپ لوڈ کریں۔",
        "weight": "وزن (ٹن)",
        "already_submitted_title": "✅ POD پہلے سے جمع ہو چکا ہے",
        "already_submitted_msg": "اس شپمنٹ کے لیے ڈیلیوری کا ثبوت **{}** کو اپ لوڈ ہو چکا ہے۔",
        "already_submitted_mode": "اپ لوڈ کی قسم: **{}**",
        "already_submitted_count": "اپ لوڈ شدہ تصاویر: **{}**",
        "already_submitted_note": "اگر آپ کو دوبارہ اپ لوڈ کرنا ہے تو براہ کرم ڈسپیچ سے رابطہ کریں۔",
    },
}


def t(key: str) -> str:
    """Get translation for the current language."""
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


def is_rtl() -> bool:
    """Check if current language is RTL."""
    return st.session_state.get("language", "en") in ("ar", "ur")


# ─────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_shipment_data() -> pd.DataFrame:
    """Fetch active drop-off shipments from Redash."""
    try:
        resp = requests.get(REDASH_API_URL, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(BytesIO(resp.content))
        return df
    except Exception as e:
        st.error(f"API Error: {e}")
        return pd.DataFrame()


def get_shipment(shipment_key: str) -> dict | None:
    """Look up a specific shipment by key."""
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
    """
    Analyze uploaded image for quality issues.
    
    Returns:
        dict with keys:
            - passed: bool
            - reasons: list of translation keys for failure reasons
            - scores: dict of individual metric scores
    """
    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"passed": False, "reasons": ["reason_no_document"], "scores": {}}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]
    reasons = []
    scores = {}

    # 1. Resolution check
    scores["resolution"] = f"{w}x{h}"
    if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
        reasons.append("reason_low_res")

    # 2. Blur detection (Laplacian variance)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    scores["sharpness"] = round(laplacian_var, 1)
    if laplacian_var < BLUR_THRESHOLD:
        reasons.append("reason_blurry")

    # 3. Brightness analysis
    mean_brightness = np.mean(gray)
    scores["brightness"] = round(mean_brightness, 1)
    if mean_brightness < DARK_THRESHOLD:
        reasons.append("reason_dark")
    elif mean_brightness > BRIGHT_THRESHOLD:
        reasons.append("reason_bright")

    # 4. Document/edge detection — checks if there's meaningful content
    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = np.count_nonzero(edges) / (h * w)
    scores["edge_ratio"] = round(edge_ratio, 4)
    if edge_ratio < MIN_EDGE_RATIO:
        reasons.append("reason_no_document")

    # 5. Local blur / smudge detection (check if large regions are uniformly blurry)
    # Split image into grid and check for locally blurry patches
    block_size = 4
    bh, bw = h // block_size, w // block_size
    blurry_blocks = 0
    total_blocks = block_size * block_size
    for i in range(block_size):
        for j in range(block_size):
            block = gray[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw]
            block_var = cv2.Laplacian(block, cv2.CV_64F).var()
            if block_var < BLUR_THRESHOLD * 0.5:
                blurry_blocks += 1
    scores["blurry_regions"] = f"{blurry_blocks}/{total_blocks}"
    # If more than 60% of blocks are blurry and we haven't already flagged blur
    if blurry_blocks > total_blocks * 0.6 and "reason_blurry" not in reasons:
        reasons.append("reason_blurry")

    return {
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "scores": scores,
    }


# ─────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────
def save_pod_image(shipment_key: str, image_bytes: bytes, index: int = 0) -> str:
    """
    Save POD image to storage. Returns the file path.
    
    In production, replace this with S3/GCS upload.
    """
    shipment_dir = os.path.join(POD_STORAGE_DIR, shipment_key)
    os.makedirs(shipment_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pod_{index}_{timestamp}.jpg"
    filepath = os.path.join(shipment_dir, filename)

    # Save image
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    return filepath


def save_pod_metadata(shipment_key: str, shipment_data: dict, file_paths: list, mode: str):
    """Save metadata JSON alongside POD images."""
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
        "upload_mode": mode,  # "single" or "fallback_triple"
        "file_paths": file_paths,
        "uploaded_at": datetime.now().isoformat(),
        "language": st.session_state.get("language", "en"),
    }

    meta_path = os.path.join(shipment_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return meta_path


def get_existing_submission(shipment_key: str) -> dict | None:
    """
    Check if a POD has already been submitted for this shipment.
    Returns the metadata dict if found, None otherwise.
    """
    meta_path = os.path.join(POD_STORAGE_DIR, shipment_key, "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


# ─────────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────────
def inject_rtl_css():
    """Inject RTL styling for Arabic/Urdu."""
    if is_rtl():
        st.markdown("""
        <style>
            .stApp { direction: rtl; text-align: right; }
            .stMarkdown, .stText { direction: rtl; text-align: right; }
            .stCheckbox > label { direction: rtl; }
            div[data-testid="stMetricValue"] { direction: ltr; }
        </style>
        """, unsafe_allow_html=True)


def inject_mobile_css():
    """Optimize layout for mobile devices."""
    st.markdown("""
    <style>
        /* Mobile-first responsive design */
        .block-container { 
            padding: 4rem 1rem 3rem 1rem !important; 
            max-width: 100% !important; 
        }
        /* Push content below Streamlit toolbar */
        header[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.95) !important;
            backdrop-filter: blur(10px);
        }
        /* Hide hamburger menu and footer on mobile for cleaner driver experience */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: visible !important; height: 2.5rem !important; }
        section[data-testid="stSidebar"] { display: none; }
        /* Larger touch targets */
        .stButton > button { 
            width: 100%; 
            padding: 0.75rem 1.5rem !important; 
            font-size: 1.1rem !important;
            min-height: 3rem;
        }
        .stCheckbox > label { 
            font-size: 1rem !important; 
            padding: 0.5rem 0 !important;
        }
        /* Success animation */
        @keyframes checkmark {
            0% { transform: scale(0); }
            50% { transform: scale(1.2); }
            100% { transform: scale(1); }
        }
        .success-icon { 
            animation: checkmark 0.5s ease-in-out; 
            font-size: 4rem; 
            text-align: center; 
        }
        /* Info cards */
        .detail-card {
            background: #f0f2f6;
            border-radius: 10px;
            padding: 1rem;
            margin: 0.5rem 0;
            border-left: 4px solid #1f77b4;
        }
        .detail-card.rtl {
            border-left: none;
            border-right: 4px solid #1f77b4;
        }
        /* Quality score badges */
        .quality-badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 1rem;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .quality-pass { background: #d4edda; color: #155724; }
        .quality-fail { background: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_html=True)


def render_language_selection():
    """Step 1: Language selection page."""
    st.markdown(
        "<h1 style='text-align:center;'>📄 Proof of Delivery</h1>"
        "<h3 style='text-align:center;'>إثبات التسليم | ڈیلیوری کا ثبوت</h3>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown(
        "<h4 style='text-align:center;'>Select your language / اختر لغتك / اپنی زبان منتخب کریں</h4>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🇬🇧 English", use_container_width=True, key="btn_en"):
            st.session_state.language = "en"
            st.session_state.step = "confirm"
            st.rerun()
    with col2:
        if st.button("🇸🇦 العربية", use_container_width=True, key="btn_ar"):
            st.session_state.language = "ar"
            st.session_state.step = "confirm"
            st.rerun()
    with col3:
        if st.button("🇵🇰 اردو", use_container_width=True, key="btn_ur"):
            st.session_state.language = "ur"
            st.session_state.step = "confirm"
            st.rerun()


def render_confirmation(shipment: dict):
    """Step 2: Show driver/shipment details and ask for confirmation."""
    inject_rtl_css()

    st.markdown(f"### {t('confirm_details')}")

    # Driver details card
    border_side = "right" if is_rtl() else "left"
    st.markdown(f"""
    <div class="detail-card {'rtl' if is_rtl() else ''}">
        <p><strong>👤 {t('driver_name')}:</strong> {shipment.get('carrier', 'N/A')}</p>
        <p><strong>📱 {t('phone_number')}:</strong> {shipment.get('carrier_mobile', 'N/A')}</p>
        <p><strong>🚛 {t('license_plate')}:</strong> {shipment.get('vehicle_plate', 'N/A')}</p>
    </div>
    """, unsafe_allow_html=True)

    # Shipment details
    st.markdown(f"""
    <div class="detail-card {'rtl' if is_rtl() else ''}">
        <p><strong>🔑 {t('shipment_ref')}:</strong> {shipment.get('key', 'N/A')}</p>
        <p><strong>🏭 {t('shipper')}:</strong> {shipment.get('entity', 'N/A')}</p>
        <p><strong>📦 {t('commodity')}:</strong> {shipment.get('commodity', 'N/A')}</p>
        <p><strong>⚖️ {t('weight')}:</strong> {shipment.get('weight', 0)}</p>
        <p><strong>📍 {t('pickup')}:</strong> {shipment.get('pickup_name', '')} — {shipment.get('pickup_city', '')}</p>
        <p><strong>🏁 {t('destination')}:</strong> {shipment.get('destination_name', '')} — {shipment.get('destination_city', '')}</p>
        <p><strong>📊 {t('status')}:</strong> ✅ {t('at_dropoff')}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    confirmed = st.checkbox(t("confirm_checkbox"), key="details_confirmed")

    if confirmed:
        if st.button(t("proceed"), type="primary", use_container_width=True):
            st.session_state.step = "upload"
            st.rerun()


def render_upload(shipment: dict):
    """Step 3: POD upload with quality checking."""
    inject_rtl_css()

    st.markdown(f"### {t('upload_title')}")
    st.markdown(f"**{t('shipment_ref')}:** {shipment.get('key', '')}")
    st.markdown("---")

    # Initialize attempt counter
    if "quality_attempts" not in st.session_state:
        st.session_state.quality_attempts = 0
    if "pod_submitted" not in st.session_state:
        st.session_state.pod_submitted = False
    if "in_fallback_mode" not in st.session_state:
        st.session_state.in_fallback_mode = False

    # Check if we're in fallback mode (3 failed quality attempts)
    if st.session_state.in_fallback_mode:
        render_fallback_upload(shipment)
        return

    # Show photo instructions
    st.info(t("upload_instructions"))
    instructions = [t(f"instruction_{i}") for i in range(1, 7)]
    for instr in instructions:
        st.markdown(f"  ✓ {instr}")

    st.markdown("---")

    # Show remaining attempts
    remaining = MAX_QUALITY_ATTEMPTS - st.session_state.quality_attempts
    if st.session_state.quality_attempts > 0:
        st.warning(t("attempts_remaining").format(remaining))

    # Camera input (primary on mobile)
    camera_photo = st.camera_input(t("take_photo"), key=f"camera_{st.session_state.quality_attempts}")

    # File upload (secondary / fallback)
    uploaded_file = st.file_uploader(
        t("upload_file"),
        type=["jpg", "jpeg", "png"],
        key=f"upload_{st.session_state.quality_attempts}",
    )

    # Process whichever input is provided
    image_source = camera_photo or uploaded_file

    if image_source is not None:
        image_bytes = image_source.getvalue()

        # Show preview
        st.image(image_bytes, use_container_width=True)

        # Analyze quality
        with st.spinner(t("analyzing")):
            result = analyze_image_quality(image_bytes)

        if result["passed"]:
            st.success(t("quality_passed"))

            # Show quality scores
            with st.expander("📊 Quality Scores", expanded=False):
                for metric, value in result["scores"].items():
                    st.markdown(f"**{metric}:** {value}")

            # Submit button
            if st.button(t("submit_pod"), type="primary", use_container_width=True):
                with st.spinner("Uploading..."):
                    filepath = save_pod_image(shipment["key"], image_bytes, index=0)
                    save_pod_metadata(
                        shipment["key"], shipment, [filepath], mode="single"
                    )
                    st.session_state.pod_submitted = True
                    st.session_state.step = "success"
                    st.rerun()
        else:
            # Quality failed
            st.error(t("quality_failed"))
            for reason in result["reasons"]:
                st.markdown(f"  ⚠️ {t(reason)}")

            # Show quality scores for debugging
            with st.expander("📊 Quality Scores", expanded=False):
                for metric, value in result["scores"].items():
                    st.markdown(f"**{metric}:** {value}")

            st.session_state.quality_attempts += 1

            if st.session_state.quality_attempts >= MAX_QUALITY_ATTEMPTS:
                st.warning(t("fallback_title"))
                st.session_state.in_fallback_mode = True
                st.rerun()
            else:
                st.info(f"🔄 {t('retake')}")


def render_fallback_upload(shipment: dict):
    """Fallback: upload 3 photos when single-photo quality keeps failing."""
    inject_rtl_css()

    st.warning(t("fallback_title"))
    st.markdown(t("fallback_message"))
    st.markdown("---")

    # Three file uploaders
    photos = []
    for i in range(1, 4):
        label = t("fallback_photo").format(i)
        photo = st.file_uploader(
            label,
            type=["jpg", "jpeg", "png"],
            key=f"fallback_photo_{i}",
        )
        if photo:
            photos.append(photo)
            st.image(photo, caption=label, use_container_width=True)

    st.markdown("---")

    if len(photos) == 3:
        if st.button(t("submit_fallback"), type="primary", use_container_width=True):
            with st.spinner("Uploading..."):
                file_paths = []
                for idx, photo in enumerate(photos):
                    filepath = save_pod_image(
                        shipment["key"], photo.getvalue(), index=idx
                    )
                    file_paths.append(filepath)

                save_pod_metadata(
                    shipment["key"], shipment, file_paths, mode="fallback_triple"
                )
                st.session_state.pod_submitted = True
                st.session_state.step = "success"
                st.rerun()
    elif len(photos) > 0:
        st.info(t("upload_all_three"))


def render_already_submitted(submission: dict, shipment: dict):
    """Show a screen indicating POD was already uploaded, with submission details."""
    # If no language set yet, show language picker first then come back
    if "language" not in st.session_state:
        # Quick language selection inline
        st.markdown(
            "<h2 style='text-align:center;'>📄 Proof of Delivery</h2>",
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🇬🇧 English", use_container_width=True, key="als_en"):
                st.session_state.language = "en"
                st.rerun()
        with col2:
            if st.button("🇸🇦 العربية", use_container_width=True, key="als_ar"):
                st.session_state.language = "ar"
                st.rerun()
        with col3:
            if st.button("🇵🇰 اردو", use_container_width=True, key="als_ur"):
                st.session_state.language = "ur"
                st.rerun()
        st.stop()

    inject_rtl_css()

    st.markdown(
        '<div class="success-icon">✅</div>', unsafe_allow_html=True
    )
    st.markdown(f"## {t('already_submitted_title')}")

    # Parse and format the upload timestamp
    uploaded_at = submission.get("uploaded_at", "unknown")
    try:
        dt = datetime.fromisoformat(uploaded_at)
        formatted_date = dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        formatted_date = uploaded_at

    st.markdown(t("already_submitted_msg").format(formatted_date))

    mode = submission.get("upload_mode", "single")
    mode_display = "Single photo" if mode == "single" else "3 photos (fallback)"
    file_count = len(submission.get("file_paths", []))

    st.markdown(t("already_submitted_mode").format(mode_display))
    st.markdown(t("already_submitted_count").format(file_count))

    # Show thumbnails of uploaded images
    file_paths = submission.get("file_paths", [])
    if file_paths:
        st.markdown("---")
        cols = st.columns(min(len(file_paths), 3))
        for idx, fp in enumerate(file_paths):
            if os.path.exists(fp):
                with cols[idx % 3]:
                    st.image(fp, caption=f"POD #{idx + 1}", use_container_width=True)

    st.markdown("---")

    # Shipment summary
    border_side = "right" if is_rtl() else "left"
    st.markdown(f"""
    <div class="detail-card {'rtl' if is_rtl() else ''}">
        <p><strong>🔑 {t('shipment_ref')}:</strong> {shipment.get('key', 'N/A')}</p>
        <p><strong>👤 {t('driver_name')}:</strong> {shipment.get('carrier', 'N/A')}</p>
        <p><strong>🏁 {t('destination')}:</strong> {shipment.get('destination_name', '')} — {shipment.get('destination_city', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    st.info(t("already_submitted_note"))


def render_success():
    """Step 4: Success confirmation screen."""
    inject_rtl_css()

    st.markdown(
        '<div class="success-icon">✅</div>', unsafe_allow_html=True
    )
    st.markdown(f"## {t('success_title')}")
    st.markdown(t("success_message"))
    st.balloons()


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Trella POD Capture",
        page_icon="📄",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inject_mobile_css()

    # ── Get shipment key from URL query param ──
    params = st.query_params
    shipment_key = params.get("shipment", None)

    if not shipment_key:
        st.error("⚠️ No shipment reference found. Please use the link sent to your phone.")
        st.markdown(
            "**Expected URL format:**  \n"
            "`https://<app-url>/?shipment=<shipment_key>`"
        )
        st.stop()

    # ── Fetch shipment data ──
    shipment = get_shipment(shipment_key)

    if shipment is None:
        # Try fetching fresh data (cache might be stale)
        st.cache_data.clear()
        shipment = get_shipment(shipment_key)

    if shipment is None:
        st.error("⚠️ Shipment not found or not currently at drop-off status.")
        st.markdown(f"**Shipment Key:** `{shipment_key}`")
        st.markdown("Please contact dispatch if you believe this is an error.")
        st.stop()

    # ── Check if POD was already submitted ──
    existing = get_existing_submission(shipment_key)
    if existing and st.session_state.get("step") != "success":
        # POD already uploaded — show the result screen
        render_already_submitted(existing, shipment)
        st.stop()

    # ── Initialize session state ──
    if "step" not in st.session_state:
        st.session_state.step = "language"

    # ── Route to the correct step ──
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
