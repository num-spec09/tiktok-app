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
    st.title("🔒 เข้าสู่ระบบ")
    st.caption("เครื่องมือภายในทีม กรุณาใส่รหัสผ่านที่ได้รับจากหัวหน้า")
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

st.title("🎬 เครื่องมือสร้างสคริปต์และสตอรี่บอร์ด TikTok")
st.caption("วิเคราะห์สินค้า → ใบงาน 2 หน้าดีไซน์พร้อมปริ้น + ภาพประกอบทุกช็อต")

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


def call_with_fallback(client, models, contents):
    last_error = None
    for name in models:
        try:
            return client.models.generate_content(model=name, contents=contents), name
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            # 404 = ไม่มีโมเดลนี้ / 429+limit 0 หรือ free_tier = บัญชีนี้ใช้โมเดลนี้ไม่ได้
            if ("404" in msg or "not_found" in msg or "not found" in msg
                    or ("429" in msg and ("limit: 0" in msg or "free_tier" in msg))):
                continue
            raise
    raise Exception(f"ลองทุกโมเดลแล้วไม่มีตัวไหนใช้ได้: {last_error}")


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
              <p><b>มุมกล้อง:</b> {s.get('camera','-')}</p>
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
              <p><b>มุมกล้อง:</b> {s.get('camera','-')}</p>
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
            # สตอรี่บอร์ดของสคริปต์นี้ (แสดงภาพเฉพาะสายแรกเพื่อประหยัดโควตา)
            shot_list = [x for x in s.get("shots", []) if isinstance(x, dict)]
            sb_html = render_shots(shot_list, shot_imgs, product_uri, show_images=(i == 0))
            blocks += f'''
            <div class="script-block">
              <div class="script-version">
                <div class="script-badge"><span class="letter">{letter}</span> สคริปต์ {letter}: {s.get("style","")}</div>
                {hook_html}
                {body}
              </div>
              <h3 class="sb-title">🎬 สตอรี่บอร์ดของสคริปต์ {letter} ({s.get("style","")})</h3>
              {sb_html}
            </div>'''
        script_html = blocks
    else:
        # เผื่อกรณี AI ตอบแบบเก่า
        script_html = "".join(f"<p>{p}</p>" for p in data.get("script", "").split("\n") if p.strip())
        shots_html = render_shots([x for x in data.get("shots", []) if isinstance(x, dict)],
                                   shot_imgs, product_uri, show_images=True)

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

<!-- ==================== สคริปต์ + สตอรี่บอร์ด ==================== -->
<h2 class="section">2. สคริปต์ + สตอรี่บอร์ด — เลือกสไตล์ A ถึง E (TikTok Safe Script)</h2>
<p class="note">*วิธีใช้: พนักงานเลือกสคริปต์ที่ชอบ (บอกหัวหน้าได้เลยว่าเอา A/B/C/D/E) แล้วถ่ายตามสตอรี่บอร์ดของสคริปต์นั้น ทุกสไตล์หลีกเลี่ยงคำต้องห้ามของ TikTok แล้ว*</p>
{script_html}

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
                main_prompt = """
                คุณคือผู้เชี่ยวชาญด้าน E-commerce และ TikTok
                วิเคราะห์ข้อมูลสินค้า+รูปภาพที่แนบมา แล้วตอบกลับเป็น JSON เท่านั้น ห้ามมีข้อความอื่น รูปแบบ:
                {
                  "product_name": "ชื่อสินค้า (ไทย + อังกฤษถ้ามี) พร้อมขนาด",
                  "features": ["จุดเด่นข้อ 1", "จุดเด่นข้อ 2", "... 4-5 ข้อ"],
                  "scripts": [
                    {"style": "สายฮา สนุกสนาน", "hook": "ประโยคเปิดสั้นๆ", "content": "สคริปต์ฉบับเต็ม แบ่งย่อหน้าด้วย \\n (Hook-เนื้อหา-CTA)"},
                    {"style": "สายให้ความรู้", "hook": "...", "content": "..."},
                    {"style": "สายรีวิวจริงใจ", "hook": "...", "content": "..."},
                    {"style": "สายเล่าปัญหา (Storytelling)", "hook": "...", "content": "..."},
                    {"style": "สายกระตุ้นให้รีบซื้อ (Urgency)", "hook": "...", "content": "..."}
                  ],
                  "shots": [
                    {"no": 1, "title": "ชื่อช็อต", "time": "0.00 - 0.05 วินาที",
                     "camera": "มุมกล้อง/ขนาดภาพ", "action": "ท่าทางพนักงานและสิ่งที่เกิดขึ้น",
                     "dialogue": "บทพูดช็อตนี้",
                     "image_prompt": "English prompt describing this exact shot for an illustration"}
                  ]
                }
                ให้มี scripts ทั้งหมด 5 เวอร์ชันตามสไตล์ที่ระบุ แต่ละเวอร์ชันเนื้อหาต่างกันจริงๆ
                และแต่ละเวอร์ชันมี shots (สตอรี่บอร์ด) 5 ช็อตของตัวเอง ที่สอดคล้องกับสคริปต์เวอร์ชันนั้น เวลารวมประมาณ 45 วินาที
                ทุกข้อความเป็นภาษาไทย (ยกเว้น image_prompt เป็นอังกฤษ)
                ห้ามใช้คำว่า ดีที่สุด, 100%, ขาวทันที, หายขาด ให้ใช้คำเลี่ยงที่ปลอดภัยตามกฎโฆษณา
                """
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
