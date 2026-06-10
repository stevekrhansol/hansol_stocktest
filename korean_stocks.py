import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from openai import OpenAI

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="국내 주식 대시보드",
    page_icon="📈",
    layout="wide",
)

# ── 종목 목록 ────────────────────────────────────────────────
STOCKS = {
    "삼성전자":       "005930.KS",
    "SK하이닉스":     "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "현대차":         "005380.KS",
    "삼성바이오로직스": "207940.KS",
    "셀트리온":       "068270.KS",
    "NAVER":          "035420.KS",
    "카카오":         "035720.KS",
    "POSCO홀딩스":    "005490.KS",
    "KB금융":         "105560.KS",
}

PERIOD_MAP = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년":   "1y",
    "2년":   "2y",
}

# ── 헤더 ─────────────────────────────────────────────────────
st.title("📈 국내 주식 대시보드")
st.markdown("KOSPI / KOSDAQ 주요 10개 종목 실시간 현황")
st.divider()

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    selected_period_label = st.selectbox("조회 기간", list(PERIOD_MAP.keys()), index=2)
    period = PERIOD_MAP[selected_period_label]

    selected_stocks = st.multiselect(
        "종목 선택 (차트)",
        list(STOCKS.keys()),
        default=["삼성전자", "SK하이닉스", "NAVER"],
    )
    st.caption("종목 요약 카드는 전체 10개를 표시합니다.")

    st.divider()
    st.header("🤖 AI 챗봇 설정")
    api_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="GPT-4o-mini 사용을 위해 OpenAI API Key를 입력하세요.",
    )

# ── 데이터 수집 ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_summary(tickers: dict) -> pd.DataFrame:
    rows = []
    for name, ticker in tickers.items():
        try:
            info = yf.Ticker(ticker).fast_info
            rows.append({
                "종목명":      name,
                "티커":        ticker,
                "현재가":      info.last_price,
                "전일종가":    info.previous_close,
                "52주 최고":   info.year_high,
                "52주 최저":   info.year_low,
                "시가총액(조)": round(info.market_cap / 1e12, 2) if info.market_cap else None,
            })
        except Exception:
            rows.append({"종목명": name, "티커": ticker})
    df = pd.DataFrame(rows)
    df["등락(%)"] = ((df["현재가"] - df["전일종가"]) / df["전일종가"] * 100).round(2)
    return df


@st.cache_data(ttl=300)
def fetch_history(tickers: dict, period: str) -> dict:
    result = {}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if not df.empty:
                result[name] = df
        except Exception:
            pass
    return result


with st.spinner("데이터 불러오는 중..."):
    summary_df = fetch_summary(STOCKS)
    selected_tickers = {k: STOCKS[k] for k in selected_stocks}
    history_data = fetch_history(selected_tickers, period)

# ── 요약 카드 (10개 종목) ────────────────────────────────────
st.subheader("📋 종목 요약")
cols = st.columns(5)
for idx, row in summary_df.iterrows():
    col = cols[idx % 5]
    with col:
        change = row.get("등락(%)", 0) or 0
        color = "🔴" if change < 0 else ("🔵" if change == 0 else "🟢")
        price = f"{int(row['현재가']):,}" if pd.notna(row.get("현재가")) else "N/A"
        st.metric(
            label=f"{color} {row['종목명']}",
            value=f"{price} 원",
            delta=f"{change:+.2f}%",
        )

st.divider()

# ── 등락률 막대 차트 ─────────────────────────────────────────
st.subheader("📊 전일 대비 등락률")
bar_df = summary_df.dropna(subset=["등락(%)"]).sort_values("등락(%)")
fig_bar = px.bar(
    bar_df,
    x="등락(%)",
    y="종목명",
    orientation="h",
    color="등락(%)",
    color_continuous_scale=["#e74c3c", "#95a5a6", "#2ecc71"],
    color_continuous_midpoint=0,
    text="등락(%)",
)
fig_bar.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
fig_bar.update_layout(height=400, coloraxis_showscale=False, yaxis_title="", xaxis_title="등락률 (%)")
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── 주가 추이 라인 차트 ──────────────────────────────────────
st.subheader(f"📉 주가 추이 ({selected_period_label})")

if history_data:
    fig_line = go.Figure()
    for name, df in history_data.items():
        close = df["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        normalized = close / close.iloc[0] * 100
        fig_line.add_trace(go.Scatter(
            x=normalized.index,
            y=normalized.values,
            mode="lines",
            name=name,
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}<extra>" + name + "</extra>",
        ))
    fig_line.update_layout(
        height=450,
        yaxis_title="정규화 지수 (시작일=100)",
        xaxis_title="날짜",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.warning("선택한 종목의 히스토리 데이터를 불러올 수 없습니다.")

st.divider()

# ── 캔들스틱 차트 ────────────────────────────────────────────
st.subheader("🕯️ 캔들스틱 차트")
candle_stock = st.selectbox("종목 선택", list(selected_tickers.keys()) if selected_tickers else list(STOCKS.keys()))

candle_data = history_data.get(candle_stock)
if candle_data is not None and not candle_data.empty:
    def _squeeze(col):
        s = candle_data[col]
        return s.squeeze() if hasattr(s, "squeeze") else s

    fig_candle = go.Figure(data=[go.Candlestick(
        x=candle_data.index,
        open=_squeeze("Open"),
        high=_squeeze("High"),
        low=_squeeze("Low"),
        close=_squeeze("Close"),
        increasing_line_color="#e74c3c",
        decreasing_line_color="#2196F3",
    )])
    fig_candle.update_layout(
        height=500,
        xaxis_rangeslider_visible=True,
        xaxis_title="날짜",
        yaxis_title="주가 (원)",
    )
    st.plotly_chart(fig_candle, use_container_width=True)
else:
    st.info("캔들스틱을 표시하려면 사이드바에서 해당 종목을 선택하세요.")

st.divider()

# ── 시가총액 비교 ────────────────────────────────────────────
st.subheader("💰 시가총액 비교 (조 원)")
mcap_df = summary_df.dropna(subset=["시가총액(조)"]).sort_values("시가총액(조)", ascending=False)
fig_mcap = px.bar(
    mcap_df,
    x="종목명",
    y="시가총액(조)",
    color="시가총액(조)",
    color_continuous_scale="Blues",
    text="시가총액(조)",
)
fig_mcap.update_traces(texttemplate="%{text:.1f}조", textposition="outside")
fig_mcap.update_layout(height=400, coloraxis_showscale=False, xaxis_title="", yaxis_title="시가총액 (조 원)")
st.plotly_chart(fig_mcap, use_container_width=True)

st.divider()

# ── 원본 데이터 테이블 ────────────────────────────────────────
with st.expander("📄 원본 데이터 보기"):
    display_df = summary_df[["종목명", "티커", "현재가", "전일종가", "등락(%)", "52주 최고", "52주 최저", "시가총액(조)"]].copy()
    display_df["현재가"] = display_df["현재가"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "N/A")
    display_df["전일종가"] = display_df["전일종가"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "N/A")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.caption(f"데이터 출처: Yahoo Finance  |  마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.divider()

# ── AI 챗봇 ──────────────────────────────────────────────────
st.subheader("🤖 AI 주식 분석 챗봇")
st.markdown("수집된 주식 데이터를 바탕으로 GPT-4o-mini가 질문에 답변합니다.")

def build_system_prompt(df: pd.DataFrame) -> str:
    lines = ["당신은 한국 주식 전문 AI 애널리스트입니다. 아래는 현재 수집된 국내 주식 10개의 실시간 데이터입니다.\n"]
    for _, row in df.iterrows():
        price  = f"{int(row['현재가']):,}원" if pd.notna(row.get("현재가")) else "N/A"
        prev   = f"{int(row['전일종가']):,}원" if pd.notna(row.get("전일종가")) else "N/A"
        change = f"{row['등락(%)']:+.2f}%" if pd.notna(row.get("등락(%)")) else "N/A"
        hi52   = f"{int(row['52주 최고']):,}원" if pd.notna(row.get("52주 최고")) else "N/A"
        lo52   = f"{int(row['52주 최저']):,}원" if pd.notna(row.get("52주 최저")) else "N/A"
        mcap   = f"{row['시가총액(조)']}조 원" if pd.notna(row.get("시가총액(조)")) else "N/A"
        lines.append(
            f"- {row['종목명']} ({row['티커']}): 현재가 {price}, 전일종가 {prev}, "
            f"등락 {change}, 52주 최고 {hi52}, 52주 최저 {lo52}, 시가총액 {mcap}"
        )
    lines.append(
        "\n위 데이터를 기반으로 사용자 질문에 친절하고 전문적으로 한국어로 답변하세요. "
        "투자 권유는 하지 말고, 데이터 분석과 정보 제공에 집중하세요."
    )
    return "\n".join(lines)


# 세션 상태 초기화
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# 대화 기록 출력
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 입력창
user_input = st.chat_input("주식에 대해 궁금한 점을 질문하세요. 예) 삼성전자 현재 상태는?")

if user_input:
    if not api_key_input:
        st.warning("사이드바에서 OpenAI API Key를 입력해주세요.")
    else:
        # 사용자 메시지 추가
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # GPT 응답
        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                try:
                    client = OpenAI(api_key=api_key_input)
                    system_prompt = build_system_prompt(summary_df)

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            *st.session_state.chat_messages,
                        ],
                        temperature=0.7,
                        max_tokens=1000,
                    )
                    answer = response.choices[0].message.content
                    st.markdown(answer)
                    st.session_state.chat_messages.append({"role": "assistant", "content": answer})

                except Exception as e:
                    err = str(e)
                    if "auth" in err.lower() or "api_key" in err.lower() or "401" in err:
                        st.error("API Key가 올바르지 않습니다. 사이드바에서 다시 확인해주세요.")
                    else:
                        st.error(f"오류가 발생했습니다: {err}")

# 대화 초기화 버튼
if st.session_state.chat_messages:
    if st.button("대화 초기화"):
        st.session_state.chat_messages = []
        st.rerun()
