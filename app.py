# -*- coding: utf-8 -*-
"""
서울 연평균기온 대시보드
- 연도별 평균기온 꺾은선 + 5년 이동평균 겹침 표시
- 사이드바 연도 범위 슬라이더
- 선택 구간 평균·최저·최고기온 표시
실행: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import urllib.error  # 원격 CSV 로드 실패(HTTP/네트워크) 처리용

# ───────────────────────── 1. 데이터 로드 ─────────────────────────
DATA_URL = (
    "https://drive.google.com/uc?export=download&id/"
    "1pPCb6GmFx_H5baemM3enjCCDUTp6irk6"
)
LOCAL_FILE = "seoul_temperature.csv"

REQUIRED_COLUMNS = ["날짜", "지점", "평균기온(℃)", "최저기온(℃)", "최고기온(℃)"]


@st.cache_data(show_spinner=False)
def load_data(url: str, local: str = LOCAL_FILE) -> pd.DataFrame:
    """Google Drive CSV 로드. 실패 시 로컬 파일 fallback."""
    encodings = ("utf-8-sig", "cp949", "euc-kr", "latin-1")

    # 원격 Drive 파일을 먼저 시도
    for enc in encodings:
        try:
            df = pd.read_csv(url, encoding=enc)
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                raise ValueError(f"필수 컬럼 누락: {missing}")
            if len(df) < 100:
                raise ValueError("데이터 행 수가 너무 적습니다.")
            st.success("원격 데이터를 불러왔습니다.")
            return df
        except (UnicodeDecodeError, ValueError, urllib.error.HTTPError, urllib.error.URLError):
            # Google Drive가 접근 제한(로그인 요구 등)이면 다음 인코딩 시도
            # → 마지막에 로컬 파일 폴백으로 전환
            continue

    # 원격 로드 실패 시 로컬 파일 사용
    try:
        df = pd.read_csv(local, encoding="utf-8-sig")
        st.info("원격 로드 실패 → 로컬 파일 'seoul_temperature.csv'를 사용합니다.")
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"필수 컬럼 누락: {missing}")
        return df
    except Exception as e:
        st.error(f"데이터 로드에 실패했습니다: {e}")
        st.info("Google Drive 링크를 확인하거나, CSV를 내려받아 같은 폴더에 저장하세요.")
        return pd.DataFrame()


df = load_data(DATA_URL)

if df.empty:
    st.stop()

# ───────────────────────── 2. 전처리 ──────────────────────────────
# 컬럼명의 공백/BOM 제거
df.columns = df.columns.str.strip()

# 날짜 값 앞의 탭 문자 제거 후 날짜 변환
df["날짜"] = df["날짜"].astype(str).str.replace("\t", "").str.strip()
df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
df = df.dropna(subset=["날짜"])

# 지점 선택 (여러 지점이 있을 경우)
if "지점" in df.columns:
    options = ["전체"] + list(df["지점"].unique())
    sel = st.sidebar.selectbox("관측 지점 선택", options)
    if sel != "전체":
        df = df[df["지점"] == sel]

# 연도 추출 및 연도별 집계
df["연도"] = df["날짜"].dt.year

yearly = (
    df.groupby("연도", as_index=False)
    .agg(
        평균기온=("평균기온(℃)", "mean"),
        최저기온=("최저기온(℃)", "mean"),
        최고기온=("최고기온(℃)", "mean"),
    )
)

# 5년 이동평균 (중앙 기준 → 양끝 2개 연도는 NaN)
yearly["5년이동평균"] = yearly["평균기온"].rolling(window=5, center=True).mean()

# ───────────────────────── 3. 화면 구성 ───────────────────────────
st.set_page_config(page_title="서울 연평균기온 대시보드", page_icon="🌡️", layout="wide")

st.title("서울 연평균기온 대시보드")
st.write(f"분석 기간: {yearly['연도'].min()}년 ~ {yearly['연도'].max()}년")

# ───────────────────────── 4. 그래프 ──────────────────────────────
st.subheader("연도별 평균기온 및 5년 이동평균")

fig = go.Figure()

# ① 연도별 평균기온 (전체 연도)
fig.add_trace(
    go.Scatter(
        x=yearly["연도"],
        y=yearly["평균기온"],
        mode="lines+markers",
        name="연도별 평균기온",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=5),
        hovertemplate="연도: %{x}년<br>평균기온: %{y:.2f} ℃<extra></extra>",
    )
)

# ② 5년 이동평균 (값이 있는 연도만)
ma_df = yearly.dropna(subset=["5년이동평균"])
fig.add_trace(
    go.Scatter(
        x=ma_df["연도"],
        y=ma_df["5년이동평균"],
        mode="lines",
        name="5년 이동평균",
        line=dict(color="#d62728", width=3, dash="dash"),
        hovertemplate="5년 이동평균: %{y:.2f} ℃<extra></extra>",
    )
)

fig.update_layout(
    title="연도별 평균기온 및 5년 이동평균",
    xaxis_title="연도",
    yaxis_title="평균기온 (℃)",
    hovermode="x unified",
    template="plotly_white",
    margin=dict(t=50, b=40),
)

st.plotly_chart(fig, use_container_width=True)
st.caption("※ 5년 이동평균은 5개 연도 중심 계산이라 양끝 2개 연도는 값이 비어 있습니다.")

# ───────────────────────── 5. 사이드바 슬라이더 + 통계 ────────────
st.sidebar.header("구간 설정")

min_year = int(yearly["연도"].min())
max_year = int(yearly["연도"].max())

year_range = st.sidebar.slider(
    "연도 범위 (선택 구간 통계)",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
    help="슬라이더로 선택한 구간의 평균·최저·최고기온이 아래에 표시됩니다.",
)

# 선택 구간 통계 (이동평균 유무와 무관하게 전체 연도 기준)
mask = (yearly["연도"] >= year_range[0]) & (yearly["연도"] <= year_range[1])
selected = yearly[mask]

if len(selected) == 0:
    st.warning("선택한 구간에 데이터가 없습니다.")
else:
    avg = selected["평균기온"].mean()
    mn = selected["최저기온"].mean()
    mx = selected["최고기온"].mean()

    st.subheader(f"선택 구간 통계 ({year_range[0]}년 ~ {year_range[1]}년, {len(selected)}개 연도)")
    st.metric("평균기온", f"{avg:.2f} ℃")
    st.metric("최저기온", f"{mn:.2f} ℃")
    st.metric("최고기온", f"{mx:.2f} ℃")

    st.dataframe(
        selected[["연도", "평균기온", "최저기온", "최고기온"]],
        use_container_width=True,
        hide_index=True,
    )
