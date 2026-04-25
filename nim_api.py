"""
NVIDIA NIM API 모듈
- 동적 모델 목록 조회 (GET /v1/models)
- 채팅 호환 모델 사전 필터링
- 개별 모델 헬스체크 (POST /v1/chat/completions)
"""

import os
import time
import requests
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NIM_BASE_URL = "https://integrate.api.nvidia.com"

# 채팅 비호환 모델 제외 패턴 (임베딩, 이미지, 의료, 특수 목적 등)
EXCLUDE_PATTERNS = [
    # 임베딩 / 리랭킹
    "embed", "rerank", "retriever", "e5", "nv-embedqa", "bge",
    # 이미지 생성 / 비전 특수 모델
    "flux", "stable-diffusion", "sdxl", "stable-video", "stable-diffusion",
    # 의료 / 바이오 / 단백질
    "alphafold", "protein", "molecular", "boltz", "diffdock",
    "rfdiffusion", "openfold", "esmfold", "esm2",
    "genmol", "maisi", "molmim",
    # 코드 생성 (채팅 아님)
    "starcoder", "codestral",
    # 특수 목적
    "cuopt", "corrdiff", "fourcastnet",
    "gliner", "pii", "jailbreak", "detect",
    "grounding-dino", "dinov2", "ocdrnet",
    "bevformer", "sparsedrive", "streampetr",
    "trellis", "visual-changenet",
    "retail-object", "cosmos-predict", "usdsearch",
    # 오디오
    "tts", "asr", "whisper", "canary", "parakeet",
    # 기타 비채팅
    "vista3d", "segformer", "sam2", "dextr",
    "fuyu", "kosmos", "llava", "phi-3-vision",
    "neva", "vila",
]

# 연결 테스트용으로 검증된 안정 모델
KNOWN_GOOD_MODELS = [
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3-8b-instruct",
    "mistralai/mistral-7b-instruct-v0.3",
    "google/gemma-2-9b-it",
]


def _get_env_key() -> str:
    """환경변수에서 API 키 조회"""
    return os.environ.get("NVIDIA_API_KEY", "")


def fetch_models(api_key: str) -> list[dict]:
    """
    GET /v1/models 에서 전체 모델 목록을 조회합니다.
    Returns list of model dicts with 'id', 'owned_by', 'max_model_len', etc.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.get(
        f"{NIM_BASE_URL}/v1/models",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def filter_chat_models(models: list[dict]) -> list[str]:
    """
    채팅 완성 API 에서 사용 가능할 가능성이 높은 모델 ID 만 필터링합니다.
    EXCLUDE_PATTERNS 에 매칭되는 모델을 제외합니다.
    """
    chat_model_ids = []
    for model in models:
        model_id = model.get("id", "").lower()
        excluded = any(pattern.lower() in model_id for pattern in EXCLUDE_PATTERNS)
        if not excluded:
            chat_model_ids.append(model["id"])
    return chat_model_ids


def get_chat_models(api_key: str) -> list[str]:
    """
    메인 진입점: 모델 목록 조회 + 채팅 모델 필터링.
    """
    models = fetch_models(api_key)
    return filter_chat_models(models)


def check_single_model(model_id: str, api_key: str, max_retries: int = 2) -> dict:
    """
    단일 모델 헬스체크.
    POST /v1/chat/completions 에 최소 페이로드를 전송하여
    응답 시간, 토큰 속도, 상태를 측정합니다.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries + 1):
        try:
            start = time.time()
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 1,
                "temperature": 0.0,
            }

            resp = requests.post(
                f"{NIM_BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=10,
            )

            duration = (time.time() - start) * 1000

            # 응답 본문 파싱
            resp_json = {}
            try:
                resp_json = resp.json()
            except Exception:
                pass

            error_detail = resp_json.get("error", {})
            if isinstance(error_detail, dict):
                error_detail = error_detail.get("message", resp.text)
            elif not isinstance(error_detail, str):
                error_detail = resp.text

            if resp.status_code == 200:
                usage = resp_json.get("usage", {})
                completion_tokens = usage.get("completion_tokens", 0)
                content = (
                    resp_json.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                tokens = len(content.split()) if content else completion_tokens
                tokens_sec = (
                    completion_tokens / (duration / 1000)
                    if duration > 0 and completion_tokens > 0
                    else 0
                )

                return {
                    "model": model_id,
                    "status": "✅",
                    "response_time": round(duration, 2),
                    "tokens_per_sec": round(tokens_sec, 2),
                    "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error": "",
                }

            elif resp.status_code == 429:
                # Rate limit — Retry-After 헤더 활용
                retry_after = int(resp.headers.get("Retry-After", 5))
                if attempt < max_retries:
                    time.sleep(retry_after)
                    continue
                return {
                    "model": model_id,
                    "status": "❌",
                    "response_time": 0,
                    "tokens_per_sec": 0,
                    "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error": f"Rate limited (429): retry after {retry_after}s",
                }

            elif resp.status_code == 503 and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue

            else:
                return {
                    "model": model_id,
                    "status": "❌",
                    "response_time": 0,
                    "tokens_per_sec": 0,
                    "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error": f"HTTP {resp.status_code}: {error_detail}",
                }

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {
                "model": model_id,
                "status": "❌",
                "response_time": 0,
                "tokens_per_sec": 0,
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": "Timeout (10s)",
            }

        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {
                "model": model_id,
                "status": "❌",
                "response_time": 0,
                "tokens_per_sec": 0,
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e),
            }

    # 모든 재시도 실패
    return {
        "model": model_id,
        "status": "❌",
        "response_time": 0,
        "tokens_per_sec": 0,
        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": f"Failed after {max_retries + 1} attempts",
    }
