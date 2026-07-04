import json
import os
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd
import time

# ============================================================
# 配置
# ============================================================

SYMBOLS = {
    'CU': {'name': '沪铜', 'unit': '元/吨', 'group': '有色金属'},
    'AL': {'name': '沪铝', 'unit': '元/吨', 'group': '有色金属'},
    'ZN': {'name': '沪锌', 'unit': '元/吨', 'group': '有色金属'},
    'PB': {'name': '沪铅', 'unit': '元/吨', 'group': '有色金属'},
    'NI': {'name': '沪镍', 'unit': '元/吨', 'group': '有色金属'},
    'SN': {'name': '沪锡', 'unit': '元/吨', 'group': '有色金属'},
    'AU': {'name': '沪金', 'unit': '元/克', 'group': '贵金属'},
    'AG': {'name': '沪银', 'unit': '元/千克', 'group': '贵金属'},
    'RB': {'name': '螺纹钢', 'unit': '元/吨', 'group': '钢材'},
    'HC': {'name': '热轧卷板', 'unit': '元/吨', 'group': '钢材'},
    'WR': {'name': '线材', 'unit': '元/吨', 'group': '钢材'},
    'SS': {'name': '不锈钢', 'unit': '元/吨', 'group': '钢材'},
    'I': {'name': '铁矿石', 'unit': '元/吨', 'group': '钢材'},
    'SI': {'name': '工业硅', 'unit': '元/吨', 'group': '新能源'},
    'LC': {'name': '碳酸锂', 'unit': '元/吨', 'group': '新能源'},
    'AO': {'name': '氧化铝', 'unit': '元/吨', 'group': '有色金属'},
}

HISTORY_DAYS = 365

# ============================================================
# 核心获取函数（逐个品种，更稳定）
# ============================================================

def fetch_main_contract(symbol):
    """使用 futures_zh_main_sina 获取主力连续合约数据"""
    try:
        df = ak.futures_zh_main_sina(symbol=symbol)
        if df is None or df.empty:
            return None
        # 取最新一行
        latest = df.iloc[-1]
        price = latest.get('最新价', 0)
        if price == 0 or pd.isna(price):
            return None
        return {
            'price': float(price),
            'volume': int(latest.get('成交量', 0)) if not pd.isna(latest.get('成交量', 0)) else 0,
            'open': float(latest.get('开盘价', 0)) if not pd.isna(latest.get('开盘价', 0)) else 0,
            'high': float(latest.get('最高价', 0)) if not pd.isna(latest.get('最高价', 0)) else 0,
            'low': float(latest.get('最低价', 0)) if not pd.isna(latest.get('最低价', 0)) else 0,
            'prev_close': float(latest.get('昨收价', 0)) if not pd.isna(latest.get('昨收价', 0)) else 0,
            'change': float(latest.get('涨跌额', 0)) if not pd.isna(latest.get('涨跌额', 0)) else 0,
            'change_pct': str(latest.get('涨跌幅', '0')) if not pd.isna(latest.get('涨跌幅', '')) else '0',
        }
    except Exception as e:
        print(f'  异常: {e}')
        return None

def fetch_gold_spot():
    """获取黄金现货价格（AU9999）"""
    try:
        df = ak.spot_gold()
        if df is None or df.empty:
            return None
        latest = df.iloc[-1]
        price = float(latest['最新价'])
        if price <= 0:
            return None
        return price
    except Exception as e:
        print(f'  黄金现货异常: {e}')
        return None

# ============================================================
# 主流程
# ============================================================

def fetch_all_metals():
    results = {}
    success_count = 0

    print('🔄 开始获取金属价格数据 (逐个合约)')
    print('=' * 60)

    for symbol, info in SYMBOLS.items():
        print(f'📊 获取 {info["name"]} ({symbol})...', end=' ')

        # 黄金优先用现货
        if symbol == 'AU':
            gold_spot = fetch_gold_spot()
            if gold_spot:
                results[symbol] = {
                    'name': info['name'],
                    'price': gold_spot,
                    'unit': info['unit'],
                    'group': info['group'],
                    'change': 0,
                    'change_pct': '0',
                    'open': 0,
                    'high': 0,
                    'low': 0,
                    'prev_close': 0,
                    'contract': 'AU9999现货',
                }
                success_count += 1
                print(f'✅ {gold_spot:,.2f} {info["unit"]} (现货)')
                continue

        # 其他品种使用期货主力
        data = fetch_main_contract(symbol)
        if data:
            results[symbol] = {
                'name': info['name'],
                'price': data['price'],
                'unit': info['unit'],
                'group': info['group'],
                'change': data['change'],
                'change_pct': data['change_pct'],
                'open': data['open'],
                'high': data['high'],
                'low': data['low'],
                'prev_close': data['prev_close'],
                'contract': '主力连续',
            }
            success_count += 1
            print(f'✅ {data["price"]:,.2f} {info["unit"]}')
        else:
            print('❌ 无数据')

        # 避免请求过快，加一个小延迟
        time.sleep(0.2)

    print('=' * 60)
    print(f'✅ 成功获取 {success_count}/{len(SYMBOLS)} 个品种')
    return results

# ============================================================
# 保存与更新
# ============================================================

def update_latest(data):
    if not data:
        return
    os.makedirs('data', exist_ok=True)
    output = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'source': 'AKShare (期货主力 + 黄金现货)',
        'note': '黄金使用AU9999现货，其他为期货主力连续合约',
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
        unit = info.get('unit', '')
        price = info.get('price', 0)
        print(f'  {info["name"]}：{price:,.2f} {unit}')
    print('=' * 60)

def main():
    print('=' * 60)
    print('📊 金属期货价格获取工具 (AKShare)')
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
