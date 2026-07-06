import requests
import json
import os
import re
from datetime import datetime, timedelta

# ============================================================
# 配置：定义需要抓取的品种及对应的合理价格区间
# ============================================================
SYMBOLS = {
    '黄金': {'code': 'AU', 'name': '沪金', 'unit': '元/克', 'min_val': 800, 'max_val': 1000},
    '白银': {'code': 'AG', 'name': '沪银', 'unit': '元/千克', 'min_val': 14000, 'max_val': 18000},
    '铜':   {'code': 'CU', 'name': '沪铜', 'unit': '元/吨', 'min_val': 60000, 'max_val': 90000},
    '铝':   {'code': 'AL', 'name': '沪铝', 'unit': '元/吨', 'min_val': 16000, 'max_val': 25000},
    '锌':   {'code': 'ZN', 'name': '沪锌', 'unit': '元/吨', 'min_val': 18000, 'max_val': 30000},
    '铅':   {'code': 'PB', 'name': '沪铅', 'unit': '元/吨', 'min_val': 14000, 'max_val': 22000},
    '镍':   {'code': 'NI', 'name': '沪镍', 'unit': '元/吨', 'min_val': 100000, 'max_val': 200000},
    '锡':   {'code': 'SN', 'name': '沪锡', 'unit': '元/吨', 'min_val': 150000, 'max_val': 300000},
    '螺纹钢': {'code': 'RB', 'name': '螺纹钢', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4000},
    '热轧卷板': {'code': 'HC', 'name': '热轧卷板', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    '线材': {'code': 'WR', 'name': '线材', 'unit': '元/吨', 'min_val': 2800, 'max_val': 4200},
    '不锈钢': {'code': 'SS', 'name': '不锈钢', 'unit': '元/吨', 'min_val': 12000, 'max_val': 20000},
    '氧化铝': {'code': 'AO', 'name': '氧化铝', 'unit': '元/吨', 'min_val': 2500, 'max_val': 5000},
}

HISTORY_DAYS = 365

# ============================================================
# 核心抓取逻辑
# ============================================================

def fetch_shfe():
    """抓取上期所日度数据页面，解析所有品种的主力合约"""
    url = 'https://www.shfe.cn/reports/tradedata/dailyandweeklydata/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.shfe.cn/'
    }
    
    print(f'📡 正在请求上期所数据...')
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.encoding = 'utf-8'
        if resp.status_code != 200:
            print(f'❌ HTTP 状态码异常: {resp.status_code}')
            return None
        html = resp.text
    except Exception as e:
        print(f'❌ 网络请求失败: {e}')
        return None

    print(f'✅ 页面获取成功 (长度: {len(html)} 字符)')
    results = {}

    # 遍历配置中的每个品种
    for product_name, info in SYMBOLS.items():
        print(f'🔍 正在解析: {product_name}...', end=' ')
        
        # 1. 截取该品种的数据区块
        # 注意：页面中是 "商品名称黄金" 无冒号，且后面紧跟换行
        pattern_block = rf'商品名称{product_name}\s*\n(.*?)(?=商品名称|小计|$)'
        block_match = re.search(pattern_block, html, re.DOTALL)
        if not block_match:
            print('❌ 未找到数据区块')
            continue
        
        block_text = block_match.group(1)
        
        # 2. 匹配该区块中的所有合约行
        # 格式示例: 2608  905.48  911.56  918.50  907.00  133396  12164570.33  136061  1013
        # 字段: 合约 | 前结算 | 开盘 | 最高 | 最低 | 收盘 | 成交手 | 成交额(万) | 持仓手 | 持仓变化
        # 注意：成交量和持仓量可能包含逗号(如 133,396)
        line_pattern = r'(\d{4})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d,]+)\s+([\d,.]+)\s+([\d,]+)\s+([\d-]+)'
        matches = re.findall(line_pattern, block_text)
        
        if not matches:
            print('❌ 未找到合约行数据')
            continue

        # 3. 挑选主力合约：成交量(索引6)最大的那行
        main_contract = None
        max_volume = 0
        for match in matches:
            try:
                # 去掉逗号并转为整数
                volume = int(match[6].replace(',', ''))
                if volume > max_volume:
                    max_volume = volume
                    main_contract = match
            except:
                continue

        if not main_contract:
            print('❌ 无法解析成交量')
            continue

        # 4. 提取数据
        try:
            contract_code = main_contract[0]
            close_price = float(main_contract[5])
            open_price = float(main_contract[2])
            high_price = float(main_contract[3])
            low_price = float(main_contract[4])
            prev_close = float(main_contract[1])
            volume = int(main_contract[6].replace(',', ''))
            
            # 计算涨跌额和涨跌幅
            change = close_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
            
            # 5. 合理性校验
            if not (info['min_val'] <= close_price <= info['max_val']):
                print(f'⚠️ 价格 {close_price} 超出合理区间，跳过')
                continue

            # 存入结果
            code = info['code']
            results[code] = {
                'name': info['name'],
                'price': close_price,
                'unit': info['unit'],
                'change': change,
                'change_pct': f"{change_pct:.2f}",
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'prev_close': prev_close,
                'volume': volume,
                'contract': contract_code,
            }
            arrow = '↑' if change_pct > 0 else '↓' if change_pct < 0 else '→'
            print(f'✅ {close_price:.2f} (主力: {contract_code}) {arrow} {abs(change_pct):.2f}%')
            
        except Exception as e:
            print(f'❌ 解析失败: {e}')

    print(f'📊 共成功解析 {len(results)} 个品种')
    return results

# ============================================================
# 保存与更新逻辑（保持与原有格式完全一致）
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
        'note': '数据来自上期所日度结算价，T+1更新，已自动选取主力合约',
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
    print(f'✅ 已更新 data/metal_history.json (共 {len(history["records"])} 条记录)')

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
    print('=' * 60)
    print('📊 金属期货价格获取工具 (上期所 SHFE)')
    print('=' * 60)
    print(f'⏰ 运行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('')

    data = fetch_shfe()
    if not data:
        print('❌ 未获取到任何有效数据，请检查网络或页面结构')
        return

    update_latest(data)
    update_history(data)
    print_summary(data)
    print('\n🎉 任务完成！')

if __name__ == '__main__':
    main()
