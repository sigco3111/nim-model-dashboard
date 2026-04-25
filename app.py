import os
import requests
import streamlit as st
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime

from nim_api import get_chat_models, fetch_models, check_single_model, _get_env_key, KNOWN_GOOD_MODELS

st.set_page_config(
    page_title="NVIDIA NIM 모델 대시보드",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

st.markdown('<div class="main-header">🚀 NVIDIA NIM 모델 대시보드</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">실시간 모델 상태, 응답 속도, 가용성 확인 도구</div>', unsafe_allow_html=True)

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

effective_key = st.session_state.get("api_key", "") or _get_env_key()

if not effective_key:
    st.warning("⚠️ 상단의 'API 키 설정'에서 NVIDIA NIM API 키를 입력하고 저장해주세요.")
    st.info("💡 [build.nvidia.com](https://build.nvidia.com/explore/discover) 에서 무료 키를 발급받으실 수 있습니다.")
    st.stop()

if st.button("🔍 모델 상태 체크 시작", key="check_btn", use_container_width=True):
    try:
        with st.spinner("📡 모델 목록을 조회하는 중..."):
            model_ids = get_chat_models(effective_key)

        if not model_ids:
            st.error("❌ 조회된 모델이 없습니다. API 키를 확인해주세요.")
            st.stop()

        st.info(f"📋 총 {len(model_ids)}개 채팅 모델을 발견했습니다. 헬스체크를 시작합니다...")

        # 검증된 안정 모델로 연결 테스트
        test_model = None
        for candidate in KNOWN_GOOD_MODELS:
            if candidate in model_ids:
                test_model = candidate
                break
        if not test_model:
            test_model = model_ids[0]

        st.write(f"🧪 연결 테스트: {test_model}")

        test_result = check_single_model(test_model, effective_key)

        if test_result["status"] == "❌":
            st.warning(f"⚠️ {test_model} 응답 없음. 전체 모델 체크를 계속 진행합니다...")
        else:
            st.success(f"✅ 연결 테스트 성공! ({test_result['response_time']}ms, {test_result['tokens_per_sec']} tokens/sec)")

        results = []
        if test_result["status"] == "✅":
            results.append(test_result)

        models_to_check = [m for m in model_ids if m != test_model]

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_model = {
                executor.submit(check_single_model, mid, effective_key): mid
                for mid in models_to_check
            }

            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, future in enumerate(as_completed(future_to_model)):
                result = future.result()
                results.append(result)
                progress = int((i + 1) / len(model_ids) * 100)
                progress_bar.progress(progress)
                checked = i + 1 + (1 if test_result["status"] == "✅" else 0)
                status_text.text(f"체크 중: {checked}/{len(model_ids)} ({result['status']}) {result['model']}")

            progress_bar.empty()
            status_text.empty()

        st.session_state.results = results
        st.session_state.last_check = datetime.now()
        st.session_state.model_count = len(model_ids)
        st.success(f"✅ 체크 완료! 총 {len(results)}개 모델 결과를 확인하세요.")
        st.rerun()

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            st.error("❌ API 키가 유효하지 않습니다. 새 키를 발급받아주세요.")
        else:
            st.error(f"❌ API 오류: {str(e)}")
    except Exception as e:
        st.error(f"❌ 에러 발생: {str(e)}")

if "results" in st.session_state and st.session_state.results:
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.selectbox("필터", ["전체", "성공", "실패"])
    with col2:
        sort_by = st.selectbox("정렬", ["응답 시간 (빠른순)", "토큰/초 (빠른순)", "모델 이름", "상태"])

    df = pd.DataFrame(st.session_state.results)

    if filter_status == "성공":
        df = df[df["status"] == "✅"]
    elif filter_status == "실패":
        df = df[df["status"] == "❌"]

    if sort_by == "응답 시간 (빠른순)":
        df = df.sort_values("response_time", key=lambda x: pd.to_numeric(x, errors="coerce"))
    elif sort_by == "토큰/초 (빠른순)":
        df = df.sort_values("tokens_per_sec", key=lambda x: pd.to_numeric(x, errors="coerce"), ascending=False)
    elif sort_by == "모델 이름":
        df = df.sort_values("model")
    elif sort_by == "상태":
        df = df.sort_values("status", ascending=False)

    total = len(df)
    success = len(df[df["status"] == "✅"])
    failed = total - success
    avg_time = df[df["status"] == "✅"]["response_time"].mean() if success > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 모델 수", total)
    c2.metric("성공", success, delta=f"{success/total*100:.1f}%" if total > 0 else "0%")
    c3.metric("실패", failed, delta=f"{failed/total*100:.1f}%" if total > 0 else "0%", delta_color="inverse")
    c4.metric("평균 응답 시간", f"{avg_time:.0f} ms" if avg_time else "N/A")

    st.dataframe(
        df.style.map(lambda v: "color: #28a745; font-weight: bold;" if v == "✅" else "color: #dc3545; font-weight: bold;" if v == "❌" else "", subset=["status"]),
        use_container_width=True,
        hide_index=True
    )

    model_info = f"조회된 모델: {st.session_state.get('model_count', '?')}개" if "model_count" in st.session_state else ""
    st.markdown(f"<div style='text-align: center; color: #6c757d; font-size: 12px; margin-top: 20px;'>마지막 체크: {st.session_state.last_check.strftime('%Y-%m-%d %H:%M:%S')} | {model_info}</div>", unsafe_allow_html=True)
