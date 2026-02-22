import streamlit as st
import simpy
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import matplotlib.font_manager as fm

# --- 1. ブランド化とメタ設定 ---
st.set_page_config(
    page_title="物流デジタルツイン診断 | 発送ライン人員配置シミュレーター",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 日本語フォント設定（リポジトリ内のファイルを直接指定） ---
import os
import matplotlib.font_manager as fm

# アップロードしたファイル名と一致させてください
font_path = './NotoSansJP-Regular.ttf'

if os.path.exists(font_path):
    # フォントをMatplotlibに登録
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = prop.get_name()
    # グラフ上のマイナス記号の文字化け防止
    plt.rcParams['axes.unicode_minus'] = False
else:
    print(f"警告: {font_path} が見つかりません。デフォルトフォントを使用します。")

# --- 2. 受信用魔法（URLパラメータ） ---
query_params = st.query_params
default_orders = int(query_params.get("orders", 60))
default_staff = int(query_params.get("staff", 3))
default_time = float(query_params.get("time", 2.5))

# --- 3. シミュレーションロジック (正規分布版) ---
def packing_process(env, name, packer_resource, packing_time_mean, wait_times):
    arrival_time = env.now
    with packer_resource.request() as request:
        yield request
        wait_time = env.now - arrival_time
        wait_times.append(wait_time)
        
        # 正規分布による「人間らしい」ばらつき
        std_dev = packing_time_mean * 0.2
        service_time = max(0.1, random.gauss(packing_time_mean, std_dev))
        yield env.timeout(service_time)

def setup(env, num_packers, arrival_interval, packing_time_mean, wait_times):
    packer_resource = simpy.Resource(env, capacity=num_packers)
    order_count = 0
    while True:
        yield env.timeout(random.expovariate(1.0 / arrival_interval))
        order_count += 1
        env.process(packing_process(env, f'Order {order_count}', packer_resource, packing_time_mean, wait_times))

# --- 4. メインUI表示 ---
st.title("📦 物流デジタルツイン診断")
st.markdown("### 発送ライン・人員配置最適化シミュレーター")

# --- 5. サイドバーUI（スマホ最適化） ---
st.sidebar.header("診断条件の設定")

avg_orders_per_hour = st.sidebar.number_input("1時間あたりの平均注文数 (件)", value=default_orders, min_value=1, step=5)
num_packers = st.sidebar.slider("出勤スタッフ数 (人)", 1, 10, value=default_staff) # sliderは最小1になっているのでOK
arrival_interval = 60.0 / avg_orders_per_hour

avg_packing_time = st.sidebar.number_input("平均梱包時間 (分)", value=default_time, min_value=0.1, step=0.1)

sim_hours = st.sidebar.slider("稼働時間 (時間)", 1, 24, 8)

# 免責事項（captionで小さく表示）
st.sidebar.markdown("---")
st.sidebar.caption("""
**【免責事項】**
本ツールは理論上のシミュレーション結果を提供するものであり、実際の現場環境（機器故障、急な欠勤、作業ミス等）を保証するものではありません。
""")

# ボタンの文字を短くし、横幅いっぱいに広げることで「分-析」の改行を防ぐ
if st.sidebar.button("シミュレーションを実行", use_container_width=True):
    # シミュレーション実行
    wait_times = []
    env = simpy.Environment()
    env.process(setup(env, num_packers, arrival_interval, avg_packing_time, wait_times))
    env.run(until=sim_hours * 60)

    # --- 6. 結果レポート ---
    st.header("📊 分析レポート")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("予測総処理数", f"{len(wait_times)} 件")
    with col2:
        avg_wait = np.mean(wait_times) if wait_times else 0
        st.metric("平均待ち時間", f"{avg_wait:.2f} 分")
    with col3:
        max_wait = np.max(wait_times) if wait_times else 0
        # 目安10分との差分を表示
        st.metric("最大待ち時間", f"{max_wait:.2f} 分", delta=f"{max_wait - 10:.1f}分 (目安10分)", delta_color="inverse")

    # グラフ表示
    fig, ax = plt.subplots()
    ax.hist(wait_times, bins=20, color='skyblue', edgecolor='black')
    ax.set_title("発送遅延リスク（待ち時間の分布）")
    ax.set_xlabel("待ち時間 (分)")
    ax.set_ylabel("注文数")
    st.pyplot(fig)

    # 診断アドバイス
    st.subheader("💡 診断アドバイス")
    if max_wait > 15:
        st.error(f"【要改善】最大待ち時間が {max_wait:.1f} 分と予測されます。発送締め切りに間に合わないリスクがあるため、スタッフの追加検討をお勧めします。")
    elif avg_wait < 1:
        st.success("【最適】非常にスムーズな稼働です。余剰人員を他の工程へ配置転換する余裕があります。")
    else:
        st.info("【安定】適切な人員配置です。安定した稼働が見込めます。")

    # --- 7. 出口戦略：コンバージョン導線（スマホ最適化） ---
    st.markdown("---")
    st.subheader("🚀 次のステップへ：現場をさらに進化させる")
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("**本格導入・カスタマイズ相談**\n\n貴社の実データを反映した専用モデルを構築。")
        # リンク先は適宜修正してください
        st.link_button("無料相談・予約", "https://victorconsulting.jp/contact/?service=logistics", use_container_width=True)
    
    with c2:
        st.success("**月額1万円で本格運用**\n\n人員配置を毎日最適化するダッシュボードを提供。")
        st.link_button("サービス詳細", "https://victorconsulting.jp/logistics-digital-twin/", use_container_width=True)
