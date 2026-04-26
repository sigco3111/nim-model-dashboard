import os
import requests
import streamlit as st
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime
from streamlit_js_eval import get_local_storage, set_local_storage, remove_local_storage

from nim_api import get_chat_models, fetch_models, check_single_model, _get_env_key, KNOWN_GOOD_MODELS

LOCALSTORAGE_KEY = "nim_api_key"
CUSTOM_MODELS_KEY = "nim_custom_models"

# 오픈코드 대상 모델 검색 패턴 (NIM API model ID에서 대소문자 무시 부분 매칭)
OPENCODE_PATTERNS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-coder-6.7b",
    "glm-5", "glm5",
    "gpt-oss",
    "kimi",
    "minimax",
    "qwen3-coder-480b",
    "qwen3.5-397b", "qwen3-5-397b",
    "nemotron-3-super",
    "nemotron-4-340b",
]

OPENCODE_DISPLAY_NAMES = {
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-coder-6.7b": "DeepSeek Coder 6.7B Instruct",
    "glm-5": "GLM5", "glm5": "GLM5",
    "gpt-oss": "GPT-OSS-120B",
    "kimi": "Kimi K2.5",
    "minimax": "MiniMax-M2.7",
    "qwen3-coder-480b": "Qwen3 Coder 480B A35B Instruct",
    "qwen3.5-397b": "Qwen3.5-397B-A17B", "qwen3-5-397b": "Qwen3.5-397B-A17B",
    "nemotron-3-super": "Nemotron 3 Super",
    "nemotron-4-340b": "Nemotron 4 340B Instruct",
}


def _match_opencode_models(model_ids: list[str]) -> list[str]:
    return [
        mid for mid in model_ids
        if any(p in mid.lower() for p in OPENCODE_PATTERNS)
    ]


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


def _write_localstorage(value: str) -> None:
    set_local_storage(LOCALSTORAGE_KEY, value)


def _remove_localstorage() -> None:
    remove_local_storage(LOCALSTORAGE_KEY)


# localStorage에서 키 복원 (비동기 응답 대기)
if "api_key" not in st.session_state:
    saved = get_local_storage(LOCALSTORAGE_KEY)
    if saved and isinstance(saved, str) and saved not in ("null", ""):
        st.session_state.api_key = saved
if "custom_models_value" not in st.session_state:
    saved_models = get_local_storage(CUSTOM_MODELS_KEY)
    if saved_models and isinstance(saved_models, str) and saved_models not in ("null", ""):
        st.session_state.custom_models_value = saved_models
        st.session_state.custom_models_widget = saved_models

with st.expander("⚙️ API 키 설정", expanded=False):
    col1, col2, col3 = st.columns([3, 1, 1])
    api_key = col1.text_input(
        "NVIDIA NIM API 키",
        type="password",
        placeholder="키를 입력하세요",
        key="api_key_input",
    )
    if col2.button("💾 저장"):
        if api_key:
            st.session_state.api_key = api_key
            _write_localstorage(api_key)
            st.success("API 키가 저장되었습니다! (브라우저에 저장되어 새로고침해도 유지됩니다)")
        else:
            st.warning("⚠️ API 키를 먼저 입력해주세요.")
    if col3.button("🗑️ 초기화"):
        if "api_key" in st.session_state:
            del st.session_state.api_key
        st.session_state.api_key_input = ""
        _remove_localstorage()
        st.success("API 키가 초기화되었습니다!")
        st.rerun()

effective_key = st.session_state.get("api_key", "") or _get_env_key()

if not effective_key:
    st.warning("⚠️ 상단의 'API 키 설정'에서 NVIDIA NIM API 키를 입력하고 저장해주세요.")
    st.info("💡 [build.nvidia.com](https://build.nvidia.com/explore/discover) 에서 무료 키를 발급받으실 수 있습니다.")
    st.stop()

st.markdown("#### 🎯 체크할 모델 선택")
filter_col1, filter_col2 = st.columns([1, 2])
with filter_col1:
    model_filter = st.selectbox(
        "필터",
        ["전체", "오픈코드", "사용자정의"],
        index=0,
    )
with filter_col2:
    if model_filter == "오픈코드":
        opencode_names = sorted(set(OPENCODE_DISPLAY_NAMES.values()))
        st.info(f"📋 **{len(opencode_names)}개 오픈코드 모델**: {', '.join(opencode_names)}")
    elif model_filter == "사용자정의":
        def _on_custom_change():
            val = st.session_state.get("custom_models_widget", "")
            st.session_state.custom_models_value = val
            set_local_storage(CUSTOM_MODELS_KEY, val)
        custom_input = st.text_input(
            "모델 ID 입력 (콤마로 구분)",
            placeholder="meta/llama-3.1-8b-instruct, google/gemma-2-9b-it",
            value=st.session_state.get("custom_models_value", ""),
            key="custom_models_widget",
            on_change=_on_custom_change,
        )

if st.button("🔍 모델 상태 체크 시작", key="check_btn", use_container_width=True):
    try:
        results = []

        if model_filter == "사용자정의":
            model_ids = [m.strip() for m in custom_input.split(",") if m.strip()]
            if not model_ids:
                st.warning("⚠️ 체크할 모델 ID를 입력해주세요.")
                st.stop()
            st.info(f"📋 사용자 정의 {len(model_ids)}개 모델 헬스체크를 시작합니다...")
        else:
            with st.spinner("📡 모델 목록을 조회하는 중..."):
                all_models = get_chat_models(effective_key)

            if not all_models:
                st.error("❌ 조회된 모델이 없습니다. API 키를 확인해주세요.")
                st.stop()

            if model_filter == "오픈코드":
                model_ids = _match_opencode_models(all_models)
                if not model_ids:
                    st.warning("⚠️ 오픈코드 대상 모델과 매칭되는 항목이 없습니다.")
                    unmatched = [e["name"] for e in [{"name": v} for v in set(OPENCODE_DISPLAY_NAMES.values())]]
                    st.info("전체 모델 목록에서 매칭을 시도합니다. API에서 제공하는 모델 ID와 패턴이 다를 수 있습니다.")
                    st.stop()
                st.info(f"📋 오픈코드 {len(model_ids)}개 모델 (전체 {len(all_models)}개 중) 헬스체크를 시작합니다...")
            else:
                model_ids = all_models
                st.info(f"📋 총 {len(model_ids)}개 채팅 모델을 발견했습니다. 헬스체크를 시작합니다...")

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

            if test_result["status"] == "✅":
                results.append(test_result)

            model_ids = [m for m in model_ids if m != test_model]

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_model = {
                executor.submit(check_single_model, mid, effective_key): mid
                for mid in model_ids
            }

            progress_bar = st.progress(0)
            status_text = st.empty()
            total_count = len(model_ids) + (1 if results else 0)

            for i, future in enumerate(as_completed(future_to_model)):
                result = future.result()
                results.append(result)
                checked = i + 1 + (1 if len(results) > len(model_ids) else 0)
                progress = int(checked / (len(model_ids) + (1 if not results or len(results) > len(future_to_model) else 0)) * 100)
                progress = min(progress, 100)
                progress_bar.progress(progress)
                status_text.text(f"체크 중: {checked}/{len(model_ids) + (1 if len(results) > len(future_to_model) else 0)} ({result['status']}) {result['model']}")

            progress_bar.empty()
            status_text.empty()

        st.session_state.results = results
        st.session_state.last_check = datetime.now()
        st.session_state.model_count = len(results)
        st.session_state.filter_label = model_filter
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

    model_info = f"체크된 모델: {st.session_state.get('model_count', '?')}개"
    filter_label = st.session_state.get("filter_label", "")
    if filter_label:
        model_info += f" ({filter_label})"
    st.markdown(f"<div style='text-align: center; color: #6c757d; font-size: 12px; margin-top: 20px;'>마지막 체크: {st.session_state.last_check.strftime('%Y-%m-%d %H:%M:%S')} | {model_info}</div>", unsafe_allow_html=True)
