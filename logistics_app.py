import streamlit as st
import simpy
import random
import numpy as np
import pandas as pd
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
font_path = "./NotoSansJP-Regular.ttf"
if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = prop.get_name()
    plt.rcParams["axes.unicode_minus"] = False

# --- URLパラメータ（既存互換） ---
query_params = st.query_params
default_orders = int(query_params.get("orders", 60))
default_staff  = int(query_params.get("staff", 3))
default_time   = float(query_params.get("time", 2.5))

# --- シミュレーション（核） ---
def packing_process(env, packer_resource, packing_time_mean, wait_times):
    arrival_time = env.now
    with packer_resource.request() as request:
        yield request
        wait_times.append(env.now - arrival_time)

        std_dev = packing_time_mean * 0.2
        service_time = max(0.1, random.gauss(packing_time_mean, std_dev))
        yield env.timeout(service_time)

def setup(env, num_packers, arrival_interval, packing_time_mean, wait_times):
    packer_resource = simpy.Resource(env, capacity=num_packers)
    while True:
        yield env.timeout(random.expovariate(1.0 / arrival_interval))
        env.process(packing_process(env, packer_resource, packing_time_mean, wait_times))

def run_simulation(avg_orders_per_hour, num_packers, avg_packing_time, sim_hours, seed=42):
    # 再現性重視
    random.seed(seed)
    wait_times = []
    env = simpy.Environment()
    arrival_interval = 60.0 / avg_orders_per_hour
    env.process(setup(env, num_packers, arrival_interval, avg_packing_time, wait_times))
    env.run(until=sim_hours * 60)
    return np.array(wait_times)

# --- 指標計算 ---
def evaluate(wait_times, sla_min, loss_per_order_yen, workdays=20):
    total = int(len(wait_times))
    if total == 0:
        return {
            "total_orders": 0,
            "avg_wait": 0.0,
            "max_wait": 0.0,
            "delay_rate": 0.0,
            "late_orders": 0,
            "daily_loss": 0,
            "monthly_loss": 0
        }

    avg_wait = float(np.mean(wait_times))
    max_wait = float(np.max(wait_times))
    late = wait_times[wait_times > sla_min]
    late_count = int(len(late))
    delay_rate = late_count / total * 100.0
    daily_loss = int(late_count * loss_per_order_yen)
    monthly_loss = int(daily_loss * workdays)

    return {
        "total_orders": total,
        "avg_wait": avg_wait,
        "max_wait": max_wait,
        "delay_rate": delay_rate,
        "late_orders": late_count,
        "daily_loss": daily_loss,
        "monthly_loss": monthly_loss
    }

# --- 人員最適化（目標遅延率を満たす最小人数） ---
def recommend_staff(avg_orders_per_hour, avg_packing_time, sim_hours, sla, loss_per_order, target_delay_rate,
                    min_staff=1, max_staff=15, seed=42):
    for staff in range(min_staff, max_staff + 1):
        wt = run_simulation(avg_orders_per_hour, staff, avg_packing_time, sim_hours, seed=seed)
        m = evaluate(wt, sla, loss_per_order)
        if m["delay_rate"] <= target_delay_rate:
            return staff, m
    return None, None

def recommend_staff_by_maxwait(avg_orders_per_hour, avg_packing_time, sim_hours, max_wait_limit,
                               min_staff=1, max_staff=15, seed=42):
    for staff in range(min_staff, max_staff + 1):
        wt = run_simulation(avg_orders_per_hour, staff, avg_packing_time, sim_hours, seed=seed)
        max_wait = float(np.max(wt)) if len(wt) else 0.0
        if max_wait <= max_wait_limit:
            return staff, max_wait
    return None, None

# --- UI ---
st.title("📦 物流デジタルツイン診断")

st.sidebar.header("診断条件（ベース）")
avg_orders_per_hour = st.sidebar.number_input("1時間あたりの平均注文数", value=default_orders, min_value=1, step=5)
num_packers = st.sidebar.slider("現在のスタッフ数", 1, 15, value=default_staff)
avg_packing_time = st.sidebar.number_input("平均梱包時間（分）", value=default_time, min_value=0.1, step=0.1)
sim_hours = st.sidebar.slider("稼働時間（時間）", 1, 24, 8)

st.sidebar.markdown("---")
st.sidebar.subheader("損失換算の設定")
sla = st.sidebar.number_input("許容待ち時間SLA（分）", value=10.0, min_value=0.0, step=0.5)
loss_per_order = st.sidebar.number_input("遅延1件あたり損失（円）", value=500, min_value=0, step=50)
workdays = st.sidebar.number_input("月間稼働日（換算）", value=20, min_value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("人員最適化の設定")
target_delay_rate = st.sidebar.slider("目標遅延率（%）", 1, 20, 5)

max_wait_limit = st.sidebar.number_input(
    "締切遵守ライン（最大待ちの上限・分）", value=15.0, min_value=0.0, step=0.5
)

st.sidebar.markdown("---")
st.sidebar.subheader("波動シナリオ比較")
enable_scenarios = st.sidebar.checkbox("波動シナリオ比較を有効化", value=True)

# 繁忙・低調を「注文数倍率」で定義、繁忙は梱包時間も悪化しやすいので倍率を用意
peak_orders_mult = st.sidebar.slider("繁忙：注文数倍率", 1.0, 3.0, 1.5, 0.1) if enable_scenarios else 1.0
peak_time_mult   = st.sidebar.slider("繁忙：梱包時間倍率", 1.0, 2.0, 1.1, 0.05) if enable_scenarios else 1.0
off_orders_mult  = st.sidebar.slider("低調：注文数倍率", 0.3, 1.0, 0.7, 0.05) if enable_scenarios else 1.0

optimize_each_scenario = st.sidebar.checkbox("各シナリオでも人員最適化を実行", value=True) if enable_scenarios else False

st.sidebar.markdown("---")
st.sidebar.caption("""**【免責事項】**  
本ツールは理論上のシミュレーション結果を提供するものであり、実際の現場環境（機器故障、急な欠勤、作業ミス等）を保証するものではありません。
""")

if st.sidebar.button("シミュレーション実行", use_container_width=True):
    # --- ベース（通常） ---
    wt_base = run_simulation(avg_orders_per_hour, num_packers, avg_packing_time, sim_hours, seed=42)
    m_base = evaluate(wt_base, sla, loss_per_order, workdays=workdays)

    st.header("📊 分析レポート（通常）")

    c1, c2, c3 = st.columns(3)
    c1.metric("総到着件数（推定）", f"{m_base['total_orders']} 件")
    c2.metric("平均待ち時間", f"{m_base['avg_wait']:.2f} 分")
    c3.metric("最大待ち時間", f"{m_base['max_wait']:.2f} 分")

    st.markdown("---")
    c4, c5, c6 = st.columns(3)
    c4.metric("遅延率（SLA超）", f"{m_base['delay_rate']:.1f} %")
    c5.metric("1日損失額（推定）", f"{m_base['daily_loss']:,.0f} 円")
    c6.metric(f"月間損失額（{workdays}日換算）", f"{m_base['monthly_loss']:,.0f} 円")

    # 分布
    fig, ax = plt.subplots()
    ax.hist(wt_base, bins=20, edgecolor="black")
    ax.axvline(sla, color="red", linestyle="--", linewidth=2, label="SLA")
    ax.set_title("待ち時間分布（通常）")
    ax.set_xlabel("待ち時間（分）")
    ax.set_ylabel("注文数")
    ax.legend()
    st.pyplot(fig)

    # --- 人員最適化（通常） ---
    st.subheader("🤖 人員最適化提案（通常）")
    rec_staff, rec_metrics = recommend_staff(
        avg_orders_per_hour, avg_packing_time, sim_hours, sla, loss_per_order, target_delay_rate,
        min_staff=1, max_staff=15, seed=42
    )

    if rec_staff is None:
        st.error("最大15人でも目標遅延率を達成できません。工程改善（作業時間短縮・工程分割・レイアウト等）が必要です。")
    else:
        diff = rec_staff - num_packers
        if diff > 0:
            st.warning(f"目標遅延率 {target_delay_rate}% を達成するには **+{diff}人（計{rec_staff}人）** が推奨されます。")
        elif diff < 0:
            st.success(f"現状は過剰配置の可能性。**-{abs(diff)}人（計{rec_staff}人）** でも目標達成可能です。")
        else:
            st.success("現状人員で目標を達成可能です。")

    # --- ④ 波動シナリオ比較 ---
    if enable_scenarios:
        st.markdown("---")
        st.header("📈 波動シナリオ比較（④）")

        scenarios = [
            ("通常", 1.0, 1.0, num_packers),
            ("繁忙", peak_orders_mult, peak_time_mult, num_packers),
            ("低調", off_orders_mult, 1.0, num_packers),
        ]

        # --- シナリオ結果の集計（表示はループ外で1回だけ） ---
        rows = []
        opt_rows = []
        opt_rows_maxwait = []
        
        for name, o_mult, t_mult, staff in scenarios:
            orders = max(1, int(round(avg_orders_per_hour * o_mult)))
            ptime = max(0.1, float(avg_packing_time * t_mult))
        
            wt = run_simulation(orders, staff, ptime, sim_hours, seed=42)
            m = evaluate(wt, sla, loss_per_order, workdays=workdays)
        
            rows.append({
                "シナリオ": name,
                "注文数(件/時)": orders,
                "梱包時間(分)": round(ptime, 2),
                "スタッフ(人)": staff,
                "遅延率(%)": round(m["delay_rate"], 1),
                f"月間損失({workdays}日)": m["monthly_loss"],
                "最大待ち(分)": round(m["max_wait"], 2),
                "平均待ち(分)": round(m["avg_wait"], 2),
                "遅延件数": m["late_orders"],
                "総到着件数": m["total_orders"],
            })
        
            if optimize_each_scenario:
                r_staff, _ = recommend_staff(
                    orders, ptime, sim_hours, sla, loss_per_order, target_delay_rate,
                    min_staff=1, max_staff=15, seed=42
                )
                opt_rows.append({
                    "シナリオ": name,
                    "推奨スタッフ(人)": r_staff if r_staff is not None else "15人でも未達",
                    "現在との差": (r_staff - num_packers) if (r_staff is not None) else "-"
                })
                r_staff_mw, mw_value = recommend_staff_by_maxwait(
                    orders, ptime, sim_hours, max_wait_limit,
                    min_staff=1, max_staff=15, seed=42
                )
                opt_rows_maxwait.append({
                    "シナリオ": name,
                    "推奨スタッフ(人)": r_staff_mw if r_staff_mw is not None else "15人でも未達",
                    "最大待ち(分)": round(mw_value, 2) if mw_value is not None else "-",
                    "現在との差": (r_staff_mw - num_packers) if (r_staff_mw is not None) else "-"
                })
        
        
        # --- ここから先は「ループ外」：表は1回だけ表示 ---
        df = pd.DataFrame(rows)
        
        # 表の並び順を固定（通常→繁忙→低調）
        order_map = {"通常": 0, "繁忙": 1, "低調": 2}
        df = df.sort_values("シナリオ", key=lambda s: s.map(order_map)).reset_index(drop=True)
        
        money_col = f"月間損失({workdays}日)"
        
        # 数値のままカンマ表示（ソートも壊れにくい）
        st.dataframe(
            df.style.format({
                money_col: "{:,.0f}",
                "注文数(件/時)": "{:,.0f}",
                "遅延件数": "{:,.0f}",
                "総到着件数": "{:,.0f}",
                "最大待ち(分)": "{:,.2f}",
                "平均待ち(分)": "{:,.2f}",
                "遅延率(%)": "{:,.1f}",
                "梱包時間(分)": "{:,.2f}",
                "スタッフ(人)": "{:,.0f}",
            }),
            use_container_width=True
        )
        
        # （任意）シナリオ別の推奨人員表
        if optimize_each_scenario:
            st.subheader("🧭 シナリオ別：推奨人員（目標遅延率ベース）")
            df_opt = pd.DataFrame(opt_rows).sort_values(
                "シナリオ", key=lambda s: s.map(order_map)
            ).reset_index(drop=True)
            st.dataframe(df_opt, use_container_width=True)

            st.subheader("🧭 シナリオ別：推奨人員（締切遵守（最大待ち）ベース）")
            df_opt_mw = pd.DataFrame(opt_rows_maxwait).sort_values(
                "シナリオ", key=lambda s: s.map(order_map)
            ).reset_index(drop=True)
            st.dataframe(df_opt_mw, use_container_width=True)

        # 比較グラフ：遅延率と月間損失
        fig2, ax2 = plt.subplots()

        # 百万円単位に変換し、小数1桁に丸める
        loss_million = (df[f"月間損失({workdays}日)"] / 1_000_000).round(1)
        
        # シナリオごとの色指定
        color_map = {
            "通常": "blue",
            "繁忙": "red",
            "低調": "green"
        }
        
        colors = [color_map.get(s, "gray") for s in df["シナリオ"]]
        
        ax2.bar(df["シナリオ"], loss_million, color=colors)
        
        ax2.set_title("シナリオ別：月間損失（推定）")
        ax2.set_xlabel("シナリオ")
        ax2.set_ylabel("損失（百万円）")
        
        # 科学表記を強制的にオフ
        ax2.ticklabel_format(style='plain', axis='y')
        
        # 棒の上に数値ラベル表示（小数1桁）
        for i, v in enumerate(loss_million):
            ax2.text(i, v + 0.05, f"{v:.1f}", ha='center', fontsize=9)
        
        st.pyplot(fig2)

        fig3, ax3 = plt.subplots()

        # 色指定（損失グラフと統一）
        color_map = {
            "通常": "blue",
            "繁忙": "red",
            "低調": "green"
        }
        
        colors = [color_map.get(s, "gray") for s in df["シナリオ"]]
        
        ax3.bar(df["シナリオ"], df["遅延率(%)"], color=colors)
        
        ax3.set_title("シナリオ別：遅延率（SLA超）")
        ax3.set_xlabel("シナリオ")
        ax3.set_ylabel("遅延率（%）")
        
        # 棒の上に数値表示
        for i, v in enumerate(df["遅延率(%)"]):
            ax3.text(i, v + 0.5, f"{v:.1f}%", ha='center', fontsize=9)
        
        st.pyplot(fig3)

        # --- 次のステップ（既存導線） ---
    # --- 次のステップ（最終クロージング導線） ---
st.markdown("---")
st.subheader("🚀 次のステップへ")

st.success(
    "**貴社専用モデルを構築します**\n\n"
    "無料診断は入口に過ぎません。\n"
    "実データを反映した『物流構造再現設計』で、"
    "人員判断を数値で確定させます。"
)

st.link_button(
    "物流構造再現設計を申し込む",
    "https://victorconsulting.jp/logistics-structure/",
    use_container_width=True
)
