import requests
import streamlit as st
from datetime import datetime, timedelta, timezone


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 일일 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 계산하기
# --------------------------------------------------

# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# 직접 한국 시간(KST, UTC+9)을 사용한다.
KST = timezone(timedelta(hours=9))

# 현재 한국 시간
now_kst = datetime.now(KST)

# 하루를 빼서 '어제'를 구한다.
yesterday = now_kst - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환한다.
target_date = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. KOBIS API 호출 함수
# --------------------------------------------------

# 같은 날짜의 결과를 1시간 동안 캐시한다.
# 따라서 페이지를 새로고침하거나 같은 날짜를 다시 요청해도
# 1시간 동안은 API를 다시 호출하지 않는다.
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Streamlit Cloud의 Secrets에서 인증키를 가져온다.
    # 실제 인증키는 코드에 직접 적지 않는다.
    api_key = st.secrets["KOBIS_KEY"]

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 전달할 요청 데이터
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # API 요청
        response = requests.get(url, params=params, timeout=10)

        # HTTP 오류가 있으면 예외를 발생시킨다.
        response.raise_for_status()

        # JSON 형태의 응답을 읽는다.
        data = response.json()

    except requests.exceptions.RequestException as e:
        # 인터넷 연결이나 API 서버 문제 등
        return {
            "success": False,
            "message": f"KOBIS API 요청에 실패했습니다.\n\n오류 내용: {e}"
        }

    except ValueError:
        # JSON으로 변환할 수 없는 응답이 온 경우
        return {
            "success": False,
            "message": "KOBIS API의 응답을 JSON으로 읽을 수 없습니다."
        }

    # --------------------------------------------------
    # 4. 인증키 오류 확인
    # --------------------------------------------------

    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있다.
    # 따라서 faultInfo가 있는지 반드시 확인한다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # faultInfo 안의 오류 메시지를 가져온다.
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
                "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
                "• KOBIS 인증키가 정확한지\n"
                "• API 사용이 정상적으로 허용된 키인지"
            )
        }

    # --------------------------------------------------
    # 5. 영화 목록 가져오기
    # --------------------------------------------------

    try:
        movie_list = data["boxOfficeResult"]["dailyBoxOfficeList"]
    except (KeyError, TypeError):
        return {
            "success": False,
            "message": (
                "KOBIS 응답에서 영화 목록을 찾을 수 없습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• KOBIS API가 정상적으로 응답했는지\n"
                "• 조회 날짜가 올바른지\n"
                "• KOBIS API 응답 구조가 변경되지 않았는지"
            )
        }

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• KOBIS에 해당 날짜의 집계 자료가 등록되었는지\n"
                "• 조회 날짜가 정상적으로 계산되었는지\n"
                "• KOBIS API가 정상적으로 응답했는지"
            )
        }

    return {
        "success": True,
        "data": movie_list
    }


# --------------------------------------------------
# 6. API에서 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 7. 오류가 발생했을 때 안내하기
# --------------------------------------------------

if not result["success"]:
    st.error("박스오피스 데이터를 불러오지 못했습니다.")
    st.warning(result["message"])
    st.stop()


movies = result["data"]


# --------------------------------------------------
# 8. 숫자 데이터를 실제 숫자로 변환하기
# --------------------------------------------------

# KOBIS에서는 숫자도 문자열로 전달되므로
# 정렬과 그래프에 사용할 수 있도록 int로 변환한다.
for movie in movies:
    movie["rank"] = int(movie["rank"])
    movie["audiCnt"] = int(movie["audiCnt"])
    movie["audiAcc"] = int(movie["audiAcc"])
    movie["scrnCnt"] = int(movie["scrnCnt"])

    # 혹시 데이터에 없는 값이 있을 경우를 대비한다.
    movie["openDt"] = movie.get("openDt", "-")


# 순위를 기준으로 정렬한다.
movies = sorted(movies, key=lambda x: x["rank"])


# --------------------------------------------------
# 9. 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.info(
    f"한국 시간 기준 어제({display_date})의 일일 박스오피스입니다."
)


# --------------------------------------------------
# 10. 1위 영화 지표 카드
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
# 11. 전체 영화 목록 표
# --------------------------------------------------

st.markdown("### 📋 전체 박스오피스")

# 표에 보여줄 데이터만 따로 만든다.
table_data = []

for movie in movies:
    table_data.append({
        "순위": movie["rank"],
        "영화명": movie["movieNm"],
        "개봉일": movie["openDt"],
        "관객수": movie["audiCnt"],
        "누적관객": movie["audiAcc"],
        "스크린수": movie["scrnCnt"]
    })


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
# 12. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.markdown("### 📊 관객수 상위 5편")

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

# Streamlit의 기본 막대그래프를 사용한다.
st.bar_chart(chart_data)


# --------------------------------------------------
# 13. 데이터 출처 안내
# --------------------------------------------------

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 API"
)
