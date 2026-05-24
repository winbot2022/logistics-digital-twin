import streamlit as st

# st.set_page_config(layout="centered", initial_sidebar_state="collapsed")

st.title("遅延損失 単価設計ツール")

st.markdown(
    """
    <div style="font-size:16px; color:gray;">
    ※ 各設問の右側にある <b>「？」</b> に、入力の補足説明があります。
    PCではマウスを重ねる／スマホでは「？」をタップすると表示されます。
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# 共通部品
# -----------------------------
def time_selector(label: str, help_text: str = "") -> float:
    """
    時間（分）の入力：
    選択式＋自由入力（文章付き選択肢）
    内部計算値は中央値（仮）
    """
    options = [
        "ほとんど発生しない（0〜2分）",
        "少し発生する（3〜5分）",
        "明確に発生する（6〜10分）",
        "かなり発生する（10分以上）",
        "自由入力（◯分）",
    ]
    choice = st.selectbox(label, options, help=help_text)

    # 中央値（仮）
    map_minutes = {
        options[0]: 1,
        options[1]: 4,
        options[2]: 8,
        options[3]: 12,  # 10分以上は仮置き
    }

    if choice == options[4]:
        return float(st.number_input("自由入力：追加作業時間（分）", min_value=0, value=0, step=1, format="%d"))
    return float(map_minutes[choice])


def percent_selector(label: str, help_text: str = "") -> float:
    """
    割合（0〜1）の入力：
    選択式＋自由入力（文章付き選択肢）
    """
    options = [
        "ほとんどない（0%）",
        "一部で発生（10%程度）",
        "半数程度（50%程度）",
        "ほぼ毎回発生（80%以上）",
        "自由入力（◯%）",
    ]
    choice = st.selectbox(label, options, help=help_text)
    map_ratio = {
        options[0]: 0.0,
        options[1]: 0.10,
        options[2]: 0.50,
        options[3]: 0.80,
    }
    if choice == options[4]:
        pct = st.number_input("自由入力：発生割合（%）", min_value=0, max_value=100, value=0, step=1, format="%d")
        return float(pct) / 100.0
    return float(map_ratio[choice])


def wage_input(label: str, default: int = 1500, help_text: str = "") -> int:
    """
    時給（円）：
    整数表示、デフォルト1500、100円刻み
    """
    return int(
        st.number_input(
            label,
            min_value=0,
            value=int(default),
            step=100,
            format="%d",
            help=help_text,
        )
    )


def yen_input(label: str, default: int = 0, step: int = 100, help_text: str = "") -> int:
    """
    金額（円）：
    整数表示（小数なし）
    """
    return int(
        st.number_input(
            label,
            min_value=0,
            value=int(default),
            step=int(step),
            format="%d",
            help=help_text,
        )
    )


# -----------------------------
# ① 直接追加コスト
# -----------------------------
st.header("① 直接追加コスト")

add_minutes = time_selector(
    "【質問1】追加作業時間（選択式＋任意入力）",
    help_text="遅延が発生した際、本来不要だった追加作業は、1件当たり、だいたい何分程度発生していますか？（再出荷対応・伝票修正・荷札再発行・段取り変更など）"
)

field_wage = wage_input(
    "【質問2】担当者の時給（円）",
    default=1500,
    help_text="上記追加作業を行う担当者の時給です（概算で可）。"
)

external_cost = yen_input(
    "【質問3】遅延1件あたりの外部への追加実費（変動費）（円／件）",
    default=0,
    step=100,
    help_text="特急便差額・再出荷送料・外注費など。人件費とは別の現金支出を入力してください。該当しない場合は0円。"
)

direct_labor_cost = (add_minutes / 60.0) * field_wage
direct_cost = direct_labor_cost + external_cost


# -----------------------------
# ② 間接オペレーション負荷
# -----------------------------
st.header("② 間接オペレーション負荷")

indirect_minutes = time_selector(
    "【質問4】問い合わせ・社内調整時間（選択式＋任意入力）",
    help_text="遅延1件あたり、問い合わせ対応や社内調整にどの程度の時間が発生していますか？（顧客連絡・社内確認・状況説明など）"
)

office_wage = wage_input(
    "【質問5】対応担当者の時給（円）",
    default=1800,
    help_text="事務・管理系など（概算で可）。"
)

manager_ratio = percent_selector(
    "【質問6】管理職・上長確認の発生割合（選択式＋任意入力）",
    help_text="遅延案件のうち、上長確認や追加承認が発生する割合です。"
)

manager_minutes = float(
    st.number_input(
        "【質問7】上長対応1回あたりの時間（分）",
        help="上長確認が発生した場合、平均何分程度かかりますか？",
        min_value=0,
        value=0,
        step=1,
        format="%d",
        )
)

manager_wage = wage_input(
    "【質問8】上長の時給（円）",
    default=3000,
    help_text="概算で可。分からなければ役職の相場で仮置きしてください。"
)

indirect_cost = ((indirect_minutes / 60.0) * office_wage) + ((manager_minutes / 60.0) * manager_wage * manager_ratio)


# -----------------------------
# ③ 将来利益の期待損失
# -----------------------------
st.header("③ 将来利益の期待損失")

gross_profit = yen_input(
    "【質問9】1出荷あたりの平均粗利（円／件）",
    default=1200,
    step=100,
    help_text="売上ではなく粗利でお答えください。（概算で可）。"
)

rate_options = [
    "影響はほぼない（0%）",
    "わずかに低下（0.5%）",
    "少し低下（1%）",
    "明確に低下（2%）",
    "大きく低下（5%）",
    "自由入力（◯%）",
]
rate_choice = st.selectbox(
    "【質問10】遅延によるリピート低下率（選択式＋任意入力）",
    rate_options,
    help="遅延が発生すると、将来の受注確率はどの程度低下すると感じますか？（感覚で可）",
)
rate_map = {
    rate_options[0]: 0.0,
    rate_options[1]: 0.005,
    rate_options[2]: 0.01,
    rate_options[3]: 0.02,
    rate_options[4]: 0.05,
}
if rate_choice == rate_options[5]:
    pct = st.number_input("自由入力：低下率（%）", min_value=0, max_value=100, value=0, step=1, format="%d")
    rate = float(pct) / 100.0
else:
    rate = float(rate_map[rate_choice])

value_loss = gross_profit * rate


# -----------------------------
# 結果表示（ボタン押下後）
# -----------------------------

st.markdown("---")

if st.button("計算する"):
    total_loss = direct_cost + indirect_cost + value_loss

    st.markdown(
        f"""
        <div style='font-size:28px'>
        直接追加コスト：{direct_cost:,.0f}円<br>
        間接オペレーション負荷：{indirect_cost:,.0f}円<br>
        将来利益の期待損失：{value_loss:,.0f}円
        <hr>
        <b>遅延1件あたり損失単価：{total_loss:,.0f}円</b>
        <hr>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.caption("※本結果は入力値に基づく設計値です。")
