import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 색상의 간단한 디자인
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9F2;
    }
    h1, h2, h3 {
        color: #754C35;
    }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F0DCCB;
        padding: 16px;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏘️ 동네별 인구 피라미드")
st.caption(
    "전국 읍·면·동의 최신 인구 데이터를 바탕으로 "
    "남녀별·연령별 인구 분포를 살펴봅니다."
)


# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/easyyyy00/"
    "dash001/main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중입니다...")
def load_data():
    # ZIP 압축 파일 안에 CSV가 하나 들어 있다는 전제로 읽습니다.
    # URL 끝이 .zip이므로 pandas가 압축 형식을 자동으로 인식합니다.
    df = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름 앞뒤에 혹시 있을 수 있는 공백을 제거합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 지역을 선택할 때 사용할 필수 열을 확인합니다.
    required_columns = ["연도", "시도", "시군구", "동"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(
            f"필수 열을 찾을 수 없습니다: {', '.join(missing)}"
        )

    # 연도 열을 숫자로 변환합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 연령별 남녀 인구 열을 찾습니다.
    # 0~99세와 100세 이상을 모두 지원합니다.
    age_columns = []

    for col in df.columns:
        if re.fullmatch(r"[남여]_(?:[0-9]+세|100세 이상)", col):
            age_columns.append(col)

    if not age_columns:
        raise ValueError(
            "남_0세, 여_0세, 남_100세 이상 형식의 "
            "인구 열을 찾을 수 없습니다."
        )

    # 인구 열을 숫자로 변환합니다.
    for col in age_columns:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        ).fillna(0)

    # 데이터에 실제로 존재하는 가장 최신 연도만 남깁니다.
    latest_year = int(df["연도"].max())
    df = df.loc[df["연도"] == latest_year].copy()

    # 지역명 결측값으로 드롭다운에 빈 항목이 생기지 않도록 합니다.
    for col in required_columns[1:]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df, latest_year, age_columns


try:
    df, latest_year, age_columns = load_data()
except Exception as e:
    st.error("데이터를 불러오거나 처리하는 중 문제가 발생했습니다.")
    st.exception(e)
    st.stop()


# --------------------------------------------------
# 3. 나이 라벨을 0세부터 100세 이상까지 생성
# --------------------------------------------------
# 이 순서는 그래프의 세로축에 그대로 적용합니다.
age_labels = [f"{age}세" for age in range(100)] + ["100세 이상"]


def get_age_column(gender, age_label):
    """화면에 표시할 나이 라벨에 대응하는 실제 데이터 열을 반환합니다."""
    return f"{gender}_{age_label}"


# 실제 데이터에 존재하는 나이 열만 추려서 순서대로 정렬합니다.
male_columns = [
    get_age_column("남", age)
    for age in age_labels
    if get_age_column("남", age) in df.columns
]
female_columns = [
    get_age_column("여", age)
    for age in age_labels
    if get_age_column("여", age) in df.columns
]

if not male_columns or not female_columns:
    st.error("남성 또는 여성의 연령별 인구 열이 충분하지 않습니다.")
    st.stop()


# --------------------------------------------------
# 4. 시도 → 시군구 → 동 드롭다운
# --------------------------------------------------
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_options = sorted(df["시도"].unique().tolist())
    selected_sido = st.selectbox("① 시도", sido_options)

# 선택한 시도에 해당하는 시군구만 표시합니다.
sido_df = df.loc[df["시도"] == selected_sido]
sigungu_options = sorted(sido_df["시군구"].unique().tolist())

with col2:
    selected_sigungu = st.selectbox("② 시군구", sigungu_options)

# 선택한 시도와 시군구에 해당하는 동만 표시합니다.
sigungu_df = sido_df.loc[
    sido_df["시군구"] == selected_sigungu
]
dong_options = sorted(sigungu_df["동"].unique().tolist())

with col3:
    selected_dong = st.selectbox("③ 동", dong_options)


# --------------------------------------------------
# 5. 선택한 동네의 인구 계산
# --------------------------------------------------
selected_df = sigungu_df.loc[
    sigungu_df["동"] == selected_dong
]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

# 동일한 지역이 여러 행으로 기록되어 있어도 연령별로 합산합니다.
male_population = (
    selected_df[male_columns].sum(axis=0)
    if male_columns
    else pd.Series(dtype=float)
)
female_population = (
    selected_df[female_columns].sum(axis=0)
    if female_columns
    else pd.Series(dtype=float)
)

# 열 이름을 나이 라벨로 바꾸어 그래프에 사용할 표를 만듭니다.
male_by_age = {
    col.removeprefix("남_"): int(round(value))
    for col, value in male_population.items()
}
female_by_age = {
    col.removeprefix("여_"): int(round(value))
    for col, value in female_population.items()
}

# 데이터에 특정 나이 열이 없더라도 해당 나이를 0명으로 표시합니다.
male_values = [
    -male_by_age.get(age, 0)
    for age in age_labels
]
female_values = [
    female_by_age.get(age, 0)
    for age in age_labels
]

total_male = abs(sum(male_values))
total_female = sum(female_values)
total_population = total_male + total_female


# --------------------------------------------------
# 6. 주요 인구 지표 표시
# --------------------------------------------------
st.divider()

st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong} 인구 현황"
)

st.caption(f"기준 연도: {latest_year}년")

metric1, metric2, metric3 = st.columns(3)

metric1.metric("전체 인구", f"{total_population:,}명")
metric2.metric("남성 인구", f"{total_male:,}명")
metric3.metric("여성 인구", f"{total_female:,}명")


# --------------------------------------------------
# 7. 인구 피라미드 그리기
# --------------------------------------------------
fig = go.Figure()

# 남성은 음수로 변환했기 때문에 왼쪽에 표시됩니다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_values,
        name="남성",
        orientation="h",
        marker_color="#D98768",
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
        customdata=[abs(v) for v in male_values],
    )
)

# 여성은 양수이므로 오른쪽에 표시됩니다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_values,
        name="여성",
        orientation="h",
        marker_color="#E8B7A0",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,}명"
            "<extra></extra>"
        ),
    )
)

# 남녀 막대를 중앙의 0을 기준으로 좌우에 배치합니다.
# categoryarray를 0세 → 100세 이상 순서로 명시하여
# 0세가 아래쪽, 100세 이상이 위쪽에 오도록 고정합니다.
fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font={
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#5B4636",
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "center",
        "x": 0.5,
    },
    margin={"l": 90, "r": 35, "t": 100, "b": 70},
    hovermode="y unified",
)

# 핵심: 축을 뒤집거나 값 크기로 정렬하지 않습니다.
# 나이 라벨의 순서를 categoryarray에 직접 고정합니다.
fig.update_yaxes(
    title_text="나이",
    type="category",
    categoryorder="array",
    categoryarray=age_labels,
    tickmode="array",
    tickvals=age_labels,
    ticktext=age_labels,
    showgrid=False,
    automargin=True,
)

# 좌우 인구 막대의 크기를 비교하기 쉽게 좌우 범위를 대칭으로 설정합니다.
max_population = max(
    [abs(v) for v in male_values] + female_values + [1]
)
axis_limit = max_population * 1.1

fig.update_xaxes(
    title_text="인구수 (명)",
    range=[-axis_limit, axis_limit],
    zeroline=True,
    zerolinewidth=2,
    zerolinecolor="#A88B75",
    showgrid=True,
    gridcolor="#EEDFD2",
    tickformat=",",
    tickmode="array",
    tickvals=np.linspace(-axis_limit, axis_limit, 9),
    ticktext=[
        f"{abs(int(round(v))):,}" for v in
        np.linspace(-axis_limit, axis_limit, 9)
    ],
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "※ 남성은 왼쪽, 여성은 오른쪽에 표시됩니다. "
    "가로축의 남성 인구는 음수로 계산했지만, "
    "화면에는 인구수의 절댓값으로 표시합니다."
)

# 축 순서 확인용 안내: 그래프의 최하단은 0세,
# 최상단은 100세 이상이며, 정렬 옵션으로 순서를 변경하지 않습니다.
with st.expander("ℹ️ 그래프 읽는 방법"):
    st.markdown(
        """
        - **세로축:** 아래에서 위로 0세부터 100세 이상까지 증가합니다.
        - **왼쪽 막대:** 남성 인구입니다.
        - **오른쪽 막대:** 여성 인구입니다.
        - **가로축:** 인구수입니다. 중앙의 0을 기준으로 좌우를 비교합니다.
        - **막대에 마우스를 올리면:** 해당 나이의 인구수를 확인할 수 있습니다.
        """
