import requests
import json
import os
from datetime import datetime, timedelta

# ============================================================
# 配置
# ============================================================

# 品种代码与合理价格区间
SYMBOLS = {
    'CU0': {'name': '沪铜', 'unit': '元/吨', 'min_val': 60000, 'max_val': 90000},
    'AL0': {'name': '沪铝', 'unit': '元/吨', 'min_val': 16000, 'max_val': 25000},
    'ZN0': {'name': '沪锌', 'unit': '元/吨', 'min_val': 18000, 'max_val': 30000},
    'PB0': {'name': '沪铅', 'unit': '元/吨', 'min_val': 14000, 'max_val': 22000},
    'NI0': {'name': '沪镍', 'unit': '元/吨', 'min_val': 100000, 'max_val': 200000},
    'SN0': {'name': '沪锡', 'unit': '元/吨', 'min_val': 150000, 'max_val': 300000},
    'AU0': {'name': '沪金', 'unit': '元/克', 'min_val': 800, 'max_val': 1000},
    'AG0': {'name': '沪银', 'unit': '元/千克', 'min_val': 14000, 'max_val': 18000},
    'RB0': {'name': '螺纹钢', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4000},
    'HC0': {'name': '热轧卷板', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'WR0': {'name': '线材', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'I0': {'name': '铁矿石', 'unit': '元/吨', 'min_val': 600, 'max_val': 1000},
    'SS0': {'name': '不锈钢', 'unit': '元/吨', 'min_val': 12000, 'max_val': 20000},
    'SI0': {'name': '工业硅', 'unit': '元/吨', 'min_val': 10000, 'max_val': 20000},
    'LC0': {'name': '碳酸锂', 'unit': '元/吨', 'min_val': 50000, 'max_val': 150000},
    'AO0': {'name': '氧化铝', 'unit': '元/吨', 'min_val': 2500, 'max_val': 5000},
}

HISTORY_DAYS = 365

# ============================================================
# 核心获取函数
# ============================================================

def fetch_sina(symbol):
    """
    从新浪财经获取指定品种的数据
    必须带 Referer 头，否则返回 Forbidden
    """
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
        print(f' 请求异常: {e}')
        return None

def parse_sina(raw, symbol):
    """
    解析新浪返回的原始数据，并进行严格校验
    """
    try:
        start = raw.find('"')
        end = raw.rfind('"')
        if start == -1 or end == -1:
            return None
        parts = raw[start+1:end].split(',')
        if len(parts) < 8:
            return None

        # 字段索引：0:名称, 1:最新价, 2:涨跌, 3:涨跌幅, 4:今开, 5:最高, 6:最低, 7:昨收
        # 尝试从多个字段取值，优先用最新价，如果异常则尝试昨收或今开
        price = None
        # 候选字段顺序：最新价、昨收、今开
        candidates = [
            parts[1] if len(parts) > 1 else '',
            parts[7] if len(parts) > 7 else '',
            parts[4] if len(parts) > 4 else ''
        ]
        for val in candidates:
            if val and val != '0':
                try:
                    p = float(val)
                    # 检查该品种的合理区间
                    info = SYMBOLS.get(symbol)
                    if info and info['min_val'] <= p <= info['max_val']:
                        price = p
                        break
                except:
                    continue

        if price is None:
            return None

        # 提取其他字段
        return {
            'price': price,
            'change': float(parts[2]) if len(parts) > 2 and parts[2] else 0,
            'change_pct': parts[3] if len(parts) > 3 else '0',
            'open': float(parts[4]) if len(parts) > 4 and parts[4] else 0,
            'high': float(parts[5]) if len(parts) > 5 and parts[5] else 0,
            'low': float(parts[6]) if len(parts) > 6 and parts[6] else 0,
            'prev_close': float(parts[7]) if len(parts) > 7 and parts[7] else 0,
            'name': parts[0] if parts[0] else ''
        }
    except Exception as e:
        print(f' 解析异常: {e}')
        return None

# ============================================================
# 主流程
# ============================================================

def fetch_all_metals():
    results = {}
    success_count = 0

    print('🔄 开始获取金属价格数据 (新浪HTTP)')
    print('=' * 60)

    for symbol, info in SYMBOLS.items():
        print(f'📊 获取 {info["name"]} ({symbol})...', end=' ')
        raw = fetch_sina(symbol)
        if raw:
            parsed = parse_sina(raw, symbol)
            if parsed:
                results[symbol] = {
                    'name': info['name'],
                    'price': parsed['price'],
                    'unit': info['unit'],
                    'change': parsed['change'],
                    'change_pct': parsed['change_pct'],
                    'open': parsed['open'],
                    'high': parsed['high'],
                    'low': parsed['low'],
                    'prev_close': parsed['prev_close'],
                }
                success_count += 1
                print(f'✅ {parsed["price"]:,.2f} {info["unit"]}')
                continue
        print('❌')

    print('=' * 60)
    print(f'✅ 成功获取 {success_count}/{len(SYMBOLS)} 个品种')
    return results

# ============================================================
# 保存与更新（与之前相同）
# ============================================================

def update_latest(data):
    if not data:
        return
    os.makedirs('data', exist_ok=True)
    output = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'source': '新浪财经',
        'note': '数据延迟约15分钟，已进行合理性校验',
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

def print_summary(data):
    if not data:
        return
    print('\n' + '=' * 60)
    print('📊 行情汇总')
    print('=' * 60)
    for symbol, info in data.items():
        print(f'  {info["name"]}：{info["price"]:,.2f} {info["unit"]}')
    print('=' * 60)

def main():
    print('=' * 60)
    print('📊 金属期货价格获取工具 (新浪HTTP)')
    print('=' * 60)
    print(f'⏰ 获取时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('')

    data = fetch_all_metals()
    if not data:
        print('❌ 没有获取到任何数据，请检查网络或稍后重试')
        return

    update_latest(data)
    update_history(data)
    print_summary(data)
    print('\n🎉 任务完成！')

if __name__ == '__main__':
    main()
