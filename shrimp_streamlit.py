import os
import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc

# ─── 리소스 경로 설정 ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DB_PATH  = os.path.join(BASE_DIR, "shrimp.db")
FONT_PATH= os.path.join(BASE_DIR, "CJ_Light.ttf")
LOGO_PATH= os.path.join(BASE_DIR, "cj.jpg")

# ─── 한글 폰트 matplotlib 등록 ─────────────────────────────────────────────────
font_manager.fontManager.addfont(FONT_PATH)
rc('font', family=font_manager.FontProperties(fname=FONT_PATH).get_name())
plt.rcParams['axes.unicode_minus'] = False

# ─── 데이터 로드 캐시 ─────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM shrimp_data", conn)
    conn.close()
    return df

# 전체 데이터
df_all = load_data()
owners = df_all['farm_owner'].unique().tolist()

# 세션 초기화
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = ""

# ─── 로그인 화면 ─────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.title("🔒 로그인")
    user_input = st.text_input("아이디 (양식장 주 이름)")
    pwd_input  = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        if user_input in owners and pwd_input == "1234!":
            st.session_state.authenticated = True
            st.session_state.user = user_input
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    st.stop()

# ─── 로그아웃 기능 ────────────────────────────────────────────────────────────
def do_logout():
    st.session_state.authenticated = False
    st.session_state.user = ""

st.sidebar.button("로그아웃", on_click=do_logout)

# ─── 인증된 사용자 대시보드 ─────────────────────────────────────────────────
user = st.session_state.user

# ── 로고 및 환영 메시지 ────────────────────────────────────────────────────────
# 오른쪽 상단에 로고, 왼쪽에 환영 메시지 배치
col1, col2 = st.columns([9,1])
with col1:
    st.title(f"🦐 환영합니다, {user}님!")
with col2:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=80)
    else:
        st.error("로고 파일(cj.jpg)이 폴더에 없습니다.")

# 본인 양식장 데이터 필터링
df = df_all[df_all['farm_owner'] == user]

# 사이드바 필터: 지역, 호지
regions = ["전체"] + sorted(df['region'].unique())
region = st.sidebar.selectbox("지역 선택", regions)
if region != "전체":
    df = df[df['region'] == region]

ponds = ["전체"] + sorted(df['pond_number'].unique())
pond   = st.sidebar.selectbox("호지 번호", [str(p) for p in ponds])
if pond != "전체":
    df = df[df['pond_number'] == int(pond)]

# ─── 트렌드 그래프 ──────────────────────────────────────────────────────────
st.subheader("비브리오 변화 추이")
dates = sorted(df['sampling_date'].unique())
g_vals = [df[(df['sampling_date']==d)&(df['vibrio_type']=='Green')]['vibrio_count'].sum() for d in dates]
y_vals = [df[(df['sampling_date']==d)&(df['vibrio_type']=='Yellow')]['vibrio_count'].sum() for d in dates]
x = np.arange(len(dates))
fig, ax = plt.subplots(figsize=(8,4))
w = 0.35
ax.bar(x, g_vals, w, label='Green', color='green')
ax.bar(x, y_vals, w, bottom=g_vals, label='Yellow', color='yellow', alpha=0.7)
for vals, col, lbl in [(g_vals,'darkgreen','Green'), (y_vals,'orange','Yellow')]:
    if len(vals) >= 3:
        coef = np.polyfit(x, vals, 2)
        trend = np.polyval(coef, x)
        ss_res = np.sum((np.array(vals)-trend)**2)
        ss_tot = np.sum((np.array(vals)-np.mean(vals))**2)
        r2 = 1 - ss_res/ss_tot if ss_tot else 0
        ax.plot(x, trend, '--', color=col, label=f'{lbl} poly2 (R²={r2:.2f})')
ax.set_xticks(x)
ax.set_xticklabels(dates, rotation=45)
ax.set_ylabel("CFU/mL")
ax.legend(); ax.grid(True)
st.pyplot(fig)

# ─── 원시 데이터 테이블 ─────────────────────────────────────────────────────
st.subheader("원시 데이터")
mapping = {
    'region':'지역','farm_owner':'양식장 주','pond_type':'호지 종류',
    'pond_number':'호지 번호','sampling_date':'채수일',
    'vibrio_type':'비브리오 종류','vibrio_count':'비브리오 수치'
}
df_disp = df.rename(columns=mapping)
df_disp['채수일'] = pd.to_datetime(df_disp['채수일']).dt.date
df_disp['비브리오 수치'] = df_disp['비브리오 수치'].astype(int).map("{:,}".format)
styled = df_disp.style.set_properties(**{'text-align':'center'})
styled.set_table_styles([{'selector':'th','props':[('text-align','center')]}])
st.dataframe(styled, use_container_width=True)

# ─── 분석 요약 ───────────────────────────────────────────────────────────────
st.subheader("분석 요약")
def analyze(vals):
    if len(vals) < 2:
        return ""
    start, now = vals[0], vals[-1]
    pct = (now - start)/start*100 if start else 0
    lines = [f"- 시작→현재: {start:,} → {now:,} ({pct:+.1f}%)"]
    for i in range(1, len(vals)):
        if vals[i] < vals[i-1]:
            drop_pct = (vals[i-1] - vals[i])/vals[i-1]*100
            lines.append(f"- 첫 감소: {dates[i]} ({drop_pct:.1f}%↓)")
            break
    return "\n".join(lines)
st.markdown(f"**[Green]**\n{analyze(g_vals)}")
st.markdown(f"**[Yellow]**\n{analyze(y_vals)}")

# ─── 데이터 내보내기 ─────────────────────────────────────────────────────────
st.subheader("데이터 내보내기")
csv = df_disp.to_csv(index=False).encode('utf-8-sig')
st.download_button("CSV 다운로드", csv, "shrimp_data.csv", "text/csv")
