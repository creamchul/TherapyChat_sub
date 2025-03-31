import streamlit as st
import os
import datetime
import time
import pandas as pd
from dotenv import load_dotenv
from auth import setup_auth, register_user, save_user_data, load_user_data, login, logout, hash_password, CONFIG_PATH
from chatbot import EMOTIONS, initialize_chat_history, display_chat_history, add_message, get_ai_response, start_new_chat, analyze_emotion, get_system_prompt
from pathlib import Path
import yaml
import numpy as np
from collections import Counter
import pytz

# 환경 변수 로드
load_dotenv()

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 페이지 설정
st.set_page_config(
    page_title="감정 치유 AI 챗봇",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 감정 아이콘 매핑
EMOTION_ICONS = {
    "기쁨": "😊",
    "슬픔": "😢",
    "분노": "😠",
    "불안": "😰",
    "스트레스": "😫",
    "외로움": "😔",
    "후회": "😞",
    "좌절": "😩",
    "혼란": "😕",
    "감사": "🙏"
}

# 감정 목표 업데이트 함수
def update_emotion_goal(emotion):
    """
    감정에 따라 사용자의 감정 목표 진행도를 업데이트하는 함수
    """
    if not st.session_state.logged_in:
        return
    
    username = st.session_state.username
    user_data = st.session_state.user_data
    
    # 활성화된 감정 목표 확인
    emotion_goals = user_data.get("emotion_goals", {"active_goal": None, "history": []})
    active_goal = emotion_goals.get("active_goal", None)
    
    if not active_goal:
        return
    
    # 목표 감정과 현재 감정 비교
    target_emotion = active_goal.get("target_emotion")
    if emotion == target_emotion:
        # 목표 감정과 일치하는 경우 진행도 증가
        progress = active_goal.get("progress", 0)
        # 5% 증가, 최대 100%
        progress = min(progress + 5, 100)
        active_goal["progress"] = progress
        
        # 성과 기록
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        active_goal.setdefault("achievements", []).append({
            "date": today,
            "description": f"목표 감정 '{target_emotion}'을(를) 경험했습니다."
        })
        
        # 목표 달성 시 자동 완료
        if progress >= 100:
            active_goal["completed"] = True
            active_goal["completion_date"] = today
            emotion_goals["history"].append(active_goal)
            emotion_goals["active_goal"] = None
    
    # 사용자 데이터 업데이트
    user_data["emotion_goals"] = emotion_goals
    st.session_state.user_data = user_data
    
    # 데이터 저장
    save_user_data(username, user_data)

# 감정 선택 저장 처리
def handle_emotion_selection(emotion):
    """
    선택된 감정 처리 및 저장 함수
    """
    # 감정 설정
    st.session_state.selected_emotion = emotion
    
    # 현재 채팅 세션에 감정 저장
    if 'chat_id' not in st.session_state:
        timestamp = datetime.datetime.now().isoformat()
        st.session_state.chat_id = f"chat_{timestamp}"
    
    chat_id = st.session_state.chat_id
    
    # 채팅 세션 업데이트
    if 'user_data' in st.session_state and 'chat_sessions' in st.session_state.user_data:
        chat_sessions = st.session_state.user_data['chat_sessions']
        found = False
        for i, chat in enumerate(chat_sessions):
            if chat['id'] == chat_id:
                chat['emotion'] = emotion
                found = True
                break
                
        if not found:
            # 새 채팅 세션 생성
            chat_sessions.append({
                "id": chat_id,
                "date": datetime.datetime.now().isoformat(),
                "emotion": emotion,
                "preview": "새로운 대화",
                "messages": []
            })
        
        # 채팅 기록 업데이트
        st.session_state.user_data['chat_sessions'] = chat_sessions
        
        # 사용자 데이터 저장
        save_user_data(st.session_state.username, st.session_state.user_data)
        
        # 감정 목표 업데이트
        update_emotion_goal(emotion)
    
    # 새 채팅 시작
    st.session_state.chat_started = True
    start_new_chat(emotion)
    
    # 화면 갱신
    st.rerun()

# DataFrames를 페이지네이션과 함께 표시하는 함수
def display_dataframe_with_pagination(df, page_size=10, key="pagination"):
    """
    DataFrame을 페이지네이션과 함께 표시하는 함수
    """
    # 세션 상태 초기화
    if f'{key}_page' not in st.session_state:
        st.session_state[f'{key}_page'] = 0
    
    # 전체 페이지 수 계산
    total_pages = max(len(df) // page_size, 1)
    
    # 현재 페이지 데이터 가져오기
    start_idx = st.session_state[f'{key}_page'] * page_size
    end_idx = min(start_idx + page_size, len(df))
    page_df = df.iloc[start_idx:end_idx]
    
    # 하단 컨트롤
    cols = st.columns([1, 3, 1])
    
    # 이전 페이지 버튼
    with cols[0]:
        if st.button("← 이전", key=f"{key}_prev", disabled=st.session_state[f'{key}_page'] == 0):
            st.session_state[f'{key}_page'] = max(0, st.session_state[f'{key}_page'] - 1)
            st.rerun()
    
    # 페이지 정보
    with cols[1]:
        st.markdown(f"**{st.session_state[f'{key}_page'] + 1}/{total_pages} 페이지** (총 {len(df)}개)")
    
    # 다음 페이지 버튼
    with cols[2]:
        if st.button("다음 →", key=f"{key}_next", disabled=st.session_state[f'{key}_page'] >= total_pages - 1):
            st.session_state[f'{key}_page'] = min(total_pages - 1, st.session_state[f'{key}_page'] + 1)
            st.rerun()
    
    # 현재 페이지 데이터 표시
    st.dataframe(page_df, use_container_width=True)

# CSS 스타일 적용
st.markdown("""
<style>
    /* 기본 스타일 */
    :root {
        --primary-color: #4f8bf9;
        --background-color: #f9f9f9;
        --card-background: white;
        --text-color: #333;
        --secondary-text-color: #666;
        --border-color: #e0e0e0;
        --hover-color: #f9f9ff;
        --button-color: #6a89cc;
        --button-hover: #5679c1;
        --warning-color: #f44336;
        --success-color: #4CAF50;
    }
    
    /* 다크 모드 */
    @media (prefers-color-scheme: dark) {
        :root {
            --primary-color: #6a89cc;
            --background-color: #1e1e1e;
            --card-background: #2d2d2d;
            --text-color: #f0f0f0;
            --secondary-text-color: #aaaaaa;
            --border-color: #444444;
            --hover-color: #3d3d3d;
            --button-color: #5679c1;
            --button-hover: #4a6cb3;
            --warning-color: #ff5252;
            --success-color: #81c784;
        }
        
        .st-emotion-cache-zt5igj {
            color: var(--text-color) !important;
        }
        
        .stTextInput input, .stSelectbox, .stDateInput input, .stTextArea textarea {
            background-color: var(--card-background) !important;
            color: var(--text-color) !important;
            border-color: var(--border-color) !important;
        }
        
        .stDataFrame {
            background-color: var(--card-background) !important;
        }
        
        .stDataFrame th {
            background-color: var(--primary-color) !important;
            color: white !important;
        }
        
        .stDataFrame td {
            color: var(--text-color) !important;
        }
        
        .chat-card {
            background-color: var(--card-background) !important;
            color: var(--text-color) !important;
            border-color: var(--border-color) !important;
        }
        
        .chat-card:hover {
            background-color: var(--hover-color) !important;
        }
    }
    
    /* 반응형 디자인 */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem !important;
        }
        
        .sub-header {
            font-size: 1.2rem !important;
        }
        
        .emotion-button {
            padding: 8px !important;
            margin: 3px !important;
            font-size: 0.9rem !important;
        }
        
        .chat-container {
            height: 350px !important;
            padding: 15px !important;
        }
        
        .chat-card {
            padding: 10px !important;
            margin-bottom: 10px !important;
        }
        
        /* 모바일에서 테이블 스크롤 가능하게 */
        .dataframe-container {
            overflow-x: auto !important;
            width: 100% !important;
        }
    }
    
    /* 공통 스타일 */
    body {
        color: var(--text-color);
        background-color: var(--background-color);
    }
    
    .main-header {
        font-size: 2.5rem;
        color: var(--primary-color);
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .sub-header {
        font-size: 1.5rem;
        color: var(--primary-color);
        margin-bottom: 1rem;
    }
    
    /* 테이블 스타일 개선 */
    .dataframe-container {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    
    .table-controls {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    
    .table-search {
        flex: 1;
        max-width: 300px;
        margin-right: 10px;
    }
    
    .table-page-controls {
        display: flex;
        align-items: center;
    }
    
    .table-page-controls button {
        margin: 0 5px;
        min-width: 30px;
    }
    
    .sortable-header {
        cursor: pointer;
        position: relative;
    }
    
    .sortable-header:hover {
        background-color: rgba(0,0,0,0.05);
    }
    
    .sortable-header::after {
        content: "↕";
        position: absolute;
        right: 8px;
        opacity: 0.5;
    }
    
    .sort-asc::after {
        content: "↑";
        opacity: 1;
    }
    
    .sort-desc::after {
        content: "↓";
        opacity: 1;
    }
    
    /* 다크/라이트 모드 전환 버튼 */
    .theme-toggle {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background-color: var(--card-background);
        color: var(--text-color);
        border: 1px solid var(--border-color);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    /* 기존 스타일 유지 및 변수로 변경 */
    .emotion-button {
        background-color: var(--background-color);
        border-radius: 10px;
        padding: 10px;
        margin: 5px;
        text-align: center;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    
    .emotion-button:hover {
        background-color: var(--hover-color);
    }
    
    .emotion-selected {
        background-color: var(--button-color);
        color: white;
        font-weight: bold;
    }
    
    .chat-container {
        border-radius: 10px;
        padding: 20px;
        background-color: var(--background-color);
        height: 400px;
        overflow-y: auto;
    }
    
    .stTextInput > div > div > input {
        border-radius: 20px;
    }
    
    .emoji {
        font-size: 1.2rem;
        margin-right: 8px;
    }
    
    .chat-card {
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: var(--card-background);
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
        position: relative;
        z-index: 1;
        cursor: pointer;
    }
    
    .chat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        background-color: var(--hover-color);
        border-color: var(--button-color);
    }
    
    .chat-card:after {
        content: "›";
        position: absolute;
        right: 15px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 24px;
        color: var(--button-color);
        opacity: 0;
        transition: opacity 0.2s;
    }
    
    .chat-card:hover:after {
        opacity: 1;
    }
    
    /* Streamlit 버튼 스타일링 - 보이지 않지만 클릭 가능하게 */
    div.chat-history-card div.stButton {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 2;
    }
    
    div.chat-history-card div.stButton > button {
        position: absolute;
        top: 0;
        left: 0;
        width: 100% !important;
        height: 100% !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: transparent !important;
        opacity: 0 !important;
    }
    
    .chat-card-header {
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 10px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
    }
    
    .chat-card-emotion {
        font-weight: bold;
        color: var(--primary-color);
    }
    
    .chat-card-date {
        color: var(--secondary-text-color);
        font-size: 0.9rem;
    }
    
    .chat-card-preview {
        color: var(--text-color);
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }
    
    .filter-section {
        background-color: var(--background-color);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        border: 1px solid var(--border-color);
    }
    
    .filter-title {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 10px;
        color: var(--primary-color);
    }
    
    .filter-item {
        margin-bottom: 5px;
    }
    
    .action-button {
        border-radius: 20px;
        padding: 10px 15px;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .icon-button {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        font-size: 1.2rem;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    
    .view-button {
        background-color: var(--background-color);
        color: var(--primary-color);
    }
    
    .view-button:hover {
        background-color: var(--hover-color);
    }
    
    .delete-button {
        background-color: #ffebee;
        color: var(--warning-color);
    }
    
    .delete-button:hover {
        background-color: #ffcdd2;
    }
    
    .pagination-button {
        margin: 0 4px;
        padding: 6px 12px;
        border-radius: 4px;
        background-color: var(--background-color);
        color: var(--text-color);
        border: 1px solid var(--border-color);
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .pagination-button:hover {
        background-color: var(--hover-color);
    }
    
    .pagination-active {
        background-color: var(--primary-color);
        color: white;
        border-color: var(--primary-color);
    }
    
    .filter-badge {
        display: inline-block;
        padding: 4px 8px;
        margin: 2px;
        border-radius: 4px;
        background-color: var(--button-color);
        color: white;
        font-size: 0.8rem;
    }
    
    /* 로그인/회원가입 버튼 스타일 */
    .login-button, .auth-container button {
        display: block;
        width: 100%;
        background-color: var(--button-color);
        color: white;
        padding: 8px 15px;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        font-weight: 500;
        margin: 8px 0;
        text-align: center;
        opacity: 1;
        position: relative;
    }
    
    .login-button:hover, .auth-container button:hover {
        background-color: var(--button-hover);
    }
    
    /* 다크 모드 토글을 위한 스크립트 */
    .dark-mode-toggle {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 9999;
        background-color: var(--card-background);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        border: 1px solid var(--border-color);
        transition: all 0.3s ease;
    }
</style>

<script>
    // 다크 모드 토글 함수
    function toggleDarkMode() {
        const body = document.body;
        if (body.classList.contains('dark-mode')) {
            body.classList.remove('dark-mode');
            localStorage.setItem('theme', 'light');
            document.getElementById('darkModeToggle').innerHTML = '🌙';
        } else {
            body.classList.add('dark-mode');
            localStorage.setItem('theme', 'dark');
            document.getElementById('darkModeToggle').innerHTML = '☀️';
        }
    }
    
    // 페이지 로드 시 적용
    document.addEventListener('DOMContentLoaded', function() {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme === 'dark' || (savedTheme === null && prefersDark)) {
            document.body.classList.add('dark-mode');
            document.getElementById('darkModeToggle').innerHTML = '☀️';
        } else {
            document.getElementById('darkModeToggle').innerHTML = '🌙';
        }
        
        // 다크 모드 토글 버튼 클릭 이벤트
        document.getElementById('darkModeToggle').addEventListener('click', toggleDarkMode);
    });
</script>

<!-- 다크 모드 토글 버튼 -->
<div id="darkModeToggle" class="dark-mode-toggle">🌙</div>
""", unsafe_allow_html=True)

# 인증 정보 설정
credentials = setup_auth()

# 감정 아이콘 매핑
EMOTION_ICONS = {
    "기쁨": "😊",
    "슬픔": "😢",
    "분노": "😠",
    "불안": "😰",
    "스트레스": "😫",
    "외로움": "😔",
    "후회": "😞",
    "좌절": "😩",
    "혼란": "😕",
    "감사": "🙏"
}

# 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'selected_emotion' not in st.session_state:
    st.session_state.selected_emotion = None
if 'chat_started' not in st.session_state:
    st.session_state.chat_started = False
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "로그인"
if 'active_page' not in st.session_state:
    st.session_state.active_page = "chat"
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.getenv("OPENAI_API_KEY", "")
if 'selected_chat_id' not in st.session_state:
    st.session_state.selected_chat_id = None

# 현재 채팅 저장 함수
def save_current_chat():
    if 'messages' in st.session_state and len(st.session_state.messages) > 1:
        chat_messages = [msg for msg in st.session_state.messages if msg["role"] != "system"]
        if not chat_messages:
            return False
            
        # 사용자가 입력한 메시지가 있는지 확인 (어시스턴트의 인사말만 있는 경우는 제외)
        has_user_message = False
        for msg in chat_messages:
            if msg["role"] == "user":
                has_user_message = True
                break
                
        # 사용자 메시지가 없으면 저장하지 않음
        if not has_user_message:
            return False
            
        # 감정 값이 없으면 저장하지 않음
        if not st.session_state.selected_emotion:
            return False
            
        # 기존 채팅 세션 리스트 확인
        if 'chat_sessions' not in st.session_state.user_data:
            st.session_state.user_data['chat_sessions'] = []
            
        # 현재 채팅의 ID 확인 또는 생성
        if 'current_chat_id' not in st.session_state:
            # 채팅 세션 정보 생성
            timestamp = datetime.datetime.now().isoformat()
            st.session_state.current_chat_id = f"chat_{timestamp}"
            
        chat_id = st.session_state.current_chat_id
        
        # 미리보기 텍스트로 사용자 메시지 사용 (없으면 어시스턴트 메시지)
        chat_preview = "새로운 대화"
        for msg in chat_messages:
            if msg["role"] == "user":
                chat_preview = msg["content"]
                break
                
        # 채팅 세션 정보 구성
        chat_session = {
            "id": chat_id,
            "date": datetime.datetime.now().isoformat(),  # 마지막 수정 시간으로 업데이트
            "emotion": st.session_state.selected_emotion,
            "preview": chat_preview,
            "messages": chat_messages
        }
        
        # 기존 채팅이 있는지 확인하고 업데이트하거나 새로 추가
        existing_chat_index = None
        for i, chat in enumerate(st.session_state.user_data['chat_sessions']):
            if chat['id'] == chat_id:
                existing_chat_index = i
                break
                
        if existing_chat_index is not None:
            # 기존 채팅 업데이트
            st.session_state.user_data['chat_sessions'][existing_chat_index] = chat_session
        else:
            # 새 채팅 추가
            st.session_state.user_data['chat_sessions'].append(chat_session)
        
        # 사용자 데이터 저장
        save_user_data(st.session_state.username, st.session_state.user_data)
        return True
    return False

# 자동 저장 함수
def auto_save():
    if (st.session_state.logged_in and 
        'user_data' in st.session_state and 
        'username' in st.session_state and
        'selected_emotion' in st.session_state and 
        st.session_state.selected_emotion):
        if 'messages' in st.session_state and len(st.session_state.messages) > 1:
            save_current_chat()

# 마지막 저장 시간 추적
if 'last_save_time' not in st.session_state:
    st.session_state.last_save_time = time.time()

# 주기적으로 저장 (5분마다)
current_time = time.time()
if (current_time - st.session_state.last_save_time > 300 and  # 300초 = 5분
    st.session_state.get('logged_in', False) and
    st.session_state.get('selected_emotion')):
    auto_save()
    st.session_state.last_save_time = current_time

# 사이드바 - 로그인/로그아웃
with st.sidebar:
    st.markdown("<h2 class='sub-header'>사용자 인증</h2>", unsafe_allow_html=True)
    
    # API 키 설정
    if st.session_state.logged_in:
        with st.expander("OpenAI API 키 설정"):
            api_key = st.text_input("OpenAI API 키", 
                                    value=st.session_state.api_key,
                                    type="password",
                                    key="api_key_input")
            if st.button("저장", key="save_api_key"):
                st.session_state.api_key = api_key
                os.environ["OPENAI_API_KEY"] = api_key
                st.success("API 키가 저장되었습니다!")
    
    if not st.session_state.logged_in:
        # 탭 선택
        tab_options = ["로그인", "회원가입"]
        selected_tab = st.radio("", tab_options, index=tab_options.index(st.session_state.active_tab))
        st.session_state.active_tab = selected_tab
        
        if selected_tab == "로그인":
            st.subheader("로그인")
            try:
                # 로그인 폼
                username = st.text_input("사용자 이름", key="login_username")
                password = st.text_input("비밀번호", type="password", key="login_password")
                
                # 로그인 버튼
                login_button = st.button("로그인", type="primary", key="login_btn", use_container_width=True)
                
                if login_button:
                    success, name = login(credentials, username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.success(f"환영합니다, {name}님!")
                        
                        # 사용자 데이터 로드
                        st.session_state.user_data = load_user_data(username)
                        
                        # 현재 채팅 ID 초기화
                        if 'current_chat_id' in st.session_state:
                            del st.session_state.current_chat_id
                        
                        # 채팅 초기화
                        initialize_chat_history()
                        st.rerun()
                    else:
                        st.error("사용자 이름 또는 비밀번호가 잘못되었습니다.")
            except Exception as e:
                st.error(f"로그인 중 오류가 발생했습니다: {e}")

            # 회원가입으로 이동 버튼
            st.markdown("---")
            if st.button("계정이 없으신가요? 회원가입", type="secondary", key="goto_signup", use_container_width=True):
                st.session_state.active_tab = "회원가입"
                st.rerun()
        elif selected_tab == "회원가입":
            st.subheader("회원가입")
            try:
                # 회원가입 폼
                username = st.text_input("사용자 이름", key="signup_username")
                name = st.text_input("이름", key="signup_name")
                email = st.text_input("이메일", key="signup_email")
                password = st.text_input("비밀번호", type="password", key="signup_password")
                password_confirm = st.text_input("비밀번호 확인", type="password", key="signup_password_confirm")
                
                # 회원가입 버튼
                signup_button = st.button("회원가입", type="primary", key="signup_btn", use_container_width=True)
                
                if signup_button:
                    # 입력 검증
                    if not username or not name or not password:
                        st.error("필수 항목을 모두 입력해주세요.")
                    elif password != password_confirm:
                        st.error("비밀번호가 일치하지 않습니다.")
                    elif username in credentials['usernames']:
                        st.error("이미 존재하는 사용자 이름입니다.")
                    else:
                        # 새 사용자 추가
                        try:
                            # 설정 파일 로드
                            config_file = Path(CONFIG_PATH)
                            
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
                                
                            # 사용자 데이터 파일 초기화
                            initial_data = {"chat_history": [], "emotions": [], "chat_sessions": []}
                            save_user_data(username, initial_data)
                            
                            st.success("계정이 생성되었습니다. 로그인해 주세요.")
                            
                            # 세션 상태 업데이트
                            st.session_state.active_tab = "로그인"
                            st.rerun()
                        except Exception as e:
                            st.error(f"회원가입 중 오류가 발생했습니다: {e}")
            except Exception as e:
                st.error(f"회원가입 중 오류가 발생했습니다: {e}")
            
            # 로그인으로 이동 버튼
            st.markdown("---")
            if st.button("이미 계정이 있으신가요? 로그인", type="secondary", key="goto_login", use_container_width=True):
                st.session_state.active_tab = "로그인"
                st.rerun()
    else:
        st.subheader(f"사용자: {st.session_state.username}")
        
        # 네비게이션 메뉴
        st.markdown("### 메뉴")
        if st.button("💬 채팅", key="nav_chat", use_container_width=True):
            st.session_state.active_page = "chat"
            st.session_state.selected_chat_id = None
            st.rerun()
            
        if st.button("📋 채팅 기록", key="nav_history", use_container_width=True):
            # 현재 채팅 저장 (감정 값이 있는 경우에만)
            if st.session_state.selected_emotion:
                auto_save()
            st.session_state.active_page = "history"
            st.rerun()
            
        if st.button("📊 감정 분석", key="nav_analysis", use_container_width=True):
            # 현재 채팅 저장 (감정 값이 있는 경우에만)
            if st.session_state.selected_emotion:
                auto_save()
            st.session_state.active_page = "analysis"
            st.rerun()
            
        st.markdown("---")
        if st.button("로그아웃", key="logout_button"):
            # 사용자 데이터 저장
            if 'messages' in st.session_state:
                if 'user_data' not in st.session_state:
                    st.session_state.user_data = {"chat_history": [], "chat_sessions": []}
                
                # 활성화된 채팅이 있으면 저장 (selected_emotion이 있을 때만)
                if 'messages' in st.session_state and len(st.session_state.messages) > 1 and st.session_state.selected_emotion:
                    save_current_chat()
                
                save_user_data(st.session_state.username, st.session_state.user_data)
            
            # 로그아웃 처리
            try:
                logout()
                st.session_state.active_tab = "로그인"
                st.rerun()
            except Exception as e:
                st.error(f"로그아웃 중 오류가 발생했습니다: {e}")

# 메인 컨텐츠
st.markdown("<h1 class='main-header'>감정 치유 AI 챗봇</h1>", unsafe_allow_html=True)

if not st.session_state.logged_in:
    # 로그인하지 않았을 때는 간단한 안내 메시지만 표시
    st.info("왼쪽 사이드바에서 로그인해주세요.")
else:
    # 선택된 페이지에 따라 다른 내용 표시
    if st.session_state.active_page == "chat":
        st.markdown("<h2 class='sub-header'>AI 챗봇과 대화하기</h2>", unsafe_allow_html=True)
        
        # 프로필 정보 가져오기 (로그인 한 경우)
        if st.session_state.logged_in:
            user_data = st.session_state.user_data
            profile = user_data.get("profile", {})
            
            # 활성화된 감정 목표 확인
            emotion_goals = user_data.get("emotion_goals", {"active_goal": None, "history": []})
            active_goal = emotion_goals.get("active_goal", None)
            
            # 감정 목표가 있는 경우 표시
            if active_goal:
                with st.expander("현재 감정 목표", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"""
                        **목표 감정:** {active_goal['target_emotion']}  
                        **목표 기간:** {active_goal['start_date']} ~ {active_goal['end_date']}  
                        **설명:** {active_goal['description']}
                        """)
                    with col2:
                        # 진행도 표시
                        st.markdown(f"**진행도:** {active_goal['progress']}%")
                        st.progress(active_goal['progress'] / 100)
        
        # 감정 선택 페이지 또는 채팅 페이지 표시
        if not st.session_state.selected_emotion:
            # 감정 선택 컨테이너
            st.markdown("<div class='emotion-container'>", unsafe_allow_html=True)
            st.markdown("### 현재 감정을 선택해주세요")
            
            # 감정 버튼 배치 (4열 그리드)
            cols = st.columns(4)
            
            # 감정 목록 순회하며 버튼 배치
            for index, (emotion, value) in enumerate(EMOTIONS.items()):
                col = cols[index % 4]
                emotion_icon = EMOTION_ICONS.get(emotion, "")
                with col:
                    if st.button(f"{emotion_icon} {emotion}", key=f"emo_{emotion}", 
                               help=f"{value}",
                               use_container_width=True,
                               type="primary" if st.session_state.selected_emotion == emotion else "secondary"):
                        handle_emotion_selection(emotion)
                        
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            # 감정이 선택된 경우
            initialize_chat_history()
            display_chat_history()
            
            # 사용자 입력
            user_input = st.chat_input("메시지를 입력하세요...")
            if user_input:
                # API 키 확인
                if not st.session_state.api_key:
                    st.warning("OpenAI API 키를 입력해주세요. 왼쪽 사이드바의 'OpenAI API 키 설정'에서 설정할 수 있습니다.")
                    st.stop()
                    
                # 사용자 메시지 추가
                add_message("user", user_input)
                st.chat_message("user").write(user_input)
                
                # 채팅 기록에서 시스템 메시지를 제외한 메시지 컨텍스트 생성
                messages_for_api = [msg for msg in st.session_state.messages if msg["role"] != "assistant" or st.session_state.messages.index(msg) == 0]
                
                # API 키 설정
                os.environ["OPENAI_API_KEY"] = st.session_state.api_key
                
                # AI 응답 생성
                with st.spinner("응답 생성 중..."):
                    ai_response = get_ai_response(messages_for_api)
                
                # AI 메시지 추가
                add_message("assistant", ai_response)
                st.chat_message("assistant").write(ai_response)
                
                # 채팅 자동 저장
                save_current_chat()
            
            # 새 감정 선택 버튼
            if st.button("다른 감정 선택하기"):
                # 현재 채팅 저장 (감정 상태가 변경되기 전에 저장)
                save_current_chat()
                
                # 현재 채팅 ID 제거
                if 'current_chat_id' in st.session_state:
                    del st.session_state.current_chat_id
                
                # displayed_messages 초기화
                if 'displayed_messages' in st.session_state:
                    del st.session_state.displayed_messages
                
                # 상태 초기화 (저장 후에 초기화)
                st.session_state.selected_emotion = None
                st.session_state.chat_started = False
                
                st.rerun()
    
    elif st.session_state.active_page == "history":
        st.markdown("<h2 class='sub-header'>채팅 기록</h2>", unsafe_allow_html=True)
        
        # 채팅 기록이 없는 경우
        if 'user_data' not in st.session_state or 'chat_sessions' not in st.session_state.user_data or not st.session_state.user_data['chat_sessions']:
            st.info("저장된 채팅 기록이 없습니다.")
        else:
            # 채팅 기록이 있는 경우
            if st.session_state.selected_chat_id:
                # 선택된 채팅 세션 표시
                selected_chat = None
                selected_chat_index = None
                for i, chat in enumerate(st.session_state.user_data['chat_sessions']):
                    if chat['id'] == st.session_state.selected_chat_id:
                        selected_chat = chat
                        selected_chat_index = i
                        break
                
                if selected_chat:
                    # 뒤로가기 버튼과 삭제 버튼을 나란히 배치
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        if st.button("← 기록 목록으로 돌아가기"):
                            st.session_state.selected_chat_id = None
                            st.rerun()
                    
                    with col2:
                        # 삭제 확인 상태 확인
                        if 'confirm_delete_dialog' not in st.session_state:
                            st.session_state.confirm_delete_dialog = False
                            
                        if not st.session_state.confirm_delete_dialog:
                            if st.button("🗑️ 이 대화 삭제하기", type="primary", use_container_width=True):
                                st.session_state.confirm_delete_dialog = True
                                st.rerun()
                        else:
                            st.warning("정말 이 대화를 삭제하시겠습니까?")
                            conf_col1, conf_col2 = st.columns(2)
                            
                            with conf_col1:
                                if st.button("예, 삭제합니다", key="confirm_delete_yes"):
                                    # 선택된 채팅 삭제
                                    st.session_state.user_data['chat_sessions'].pop(selected_chat_index)
                                    save_user_data(st.session_state.username, st.session_state.user_data)
                                    st.session_state.selected_chat_id = None
                                    st.session_state.confirm_delete_dialog = False
                                    st.success("대화가 삭제되었습니다.")
                                    st.rerun()
                            
                            with conf_col2:
                                if st.button("아니오", key="confirm_delete_no"):
                                    st.session_state.confirm_delete_dialog = False
                                    st.rerun()
                    
                    # 채팅 세션 정보 표시
                    chat_date = datetime.datetime.fromisoformat(selected_chat['date']).strftime("%Y년 %m월 %d일 %H:%M")
                    emotion = selected_chat.get('emotion', '알 수 없음')
                    emotion_icon = EMOTION_ICONS.get(emotion, "")
                    
                    st.markdown(f"**날짜:** {chat_date}")
                    st.markdown(f"**감정:** {emotion_icon} {emotion}")
                    st.markdown("---")
                    
                    # 채팅 내용 표시
                    for msg in selected_chat['messages']:
                        role = msg.get('role', '')
                        content = msg.get('content', '')
                        
                        if role == 'user':
                            st.chat_message("user").write(content)
                        elif role == 'assistant':
                            st.chat_message("assistant").write(content)
                    
                    # 채팅 계속하기 버튼
                    if st.button("이 대화 계속하기"):
                        st.session_state.active_page = "chat"
                        st.session_state.selected_emotion = selected_chat.get('emotion', None)
                        st.session_state.chat_started = True
                        
                        # 기존 채팅 ID 사용
                        st.session_state.current_chat_id = selected_chat['id']
                        
                        # displayed_messages 초기화
                        if 'displayed_messages' in st.session_state:
                            del st.session_state.displayed_messages
                        
                        # 채팅 메시지 복원
                        st.session_state.messages = []
                        
                        # 시스템 메시지 추가
                        system_prompt = get_system_prompt(selected_chat.get('emotion', None))
                        st.session_state.messages.append({"role": "system", "content": system_prompt})
                        
                        # 대화 메시지 추가
                        for msg in selected_chat['messages']:
                            st.session_state.messages.append(msg)
                        
                        st.rerun()
                else:
                    st.error("선택한 채팅을 찾을 수 없습니다.")
                    st.session_state.selected_chat_id = None
            else:
                # 필터링 옵션 초기화
                if 'filter_emotion' not in st.session_state:
                    st.session_state.filter_emotion = []
                if 'filter_date_start' not in st.session_state:
                    st.session_state.filter_date_start = None
                if 'filter_date_end' not in st.session_state:
                    st.session_state.filter_date_end = None
                
                # 필터링 옵션 UI
                with st.expander("필터 옵션", expanded=False):
                    st.markdown("<div class='filter-section'>", unsafe_allow_html=True)
                    st.markdown("<div class='filter-title'>채팅 기록 필터링</div>", unsafe_allow_html=True)
                    
                    # 감정 필터
                    st.markdown("<div class='filter-item'><strong>감정 선택</strong></div>", unsafe_allow_html=True)
                    emotions_list = list(EMOTIONS.keys())
                    
                    # 감정 필터 UI를 더 효율적으로 표시
                    cols = st.columns(5)  # 한 행에 5개씩 표시
                    selected_emotions = []
                    
                    for i, emotion in enumerate(emotions_list):
                        col_idx = i % 5
                        emotion_icon = EMOTION_ICONS.get(emotion, "")
                        emotion_selected = cols[col_idx].checkbox(
                            f"{emotion_icon} {emotion}", 
                            value=emotion in st.session_state.filter_emotion,
                            key=f"filter_{emotion}"
                        )
                        if emotion_selected:
                            selected_emotions.append(emotion)
                    
                    st.session_state.filter_emotion = selected_emotions
                    
                    # 날짜 필터 (시작 및 종료 날짜)
                    st.markdown("<div class='filter-item'><strong>날짜 범위 선택</strong></div>", unsafe_allow_html=True)
                    
                    date_col1, date_col2 = st.columns(2)
                    
                    with date_col1:
                        start_date = st.date_input(
                            "시작 날짜", 
                            value=st.session_state.filter_date_start if st.session_state.filter_date_start else None,
                            format="YYYY-MM-DD"
                        )
                        if start_date:
                            st.session_state.filter_date_start = datetime.datetime.combine(start_date, datetime.time.min)
                        
                    with date_col2:
                        end_date = st.date_input(
                            "종료 날짜", 
                            value=st.session_state.filter_date_end if st.session_state.filter_date_end else None,
                            format="YYYY-MM-DD"
                        )
                        if end_date:
                            st.session_state.filter_date_end = datetime.datetime.combine(end_date, datetime.time.max)
                    
                    # 필터 초기화 버튼
                    if st.button("필터 초기화", type="secondary", use_container_width=True):
                        st.session_state.filter_emotion = []
                        st.session_state.filter_date_start = None
                        st.session_state.filter_date_end = None
                        st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # 채팅 기록 목록 표시
                chat_sessions = st.session_state.user_data['chat_sessions']
                
                # 필터링 적용
                filtered_sessions = []
                for chat in chat_sessions:
                    # 감정 필터링
                    emotion_match = True
                    if st.session_state.filter_emotion:
                        chat_emotion = chat.get('emotion', '')
                        if chat_emotion not in st.session_state.filter_emotion:
                            emotion_match = False
                    
                    # 날짜 필터링
                    date_match = True
                    if st.session_state.filter_date_start or st.session_state.filter_date_end:
                        chat_date = datetime.datetime.fromisoformat(chat.get('date', ''))
                        
                        if st.session_state.filter_date_start and chat_date < st.session_state.filter_date_start:
                            date_match = False
                        
                        if st.session_state.filter_date_end and chat_date > st.session_state.filter_date_end:
                            date_match = False
                    
                    # 필터 조건에 맞는 경우만 추가
                    if emotion_match and date_match:
                        filtered_sessions.append(chat)
                
                # 필터링 결과 안내
                if st.session_state.filter_emotion or st.session_state.filter_date_start or st.session_state.filter_date_end:
                    st.markdown("<div style='margin-bottom: 15px;'>", unsafe_allow_html=True)
                    st.markdown("<strong>적용된 필터:</strong>", unsafe_allow_html=True)
                    
                    # 감정 필터 배지
                    if st.session_state.filter_emotion:
                        st.markdown("<div>", unsafe_allow_html=True)
                        for emotion in st.session_state.filter_emotion:
                            emotion_icon = EMOTION_ICONS.get(emotion, "")
                            st.markdown(f"<span class='filter-badge'>{emotion_icon} {emotion}</span>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # 날짜 필터 배지
                    if st.session_state.filter_date_start or st.session_state.filter_date_end:
                        st.markdown("<div>", unsafe_allow_html=True)
                        if st.session_state.filter_date_start:
                            start_date_str = st.session_state.filter_date_start.strftime("%Y-%m-%d")
                            st.markdown(f"<span class='filter-badge'>시작일: {start_date_str}</span>", unsafe_allow_html=True)
                        
                        if st.session_state.filter_date_end:
                            end_date_str = st.session_state.filter_date_end.strftime("%Y-%m-%d")
                            st.markdown(f"<span class='filter-badge'>종료일: {end_date_str}</span>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    if not filtered_sessions:
                        st.warning("필터 조건에 맞는 채팅 기록이 없습니다.")
                
                # 최신 순으로 정렬
                filtered_sessions.sort(key=lambda x: x.get('date', ''), reverse=True)
                
                # 결과 갯수 표시
                if filtered_sessions:
                    st.markdown(f"<div style='margin-bottom: 10px;'><strong>{len(filtered_sessions)}개</strong>의 대화 기록이 있습니다.</div>", unsafe_allow_html=True)
                
                # 필터링된 채팅 기록 표시
                for chat in filtered_sessions:
                    # 카드 컨테이너 (상대 위치로 설정)
                    card_container = st.container()
                    
                    with card_container:
                        # 로그인 버튼과 충돌하지 않도록 div에 특정 클래스 추가
                        st.markdown('<div class="chat-history-card">', unsafe_allow_html=True)
                        
                        # 카드 스타일 컨테이너
                        st.markdown(f"""
                        <div class="chat-card">
                            <div class="chat-card-header">
                                <span class="chat-card-emotion">{EMOTION_ICONS.get(chat.get('emotion', ''), '')} {chat.get('emotion', '알 수 없음')}</span>
                                <span class="chat-card-date">{datetime.datetime.fromisoformat(chat.get('date', '')).strftime("%Y년 %m월 %d일 %H:%M")}</span>
                            </div>
                            <div class="chat-card-preview">{chat.get('preview', '대화 내용 없음')[:100]}...</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 카드 클릭 감지를 위한 버튼 (숨김)
                        card_clicked = st.button(
                            "보기",
                            key=f"chat_card_{chat['id']}"
                        )
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        if card_clicked:
                            st.session_state.selected_chat_id = chat['id']
                            st.rerun()

    elif st.session_state.active_page == "analysis":
        st.markdown("<h2 class='sub-header'>감정 분석</h2>", unsafe_allow_html=True)
        
        # 채팅 기록이 없는 경우
        if 'user_data' not in st.session_state or 'chat_sessions' not in st.session_state.user_data or not st.session_state.user_data['chat_sessions']:
            st.info("분석할 채팅 기록이 없습니다. 먼저 대화를 진행해주세요.")
        else:
            # 탭 설정
            tab1, tab2, tab3 = st.tabs(["감정 변화 그래프", "주간/월간 리포트", "감정 패턴 분석"])
            
            # 채팅 세션에서 감정 데이터 추출
            chat_sessions = st.session_state.user_data['chat_sessions']
            
            # 날짜와 감정 데이터 추출
            emotion_data = []
            for chat in chat_sessions:
                if 'date' in chat and 'emotion' in chat and chat['emotion']:
                    date = datetime.datetime.fromisoformat(chat['date'])
                    # UTC를 KST로 변환 (9시간 추가)
                    date = date.replace(tzinfo=pytz.UTC).astimezone(KST)
                    emotion_data.append({
                        'date': date,
                        'emotion': chat['emotion'],
                        'year': date.year,
                        'month': date.month,
                        'week': date.isocalendar()[1],
                        'day': date.day,
                    })
            
            if not emotion_data:
                st.warning("감정 데이터가 충분하지 않습니다. 더 많은 대화를 진행해주세요.")
            else:
                # 데이터프레임으로 변환
                df = pd.DataFrame(emotion_data)
                df = df.sort_values('date')
                
                with tab1:
                    st.subheader("시간에 따른 감정 변화")
                    
                    # 날짜 범위 선택
                    col1, col2 = st.columns(2)
                    with col1:
                        start_date = st.date_input(
                            "시작 날짜", 
                            value=df['date'].min().date(),
                            key="emotion_start_date"
                        )
                    with col2:
                        end_date = st.date_input(
                            "종료 날짜", 
                            value=df['date'].max().date(),
                            key="emotion_end_date"
                        )
                    
                    # 필터링
                    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
                    filtered_df = df.loc[mask]
                    
                    if filtered_df.empty:
                        st.warning("선택한 날짜 범위에 데이터가 없습니다.")
                    else:
                        # 그래프 대신 테이블 표시
                        st.markdown("#### 감정 변화 추이 (시간순)")
                        
                        # 표시할 데이터 준비
                        display_df = filtered_df[['date', 'emotion']].copy()
                        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d %H:%M')
                        display_df.columns = ['날짜', '감정']
                        
                        # 테이블로 표시
                        display_dataframe_with_pagination(display_df, key="emotion_change")
                
                with tab2:
                    st.subheader("주간/월간 감정 리포트")
                    
                    # 분석 기간 선택
                    report_type = st.radio(
                        "리포트 유형 선택",
                        ["주간", "월간"],
                        horizontal=True,
                        key="report_type"
                    )
                    
                    if report_type == "주간":
                        # 주간 데이터 그룹화
                        weekly_data = df.groupby(['year', 'week'])['emotion'].apply(list).reset_index()
                        weekly_data['period'] = weekly_data.apply(
                            lambda x: f"{x['year']}년 {x['week']}주차", axis=1)
                        weekly_data['count'] = weekly_data['emotion'].apply(len)
                        
                        # 기간 선택 (최근 4주 기본)
                        weeks = weekly_data['period'].unique()
                        selected_week = st.selectbox(
                            "분석할 주 선택",
                            weeks,
                            index=min(len(weeks)-1, 0),
                            key="selected_week"
                        )
                        
                        if selected_week:
                            # 선택한 주의 데이터
                            selected_data = weekly_data[weekly_data['period'] == selected_week]
                            
                            if not selected_data.empty:
                                emotions = selected_data.iloc[0]['emotion']
                                emotion_counts = Counter(emotions)
                                
                                # 차트 대신 테이블로 표현
                                st.markdown(f"#### {selected_week} 감정 분포")
                                
                                # 데이터프레임으로 변환
                                emotion_dist_df = pd.DataFrame({
                                    '감정': list(emotion_counts.keys()),
                                    '횟수': list(emotion_counts.values()),
                                    '비율(%)': [(count / sum(emotion_counts.values()) * 100) for count in emotion_counts.values()]
                                })
                                
                                # 비율 소수점 한 자리로 포맷팅
                                emotion_dist_df['비율(%)'] = emotion_dist_df['비율(%)'].round(1)
                                
                                # 빈도 내림차순으로 정렬
                                emotion_dist_df = emotion_dist_df.sort_values('횟수', ascending=False)
                                
                                # 테이블 표시
                                display_dataframe_with_pagination(emotion_dist_df, key="weekly_emotion")
                                
                                # 요약 통계
                                st.markdown("### 주간 감정 요약")
                                
                                # 요약 데이터 준비
                                summary_data = {
                                    '지표': ['총 대화 수', '가장 많이 느낀 감정', '감정 다양성'],
                                    '값': [
                                        f"{sum(emotion_counts.values())}회",
                                        f"{max(emotion_counts, key=emotion_counts.get)} ({emotion_counts[max(emotion_counts, key=emotion_counts.get)]}회)",
                                        f"{len(emotion_counts)}개 감정 경험"
                                    ]
                                }
                                
                                # 요약 테이블 표시
                                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
                            else:
                                st.warning("선택한 주에 데이터가 없습니다.")
                    else:  # 월간 리포트
                        # 월간 데이터 그룹화
                        monthly_data = df.groupby(['year', 'month'])['emotion'].apply(list).reset_index()
                        monthly_data['period'] = monthly_data.apply(
                            lambda x: f"{x['year']}년 {x['month']}월", axis=1)
                        monthly_data['count'] = monthly_data['emotion'].apply(len)
                        
                        # 기간 선택
                        months = monthly_data['period'].unique()
                        selected_month = st.selectbox(
                            "분석할 월 선택",
                            months,
                            index=min(len(months)-1, 0),
                            key="selected_month"
                        )
                        
                        if selected_month:
                            # 선택한 월의 데이터
                            selected_data = monthly_data[monthly_data['period'] == selected_month]
                            
                            if not selected_data.empty:
                                emotions = selected_data.iloc[0]['emotion']
                                emotion_counts = Counter(emotions)
                                
                                # 차트 대신 테이블로 표현
                                st.markdown(f"#### {selected_month} 감정 분포")
                                
                                # 감정 순서대로 정렬
                                ordered_emotions = [e for e in EMOTIONS.keys() if e in emotion_counts]
                                ordered_counts = [emotion_counts[e] for e in ordered_emotions]
                                
                                # 데이터프레임으로 변환
                                emotion_monthly_df = pd.DataFrame({
                                    '감정': ordered_emotions,
                                    '횟수': ordered_counts,
                                    '비율(%)': [(count / sum(ordered_counts) * 100) for count in ordered_counts]
                                })
                                
                                # 비율 소수점 한 자리로 포맷팅
                                emotion_monthly_df['비율(%)'] = emotion_monthly_df['비율(%)'].round(1)
                                
                                # 빈도 내림차순으로 정렬
                                emotion_monthly_df = emotion_monthly_df.sort_values('횟수', ascending=False)
                                
                                # 테이블 표시
                                display_dataframe_with_pagination(emotion_monthly_df, key="monthly_emotion")
                                
                                # 요약 통계
                                st.markdown("### 월간 감정 요약")
                                
                                # 요약 데이터 준비
                                summary_data = {
                                    '지표': ['총 대화 수', '가장 많이 느낀 감정', '감정 다양성'],
                                    '값': [
                                        f"{sum(emotion_counts.values())}회",
                                        f"{max(emotion_counts, key=emotion_counts.get)} ({emotion_counts[max(emotion_counts, key=emotion_counts.get)]}회)",
                                        f"{len(emotion_counts)}개 감정 / 전체 {len(EMOTIONS)}개 감정 중 ({(len(emotion_counts) / len(EMOTIONS) * 100):.1f}%)"
                                    ]
                                }
                                
                                # 요약 테이블 표시
                                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
                            else:
                                st.warning("선택한 월에 데이터가 없습니다.")
                
                with tab3:
                    st.subheader("감정 패턴 분석")
                    
                    # 전체 감정 분포 (파이 차트 대신 테이블로)
                    emotion_overall = df['emotion'].value_counts()
                    
                    # 테이블로 표시
                    st.markdown("#### 전체 감정 분포")
                    
                    # 데이터프레임으로 변환
                    emotion_overall_df = pd.DataFrame({
                        '감정': emotion_overall.index,
                        '횟수': emotion_overall.values,
                        '비율(%)': (emotion_overall.values / emotion_overall.sum() * 100).round(1)
                    })
                    
                    # 테이블 표시
                    display_dataframe_with_pagination(emotion_overall_df, key="overall_emotion")
                    
                    # 시간대별 감정 분석
                    st.markdown("### 시간대별 감정 패턴")
                    
                    # 시간대 추가
                    df['hour'] = df['date'].dt.hour
                    df['time_category'] = pd.cut(
                        df['hour'],
                        bins=[0, 6, 12, 18, 24],
                        labels=['새벽 (0-6시)', '오전 (6-12시)', '오후 (12-18시)', '저녁 (18-24시)'],
                        include_lowest=True
                    )
                    
                    # 시간대별 감정 분포 (히트맵 대신 테이블로)
                    time_emotion = pd.crosstab(df['time_category'], df['emotion'])
                    
                    # 시간대별 합계 추가
                    time_emotion['합계'] = time_emotion.sum(axis=1)
                    
                    # 각 행의 합계를 정렬 기준으로 활용 (내림차순)
                    time_emotion_sorted = time_emotion.sort_values('합계', ascending=False)
                    
                    # 비율 계산을 위한 복사본 생성
                    time_emotion_pct = time_emotion_sorted.copy()
                    
                    # '합계' 열 제외하고 각 행을 합계로 나누어 비율 계산
                    for col in time_emotion_pct.columns[:-1]:  # 마지막 '합계' 열 제외
                        time_emotion_pct[col] = (time_emotion_pct[col] / time_emotion_pct['합계'] * 100).round(1)
                    
                    # 절대값 테이블 표시
                    st.markdown("#### 시간대별 감정 빈도 (절대값)")
                    st.dataframe(time_emotion_sorted, use_container_width=True)
                    
                    # 비율 테이블 표시
                    st.markdown("#### 시간대별 감정 분포 (비율 %)")
                    # '합계' 열 제거 후 비율 테이블 표시
                    st.dataframe(time_emotion_pct.drop(columns=['합계']), use_container_width=True)
                    
                    # 패턴 분석 문장 생성
                    try:
                        most_common_time = time_emotion.sum(axis=1).idxmax()
                        most_common_emotion_overall = emotion_overall.idxmax()
                        
                        # 시간대별 가장 많은 감정
                        time_most_emotions = {}
                        for time_cat in time_emotion.index:
                            if not time_emotion.loc[time_cat].sum() == 0:
                                time_most_emotions[time_cat] = time_emotion.loc[time_cat].idxmax()
                        
                        # 분석 결과 텍스트 표시 - 더 간결하게
                        st.markdown("### 감정 패턴 인사이트")
                        
                        # 통계 요약을 컴팩트하게 표시
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**주요 대화 시간대:** {most_common_time}")
                            st.markdown(f"**주요 감정:** {most_common_emotion_overall}")
                        
                        with col2:
                            if len(df) > 3:
                                recent_emotions = df.sort_values('date').tail(3)['emotion'].tolist()
                                if len(set(recent_emotions)) == 1:
                                    st.markdown(f"**최근 감정:** {recent_emotions[0]}")
                                else:
                                    st.markdown(f"**최근 감정 변화:** {', '.join(recent_emotions)}")
                        
                        # 시간대별 주요 감정을 표 형태로 표시
                        st.markdown("#### 시간대별 주요 감정")
                        time_emotion_data = {"시간대": [], "주요 감정": []}
                        for time_cat, emotion in time_most_emotions.items():
                            time_emotion_data["시간대"].append(time_cat)
                            time_emotion_data["주요 감정"].append(emotion)
                        
                        time_emotion_df = pd.DataFrame(time_emotion_data)
                        st.dataframe(time_emotion_df, hide_index=True, use_container_width=True)
                            
                    except:
                        st.markdown("데이터가 충분하지 않아 상세 분석을 생성할 수 없습니다.")
                    
                    # 팁 제공
                    with st.expander("감정 관리 팁"):
                        emotion_tips = {
                            "기쁨": "긍정적인 감정을 유지하고 다른 사람과 나누세요. 감사 일기를 작성하면 기쁨을 오래 간직할 수 있습니다.",
                            "슬픔": "감정을 억누르지 말고 표현하세요. 가까운 사람과 대화하거나 글로 감정을 표현해보세요.",
                            "분노": "깊게 호흡하고 10까지 세어보세요. 분노를 느끼는 상황에서 잠시 벗어나 진정할 시간을 가지세요.",
                            "불안": "마음챙김 명상을 통해 현재에 집중하세요. 불안한 생각을 종이에 적어보면 객관화하는 데 도움이 됩니다.",
                            "스트레스": "가벼운 운동이나 취미 활동으로 기분 전환하세요. 충분한 휴식과 수면도 중요합니다.",
                            "외로움": "온라인 커뮤니티나 모임에 참여해보세요. 자원봉사 활동도 사회적 연결감을 높이는 데 도움이 됩니다.",
                            "후회": "과거에서 배울 점을 찾고 미래에 적용하세요. 자기 용서도 중요한 과정입니다.",
                            "좌절": "작은 목표부터 설정하고 성취해보세요. 성공 경험이 쌓이면 자신감이 생깁니다.",
                            "혼란": "생각을 정리하기 위해 마인드맵이나 일기를 작성해보세요. 필요하다면 전문가의 조언을 구하세요.",
                            "감사": "감사한 일들을 매일 기록하는 습관을 들이세요. 감사함이 더 많은 긍정적인 경험을 끌어당깁니다."
                        }
                        
                        if not emotion_overall.empty:
                            most_common = emotion_overall.idxmax()
                            st.markdown(f"### {EMOTION_ICONS.get(most_common, '')} {most_common} 감정을 위한 팁")
                            st.markdown(emotion_tips.get(most_common, "감정을 관리하기 위해 규칙적인 생활과 자기 돌봄을 실천하세요."))
                        
                        st.markdown("### 일반적인 감정 관리 전략")
                        st.markdown("""
                        1. **규칙적인 운동**: 신체 활동은 좋은 기분을 촉진하는 호르몬을 분비합니다.
                        2. **충분한 수면**: 수면 부족은 감정 조절 능력을 저하시킵니다.
                        3. **균형 잡힌 식사**: 영양소가 풍부한 식단은 뇌 기능과 기분에 영향을 줍니다.
                        4. **명상과 호흡법**: 스트레스 감소와 현재 순간에 집중하는 데 도움이 됩니다.
                        5. **사회적 연결**: 친구, 가족과의 소통은 정서적 지원을 제공합니다.
                        """)
                        
                        st.markdown(f"감정 관련 도움이 필요하시면 언제든지 AI 챗봇과 대화하거나 전문가와 상담하세요.")
                    
                    # 추천 사항
                    st.markdown("### 개인 맞춤 추천")
                    
                    if not emotion_overall.empty:
                        dominant_emotions = emotion_overall.nlargest(2).index.tolist()
                        
                        # 추천 활동을 한 행에 복수 열로 표시
                        st.markdown("##### 추천 활동")
                        activities = {
                            "기쁨": ["긍정적인 경험 일기 쓰기", "다른 사람과 기쁨 나누기", "감사 명상"],
                            "슬픔": ["감정 일기 쓰기", "자연 속 산책", "슬픔을 표현하는 예술 활동"],
                            "분노": ["운동하기", "심호흡 연습", "감정 정리 글쓰기"],
                            "불안": ["마음챙김 명상", "점진적 근육 이완법", "걱정 목록 작성하기"],
                            "스트레스": ["요가", "충분한 휴식", "자연 속에서 시간 보내기"],
                            "외로움": ["온라인 모임 참여", "자원봉사", "새로운 취미 배우기"],
                            "후회": ["자기 용서 명상", "교훈 찾기 연습", "미래 계획 세우기"],
                            "좌절": ["작은 성취 목표 설정", "멘토 찾기", "역경 극복 사례 읽기"],
                            "혼란": ["생각 정리를 위한 글쓰기", "전문가 상담", "명상"],
                            "감사": ["감사 일기 쓰기", "타인에게 감사 표현하기", "봉사활동"]
                        }
                        
                        # 추천 활동을 표로 표시
                        activity_data = {"감정": [], "추천 활동": []}
                        for emotion in dominant_emotions:
                            if emotion in activities:
                                activity_data["감정"].append(emotion)
                                activity_data["추천 활동"].append(", ".join(activities[emotion]))
                        
                        activity_df = pd.DataFrame(activity_data)
                        st.dataframe(activity_df, hide_index=True, use_container_width=True)
                            
                        # 시간대별 추천을 표로 변경
                        st.markdown("##### 시간대별 추천")
                        time_recommendations = {
                            "새벽 (0-6시)": "충분한 수면을 취하고, 명상이나 가벼운 스트레칭으로 하루를 시작해보세요.",
                            "오전 (6-12시)": "가장 에너지가 높은 시간대입니다. 중요한 의사결정이나 창의적인 활동에 집중해보세요.",
                            "오후 (12-18시)": "가벼운 산책이나 동료와의 대화로 에너지를 유지하세요.",
                            "저녁 (18-24시)": "하루를 돌아보고 감사한 일들을 기록하세요. 편안한 활동으로 수면 준비를 시작하세요."
                        }
                        
                        # 사용자가 가장 많이 대화한 시간대 확인
                        if not df.empty:
                            user_peak_time = df['time_category'].mode()[0]
                            
                            # 시간대별 추천을 표로 표시
                            rec_data = {"시간대": [], "추천 활동": []}
                            rec_data["시간대"].append(user_peak_time)
                            rec_data["추천 활동"].append(time_recommendations.get(user_peak_time, "규칙적인 생활 패턴을 유지하세요."))
                            
                            rec_df = pd.DataFrame(rec_data)
                            st.dataframe(rec_df, hide_index=True, use_container_width=True)

# 주기적 자동 저장
if (st.session_state.logged_in and 
    'messages' in st.session_state and 
    len(st.session_state.messages) > 1 and
    'selected_emotion' in st.session_state and
    st.session_state.selected_emotion and
    'auto_save' not in st.session_state):
    st.session_state.auto_save = True
    auto_save()

# 푸터
st.markdown("---")
st.markdown("© 2025 감정 치유 AI 챗봇 | 개인 정보는 안전하게 보호됩니다.")