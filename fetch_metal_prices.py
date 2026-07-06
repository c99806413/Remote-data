import json
import os
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd

# ============================================================
# 配置
# ============================================================

# 品种代码映射（akshare 中的品种代码 → 显示名称 + 单位 + 合理区间）
# akshare 返回的 product 字段是小写代码
SYMBOLS = {
    'cu': {'name': '沪铜', 'unit': '元/吨', 'min_val': 60000, 'max_val': 90000},
    'al': {'name': '沪铝', 'unit': '元/吨', 'min_val': 16000, 'max_val': 25000},
    'zn': {'name': '沪锌', 'unit': '元/吨', 'min_val': 18000, 'max_val': 30000},
    'pb': {'name': '沪铅', 'unit': '元/吨', 'min_val': 14000, 'max_val': 22000},
    'ni': {'name': '沪镍', 'unit': '元/吨', 'min_val': 100000, 'max_val': 200000},
    'sn': {'name': '沪锡', 'unit': '元/吨', 'min_val': 150000, 'max_val': 300000},
    'au': {'name': '沪金', 'unit': '元/克', 'min_val': 800, 'max_val': 1000},      # ✅ 黄金
    'ag': {'name': '沪银', 'unit': '元/千克', 'min_val': 14000, 'max_val': 18000}, # ✅ 白银
    'rb': {'name': '螺纹钢', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4000},
    'hc': {'name': '热轧卷板', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'wr': {'name': '线材', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'i': {'name': '铁矿石', 'unit': '元/吨', 'min_val': 600, 'max_val': 1000},
    'ss': {'name': '不锈钢', 'unit': '元/吨', 'min_val': 12000, 'max_val': 20000},
    'si': {'name': '工业硅', 'unit': '元/吨', 'min_val': 10000, 'max_val': 20000},
    'lc': {'name': '碳酸锂', 'unit': '元/吨', 'min_val': 50000, 'max_val': 150000},
    'ao': {'name': '氧化铝', 'unit': '元/吨', 'min_val': 2500, 'max_val': 5000},
}

# 主力合约代码（akshare 中查询时用）
# 格式：品种代码 + 主力月份，如 cu 的主力是 cu2508
# 也可以直接用 'CU0' 这种新浪代码，但 akshare 需要的是具体合约或连续合约标识
# 使用 akshare 的 futures_daily_bar 接口，传入 'CU' 这种简写即可
HISTORY_DAYS = 365

# ============================================================
# 核心获取函数（使用 akshare）
# ============================================================

def fetch_akshare():
    """
    使用 akshare 获取上期所所有品种的日度数据
    返回字典：{ 'cu': {'price': xxx, 'change': xxx, ...}, ... }
    """
    results = {}
    
    # 获取最近一个交易日（akshare 会自动返回最新交易日的数据）
    # 使用 futures_daily_bar 获取上期所所有品种的日度数据
    try:
        # 获取上期所日度数据（返回所有品种）
        df = ak.futures_daily_bar(market="SHFE")
        if df is None or df.empty:
            print("❌ akshare 返回空数据")
            return results
        
        print(f"✅ 成功获取 {len(df)} 条数据记录")
        print(f"📋 数据字段: {df.columns.tolist()}")
        print(f"📋 品种列表: {df['product'].unique().tolist()}")
        
        # 按品种分组，取每个品种的最新一条记录（主力合约）
        # 通常每个品种有多个月份合约，我们取成交量最大的作为主力
        df_latest = df.sort_values(['product', 'volume'], ascending=[True, False])
        df_main = df_latest.drop_duplicates(subset=['product'], keep='first')
        
        print(f"📋 主力合约品种: {df_main['product'].tolist()}")
        
        # 遍历每个品种，提取数据
        for _, row in df_main.iterrows():
            code = row['product']  # 小写代码，如 'cu', 'au', 'ag'
            if code not in SYMBOLS:
                continue  # 只处理我们配置的品种
            
            info = SYMBOLS[code]
            
            # 提取价格数据
            price = float(row['close']) if pd.notna(row['close']) else 0
            open_price = float(row['open']) if pd.notna(row['open']) else 0
            high = float(row['high']) if pd.notna(row['high']) else 0
            low = float(row['low']) if pd.notna(row['low']) else 0
            prev_close = float(row['pre_close']) if pd.notna(row['pre_close']) else 0
            volume = float(row['volume']) if pd.notna(row['volume']) else 0
            
            # 计算涨跌额和涨跌幅
            change = price - prev_close if prev_close > 0 else 0
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            # 合理性校验
            if info['min_val'] <= price <= info['max_val']:
                results[code] = {
                    'name': info['name'],
                    'price': price,
                    'unit': info['unit'],
                    'change': change,
                    'change_pct': f"{change_pct:.2f}",
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'prev_close': prev_close,
                    'volume': volume,  # 额外保留成交量
                    'contract': row.get('symbol', ''),  # 合约代码
                }
                print(f"  ✅ {info['name']}: {price:.2f} {info['unit']} (涨跌幅: {change_pct:.2f}%)")
            else:
                print(f"  ⚠️ {info['name']} 价格 {price} 超出合理区间 [{info['min_val']}, {info['max_val']}]，跳过")
        
        print(f"✅ 成功获取 {len(results)} 个品种的数据")
        return results
        
    except Exception as e:
        print(f"❌ akshare 获取失败: {e}")
        import traceback
        traceback.print_exc()
        return results


def fetch_all_metals():
    """主入口：调用 akshare 获取数据"""
    print('🔄 开始获取金属价格数据 (akshare)')
    print('=' * 60)
    return fetch_akshare()


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
        'source': 'akshare (上期所官方数据)',
        'note': '数据来自上海期货交易所日度结算价，T+1更新',
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
    # 删除今天已有的记录（防止重复）
    history['records'] = [r for r in history['records'] if r.get('date') != today]
    # 添加新记录
    history['records'].append({'date': today, 'rates': data})
    # 按日期排序
    history['records'] = sorted(history['records'], key=lambda x: x['date'])
    # 只保留最近 HISTORY_DAYS 天
    cutoff = (datetime.utcnow() - timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')
    history['records'] = [r for r in history['records'] if r['date'] >= cutoff]

    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f'✅ 历史记录已保存到 data/metal_history.json (共 {len(history["records"])} 条)')


def print_summary(data):
    if not data:
        return
    print('\n' + '=' * 60)
    print('📊 行情汇总')
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
    print('=' * 60)
    print('📊 金属期货价格获取工具 (akshare)')
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
