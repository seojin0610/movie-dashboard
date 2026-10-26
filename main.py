import datetime
import urllib.parse
import urllib.request
import json
import pandas as pd
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제 일별 박스오피스 순위")

# 1. API 인증키 불러오기 (secrets.toml 또는 스트림릿 클라우드 Secrets 설정)
if "KOBIS_KEY" not in st.secrets:
    st.error("🔑 API 인증키(KOBIS_KEY)가 설정되지 않았습니다.")
    st.info("""
    **해결 방법:**
    1. 스트림릿 클라우드 관리 화면에서 **App settings > Secrets** 메뉴로 이동합니다.
    2. 아래와 같이 KOBIS_KEY를 설정해 주세요:
       ```toml
       KOBIS_KEY = "발급받은_KOBIS_인증키"
       ```
    3. 로컬 환경에서 실행하는 경우 프로젝트 폴더 내 `.streamlit/secrets.toml` 파일에 위 내용을 저장하세요.
    """)
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 2. 한국 시간(KST, UTC+9) 기준 어제 날짜 계산
# 서버 시계(UTC)와 상관없이 한국 표준시(UTC+9)를 기준으로 어제 날짜를 구합니다.
utc_now = datetime.datetime.now(datetime.timezone.utc)
kst_now = utc_now + datetime.timedelta(hours=9)
yesterday = kst_now - datetime.timedelta(days=1)
target_date = yesterday.strftime("%Y%m%d")
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.caption(f"📅 **조회 기준일:** {display_date} (한국 시간 기준 어제)")

# 3. KOBIS OpenAPI 호출 및 데이터 가져오기
base_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": api_key,
    "targetDt": target_date
}
url = f"{base_url}?{urllib.parse.urlencode(params)}"

@st.cache_data(ttl=3600)  # 1시간 동안 응답 결과 캐싱 (반복 요청 방지)
def fetch_box_office(api_url):
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data, None
            else:
                return None, f"서버 응답 오류 (상태 코드: {response.status})"
    except Exception as e:
        return None, f"네트워크 요청 실패: {str(e)}"

data, error_msg = fetch_box_office(url)

# 4. 에러 처리 및 예외 상황 안내
if error_msg:
    st.error(f"❌ 데이터를 가져오지 못했습니다: {error_msg}")
    st.info("💡 **확인해 보세요:** 인터넷 연결 상태나 KOBIS 서버 상태를 확인해 주세요.")
    st.stop()

# API 인증키 오류 발생 시 (상태코드 200이지만 faultInfo 전달)
if "faultInfo" in data:
    fault = data["faultInfo"]
    message = fault.get("message", "인증키 또는 요청에 문제가 있습니다.")
    st.error(f"⚠️ KOBIS API 오류 발생: {message}")
    st.info("""
    💡 **확인해 보세요:**
    - KOBIS_KEY에 입력한 인증키가 올바른지 확인해 주세요.
    - [KOBIS 영화관입장권통합전산망 OpenAPI](https://www.kobis.or.kr/kobisopenapi/)에서 키 발급 상태 및 일일 사용량을 확인하세요.
    """)
    st.stop()

# 응답 데이터 파싱
boxoffice_result = data.get("boxOfficeResult", {})
daily_list = boxoffice_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어있는 경우
if not daily_list:
    st.warning("⚠️ 해당 날짜의 박스오피스 데이터가 존재하지 않습니다.")
    st.info("""
    💡 **확인해 보세요:**
    - 아직 어제 날짜의 집계 작업이 완료되지 않았을 수 있습니다. 잠시 후 다시 시도해 주세요.
    - KOBIS 서버의 일시적인 집계 지연일 수 있습니다.
    """)
    st.stop()

# 5. 데이터프레임 변환 및 전처리 (문자열 -> 숫자 변환)
df = pd.DataFrame(daily_list)

df["rank"] = pd.to_numeric(df["rank"])
df["audiCnt"] = pd.to_numeric(df["audiCnt"])
df["audiAcc"] = pd.to_numeric(df["audiAcc"])
df["scrnCnt"] = pd.to_numeric(df["scrnCnt"])

# 6. 1위 영화 핵심 지표 카드 (Metrics)
top_movie = df.iloc[0]

st.subheader("🏆 1위 영화 요약")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="🎬 1위 영화명",
        value=top_movie["movieNm"],
        delta=f"개봉일: {top_movie['openDt']}"
    )

with col2:
    st.metric(
        label="👥 어제 관객수",
        value=f"{top_movie['audiCnt']:,} 명"
    )

with col3:
    st.metric(
        label="🍿 누적 관객수",
        value=f"{top_movie['audiAcc']:,} 명"
    )

st.markdown("---")

# 7. 관객수 상위 5편 막대그래프
st.subheader("📊 관객수 상위 5개 영화")
top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
top5_df.rename(columns={"movieNm": "영화명", "audiCnt": "어제 관객수"}, inplace=True)

# 시각화를 위해 영화명을 인덱스로 설정
chart_data = top5_df.set_index("영화명")
st.bar_chart(chart_data)

st.markdown("---")

# 8. 전체 순위 표 출력 (순위, 영화명, 개봉일, 관객수, 누적관객, 스크린수)
st.subheader("📋 박스오피스 전체 순위 (TOP 10)")

display_df = df[[
    "rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"
]].copy()

# 컬럼명 한글 변경
display_df.columns = ["순위", "영화명", "개봉일", "어제 관객수", "누적 관객수", "스크린수"]

# 숫자 포맷팅 (천 단위 쉼표 추가)
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn("순위", format="%d위"),
        "어제 관객수": st.column_config.NumberColumn("어제 관객수", format="%d명"),
        "누적 관객수": st.column_config.NumberColumn("누적 관객수", format="%d명"),
        "스크린수": st.column_config.NumberColumn("스크린수", format="%d개"),
    }
)
