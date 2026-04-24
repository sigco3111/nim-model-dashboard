import os
import sys
import subprocess
import threading
import time

# Streamlit 서버 실행 함수
def run_streamlit():
    # Streamlit 서버를 백그라운드에서 실행
    # Vercel 환경에서는 포트 8080 을 사용해야 함
    port = int(os.environ.get("PORT", 8080))
    
    # Streamlit 실행 명령어
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ]
    
    # 프로세스 실행
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 로그 출력 (디버깅용)
    def log_output(pipe):
        for line in iter(pipe.readline, b''):
            print(line.decode(), end='')
    
    threading.Thread(target=log_output, args=(process.stdout,), daemon=True).start()
    threading.Thread(target=log_output, args=(process.stderr,), daemon=True).start()
    
    # 프로세스 대기 (정지될 때까지)
    process.wait()

if __name__ == "__main__":
    run_streamlit()
