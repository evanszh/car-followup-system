import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import plotly.express as px

# ==========================================
# 1. 核心连接与数据加载 (增加缓存保护)
# ==========================================
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # 💡 核心修改：不再读取文件，而是读取 Streamlit 的后台配置
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # 这行是为了让你在本地测试时依然能用
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
    
    # 强制转换日期格式
    df['购车日期'] = pd.to_datetime(df['购车日期'], errors='coerce')
    df['生日'] = pd.to_datetime(df['生日'], errors='coerce')
    
    # 预处理标记列：统一转为布尔值
    target_cols = ['购车回访_3天', '购车回访_15天', '购车回访_30天', '生日回访标记']
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).upper() in ['TRUE', '是', '1', 'CHECKED', 'V'])
        else:
            df[col] = False
    return df

# ==========================================
# 2. 页面配置与 UI 样式
# ==========================================
st.set_page_config(page_title="精准回访工作台", layout="wide")

st.markdown("""
    <style>
    /* --- 顶部指标卡(Metric)美化 --- */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        padding: 15px 20px;
        border-radius: 12px;
        transition: transform 0.2s ease-in-out;
        border-left: 5px solid #dee2e6;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    /* 为指标卡设置分类颜色 */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] { border-left-color: #28a745; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] { border-left-color: #fd7e14; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] { border-left-color: #007bff; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] { border-left-color: #e83e8c; }
    div[data-testid="stHorizontalBlock"] > div:nth-child(5) [data-testid="stMetric"] { border-left-color: #dc3545; background-color: #fff5f5; }

    /* --- 同步按钮美化 & 去掉红框 --- */
    div.stButton > button[kind="primary"] {
        background-color: #28a745;
        color: white;
        border-radius: 10px;
        border: none !important;
        padding: 0.6rem 1rem;
        transition: all 0.3s ease;
        font-weight: bold;
    }
    /* 彻底去掉获得焦点时的红框/边框 */
    div.stButton > button:focus, div.stButton > button:active, div.stButton > button:focus-visible {
        outline: none !important;
        box-shadow: 0 0 0 3px rgba(40, 167, 69, 0.3) !important;
        border: none !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838;
        transform: scale(1.02);
        border: none !important;
    }

    /* 同步区域的外壳装饰 */
    .sync-footer-zone {
        background-color: #f8f9fa;
        padding: 30px;
        border-radius: 20px;
        border: 2px dashed #e9ecef;
        margin-top: 40px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 业务逻辑计算
# ==========================================
gsheet = init_connection()
df = load_data_cached(gsheet)
if not df.empty:
    today = pd.to_datetime(datetime.now().date())

    # --- 侧边栏筛选 ---
    with st.sidebar:
        st.title("🛠️ 管理面板")
        if st.button("🔄 刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        sales_reps = ["全部"] + sorted(df['对应销售'].unique().tolist())
        selected_rep = st.selectbox("选择销售人员", sales_reps)
        
        # 保留原始索引以供同步
        working_df = df if selected_rep == "全部" else df[df['对应销售'] == selected_rep]

    # --- 逻辑过滤函数 ---
    def get_standard_list(days, col):
        """获取处于回访窗口期(目标天数~目标天数+2)的名单"""
        start = today - timedelta(days=days + 2)
        end = today - timedelta(days=days)
        return working_df[(working_df['购车日期'] >= start) & (working_df['购车日期'] <= end) & (working_df[col] == False)]

    def get_overdue_list(df_in):
        """计算特定逾期：30天满月回访逾期 & 生日过去7天逾期"""
        # 1. 30天逾期：购车超过32天且未标记
        o30 = df_in[(today > df_in['购车日期'] + timedelta(days=32)) & (df_in['购车回访_30天'] == False)].copy()
        o30['逾期类型'] = '30天满月逾期'

        # 2. 生日逾期：生日已过去超过7天且未标记
        def is_bday_overdue(b_date):
            if pd.isnull(b_date): return False
            # 将生日对齐到今年
            this_year_bday = b_date.replace(year=today.year)
            return today > (this_year_bday + timedelta(days=7))

        mask_bd = df_in.apply(lambda r: is_bday_overdue(r['生日']) and not r['生日回访标记'], axis=1)
        obd = df_in[mask_bd].copy()
        obd['逾期类型'] = '生日关怀逾期(>7d)'
        
        return pd.concat([o30, obd])

    # 名单分配
    list_3d = get_standard_list(3, '购车回访_3天')
    list_15d = get_standard_list(15, '购车回访_15天')
    list_30d = get_standard_list(30, '购车回访_30天')
    list_ov = get_overdue_list(working_df)
    
    # 生日范围内 (今天 ± 3天)
    b_range = [(today + timedelta(days=i)) for i in range(-3, 4)]
    list_bd = working_df[(working_df['生日'].dt.month.isin([d.month for d in b_range])) & 
                        (working_df['生日'].dt.day.isin([d.day for d in b_range])) & 
                        (working_df['生日回访标记'] == False)]

    # ==========================================
    # 4. 主页面渲染
    # ==========================================
    st.title("🚀 精准分阶段回访系统")
    
    # 指标概览
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("3日待办", len(list_3d))
    m2.metric("15日待办", len(list_15d))
    m3.metric("30日待办", len(list_30d))
    m4.metric("近期生日", len(list_bd))
    m5.metric("⚠️ 严重逾期", len(list_ov), delta_color="inverse")

    # 第一区：常规任务
    st.markdown("### 📅 节点回访任务 (窗口期内)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.success("🚩 第3天：初次关怀")
        e3 = st.data_editor(list_3d[['姓名','购车日期','购车回访_3天']], key="e3", disabled=["姓名","购车日期"], use_container_width=True)
    with c2:
        st.warning("🚩 第15天：用车反馈")
        e15 = st.data_editor(list_15d[['姓名','购车日期','购车回访_15天']], key="e15", disabled=["姓名","购车日期"], use_container_width=True)
    with c3:
        st.info("🚩 第30天：满月维护")
        e30 = st.data_editor(list_30d[['姓名','购车日期','购车回访_30天']], key="e30", disabled=["姓名","购车日期"], use_container_width=True)

    # 第二区：生日与逾期监控
    st.divider()
    ca, cb = st.columns([1, 2])
    with ca:
        st.markdown("### 🎂 生日关怀 (±3日)")
        ebd = st.data_editor(list_bd[['姓名','生日','生日回访标记']], key="ebd", disabled=["姓名","生日"], use_container_width=True)
    
    with cb:
        st.markdown("### ⚠️ 重点逾期监控 (30日/生日+7)")
        if not list_ov.empty:
            # 逾期分布图
            fig = px.bar(list_ov['逾期类型'].value_counts().reset_index(), x='逾期类型', y='count', 
                         color='逾期类型', color_discrete_sequence=['#dc3545', '#fd7e14'], height=250)
            fig.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("目前无严重逾期，跟进非常及时！")

    # 逾期明细展示
    if not list_ov.empty:
        with st.expander("查看具体逾期客户清单"):
            st.table(list_ov[['姓名', '逾期类型', '购车日期', '对应销售']])

    # ==========================================
    # 5. 批量同步逻辑
    # ==========================================
    st.divider()
    if st.button("💾 确认并同步勾选至云端", type="primary"):
        with st.status("正在同步...", expanded=False) as status:
            updates = []
            idx_map = {col: df.columns.get_loc(col) + 1 for col in ['购车回访_3天', '购车回访_15天', '购车回访_30天', '生日回访标记']}
            
            def collect(editor_df, col_key):
                for idx, row in editor_df.iterrows():
                    if row[col_key] == True:
                        updates.append({'range': gspread.utils.rowcol_to_a1(idx + 2, idx_map[col_key]), 'values': [['TRUE']]})

            collect(e3, '购车回访_3天')
            collect(e15, '购车回访_15天')
            collect(e30, '购车回访_30天')
            collect(ebd, '生日回访标记')

            if updates:
                gsheet.batch_update(updates)
                st.cache_data.clear()
                status.update(label="✅ 数据已成功同步！", state="complete")
                st.rerun()
            else:
                status.update(label="ℹ️ 未检测到新勾选", state="complete")
else:

    st.error("无法读取数据，请检查 Google Sheets 是否包含正确表头：姓名, 购车日期, 生日, 对应销售, 购车回访_3天, 购车回访_15天, 购车回访_30天, 生日回访标记")


