"""
💰🐦 DMMアフィリエイト → X（Twitter）投稿文ジェネレーター
DMMから商品情報を取得し、X投稿用テキストをデスクトップに保存します。
（X APIは使わないので完全無料で動作します）
"""

import os
import sys
import json
import datetime
import requests

# ================================================================
# ⚙️  設定（環境変数から読み込み）
# ================================================================

DMM_API_ID       = os.environ.get('DMM_API_ID', '')
DMM_AFFILIATE_ID = os.environ.get('DMM_AFFILIATE_ID', '')

if not DMM_API_ID or not DMM_AFFILIATE_ID:
    print('❌ 環境変数 DMM_API_ID / DMM_AFFILIATE_ID が設定されていません。')
    sys.exit(1)

print('✅ 認証情報を読み込みました。')

DMM_FLOOR = os.environ.get('DMM_FLOOR', 'videoa')
DMM_SORT  = os.environ.get('DMM_SORT', '-date')
DMM_HITS  = int(os.environ.get('DMM_HITS', '20'))
POST_ALL  = os.environ.get('POST_ALL', 'false').lower() == 'true'
POST_INDEX = int(os.environ.get('POST_INDEX', '0'))

DMM_API_BASE = 'https://api.dmm.com/affiliate/v3'

FLOOR_SERVICE_MAP = {
    'videoa':  ('digital', 'videoa'),
    'videoc':  ('digital', 'videoc'),
    'anime':   ('digital', 'anime'),
    'doujin':  ('doujin',  'digital_doujin'),
    'comic':   ('ebook',   'comic'),
    'goods':   ('mono',    'goods'),
    'digital': ('digital', 'videoa'),
}

HASHTAG_MAP = {
    'videoa': '#FANZA #DMM #アダルト #PR #アフィリエイト #新着',
    'videoc': '#FANZA #DMM #素人 #PR #アフィリエイト #新着',
    'anime':  '#FANZA #DMM #アニメ #PR #アフィリエイト #新着',
    'doujin': '#FANZA #DMM #同人 #PR #アフィリエイト #新着',
    'comic':  '#DMM #電子書籍 #漫画 #PR #アフィリエイト #新着',
    'goods':  '#DMM #グッズ #PR #アフィリエイト #新着',
    'default': '#DMM #PR #アフィリエイト #新着',
}

# ================================================================
# 🔧 DMM API 関数
# ================================================================

def fetch_dmm_products():
    service, floor_name = FLOOR_SERVICE_MAP.get(DMM_FLOOR, ('digital', 'videoa'))
    params = {
        'api_id':       DMM_API_ID,
        'affiliate_id': DMM_AFFILIATE_ID,
        'site':         'FANZA',
        'service':      service,
        'floor':        floor_name,
        'hits':         DMM_HITS,
        'sort':         DMM_SORT,
        'output':       'json',
    }
    try:
        resp = requests.get(f'{DMM_API_BASE}/ItemList', params=params, timeout=15)
        data = resp.json()
        items = data.get('result', {}).get('items', [])
        if isinstance(items, dict):
            items = items.get('item', [])
        print(f'  ✅ {len(items)} 件の商品を取得しました。')
        return items
    except Exception as e:
        print(f'  ❌ DMM APIエラー: {e}')
        return []


def parse_product(item):
    title         = item.get('title', '')
    affiliate_url = item.get('affiliateURL', '') or item.get('URL', '')
    prices        = item.get('prices', {})
    price_str     = ''
    if prices:
        price_val = prices.get('price') or prices.get('list_price') or ''
        if price_val:
            price_num = ''.join(c for c in str(price_val) if c.isdigit())
            price_str = f'¥{int(price_num):,}' if price_num else ''
    actors = [a.get('name', '') for a in (item.get('iteminfo', {}).get('actress') or [])][:3]
    genres = [g.get('name', '') for g in (item.get('iteminfo', {}).get('genre') or [])][:3]
    maker  = ((item.get('iteminfo', {}).get('maker') or [{}])[0]).get('name', '')
    return {
        'title':         title,
        'affiliate_url': affiliate_url,
        'price':         price_str,
        'actors':        actors,
        'genres':        genres,
        'maker':         maker,
    }

# ================================================================
# 📝 X投稿文生成（280文字制限を考慮）
# ================================================================

def clean_url(url):
    """URLの不正文字を除去・検証する"""
    if not url:
        return ''
    # 前後の空白・改行を除去
    url = url.strip()
    # 全角文字や改行が混入している場合を除去
    url = url.replace('\n', '').replace('\r', '').replace('　', '')
    # URLが正しく始まっているか確認
    if not url.startswith('http'):
        return ''
    return url


def build_x_post(product):
    hashtags = HASHTAG_MAP.get(DMM_FLOOR, HASHTAG_MAP['default'])
    url      = clean_url(product['affiliate_url'])

    # タイトルを短縮（長すぎる場合）
    title = product['title']
    if len(title) > 40:
        title = title[:40] + '…'

    lines = []
    lines.append(f"🎬 {title}")
    lines.append('')
    if product['price']:
        lines.append(f"💰 {product['price']}")
    if product['actors']:
        lines.append(f"👤 {'　'.join(product['actors'])}")
    if product['genres']:
        lines.append(f"🎞 {'　'.join(product['genres'][:2])}")
    lines.append('')
    lines.append('✅ 詳細・購入はこちら👇')
    lines.append(url)
    lines.append('')
    lines.append('※アフィリエイト広告')
    lines.append(hashtags)

    text = '\n'.join(lines)

    # 280文字を超える場合は調整
    if len(text) > 280:
        lines2 = []
        lines2.append(f"🎬 {title}")
        lines2.append('')
        if product['price']:
            lines2.append(f"💰 {product['price']}")
        lines2.append('')
        lines2.append('✅ 詳細はこちら👇')
        lines2.append(url)
        lines2.append('')
        lines2.append('※アフィリエイト広告')
        lines2.append(hashtags)
        text = '\n'.join(lines2)

    return text

# ================================================================
# 💾 デスクトップへの保存
# ================================================================

def get_save_dir():
    """保存先ディレクトリを返す（デスクトップ優先）"""
    # デスクトップのパスを試す
    candidates = [
        os.path.join(os.path.expanduser('~'), 'Desktop'),
        os.path.join(os.path.expanduser('~'), 'デスクトップ'),
        os.path.expanduser('~'),  # フォールバック
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return '.'


def save_posts(posts):
    save_dir  = get_save_dir()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f'dmm_x_posts_{timestamp}.txt'
    filepath  = os.path.join(save_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# DMMアフィリエイト X投稿文\n")
        f.write(f"# 生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# フロア: {DMM_FLOOR} / ソート: {DMM_SORT}\n")
        f.write(f"# 投稿数: {len(posts)}件\n")
        f.write("=" * 60 + "\n\n")

        for i, (product, text) in enumerate(posts, 1):
            f.write(f"【投稿 {i}/{len(posts)}】\n")
            f.write(f"商品名: {product['title']}\n")
            f.write(f"文字数: {len(text)}文字\n")
            f.write(f"URL確認: {product['affiliate_url']}\n")
            f.write("-" * 40 + "\n")
            f.write(text)
            f.write("\n\n" + "=" * 60 + "\n\n")

    print(f'\n💾 保存完了！')
    print(f'📄 ファイル: {filepath}')
    return filepath

# ================================================================
# 🚀 メイン実行
# ================================================================

print(f'🛍️  DMMから商品情報を取得中（フロア: {DMM_FLOOR} / ソート: {DMM_SORT}）...')
raw_items = fetch_dmm_products()

if not raw_items:
    print('❌ 商品が1件も取得できませんでした。')
    sys.exit(1)

products = [parse_product(item) for item in raw_items]
print(f'\n合計 {len(products)} 件の商品を処理します。\n')

# 投稿文を生成
print('📝 X投稿文を生成中...')
posts = []

if POST_ALL:
    targets = products
else:
    if POST_INDEX >= len(products):
        print(f'❌ POST_INDEX={POST_INDEX} が範囲外です（0〜{len(products)-1}）')
        sys.exit(1)
    targets = [products[POST_INDEX]]

for p in targets:
    text = build_x_post(p)
    posts.append((p, text))
    title_short = p['title'][:30]
    print(f"  ✅ [{len(text)}文字] {title_short}...")

# ターミナルにプレビュー表示
print('\n' + '=' * 60)
print('📋 投稿文プレビュー（最初の1件）')
print('=' * 60)
print(posts[0][1])
print('=' * 60)

# ファイルに保存
save_posts(posts)
print(f'\n✅ 完了！テキストファイルを開いてXに手動投稿してください。')
