# 📊 Blue Value — 기업가치 분석툴

티커 하나만 입력하면 Yahoo Finance 데이터를 자동 수집해 **9가지 가치평가 모델**로 적정주가를 계산합니다.

---

## 🚀 Render 배포 방법 (5분 완성)

### 1단계 — GitHub에 올리기

```bash
# 이 폴더를 GitHub 저장소로 만들기
git init
git add .
git commit -m "first commit"

# GitHub에서 새 저장소 만든 후 연결
git remote add origin https://github.com/내아이디/bluevalue.git
git push -u origin main
```

### 2단계 — Render 배포

1. [render.com](https://render.com) 접속 → 무료 계정 가입
2. **New +** → **Web Service** 클릭
3. GitHub 저장소 연결
4. 설정 확인:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: `Free`
5. **Create Web Service** 클릭
6. 배포 완료 → `https://bluevalue-xxxx.onrender.com` URL 생성됨 🎉

---

## 💻 로컬 실행 방법

```bash
# 패키지 설치
pip install -r requirements.txt

# 서버 실행
python app.py

# 브라우저에서 접속
open http://localhost:5000
```

---

## 📁 파일 구조

```
bluevalue/
├── app.py              # Flask 백엔드 API
├── requirements.txt    # Python 패키지
├── render.yaml         # Render 배포 설정
├── .gitignore
└── static/
    └── index.html      # 프론트엔드
```

---

## 📈 가치평가 모델 9종

| # | 모델 | 공식 |
|---|------|------|
| 1 | 벤저민 그레이엄 | √(22.5 × EPS × BPS) |
| 2 | 네프 상수 (PEG) | EPS × (성장률 + 배당률) |
| 3 | 존 템플턴 | 5년 EPS 합계 × 1.5 |
| 4 | 간단 BPS법 | BPS × 5년 평균 PBR |
| 5 | 올슨 RIM | BPS + BPS×(ROE-Rf)/(k-g) |
| 6 | 야마구치 요헤이 | 5년 주당이익 현재가치 + 기말BPS |
| 7 | 칸타빌레 | BPS×0.4 + 연평균EPS×PER×0.6 |
| 8 | DCF | 5년 FCF + 터미널밸류 할인 |
| 9 | PSR 역산 | 주당매출 × 1.5 |

---

## ⚠️ 주의사항

- Render 무료 플랜은 15분 미사용 시 슬립 모드 → 첫 요청에 30~60초 소요
- Yahoo Finance 데이터 기반 추정치이며 **투자 권유가 아닙니다**
