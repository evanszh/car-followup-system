import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# ==========================================
# 1. 基础配置与连接
# ==========================================
st.set_page_config(page_title="回访工作台", layout="wide")

st.markdown("""
    <style>
    /* 增大表格行高，方便手指点击 */
    div[data-testid="stDataFrame"] td { padding: 15px !important; height: 60px !important; }
    
    /* 美化指标卡片 */
    [data-testid="stMetric"] { 
        background-color: #ffffff; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
        padding: 10px; 
        border-radius: 10px; 
        border-left: 5px solid #dee2e6; 
    }
    
    /* 去除输入框红框 */
    button:focus, input:focus, select:focus { 
        outline: none !important; 
        box-shadow: none !important; 
        border-color: #28a745 !important; 
    }
    
    /* 底部保存区域样式 */
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

@st.cache_resource
def init_connection():
    """初始化 Google Sheet 连接"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # 请确保文件名与你本地的一致
            creds = ServiceAccountCredentials.from_json_keyfile_name("glass-quest-482522-t7-977042a18a8b.json", scope)
        
        client = gspread.authorize(creds)
        return client.open("中国市场回访表").get_worksheet(0)
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None

@st.cache_data(ttl=600)
def load_data_cached(_sheet):
    """读取数据并预处理"""
    if _sheet is None: return pd.DataFrame()
    
    data = _sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # 记录原始行号
    df['_row_idx'] = range(2, len(df) + 2)
    
    # 日期转换
    df['购车日期'] = pd.to_datetime(df['购车日期'], errors='coerce')
    df['生日'] = pd.to_datetime(df['生日'], errors='coerce')
    
    # 布尔值标准化
    target_cols = ['购车回访_3天', '购车回访_15天', '购车回访_30天', '生日回访标记']
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).upper() in ['TRUE', '是', '1', 'CHECKED', 'V'])
        else:
            df[col] = False
            
    return df

# ==========================================
# 2. 核心逻辑处理
# ==========================================
gsheet = init_connection()
if gsheet:
    df = load_data_cached(gsheet)
else:
    st.stop()

if not df.empty:
    today = pd.to_datetime(datetime.now().date())
    
    # --- 侧边栏筛选 ---
    with st.sidebar:
        st.title("⚙️ 筛选工作台")
        if '对应销售' in df.columns:
            sales_list = sorted([str(x) for x in df['对应销售'].unique() if str(x).strip() != ''])
            reps = ["全部"] + sales_list
            sel_rep = st.selectbox("选择销售", reps)
        else:
            sel_rep = "全部"
            
        if st.button("🔄 刷新数据", type="secondary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    work_df = df if sel_rep == "全部" else df[df['对应销售'] == sel_rep].copy()

    # --- 逻辑计算 ---
    work_df['diff_days'] = (today - work_df['购车日期']).dt.days

    def get_days_to_bday(bday_date):
        if pd.isnull(bday_date): return 9999
        try:
            this_year_bday = bday_date.replace(year=today.year)
        except ValueError:
            this_year_bday = bday_date.replace(year=today.year, day=28)
            
        diff = (this_year_bday - today).days
        
        if diff < -3: 
            try:
                next_year_bday = bday_date.replace(year=today.year + 1)
            except ValueError:
                next_year_bday = bday_date.replace(year=today.year + 1, day=28)
            diff = (next_year_bday - today).days
        return diff

    work_df['bday_diff'] = work_df['生日'].apply(get_days_to_bday)

    # --- 任务筛选 ---
    # 规则1：首次回访 (3-8天)
    l3 = work_df[
        (work_df['diff_days'] >= 3) & 
        (work_df['diff_days'] <= 8) & 
        (work_df['购车回访_3天'] == False)
    ]

    # 规则2：二次回访 (15-20天)
    l15 = work_df[
        (work_df['diff_days'] >= 15) & 
        (work_df['diff_days'] <= 20) & 
        (work_df['购车回访_15天'] == False)
    ]

    # 规则3：周年回访 (360-365天)
    l360 = work_df[
        (work_df['diff_days'] >= 360) & 
        (work_df['diff_days'] <= 365) & 
        (work_df['购车回访_30天'] == False)
    ]
    
    # 规则4：生日回访 (提前30天 ~ 当天)
    lbd = work_df[
        (work_df['bday_diff'] >= 0) & 
        (work_df['bday_diff'] <= 30) & 
        (work_df['生日回访标记'] == False)
    ].sort_values('bday_diff')

    # 规则5：逾期监控
    ov_l3 = work_df[(work_df['diff_days'] > 8) & (work_df['diff_days'] <= 11) & (work_df['购车回访_3天'] == False)].assign(原因='首次回访逾期')
    ov_l15 = work_df[(work_df['diff_days'] > 20) & (work_df['diff_days'] <= 23) & (work_df['购车回访_15天'] == False)].assign(原因='二次回访逾期')
    ov_l360 = work_df[(work_df['diff_days'] > 365) & (work_df['diff_days'] <= 368) & (work_df['购车回访_30天'] == False)].assign(原因='周年回访逾期')
    ov_bd = work_df[(work_df['bday_diff'] >= -3) & (work_df['bday_diff'] < 0) & (work_df['生日回访标记'] == False)].assign(原因='生日回访逾期')
    
    lov = pd.concat([ov_l3, ov_l15, ov_l360, ov_bd])

    # ==========================================
    # 3. UI 渲染展示
    # ==========================================
    st.title("🚀 客户回访控制台")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📅 首次 (3-8天)", len(l3))
    m2.metric("🚗 二次 (15-20天)", len(l15))
    m3.metric("🌟 周年 (1年)", len(l360))
    m4.metric("🎂 生日 (30天内)", len(lbd))
    m5.metric("⚠️ 近期逾期", len(lov), delta_color="inverse")

    t1, t2, t3 = st.tabs(["🚩节点回访", "🎂生日关怀", "⚠️逾期监控"])

    hide_cfg = {"_row_idx": None}

    with t1:
        st.caption("任务将在进入时间窗口后自动出现，完成后请勾选并保存。")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.success("首次回访 (3-8天)")
            # 增加 '对应销售' 列显示
            e3 = st.data_editor(
                l3[['姓名', '对应销售', '购车回访_3天', '_row_idx']], 
                key="e3", 
                disabled=["姓名", "对应销售", "_row_idx"], 
                column_config=hide_cfg, 
                use_container_width=True, 
                hide_index=True
            )
            
        with col_b:
            st.warning("二次回访 (15-20天)")
            # 增加 '对应销售' 列显示
            e15 = st.data_editor(
                l15[['姓名', '对应销售', '购车回访_15天', '_row_idx']], 
                key="e15", 
                disabled=["姓名", "对应销售", "_row_idx"], 
                column_config=hide_cfg, 
                use_container_width=True, 
                hide_index=True
            )
            
        with col_c:
            st.info("周年回访 (360-365天)")
            # 增加 '对应销售' 列显示
            e360 = st.data_editor(
                l360[['姓名', '对应销售', '购车回访_30天', '_row_idx']], 
                key="e360", 
                disabled=["姓名", "对应销售", "_row_idx"], 
                column_config={
                    "_row_idx": None,
                    "购车回访_30天": st.column_config.CheckboxColumn("完成周年回访")
                }, 
                use_container_width=True, 
                hide_index=True
            )

    with t2:
        st.write("🎂 未来30天内过生日的客户（含当天）")
        
        lbd_display = lbd.copy()
        lbd_display['倒计时'] = lbd_display['bday_diff'].apply(lambda x: "🎉今天!" if x==0 else f"还有 {x} 天")
        lbd_display['生日日期'] = lbd_display['生日'].dt.strftime('%m月%d日')
        
        # 增加 '对应销售' 列显示
        ebd = st.data_editor(
            lbd_display[['姓名', '对应销售', '生日日期', '倒计时', '生日回访标记', '_row_idx']], 
            key="ebd", 
            disabled=["姓名", "对应销售", "生日日期", "倒计时", "_row_idx"], 
            column_config=hide_cfg, 
            use_container_width=True, 
            hide_index=True
        )

    with t3:
        if lov.empty:
            st.success("🎉 当前没有处于宽限期内的逾期任务")
        else:
            st.error("以下是逾期但未超过3天的任务 (请尽快处理，超过3天将不再显示)")
            # 逾期列表也加上销售
            st.dataframe(lov[['姓名', '对应销售', '原因', '购车日期', '生日']], use_container_width=True)

  

    # ==========================================
    # 4. 数据保存与同步
    # ==========================================
    st.markdown('<div class="sync-zone">', unsafe_allow_html=True)
    if st.button("💾 确认并同步勾选结果至云端", type="primary", use_container_width=True):
        with st.status("正在连接 Google Sheet 保存数据...", expanded=False) as status:
            updates = []
            
            # 动态获取列的索引位置
            cols_to_sync = ['购车回访_3天', '购车回访_15天', '购车回访_30天', '生日回访标记']
            col_indices = {c: df.columns.get_loc(c) + 1 for c in cols_to_sync}
            
            def collect_updates(editor_df, check_col):
                if editor_df is None or editor_df.empty: return
                for index, row in editor_df.iterrows():
                    if row[check_col]:
                        sheet_row = row['_row_idx']
                        sheet_col = col_indices[check_col]
                        cell_loc = gspread.utils.rowcol_to_a1(sheet_row, sheet_col)
                        updates.append({'range': cell_loc, 'values': [['TRUE']]})

            collect_updates(e3, '购车回访_3天')
            collect_updates(e15, '购车回访_15天')
            collect_updates(e360, '购车回访_30天')
            collect_updates(ebd, '生日回访标记')
            
            if updates:
                try:
                    gsheet.batch_update(updates)
                    st.cache_data.clear()
                    status.update(label="✅ 保存成功！", state="complete")
                    st.toast("已同步至 Google 表格", icon="🎉")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    status.update(label="❌ 保存失败", state="error")
                    st.error(f"写入 Google Sheet 时出错: {e}")
            else:
                status.update(label="ℹ️ 没有检测到新的勾选", state="complete")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.warning("⚠️ 数据加载为空，请检查 Google Sheet 格式或网络连接")


