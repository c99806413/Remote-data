import json
import os
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd

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
# 核心获取函数（使用 futures_zh_spot_sina）
# ============================================================

def fetch_futures_spot_sina(symbol):
    """
    使用 AKShare 的 futures_zh_spot_sina 获取该品种所有合约的实时行情
    返回 DataFrame，含该品种所有合约
    """
    try:
        df = ak.futures_zh_spot_sina(symbol=symbol)
        if df is None or df.empty:
            return None
        # 过滤最新价 <= 0 的无效数据
        df = df[df['最新价'] > 0]
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f' 异常: {e}')
        return None

def get_main_contract_from_df(df):
    """
    从 DataFrame 中提取主力合约（成交量最大）
    返回一条 Series
    """
    if df is None or df.empty:
        return None
    # 按成交量降序
    main = df.sort_values('成交量', ascending=False).iloc[0]
    return main

def fetch_gold_spot():
    """
    尝试获取黄金现货价格（AU9999）
    """
    try:
        # 注意：不同版本函数名可能不同，尝试几种常见写法
        if hasattr(ak, 'spot_gold'):
            df = ak.spot_gold()
        elif hasattr(ak, 'gold_spot'):
            df = ak.gold_spot()
        elif hasattr(ak, 'gold_spot_df'):
            df = ak.gold_spot_df()
        else:
            return None
        if df is not None and not df.empty:
            # 取最新价（可能在不同列）
            if '最新价' in df.columns:
                price = float(df['最新价'].iloc[-1])
            elif 'price' in df.columns:
                price = float(df['price'].iloc[-1])
            else:
                # 尝试取第一列数值
                price = float(df.iloc[-1, 1])
            if price > 0:
                return price
    except Exception as e:
        print(f' 黄金现货异常: {e}')
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

        # 黄金特殊处理：优先现货
        if symbol == 'AU':
            gold_price = fetch_gold_spot()
            if gold_price:
                results[symbol] = {
                    'name': info['name'],
                    'price': gold_price,
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
                print(f'✅ {gold_price:,.2f} {info["unit"]} (现货)')
                continue

        # 期货数据获取
        df = fetch_futures_spot_sina(symbol)
        if df is not None:
            main = get_main_contract_from_df(df)
            if main is not None:
                # 提取字段
                results[symbol] = {
                    'name': info['name'],
                    'price': float(main['最新价']),
                    'unit': info['unit'],
                    'group': info['group'],
                    'change': float(main['涨跌额']) if '涨跌额' in main else 0,
                    'change_pct': str(main['涨跌幅']) if '涨跌幅' in main else '0',
                    'open': float(main['今开']) if '今开' in main else 0,
                    'high': float(main['最高']) if '最高' in main else 0,
                    'low': float(main['最低']) if '最低' in main else 0,
                    'prev_close': float(main['昨收']) if '昨收' in main else 0,
                    'contract': main['合约'] if '合约' in main else '',
                }
                success_count += 1
                print(f'✅ {results[symbol]["price"]:,.2f} {info["unit"]}')
                continue

        print('❌ 无数据')

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
        'source': 'AKShare (上海期货交易所 + 上海黄金交易所)',
        'note': '主力合约自动识别，黄金优先使用AU9999现货',
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
