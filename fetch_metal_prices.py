import json
import os
from datetime import datetime, timedelta
import akshare as ak
import pandas as pd

# ============================================================
# 配置
# ============================================================

# 品种代码映射（akshare 返回的 product 字段是大写代码，如 'CU', 'AU', 'AG'）
SYMBOLS = {
    'CU': {'name': '沪铜', 'unit': '元/吨', 'min_val': 60000, 'max_val': 90000},
    'AL': {'name': '沪铝', 'unit': '元/吨', 'min_val': 16000, 'max_val': 25000},
    'ZN': {'name': '沪锌', 'unit': '元/吨', 'min_val': 18000, 'max_val': 30000},
    'PB': {'name': '沪铅', 'unit': '元/吨', 'min_val': 14000, 'max_val': 22000},
    'NI': {'name': '沪镍', 'unit': '元/吨', 'min_val': 100000, 'max_val': 200000},
    'SN': {'name': '沪锡', 'unit': '元/吨', 'min_val': 150000, 'max_val': 300000},
    'AU': {'name': '沪金', 'unit': '元/克', 'min_val': 800, 'max_val': 1000},       # ✅ 黄金
    'AG': {'name': '沪银', 'unit': '元/千克', 'min_val': 14000, 'max_val': 18000},  # ✅ 白银
    'RB': {'name': '螺纹钢', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4000},
    'HC': {'name': '热轧卷板', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'WR': {'name': '线材', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    'I': {'name': '铁矿石', 'unit': '元/吨', 'min_val': 600, 'max_val': 1000},
    'SS': {'name': '不锈钢', 'unit': '元/吨', 'min_val': 12000, 'max_val': 20000},
    'SI': {'name': '工业硅', 'unit': '元/吨', 'min_val': 10000, 'max_val': 20000},
    'LC': {'name': '碳酸锂', 'unit': '元/吨', 'min_val': 50000, 'max_val': 150000},
    'AO': {'name': '氧化铝', 'unit': '元/吨', 'min_val': 2500, 'max_val': 5000},
}

HISTORY_DAYS = 365

# ============================================================
# 核心获取函数（使用 akshare get_futures_daily）
# ============================================================

def fetch_akshare():
    """
    使用 akshare 的 get_futures_daily 获取上期所日度数据
    """
    results = {}
    
    try:
        # 获取最近一个交易日的数据
        # 日期格式可以是 "YYYYMMDD" 或 "YYYY-MM-DD"
        today = datetime.now()
        end_date = today.strftime("%Y%m%d")
        # 往前推5天，确保覆盖到最近一个交易日
        start_date = (today - timedelta(days=10)).strftime("%Y%m%d")
        
        print(f"📅 获取日期范围: {start_date} 至 {end_date}")
        print("📊 正在调用 get_futures_daily(market='SHFE')...")
        
        # 正确的函数名是 get_futures_daily[reference:4]
        df = ak.get_futures_daily(
            start_date=start_date,
            end_date=end_date,
            market="SHFE"  # 上期所
        )
        
        if df is None or df.empty:
            print("❌ get_futures_daily 返回空数据")
            return results
        
        print(f"✅ 成功获取 {len(df)} 条数据记录")
        print(f"📋 数据字段: {df.columns.tolist()}")
        
        # 获取所有品种列表
        products = df['product'].unique().tolist() if 'product' in df.columns else []
        print(f"📋 品种列表: {products}")
        
        # 获取最新日期
        if 'date' in df.columns:
            latest_date = df['date'].max()
            print(f"📅 最新数据日期: {latest_date}")
            # 只保留最新一天的数据
            df_latest = df[df['date'] == latest_date]
        else:
            # 如果没有 date 列，按日期索引取最后一天
            df_latest = df.groupby('product').last().reset_index()
        
        # 按品种分组，取每个品种的最新记录
        # 如果有多个合约，取成交量最大的作为主力
        if 'volume' in df_latest.columns:
            df_main = df_latest.sort_values(['product', 'volume'], ascending=[True, False])
            df_main = df_main.drop_duplicates(subset=['product'], keep='first')
        else:
            df_main = df_latest.drop_duplicates(subset=['product'], keep='first')
        
        print(f"📋 主力合约品种: {df_main['product'].tolist() if 'product' in df_main.columns else '未知'}")
        
        # 遍历每个品种
        for _, row in df_main.iterrows():
            code = row['product']  # 大写代码，如 'CU', 'AU', 'AG'
            
            # 只处理我们配置的品种
            if code not in SYMBOLS:
                continue
            
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
                    'volume': volume,
                    'contract': row.get('symbol', ''),
                    'date': row.get('date', '')
                }
                arrow = '↑' if change_pct > 0 else '↓' if change_pct < 0 else '→'
                print(f"  ✅ {info['name']}: {price:.2f} {info['unit']} {arrow} {abs(change_pct):.2f}%")
            else:
                print(f"  ⚠️ {info['name']} 价格 {price} 超出合理区间 [{info['min_val']}, {info['max_val']}]，跳过")
        
        print(f"✅ 成功获取 {len(results)} 个品种的数据")
        return results
        
    except AttributeError as e:
        print(f"❌ 函数不存在: {e}")
        print("💡 请确认 akshare 版本: pip show akshare")
        print("💡 如果版本过旧，请升级: pip install akshare --upgrade")
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
# 保存与更新（保持不变）
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
        'note': '数据来自上海期货交易所日度结算价',
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
