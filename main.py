import requests
import streamlit as st
from datetime import datetime, timedelta, timezone


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 일일 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 설정
# --------------------------------------------------

# Streamlit Cloud 서버가 한국 시간이 아닐 수 있기 때문에
# UTC+9를 직접 지정한다.
KST = timezone(timedelta(hours=9))

# 현재 한국 날짜
today_kst = datetime.now(KST).date()

# 오늘 영화 데이터는 아직 집계되지 않았으므로
# 선택할 수 있는 가장 늦은 날짜를 '어제'로 설정한다.
yesterday_kst = today_kst - timedelta(days=1)


# --------------------------------------------------
# 3. 날짜 선택
# --------------------------------------------------

st.subheader("📅 조회 날짜")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜를 선택하세요.",
    value=yesterday_kst,
    max_value=yesterday_kst,
    format="YYYY-MM-DD"
)

# 날짜를 KOBIS API가 요구하는 YYYYMMDD 형식으로 변환한다.
target_date = selected_date.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 4. KOBIS API 호출 함수
# --------------------------------------------------

# 같은 날짜를 다시 조회하면 1시간 동안 캐시된 결과를 사용한다.
# 따라서 같은 날짜를 여러 번 선택해도 API를 계속 호출하지 않는다.
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # Streamlit Cloud Secrets에서 인증키를 가져온다.
    # 실제 인증키는 코드에 직접 작성하지 않는다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Settings → Secrets에서 "
                "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
            )
        }

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 전달할 요청값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # KOBIS API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류 확인
        response.raise_for_status()

        # JSON 데이터로 변환
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"오류 내용: {e}\n\n"
                "인터넷 연결이나 KOBIS API 서버 상태를 확인해 주세요."
            )
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API의 응답을 JSON으로 읽을 수 없습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인해 주세요."
            )
        }

    # --------------------------------------------------
    # 5. faultInfo 확인
    # --------------------------------------------------

    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있다.
    # 따라서 faultInfo가 있는지 반드시 확인한다.
    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        message = fault_info.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다."
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류가 반환되었습니다.\n\n"
                f"오류 내용: {message}\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• KOBIS_KEY가 정확한지\n"
                "• Streamlit Cloud Secrets에 KOBIS_KEY가 등록되어 있는지\n"
                "• KOBIS API 사용이 정상적으로 허용된 인증키인지"
            )
        }

    # --------------------------------------------------
    # 6. 영화 목록 가져오기
    # --------------------------------------------------

    try:
        movie_list = data["boxOfficeResult"]["dailyBoxOfficeList"]

    except (KeyError, TypeError):
        return {
            "success": False,
            "message": (
                "KOBIS 응답에서 영화 목록을 찾을 수 없습니다.\n\n"
                "KOBIS API 응답 상태를 확인해 주세요."
            )
        }

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "그날은 아직 집계 전입니다."
        }

    return {
        "success": True,
        "empty": False,
        "data": movie_list
    }


# --------------------------------------------------
# 7. 선택한 날짜의 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 8. 오류 또는 빈 데이터 처리
# --------------------------------------------------

if not result["success"]:

    # 영화 목록 자체가 없는 경우
    if result.get("empty", False):
        st.warning("📭 그날은 아직 집계 전입니다.")
        st.info(
            "다른 날짜를 선택해 주세요. "
            "KOBIS에 해당 날짜의 박스오피스 데이터가 등록되면 조회할 수 있습니다."
        )

    # API 오류나 인증키 오류 등
    else:
        st.error("❌ 박스오피스 데이터를 불러오지 못했습니다.")
        st.warning(result["message"])

    # 이후 코드는 실행하지 않는다.
    st.stop()


movies = result["data"]


# --------------------------------------------------
# 9. 숫자 데이터를 숫자로 변환
# --------------------------------------------------

for movie in movies:

    # KOBIS API에서는 숫자도 문자열로 전달된다.
    # 정렬과 그래프에 사용할 수 있도록 int로 변환한다.
    movie["rank"] = int(movie["rank"])
    movie["rankInten"] = int(movie.get("rankInten", 0))
    movie["audiCnt"] = int(movie["audiCnt"])
    movie["audiAcc"] = int(movie["audiAcc"])
    movie["scrnCnt"] = int(movie["scrnCnt"])

    movie["openDt"] = movie.get("openDt", "-")


# 순위를 기준으로 정렬한다.
movies = sorted(
    movies,
    key=lambda x: x["rank"]
)


# --------------------------------------------------
# 10. 조회 날짜 표시
# --------------------------------------------------

st.divider()

st.subheader(f"📊 {display_date} 박스오피스")


# --------------------------------------------------
# 11. 1위 영화 지표 카드
# --------------------------------------------------

first_movie = movies[0]

st.markdown("### 🏆 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="영화명",
        value=first_movie["movieNm"]
    )

with col2:
    st.metric(
        label="일일 관객수",
        value=f'{first_movie["audiCnt"]:,}명'
    )

with col3:
    st.metric(
        label="누적 관객수",
        value=f'{first_movie["audiAcc"]:,}명'
    )


# --------------------------------------------------
# 12. 전체 박스오피스 표 만들기
# --------------------------------------------------

st.markdown("### 📋 전체 박스오피스")

table_data = []

for movie in movies:

    # 순위 증감 표시 만들기
    rank_change = movie["rankInten"]

    if rank_change > 0:
        # 양수 = 순위가 오른 영화
        rank_display = f"🔴 ↑ {rank_change}"

    elif rank_change < 0:
        # 음수 = 순위가 내려간 영화
        rank_display = f"🔵 ↓ {abs(rank_change)}"

    else:
        # 순위 변동이 없는 경우
        rank_display = "―"


    # 누적관객 100만 명 이상이면 트로피 표시
    movie_name = movie["movieNm"]

    if movie["audiAcc"] >= 1_000_000:
        movie_name = f"🏆 {movie_name}"


    table_data.append({
        "순위": movie["rank"],
        "증감": rank_display,
        "영화명": movie_name,
        "개봉일": movie["openDt"],
        "관객수": movie["audiCnt"],
        "누적관객": movie["audiAcc"],
        "스크린수": movie["scrnCnt"]
    })


# 표 출력
st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d"
        ),

        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명"
        ),

        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명"
        ),

        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개"
        )
    }
)


# --------------------------------------------------
# 13. 관객수 상위 5편 그래프
# --------------------------------------------------

st.markdown("### 📈 관객수 상위 5편")

# 관객수를 기준으로 내림차순 정렬한다.
top5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True
)[:5]


# 그래프에 사용할 데이터를 만든다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}


# Streamlit 기본 막대그래프
st.bar_chart(chart_data)


# --------------------------------------------------
# 14. 데이터 출처
# --------------------------------------------------

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 API"
)
