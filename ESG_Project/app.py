import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
import datetime

# 1. 페이지 설정
st.set_page_config(page_title="ESG 수질 관리 플랫폼", layout="wide")

# 2. 실시간 API 함수
def get_api_realtime_data():
    service_key = "a810c94e1da3f88775b8a6fa0499d92deb044be2069bc29203f152d2ae1d8373"
    url = 'http://apis.data.go.kr/B500001/rwis/waterQuality/list'
    
    now = datetime.datetime.now()
    target_date = now.strftime('%Y-%m-%d')
    
    params = {
        'serviceKey' : service_key,
        'stDt' : target_date,
        'stTm' : '00',
        'edDt' : target_date,
        'edTm' : '23',
        'fcltyMngNo' : '4824012333',
        'sujCode' : '333',
        'liIndDiv' : '1',
        'numOfRows' : '10',
        'pageNo' : '1',
        '_type' : 'json'
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED" in response.text:
                return "❌ [키 에러] 인증키가 아직 활성화되지 않았습니다."
            
            data = response.json()
            if 'response' in data and 'body' in data['response']:
                body = data['response']['body']
                if 'items' in body and body['items'] and 'item' in body['items']:
                    return pd.DataFrame(body['items']['item'])
            return f"⚠️ [데이터 없음] 해당 조건에 값이 없습니다."
        return f"❌ [서버 연결 실패] HTTP {response.status_code}"
    except Exception as e:
        return f"❌ [오류 발생] {str(e)}"

# 3. 과거 데이터 로드 함수 (경로 인식 및 파일 탐색 최적화)
def load_excel_safe():
    # 현재 app.py가 실행되는 디렉토리 경로 확보
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 해당 폴더 내의 모든 파일 목록 추출
    try:
        files = os.listdir(current_dir)
    except Exception as e:
        st.error(f"디렉토리 접근 오류: {e}")
        return None

    # 확장자가 .xlsx인 파일만 필터링
    w_files = [f for f in files if f.endswith('.xlsx')]
    
    if not w_files:
        return None
    
    target_columns = ['일자', '총량지점명', 'BOD(㎎/L)', '유량(㎥/s)']
    data_list = []
    
    try:
        for f in w_files:
            # 절대 경로로 파일 위치 지정
            file_path = os.path.join(current_dir, f)
            # 엑셀 읽기 (두 번째 줄이 헤더인 기존 규격 유지)
            temp = pd.read_excel(file_path, header=1, usecols=lambda x: x in target_columns)
            
            if 'BOD(㎎/L)' in temp.columns:
                temp['BOD(㎎/L)'] = temp['BOD(㎎/L)'].astype('float32')
            data_list.append(temp)
        
        if not data_list:
            return None
            
        full_df = pd.concat(data_list, ignore_index=True)
        # 날짜 형식 처리 (.을 -로 변환)
        full_df['일자'] = pd.to_datetime(full_df['일자'].astype(str).str.replace('.', '-'), errors='coerce')
        return full_df
    except Exception as e:
        st.error(f"데이터 처리 중 오류 발생: {e}")
        return None

# --- 메인 실행부 ---
st.title("🌊 지능형 ESG 수질-기상 통합 플랫폼")

tab1, tab2 = st.tabs(["📊 과거 분석 시뮬레이션", "📡 실시간 API 모니터링"])

with tab1:
    df = load_excel_safe()
    if df is not None and not df.empty:
        st.sidebar.header("📍 분석 설정")
        # 지점 목록 추출 및 정렬
        locations = sorted(df['총량지점명'].dropna().unique())
        target = st.sidebar.selectbox("지점 선택", locations)
        rate = st.sidebar.slider("목표 저감률 (%)", 0, 100, 50)
        
        filtered = df[df['총량지점명'] == target].copy().sort_values('일자')
        
        if not filtered.empty:
            # 탄소 배출 방정식 적용 (팀장님 수식)
            filtered['Original_C'] = filtered['BOD(㎎/L)'] * filtered['유량(㎥/s)'] * 86.4 * 0.5 * 0.4781
            filtered['Simulated_C'] = filtered['Original_C'] * (1 - rate / 100)

            c1, c2, c3 = st.columns(3)
            c1.metric("선택 지점", target)
            
            # 최근 데이터 추출
            last_bod = filtered.iloc[-1]['BOD(㎎/L)']
            total_reduction = filtered['Original_C'].sum() - filtered['Simulated_C'].sum()
            
            c2.metric("최근 BOD", f"{last_bod:.2f} mg/L")
            c3.metric("예상 저감량", f"{total_reduction:.1f} kg")
            
            # 시각화
            fig = px.line(filtered, x='일자', y=['Original_C', 'Simulated_C'], 
                          title=f"[{target}] 탄소 배출 시뮬레이션 (저감률 {rate}%)",
                          labels={'value': '탄소 배출량 (kg)', 'variable': '구분'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("선택한 지점에 해당하는 데이터가 없습니다.")
    else:
        st.info("📂 ESG_Project 폴더 내에 엑셀 파일(.xlsx)이 있는지 확인해주세요.")

with tab2:
    st.subheader("📡 K-water 실시간 연동 (샘플 코드 규격)")
    if st.button("🔄 데이터 실시간 호출"):
        with st.spinner("데이터 요청 중..."):
            res = get_api_realtime_data()
            if isinstance(res, pd.DataFrame):
                st.success("✅ 실시간 연결 성공!")
                st.dataframe(res)
            else:
                st.error(res)
