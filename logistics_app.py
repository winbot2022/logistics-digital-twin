import streamlit as st
import simpy
import random
import numpy as np
import matplotlib.pyplot as plt
import os
import matplotlib.font_manager as fm

# --- 1. ブランド設定 ---
st.set_page_config(
    page_title="物流デジタルツイン診断 | 発送ライン最適化シミュレーター",
    page_icon="📦",
    layout="wide"
)

# --- 日本語フォント ---
font_path = './NotoSansJP-Regular.ttf'
if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = prop.get_name()
    plt.rcParams['axes.unicode_minus'] = False

# --- シミュレーション関数 ---
def packing_process(env, packer_resource, packing_time_mean, wait_times):
    arrival_time = env.now
    with packer_resource.request() as request:
        yield request
        wait_time = env.now - arrival_time
        wait_times.append(wait_time)

        std_dev = packing_time_mean * 0.2
        service_time = max(0.1, random.gauss(packing_time_mean, std_dev))
        yield env.timeout(service_time)

def setup(env, num_packers, arrival_interval, packing_time_mean, wait_times):
    packer_resource = simpy.Resource(env, capacity=num_packers)
    while True:
        yield env.timeout(random.expovariate(1.0 / arrival_interval))
        env.process(packing_process(env, packer_resource, packing_time_mean, wait_times))

def run_simulation(avg_orders_per_hour, num_packers, avg_packing_time, sim_hours, seed=42):
    random.seed(seed)
    wait_times = []
    env = simpy.Environment()
    arrival_interval = 60.0 / avg_orders_per_hour
    env.process(setup(env, num_packers, arrival_interval, avg_packing_time, wait_times))
    env.run(until=sim_hours * 60)
    return np.array(wait_times)

# --- UI ---
st.title("📦 物流デジタルツイン診断")
st.markdown("### 損失金額換算＋人員最適化付きモデル")

st.sidebar.header("診断条件")

avg_orders_per_hour = st.sidebar.number_input("1時間あたりの平均注文数", value=60, min_value=1)
num_packers = st.sidebar.slider("現在のスタッフ数", 1, 15, 3)
avg_packing_time = st.sidebar.number_input("平均梱包時間（分）", value=2.5, min_value=0.1)
sim_hours = st.sidebar.slider("稼働時間（時間）", 1, 24, 8)

st.sidebar.markdown("---")
sla = st.sidebar.number_input("許容待ち時間SLA（分）", value=10.0)
loss_per_order = st.sidebar.number_input("遅延1件あたり損失（円）", value=500)
target_delay_rate = st.sidebar.slider("目標遅延率（%）", 1, 20, 5)

if st.sidebar.button("シミュレーション実行", use_container_width=True):

    wait_times = run_simulation(avg_orders_per_hour, num_packers, avg_packing_time, sim_hours)

    total_orders = len(wait_times)
    avg_wait = np.mean(wait_times)
    max_wait = np.max(wait_times)

    late_orders = wait_times[wait_times > sla]
    delay_rate = len(late_orders) / total_orders * 100
    daily_loss = len(late_orders) * loss_per_order
    monthly_loss = daily_loss * 20

    st.header("📊 分析レポート")

    c1, c2, c3 = st.columns(3)
    c1.metric("総処理件数", f"{total_orders} 件")
    c2.metric("平均待ち時間", f"{avg_wait:.2f} 分")
    c3.metric("最大待ち時間", f"{max_wait:.2f} 分")

    st.markdown("---")

    c4, c5, c6 = st.columns(3)
    c4.metric("遅延率", f"{delay_rate:.1f} %")
    c5.metric("1日損失額", f"{daily_loss:,.0f} 円")
    c6.metric("月間損失額（20日）", f"{monthly_loss:,.0f} 円")

    fig, ax = plt.subplots()
    ax.hist(wait_times, bins=20, color='skyblue', edgecolor='black')
    ax.axvline(sla, color='red', linestyle='--', label='SLA')
    ax.set_title("待ち時間分布とSLAライン")
    ax.set_xlabel("待ち時間（分）")
    ax.set_ylabel("注文数")
    ax.legend()
    st.pyplot(fig)

    # --- 人員最適化 ---
    recommended_staff = None
    for staff in range(1, 16):
        test_wait = run_simulation(avg_orders_per_hour, staff, avg_packing_time, sim_hours)
        late = test_wait[test_wait > sla]
        rate = len(late) / len(test_wait) * 100
        if rate <= target_delay_rate:
            recommended_staff = staff
            break

    st.subheader("🤖 人員最適化提案")

    if recommended_staff:
        diff = recommended_staff - num_packers
        if diff > 0:
            st.warning(f"目標遅延率 {target_delay_rate}% を達成するには **+{diff}人（計{recommended_staff}人）** が推奨されます。")
        elif diff < 0:
            st.success(f"現状は過剰配置の可能性。**-{abs(diff)}人（計{recommended_staff}人）** でも目標達成可能です。")
        else:
            st.success("現状人員で目標を達成可能です。")
    else:
        st.error("最大15人でも目標遅延率を達成できません。工程改善が必要です。")

    st.markdown("---")
    st.subheader("🚀 次のステップ")
    st.link_button("無料相談・予約", "https://victorconsulting.jp/contact/?service=logistics", use_container_width=True)
