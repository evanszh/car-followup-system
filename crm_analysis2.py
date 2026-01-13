import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# ==========================================
# 1. 基础配置与连接
# ==========================================
st.set_page_config(page_title="精准回访 App", layout="wide")

@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # 优先从 Secrets 读取 (部署用)
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # 本地测试回退
            creds = ServiceAccountCredentials.from_json_keyfile_name("glass-quest-482522-t7-977042a18a8b.json", scope)
        client = gspread.authorize(creds)
        return client.open("中国市场回访表").get_worksheet(0)
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None

@st.cache_data(ttl=600)
def load_data_cached(_sheet):
    if _sheet is None: return pd.DataFrame()
    data = _sheet.get_all_records()
    df = pd.DataFrame(data)
    # 日期预处理
    df['购车日期'] = pd.to_datetime(df['购车日期'], errors='coerce')
    df['生日'] = pd.to_datetime(df['生日'], errors='coerce')
    # 布尔值清理
    target_cols = ['购车回访_3天', '购车回访_15天', '购车回访_30天', '生日回访标记']
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).upper() in ['TRUE', '是', '1', 'CHECKED', 'V'])
        else:
            df[col] = False
    return df

# ==========================================
# 2. 全局样式美化 (CSS)
# ==========================================
st.markdown("""
    <style>
    /* 指标卡美化 */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        padding: 12px;
        border-radius: 12px;
        border-left: 5px solid #dee2e6;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] { border-left-color: #28a745; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] { border-left-color: #fd7e14; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] { border-left-color: #007bff; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] { border-left-color: #e83e8c; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"] { border-left-color: #dc3545; background-color: #fff5f5; }

    /* 按钮样式：去掉红框 */
    div.stButton > button {
        border-radius: 8px;
        padding: 10px;
        font-weight: bold;
        transition: all 0.2s;
    }
    div.stButton > button:focus, div.stButton > button:active {
        outline: none !important;
        box-shadow: 0 0 0 2px rgba(40,167,69,0.2) !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心交互函数：移动端卡片
# ==========================================
def render_task_card(current_df, col_to_update, label, color):
    if current_df.empty:
        st.info(f"✨ 暂无{label}任务")
        return

    for idx, row in current_df.iterrows():
        with st.container():
            # 卡片背景
            st.markdown(f"""
                <div style="border-left: 6px solid {color}; padding: 12px; margin: 10px 0; background-color: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 18px; font-weight: bold;">👤 {row['姓名']}</span>
                        <span style="font-size: 13px; color: #888;">{row['购车日期'].strftime('%Y-%m-%d') if pd.notnull(row['购车日期']) else ''}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 交互按钮
            if st.button(f"完成{label}登记", key=f"btn_{col_to_update}_{idx}", use_container_width=True):
                with st.spinner("同步中..."):
                    idx_col = df.columns.get_loc(col_to_update) + 1
                    cell_a1 = gspread.utils.rowcol_to_a1(idx + 2, idx_col)
                    gsheet.update_acell(cell_a1, "TRUE")
                    st.cache_data.clear() # 关键：清除缓存强制重新加载
                    st.toast(f"{row['姓名']} 登记成功！", icon="🎉")
                    st.rerun()

# ==========================================
# 4. 数据处理逻辑
# ==========================================
gsheet = init_connection()
df = load_data_cached(gsheet)

if not df.empty:
    today = pd.to_datetime(datetime.now().date())
    
    # 侧边栏：筛选销售
    with st.sidebar:
        st.title("⚙️ 选项")
        reps = ["全部"] + sorted(df['对应销售'].unique().tolist())
        sel_rep = st.selectbox("选择销售人员", reps)
        if st.button("🔄 刷新数据"):
            st.cache_data.clear()
            st.rerun()
    
    work_df = df if sel_rep == "全部" else df[df['对应销售'] == sel_rep]

    # --- 过滤逻辑 ---
    l3 = work_df[(work_df['购车日期'] >= today - timedelta(days=5)) & (work_df['购车日期'] <= today - timedelta(days=3)) & (work_df['购车回访_3天'] == False)]
    l15 = work_df[(work_df['购车日期'] >= today - timedelta(days=17)) & (work_df['购车日期'] <= today - timedelta(days=15)) & (work_df['购车回访_15天'] == False)]
    l30 = work_df[(work_df['购车日期'] >= today - timedelta(days=32)) & (work_df['购车日期'] <= today - timedelta(days=30)) & (work_df['购车回访_30天'] == False)]
    
    b_days = [(today + timedelta(days=i)).strftime('%m%d') for i in range(-3, 4)]
    lbd = work_df[(work_df['生日'].dt.strftime('%m%d').isin(b_days)) & (work_df['生日回访标记'] == False)]

    # 逾期逻辑
    ov30 = work_df[(today > work_df['购车日期'] + timedelta(days=32)) & (work_df['购车回访_30天'] == False)].assign(T='30天回访逾期')
    ov_bd = work_df[work_df.apply(lambda r: pd.notnull(r['生日']) and today > (r['生日'].replace(year=today.year) + timedelta(days=7)) and not r['生日回访标记'], axis=1)].assign(T='生日关怀逾期')
    lov = pd.concat([ov30, ov_bd])

    # ==========================================
    # 5. UI 渲染
    # ==========================================
    st.title("🚀 回访工作台 (移动优化版)")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📅 3日", len(l3))
    m2.metric("🚗 15日", len(l15))
    m3.metric("🌟 30日", len(l30))
    m4.metric("🎂 生日", len(lbd))
    ov_c = len(lov)
    m5.metric("⚠️ 逾期", ov_c, delta=-ov_c if ov_c > 0 else 0, delta_color="inverse")

    # 选项卡切换
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚩3日", "🚩15日", "🚩30日", "🎂生日", "⚠️逾期"])

    with tab1: render_task_card(l3, '购车回访_3天', "3日回访", "#28a745")
    with tab2: render_task_card(l15, '购车回访_15天', "15日回访", "#fd7e14")
    with tab3: render_task_card(l30, '购车回访_30天', "30日回访", "#007bff")
    with tab4: render_task_card(lbd, '生日回访标记', "生日关怀", "#e83e8c")
    
    with tab5:
        if lov.empty:
            st.success("暂无逾期，表现极佳！")
        else:
            for i, r in lov.iterrows():
                with st.container():
                    st.markdown(f'<div style="border-left:6px solid #dc3545; padding:12px; margin:10px 0; background-color:#fff5f5; border-radius:10px;"><b>👤 {r["姓名"]}</b> <span style="float:right; color:red;">{r["T"]}</span></div>', unsafe_allow_html=True)
                    t_col = '购车回访_30天' if '30天' in r['T'] else '生日回访标记'
                    if st.button(f"立即补录: {r['姓名']}", key=f"ov_{i}", use_container_width=True):
                        idx_c = df.columns.get_loc(t_col) + 1
                        gsheet.update_acell(gspread.utils.rowcol_to_a1(i+2, idx_c), "TRUE")
                        st.cache_data.clear()
                        st.rerun()

else:
    st.warning("⚠️ 无法读取数据，请检查 Google Sheets 共享权限或表头设置。")
