import streamlit as st
import base64
import re
import html as html_lib
import json
import time
import io
from pathlib import Path

import fitz  # PyMuPDF
from mistralai.client import Mistral

# ──────────────────────────────────────────────────────────────────────────────
# Config file — saves API key + theme locally
# ──────────────────────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "ocr_config.json"

def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_config(data: dict) -> None:
    try:
        existing = load_config()
        existing.update(data)
        CONFIG_FILE.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Arabic PDF OCR — Mistral OCR",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# Session State
# ──────────────────────────────────────────────────────────────────────────────
cfg = load_config()
if "saved_key" not in st.session_state:
    st.session_state.saved_key = cfg.get("api_key", "")
if "result_pages" not in st.session_state:
    st.session_state.result_pages = []
if "result_all_pages" not in st.session_state:
    st.session_state.result_all_pages = []
if "result_pdf_bytes" not in st.session_state:
    st.session_state.result_pdf_bytes = b""
if "result_filename" not in st.session_state:
    st.session_state.result_filename = ""
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = cfg.get("dark_mode", False)
if "show_all" not in st.session_state:
    st.session_state.show_all = False

SEPARATOR = "\n\n" + "─" * 40 + "\n\n"

# ──────────────────────────────────────────────────────────────────────────────
# Theme CSS
# ──────────────────────────────────────────────────────────────────────────────
dark = st.session_state.dark_mode

if dark:
    BG = "#0F0D1A"
    CARD_BG = "#1A1726"
    CARD_BORDER = "#2D2640"
    TEXT = "#E8E4F0"
    TEXT_SUB = "#A09BB0"
    INPUT_BG = "#1A1726"
    INPUT_BORDER = "#2D2640"
    INPUT_FOCUS = "#8B5CF6"
    ARABIC_BG = "linear-gradient(160deg,#1A1726,#150F25)"
    ARABIC_BORDER = "#3D2E6B"
    ARABIC_TEXT = "#E8E4F0"
    INFO_BG = "#1A1726"
    INFO_BORDER = "#7C3AED"
    INFO_TEXT = "#C4B5FD"
    UPLOADER_BG = "#1A1726"
    UPLOADER_BORDER = "#3D2E6B"
    UPLOADER_HOVER = "#2D2640"
    STAT_BG = "#1A1726"
    PROGRESS_BG = "linear-gradient(135deg,#1A1726,#150F25)"
    PROGRESS_BORDER = "#3D2E6B"
else:
    BG = "#F7F5FF"
    CARD_BG = "#fff"
    CARD_BORDER = "#E5E7EB"
    TEXT = "#111827"
    TEXT_SUB = "#6B7280"
    INPUT_BG = "#F9FAFB"
    INPUT_BORDER = "#E5E7EB"
    INPUT_FOCUS = "#8B5CF6"
    ARABIC_BG = "linear-gradient(160deg,#FDFCFF,#F5F0FF)"
    ARABIC_BORDER = "#C4B5FD"
    ARABIC_TEXT = "#111827"
    INFO_BG = "#F5F3FF"
    INFO_BORDER = "#8B5CF6"
    INFO_TEXT = "#4C1D95"
    UPLOADER_BG = "#F5F3FF"
    UPLOADER_BORDER = "#C4B5FD"
    UPLOADER_HOVER = "#EDE9FE"
    STAT_BG = "#fff"
    PROGRESS_BG = "linear-gradient(135deg,#FDFCFF,#F5F0FF)"
    PROGRESS_BORDER = "#C4B5FD"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Amiri:wght@400;700&display=swap');
#MainMenu, footer, header {{ visibility: hidden; }}
.stApp {{ background:{BG}; font-family:'Inter',sans-serif; color:{TEXT}; }}

.hero {{ background:linear-gradient(135deg,#4C1D95 0%,#7C3AED 55%,#9333EA 100%); border-radius:14px; padding:2.6rem 1.5rem 2.2rem; margin-bottom:1.8rem; text-align:center; box-shadow:0 8px 32px rgba(124,58,237,.22); position:relative; overflow:hidden; }}
.hero::before {{ content:""; position:absolute; inset:0; background:url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.04'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"); }}
.hero-badge {{ display:inline-flex; align-items:center; gap:6px; background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.3); color:rgba(255,255,255,.95); padding:.3rem 1rem; border-radius:20px; font-size:.78rem; font-weight:500; margin-bottom:1rem; }}
.hero h1 {{ color:#fff; font-size:2.1rem; font-weight:700; margin:0 0 .4rem; position:relative; }}
.hero p  {{ color:rgba(255,255,255,.82); font-size:.95rem; margin:0; position:relative; }}

.card {{ background:{CARD_BG}; border:1px solid {CARD_BORDER}; border-radius:14px; padding:1.3rem 1.4rem; margin-bottom:1.1rem; box-shadow:0 2px 8px rgba(0,0,0,.07); }}
.section-label {{ font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.09em; color:#7C3AED; margin-bottom:.7rem; display:flex; align-items:center; gap:5px; }}
.info-box {{ background:{INFO_BG}; border-left:3px solid {INFO_BORDER}; border-radius:8px; padding:.7rem 1rem; font-size:.84rem; color:{INFO_TEXT}; margin-top:.55rem; }}
.info-box a {{ color:#7C3AED; }}
.step {{ display:flex; align-items:flex-start; gap:10px; margin-bottom:.7rem; }}
.step-num {{ background:#7C3AED; color:#fff; min-width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.7rem; font-weight:700; flex-shrink:0; margin-top:1px; }}
.step-text {{ font-size:.84rem; color:{TEXT_SUB}; line-height:1.55; }}

.stat-box {{ background:{STAT_BG}; border:1px solid {CARD_BORDER}; border-radius:10px; padding:.9rem .7rem; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,.07); }}
.stat-value {{ font-size:1.6rem; font-weight:700; color:#7C3AED; }}
.stat-label {{ font-size:.74rem; color:{TEXT_SUB}; margin-top:2px; }}

.progress-panel {{ background:{PROGRESS_BG}; border:1.5px solid {PROGRESS_BORDER}; border-radius:14px; padding:1.3rem 1.5rem; margin:1rem 0; }}
.progress-row {{ display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:.6rem; }}
.progress-item {{ text-align:center; }}
.progress-big {{ font-size:1.5rem; font-weight:700; color:#7C3AED; line-height:1; }}
.progress-tiny {{ font-size:.72rem; color:{TEXT_SUB}; margin-top:2px; }}
.status-msg {{ font-size:.9rem; color:{TEXT_SUB}; }}

.arabic-output {{ background:{ARABIC_BG}; border:2px solid {ARABIC_BORDER}; border-radius:14px; padding:1.8rem 2rem; font-family:'Amiri','Noto Naskh Arabic','Traditional Arabic','Arial',serif; font-size:1.22rem; line-height:2.3; color:{ARABIC_TEXT}; direction:rtl; text-align:right; white-space:pre-wrap; word-break:break-word; min-height:80px; box-shadow:inset 0 2px 10px rgba(124,58,237,.06); }}
.result-header {{ background:linear-gradient(135deg,#059669,#10B981); border-radius:10px; padding:.85rem 1.3rem; color:#fff; font-weight:600; font-size:.95rem; margin-bottom:.9rem; box-shadow:0 4px 14px rgba(5,150,105,.22); }}

.download-row {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:1rem; }}

.page-sep {{ border:none; border-top:2px dashed {ARABIC_BORDER}; margin:1rem 0; }}

div[data-testid="stTextInput"] input, div[data-testid="stTextInput"] input[type="password"] {{ border-radius:10px !important; border:1.5px solid {INPUT_BORDER} !important; padding:.65rem 1rem !important; font-size:.9rem !important; background:{INPUT_BG} !important; color:{TEXT} !important; }}
div[data-testid="stTextInput"] input:focus {{ border-color:{INPUT_FOCUS} !important; box-shadow:0 0 0 3px rgba(139,92,246,.15) !important; }}
div[data-testid="stFileUploader"] section {{ border:2px dashed {UPLOADER_BORDER} !important; border-radius:12px !important; background:{UPLOADER_BG} !important; }}
div[data-testid="stFileUploader"] section:hover {{ border-color:#7C3AED !important; background:{UPLOADER_HOVER} !important; }}
div[data-testid="stButton"] button {{ background:linear-gradient(135deg,#5B21B6,#8B5CF6) !important; color:#fff !important; border:none !important; border-radius:10px !important; padding:.75rem 2rem !important; font-weight:600 !important; font-size:1rem !important; box-shadow:0 4px 16px rgba(124,58,237,.32) !important; min-height:48px !important; }}
div[data-testid="stButton"] button:hover {{ transform:translateY(-1px) !important; box-shadow:0 6px 22px rgba(124,58,237,.42) !important; }}
div[data-testid="stDownloadButton"] button {{ background:linear-gradient(135deg,#059669,#10B981) !important; color:#fff !important; border:none !important; border-radius:10px !important; padding:.6rem 1.2rem !important; font-weight:600 !important; font-size:.88rem !important; box-shadow:0 4px 14px rgba(5,150,105,.28) !important; min-height:44px !important; }}
div[data-testid="stDownloadButton"] button:hover {{ transform:translateY(-1px) !important; }}
div[data-testid="stProgressBar"] > div > div {{ background:linear-gradient(90deg,#5B21B6,#8B5CF6) !important; border-radius:10px !important; }}
hr {{ border:none; border-top:1px solid {CARD_BORDER}; margin:1.3rem 0; }}

@media (max-width: 768px) {{
    .hero {{ padding:1.8rem 1rem 1.6rem; }} .hero h1 {{ font-size:1.5rem; }} .hero p {{ font-size:.88rem; }}
    .hero-badge {{ font-size:.72rem; padding:.25rem .75rem; }} .arabic-output {{ font-size:1.1rem; padding:1.2rem 1.1rem; line-height:2.1; }}
    .stat-value {{ font-size:1.3rem; }} .progress-big {{ font-size:1.2rem; }}
    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {{ font-size:.9rem !important; padding:.65rem 1rem !important; }}
    .card {{ padding:1rem 1.1rem; }}
}}
@media (max-width: 480px) {{ .hero h1 {{ font-size:1.3rem; }} .arabic-output {{ font-size:1rem; padding:1rem .9rem; }} }}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def get_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = len(doc)
    doc.close()
    return count


def _is_arabic_char(c: str) -> bool:
    cp = ord(c)
    return (0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or
            0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF)


def _scrub_exotic_chars(text: str) -> str:
    out = []
    for c in text:
        cp = ord(c)
        if 0x0400 <= cp <= 0x052F: continue
        if 0x3000 <= cp <= 0x9FFF: continue
        if 0xAC00 <= cp <= 0xD7FF: continue
        if 0xF900 <= cp <= 0xFAFF: continue
        if 0x20000 <= cp <= 0x2FA1F: continue
        if 0xFF01 <= cp <= 0xFF60: continue
        out.append(c)
    return ''.join(out)


def filter_arabic_content(text: str) -> str:
    text = _scrub_exotic_chars(text)
    lines = text.split('\n')
    kept: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            kept.append(line); continue
        if any(_is_arabic_char(c) for c in s):
            kept.append(line); continue
        if all(c.isdigit() or c in ' /-:.,()،؟!٪%٠١٢٣٤٥٦٧٨٩#*—─|' for c in s):
            kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", '\n'.join(kept)).strip()


def clean_markdown_artifacts(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[tbl-.*?\]\(.*?\)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def run_mistral_ocr(pdf_bytes: bytes, api_key: str) -> list[str]:
    client = Mistral(api_key=api_key)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{pdf_b64}",
        },
        include_image_base64=False,
    )
    pages_text: list[str] = []
    for page in ocr_response.pages:
        raw_md = page.markdown or ""
        cleaned = clean_markdown_artifacts(raw_md)
        filtered = filter_arabic_content(cleaned)
        pages_text.append(filtered)
    return pages_text


def _find_arabic_font() -> Path | None:
    candidates = [
        Path(r"C:\Windows\Fonts\tahoma.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
    ]
    for fp in candidates:
        if fp.exists():
            return fp
    return None


def generate_searchable_pdf(original_bytes: bytes, all_pages_text: list[str]) -> bytes:
    """Overlay invisible OCR text on each page of the original PDF.

    Uses PDF render_mode=3 (invisible text) which is the standard
    mechanism for searchable/OCR PDFs — the text is selectable and
    copyable but not visually rendered.
    """
    doc = fitz.open(stream=original_bytes, filetype="pdf")

    font_path = _find_arabic_font()
    if font_path is None:
        return original_bytes

    for i in range(len(doc)):
        if i >= len(all_pages_text):
            break
        text = all_pages_text[i].strip()
        if not text:
            continue

        page = doc[i]
        margin = 30
        rect = fitz.Rect(
            margin, margin,
            page.rect.width - margin,
            page.rect.height - margin,
        )

        try:
            page.insert_textbox(
                rect,
                text,
                fontfile=str(font_path),
                fontsize=10,
                render_mode=3,
                overlay=True,
            )
        except Exception:
            pass

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def classify_error(exc: Exception) -> str:
    msg = str(exc)
    if "401" in msg or "Unauthorized" in msg or "invalid" in msg.lower():
        return "**مفتاح API غير صحيح أو منتهي.**  تحقق منه على [console.mistral.ai](https://console.mistral.ai)."
    if "429" in msg or "rate limit" in msg.lower():
        return "**تم تجاوز الحد المسموح به.**  انتظر دقيقة ثم حاول مجدداً."
    if "quota" in msg.lower() or "insufficient" in msg.lower() or "payment" in msg.lower():
        return "**رصيد الحساب نفد.**  يرجى إعادة الشحن على [console.mistral.ai](https://console.mistral.ai)."
    if "413" in msg or "too large" in msg.lower():
        return "**الملف كبير جداً.**  جرّب ملف أصغر أو قسّمه لأجزاء."
    return f"**خطأ من API.**  \n`{msg[:300]}`"


def fmt_time(seconds: float) -> str:
    m, s = int(seconds // 60), int(seconds % 60)
    return f"{m:02d}:{s:02d}"


# ──────────────────────────────────────────────────────────────────────────────
# Hero + Theme Toggle
# ──────────────────────────────────────────────────────────────────────────────
theme_col1, theme_col2 = st.columns([6, 1])
with theme_col2:
    theme_label = "☀️ نهاري" if st.session_state.dark_mode else "🌙 ليلي"
    if st.button(theme_label, key="theme_toggle", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        save_config({"dark_mode": st.session_state.dark_mode})
        st.rerun()

st.markdown("""
<div class="hero">
    <div class="hero-badge">⚡ Mistral OCR · طلب واحد للملف كاملاً · دقة عالية</div>
    <h1>📜 مستخرج النصوص العربية من PDF</h1>
    <p>ارفع ملف PDF — يُعالج الملف كاملاً في طلب واحد بتقنية Mistral OCR</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Layout
# ──────────────────────────────────────────────────────────────────────────────
col_main, col_guide = st.columns([3, 1], gap="large")

with col_guide:
    st.markdown(f"""
<div class="card">
    <div class="section-label">📋 كيفية الاستخدام</div>
    <div class="step"><div class="step-num">1</div><div class="step-text">الصق <strong>مفتاح Mistral AI</strong> — يُحفظ تلقائياً.</div></div>
    <div class="step"><div class="step-num">2</div><div class="step-text">ارفع ملف <strong>PDF</strong> العربي.</div></div>
    <div class="step"><div class="step-num">3</div><div class="step-text">اضغط <strong>ابدأ الاستخراج</strong> وانتظر.</div></div>
    <div class="step"><div class="step-num">4</div><div class="step-text">حمّل النتيجة بصيغة <strong>TXT أو MD أو PDF</strong>.</div></div>
</div>
<div class="card">
    <div class="section-label">⚡ المميزات</div>
    <p style="font-size:.82rem;color:{TEXT_SUB};line-height:1.9;margin:0;">
        • يُرسل الملف كاملاً في <strong>طلب واحد</strong>.<br>
        • نموذج OCR متخصص بدقة عالية.<br>
        • يحافظ على بنية المستند.<br>
        • تحميل بـ 3 صيغ: TXT, MD, PDF.<br>
        • ثيم ليلي / نهاري.<br>
        • مفتاح من <a href="https://console.mistral.ai" target="_blank" style="color:#7C3AED;">console.mistral.ai</a>
    </p>
</div>
""", unsafe_allow_html=True)

with col_main:
    # ── API Key ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">🔑 مفتاح Mistral AI API</div>', unsafe_allow_html=True)
    api_key_input = st.text_input(
        label="api_key", type="password",
        placeholder="الصق مفتاحك هنا…",
        value=st.session_state.saved_key,
        help="يُحفظ تلقائياً.", label_visibility="collapsed",
    )
    if api_key_input and api_key_input != st.session_state.saved_key:
        save_config({"api_key": api_key_input})
        st.session_state.saved_key = api_key_input

    if api_key_input:
        masked = api_key_input[:5] + "●" * 8 + api_key_input[-4:] if len(api_key_input) > 9 else "●" * len(api_key_input)
        tag = " · <strong>محفوظ ✅</strong>" if CONFIG_FILE.exists() else ""
        st.markdown(f'<div class="info-box">🔑 المفتاح: <code>{masked}</code>{tag}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box">🔒 المفتاح يُحفظ محلياً فقط.</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── File Upload ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">📁 رفع ملف PDF</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("اسحب الملف هنا أو اضغط للاختيار", type=["pdf"], help="يدعم ملفات كبيرة متعددة الصفحات")

    if uploaded_file is not None:
        fsize_kb = len(uploaded_file.getvalue()) / 1024
        st.markdown(f'<div class="info-box">📄 <strong>{uploaded_file.name}</strong> · {fsize_kb:.1f} KB — جاهز ✅</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Start Button ───────────────────────────────────────────────────────────
    start = st.button("🚀  ابدأ الاستخراج", use_container_width=True)

    if start:
        if not api_key_input:
            st.error("❌ **مفتاح API مفقود.**"); st.stop()
        if uploaded_file is None:
            st.error("❌ **لم يتم رفع ملف.**"); st.stop()

        pdf_bytes = uploaded_file.getvalue()
        fsize_mb  = len(pdf_bytes) / 1024 / 1024
        base_name = uploaded_file.name.rsplit(".", 1)[0]

        try:
            total_pages = get_page_count(pdf_bytes)
        except Exception:
            total_pages = "?"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-value">{total_pages}</div><div class="stat-label">عدد الصفحات</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-value">{fsize_mb:.1f} MB</div><div class="stat-label">حجم الملف</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="stat-box"><div class="stat-value">1</div><div class="stat-label">طلب API واحد</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        live_panel = st.empty()
        start_t = time.time()

        live_panel.markdown(f"""
<div class="progress-panel">
    <div class="progress-row">
        <div class="progress-item"><div class="progress-big">{total_pages}</div><div class="progress-tiny">صفحة</div></div>
        <div class="progress-item"><div class="progress-big">⏱ 00:00</div><div class="progress-tiny">الوقت المنقضي</div></div>
    </div>
    <div class="status-msg">⚙️ جار إرسال الملف كاملاً إلى Mistral OCR — يرجى الانتظار…</div>
</div>
""", unsafe_allow_html=True)

        try:
            pages_text = run_mistral_ocr(pdf_bytes, api_key_input)
        except Exception as exc:
            live_panel.empty()
            st.error(f"❌ {classify_error(exc)}")
            st.stop()

        total_elapsed = time.time() - start_t
        non_empty = [t for t in pages_text if t.strip()]

        live_panel.markdown(f"""
<div class="progress-panel">
    <div class="progress-row">
        <div class="progress-item"><div class="progress-big" style="color:#059669;">{len(non_empty)} / {len(pages_text)}</div><div class="progress-tiny">صفحات بنص</div></div>
        <div class="progress-item"><div class="progress-big" style="color:#059669;">⏱ {fmt_time(total_elapsed)}</div><div class="progress-tiny">إجمالي الوقت</div></div>
    </div>
    <div class="status-msg" style="color:#059669;font-weight:600;">✅ اكتمل الاستخراج!</div>
</div>
""", unsafe_allow_html=True)

        if non_empty:
            st.session_state.result_pages = non_empty
            st.session_state.result_all_pages = pages_text
            st.session_state.result_pdf_bytes = pdf_bytes
            st.session_state.result_filename = base_name
            st.session_state.show_all = False
        else:
            st.warning("⚠️ لم يُستخرج أي نص عربي من الملف.")

    # ── Show results ──────────────────────────────────────────────────────────
    if st.session_state.result_pages:
        pages = st.session_state.result_pages
        fname = st.session_state.result_filename
        full_text = SEPARATOR.join(pages)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Download buttons (above text) ─────────────────────────────────────
        st.markdown('<div class="result-header">📥 تحميل النتيجة</div>', unsafe_allow_html=True)

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                label="⬇️ TXT نص عادي",
                data=full_text.encode("utf-8"),
                file_name=f"{fname}.txt",
                mime="text/plain; charset=utf-8",
                use_container_width=True,
            )
        with dl2:
            md_content = ""
            for i, pg in enumerate(pages):
                md_content += f"{pg}\n\n---\n\n"
            st.download_button(
                label="⬇️ MD ماركداون",
                data=md_content.encode("utf-8"),
                file_name=f"{fname}.md",
                mime="text/markdown; charset=utf-8",
                use_container_width=True,
            )
        with dl3:
            try:
                pdf_data = generate_searchable_pdf(
                    st.session_state.result_pdf_bytes,
                    st.session_state.result_all_pages,
                )
                st.download_button(
                    label="⬇️ PDF قابل للنسخ",
                    data=pdf_data,
                    file_name=f"{fname}_searchable.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception:
                st.download_button(
                    label="⬇️ PDF الأصلي",
                    data=st.session_state.result_pdf_bytes,
                    file_name=f"{fname}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_fallback",
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Text preview ──────────────────────────────────────────────────────
        st.markdown('<div class="result-header">✨ النص العربي المستخرج</div>', unsafe_allow_html=True)

        max_preview = min(10, len(pages))
        initial_visible = min(2, len(pages))
        show_all = st.session_state.show_all

        if show_all:
            display_pages = pages[:max_preview]
        else:
            display_pages = pages[:initial_visible]

        for i, pg in enumerate(display_pages):
            if pg.strip():
                page_label = f"— صفحة {i+1} —"
                st.markdown(
                    f'<div style="text-align:center;font-size:.75rem;color:{TEXT_SUB};margin:.5rem 0;">{page_label}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="arabic-output">{html_lib.escape(pg)}</div>',
                    unsafe_allow_html=True,
                )

        remaining = max_preview - initial_visible
        if not show_all and remaining > 0 and len(pages) > initial_visible:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"📄  عرض {remaining} صفحات إضافية (حتى {max_preview} صفحة)", use_container_width=True, key="show_more"):
                st.session_state.show_all = True
                st.rerun()

        if len(pages) > max_preview:
            st.markdown(
                f'<div class="info-box">📌 يُعرض أول {max_preview} صفحات فقط. لقراءة الكل، حمّل الملف بأي صيغة أعلاه.</div>',
                unsafe_allow_html=True,
            )
