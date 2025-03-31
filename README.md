# 감정 치유 AI 챗봇

감정을 선택해서 자가 진단을 돕고, AI 챗봇의 따뜻한 대화로 감정을 치유하는 웹 애플리케이션입니다.

## 주요 기능

- 로그인/로그아웃 기능
- 감정 선택 기능
- AI 챗봇과의 대화 기능

## 설치 및 실행 방법

1. 저장소 클론
```bash
git clone https://github.com/your-username/emotion-healing-chatbot.git
cd emotion-healing-chatbot
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

3. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가하세요:
```
OPENAI_API_KEY=your_api_key_here
```

4. 애플리케이션 실행
```bash
streamlit run app.py
```

## 배포

이 애플리케이션은 Streamlit Cloud를 통해 배포할 수 있습니다. 