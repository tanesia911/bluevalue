from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import traceback
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

FMP_KEY = os.environ.get('FMP_API_KEY', 'qYW2mJtVejnjTkyfKfPWq5RswuXmzSEm')
FMP = 'https://financialmodelingprep.com/api/v3'

def normalize_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.isdigit() and len(t) == 6:
        return t + '.KS'
    if t.endswith('Q') and t[:-1].isdigit() and len(t) == 7:
        return t[:-1] + '.KQ'
    return t

def fmp_get(path):
    sep = '&' if '?' in path else '?'
    url = f"{FMP}{path}{sep}apikey={FMP_KEY}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()

@app.route('/api/analyze')
def analyze():
    raw = request.args.get('ticker', '').strip()
    if not raw:
        return jsonify({'error': '티커를 입력해주세요'}), 400

    ticker = normalize_ticker(raw)

    try:
        # 1. 기본 프로필
        profile_data = fmp_get(f'/profile/{ticker}')
        if not profile_data or not isinstance(profile_data, list):
            return jsonify({'error': f'"{ticker}" 데이터를 찾을 수 없습니다.'}), 404

        p = profile_data[0]
        cur_price = p.get('price', 0)
        currency = p.get('currency', 'USD')
        shares = p.get('sharesOutstanding', 0) or 1

        # 2. TTM 재무비율
        ratios = fmp_get(f'/ratios-ttm/{ticker}')
        r = ratios[0] if ratios and isinstance(ratios, list) else {}

        # 3. TTM 핵심 지표
        metrics_data = fmp_get(f'/key-metrics-ttm/{ticker}')
        m = metrics_data[0] if metrics_data and isinstance(metrics_data, list) else {}

        # 4. 5년 연도별 지표
        hist_metrics = fmp_get(f'/key-metrics/{ticker}?limit=5')
        income_hist  = fmp_get(f'/income-statement/{ticker}?limit=5')
        balance_hist = fmp_get(f'/balance-sheet-statement/{ticker}?limit=5')
        cf_hist      = fmp_get(f'/cash-flow-statement/{ticker}?limit=5')

        # 5. 주가 이력
        price_hist = fmp_get(f'/historical-price-full/{ticker}?serietype=line&timeseries=180')

        # 주가 월별 샘플링
        price_history = []
        hist_prices = list(reversed(price_hist.get('historical', [])))
        seen_months = {}
        for h in hist_prices:
            ym = h['date'][:7]
            seen_months[ym] = round(h['close'], 2)
        price_history = [{'date': k, 'close': v} for k, v in sorted(seen_months.items())][-6:]

        # 연도별 데이터
        yearly_data = []
        inc_map = {str(i.get('calendarYear','')): i for i in income_hist}
        bal_map = {str(i.get('calendarYear','')): i for i in balance_hist}
        cf_map  = {str(i.get('calendarYear','')): i for i in cf_hist}
        hm_map  = {str(i.get('date',''))[:4]: i for i in (hist_metrics or [])}

        years = sorted(set(list(inc_map.keys()) + list(bal_map.keys())))[-5:]
        for yr in years:
            inc = inc_map.get(yr, {})
            bal = bal_map.get(yr, {})
            cf  = cf_map.get(yr, {})

            rev_y  = inc.get('revenue')
            oi_y   = inc.get('operatingIncome')
            ni_y   = inc.get('netIncome')
            eq_y   = bal.get('totalStockholdersEquity') or bal.get('totalEquity')
            ltd_y  = (bal.get('longTermDebt') or 0) + (bal.get('shortTermDebt') or 0)
            ocf_y  = cf.get('operatingCashFlow')
            capex_y = cf.get('capitalExpenditure') or 0
            fcf_y  = (ocf_y + capex_y) if ocf_y is not None else cf.get('freeCashFlow')

            eps_y  = (ni_y / shares) if ni_y and shares else None
            bps_y  = (eq_y / shares) if eq_y and shares else None
            roe_y  = (ni_y / eq_y * 100) if ni_y and eq_y else None
            nim_y  = (ni_y / rev_y * 100) if ni_y and rev_y else None
            de_y   = (ltd_y / eq_y * 100) if ltd_y and eq_y else None

            yearly_data.append({
                'year': yr,
                'revenue': rev_y,
                'operatingIncome': oi_y,
                'netIncome': ni_y,
                'eps': round(eps_y, 2) if eps_y else None,
                'bps': round(bps_y, 2) if bps_y else None,
                'roe': round(roe_y, 2) if roe_y else None,
                'netMargin': round(nim_y, 2) if nim_y else None,
                'debtRatio': round(de_y, 2) if de_y else None,
                'fcf': fcf_y,
            })

        chg_amt = p.get('changes', 0) or 0
        chg_pct = (chg_amt / (cur_price - chg_amt) * 100) if cur_price and chg_amt else None

        rng = str(p.get('range', ''))
        hi52 = lo52 = None
        if '-' in rng:
            parts = rng.split('-')
            try: lo52 = float(parts[0].strip())
            except: pass
            try: hi52 = float(parts[1].strip())
            except: pass

        result = {
            'ticker': ticker,
            'name': p.get('companyName', ticker),
            'exchange': p.get('exchangeShortName', ''),
            'sector': p.get('sector', ''),
            'industry': p.get('industry', ''),
            'currency': currency,
            'description': (p.get('description') or '')[:400],
            'currentPrice': cur_price,
            'priceChange': chg_amt,
            'priceChangePct': round(chg_pct, 2) if chg_pct else None,
            'fiftyTwoWeekHigh': hi52,
            'fiftyTwoWeekLow': lo52,
            'marketCap': p.get('mktCap'),
            'sharesOutstanding': shares,
            'heldPercentInstitutions': m.get('institutionalOwnershipPercentage'),
            'trailingPE': r.get('peRatioTTM'),
            'forwardPE': r.get('priceEarningsRatioTTM'),
            'priceToBook': r.get('priceToBookRatioTTM'),
            'trailingEps': m.get('netIncomePerShareTTM'),
            'bookValue': m.get('bookValuePerShareTTM'),
            'dividendRate': p.get('lastDiv'),
            'dividendYield': round(r.get('dividendYieldTTM', 0) * 100, 2) if r.get('dividendYieldTTM') else None,
            'payoutRatio': round(r.get('payoutRatioTTM', 0) * 100, 2) if r.get('payoutRatioTTM') else None,
            'profitMargins': round(r.get('netProfitMarginTTM', 0) * 100, 2) if r.get('netProfitMarginTTM') else None,
            'operatingMargins': round(r.get('operatingProfitMarginTTM', 0) * 100, 2) if r.get('operatingProfitMarginTTM') else None,
            'grossMargins': round(r.get('grossProfitMarginTTM', 0) * 100, 2) if r.get('grossProfitMarginTTM') else None,
            'returnOnEquity': round(r.get('returnOnEquityTTM', 0) * 100, 2) if r.get('returnOnEquityTTM') else None,
            'returnOnAssets': round(r.get('returnOnAssetsTTM', 0) * 100, 2) if r.get('returnOnAssetsTTM') else None,
            'debtToEquity': r.get('debtEquityRatioTTM'),
            'currentRatio': r.get('currentRatioTTM'),
            'quickRatio': r.get('quickRatioTTM'),
            'beta': p.get('beta'),
            'totalRevenue': (m.get('revenuePerShareTTM') or 0) * shares or None,
            'operatingCashflow': (m.get('operatingCashFlowPerShareTTM') or 0) * shares or None,
            'freeCashflow': (m.get('freeCashFlowPerShareTTM') or 0) * shares or None,
            'priceHistory': price_history,
            'yearlyData': yearly_data,
        }
        return jsonify(result)

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else 500
        return jsonify({'error': f'API 오류 ({code})'}), code
    except Exception as e:
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '2.0', 'provider': 'FMP'})

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
