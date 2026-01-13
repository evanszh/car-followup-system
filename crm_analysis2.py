import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# ==========================================
# 1. 基础配置与连接
# ==========================================
st.set_page_config(page_title="回访工作台", layout="wide")

@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
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
    df['购车日期'] = pd.to_datetime(df['购车日期'], errors='coerce')
    df['生日'] = pd.to_datetime(df['生日'], errors='coerce')
    target_cols = ['购车回访_3天', '购车回访_15天', '购车回访_30天', '生日回访标记']
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).upper() in ['TRUE', '是', '1', 'CHECKED', 'V'])
        else:
            df[col] = False
    return df

# ==========================================
# 2. 核心 CSS 优化：让手机打勾更容易
# ==========================================
st.markdown("""
    <style>
    /* 1. 增大表格行高，防止误触 */
    div[data-testid="stDataFrame"] td {
        padding: 15px !important;
        height: 60px !important;
    }
    
    /* 2. 针对手机端美化指标卡 */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        padding: 10px;
        border-radius: 10px;
        border-left: 5px solid #dee2e6;
    }

    /* 3. 彻底去掉按钮和输入框的红框 */
    button:focus, input:focus, select:focus {
        outline: none !important;
        box-shadow: none !important;
        border-color: #28a745 !important;
    }

    /* 4. 底部同步区域装饰 */
    .sync-zone {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 15px;
        border: 2px dashed #e9ecef;
        margin-top: 20px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 业务逻辑
# ==========================================
gsheet = init_connection()
df = load_data_cached(gsheet)

if not df.empty:
    today = pd.to_datetime(datetime.now().date())
    
    with st.sidebar:
        st.title("⚙️ 筛选")
        reps = ["全部"] + sorted(df['对应销售'].unique().tolist())
        sel_rep = st.selectbox("选择销售", reps)
        if st.button("🔄 刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    work_df = df if sel_rep == "全部" else df[df['对应销售'] == sel_rep]

    # --- 过滤名单 ---
    l3 = work_df[(work_df['购车日期'] >= today - timedelta(days=5)) & (work_df['购车日期'] <= today - timedelta(days=3)) & (work_df['购车回访_3天'] == False)]
    l15 = work_df[(work_df['购车日期'] >= today - timedelta(days=17)) & (work_df['购车日期'] <= today - timedelta(days=15)) & (work_df['购车回访_15天'] == False)]
    l30 = work_df[(work_df['购车日期'] >= today - timedelta(days=32)) & (work_df['购车日期'] <= today - timedelta(days=30)) & (work_df['购车回访_30天'] == False)]
    
    b_days = [(today + timedelta(days=i)).strftime('%m%d') for i in range(-3, 4)]
    lbd = work_df[(work_df['生日'].dt.strftime('%m%d').isin(b_days)) & (work_df['生日回访标记'] == False)]

    # 逾期逻辑：30天逾期 & 生日逾期
    ov30 = work_df[(today > work_df['购车日期'] + timedelta(days=32)) & (work_df['购车回访_30天'] == False)].assign(原因='30天逾期')
    def is_b_ov(b):
        if pd.isnull(b): return False
        return today > (b.replace(year=today.year) + timedelta(days=7))
    ov_bd = work_df[work_df.apply(lambda r: is_b_ov(r['生日']) and not r['生日回访标记'], axis=1)].assign(原因='生日逾期')
    lov = pd.concat([ov30, ov_bd])

    # ==========================================
    # 4. UI 渲染
    # ==========================================
    st.title("🚀 精准回访清单")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📅 3日", len(l3))
    m2.metric("🚗 15日", len(l15))
    m3.metric("🌟 30日", len(l30))
    m4.metric("🎂 生日", len(lbd))
    m5.metric("⚠️ 逾期", len(lov), delta_color="inverse")

    # 为了适应手机，我们把任务分成 Tab
    t1, t2, t3, t4 = st.tabs(["🚩节点回访", "🎂生日关怀", "⚠️逾期监控", "📋全部数据"])

    with t1:
        st.write("勾选已完成的任务，完成后点击底部保存")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.success("3日任务")
            e3 = st.data_editor(l3[['姓名','购车回访_3天']], key="e3", disabled=["姓名"], use_container_width=True, hide_index=True)
        with col_b:
            st.warning("15日任务")
            e15 = st.data_editor(l15[['姓名','购车回访_15天']], key="e15", disabled=["姓名"], use_container_width=True, hide_index=True)
        with col_c:
            st.info("30日任务")
            e30 = st.data_editor(l30[['姓名','购车回访_30天']], key="e30", disabled=["姓名"], use_container_width=True, hide_index=True)

    with t2:
        ebd = st.data_editor(lbd[['姓名','生日','生日回访标记']], key="ebd", disabled=["姓名","生日"], use_container_width=True, hide_index=True)

    with t3:
        if lov.empty:
            st.success("暂无逾期")
            eov = pd.DataFrame()
        else:
            # 逾期也可以打勾补录
            st.error("以下是已超期的任务")
            lov_display = lov[['姓名', '原因', '购车回访_30天', '生日回访标记']]
            eov = st.data_editor(lov_display, key="eov", disabled=["姓名","原因"], use_container_width=True, hide_index=True)

    with t4:
        st.dataframe(work_df[['姓名', '购车日期', '对应销售']], use_container_width=True)

    # ==========================================
    # 5. 同步保存
    # ==========================================
    st.markdown('<div class="sync-zone">', unsafe_allow_html=True)
    if st.button("💾 确认并同步勾选结果至云端", type="primary", use_container_width=True):
        with st.status("正在保存...", expanded=False) as status:
            updates = []
            idx_map = {c: df.columns.get_loc(c)+1 for c in ['购车回访_3天','购车回访_15天','购车回访_30天','生日回访标记']}
            
            def collect(editor, col_name):
                for i, r in editor.iterrows():
                    if r[col_name]: updates.append({'range': gspread.utils.rowcol_to_a1(i+2, idx_map[col_name]), 'values': [['TRUE']]})

            collect(e3, '购车回访_3天'); collect(e15, '购车回访_15天'); collect(e30, '购车回访_30天'); collect(ebd, '生日回访标记')
            # 处理逾期补录
            if not eov.empty:
                for i, r in eov.iterrows():
                    if r['购车回访_30天']: updates.append({'range': gspread.utils.rowcol_to_a1(i+2, idx_map['购车回访_30天']), 'values': [['TRUE']]})
                    if r['生日回访标记']: updates.append({'range': gspread.utils.rowcol_to_a1(i+2, idx_map['生日回访标记']), 'values': [['TRUE']]})

            if updates:
                gsheet.batch_update(updates)
                st.cache_data.clear()
                status.update(label="✅ 保存成功！", state="complete")
                st.toast("已同步至 Google 表格", icon="🎉")
                st.rerun()
            else:
                status.update(label="ℹ️ 无新勾选", state="complete")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.warning("⚠️ 无法加载数据")
