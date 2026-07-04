import requests
import json
import os
from datetime import datetime, timedelta

# ============================================================
# 新浪财经 HTTP 接口获取金属期货数据
# 不依赖 AKShare，完全用 requests，避免版本问题
# ============================================================

# 品种配置：新浪代码
SYMBOLS = {
    'CU0': {'name': '沪铜', 'unit': '元/吨'},
    'AL0': {'name': '沪铝', 'unit': '元/吨'},
    'ZN0': {'name': '沪锌', 'unit': '元/吨'},
    'PB0': {'name': '沪铅', 'unit': '元/吨'},
    'NI0': {'name': '沪镍', 'unit': '元/吨'},
    'SN0': {'name': '沪锡', 'unit': '元/吨'},
    'AU0': {'name': '沪金', 'unit': '元/克'},
    'AG0': {'name': '沪银', 'unit': '元/千克'},
    'RB0': {'name': '螺纹钢', 'unit': '元/吨'},
    'HC0': {'name': '热轧卷板', 'unit': '元/吨'},
    'WR0': {'name': '线材', 'unit': '元/吨'},
    'I0': {'name': '铁矿石', 'unit': '元/吨'},
    'SS9999': {'name': '不锈钢', 'unit': '元/吨'},  # 使用 9999 代表主力连续
    'SI0': {'name': '工业硅', 'unit': '元/吨'},
    'LC0': {'name': '碳酸锂', 'unit': '元/吨'},
    'AO0': {'name': '氧化铝', 'unit': '元/吨'},
}

HISTORY_DAYS = 365

def fetch_sina(symbol):
    """请求新浪财经接口"""
    url = f'https://hq.sinajs.cn/list={symbol}'
    headers = {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'gbk'
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        if not text or '404' in text or 'Forbidden' in text:
            return None
        return text
    except Exception as e:
        print(f'  请求异常: {e}')
        return None

def parse_sina(raw):
    """解析新浪返回的数据"""
    try:
        start = raw.find('"')
        end = raw.rfind('"')
        if start == -1 or end == -1:
            return None
        parts = raw[start+1:end].split(',')
        if len(parts) < 8:
            return None
        price = parts[1]
        if not price or price == '0':
            return None
        return {
            'price': float(price),
            'change': float(parts[2]) if parts[2] else 0,
            'change_pct': parts[3] if parts[3] else '0',
            'open': float(parts[4]) if parts[4] else 0,
            'high': float(parts[5]) if parts[5] else 0,
            'low': float(parts[6]) if parts[6] else 0,
            'prev_close': float(parts[7]) if parts[7] else 0,
        }
    except:
        return None

def fetch_all_metals():
    results = {}
    success_count = 0
    print('🔄 开始获取金属价格数据 (HTTP)')
    print('='*60)
    for code, info in SYMBOLS.items():
        print(f'📊 获取 {info["name"]} ({code})...', end=' ')
        raw = fetch_sina(code)
        if raw:
            parsed = parse_sina(raw)
            if parsed:
                results[code] = {
                    'name': info['name'],
                    'price': parsed['price'],
                    'unit': info['unit'],
                    'change': parsed['change'],
                    'change_pct': parsed['change_pct'],
                    'high': parsed['high'],
                    'low': parsed['low'],
                    'open': parsed['open'],
                    'prev_close': parsed['prev_close'],
                }
                success_count += 1
                print(f'✅ {parsed["price"]:,.2f} {info["unit"]}')
                continue
        print('❌')
    print('='*60)
    print(f'✅ 成功获取 {success_count}/{len(SYMBOLS)} 个品种')
    return results

def update_latest(data):
    if not data:
        return
    os.makedirs('data', exist_ok=True)
    output = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'source': '新浪财经 HTTP',
        'note': '数据延迟约15分钟',
        'rates': data
    }
    with open('data/metal_prices.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print('✅ 最新价格已保存')

def update_history(data):
    if not data:
        return
    history_file = 'data/metal_history.json'
    history = {'records': []}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            pass
    today = datetime.utcnow().strftime('%Y-%m-%d')
    today_record = {'date': today, 'rates': data}
    history['records'] = [r for r in history['records'] if r.get('date') != today]
    history['records'].append(today_record)
    history['records'] = sorted(history['records'], key=lambda x: x['date'])
    cutoff = (datetime.utcnow() - timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')
    history['records'] = [r for r in history['records'] if r['date'] >= cutoff]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f'✅ 历史记录已更新 (保留 {HISTORY_DAYS} 天，共 {len(history["records"])} 条)')

def main():
    print('='*60)
    print('📊 金属期货价格获取工具 (HTTP)')
    print('='*60)
    print(f'⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    data = fetch_all_metals()
    if data:
        update_latest(data)
        update_history(data)
        print('\n🎉 任务完成！')
    else:
        print('❌ 没有获取到任何数据')

if __name__ == '__main__':
    main()