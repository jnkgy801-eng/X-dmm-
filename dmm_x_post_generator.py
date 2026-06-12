"""
💰🐦 DMMアフィリエイト → X（Twitter）投稿文ジェネレーター
DMM/FANZAから商品情報を取得し、X投稿用テキストを保存します。
FANZA同人(doujin)に完全対応しました。
"""

import os
import sys
import datetime
import requests
import random
from pathlib import Path

# ================================================================
# ⚙️ 設定（環境変数から読み込み）
# ================================================================

DMM_API_ID       = os.environ.get('DMM_API_ID', '')
DMM_AFFILIATE_ID = os.environ.get('DMM_AFFILIATE_ID', '')

if not DMM_API_ID or not DMM_AFFILIATE_ID:
    print('❌ 環境変数 DMM_API_ID / DMM_AFFILIATE_ID が設定されていません。')
    sys.exit(1)

print('✅ 認証情報を読み込みました。')

DMM_FLOOR = os.environ.get('DMM_FLOOR', 'videoa')
DMM_SORT_MODE = os.environ.get('DMM_SORT_MODE', 'both').lower()
POST_START_INDEX = int(os.environ.get('POST_START_INDEX', '1'))
DMM_PRICE_RANGE = os.environ.get('DMM_PRICE_RANGE', 'all')
SAVE_TO_REPO = os.environ.get('SAVE_TO_REPO', 'false').lower() == 'true'

SORT_TARGETS = {
    'both': [('date', '新着順'), ('rank', '人気順')],
    'date': [('date', '新着順')],
    'rank': [('rank', '人気順')]
}

SORT_LIST = SORT_TARGETS.get(DMM_SORT_MODE, SORT_TARGETS['both'])

# 価格レンジ解析
PRICE_RANGE_BOUNDS = None
if DMM_PRICE_RANGE != 'all' and '-' in DMM_PRICE_RANGE:
    try:
        low, high = map(int, DMM_PRICE_RANGE.split('-'))
        PRICE_RANGE_BOUNDS = (low, high)
    except:
        pass

# フロア設定マッピング
# FANZA同人の場合は site='FANZA', service='digital', floor='doujin' となるように自動判定
def get_floor_params(floor_name):
    # デフォルトはvideoa(ビデオ)
    params = {
        'site': 'FANZA',
        'service': 'digital',
        'floor': 'videoa'
    }
    
    if floor_name == 'videoa':
        params.update({'service': 'digital', 'floor': 'videoa', 'site': 'FANZA'})
    elif floor_name == 'videoc':
        params.update({'service': 'digital', 'floor': 'videoc', 'site': 'FANZA'})
    elif floor_name == 'anime':
        params.update({'service': 'digital', 'floor': 'anime', 'site': 'FANZA'})
    elif floor_name == 'doujin':
        params.update({'service': 'digital', 'floor': 'doujin', 'site': 'FANZA'}) # FANZA同人
    elif floor_name == 'comic':
        params.update({'service': 'digital', 'floor': 'comic', 'site': 'FANZA'})
    elif floor_name == 'goods':
        params.update({'service': 'mono', 'floor': 'goods', 'site': 'DMM'})
    else:
        params.update({'service': 'digital', 'floor': floor_name})
    return params

def fetch_dmm_products(sort_key, sort_label):
    url = "https://api.dmm.com/affiliate/v3/ItemList"
    floor_p = get_floor_params(DMM_FLOOR)
    
    params = {
        "api_id": DMM_API_ID,
        "affiliate_id": DMM_AFFILIATE_ID,
        "site": floor_p['site'],
        "service": floor_p['service'],
        "floor": floor_p['floor'],
        "hits": 20,
        "offset": POST_START_INDEX,
        "sort": sort_key,
        "output": "json"
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        return data.get("result", {}).get("items", [])
    except Exception as e:
        print(f"  ⚠️ APIエラー [{sort_label}]: {e}")
        return []

def parse_product(item):
    # 価格取得
    price = "不明"
    if "prices" in item:
        price_val = item["prices"].get("price")
        if price_val is not None:
            price = f"¥{int(price_val):,}"
        elif "deliveries" in item and "delivery" in item["deliveries"]:
            # 電子等の価格
            deliv = item["deliveries"]["delivery"]
            if isinstance(deliv, list) and len(deliv) > 0:
                price_val = deliv[0].get("price")
            elif isinstance(deliv, dict):
                price_val = deliv.get("price")
            if price_val is not None:
                price = f"¥{int(price_val):,}"

    # 作者・サークル・女優などのハッシュタグ用
    tags = []
    if "iteminfo" in item:
        info = item["iteminfo"]
        # 同人サークル
        if "maker" in info:
            tags.extend([m.get("name") for m in info["maker"] if m.get("name")])
        # 女優(ビデオ)
        elif "actress" in info:
            tags.extend([a.get("name") for a in info["actress"] if a.get("name")])
        # 作者(コミックなど)
        elif "author" in info:
            tags.extend([a.get("name") for a in info["author"] if a.get("name")])

    # サンプル動画・プレビューURL
    sample_url = ""
    if "sampleMovieURL" in item:
        sample_url = item["sampleMovieURL"].get("size_720_480") or item["sampleMovieURL"].get("size_476_306") or ""

    return {
        "title": item.get("title", "無題の商品"),
        "url": item.get("affiliateURL", item.get("url", "")),
        "price": price,
        "price_raw": item.get("prices", {}).get("price") or 0,
        "tags": list(set(tags))[:3], # 最大3つ
        "sample_url": sample_url,
        "cid": item.get("content_id", "")
    }

def price_in_range(p):
    if not PRICE_RANGE_BOUNDS:
        return True
    try:
        val = int(p["price_raw"])
        return PRICE_RANGE_BOUNDS[0] <= val <= PRICE_RANGE_BOUNDS[1]
    except:
        return True

def build_x_post(p):
    # X（Twitter）用の投稿文を作成
    title = p["title"]
    if len(title) > 50:
        title = title[:47] + "..."

    # 同人フロアに合わせた絵文字や文言の調整
    icon = "🎨" if DMM_FLOOR == "doujin" else "🎬"
    floor_tag = "#FANZA同人 #同人誌" if DMM_FLOOR == "doujin" else "#FANZA #録画"
    if DMM_FLOOR == "comic":
        icon = "📖"
        floor_tag = "#FANZAコミック"

    tag_str = " ".join([f"#{t.replace(' ', '').replace(' ', '')}" for t in p["tags"]])
    
    # 【修正箇所】トリプルクォーテーションに変更し、改行が崩れないように修正
    text = f"""{icon} {title}

注目作品を今すぐチェック！✨

💰 価格: {p['price']}
"""
    if tag_str:
        text += f"👤 {tag_str}\n"
    
    text += f"\n{p['url']}\n"
    
    if p['sample_url']:
        text += f"▶ サンプル動画あり\n"
        
    text += f"{floor_tag} #PR"
    return text

def save_output(all_sections):
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dmm_x_posts_{now}.txt"
    
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    filepath = out_dir / filename
    
    total_posts = sum(len(posts) for _, posts in all_sections)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# DMM/FANZAアフィリエイト X投稿文\n")
        f.write(f"# 生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# フロア: {DMM_FLOOR} / モード: {DMM_SORT_MODE}\n")
        f.write(f"# 価格フィルター: {DMM_PRICE_RANGE}\n")
        f.write(f"# 取得開始インデックス: {POST_START_INDEX}\n")
        f.write(f"# 総投稿数: {total_posts}件\n")
        f.write(f"============================================================\n\n")
        
        for label, posts in all_sections:
            f.write(f"============================================================\n")
            f.write(f"【{label}】{len(posts)}件\n")
            f.write(f"============================================================\n\n")
            
            for i, (p, text) in enumerate(posts, 1):
                f.write(f"--- {label} {i}/{len(posts)} ---\n")
                f.write(f"商品名: {p['title']}\n")
                f.write(f"文字数: {len(text)}文字\n")
                f.write(f"URL: {p['url']}\n")
                if p['sample_url']:
                    f.write(f"サンプル: {p['sample_url']}\n")
                f.write(f"----------------------------------------\n")
                f.write(f"{text}\n\n")
                
    print(f'\n💾 保存完了！')
    print(f'📄 ファイル: {filepath}')
    return filepath

if __name__ == "__main__":
    print(f'🛍️ DMM/FANZAから商品情報を取得中（フロア: {DMM_FLOOR} / モード: {DMM_SORT_MODE}）...')
    all_sections = []

    for sort_key, sort_label in SORT_LIST:
        raw_items = fetch_dmm_products(sort_key, sort_label)
        if not raw_items:
            print(f'  ⚠️ [{sort_label}] 商品が取得できませんでした。スキップします。')
            continue

        products = [parse_product(item) for item in raw_items]

        if PRICE_RANGE_BOUNDS:
            before_count = len(products)
            products = [p for p in products if price_in_range(p)]
            print(f'  💰 価格フィルター適用: {before_count}件 → {len(products)}件')

        if not products:
            print(f'  ⚠️ [{sort_label}] 価格条件に合う商品がありませんでした。スキップします。')
            continue

        print(f'  📝 [{sort_label}] 投稿文を生成中...')
        posts = []
        for p in products:
            text = build_x_post(p)
            posts.append((p, text))
            print(f"    ✅ [{len(text)}文字] {p['title'][:30]}...")

        all_sections.append((sort_label, posts))

    if all_sections:
        save_output(all_sections)
    else:
        print("❌ 投稿文を生成できる商品がありませんでした。")
