import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# ==========================================
# 1. 基础配置与视觉优化 (CSS)
# ==========================================
st.set_page_config(page_title="回访工作台", layout="wide", page_icon="🚗")

st.markdown("""
    <style>
    /* --- 全局字体与配色优化 --- */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* --- 表格样式优化 --- */
    /* 表头背景色 */
    div[data-testid="stDataFrame"] th {
        background-color: #f1f3f5 !important;
        color: #495057 !important;
        font-weight: 600 !important;
    }
    /* 增大行高，适配手指点击 */
    div[data-testid="stDataFrame"] td { 
        padding: 12px 15px !important; 
        height: 55px !important; 
        vertical-align: middle !important;
        font-size: 15px;
    }
    
    /* --- 指标卡片 (Metric) --- */
    [data-testid="stMetric"] { 
        background-color: #ffffff; 
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03); 
        padding: 15px; 
        border-radius: 12px; 
        transition: transform 0.2s;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    
    /* --- 底部保存按钮深度美化 (重点) --- */
    .sync-container {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 999;
        width: 90%;
        max-width: 600px;
    }
    
    /* 定制 Streamlit 按钮样式 */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #0061f2 0%, #00c6f9 100%); /* 现代渐变蓝 */
        color: white !important;
        border: none;
        padding: 12px 24px;
        font-size: 18px !important;
        font-weight: 600 !important;
        border-radius: 50px !important; /* 圆角胶囊样式 */
        box-shadow: 0 10px 20px rgba(0, 97, 242, 0.3);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        letter-spacing: 1px;
    }
    
    /* 按钮悬停效果 */
    div.stButton > button:hover {
        transform: translateY(-2px) scale(1.01);
        box-shadow: 0 14px 28px rgba(0, 97, 242, 0.4);
        background: linear-gradient(135deg, #0056d6 0%, #00b3e3 100%);
    }
    
    /* 按钮点击效果 */
    div.stButton > button:active {
        transform: translateY(1px);
        box-shadow: 0 5px 10px rgba(0, 97, 242, 0.3);
    }
    
    /* 底部区域背景装饰 */
    .bottom-zone {
        background-color: white;
        padding: 30px;
        border-radius: 20px;
        border: 1px solid #edf2f7;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.02);
        margin-top: 40px;
        margin-bottom: 20px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

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
    df['_row_idx'] = range(2, len(df) + 2)
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
# 2. 核心逻辑
# ==========================================
gsheet = init_connection()
if gsheet:
    df = load_data_cached(gsheet)
else:
    st.stop()

if not df.empty:
    today = pd.to_datetime(datetime.now().date())
    
    with st.sidebar:
        st.header("⚙️ 筛选面板")
        if '对应销售' in df.columns:
            sales_list = sorted([str(x) for x in df['对应销售'].unique() if str(x).strip() != ''])
            reps = ["全部"] + sales_list
            sel_rep = st.selectbox("选择销售顾问", reps)
        else:
            sel_rep = "全部"
        
        st.markdown("---")
        if st.button("🔄 刷新最新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    work_df = df if sel_rep == "全部" else df[df['对应销售'] == sel_rep].copy()
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

    # --- 筛选任务 ---
    l3 = work_df[(work_df['diff_days'] >= 3) & (work_df['diff_days'] <= 8) & (work_df['购车回访_3天'] == False)]
    l15 = work_df[(work_df['diff_days'] >= 15) & (work_df['diff_days'] <= 20) & (work_df['购车回访_15天'] == False)]
    l360 = work_df[(work_df['diff_days'] >= 360) & (work_df['diff_days'] <= 365) & (work_df['购车回访_30天'] == False)]
    lbd = work_df[(work_df['bday_diff'] >= 0) & (work_df['bday_diff'] <= 30) & (work_df['生日回访标记'] == False)].sort_values('bday_diff')

    # --- 逾期监控 ---
    ov_l3 = work_df[(work_df['diff_days'] > 8) & (work_df['diff_days'] <= 11) & (work_df['购车回访_3天'] == False)].assign(原因='首次逾期')
    ov_l15 = work_df[(work_df['diff_days'] > 20) & (work_df['diff_days'] <= 23) & (work_df['购车回访_15天'] == False)].assign(原因='二次逾期')
    ov_l360 = work_df[(work_df['diff_days'] > 365) & (work_df['diff_days'] <= 368) & (work_df['购车回访_30天'] == False)].assign(原因='周年逾期')
    ov_bd = work_df[(work_df['bday_diff'] >= -3) & (work_df['bday_diff'] < 0) & (work_df['生日回访标记'] == False)].assign(原因='生日逾期')
    lov = pd.concat([ov_l3, ov_l15, ov_l360, ov_bd])

    # ==========================================
    # 3. UI 展示
    # ==========================================
    st.title("🚀 客户回访控制台")
    st.caption(f"当前日期: {today.strftime('%Y-%m-%d')} | 操作员: {sel_rep}")
    
    # 指标卡片
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📅 首次回访", f"{len(l3)}人", help="3-8天")
    col2.metric("🚗 二次回访", f"{len(l15)}人", help="15-20天")
    col3.metric("🌟 周年回访", f"{len(l360)}人", help="满一年")
    col4.metric("🎂 生日提醒", f"{len(lbd)}人", help="未来30天")
    col5.metric("⚠️ 近期逾期", f"{len(lov)}人", delta_color="inverse")

    st.markdown("---")

    # 分页显示
    t1, t2, t3 = st.tabs(["📋 节点回访任务", "🎂 生日关怀任务", "⚠️ 逾期警报"])
    
    hide_cfg = {"_row_idx": None}

    with t1:
        st.info("💡 提示：勾选右侧方框代表【已完成】，别忘了点击底部的蓝色大按钮保存哦！")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 1️⃣ 首次回访")
            st.caption("购车后 3-8 天")
            e3 = st.data_editor(l3[['姓名', '对应销售', '购车回访_3天', '_row_idx']], 
                key="e3", disabled=["姓名", "对应销售", "_row_idx"], column_config=hide_cfg, use_container_width=True, hide_index=True)
        
        with c2:
            st.markdown("### 2️⃣ 二次回访")
            st.caption("购车后 15-20 天")
            e15 = st.data_editor(l15[['姓名', '对应销售', '购车回访_15天', '_row_idx']], 
                key="e15", disabled=["姓名", "对应销售", "_row_idx"], column_config=hide_cfg, use_container_width=True, hide_index=True)
        
        with c3:
            st.markdown("### 3️⃣ 周年回访")
            st.caption("购车满 1 年")
            e360 = st.data_editor(l360[['姓名', '对应销售', '购车回访_30天', '_row_idx']], 
                key="e360", disabled=["姓名", "对应销售", "_row_idx"], 
                column_config={"_row_idx": None, "购车回访_30天": st.column_config.CheckboxColumn("标记完成")}, 
                use_container_width=True, hide_index=True)

    with t2:
        st.markdown("#### 🎂 本月及下月寿星 (30天内)")
        lbd_display = lbd.copy()
        lbd_display['倒计时'] = lbd_display['bday_diff'].apply(lambda x: "🎉 今天!" if x==0 else f"还有 {x} 天")
        lbd_display['生日日期'] = lbd_display['生日'].dt.strftime('%m月%d日')
        
        ebd = st.data_editor(
            lbd_display[['姓名', '对应销售', '生日日期', '倒计时', '生日回访标记', '_row_idx']], 
            key="ebd", disabled=["姓名", "对应销售", "生日日期", "倒计时", "_row_idx"], 
            column_config=hide_cfg, use_container_width=True, hide_index=True
        )

    with t3:
        if lov.empty:
            st.success("✨ 太棒了！当前没有任何逾期任务。")
        else:
            st.error(f"发现 {len(lov)} 个逾期任务 (仅显示最近3天逾期，请尽快补救)")
            st.dataframe(lov[['姓名', '对应销售', '原因', '购车日期', '生日']], use_container_width=True)

    # ==========================================
    # 4. 底部保存区域 (UI 重点优化)
    # ==========================================
    st.markdown("<br><br>", unsafe_allow_html=True) # 占位符，防止内容被按钮遮挡
    
    st.markdown('<div class="bottom-zone">', unsafe_allow_html=True)
    st.write("📝 完成上述勾选后，请点击下方按钮同步至数据库")
    
    # 这是一个全宽的大按钮，样式由顶部的 CSS 控制
    if st.button("💾 确认并同步所有更改 (Save Changes)", type="primary"):
        with st.status("🚀 正在连接云端数据库...", expanded=True) as status:
            updates = []
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

            st.write("正在汇总节点回访数据...")
            collect_updates(e3, '购车回访_3天')
            collect_updates(e15, '购车回访_15天')
            collect_updates(e360, '购车回访_30天')
            st.write("正在汇总生日回访数据...")
            collect_updates(ebd, '生日回访标记')
            
            if updates:
                try:
                    st.write(f"正在写入 {len(updates)} 条更新记录...")
                    gsheet.batch_update(updates)
                    st.cache_data.clear()
                    status.update(label="✅ 同步成功！页面即将刷新...", state="complete")
                    st.balloons() # 成功撒花特效
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    status.update(label="❌ 保存失败", state="error")
                    st.error(f"写入 Google Sheet 时出错: {e}")
            else:
                status.update(label="ℹ️ 未检测到任何修改", state="complete")
                time.sleep(1)
                
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.warning("⚠️ 数据加载为空，请检查 Google Sheet 格式或网络连接")
