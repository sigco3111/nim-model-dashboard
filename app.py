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

# NVIDIA NIM 공식 엔드포인트 ID 목록 (2024-10 기준, build.nvidia.com 기반)
# 주의: ID 형식은 `org/model-name` 형태이며, 버전 정보 (예: 3.1) 는 제거된 경우가 많음
NIM_MODELS = [
    "meta/llama3-8b-instruct",      # 가장 안정적인 모델 (무료 티어 권장)
    "meta/llama3-70b-instruct",
    "nvidia/nemotron-4-340b-instruct",
    "mistralai/mixtral-8x7b-instruct-v0.1",
    "mistralai/mistral-7b-instruct-v0.3",
    "google/gemma-2-9b-it",
    "google/gemma-2-27b-it",
    "qwen/qwen2-7b-instruct",
    "qwen/qwen2-72b-instruct",
    "cohere/command-r-plus",
    "cohere/command-r",
    "ai21labs/jamba-1.5-mini-instruct",
    "snowflake/arctic",
    "databricks/dbrx-instruct",
    "THUDM/glm-4-9b-chat",
    "01-ai/Yi-1.5-9B-Chat",
]

# 체크 함수 (동기 방식) - 에러 상세 정보 포함
def check_single_model(model_id, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
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
        
        # 응답 본문 확인 (에러 메시지 포함)
        try:
            error_detail = resp.json().get("detail", resp.text)
        except:
            error_detail = resp.text
        
        if resp.status_code == 200:
            resp_data = resp.json()
            content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = len(content.split()) if content else 0
            tokens_sec = tokens / (duration / 1000) if duration > 0 else 0
            
            return {
                "model": model_id,
                "status": "✅",
                "response_time": round(duration, 2),
                "tokens_per_sec": round(tokens_sec, 2),
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": ""
            }
        else:
            return {
                "model": model_id,
                "status": "❌",
                "response_time": 0,
                "tokens_per_sec": 0,
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": f"HTTP {resp.status_code}: {error_detail}"
            }
    except requests.exceptions.Timeout:
        return {
            "model": model_id,
            "status": "❌",
            "response_time": 0,
            "tokens_per_sec": 0,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": "Timeout (15s)"
        }
    except Exception as e:
        return {
            "model": model_id,
            "status": "❌",
            "response_time": 0,
            "tokens_per_sec": 0,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e)
        }

# 체크 버튼
if st.button("🔍 모델 상태 체크 시작", key="check_btn", use_container_width=True):
    try:
        # 1. 단일 모델 테스트 (첫 번째 모델만 체크)
        test_model = NIM_MODELS[0]
        st.write(f"🧪 먼저 첫 번째 모델 ({test_model}) 로 테스트 중...")
        
        test_result = check_single_model(test_model, st.session_state.api_key)
        
        if test_result["status"] == "❌":
            st.error(f"❌ 테스트 모델 체크 실패: {test_result['error']}")
            st.info(f"""
            💡 **확인사항**:
            - **API 키**: [build.nvidia.com](https://build.nvidia.com) 에서 새 키를 발급받으세요.
            - **모델 지원 여부**: 무료 티어에서 `{test_model}`이 지원되는지 확인하세요.
            - **엔드포인트 ID**: `build.nvidia.com` 에서 모델을 선택하면 **API 엔드포인트**가 표시됩니다. 그 URL 에서 ID 를 추출하세요.
              - 예: `https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{test_model}`
            - **권장**: `meta/llama3-8b-instruct` 는 가장 안정적인 모델입니다.
            """)
            st.stop()
        else:
            st.success(f"✅ 테스트 성공! ({test_result['response_time']}ms, {test_result['tokens_per_sec']} tokens/sec)")
            st.write(f"🔎 총 {len(NIM_MODELS)}개 모델을 체크합니다...")
        
        # 2. 전체 모델 체크
        results = [test_result]  # 테스트 결과를 포함
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 첫 번째 모델 제외하고 체크
            remaining_models = NIM_MODELS[1:]
            future_to_model = {executor.submit(check_single_model, mid, st.session_state.api_key): mid for mid in remaining_models}
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, future in enumerate(as_completed(future_to_model)):
                result = future.result()
                results.append(result)
                progress = int((i + 1) / len(NIM_MODELS) * 100)
                progress_bar.progress(progress)
                status_text.text(f"체크 중: {i + 2}/{len(NIM_MODELS)} ({result['status']})")
            
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
        df.style.map(lambda v: "color: #28a745; font-weight: bold;" if v == "✅" else "color: #dc3545; font-weight: bold;" if v == "❌" else "", subset=["status"]),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown(f"<div style='text-align: center; color: #6c757d; font-size: 12px; margin-top: 20px;'>마지막 체크: {st.session_state.last_check.strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)
