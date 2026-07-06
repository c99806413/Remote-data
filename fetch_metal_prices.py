import requests
import json
import os
from datetime import datetime, timedelta

# ============================================================
# 配置：品种名称映射 + 单位 + 合理区间
# ============================================================
SYMBOL_MAP = {
    'au_f': {'code': 'AU', 'name': '沪金', 'unit': '元/克', 'min_val': 800, 'max_val': 1000},
    'ag_f': {'code': 'AG', 'name': '沪银', 'unit': '元/千克', 'min_val': 14000, 'max_val': 18000},
    'cu_f': {'code': 'CU', 'name': '沪铜', 'unit': '元/吨', 'min_val': 60000, 'max_val': 90000},
    'al_f': {'code': 'AL', 'name': '沪铝', 'unit': '元/吨', 'min_val': 16000, 'max_val': 25000},
    'zn_f': {'code': 'ZN', 'name': '沪锌', 'unit': '元/吨', 'min_val': 18000, 'max_val': 30000},
    'pb_f': {'code': 'PB', 'name': '沪铅', 'unit': '元/吨', 'min_val': 14000, 'max_val': 22000},
    'ni_f': {'code': 'NI', 'name': '沪镍', 'unit': '元/吨', 'min_val': 100000, 'max_val': 200000},
    'sn_f': {'code': 'SN', 'name': '沪锡', 'unit': '元/吨', 'min_val': 150000, 'max_val': 300000},
    'rb_f': {'code': 'RB', 'name': '螺纹钢', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4000},
    'hc_f': {'code': 'HC', 'name': '热轧卷板', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'wr_f': {'code': 'WR', 'name': '线材', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'ss_f': {'code': 'SS', 'name': '不锈钢', 'unit': '元/吨', 'min_val': 12000, 'max_val': 20000},
    'ao_f': {'code': 'AO', 'name': '氧化铝', 'unit': '元/吨', 'min_val': 2500, 'max_val': 5000},
}

HISTORY_DAYS = 365

# ============================================================
# 核心抓取逻辑
# ============================================================

def fetch_shfe():
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://www.shfe.cn/data/tradedata/future/dailydata/kx{today}.dat"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.shfe.cn/'
    }
    
    print(f'📡 请求上期所数据: {url}')
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f'❌ HTTP {resp.status_code}')
            return None
        data = resp.json()
        print(f'✅ 数据获取成功')
    except Exception as e:
        print(f'❌ 请求失败: {e}')
        return None

    products = data.get('o_curproduct', [])
    if not products:
        print('❌ 未找到品种数据')
        return None

    results = {}
    for item in products:
        product_id = item.get('PRODUCTID', '')
        if product_id not in SYMBOL_MAP:
            continue
        
        info = SYMBOL_MAP[product_id]
        
        # 提取价格字段，优先用均价，次选收盘价，再取开盘价
        price = None
        avg_price = item.get('AVGPRICE', '')
        close_price = item.get('CLOSEPRICE', '')
        open_price = item.get('OPENPRICE', '')
        
        if avg_price and avg_price != '':
            try:
                price = float(avg_price)
            except:
                pass
        if price is None and close_price and close_price != '':
            try:
                price = float(close_price)
            except:
                pass
        if price is None and open_price and open_price != '':
            try:
                price = float(open_price)
            except:
                pass
        
        if price is None:
            print(f'⚠️ {info["name"]} 无有效价格')
            continue
        
        # 合理性校验
        if not (info['min_val'] <= price <= info['max_val']):
            print(f'⚠️ {info["name"]} 价格 {price} 超出合理区间，跳过')
            continue
        
        # 提取其他字段
        prev_close = item.get('PRECLOSEPRICE', '')
        prev_close = float(prev_close) if prev_close and prev_close != '' else price
        
        high = item.get('HIGHESTPRICE', '')
        high = float(high) if high and high != '' else price
        
        low = item.get('LOWESTPRICE', '')
        low = float(low) if low and low != '' else price
        
        open_price = float(open_price) if open_price and open_price != '' else price
        
        # 计算涨跌
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        
        results[info['code']] = {
            'name': info['name'],
            'price': price,
            'unit': info['unit'],
            'change': change,
            'change_pct': f"{change_pct:.2f}",
            'open': open_price,
            'high': high,
            'low': low,
            'prev_close': prev_close,
            'volume': item.get('VOLUME', 0),
        }
        arrow = '↑' if change_pct > 0 else '↓' if change_pct < 0 else '→'
        print(f'  ✅ {info["name"]}: {price:.2f} {info["unit"]} {arrow} {abs(change_pct):.2f}%')
    
    print(f'📊 共获取 {len(results)} 个品种')
    return results

def fetch_all_metals():
    print('=' * 60)
    print('📊 金属期货价格获取工具 (上期所官方接口)')
    print('=' * 60)
    print(f'⏰ 运行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('')
    return fetch_shfe()

# ============================================================
# 保存与更新（与之前完全一致）
# ============================================================

def update_latest(data):
    if not data:
        return
    os.makedirs('data', exist_ok=True)
    output = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'source': '上海期货交易所 (SHFE)',
        'note': '数据来自上期所日度结算价，使用加权均价',
        'rates': data
    }
    with open('data/metal_prices.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print('✅ 已更新 data/metal_prices.json')

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
    print(f'✅ 已更新 data/metal_history.json (共 {len(history["records"])} 条)')

def print_summary(data):
    if not data:
        return
    print('\n' + '=' * 60)
    print('📊 行情汇总 (上海期货交易所)')
    print('=' * 60)
    for code, info in data.items():
        try:
            pct = float(info['change_pct'])
            arrow = '↑' if pct > 0 else '↓' if pct < 0 else '→'
            print(f'  {info["name"]}：{info["price"]:,.2f} {info["unit"]}  {arrow} {abs(pct):.2f}%')
        except:
            print(f'  {info["name"]}：{info["price"]:,.2f} {info["unit"]}')
    print('=' * 60)

def main():
    data = fetch_all_metals()
    if not data:
        print('❌ 未获取到任何有效数据')
        return
    update_latest(data)
    update_history(data)
    print_summary(data)
    print('\n🎉 任务完成！')

if __name__ == '__main__':
    main()
