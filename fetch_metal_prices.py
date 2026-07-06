import requests
import json
import os
from datetime import datetime, timedelta
import time

# ============================================================
# 配置
# ============================================================

# 新浪财经期货代码（0 表示主力连续合约）
# 新浪接口支持 AU0（沪金）和 AG0（沪银），之前抓不到是因为解析逻辑没适配
SYMBOLS = {
    'CU0': {'name': '沪铜', 'unit': '元/吨', 'min_val': 60000, 'max_val': 90000},
    'AL0': {'name': '沪铝', 'unit': '元/吨', 'min_val': 16000, 'max_val': 25000},
    'ZN0': {'name': '沪锌', 'unit': '元/吨', 'min_val': 18000, 'max_val': 30000},
    'PB0': {'name': '沪铅', 'unit': '元/吨', 'min_val': 14000, 'max_val': 22000},
    'NI0': {'name': '沪镍', 'unit': '元/吨', 'min_val': 100000, 'max_val': 200000},
    'SN0': {'name': '沪锡', 'unit': '元/吨', 'min_val': 150000, 'max_val': 300000},
    'AU0': {'name': '沪金', 'unit': '元/克', 'min_val': 800, 'max_val': 1000},      # ✅ 黄金主力
    'AG0': {'name': '沪银', 'unit': '元/千克', 'min_val': 14000, 'max_val': 18000}, # ✅ 白银主力
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
# 核心获取函数（新浪财经 HTTP，直连）
# ============================================================

def fetch_sina(symbol):
    """
    从新浪财经获取指定品种的数据
    必须带 Referer 和 User-Agent，否则返回 Forbidden
    """
    url = f'https://hq.sinajs.cn/list={symbol}'
    headers = {
        'Referer': 'https://finance.sina.com.cn/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'gbk'
        if resp.status_code != 200:
            print(f'  HTTP {resp.status_code}')
            return None
        text = resp.text.strip()
        if not text or '404' in text or 'Forbidden' in text or 'FAILED' in text.upper():
            return None
        return text
    except Exception as e:
        print(f'  请求异常: {e}')
        return None

def parse_sina(raw, symbol):
    """
    解析新浪返回的原始数据
    新浪期货格式：var hq_str_CU0="名称,最新价,涨跌额,涨跌幅%,今开,最高,最低,昨收,...";
    """
    try:
        start = raw.find('"')
        end = raw.rfind('"')
        if start == -1 or end == -1:
            return None
        parts = raw[start+1:end].split(',')
        if len(parts) < 8:
            return None

        # 字段索引：
        # 0: 名称（如 "沪铜连续"）
        # 1: 最新价
        # 2: 涨跌额
        # 3: 涨跌幅%（如 "0.50" 或 "--"）
        # 4: 今开
        # 5: 最高
        # 6: 最低
        # 7: 昨收
        
        raw_name = parts[0] if len(parts) > 0 else ''
        # 提取纯中文名称（去掉"连续"、"主力"等后缀）
        name_parts = raw_name.split()
        clean_name = name_parts[0] if name_parts else raw_name
        
        # 尝试提取最新价（优先），如果最新价为 0 或无效，则用昨收或今开
        price = None
        candidates = [
            parts[1] if len(parts) > 1 else '',
            parts[7] if len(parts) > 7 else '',
            parts[4] if len(parts) > 4 else ''
        ]
        for val in candidates:
            if val and val != '0' and val != '--':
                try:
                    p = float(val)
                    info = SYMBOLS.get(symbol)
                    if info and info['min_val'] <= p <= info['max_val']:
                        price = p
                        break
                except:
                    continue

        if price is None:
            return None

        # 提取其他字段
        change_val = 0.0
        if len(parts) > 2 and parts[2] and parts[2] != '0' and parts[2] != '--':
            try:
                change_val = float(parts[2])
            except:
                pass
        # 如果涨跌额为 0，尝试用最新价-昨收计算
        if change_val == 0 and len(parts) > 7 and parts[7]:
            try:
                prev_close = float(parts[7])
                change_val = price - prev_close
            except:
                pass

        change_pct_str = '0'
        if len(parts) > 3 and parts[3]:
            pct_raw = parts[3].replace('%', '').strip()
            if pct_raw and pct_raw != '--' and pct_raw != '':
                try:
                    # 如果涨跌幅是数字，直接使用
                    float(pct_raw)
                    change_pct_str = pct_raw
                except:
                    # 如果不是数字，用涨跌额/昨收计算
                    if len(parts) > 7 and parts[7]:
                        try:
                            prev_close = float(parts[7])
                            if prev_close > 0:
                                change_pct_str = f"{(change_val / prev_close * 100):.2f}"
                        except:
                            pass

        return {
            'price': price,
            'change': change_val,
            'change_pct': change_pct_str,
            'open': float(parts[4]) if len(parts) > 4 and parts[4] and parts[4] != '0' else price,
            'high': float(parts[5]) if len(parts) > 5 and parts[5] and parts[5] != '0' else price,
            'low': float(parts[6]) if len(parts) > 6 and parts[6] and parts[6] != '0' else price,
            'prev_close': float(parts[7]) if len(parts) > 7 and parts[7] and parts[7] != '0' else price,
            'name': clean_name
        }
    except Exception as e:
        print(f'  解析异常: {e}')
        return None

def fetch_all_metals():
    results = {}
    success_count = 0

    print('🔄 开始获取金属价格数据 (新浪财经 HTTP)')
    print('=' * 60)

    for symbol, info in SYMBOLS.items():
        print(f'📊 获取 {info["name"]} ({symbol})...', end=' ', flush=True)
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
                try:
                    pct = float(parsed['change_pct'])
                    arrow = '↑' if pct > 0 else '↓' if pct < 0 else '→'
                    print(f'✅ {parsed["price"]:,.2f} {info["unit"]} {arrow} {abs(pct):.2f}%')
                except:
                    print(f'✅ {parsed["price"]:,.2f} {info["unit"]}')
                continue
        print('❌')
        # 避免请求过快被封
        time.sleep(0.3)

    print('=' * 60)
    print(f'✅ 成功获取 {success_count}/{len(SYMBOLS)} 个品种')
    return results

# ============================================================
# 保存与更新（与原代码相同）
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
    print('✅ 最新价格已保存到 data/metal_prices.json')

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
    history['records'] = [r for r in history['records'] if r.get('date') != today]
    history['records'].append({'date': today, 'rates': data})
    history['records'] = sorted(history['records'], key=lambda x: x['date'])
    cutoff = (datetime.utcnow() - timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')
    history['records'] = [r for r in history['records'] if r['date'] >= cutoff]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f'✅ 历史记录已保存 (共 {len(history["records"])} 条)')

def print_summary(data):
    if not data:
        return
    print('\n' + '=' * 60)
    print('📊 行情汇总')
    print('=' * 60)
    for symbol, info in data.items():
        try:
            pct = float(info['change_pct'])
            arrow = '↑' if pct > 0 else '↓' if pct < 0 else '→'
            print(f'  {info["name"]}：{info["price"]:,.2f} {info["unit"]}  {arrow} {abs(pct):.2f}%')
        except:
            print(f'  {info["name"]}：{info["price"]:,.2f} {info["unit"]}')
    print('=' * 60)

def main():
    print('=' * 60)
    print('📊 金属期货价格获取工具 (新浪财经 HTTP)')
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
