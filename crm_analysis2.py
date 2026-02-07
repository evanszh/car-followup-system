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
    /* --- 全局背景 --- */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* --- 表格样式 --- */
    div[data-testid="stDataFrame"] th {
        background-color: #f1f3f5 !important;
        color: #495057 !important;
        font-weight: 600 !important;
    }
    div[data-testid="stDataFrame"] td { 
        padding: 12px 15px !important; 
        height: 55px !important; 
        vertical-align: middle !important;
        font-size: 15px;
    }
    
    /* --- 侧边栏刷新按钮 (次要按钮) 样式 --- */
    /* 恢复为简约白底，避免太抢眼 */
    section[data-testid="stSidebar"] button {
        background-color: #ffffff !important;
        color: #495057 !important;
        border: 1px solid #dee2e6 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s;
    }
    section[data-testid="stSidebar"] button:hover {
        border-color: #1D976C !important;
        color: #1D976C !important;
        background-color: #f8f9fa !important;
    }

    /* --- 底部保存按钮 (主要按钮) 样式 --- */
    /* 现在的颜色：极光绿 (Aurora Green) - 稳重且代表“通过/保存” */
    .bottom-zone button {
        width: 100%;
        /* 这里的渐变色：从深翠绿(#1D976C) 到 清新绿(#93F9B9) */
        background: linear-gradient(135deg, #1D976C 0%, #48c6ef 100%) !important; 
        /* 或者尝试更商务的深海蓝，如下行所示 (如果不喜欢绿色，取消下行注释) */
        /* background: linear-gradient(135deg, #2C3E50 0%, #4CA1AF 100%) !important; */
        
        color: white !important;
        border: none !important;
        padding: 14px 24px !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        border-radius: 50px !important;
        box-shadow: 0 8px 15px rgba(29, 151, 108, 0.2) !important;
        letter-spacing: 1px !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    
    /* 底部按钮悬停效果 */
    .bottom-zone button:hover {
        transform: translateY(-3px) scale(1.01) !important;
        box-shadow: 0 12px 25px rgba(29, 151, 108, 0.35) !important;
        filter: brightness(1.05) !important;
    }
    
    /* 底部按钮点击效果 */
    .bottom-zone button:active {
        transform: translateY(1px) !important;
        box-shadow: 0 4px 8px rgba(29, 151, 108, 0.2) !important;
    }
    
    /* 底部区域容器 */
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

    /* --- 指标卡片优化 --- */
    [data-testid="stMetric"] { 
        background-color: #ffffff; 
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 6px rgba(0,0,0,0.02); 
        padding: 15px; 
        border-radius: 12px; 
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
        # 这个按钮会自动应用上面定义的 section[data-testid="stSidebar"] button 样式
        # 也就是简约白色样式
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
   # --- 筛选任务 (修改后：包含逾期宽限期) ---
    
    # 规则1：首次回访 (原 3-8天 -> 改为 3-11天)
    # 这样第 9,10,11 天的任务依然会留在这里，直到第12天彻底消失
    l3 = work_df[
        (work_df['diff_days'] >= 3) & 
        (work_df['diff_days'] <= 11) &  # <--- 修改了这里，从 8 改为 11
        (work_df['购车回访_3天'] == False)
    ]

    # 规则2：二次回访 (原 15-20天 -> 改为 15-23天)
    l15 = work_df[
        (work_df['diff_days'] >= 15) & 
        (work_df['diff_days'] <= 23) &  # <--- 修改了这里，从 20 改为 23
        (work_df['购车回访_15天'] == False)
    ]

    # 规则3：周年回访 (原 360-365天 -> 改为 360-368天)
    l360 = work_df[
        (work_df['diff_days'] >= 360) & 
        (work_df['diff_days'] <= 368) & # <--- 修改了这里，从 365 改为 368
        (work_df['购车回访_30天'] == False)
    ]
    
    # 规则4：生日回访 (原 0~30天 -> 改为 -3~30天)
    # 包含了过去3天内的生日
    lbd = work_df[
        (work_df['bday_diff'] >= -3) &  # <--- 修改了这里，从 0 改为 -3
        (work_df['bday_diff'] <= 30) & 
        (work_df['生日回访标记'] == False)
    ].sort_values('bday_diff')

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
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📅 首次回访", f"{len(l3)}人", help="3-8天")
    col2.metric("🚗 二次回访", f"{len(l15)}人", help="15-20天")
    col3.metric("🌟 周年回访", f"{len(l360)}人", help="满一年")
    col4.metric("🎂 生日提醒", f"{len(lbd)}人", help="未来30天")
    col5.metric("⚠️ 近期逾期", f"{len(lov)}人", delta_color="inverse")

    st.markdown("---")

    t1, t2, t3 = st.tabs(["📋 节点回访任务", "🎂 生日关怀任务", "⚠️ 逾期警报"])
    
    hide_cfg = {"_row_idx": None}

    with t1:
        st.info("💡 提示：勾选右侧方框代表【已完成】，别忘了点击底部的绿色大按钮保存哦！")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 1️⃣ 首次回访")
            st.caption("购车后 3-8 天")
            e3 = st.data_editor(l3[['姓名', '对应销售', '购车回访_3天', '_row_idx']], 
                key="e3", disabled=["姓名", '对应销售', "_row_idx"], column_config=hide_cfg, use_container_width=True, hide_index=True)
        
        with c2:
            st.markdown("### 2️⃣ 二次回访")
            st.caption("购车后 15-20 天")
            e15 = st.data_editor(l15[['姓名', '对应销售', '购车回访_15天', '_row_idx']], 
                key="e15", disabled=["姓名", '对应销售', "_row_idx"], column_config=hide_cfg, use_container_width=True, hide_index=True)
        
        with c3:
            st.markdown("### 3️⃣ 周年回访")
            st.caption("购车满 1 年")
            e360 = st.data_editor(l360[['姓名', '对应销售', '购车回访_30天', '_row_idx']], 
                key="e360", disabled=["姓名", '对应销售', "_row_idx"], 
                column_config={"_row_idx": None, "购车回访_30天": st.column_config.CheckboxColumn("标记完成")}, 
                use_container_width=True, hide_index=True)

    with t2:
        st.markdown("#### 🎂 本月及下月寿星 (30天内)")
        lbd_display = lbd.copy()
        lbd_display['倒计时'] = lbd_display['bday_diff'].apply(lambda x: "🎉 今天!" if x==0 else f"还有 {x} 天")
        lbd_display['生日日期'] = lbd_display['生日'].dt.strftime('%m月%d日')
        
        ebd = st.data_editor(
            lbd_display[['姓名', '对应销售', '生日日期', '倒计时', '生日回访标记', '_row_idx']], 
            key="ebd", disabled=["姓名", '对应销售', "生日日期", "倒计时", "_row_idx"], 
            column_config=hide_cfg, use_container_width=True, hide_index=True
        )

    with t3:
        if lov.empty:
            st.success("✨ 太棒了！当前没有任何逾期任务。")
        else:
            st.error(f"发现 {len(lov)} 个逾期任务 (仅显示最近3天逾期，请尽快补救)")
            st.dataframe(lov[['姓名', '对应销售', '原因', '购车日期', '生日']], use_container_width=True)

    # ==========================================
    # 4. 底部保存区域 (美化)
    # ==========================================
    st.markdown("<br><br>", unsafe_allow_html=True) 
    
    # 这里的 class="bottom-zone" 会触发 CSS 样式
    st.markdown('<div class="bottom-zone">', unsafe_allow_html=True)
    st.write("📝 完成上述勾选后，请点击下方按钮同步至数据库")
    
    # 这个按钮因为在 .bottom-zone 里面，会应用极光绿渐变样式
    if st.button("💾 确认并同步所有更改 (Save Changes)"):
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

            collect_updates(e3, '购车回访_3天')
            collect_updates(e15, '购车回访_15天')
            collect_updates(e360, '购车回访_30天')
            collect_updates(ebd, '生日回访标记')
            
            if updates:
                try:
                    gsheet.batch_update(updates)
                    st.cache_data.clear()
                    status.update(label="✅ 同步成功！页面即将刷新...", state="complete")
                    st.balloons()
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

