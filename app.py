import streamlit as st
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="NVIDIA NIM 모델 대시보드",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 커스텀 CSS (깔끔한 디자인)
st.markdown("""
<style>
    .main-header { font-size: 28px; font-weight: 700; color: #1a1a1a; text-align: center; margin-bottom: 20px; }
    .subtitle { text-align: center; color: #6c757d; margin-bottom: 30px; font-size: 16px; }
    .metric-card { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 15px; text-align: center; }
    .metric-value { font-size: 24px; font-weight: 700; color: #0066cc; }
    .metric-label { font-size: 14px; color: #6c757d; margin-top: 5px; }
    .status-success { color: #28a745; font-weight: 600; }
    .status-error { color: #dc3545; font-weight: 600; }
    .btn-check { background-color: #0066cc; color: white; border: none; border-radius: 6px; padding: 12px 24px; font-weight: 600; font-size: 16px; width: 100%; margin-bottom: 20px; }
    .btn-check:hover { background-color: #0052a3; }
    .api-section { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# 헤더
st.markdown('<div class="main-header">🚀 NVIDIA NIM 모델 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">실시간 모델 상태, 응답 속도, 가용성 확인 도구</div>', unsafe_allow_html=True)

# API 키 관리
with st.expander("⚙️ API 키 설정", expanded=False):
    col1, col2, col3 = st.columns([3, 1, 1])
    api_key = col1.text_input("NVIDIA NIM API 키", type="password", placeholder="키를 입력하세요")
    if col2.button("💾 저장"):
        st.session_state.api_key = api_key
        st.success("API 키가 저장되었습니다!")
    if col3.button("🗑️ 초기화"):
        if "api_key" in st.session_state:
            del st.session_state.api_key
        st.success("API 키가 초기화되었습니다!")
        st.rerun()

# 키 확인
if "api_key" not in st.session_state or not st.session_state.api_key:
    st.warning("⚠️ 상단의 'API 키 설정'에서 NVIDIA NIM API 키를 입력하고 저장해주세요.")
    st.stop()

# 체크 함수 (동기 방식)
def check_single_model(model, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    model_id = model.get("id", "unknown")
    model_name = model.get("name", model_id)
    
    try:
        start = time.time()
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1
        }
        
        resp = requests.post(
            f"https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{model_id}",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        duration = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            resp_data = resp.json()
            content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = len(content.split()) if content else 0
            tokens_sec = tokens / (duration / 1000) if duration > 0 else 0
            
            return {
                "model": model_name,
                "status": "✅",
                "response_time": round(duration, 2),
                "tokens_per_sec": round(tokens_sec, 2),
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": ""
            }
        else:
            return {
                "model": model_name,
                "status": "❌",
                "response_time": 0,
                "tokens_per_sec": 0,
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": f"HTTP {resp.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "model": model_name,
            "status": "❌",
            "response_time": 0,
            "tokens_per_sec": 0,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": "Timeout"
        }
    except Exception as e:
        return {
            "model": model_name,
            "status": "❌",
            "response_time": 0,
            "tokens_per_sec": 0,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e)
        }

# 체크 버튼
if st.button("🔍 모델 상태 체크 시작", key="check_btn", use_container_width=True):
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.api_key}",
            "Content-Type": "application/json"
        }
        
        # 1. 모델 목록 조회
        st.write("📡 NVIDIA NIM API 에서 모델 목록을 가져오는 중...")
        resp = requests.get("https://api.nvcf.nvidia.com/v2/nvcf/functions", headers=headers, timeout=30)
        if resp.status_code != 200:
            st.error(f"모델 목록 조회 실패: {resp.status_code} - {resp.text}")
            st.stop()
        
        models_list = resp.json().get("functions", [])
        nim_models = models_list  # 모든 모델 체크
        
        total = len(nim_models)
        st.write(f"🔎 총 {total}개 모델을 발견했습니다. 체크를 시작합니다...")
        
        # 2. 병렬 체크 (ThreadPoolExecutor 사용)
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_model = {executor.submit(check_single_model, m, st.session_state.api_key): m for m in nim_models}
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, future in enumerate(as_completed(future_to_model)):
                result = future.result()
                results.append(result)
                progress = int((i + 1) / total * 100)
                progress_bar.progress(progress)
                status_text.text(f"체크 중: {i + 1}/{total} ({result['status']})")
            
            progress_bar.empty()
            status_text.empty()
        
        st.session_state.results = results
        st.session_state.last_check = datetime.now()
        st.success(f"✅ 체크 완료! 총 {len(results)}개 모델 결과를 확인하세요.")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ 에러 발생: {str(e)}")

# 결과 표시
if "results" in st.session_state and st.session_state.results:
    st.markdown("---")
    
    # 필터 & 정렬
    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.selectbox("필터", ["전체", "성공", "실패"])
    with col2:
        sort_by = st.selectbox("정렬", ["응답 시간 (빠른순)", "토큰/초 (빠른순)", "모델 이름", "상태"])
    
    df = pd.DataFrame(st.session_state.results)
    
    # 필터 적용
    if filter_status == "성공":
        df = df[df["status"] == "✅"]
    elif filter_status == "실패":
        df = df[df["status"] == "❌"]
    
    # 정렬 적용
    if sort_by == "응답 시간 (빠른순)":
        df = df.sort_values("response_time", key=lambda x: pd.to_numeric(x, errors="coerce"))
    elif sort_by == "토큰/초 (빠른순)":
        df = df.sort_values("tokens_per_sec", key=lambda x: pd.to_numeric(x, errors="coerce"), ascending=False)
    elif sort_by == "모델 이름":
        df = df.sort_values("model")
    elif sort_by == "상태":
        df = df.sort_values("status", ascending=False)
    
    # 메트릭스
    total = len(df)
    success = len(df[df["status"] == "✅"])
    failed = total - success
    avg_time = df[df["status"] == "✅"]["response_time"].mean() if success > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 모델 수", total)
    c2.metric("성공", success, delta=f"{success/total*100:.1f}%" if total > 0 else "0%")
    c3.metric("실패", failed, delta=f"{failed/total*100:.1f}%" if total > 0 else "0%", delta_color="inverse")
    c4.metric("평균 응답 시간", f"{avg_time:.0f} ms" if avg_time else "N/A")
    
    # 테이블
    st.dataframe(
        df.style.applymap(lambda v: "color: #28a745; font-weight: bold;" if v == "✅" else "color: #dc3545; font-weight: bold;" if v == "❌" else "", subset=["status"]),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown(f"<div style='text-align: center; color: #6c757d; font-size: 12px; margin-top: 20px;'>마지막 체크: {st.session_state.last_check.strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)
