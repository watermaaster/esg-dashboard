import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
import datetime  # 날짜 처리를 위해 반드시 상단에 필요

# 1. 페이지 설정
st.set_page_config(page_title="ESG 수질 관리 플랫폼", layout="wide")

# 2. 실시간 API 함수 (팀장님이 찾아낸 샘플 코드 규격 적용)
def get_api_realtime_data():
    service_key = "a810c94e1da3f88775b8a6fa0499d92deb044be2069bc29203f152d2ae1d8373"
    url = 'http://apis.data.go.kr/B500001/rwis/waterQuality/list'
    
    # 샘플 코드처럼 날짜와 필수 코드들을 설정합니다.
    # 현재 날짜로 설정하되, 데이터가 없을 경우를 대비해 파라미터를 정밀하게 구성합니다.
    now = datetime.datetime.now()
    target_date = now.strftime('%Y-%m-%d')
    
    params = {
        'serviceKey' : service_key,
        'stDt' : target_date,      # 시작 날짜
        'stTm' : '00',              # 시작 시간
        'edDt' : target_date,      # 종료 날짜
        'edTm' : '23',              # 종료 시간
        'fcltyMngNo' : '4824012333', # 팀장님이 찾은 시설관리번호
        'sujCode' : '333',          # 수계코드
        'liIndDiv' : '1',           # 라인/인덱스 구분
        'numOfRows' : '10',
        'pageNo' : '1',
        '_type' : 'json'            # 결과 포맷
    }

    try:
        # 샘플 코드의 requests 방식을 그대로 따릅니다.
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in response.text:
                return "❌ [키 에러] 인증키가 아직 활성화되지 않았습니다."
            
            data = response.json()
            # 공공데이터 특유의 복잡한 JSON 구조 파싱
            if 'response' in data and 'body' in data['response']:
                body = data['response']['body']
                if 'items' in body and body['items'] and 'item' in body['items']:
                    return pd.DataFrame(body['items']['item'])
            return f"⚠️ [데이터 없음] 해당 조건에 값이 없습니다. (응답: {response.text[:50]})"
        return f"❌ [서버 연결 실패] HTTP {response.status_code}"
    except Exception as e:
        return f"❌ [오류 발생] {str(e)}"

# 3. 과거 데이터 로드 함수 (메모리 최적화 유지)
def load_excel_safe():
    files = os.listdir('.')
    w_files = [f for f in files if f.endswith('.xlsx')]
    if not w_files: return None
    
    target_columns = ['일자', '총량지점명', 'BOD(㎎/L)', '유량(㎥/s)']
    try:
        data_list = []
        for f in w_files:
            temp = pd.read_excel(f, header=1, usecols=lambda x: x in target_columns)
            if 'BOD(㎎/L)' in temp.columns: temp['BOD(㎎/L)'] = temp['BOD(㎎/L)'].astype('float32')
            data_list.append(temp)
        full_df = pd.concat(data_list, ignore_index=True)
        full_df['일자'] = pd.to_datetime(full_df['일자'].astype(str).str.replace('.', '-'), errors='coerce')
        return full_df
    except:
        return None

# --- 메인 실행부 ---
st.title("🌊 지능형 ESG 수질-기상 통합 플랫폼")

tab1, tab2 = st.tabs(["📊 과거 분석 시뮬레이션", "📡 실시간 API 모니터링"])

with tab1:
    df = load_excel_safe()
    if df is not None:
        st.sidebar.header("📍 분석 설정")
        target = st.sidebar.selectbox("지점 선택", sorted(df['총량지점명'].unique()))
        rate = st.sidebar.slider("목표 저감률 (%)", 0, 100, 50)
        
        filtered = df[df['총량지점명'] == target].copy().sort_values('일자')
        filtered['Original_C'] = filtered['BOD(㎎/L)'] * filtered['유량(㎥/s)'] * 86.4 * 0.5 * 0.4781
        filtered['Simulated_C'] = filtered['Original_C'] * (1 - rate / 100)

        c1, c2, c3 = st.columns(3)
        if not filtered.empty:
            c1.metric("선택 지점", target)
            c2.metric("최근 BOD", f"{filtered.iloc[-1]['BOD(㎎/L)']} mg/L")
            c3.metric("예상 저감량", f"{round(filtered['Original_C'].sum() - filtered['Simulated_C'].sum(), 1)} kg")
            
            fig = px.line(filtered, x='일자', y=['Original_C', 'Simulated_C'], title="탄소 배출 시뮬레이션")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📂 폴더에 '수질' 엑셀 파일을 넣어주세요.")

with tab2:
    st.subheader("📡 K-water 실시간 연동 (샘플 코드 규격)")
    if st.button("🔄 데이터 실시간 호출"):
        with st.spinner("샘플 파라미터로 데이터 요청 중..."):
            res = get_api_realtime_data()
            if isinstance(res, pd.DataFrame):
                st.success("✅ 실시간 연결 성공!")
                st.dataframe(res)
            else:
                st.error(res)
