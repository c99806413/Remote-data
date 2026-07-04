import json
import os
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd

# ============================================================
# 配置
# ============================================================

# 目标品种及对应信息
SYMBOLS = {
    'CU': {'name': '沪铜', 'unit': '元/吨', 'group': '有色金属'},
    'AL': {'name': '沪铝', 'unit': '元/吨', 'group': '有色金属'},
    'ZN': {'name': '沪锌', 'unit': '元/吨', 'group': '有色金属'},
    'PB': {'name': '沪铅', 'unit': '元/吨', 'group': '有色金属'},
    'NI': {'name': '沪镍', 'unit': '元/吨', 'group': '有色金属'},
    'SN': {'name': '沪锡', 'unit': '元/吨', 'group': '有色金属'},
    'AU': {'name': '沪金', 'unit': '元/克', 'group': '贵金属'},   # 黄金期货（备用）
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
# 核心获取函数
# ============================================================

def fetch_futures_spot():
    """
    使用 AKShare 的 futures_zh_spot() 获取所有期货合约实时行情
    返回 DataFrame，包含所有品种所有合约的最新数据
    """
    try:
        df = ak.futures_zh_spot()
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print(f'❌ 获取期货行情失败: {e}')
        return None

def get_main_contract_price(df, symbol):
    """
    从全市场 DataFrame 中提取指定品种的主力合约价格
    主力合约 = 成交量最大的合约
    """
    try:
        # 筛选品种
        subset = df[df['品种代码'] == symbol]
        if subset.empty:
            return None
        
        # 过滤无效数据（最新价为0或空）
        subset = subset[subset['最新价'] > 0]
        if subset.empty:
            return None
        
        # 按成交量降序排序，取第一个
        main = subset.sort_values('成交量', ascending=False).iloc[0]
        return {
            'price': float(main['最新价']),
            'volume': int(main['成交量']),
            'open': float(main['今开']),
            'high': float(main['最高']),
            'low': float(main['最低']),
            'prev_close': float(main['昨收']),
            'change': float(main['涨跌额']) if '涨跌额' in main else 0,
            'change_pct': str(main['涨跌幅']) if '涨跌幅' in main else '0',
            'contract': main['合约名称'] if '合约名称' in main else '',
        }
    except Exception as e:
        print(f'⚠️ 处理 {symbol} 异常: {e}')
        return None

def fetch_gold_spot():
    """
    获取黄金现货价格（AU9999），用于替代期货价格（更接近回收价）
    """
    try:
        df = ak.spot_gold()
        if df is None or df.empty:
            return None
        # 取第一行（最新）
        latest = df.iloc[-1]  # 通常最新一行是最近数据
        price = float(latest['最新价'])
        if price <= 0:
            return None
        return price
    except Exception as e:
        print(f'⚠️ 获取黄金现货失败: {e}')
        return None

# ============================================================
# 主流程
# ============================================================

def fetch_all_metals():
    results = {}
    success_count = 0

    print('🔄 开始获取金属价格数据 (AKShare)')
    print('=' * 60)

    # 1. 获取全市场期货数据
    df = fetch_futures_spot()
    if df is None:
        print('❌ 无法获取期货数据，请检查网络或 AKShare 版本')
        return {}

    # 2. 逐个品种提取
    for symbol, info in SYMBOLS.items():
        print(f'📊 获取 {info["name"]} ({symbol})...', end=' ')

        # 特殊处理黄金：优先使用现货价格
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
            else:
                print('⚠️ 现货获取失败，尝试期货...', end=' ')

        # 其他品种从期货数据中提取
        data = get_main_contract_price(df, symbol)
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
                'contract': data['contract'],
            }
            success_count += 1
            print(f'✅ {data["price"]:,.2f} {info["unit"]}')
        else:
            print('❌ 无数据')

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
        'source': 'AKShare (上海期货交易所 + 上海黄金交易所)',
        'note': '主力合约自动识别，黄金使用AU9999现货价格',
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
    # 移除今天的旧记录（如果存在）
    history['records'] = [r for r in history['records'] if r.get('date') != today]
    history['records'].append(today_record)
    history['records'] = sorted(history['records'], key=lambda x: x['date'])
    # 只保留最近 HISTORY_DAYS 天
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
