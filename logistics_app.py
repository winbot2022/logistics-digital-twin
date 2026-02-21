import streamlit as st # [cite: 92]
import simpy # [cite: 2, 68]
import random # [cite: 68]
import pandas as pd # [cite: 146]
import numpy as np # [cite: 68]
import matplotlib.pyplot as plt # [cite: 150]
import os
import matplotlib.font_manager as fm

# --- 0. 基本設定と日本語フォント対策 ---
st.set_page_config(page_title="物流デジタルツイン MVP", layout="wide")

# Linuxサーバー（Streamlit Cloud）用フォント設定
# [cite: 92, 97]
jp_font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
if os.path.exists(jp_font_path):
    prop = fm.FontProperties(fname=jp_font_path)
    plt.rcParams['font.family'] = prop.get_name()

# --- 1. 受信用魔法：URLパラメータを読み取る ---
# [cite: 133, 136]
query_params = st.query_params

# URLから値を取得（なければデフォルト値をセット）
default_orders = int(query_params.get("orders", 60))
default_staff = int(query_params.get("staff", 3))
default_time = float(query_params.get("time", 2.5))

# --- 2. シミュレーションロジック部 (SimPy) ---
def packing_process(env, name, packer_resource, packing_time_mean, wait_times):
    arrival_time = env.now
    
    # 梱包台（スタッフ）が空くのを待つ
    with packer_resource.request() as request:
        yield request
        wait_time = env.now - arrival_time
        wait_times.append(wait_time)
        
        # 梱包作業の実施（指数分布でバラツキを表現）
        # [cite: 14, 79]
        service_time = random.expovariate(1.0 / packing_time_mean)
        yield env.timeout(service_time)

def setup(env, num_packers, arrival_interval, packing_time_mean, wait_times):
    # スタッフ数（リソースのキャパシティ）を設定 [cite: 62, 74]
    packer_resource = simpy.Resource(env, capacity=num_packers)
    order_count = 0
    
    while True:
        # 次の注文が来るまでの時間 [cite: 11, 80]
        yield env.timeout(random.expovariate(1.0 / arrival_interval))
        order_count += 1
        env.process(packing_process(env, f'Order {order_count}', packer_resource, packing_time_mean, wait_times))

# --- 3. Streamlit フロントエンド (UI部) ---
# [cite: 92, 135]
st.title("📦 EC梱包ライン・人員配置シミュレーター")
st.sidebar.header("明日の稼働条件を設定")

# サイドバーウィジェットの配置 [cite: 138, 140, 161]
st.sidebar.subheader("1. 注文の負荷")
avg_orders_per_hour = st.sidebar.number_input(
    "1時間あたりの平均注文数 (件)", 
    value=default_orders, 
    step=5
)
arrival_interval = 60.0 / avg_orders_per_hour

st.sidebar.subheader("2. 現場のキャパシティ")
num_packers = st.sidebar.slider(
    "出勤する梱包スタッフ数 (人)", 
    1, 10, 
    value=default_staff
)
avg_packing_time = st.sidebar.number_input(
    "1件あたりの平均梱包時間 (分)", 
    value=default_time, 
    step=0.1
)

st.sidebar.subheader("3. シミュレーション期間")
sim_hours = st.sidebar.slider("稼働時間 (時間)", 1, 24, 8) # [cite: 69, 142]

# シミュレーション実行ボタン [cite: 156]
if st.sidebar.button("シミュレーション実行"):
    wait_times = []
    env = simpy.Environment() # [cite: 73]
    env.process(setup(env, num_packers, arrival_interval, avg_packing_time, wait_times)) # [cite: 86]
    env.run(until=sim_hours * 60) # [cite: 79]

    # --- 4. 結果の可視化 ---
    st.header("📊 シミュレーション結果レポート") # [cite: 134]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # 総処理注文数 [cite: 107, 144]
        st.metric("総処理注文数", f"{len(wait_times)} 件")
    with col2:
        # 平均待ち時間 [cite: 23, 147]
        avg_wait = np.mean(wait_times) if wait_times else 0
        st.metric("平均待ち時間", f"{avg_wait:.2f} 分")
    with col3:
        # 最大待ち時間 [cite: 24, 147]
        max_wait = np.max(wait_times) if wait_times else 0
        st.metric("最大待ち時間", f"{max_wait:.2f} 分", delta=f"{max_wait - 10:.1f}分 (目安10分)", delta_color="inverse")

    # 待ち時間の分布グラフ [cite: 52, 150]
    fig, ax = plt.subplots()
    ax.hist(wait_times, bins=20, color='skyblue', edgecolor='black')
    ax.set_title("待ち時間の分布（お客様への発送遅延リスク）")
    ax.set_xlabel("待ち時間 (分)")
    ax.set_ylabel("注文数")
    st.pyplot(fig)

    # 現場への改善アドバイス [cite: 59, 145]
    st.subheader("💡 現場へのアドバイス")
    if max_wait > 15:
        st.error(f"警告：最大待ち時間が{max_wait:.1f}分に達しています。発送締め切りに間に合わないリスクが高いです。スタッフを1名追加するか、残業を検討してください。")
    elif avg_wait < 1:
        st.success("現在は非常に余裕があります。スタッフを1名他の工程（検品など）に回しても、発送品質は維持できる可能性があります。")
    else:
        st.info("適切な人員配置です。現状のシフトで安定した稼働が見込めます。")
