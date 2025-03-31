import os
import app
# 이 파일은 Streamlit Cloud에서 인식하는 메인 진입점 역할을 합니다.
# app.py가 모든 로직을 담고 있고, 이 파일은 그것을 임포트하여 실행합니다. 

# 데이터 디렉토리 설정 (앱 실행 전에 필요)
current_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(current_dir, "data")
os.makedirs(data_dir, exist_ok=True)
os.makedirs(os.path.join(data_dir, "user_data"), exist_ok=True)

# 환경 변수 설정
os.environ["DATA_DIR"] = data_dir 