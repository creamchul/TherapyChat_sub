import streamlit as st
import yaml
from yaml.loader import SafeLoader
import os
import pickle
from pathlib import Path
import hashlib
import uuid
import datetime

# 절대 경로 설정
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))
CONFIG_PATH = os.path.join(DATA_DIR, "config.yaml")
USER_DATA_DIR = os.path.join(DATA_DIR, "user_data")

# 데이터 디렉토리 생성
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)

# 비밀번호 해싱 함수
def hash_password(password):
    """비밀번호를 안전하게 해싱합니다."""
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

def check_password(hashed_password, user_password):
    """해시된 비밀번호와 사용자 입력 비밀번호를 비교합니다."""
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()

# 사용자 인증 설정
def setup_auth():
    # 설정 파일이 없는 경우 생성
    config_file = Path(CONFIG_PATH)
    if not config_file.exists():
        # 기본 사용자 생성
        credentials = {
            'usernames': {
                'guest': {
                    'name': '게스트',
                    'password': hash_password('guest'),
                    'email': 'guest@example.com'
                }
            }
        }
        config = {
            'credentials': credentials,
            'cookie': {
                'expiry_days': 30
            }
        }
        with open(config_file, 'w') as file:
            yaml.dump(config, file, default_flow_style=False)

    # 설정 파일 로드
    with open(config_file) as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    # 인증 클래스 대신 딕셔너리 반환
    return config['credentials']

# 로그인 함수
def login(credentials, username, password):
    """사용자 로그인을 처리합니다."""
    if username in credentials['usernames']:
        if check_password(credentials['usernames'][username]['password'], password):
            return True, credentials['usernames'][username]['name']
    return False, None

# 로그아웃 함수
def logout():
    """사용자 로그아웃을 처리합니다."""
    for key in list(st.session_state.keys()):
        if key in ['active_tab']:  # 유지할 세션 상태
            continue
        del st.session_state[key]

# 사용자 등록 UI 함수
def register_user(credentials):
    st.title("회원가입")
    
    with st.form("register_form"):
        username = st.text_input("사용자 이름 *", help="로그인에 사용될 ID입니다")
        name = st.text_input("이름 *", help="서비스 내에서 표시될 이름입니다")
        email = st.text_input("이메일", help="선택 사항입니다")
        password = st.text_input("비밀번호 *", type="password")
        password_confirm = st.text_input("비밀번호 확인 *", type="password")
        
        # 버튼을 중앙에 배치하고 primary 유형으로 변경
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submit_button = st.form_submit_button("회원가입", type="primary", use_container_width=True)
        
        if submit_button:
            # 입력 검증
            if not username or not name or not password:
                st.error("필수 항목을 모두 입력해주세요.")
                return
                
            if password != password_confirm:
                st.error("비밀번호가 일치하지 않습니다.")
                return
                
            # 설정 파일 로드
            config_file = Path(CONFIG_PATH)
            try:
                # 사용자 이름 중복 확인
                if username in credentials['usernames']:
                    st.error("이미 존재하는 사용자 이름입니다.")
                    return
                    
                # 새 사용자 추가
                hashed_password = hash_password(password)
                credentials['usernames'][username] = {
                    'name': name,
                    'password': hashed_password,
                    'email': email
                }
                
                # 설정 파일 저장
                with open(config_file, 'w') as file:
                    config = {
                        'credentials': credentials,
                        'cookie': {
                            'expiry_days': 30
                        }
                    }
                    yaml.dump(config, file, default_flow_style=False)
                    
                # 사용자 데이터 초기화 및 저장
                if create_new_user(username, name, email, hashed_password):
                    st.success("계정이 생성되었습니다. 로그인해 주세요.")
                    
                    # 세션 상태 업데이트
                    st.session_state.active_tab = "로그인"
                    st.rerun()
                else:
                    st.error("사용자 데이터 생성 중 오류가 발생했습니다.")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# 사용자 생성 백엔드 함수
def create_new_user(username, name, email, password_hash):
    """새 사용자 데이터를 생성하는 함수"""
    try:
        # 사용자 데이터 로드
        user_data = load_user_data(username)
        
        # 사용자 이름 중복 확인
        if username in user_data:
            return False
        
        # 새 사용자 정보 저장
        user_data[username] = {
            "name": name,
            "email": email,
            "password": password_hash,
            "chat_sessions": [],
            "profile": {
                "nickname": name,
                "image": "",
                "bio": "",
                "theme": "light"
            },
            "emotion_goals": {
                "active_goal": None,
                "history": []
            }
        }
        
        # 저장
        save_user_data(username, user_data)
        
        return True
    except Exception as e:
        print(f"사용자 생성 오류: {e}")
        return False

# 사용자 데이터 관리
def save_user_data(username, data):
    """사용자 데이터를 저장합니다."""
    user_data_path = os.path.join(USER_DATA_DIR, f"{username}.pkl")
    with open(user_data_path, "wb") as f:
        pickle.dump(data, f)

def load_user_data(username):
    """사용자 데이터를 로드합니다."""
    user_data_path = os.path.join(USER_DATA_DIR, f"{username}.pkl")
    try:
        with open(user_data_path, "rb") as f:
            data = pickle.load(f)
            
            # 이전 버전 데이터 구조 마이그레이션
            if 'chat_sessions' not in data:
                data['chat_sessions'] = []
                
                # 기존 채팅 기록이 있으면 새 형식으로 변환
                if 'chat_history' in data and data['chat_history']:
                    timestamp = datetime.datetime.now().isoformat()
                    chat_id = f"chat_legacy_{timestamp}"
                    
                    emotion = None
                    if 'emotions' in data and data['emotions']:
                        emotion = data['emotions'][-1]
                        
                    chat_preview = data['chat_history'][0]['content'] if data['chat_history'] else "이전 대화"
                    
                    # 레거시 채팅 세션 생성
                    chat_session = {
                        "id": chat_id,
                        "date": timestamp,
                        "emotion": emotion,
                        "preview": chat_preview,
                        "messages": data['chat_history']
                    }
                    
                    data['chat_sessions'].append(chat_session)
            
            return data
    except FileNotFoundError:
        # 새 사용자 데이터 초기화
        initial_data = {"chat_history": [], "emotions": [], "chat_sessions": []}
        save_user_data(username, initial_data)
        return initial_data 