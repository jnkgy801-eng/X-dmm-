"""
💰🐦 DMMアフィリエイト → X（Twitter）投稿文ジェネレーター
DMMから商品情報を取得し、X投稿用テキストをデスクトップに保存します。
（X APIは使わないので完全無料で動作します）
"""

import os
import sys
import datetime
import requests
import random
from pathlib import Path

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

# ----------------------------------------------------------------
# 📌 ソートモード設定
#    DMM_SORT_MODE=both（デフォルト）→ 新着20件 ＋ 人気20件 = 計40件を1ファイルに保存
#    DMM_SORT_MODE=date              → 新着順のみ20件
#    DMM_SORT_MODE=rank              → 人気順のみ20件
# ----------------------------------------------------------------
DMM_SORT_MODE = os.environ.get('DMM_SORT_MODE', 'both').lower()

SORT_TARGETS = {
    'both': [('-date', '新着順'), ('-rank', '人気順')],
    'date': [('-date', '新着順')],
    'rank': [('-rank', '人気順')],
}
SORT_LIST = SORT_TARGETS.get(DMM_SORT_MODE, SORT_TARGETS['both'])

# 取得開始位置（1始まり）・件数
POST_START_INDEX = int(os.environ.get('POST_START_INDEX', '1'))
FETCH_COUNT      = 20
DMM_OFFSET       = POST_START_INDEX
DMM_HITS         = FETCH_COUNT

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
    'videoa': '#FANZA #DMM #アダルト #PR #新着',
    'videoc': '#FANZA #DMM #素人 #PR #新着',
    'anime':  '#FANZA #DMM #アニメ #PR #新着',
    'doujin': '#FANZA #DMM #同人 #PR #新着',
    'comic':  '#DMM #電子書籍 #漫画 #PR #新着',
    'goods':  '#DMM #グッズ #PR #新着',
    'default': '#DMM #PR #新着',
}

COPY_TEMPLATES = [
    "今すぐチェック！期間限定で見逃せない作品が登場🔥",
    "ファン待望の最新作がついに配信スタート✨",
    "クオリティに驚くはず…一度見たら止まらない😍",
    "話題沸騰中🔥今だけポイントバックもあるかも！",
    "これは保存確定の神作品👑早めにゲットしておこう！",
    "高画質でいつでも・どこでも楽しめる📱💻",
    "無料試し読み／体験あり！まずはチェックを👀",
    "このクオリティでこの価格はお得すぎる…💸",
    "レビュー高評価続出！納得のクオリティをぜひ体験して✨",
    "見逃す前にダウンロード！ストリーミングにも対応🎬",
]

def get_copy():
    return random.choice(COPY_TEMPLATES)

# ================================================================
# 🔧 DMM API 関数
# ================================================================

def fetch_dmm_products(sort_key, sort_label):
    """sort_key: '-date'（新着順）または '-rank'（人気順）"""
    service, floor_name = FLOOR_SERVICE_MAP.get(DMM_FLOOR, ('digital', 'videoa'))
    params = {
        'api_id':       DMM_API_ID,
        'affiliate_id': DMM_AFFILIATE_ID,
        'site':         'FANZA',
        'service':      service,
        'floor':        floor_name,
        'hits':         DMM_HITS,
        'offset':       DMM_OFFSET,
        'sort':         sort_key,
        'output':       'json',
    }
    print(f'\n  [{sort_label}] 取得範囲: {DMM_OFFSET}件目〜{DMM_OFFSET + DMM_HITS - 1}件目')
    try:
        resp = requests.get(f'{DMM_API_BASE}/ItemList', params=params, timeout=15)
        data = resp.json()
        items = data.get('result', {}).get('items', [])
        if isinstance(items, dict):
            items = items.get('item', [])
        if items:
            url_str = items[0].get('affiliateURL', '')
            print(f"  URLの総文字数: {len(url_str)} / 末尾10文字: {url_str[-10:]}")
        print(f'  ✅ {len(items)} 件取得しました。')
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
            price_str = f'\u00a5{int(price_num):,}' if price_num else ''
    actors = [a.get('name', '') for a in (item.get('iteminfo', {}).get('actress') or [])][:3]
    genres = [g.get('name', '') for g in (item.get('iteminfo', {}).get('genre') or [])][:3]
    maker  = ((item.get('iteminfo', {}).get('maker') or [{}])[0]).get('name', '')

    # ★ サンプル動画URL（解像度の高い順に取得）
    sample_movie_url = ''
    smv = item.get('sampleMovieURL', {})
    if smv:
        for key in ['size_720_480', 'size_644_414', 'size_560_360', 'size_476_306']:
            val = smv.get(key, '')
            if val:
                sample_movie_url = val.strip()
                break

    return {
        'title':            title,
        'affiliate_url':    affiliate_url,
        'price':            price_str,
        'actors':           actors,
        'genres':           genres,
        'maker':            maker,
        'sample_movie_url': sample_movie_url,
    }

def clean_url(url):
    if not url:
        return ''
    url = url.strip().replace('\n', '').replace('\r', '').replace('　', '')
    if not url.startswith('http'):
        return ''
    return url


def actor_tags(actors):
    """女優名を #タグ 形式に変換（スペースを除去してハッシュタグ化）"""
    return '　'.join('#' + a.replace(' ', '').replace('　', '') for a in actors if a)


def build_x_post(product):
    """
    【投稿文の構造】
    本文（タイトル・コピー・価格・女優#タグ・ジャンル）
    ↓
    購入URL（単独行）→ OGP大カード表示を促進
    ↓
    サンプル動画URL（あれば）
    ↓
    ハッシュタグ
    """
    hashtags  = HASHTAG_MAP.get(DMM_FLOOR, HASHTAG_MAP['default'])
    url       = clean_url(product['affiliate_url'])
    sample    = clean_url(product.get('sample_movie_url', ''))
    copy      = get_copy()
    act_tags  = actor_tags(product['actors'])  # ★ 女優#タグ

    title = product['title']
    if len(title) > 35:
        title = title[:35] + '…'

    lines = []
    lines.append(f"🎬 {title}")
    lines.append('')
    lines.append(copy)
    lines.append('')
    if product['price']:
        lines.append(f"💰 価格: {product['price']}")
    if act_tags:
        lines.append(f"👤 {act_tags}")          # ★ #名前 形式で出演者
    if product['genres']:
        lines.append(f"🎞 {'　'.join(product['genres'][:2])}")
    lines.append('')
    lines.append(url)                            # 購入URL（OGPカード用）
    if sample:
        lines.append(f"▶ サンプル動画: {sample}")  # ★ サンプル動画URL
    lines.append(hashtags)

    text = '\n'.join(lines)

    # 280文字超の場合は短縮バージョンへ
    if len(text) > 280:
        lines2 = []
        lines2.append(f"🎬 {title}")
        lines2.append('')
        lines2.append(copy)
        lines2.append('')
        if product['price']:
            lines2.append(f"💰 {product['price']}")
        if act_tags:
            lines2.append(f"👤 {act_tags}")
        lines2.append('')
        lines2.append(url)
        if sample:
            lines2.append(f"▶ サンプル: {sample}")
        lines2.append(hashtags)
        text = '\n'.join(lines2)

    return text

# ================================================================
# 💾 保存
# ================================================================

def get_save_dir():
    try:
        home = Path.home()
        for path in [
            home / "Desktop",
            home / "OneDrive" / "Desktop",
            home / "OneDrive" / "デスクトップ",
            home / "デスクトップ",
        ]:
            if path.exists():
                return str(path)
    except Exception:
        pass
    return '.'


def save_posts(all_sections):
    """
    all_sections: [ (sort_label, [(product, text), ...]), ... ]
    新着順・人気順をセクション分けして1ファイルに保存する
    """
    save_dir  = get_save_dir()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f'dmm_x_posts_{timestamp}.txt'
    filepath  = os.path.join(save_dir, filename)

    total = sum(len(posts) for _, posts in all_sections)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# DMMアフィリエイト X投稿文\n")
        f.write(f"# 生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# フロア: {DMM_FLOOR} / モード: {DMM_SORT_MODE}\n")
        f.write(f"# 取得開始: {DMM_OFFSET}件目 / 各ソート{FETCH_COUNT}件\n")
        f.write(f"# 総投稿数: {total}件\n")
        f.write("=" * 60 + "\n\n")

        for sort_label, posts in all_sections:
            f.write(f"{'=' * 60}\n")
            f.write(f"【{sort_label}】{len(posts)}件\n")
            f.write(f"{'=' * 60}\n\n")

            for i, (product, text) in enumerate(posts, 1):
                f.write(f"--- {sort_label} {i}/{len(posts)} ---\n")
                f.write(f"商品名: {product['title']}\n")
                f.write(f"文字数: {len(text)}文字\n")
                f.write(f"URL確認: {product['affiliate_url']}\n")
                if product.get('sample_movie_url'):
                    f.write(f"サンプル動画: {product['sample_movie_url']}\n")
                f.write("-" * 40 + "\n")
                f.write(text)
                f.write("\n\n")

    print(f'\n💾 保存完了！')
    print(f'📄 ファイル: {filepath}')
    return filepath

# ================================================================
# 🚀 メイン実行
# ================================================================

print(f'🛍️  DMMから商品情報を取得中（フロア: {DMM_FLOOR} / モード: {DMM_SORT_MODE}）...')

all_sections = []

for sort_key, sort_label in SORT_LIST:
    raw_items = fetch_dmm_products(sort_key, sort_label)
    if not raw_items:
        print(f'  ⚠️  [{sort_label}] 商品が取得できませんでした。スキップします。')
        continue

    products = [parse_product(item) for item in raw_items]
    print(f'  📝 [{sort_label}] 投稿文を生成中...')

    posts = []
    for p in products:
        text = build_x_post(p)
        posts.append((p, text))
        print(f"    ✅ [{len(text)}文字] {p['title'][:30]}...")

    all_sections.append((sort_label, posts))

if not all_sections:
    print('❌ 商品が1件も取得できませんでした。')
    sys.exit(1)

# プレビュー（最初のセクションの1件目）
first_label, first_posts = all_sections[0]
print('\n' + '=' * 60)
print(f'📋 投稿文プレビュー（{first_label} 1件目）')
print('=' * 60)
print(first_posts[0][1])
print('=' * 60)

save_posts(all_sections)

total = sum(len(p) for _, p in all_sections)
print(f'\n✅ 完了！合計 {total} 件の投稿文を保存しました。')
print('テキストファイルを開いてXに手動投稿してください。')
