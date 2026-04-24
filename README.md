# 🚀 NVIDIA NIM 모델 대시보드

> NVIDIA NIM (NVIDIA Inference Microservices) 에서 제공하는 모든 모델의 **실시간 상태**, **응답 속도**, **가용성**을 한눈에 확인하는 전문 대시보드입니다.

![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green.svg)
![Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 📋 주요 기능

- **🔍 실시간 모델 상태 체크**: NVIDIA NIM API 를 통해 현재 제공되는 **모든 모델**의 가용성을 즉시 확인합니다.
- **⚡ 성능 측정**: 각 모델의 **평균 응답 시간 (ms)**과 **토큰 처리 속도 (Tokens/sec)**를 정밀하게 측정합니다.
- **🔄 동적 모델 목록**: 고정된 목록이 아닌, API 를 통해 **실시간으로 최신 모델 목록**을 가져옵니다. (새 모델 추가/제거 자동 반영)
- **📊 고급 필터링 & 정렬**:
  - **필터**: 성공/실패 모델만 필터링
  - **정렬**: 응답 시간 (빠른순), 토큰/초 (빠른순), 모델 이름, 상태별 정렬
- **🔑 안전한 API 키 관리**: 브라우저 `localStorage` 기반의 안전한 키 저장 (서버 전송 없음).
- **📱 모바일 최적화**: 반응형 디자인으로 PC 와 모바일 어디서든 편리하게 사용 가능합니다.
- **🎨 깔끔한 UI**: 불필요한 애니메이션 없이 **데이터 중심의 전문적인 디자인**을 지향합니다.

---

## 🖥️ 데모

실시간 데모는 다음 URL 에서 확인하실 수 있습니다:
👉 **[https://nim-model-dashboard.vercel.app](https://nim-model-dashboard.vercel.app)**

---

## 🛠️ 기술 스택

- **Backend**: FastAPI (Python 3.12), httpx (비동기 HTTP 클라이언트)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (프레임워크 없음)
- **Deployment**: Vercel (Serverless Functions)
- **API**: NVIDIA NIM API (build.nvidia.com)

---

## 📦 설치 및 실행 (로컬)

로컬 환경에서 개발 및 테스트하려면 다음 단계를 따르세요:

### 1. 저장소 클론
```bash
git clone https://github.com/sigco3111/nim-model-dashboard.git
cd nim-model-dashboard
```

### 2. 가상 환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

### 5. 브라우저 접속
```
http://localhost:8000
```

---

## 📖 사용 방법

1. **API 키 입력**:
   - 사이트 상단의 입력창에 **NVIDIA NIM API 키**를 입력합니다.
   - [NVIDIA NIM](https://build.nvidia.com/explore/discover) 에서 무료 키를 발급받으실 수 있습니다.
   - **저장** 버튼을 클릭하여 키를 브라우저에 저장합니다.

2. **모델 체크 시작**:
   - **"모델 상태 체크 시작"** 버튼을 클릭합니다.
   - 시스템이 자동으로 최신 모델 목록을 조회하고, 각 모델에 대해 짧은 헬스체크 요청을 보냅니다.
   - 진행 상황에 따라 결과가 실시간으로 표시됩니다.

3. **결과 분석**:
   - **테이블**: 모델명, 상태 (✅/❌), 응답 시간, 토큰/초, 오류 메시지 확인
   - **필터/정렬**: 상단 드롭다운을 이용해 원하는 데이터만 필터링하거나 정렬합니다.
   - **메트릭스**: 전체 모델 수, 성공/실패 개수, 평균 응답 시간 요약

---

## ⚠️ 주의사항

- **API Rate Limit**: NVIDIA NIM 무료 티어는 분당 요청 수 제한이 있을 수 있습니다. 대시보드는 동시성 3 개로 제한하여 안정성을 높였습니다.
- **체크 시간**: 모델 수가 200 개 이상일 경우, 모든 모델을 체크하는 데 **10~30 분**이 소요될 수 있습니다.
- **서버리스 환경**: Vercel 배포 시, 서버리스 함수의 타임아웃 제한 (약 60 초) 으로 인해 대용량 체크 시 일부 모델이 타임아웃될 수 있습니다. 로컬 실행 시에는 이 제한이 없습니다.
- **보안**: API 키는 사용자의 브라우저 `localStorage`에만 저장되며, 서버 (Vercel) 나 제 3 에 전송되지 않습니다.

---

## 🤝 기여하기

이 프로젝트에 기여하고 싶으시다면, Pull Request 를 보내주시거나 이슈를 등록해 주세요!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 라이선스

이 프로젝트는 **MIT License** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 📞 연락처

- **개발자**: sigco3111
- **GitHub**: [https://github.com/sigco3111](https://github.com/sigco3111)
- **프로젝트**: [https://github.com/sigco3111/nim-model-dashboard](https://github.com/sigco3111/nim-model-dashboard)

---

**NVIDIA NIM 모델 대시보드**를 이용해 주셔서 감사합니다! 🎉
