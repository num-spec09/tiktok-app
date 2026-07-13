# -*- coding: utf-8 -*-
"""
🎬 TikTok Content Builder v6
ใบงานดีไซน์สวยแบบมืออาชีพ (หัวส้ม + ตาราง + การ์ดช็อต) พร้อมภาพประกอบทุกช็อต

ใหม่ใน v6:
- ใบงานถูกจัดหน้าเป็นเอกสาร 2 หน้าดีไซน์เดียวกับตัวอย่าง PDF
  หน้า 1: ตารางข้อมูลสินค้า + สคริปต์ Safe Script
  หน้า 2: Storyboard Shot List เป็นการ์ด พร้อม "ภาพประกอบจริง" ทุกช็อต
- ปุ่มปริ้นอยู่ในตัวเอกสาร ปริ้นออกมาสะอาด ไม่ติด UI ของแอป
- ดาวน์โหลดใบงานเป็นไฟล์ .html เก็บไว้เปิด/ปริ้นทีหลังได้

วิธีรัน:
    pip install streamlit google-genai pillow openai
    python -m streamlit run app.py
"""

import base64
import json
import re
import time

import streamlit as st
import streamlit.components.v1 as components
from google import genai
from PIL import Image

# openai เป็น optional - โหลดเฉพาะตอนผู้ใช้เลือก DALL-E เท่านั้น
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

st.set_page_config(page_title="TikTok Content Builder", page_icon="🎬", layout="wide")

# ===== ตัวช่วยดึงค่าจาก Secrets แบบปลอดภัย =====
# ตอนรันในเครื่องจะยังไม่มีไฟล์ secrets.toml -> st.secrets จะ error
# ฟังก์ชันนี้ครอบ try/except ให้ ถ้าไม่มีก็คืนค่าเริ่มต้นแทน (ไม่พัง)
def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


# ===== ด่านรหัสผ่าน: กันคนนอกที่ไม่ใช่พนักงานเข้ามาใช้ Key บริษัท =====
def check_password() -> bool:
    """ให้ผ่านเมื่อกรอกรหัสตรงกับที่ตั้งไว้ใน Secrets (คีย์ APP_PASSWORD)"""
    correct = get_secret("APP_PASSWORD", None)
    if not correct:
        return True  # ถ้ายังไม่ได้ตั้งรหัสใน Secrets ก็ไม่ล็อก (ตอนทดสอบในเครื่อง)
    if st.session_state.get("password_ok"):
        return True
    st.markdown("""
    <style>
    .stApp { background: #0a0a0a; }
    .stApp p, .stApp label, .stApp span { color: #e8e8e8; }
    .stTextInput input { background:#141414 !important; color:#eee !important;
        border:0.5px solid #2a2a2a !important; border-radius:10px !important; }
    </style>
    <div style="text-align:center; padding: 40px 0 20px;">
      <div style="font-size:40px;">🔒</div>
      <div style="font-size:24px; font-weight:600; color:#fff; margin-top:8px;">TikTok Content Studio</div>
      <div style="color:#8a8a8a; font-size:14px; margin-top:4px;">เครื่องมือภายในทีม · กรุณาใส่รหัสผ่านที่ได้รับจากหัวหน้า</div>
    </div>
    """, unsafe_allow_html=True)
    pwd = st.text_input("รหัสผ่าน", type="password")
    if pwd:
        if pwd == correct:
            st.session_state.password_ok = True
            st.rerun()
        else:
            st.error("รหัสผ่านไม่ถูกต้อง ลองใหม่อีกครั้ง")
    return False

if not check_password():
    st.stop()

# ===== ธีม TikTok พื้นดำ + สีฟ้าไซแอน/ชมพูแดง =====
st.markdown("""
<style>
/* พื้นหลังแอปเป็นสีดำแบบ TikTok */
.stApp { background: #0a0a0a; }
[data-testid="stMainBlockContainer"] { max-width: 1100px; padding-top: 3.5rem; }
/* ให้แถบเครื่องมือด้านบนของ Streamlit โปร่งใสเข้าธีมดำ ไม่บังหัว */
[data-testid="stHeader"] { background: transparent !important; }
/* ข้อความทั่วไปเป็นสีขาว */
.stApp, .stApp p, .stApp label, .stApp span, .stApp div { color: #e8e8e8; }
/* หัวข้อ label ของช่องกรอก */
[data-testid="stTextArea"] label, [data-testid="stFileUploader"] label { color: #fff !important; font-weight: 500 !important; }
/* กล่องกรอกข้อความพื้นเข้ม */
.stTextArea textarea, .stTextInput input {
    background: #141414 !important; color: #eee !important;
    border: 0.5px solid #2a2a2a !important; border-radius: 10px !important;
}
/* ปุ่มอัปโหลด */
[data-testid="stFileUploader"] section {
    background: #141414 !important; border: 1.5px dashed #333 !important; border-radius: 10px !important;
}
/* ปุ่มหลัก (สร้างใบงาน) สีชมพูแดง TikTok */
.stButton button[kind="primary"], .stButton button {
    background: #FE2C55 !important; color: #fff !important;
    border: none !important; border-radius: 10px !important;
    font-weight: 500 !important; font-size: 16px !important; padding: 12px !important;
}
.stButton button:hover { background: #e02248 !important; }
/* Sidebar พื้นเข้ม */
[data-testid="stSidebar"] { background: #111 !important; }
[data-testid="stSidebar"] * { color: #ddd !important; }
/* การ์ดหัวและสถิติ */
.tt-header {
    background: linear-gradient(0deg,#0a0a0a,#0a0a0a); padding: 20px 26px; border-radius: 14px;
    border: 0.5px solid #1f1f1f; display: flex; align-items: center; gap: 14px; margin: 8px 0 18px;
}
.tt-logo { position: relative; width: 44px; height: 44px; flex-shrink: 0; }
.tt-logo .l1,.tt-logo .l2,.tt-logo .l3 { position: absolute; inset: 0; border-radius: 11px; }
.tt-logo .l1 { background:#FE2C55; transform: translate(2px,2px); }
.tt-logo .l2 { background:#00F2EA; transform: translate(-2px,-2px); }
.tt-logo .l3 { background:#0a0a0a; display:flex; align-items:center; justify-content:center; font-size:22px; }
.tt-title { font-size: 21px; font-weight: 600; color: #fff; letter-spacing:-0.3px; }
.tt-sub { font-size: 13px; color: #8a8a8a; }
.tt-stats { display:flex; justify-content:center; gap:26px; margin: 6px 0 22px; }
.tt-stat { text-align:center; }
.tt-stat .n { font-size:22px; font-weight:600; }
.tt-stat .l { font-size:11px; color:#777; }
.tt-divider { width:0.5px; background:#2a2a2a; }
</style>

<div class="tt-header">
  <div class="tt-logo"><div class="l1"></div><div class="l2"></div><div class="l3">🎵</div></div>
  <div>
    <div class="tt-title">TikTok Content Studio</div>
    <div class="tt-sub">สร้างสคริปต์ + สตอรี่บอร์ด 5 สไตล์ จากข้อมูลสินค้า</div>
  </div>
</div>

<div class="tt-stats">
  <div class="tt-stat"><div class="n" style="color:#00F2EA">5</div><div class="l">สไตล์สคริปต์</div></div>
  <div class="tt-divider"></div>
  <div class="tt-stat"><div class="n" style="color:#fff">A–E</div><div class="l">เลือกง่าย</div></div>
  <div class="tt-divider"></div>
  <div class="tt-stat"><div class="n" style="color:#FE2C55">~30วิ</div><div class="l">ต่อใบงาน</div></div>
</div>
""", unsafe_allow_html=True)

# ===== API Key: ดึงจากหลังบ้าน (Secrets) อัตโนมัติ พนักงานไม่ต้องกรอก =====
api_key = get_secret("GEMINI_API_KEY", "")
if api_key:
    st.sidebar.success("🔑 เชื่อมต่อระบบเรียบร้อย")
else:
    # กรณีรันในเครื่องตัวเองที่ยังไม่ได้ตั้ง Secrets ให้กรอกเองได้
    api_key = st.sidebar.text_input("🔑 ใส่ Google Gemini API Key", type="password")
    st.sidebar.caption("ขอ API Key ฟรีได้ที่ aistudio.google.com/apikey")

preferred_model = st.sidebar.selectbox(
    "🧠 โมเดลข้อความ",
    ["อัตโนมัติ (แนะนำ)",
     "gemini-3.1-pro-preview  (Pro - ต้องเปิด billing)",
     "gemini-3.5-flash",
     "gemini-3.1-flash-lite",
     "gemini-2.5-flash"],
    index=0,
    help="รุ่น Pro ฉลาดสุดแต่ต้องเปิด billing ก่อน ถ้าบัญชีใช้ไม่ได้ระบบจะสลับไปตัวอื่นให้อัตโนมัติ",
)
draw_images = st.sidebar.toggle("🎨 ใส่ภาพประกอบในสตอรี่บอร์ด", value=False,
                                help="ค่าเริ่มต้นคือปิด (เอกสารเป็นตัวหนังสือล้วน ประหยัดกระดาษ+เร็วกว่า) เปิดได้ถ้าต้องการภาพ")

image_engine = st.sidebar.radio(
    "🖼️ แหล่งวาดภาพ",
    ["Gemini (Nano Banana) — แนบรูปสินค้าได้ แนะนำ",
     "DALL-E 3 (OpenAI) — ต้องใช้ OpenAI key แยก"],
    index=0,
    help="Nano Banana วาดสินค้าให้ตรงรูปจริงได้ ส่วน DALL-E วาดจากข้อความอย่างเดียว (สินค้าจะไม่ตรงรุ่น)",
)
use_dalle = image_engine.startswith("DALL-E")
openai_key = get_secret("OPENAI_API_KEY", "")
if use_dalle and not openai_key:
    openai_key = st.sidebar.text_input("🔑 ใส่ OpenAI API Key", type="password",
                                       help="ขอที่ platform.openai.com/api-keys (ต้องเติมเงินก่อนใช้)")
    st.sidebar.caption("⚠️ DALL-E วาดจากข้อความเท่านั้น หลอดครีมในภาพอาจไม่ตรงรุ่นสินค้าจริง")

# ===== เลือกประเภทคอนเทนต์ =====
mode = st.radio("📌 เลือกประเภทคอนเทนต์ที่ต้องการ",
                ["🎬 คลิปสั้น", "🔴 ไลฟ์สด", "✨ ทั้งคู่"],
                horizontal=True, index=0)
want_clip = (mode != "🔴 ไลฟ์สด")
want_live = (mode != "🎬 คลิปสั้น")

col1, col2 = st.columns(2)
with col1:
    product_info = st.text_area("🔗 1. วางลิงก์ หรือ พิมพ์รายละเอียดสินค้า", height=150)
with col2:
    uploaded_image = st.file_uploader("📸 2. อัปโหลดรูปภาพสินค้า",
                                      type=["png", "jpg", "jpeg", "webp", "gif", "bmp"])
    if uploaded_image:
        st.image(uploaded_image, width=200, caption="รูปที่อัปโหลด")

if "worksheet_html" not in st.session_state:
    st.session_state.worksheet_html = None
if "shots_data" not in st.session_state:
    st.session_state.shots_data = None
if "used_model" not in st.session_state:
    st.session_state.used_model = None
if "image_note" not in st.session_state:
    st.session_state.image_note = ""

TEXT_MODELS = [
    "gemini-flash-latest", "gemini-3.5-flash", "gemini-3-flash-preview",
    "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite",
]

# ถ้าผู้ใช้เลือกโมเดลเอง ให้เอาตัวนั้นขึ้นเป็นลำดับแรก (ที่เหลือเป็นแผนสำรอง)
if preferred_model != "อัตโนมัติ (แนะนำ)":
    chosen = preferred_model.split()[0]  # ตัดคำอธิบายท้ายชื่อออก
    TEXT_MODELS = [chosen] + [m for m in TEXT_MODELS if m != chosen]
# ชื่อโมเดลสร้างภาพปัจจุบัน (ตระกูล Nano Banana) เรียงจากถูกสุด -> แพงสุด
# หมายเหตุ: การวาดภาพผ่าน API ต้องเปิด billing (ไม่มีโควตาฟรี) ค่าใช้จ่ายราวภาพละ 1-2 บาท
IMAGE_MODELS = [
    "gemini-3.1-flash-lite-image",   # Nano Banana 2 Lite - ถูกและเร็วสุด
    "gemini-3.1-flash-image",        # Nano Banana 2 - คุณภาพดี แนะนำ
    "gemini-2.5-flash-image",        # รุ่นเก่า เผื่อบางบัญชียังใช้ได้
    "gemini-3-pro-image",            # Pro - แพงสุด คุณภาพสูงสุด
]


def call_with_fallback(client, models, contents, max_retries=3):
    last_error = None
    for name in models:
        for attempt in range(max_retries):
            try:
                return client.models.generate_content(model=name, contents=contents), name
            except Exception as e:
                last_error = e
                msg = str(e).lower()
                # 503/overloaded/unavailable = เซิร์ฟเวอร์ Google คนใช้เยอะ -> รอแล้วลองใหม่
                if ("503" in msg or "unavailable" in msg or "overloaded" in msg
                        or "high demand" in msg or "500" in msg):
                    if attempt < max_retries - 1:
                        time.sleep(2 * (attempt + 1))  # รอ 2, 4 วินาที แล้วลองใหม่
                        continue
                    break  # ลองครบแล้วยังไม่ได้ -> ไปโมเดลถัดไป
                # 404/บัญชีใช้ไม่ได้ -> ข้ามไปโมเดลถัดไปทันที
                if ("404" in msg or "not_found" in msg or "not found" in msg
                        or ("429" in msg and ("limit: 0" in msg or "free_tier" in msg))):
                    break
                raise
    raise Exception(f"เซิร์ฟเวอร์ไม่ว่างหรือใช้โมเดลไม่ได้: {last_error}")


def extract_image(resp):
    """คืน (bytes, mime) ของภาพจากคำตอบโมเดลสร้างภาพ"""
    try:
        for part in resp.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data, getattr(inline, "mime_type", None) or "image/png"
    except Exception:
        pass
    return None, None


def to_data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def ascii_safe(text: str) -> str:
    """กรองข้อความให้เหลือเฉพาะอักขระ ASCII ที่ปลอดภัย
    (บางครั้ง AI ใส่ภาษาไทยใน image_prompt มา ทำให้ตัววาดภาพ error)"""
    if not text:
        return ""
    # ตัดอักขระที่ไม่ใช่ ASCII ออก (เช่น อักษรไทย) เหลือแต่อังกฤษ/ตัวเลข/สัญลักษณ์
    cleaned = text.encode("ascii", "ignore").decode("ascii").strip()
    # ถ้ากรองแล้วเหลือน้อยเกินไป (แปลว่า prompt เป็นไทยล้วน) ใช้ข้อความสำรอง
    if len(cleaned) < 10:
        cleaned = "a Thai staff member demonstrating a pink skincare tube product"
    return cleaned


def draw_with_dalle(oa_client, image_prompt: str) -> str:
    image_prompt = ascii_safe(image_prompt)
    """วาดภาพแนวตั้งด้วย DALL-E 3 คืนค่า data URI (base64)"""
    result = oa_client.images.generate(
        model="dall-e-3",
        prompt=("Vertical 9:16 storyboard illustration for a TikTok video shot, "
                "clean flat pastel style, a Thai staff member demonstrating a pink "
                "skincare tube product. " + image_prompt + " No text in the image."),
        size="1024x1792",   # แนวตั้งตามที่กำหนด
        quality="standard",
        n=1,
        response_format="b64_json",
    )
    b64 = result.data[0].b64_json
    return f"data:image/png;base64,{b64}"


# ===== ฐานข้อมูลคำต้องห้ามในโฆษณา TikTok/อย. + คำทดแทนที่ปลอดภัย =====
BANNED_WORDS = {
    "ดีที่สุด": "ดีมาก / โดดเด่น",
    "ที่สุดในโลก": "ระดับท็อป",
    "อันดับ 1": "ยอดนิยม",
    "100%": "อย่างเต็มที่",
    "หายขาด": "ช่วยดูแลให้ดีขึ้น",
    "รักษา": "ช่วยดูแล / บรรเทา",
    "ขาวทันที": "ผิวดูกระจ่างใสขึ้น",
    "ขาวขึ้นทันที": "ผิวดูกระจ่างใสขึ้น",
    "เห็นผลทันที": "เห็นความเปลี่ยนแปลงได้ไว",
    "เห็นผล 100": "ผู้ใช้ส่วนใหญ่พึงพอใจ",
    "ปลอดภัย 100": "ผ่านการทดสอบแล้ว",
    "ไม่มีผลข้างเคียง": "อ่อนโยน",
    "การันตี": "มั่นใจได้",
    "รับประกันผล": "ผู้ใช้จำนวนมากพึงพอใจ",
    "ถูกที่สุด": "คุ้มค่ามาก",
    "ลดน้ำหนัก": "ดูแลรูปร่าง",
    "ผอมเร็ว": "ดูแลรูปร่าง",
    "หน้าเด็ก": "ผิวดูอ่อนเยาว์",
    "เด้งทันที": "ดูเรียบเนียนขึ้น",
    "หายเลย": "ดีขึ้น",
}


def check_banned_words(data: dict) -> list:
    """สแกนทุกข้อความในผลลัพธ์ หาคำต้องห้าม คืนรายการ [{word, suggest, where}]"""
    found, seen = [], set()

    # เพิ่มคำเลี่ยงเฉพาะหมวดที่ AI ระบุ เข้าไปในฐานตรวจด้วย
    dynamic = dict(BANNED_WORDS)
    for a in data.get("avoid_words", []) or []:
        if isinstance(a, dict) and a.get("bad"):
            dynamic[a["bad"]] = a.get("good", "ปรับคำให้เหมาะสม")

    def scan(text, where):
        for w, rep in dynamic.items():
            if w in (text or "") and (w, where) not in seen:
                seen.add((w, where))
                found.append({"word": w, "suggest": rep, "where": where})

    for i, s in enumerate(data.get("scripts", []) or []):
        if not isinstance(s, dict):
            continue
        label = chr(65 + i)
        scan(s.get("hook", ""), f"สคริปต์ {label}")
        scan(s.get("content", ""), f"สคริปต์ {label}")
        for x in s.get("closings", []) or []:
            scan(x, f"ปิดการขาย (สคริปต์ {label})")
        for sh in s.get("shots", []) or []:
            if isinstance(sh, dict):
                scan(sh.get("dialogue", ""), f"สตอรี่บอร์ด {label}")
    for i, lv in enumerate(data.get("live_scripts", []) or []):
        if not isinstance(lv, dict):
            continue
        for seg in lv.get("segments", []) or []:
            if isinstance(seg, dict):
                scan(seg.get("talk", ""), f"ไลฟ์สไตล์ {i+1}")
                scan(seg.get("example", ""), f"ไลฟ์สไตล์ {i+1}")
        for x in lv.get("closings", []) or []:
            scan(x, f"ปิดการขาย (ไลฟ์ {i+1})")
    for c in data.get("closing_lines", []) or []:
        if isinstance(c, dict):
            scan(c.get("clip", ""), "ประโยคปิดการขาย")
            scan(c.get("live", ""), "ประโยคปิดการขาย")
    return found


# ===== แปลศัพท์มุมกล้องภาษาอังกฤษเป็นไทย (เผื่อ AI หลุดมา) =====
CAMERA_TERMS = [
    ("Extreme Close-up", "ถ่ายซูมใกล้มาก เห็นรายละเอียด"),
    ("Extreme Close Up", "ถ่ายซูมใกล้มาก เห็นรายละเอียด"),
    ("Medium Close-up", "ถ่ายใกล้ครึ่งอก"),
    ("Medium Close Up", "ถ่ายใกล้ครึ่งอก"),
    ("Close-up", "ถ่ายใกล้ เน้นใบหน้า/จุดเด่น"),
    ("Close Up", "ถ่ายใกล้ เน้นใบหน้า/จุดเด่น"),
    ("Medium Shot", "ถ่ายครึ่งตัว"),
    ("Full Shot", "ถ่ายเห็นทั้งตัว"),
    ("Wide Shot", "ถ่ายมุมกว้าง เห็นฉากรอบ"),
    ("Long Shot", "ถ่ายระยะไกล เห็นทั้งตัวและฉาก"),
    ("Over the Shoulder", "ถ่ายข้ามไหล่"),
    ("Point of View", "ถ่ายมุมมองบุคคลที่หนึ่ง"),
    ("Top View", "ถ่ายมุมสูง มองจากด้านบน"),
    ("Top-down", "ถ่ายมุมสูง มองจากด้านบน"),
    ("Low Angle", "ถ่ายมุมต่ำ เงยขึ้น"),
    ("High Angle", "ถ่ายมุมสูง ก้มลง"),
    ("ECU", "ถ่ายซูมใกล้มาก"),
    ("MCU", "ถ่ายใกล้ครึ่งอก"),
    ("MS", "ถ่ายครึ่งตัว"),
    ("CU", "ถ่ายใกล้ เน้นใบหน้า"),
    ("POV", "ถ่ายมุมมองบุคคลที่หนึ่ง"),
    ("9:16", "แนวตั้ง 9:16"),
]


def th_camera(text: str) -> str:
    """แปลศัพท์กล้องภาษาอังกฤษในข้อความเป็นไทย"""
    if not text:
        return text
    import re as _re
    out = text
    for en, th in CAMERA_TERMS:
        out = _re.sub(_re.escape(en), th, out, flags=_re.IGNORECASE)
    # เก็บกวาด: ลบวงเล็บที่เนื้อในซ้ำกับข้อความข้างหน้า เช่น "ถ่ายครึ่งตัว (ถ่ายครึ่งตัว)"
    out = _re.sub(r'(\S+)\s*\(\1\)', r'\1', out)
    # ลบคำไทยที่ติดกันซ้ำ เช่น "แนวตั้ง แนวตั้ง"
    out = _re.sub(r'(ถ่าย\S+|แนวตั้ง)\s+\1', r'\1', out)
    # ยุบช่องว่างซ้อน
    out = _re.sub(r'\s{2,}', ' ', out).strip()
    return out


def render_shots(shots, shot_imgs, product_uri, show_images):
    """สร้าง HTML การ์ดสตอรี่บอร์ด; show_images=True จะแสดงภาพประกอบ"""
    html = ""
    for s in shots:
        if not isinstance(s, dict):
            continue
        if show_images and shot_imgs.get(s.get("no")):
            # มีภาพ: วางข้อความซ้าย ภาพขวา
            img_uri = shot_imgs.get(s.get("no"))
            body = f'''<div class="shot-body">
            <div class="shot-text">
              <p><b>บทพูด:</b> "{s.get('dialogue','-')}"</p>
              <p><b>มุมกล้อง:</b> {th_camera(s.get('camera','-'))}</p>
              <p><b>Action พนักงาน:</b> {s.get('action','-')}</p>
            </div>
            <div class="shot-img"><img src="{img_uri}" alt="shot">
              <div class="img-cap">ภาพประกอบ (AI)</div></div>
          </div>'''
        else:
            # ไม่มีภาพ: ข้อความใช้เต็มความกว้าง
            body = f'''<div class="shot-body">
            <div class="shot-text" style="width:100%">
              <p><b>บทพูด:</b> "{s.get('dialogue','-')}"</p>
              <p><b>มุมกล้อง:</b> {th_camera(s.get('camera','-'))}</p>
              <p><b>Action พนักงาน:</b> {s.get('action','-')}</p>
            </div>
          </div>'''
        html += f'''
        <div class="shot-card">
          <div class="shot-head">ช็อตที่ {s.get('no','')}: {s.get('title','')} ({s.get('time','')})</div>
          {body}
        </div>'''
    return html


def build_worksheet_html(data: dict, shot_imgs: dict, product_uri: str,
                         product_link: str) -> str:
    """ประกอบใบงาน 2 หน้าเป็น HTML ดีไซน์แบบตัวอย่าง PDF"""
    features_html = "".join(f"<li>{f}</li>" for f in data.get("features", []))

    # สร้างบล็อกสคริปต์ 5 เวอร์ชัน แต่ละเวอร์ชันตามด้วยสตอรี่บอร์ดของตัวเอง
    scripts = data.get("scripts")
    shots_html = ""  # ในโหมดใหม่ สตอรี่บอร์ดอยู่ในแต่ละสคริปต์แล้ว
    if scripts:
        blocks = ""
        labels = ["A", "B", "C", "D", "E", "F", "G", "H"]  # เผื่อกรณีมีเกิน 5
        for i, s in enumerate(scripts):
            letter = labels[i] if i < len(labels) else str(i + 1)
            body = "".join(f"<p>{p}</p>" for p in s.get("content", "").split("\n") if p.strip())
            hook = s.get("hook", "")
            hook_html = f'<p class="script-hook">🪝 Hook: {hook}</p>' if hook else ""
            cl = s.get("closings", []) or []
            closings_html = ""
            if cl:
                items = "".join(f"<li>{x}</li>" for x in cl)
                closings_html = f'<div class="closings-box"><b>💰 ประโยคปิดการขาย:</b><ul>{items}</ul></div>' 
            # สตอรี่บอร์ดของสคริปต์นี้ (แสดงภาพเฉพาะสายแรกเพื่อประหยัดโควตา)
            shot_list = [x for x in s.get("shots", []) if isinstance(x, dict)]
            sb_html = render_shots(shot_list, shot_imgs, product_uri, show_images=(i == 0))
            blocks += f'''
            <div class="script-block">
              <div class="script-version">
                <div class="script-badge"><span class="letter">{letter}</span> สคริปต์ {letter}: {s.get("style","")}</div>
                {hook_html}
                {body}
                {closings_html}
              </div>
              <h3 class="sb-title">🎬 สตอรี่บอร์ดของสคริปต์ {letter} ({s.get("style","")})</h3>
              {sb_html}
            </div>'''
        script_html = blocks
    else:
        script_html = "".join(f"<p>{p}</p>" for p in data.get("script", "").split("\n") if p.strip())
        shots_html = render_shots([x for x in data.get("shots", []) if isinstance(x, dict)],
                                   shot_imgs, product_uri, show_images=True)

    # ===== ส่วนสคริปต์ไลฟ์สด (ถ้ามี) =====
    live_html = ""
    live_scripts = data.get("live_scripts") or []
    if live_scripts:
        lblocks = ""
        for i, lv in enumerate(live_scripts, 1):
            if not isinstance(lv, dict):
                continue
            seg_html = ""
            for seg in lv.get("segments", []) or []:
                if not isinstance(seg, dict):
                    continue
                seg_html += f'''
                <div class="live-seg">
                  <div class="live-seg-head">{seg.get("name","")} <span class="live-time">{seg.get("time","")}</span></div>
                  <p><b>แนวทางพูด:</b> {seg.get("talk","-")}</p>
                  <p class="live-ex"><b>ตัวอย่างประโยค:</b> {seg.get("example","-")}</p>
                  <p class="live-eng"><b>💬 ดึงมีส่วนร่วม:</b> {seg.get("engagement","-")}</p>
                </div>'''
            lv_cl = lv.get("closings", []) or []
            lv_cl_html = ""
            if lv_cl:
                items = "".join(f"<li>{x}</li>" for x in lv_cl)
                lv_cl_html = f'<div class="closings-box"><b>💰 ประโยคปิดการขาย (ไลฟ์):</b><ul>{items}</ul></div>'
            lblocks += f'''
            <div class="script-block">
              <div class="live-badge">🔴 ไลฟ์สไตล์ {i}: {lv.get("style","")}</div>
              {seg_html}
              {lv_cl_html}
            </div>'''
        live_html = f'''
        <div class="force-new-page"></div>
        <h2 class="section">3. สคริปต์ไลฟ์สด — 3 สไตล์ให้เลือก</h2>
        <p class="note">*เลือกสไตล์ที่เข้ากับคนไลฟ์ ตัวเลขเวลาเป็นแนวทาง ปรับตามหน้างานได้*</p>
        {lblocks}'''

    # ===== ส่วนกฎเฉพาะหมวด + ตารางคำเลี่ยง =====
    closing_html = ""  # ปิดการขายย้ายไปอยู่ในแต่ละสคริปต์/ไลฟ์แล้ว
    category = data.get("category", "")
    cat_rules = data.get("category_rules", []) or []
    avoid = data.get("avoid_words", []) or []
    cat_html = ""
    if category or cat_rules or avoid:
        rules_li = "".join(f"<li>{r}</li>" for r in cat_rules)
        rules_block = f'<div class="cat-rules"><b>⚠️ กฎโฆษณาที่ต้องระวังสำหรับหมวด \"{category}\":</b><ul>{rules_li}</ul></div>' if cat_rules else ""
        avoid_rows = ""
        for a in avoid:
            if isinstance(a, dict):
                avoid_rows += f'''<tr>
                  <td class="bad-word">{a.get("bad","")}</td>
                  <td class="good-word">{a.get("good","")}</td>
                  <td>{a.get("why","-")}</td>
                </tr>'''
        avoid_table = f'''<table class="avoid-table">
          <tr><th>คำที่ควรเลี่ยง</th><th>ใช้คำนี้แทน</th><th>เหตุผล</th></tr>
          {avoid_rows}
        </table>''' if avoid_rows else ""
        cat_html = f'''
        <div class="force-new-page"></div>
        <h2 class="section">📋 กฎโฆษณา + คำเลี่ยงเฉพาะหมวดสินค้า</h2>
        <p class="note">*หมวดสินค้า: <b>{category}</b> — คำเลี่ยงด้านล่างปรับตามประเภทสินค้านี้โดยเฉพาะ*</p>
        {rules_block}
        {avoid_table}'''

    # ===== ส่วนตรวจคำต้องห้าม =====
    banned_html = ""
    banned_found = check_banned_words(data)
    if banned_found:
        rows = ""
        for b in banned_found:
            rows += f'''<tr>
              <td class="bad-word">{b["word"]}</td>
              <td class="good-word">{b["suggest"]}</td>
              <td>{b["where"]}</td>
            </tr>'''
        banned_html = f'''
        <div class="banned-box">
          <div class="banned-title">⚠️ ตรวจพบคำที่ควรเลี่ยง {len(banned_found)} จุด</div>
          <p class="note">ระบบพบคำที่อาจผิดกฎโฆษณา แนะนำแก้เป็นคำในคอลัมน์ขวาก่อนใช้จริง</p>
          <table class="banned-table">
            <tr><th>คำที่พบ</th><th>แนะนำเปลี่ยนเป็น</th><th>อยู่ตรงไหน</th></tr>
            {rows}
          </table>
        </div>'''
    else:
        banned_html = '''<div class="banned-box ok">
          <div class="banned-title" style="color:#0F6E56">✅ ไม่พบคำต้องห้าม</div>
          <p class="note">ระบบตรวจแล้วไม่พบคำที่ผิดกฎโฆษณา แต่แนะนำให้คนตรวจอีกครั้งก่อนถ่ายจริง</p>
        </div>'''

    clip_heading = ""
    if data.get("scripts"):
        clip_heading = (
            '<h2 class="section">2. สคริปต์ + สตอรี่บอร์ด — เลือกสไตล์ A ถึง E (TikTok Safe Script)</h2>'
            '<p class="note">*วิธีใช้: พนักงานเลือกสคริปต์ที่ชอบ (บอกหัวหน้าได้เลยว่าเอา A/B/C/D/E) '
            'แล้วถ่ายตามสตอรี่บอร์ดของสคริปต์นั้น*</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>ใบงานผลิตคอนเทนต์ TikTok</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', 'Leelawadee UI', 'Sarabun', sans-serif;
    background: #FBF1EE; color: #333; padding: 24px;
    font-size: 15px; line-height: 1.7;
  }}
  .banner {{
    background: #E8714F; color: white; text-align: center;
    border-radius: 10px; padding: 18px 10px; margin-bottom: 22px;
  }}
  .banner h1 {{ font-size: 24px; }}
  .banner p {{ opacity: .9; margin-top: 4px; }}
  h2.section {{
    border-left: 6px solid #E8714F; padding-left: 10px;
    color: #C4502F; font-size: 19px; margin: 22px 0 12px;
  }}
  table.product {{
    width: 100%; border-collapse: collapse; background: white;
    border-radius: 8px; overflow: hidden;
  }}
  table.product td {{ border: 1px solid #F1D9D1; padding: 10px 14px; vertical-align: top; }}
  table.product td.k {{ background: #FDF6F3; font-weight: bold; width: 190px; }}
  table.product ul {{ margin-left: 18px; }}
  a {{ color: #E8714F; word-break: break-all; }}
  .note {{ font-size: 13px; color: #8A6A60; font-style: italic; margin-bottom: 8px; }}
  .avoid-break {{ page-break-inside: avoid; break-inside: avoid; }}
  .script-version {{
    background: white; border: 1px solid #F1D9D1; border-radius: 10px;
    padding: 14px 18px; margin-bottom: 14px;
  }}
  .script-badge {{
    display: inline-flex; align-items: center; gap: 8px;
    background: #FBE3DA; color: #C4502F;
    font-weight: bold; padding: 6px 16px 6px 6px; border-radius: 24px;
    margin-bottom: 10px; font-size: 16px;
  }}
  .script-badge .letter {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; border-radius: 50%;
    background: #E8714F; color: white; font-size: 17px; font-weight: bold;
  }}
  .script-hook {{ color: #C4502F; font-weight: bold; margin-bottom: 8px; }}
  .sb-title {{ color: #C4502F; font-size: 16px; margin: 14px 0 10px;
    padding-left: 8px; border-left: 4px solid #E8A48D; }}
  .script-block {{ margin-bottom: 22px; padding-bottom: 8px;
    border-bottom: 1px dashed #E5CDC4; }}
  .script-box {{
    background: white; border: 2px dashed #E8A48D; border-radius: 10px;
    padding: 16px 20px;
  }}
  .script-box p {{ margin-bottom: 12px; }}
  .product-hero {{ text-align: center; margin: 14px 0; }}
  .product-hero img {{ max-height: 220px; border-radius: 8px; }}
  .shot-card {{
    background: white; border: 1px solid #F1D9D1; border-radius: 10px;
    margin-bottom: 16px; overflow: hidden; page-break-inside: avoid;
  }}
  .shot-head {{
    background: #FBE3DA; color: #C4502F; font-weight: bold;
    padding: 10px 16px; font-size: 16px;
  }}
  .shot-body {{ display: flex; gap: 14px; padding: 14px 16px; }}
  .shot-text {{ flex: 1; }}
  .shot-text p {{ margin-bottom: 8px; }}
  .shot-img {{ width: 200px; flex-shrink: 0; text-align: center; }}
  .shot-img img {{
    width: 100%; max-height: 300px; object-fit: cover;
    border: 1px solid #E5CDC4; border-radius: 8px; background: #f5f5f5;
  }}
  .img-cap {{ font-size: 12px; color: #8A6A60; margin-top: 4px; }}
  .page-break {{ page-break-before: always; }}
  .live-badge {{ display:inline-block; background:#0a0a0a; color:#00F2EA;
    font-weight:bold; padding:6px 16px; border-radius:8px; margin-bottom:10px; font-size:16px; }}
  .live-seg {{ background:white; border:1px solid #F1D9D1; border-left:4px solid #00c4bd;
    border-radius:6px; padding:10px 14px; margin-bottom:10px; }}
  .live-seg-head {{ font-weight:bold; color:#0a7a75; margin-bottom:6px; }}
  .live-time {{ color:#888; font-size:13px; font-weight:normal; }}
  .live-ex {{ background:#f0fbfa; border-radius:4px; padding:6px 10px; }}
  .live-eng {{ color:#C4502F; }}
  .closing-table, .banned-table {{ width:100%; border-collapse:collapse; background:white; }}
  .closing-table th, .banned-table th {{ background:#FBE3DA; color:#C4502F; padding:8px 12px; text-align:left; font-size:14px; }}
  .closing-table td, .banned-table td {{ border:1px solid #F1D9D1; padding:8px 12px; vertical-align:top; }}
  .cl-type {{ background:#FDF6F3; font-weight:bold; width:150px; }}
  .banned-box {{ background:#FCEBEB; border:1px solid #F09595; border-radius:10px; padding:14px 18px; margin-top:16px; }}
  .banned-box.ok {{ background:#E1F5EE; border-color:#5DCAA5; }}
  .banned-title {{ font-weight:bold; color:#A32D2D; font-size:16px; margin-bottom:4px; }}
  .bad-word {{ color:#A32D2D; font-weight:bold; text-decoration:line-through; }}
  .good-word {{ color:#0F6E56; font-weight:bold; }}
  .closings-box {{ background:#FDF6F3; border-left:3px solid #E8714F; border-radius:0 6px 6px 0;
    padding:8px 14px; margin-top:10px; }}
  .closings-box ul {{ margin:4px 0 0 18px; }}
  .closings-box li {{ margin-bottom:4px; }}
  .cat-rules {{ background:#FFF8E8; border:1px solid #FAC775; border-radius:8px;
    padding:12px 16px; margin-bottom:14px; }}
  .cat-rules ul {{ margin:6px 0 0 18px; }}
  .cat-rules li {{ margin-bottom:5px; }}
  .avoid-table {{ width:100%; border-collapse:collapse; background:white; }}
  .avoid-table th {{ background:#FBE3DA; color:#C4502F; padding:8px 12px; text-align:left; font-size:14px; }}
  .avoid-table td {{ border:1px solid #F1D9D1; padding:8px 12px; vertical-align:top; }}
  .toolbar {{ text-align: center; margin: 20px 0; }}
  .print-btn {{
    background: #E8714F; color: white; border: none; border-radius: 8px;
    padding: 12px 34px; font-size: 17px; font-weight: bold; cursor: pointer;
    font-family: inherit;
  }}
  @media print {{
    @page {{ size: A4; margin: 12mm; }}
    body {{ background: white; padding: 0; }}
    .toolbar {{ display: none; }}
    /* คุมขนาดภาพไม่ให้ล้นหน้ากระดาษ และไม่ให้การ์ดถูกตัดครึ่งข้ามหน้า */
    .shot-card {{ page-break-inside: avoid; }}
    .script-box {{ page-break-inside: avoid; break-inside: avoid; }}
    h2.section {{ page-break-after: avoid; }}
    .force-new-page {{ page-break-before: always; }}
    /* ไม่ล็อกทั้งก้อน script-block แล้ว เพื่อให้เนื้อหาไหลเต็มทุกหน้า (ประหยัดกระดาษสุด) */
    /* กันแค่ระดับย่อย: กล่องสคริปต์ และการ์ดช็อตเดียว ไม่ให้ถูกตัดกลาง */
    .script-version {{ page-break-inside: avoid; break-inside: avoid; }}
    .shot-card {{ page-break-inside: avoid; break-inside: avoid; }}
    .sb-title {{ page-break-after: avoid; }}
    .shot-img {{ width: 170px; }}
    .shot-img img {{ max-height: 210px; }}
    .banner {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .shot-head {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>

<div class="toolbar">
  <button class="print-btn" onclick="window.print()">🖨️ กดปริ้นใบงาน (Print)</button>
</div>

<!-- ==================== หน้า 1 ==================== -->
<div class="banner">
  <h1>ใบงานผลิตคอนเทนต์ TikTok</h1>
  <p>ข้อมูลสินค้า + สคริปต์ 5 สไตล์ พร้อมสตอรี่บอร์ด</p>
</div>

<h2 class="section">1. รายละเอียดข้อมูลสินค้า (Product Details)</h2>
<table class="product">
  <tr><td class="k">ชื่อสินค้า</td><td><b>{data.get('product_name','-')}</b></td></tr>
  <tr><td class="k">ลิงก์ / ข้อมูลสินค้า</td><td>{product_link}</td></tr>
  <tr><td class="k">คุณสมบัติเด่น<br>(วิเคราะห์จากรูปภาพ)</td><td><ul>{features_html}</ul></td></tr>
  <tr><td class="k">รูปภาพสินค้าอ้างอิง</td>
      <td><div class="product-hero"><img src="{product_uri}" alt="product"></div></td></tr>
</table>

{clip_heading}
{script_html}
{live_html}
{cat_html}
{banned_html}

<div class="toolbar">
  <button class="print-btn" onclick="window.print()">🖨️ กดปริ้นใบงาน (Print)</button>
</div>

</body>
</html>"""


# ==========================================
# ประมวลผล
# ==========================================
if st.button("🚀 สร้างใบงาน (Generate)", type="primary", use_container_width=True):
    if not api_key:
        st.warning("⚠️ กรุณาใส่ Gemini API Key ที่แถบด้านข้างก่อนครับ")
    elif not product_info or not uploaded_image:
        st.warning("⚠️ กรุณาใส่ข้อมูลให้ครบทั้ง รายละเอียดสินค้า และ รูปภาพ ครับ")
    else:
        try:
            # ตรวจสอบ key: ต้องเป็น ASCII (a-z, 0-9, สัญลักษณ์) เท่านั้น
            # ถ้ามีอักขระไทยหรือช่องว่างแปลกปลอมติดมาตอนวางใน Secrets จะ error
            clean_key = api_key.strip()
            try:
                clean_key.encode("ascii")
            except UnicodeEncodeError:
                st.error("❌ API Key มีอักขระที่ไม่ถูกต้อง (อาจมีภาษาไทยหรือช่องว่างพิเศษติดมา) "
                         "กรุณาตรวจสอบค่า GEMINI_API_KEY ใน Settings ของแอป")
                st.stop()
            client = genai.Client(api_key=clean_key)
            img = Image.open(uploaded_image)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # ---------- ขั้น 1: ให้ AI วิเคราะห์และวางโครงใบงานทั้งหมดเป็น JSON ----------
            with st.spinner("📝 (1/2) กำลังวิเคราะห์สินค้าและเขียนสคริปต์..."):
                # ประกอบ prompt ตามโหมดที่เลือก (คลิป/ไลฟ์/ทั้งคู่)
                p_head = (
                    "คุณคือผู้เชี่ยวชาญด้าน E-commerce, TikTok, การไลฟ์ขายของ และกฎหมายโฆษณาไทย (อย./สคบ./กสทช.)\n"
                    "วิเคราะห์ข้อมูลสินค้า+รูปภาพที่แนบมา แล้วตอบกลับเป็น JSON เท่านั้น "
                    "ห้ามมีข้อความอื่น รูปแบบ:\n{\n"
                    '  "product_name": "ชื่อสินค้า (ไทย + อังกฤษถ้ามี) พร้อมขนาด",\n'
                    '  "category": "หมวดสินค้า เช่น สกินแคร์/เครื่องสำอาง/อาหารเสริม/อาหาร-เครื่องดื่ม/แฟชั่น/ของใช้ในบ้าน/แกดเจ็ต ฯลฯ",\n'
                    '  "category_rules": ["กฎโฆษณาที่ต้องระวังเฉพาะหมวดนี้ 3-5 ข้อ เช่น สกินแคร์ห้ามเคลมรักษาสิว/ขาวถาวร, อาหารเสริมห้ามอ้างรักษาโรค"],\n'
                    '  "avoid_words": [{"bad": "คำที่ห้ามใช้เฉพาะหมวดนี้", "good": "คำเลี่ยงที่ปลอดภัย", "why": "เหตุผลสั้นๆ"}],\n'
                    '  "features": ["จุดเด่น 4-5 ข้อ"],\n'
                )
                p_clip = (
                    '  "scripts": [\n'
                    '    {"style": "สายฮา สนุกสนาน", "hook": "ประโยคเปิดสั้นๆ",\n'
                    '     "content": "สคริปต์ฉบับเต็ม แบ่งย่อหน้าด้วยการขึ้นบรรทัดใหม่ (Hook-เนื้อหา-CTA)",\n'
                    '     "closings": ["ประโยคปิดการขายสำหรับคลิป 2-3 ประโยค ติดหู กระตุ้นให้กดซื้อ"],\n'
                    '     "shots": [{"no": 1, "title": "ชื่อช็อต", "time": "0.00 - 0.05 วินาที",\n'
                    '       "camera": "มุมกล้องเป็นภาษาไทยที่คนทั่วไปเข้าใจ เช่น ถ่ายครึ่งตัว/ถ่ายใกล้เน้นใบหน้า/ถ่ายเห็นทั้งตัว/ถ่ายซูมใกล้มากเห็นรายละเอียด", "action": "ท่าทางพนักงาน",\n'
                    '       "dialogue": "บทพูด", "image_prompt": "English prompt"}]},\n'
                    '    {อีก 4 สไตล์โครงเดียวกัน (มี closings + shots): สายให้ความรู้ / สายรีวิวจริงใจ / สายเล่าปัญหา Storytelling / สายกระตุ้นให้รีบซื้อ Urgency}\n'
                    '  ],\n'
                )
                p_live = (
                    '  "live_scripts": [\n'
                    '    {"style": "สายขายตรง จัดโปรแรง",\n'
                    '     "segments": [{"name": "เปิดไลฟ์ดึงคนเข้า", "time": "นาทีที่ 0-5",\n'
                    '       "talk": "แนวทางการพูดช่วงนี้",\n'
                    '       "example": "ตัวอย่างประโยคพูดจริง 2-3 ประโยค",\n'
                    '       "engagement": "เทคนิคดึงคนดูมีส่วนร่วม"}],\n'
                    '     "closings": ["ประโยคปิดการขายสำหรับไลฟ์ 2-3 ประโยค ติดหู กระตุ้นให้กดซื้อ"]},\n'
                    '    {อีก 2 สไตล์โครงเดียวกัน (มี segments + closings): สายเอนเตอร์เทน คุยสนุก / สายให้ความรู้ สาธิตละเอียด}\n'
                    '  ],\n'
                )
                p_tail = '  "_end": true\n}\n'

                rules = []
                rules.append("- category ระบุหมวดสินค้าให้ชัด และ category_rules บอกกฎโฆษณาเฉพาะหมวดนั้น 3-5 ข้อ")
                rules.append("- avoid_words ให้คำที่ห้ามใช้เฉพาะหมวดนี้พร้อมคำเลี่ยง 6-10 คู่ (ปรับตามประเภทสินค้าจริง)")
                if want_clip:
                    rules.append("- scripts ครบ 5 เวอร์ชัน เนื้อหาต่างกันจริง แต่ละเวอร์ชันมี closings (ปิดการขาย 2-3 ประโยค) และ shots 5 ช็อตของตัวเอง เวลารวม ~45 วินาที")
                if want_live:
                    rules.append("- live_scripts ครบ 3 สไตล์ แต่ละสไตล์มี segments 4-5 ช่วง (เปิดไลฟ์/แนะนำ/สาธิต/ตอบคำถาม/ปิดการขาย) และ closings (ปิดการขาย 2-3 ประโยค)")
                rules.append("ทุกข้อความเป็นภาษาไทย (ยกเว้น image_prompt เป็นอังกฤษ)")
                rules.append("- ช่อง camera (มุมกล้อง) ห้ามใช้ศัพท์กล้องภาษาอังกฤษ เช่น Medium Shot, Close-up, MCU ให้เขียนเป็นภาษาไทยที่พนักงานถ่ายเข้าใจทันที เช่น ถ่ายครึ่งตัว, ถ่ายใกล้เน้นหน้า, ถ่ายซูมใกล้มาก")
                rules.append("ห้ามใช้คำต้องห้ามโฆษณา เช่น ดีที่สุด, 100%, ขาวทันที, หายขาด, รักษา, การันตี และคำเฉพาะหมวดใน avoid_words ให้ใช้คำเลี่ยงที่ปลอดภัยเสมอ")

                main_prompt = (p_head
                               + (p_clip if want_clip else "")
                               + (p_live if want_live else "")
                               + p_tail
                               + "\n".join(rules))
                resp1, used_model = call_with_fallback(
                    client, TEXT_MODELS, [main_prompt, product_info, img])
                raw = re.sub(r"^```(json)?|```$", "", resp1.text.strip(),
                             flags=re.MULTILINE).strip()
                data = json.loads(raw)
                st.session_state.used_model = used_model

            # ---------- ขั้น 2: วาดภาพประกอบแต่ละช็อต ----------
            shot_imgs = {}
            st.session_state.image_note = ""

            # เตรียม client ของ DALL-E ถ้าเลือกใช้
            oa_client = None
            if draw_images and use_dalle:
                if OpenAI is None:
                    st.session_state.image_note = ("ยังไม่ได้ติดตั้งไลบรารี openai "
                        "ให้รัน: pip install openai แล้วลองใหม่ (ตอนนี้ใช้รูปสินค้าจริงแทน)")
                    draw_images = False
                elif not openai_key:
                    st.session_state.image_note = ("เลือก DALL-E แต่ยังไม่ได้ใส่ OpenAI API Key "
                        "(ตอนนี้ใช้รูปสินค้าจริงแทน)")
                    draw_images = False
                else:
                    oa_client = OpenAI(api_key=openai_key.strip())

            if draw_images:
                engine_label = "DALL-E 3" if use_dalle else "Gemini (Nano Banana)"
                progress = st.progress(0, text=f"🎨 (2/2) กำลังวาดภาพประกอบ (สายแรก) ด้วย {engine_label}...")
                image_model_ok = True
                # ดึง shots จากสคริปต์สายแรก (วาดภาพชุดเดียวเพื่อประหยัดโควตา)
                scripts_data = data.get("scripts", [])
                if scripts_data and isinstance(scripts_data[0], dict):
                    shots = [x for x in scripts_data[0].get("shots", []) if isinstance(x, dict)]
                else:
                    shots = [x for x in data.get("shots", []) if isinstance(x, dict)]
                for i, shot in enumerate(shots):
                    if not image_model_ok:
                        break
                    try:
                        prompt_txt = ascii_safe(shot.get("image_prompt", ""))
                        if use_dalle:
                            # DALL-E: ข้อความอย่างเดียว
                            shot_imgs[shot["no"]] = draw_with_dalle(oa_client, prompt_txt)
                        else:
                            # Nano Banana: แนบรูปสินค้าจริงไปด้วย
                            p = ("Simple clean storyboard illustration, flat pastel colors, "
                                 "vertical 9:16 phone-video framing: " + prompt_txt
                                 + " The product must look like the attached product photo. "
                                 + "No text or words in the image.")
                            resp_img, _ = call_with_fallback(client, IMAGE_MODELS, [p, img])
                            img_bytes, mime = extract_image(resp_img)
                            if img_bytes:
                                shot_imgs[shot["no"]] = to_data_uri(img_bytes, mime)
                    except Exception as img_err:
                        image_model_ok = False
                        st.session_state.image_note = (
                            f"วาดภาพด้วย {engine_label} ไม่สำเร็จ ระบบใช้รูปสินค้าจริงแทน | สาเหตุ: "
                            + str(img_err)[:300])
                    progress.progress((i + 1) / max(len(shots), 1),
                                      text=f"🎨 (2/2) วาดภาพช็อตที่ {i + 1}/{len(shots)}...")
                progress.empty()
            else:
                if not st.session_state.image_note:
                    st.session_state.image_note = "โหมดตัวหนังสือล้วน (ไม่มีภาพประกอบ) — เอกสารกระชับ ประหยัดกระดาษ"

            # ---------- ประกอบใบงาน HTML ----------
            uploaded_image.seek(0)
            product_uri = to_data_uri(uploaded_image.getvalue(),
                                      uploaded_image.type or "image/jpeg")
            link_text = product_info.strip().replace("\n", " ")
            if link_text.startswith("http"):
                product_link = f'<a href="{link_text.split(" ")[0]}">{link_text.split(" ")[0][:90]}...</a>'
            else:
                product_link = link_text[:180] + ("..." if len(link_text) > 180 else "")

            st.session_state.worksheet_html = build_worksheet_html(
                data, shot_imgs, product_uri, product_link)
            _sd = data.get("scripts", [])
            if _sd and isinstance(_sd[0], dict):
                st.session_state.shots_data = _sd[0].get("shots", [])
            else:
                st.session_state.shots_data = data.get("shots", [])

        except json.JSONDecodeError:
            st.error("AI ตอบกลับมาในรูปแบบที่อ่านไม่ได้ ลองกดสร้างใหม่อีกครั้งครับ")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
            st.info("ตรวจสอบว่า API Key ถูกต้อง และยังไม่เกินโควตาการใช้งาน")

# ==========================================
# แสดงใบงาน
# ==========================================
if st.session_state.worksheet_html:
    st.success(f"✅ สร้างใบงานสำเร็จ! (โมเดลข้อความ: {st.session_state.used_model})")
    if st.session_state.image_note:
        st.info("ℹ️ " + st.session_state.image_note)

    st.download_button("💾 ดาวน์โหลดใบงาน (.html — เปิด/ปริ้นทีหลังได้)",
                       data=st.session_state.worksheet_html,
                       file_name="tiktok_worksheet.html", mime="text/html",
                       use_container_width=True)

    components.html(st.session_state.worksheet_html, height=1400, scrolling=True)
    st.caption("💡 กดปุ่มปริ้นสีส้มในตัวใบงานได้เลย จะปริ้นเฉพาะใบงานแบบสะอาดๆ ไม่ติดหน้าจอแอป")

    # ทางเลือกฟรี: เอาพรอมต์ไปวาดเองในแอป Gemini (gemini.google.com วาดฟรีได้วันละ ~20 ภาพ)
    if st.session_state.shots_data:
        with st.expander("🎨 พรอมต์สำหรับไปวาดภาพเองฟรีที่ gemini.google.com (คลิกเปิด)"):
            st.markdown(
                "การวาดภาพผ่าน API ต้องเปิด billing แต่ที่ **gemini.google.com** วาดฟรีได้ "
                "ก๊อปพรอมต์ด้านล่างไปวางทีละช็อต (แนบรูปสินค้าไปด้วย) แล้วเซฟภาพมาแปะในใบงานได้เลย")
            for s in st.session_state.shots_data:
                st.markdown(f"**ช็อตที่ {s['no']}: {s.get('title','')}**")
                st.code(
                    "Simple clean storyboard illustration, flat pastel colors, "
                    "vertical 9:16 phone-video framing: "
                    + s.get("image_prompt", "")
                    + " The product must look like the attached product photo. "
                    "No text or words in the image.",
                    language=None)
