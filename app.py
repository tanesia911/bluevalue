from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yfinance as yf
import traceback
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# ── 한국 주식 티커 자동 변환 ──────────────────────────────────────────────
def normalize_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    # 숫자 6자리면 한국 주식 (KOSPI)
    if t.isdigit() and len(t) == 6:
        return t + '.KS'
    # 숫자 6자리 + Q이면 코스닥
    if t.endswith('Q') and t[:-1].isdigit() and len(t) == 7:
        return t[:-1] + '.KQ'
    return t

# ── 메인 분석 API ─────────────────────────────────────────────────────────
@app.route('/api/analyze')
def analyze():
    raw = request.args.get('ticker', '').strip()
    if not raw:
        return jsonify({'error': '티커를 입력해주세요'}), 400

    ticker = normalize_ticker(raw)

    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None:
            return jsonify({'error': f'"{ticker}" 데이터를 찾을 수 없습니다. 티커를 확인해주세요.'}), 404

        # ── 기본 정보 ────────────────────────────────────────────────────
        cur_price = info.get('currentPrice') or info.get('regularMarketPrice') or 0

        # ── 6개월 주가 ───────────────────────────────────────────────────
        hist = t.history(period='6mo', interval='1mo')
        price_history = []
        for date, row in hist.iterrows():
            price_history.append({
                'date': date.strftime('%Y-%m'),
                'close': round(row['Close'], 2)
            })

        # ── 5년 연도별 재무 ──────────────────────────────────────────────
        yearly_data = []
        try:
            inc = t.financials          # 연간 손익계산서 (최신→과거)
            bal = t.balance_sheet       # 연간 대차대조표
            cf  = t.cashflow            # 연간 현금흐름표

            shares = info.get('sharesOutstanding') or 0

            years = sorted(inc.columns, key=lambda x: x.year) if inc is not None and not inc.empty else []

            for col in years[-5:]:   # 최근 5년
                yr = col.year

                # 손익
                rev  = _safe(inc, 'Total Revenue', col)
                oi   = _safe(inc, 'Operating Income', col)
                ni   = _safe(inc, 'Net Income', col)

                # 대차
                eq   = _safe(bal, 'Stockholders Equity', col) or _safe(bal, 'Common Stock Equity', col)
                ltd  = _safe(bal, 'Long Term Debt', col) or 0
                stld = _safe(bal, 'Current Debt', col) or 0

                # 현금흐름
                ocf_y = _safe(cf, 'Operating Cash Flow', col)
                capex = _safe(cf, 'Capital Expenditure', col) or 0
                fcf_y = ocf_y + capex if ocf_y is not None else None

                # 주당 지표
                eps_y = ni / shares if ni and shares else None
                bps_y = eq / shares if eq and shares else None
                roe_y = (ni / eq * 100) if ni and eq and eq != 0 else None
                nim_y = (ni / rev * 100) if ni and rev and rev != 0 else None
                de_y  = ((ltd + stld) / eq * 100) if eq and eq != 0 else None

                yearly_data.append({
                    'year': yr,
                    'revenue': _fmt(rev),
                    'operatingIncome': _fmt(oi),
                    'netIncome': _fmt(ni),
                    'eps': round(eps_y, 2) if eps_y is not None else None,
                    'bps': round(bps_y, 2) if bps_y is not None else None,
                    'roe': round(roe_y, 2) if roe_y is not None else None,
                    'netMargin': round(nim_y, 2) if nim_y is not None else None,
                    'debtRatio': round(de_y, 2) if de_y is not None else None,
                    'fcf': _fmt(fcf_y),
                })
        except Exception:
            pass  # 재무제표 없으면 빈 배열

        # ── 응답 조립 ─────────────────────────────────────────────────────
        result = {
            'ticker': ticker,
            'name': info.get('longName') or info.get('shortName') or ticker,
            'exchange': info.get('exchange') or info.get('exchangeName') or '',
            'sector': info.get('sector') or '',
            'industry': info.get('industry') or '',
            'currency': info.get('currency') or 'USD',
            'description': (info.get('longBusinessSummary') or '')[:400],
            'fiscalYearEnd': info.get('lastFiscalYearEnd') or '',

            # 가격
            'currentPrice': cur_price,
            'previousClose': info.get('previousClose'),
            'priceChange': round(cur_price - (info.get('previousClose') or cur_price), 4),
            'priceChangePct': round((cur_price / (info.get('previousClose') or cur_price) - 1) * 100, 2),
            'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
            'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),

            # 시장 정보
            'marketCap': info.get('marketCap'),
            'sharesOutstanding': info.get('sharesOutstanding'),
            'floatShares': info.get('floatShares'),
            'heldPercentInstitutions': info.get('heldPercentInstitutions'),

            # 밸류에이션
            'trailingPE': info.get('trailingPE'),
            'forwardPE': info.get('forwardPE'),
            'priceToBook': info.get('priceToBook'),
            'priceToSalesTrailing12Months': info.get('priceToSalesTrailing12Months'),
            'enterpriseToEbitda': info.get('enterpriseToEbitda'),

            # 주당 지표
            'trailingEps': info.get('trailingEps'),
            'forwardEps': info.get('forwardEps'),
            'bookValue': info.get('bookValue'),

            # 배당
            'dividendRate': info.get('dividendRate'),
            'dividendYield': round(info.get('dividendYield') * 100, 2) if info.get('dividendYield') else None,
            'payoutRatio': round(info.get('payoutRatio') * 100, 2) if info.get('payoutRatio') else None,

            # 수익성
            'profitMargins': round(info.get('profitMargins') * 100, 2) if info.get('profitMargins') else None,
            'operatingMargins': round(info.get('operatingMargins') * 100, 2) if info.get('operatingMargins') else None,
            'grossMargins': round(info.get('grossMargins') * 100, 2) if info.get('grossMargins') else None,
            'returnOnEquity': round(info.get('returnOnEquity') * 100, 2) if info.get('returnOnEquity') else None,
            'returnOnAssets': round(info.get('returnOnAssets') * 100, 2) if info.get('returnOnAssets') else None,

            # 재무 건전성
            'debtToEquity': info.get('debtToEquity'),
            'currentRatio': info.get('currentRatio'),
            'quickRatio': info.get('quickRatio'),
            'beta': info.get('beta'),

            # 규모
            'totalRevenue': info.get('totalRevenue'),
            'operatingCashflow': info.get('operatingCashflow'),
            'freeCashflow': info.get('freeCashflow'),

            # 히스토리
            'priceHistory': price_history,
            'yearlyData': yearly_data,
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500


def _safe(df, key, col):
    """DataFrame에서 안전하게 값 추출"""
    try:
        if df is None or df.empty:
            return None
        # 부분 매칭
        matches = [i for i in df.index if key.lower() in str(i).lower()]
        if not matches:
            return None
        val = df.loc[matches[0], col]
        return float(val) if val is not None and str(val) != 'nan' else None
    except:
        return None

def _fmt(v):
    """큰 숫자 반올림"""
    if v is None: return None
    return round(v)


# ── 헬스체크 ──────────────────────────────────────────────────────────────
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.0'})

# ── 프론트엔드 서빙 ───────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
