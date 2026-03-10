import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client
import numpy as np
from scipy.integrate import odeint
import ssl
import os

# ==================== 强化SSL绕过（解决之前报错） ====================
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

# ==================== Supabase配置 ====================
SUPABASE_URL = "https://toesqwoexmuowjsxvxxx.supabase.co"      # ← 改成你的
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRvZXNxd29leG11b3dqc3h2eHh4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3Nzc5MTIsImV4cCI6MjA4ODM1MzkxMn0.W0lOjxGOqwtv43gjD96k1gL9r-gjAGkN2icKWFoNwhc"                   # ← 改成你的
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== 系统标题 + 美化CSS ====================
st.set_page_config(page_title="脑卒中预警物联网系统", layout="wide")
st.title("🧠 生理信号监测 - 脑数字孪生物联网系统")
st.markdown("**极速优化版**：缓存加速 + 选择病人置顶 + 标题同等大字体")

st.markdown("""
<style>
    [data-testid="stSidebar"] h1 {font-size: 1.8rem !important; text-align: center !important; font-weight: bold;}
    .stButton > button {font-size: 1.5rem !important; width: 100% !important; text-align: center !important; margin: 4px 0;}
    .stButton > button:hover {background-color: #ff4d4d !important; color: white !important;}
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {background-color: #1E90FF !important; color: white !important;}
</style>
""", unsafe_allow_html=True)

# ==================== 缓存函数（核心加速！） ====================
@st.cache_data(ttl=60)   # 病人列表缓存60秒
def get_patients():
    try:
        data = supabase.table("signal").select("patient_id").execute().data
        patients = [d.get("patient_id") for d in data if d.get("patient_id")]
        patients = sorted(set(p for p in patients if p)) if patients else ["默认病人"]
        return ["全部病人"] + patients + ["新建病人"]
    except:
        return ["全部病人", "默认病人"]

@st.cache_data(ttl=30)   # 数据查询缓存30秒
def get_data(patient, limit=10, order="desc"):
    query = supabase.table("signal").select("*")
    if patient != "全部病人":
        query = query.eq("patient_id", patient)
    if order == "desc":
        query = query.order("id", desc=True)
    data = query.limit(limit).execute().data
    return pd.DataFrame(data) if data else pd.DataFrame()

# ==================== 病人选择状态 ====================
if 'current_patient' not in st.session_state:
    st.session_state.current_patient = "全部病人"

# ==================== 左侧布局：选择病人置顶（标题同等大） ====================
st.sidebar.markdown("<h1>👤 选择病人</h1>", unsafe_allow_html=True)

patients_list = get_patients()
selected = st.sidebar.selectbox("", patients_list, 
                                index=patients_list.index(st.session_state.current_patient) 
                                if st.session_state.current_patient in patients_list else 0)

if selected == "新建病人":
    new_p = st.sidebar.text_input("输入新病人姓名/编号")
    if new_p and st.sidebar.button("✅ 创建并切换"):
        st.session_state.current_patient = new_p
        st.rerun()
else:
    st.session_state.current_patient = selected

current_patient = st.session_state.current_patient

st.sidebar.markdown("---")
st.sidebar.markdown("<h1>选择功能</h1>", unsafe_allow_html=True)

# ==================== 功能按钮 ====================
pages = ["📤 数据上传", "📊 仪表盘", "📈 可视化图表", "🚨 异常报警", "🧬 脑数字孪生模型", "⚙️ 阈值设置"]
for p in pages:
    if st.sidebar.button(p, key=p, use_container_width=True):
        st.session_state.current_page = p

page = st.session_state.get('current_page', "📤 数据上传")

thresholds = {
    "heart_rate_min": 60, "heart_rate_max": 100,
    "systolic_max": 140, "diastolic_max": 90,
    "spo2_min": 95
}

# ==================== 页面1：数据上传 ====================
if page == "📤 数据上传":
    st.header("上传Excel / 传感器数据")
    upload_patient = st.selectbox("本次数据属于哪个病人", patients_list, index=0)
    if upload_patient == "新建病人":
        upload_patient = st.text_input("新建病人姓名")
    
    if st.button("🗑️ 清空当前病人所有数据"):
        if current_patient != "全部病人":
            supabase.table("signal").delete().eq("patient_id", current_patient).execute()
            st.success(f"已清空 {current_patient}")
            st.rerun()

    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "csv"])
    if uploaded_file and upload_patient and upload_patient not in ["全部病人", "新建病人"]:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            df["timestamp"] = [datetime.now().strftime("%Y-%m-%d %H:%M:%S") for _ in range(len(df))]
        df["patient_id"] = upload_patient
        
        timestamps = df["timestamp"].tolist()
        supabase.table("signal").delete().in_("timestamp", timestamps).eq("patient_id", upload_patient).execute()
        supabase.table("signal").insert(df.to_dict(orient="records")).execute()
        st.success(f"🎉 {len(df)} 条数据已存入 **{upload_patient}**（同时间戳自动覆盖）")
        st.balloons()

    with st.expander("🔌 传感器实时上传接口", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            hr = st.number_input("❤️ 心率 (bpm)", value=80)
            sbp = st.number_input("🩸 收缩压", value=120)
        with col2:
            dbp = st.number_input("🩸 舒张压", value=80)
            spo2 = st.number_input("🫁 血氧 (%)", value=98)
        if st.button("🚀 实时发送", type="primary") and upload_patient and upload_patient not in ["全部病人", "新建病人"]:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_data = [{"timestamp": ts, "heart_rate": hr, "systolic_bp": sbp, "diastolic_bp": dbp, "spo2": spo2, "patient_id": upload_patient}]
            supabase.table("signal").delete().eq("timestamp", ts).eq("patient_id", upload_patient).execute()
            supabase.table("signal").insert(new_data).execute()
            st.success(f"✅ 已实时存入 **{upload_patient}**")

# ==================== 其他页面（使用缓存后的 get_data） ====================
elif page == "📊 仪表盘":
    st.header(f"实时仪表盘 - {current_patient}")
    df = get_data(current_patient, 1)
    if not df.empty:
        latest = df.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("❤️ 心率", f"{latest['heart_rate']:.1f} bpm")
        with col2: st.metric("🩸 血压", f"{latest['systolic_bp']:.0f}/{latest['diastolic_bp']:.0f} mmHg")
        with col3: st.metric("🫁 血氧", f"{latest['spo2']:.1f} %")
        with col4:
            risk = "⚠️ 高风险" if latest["systolic_bp"] > thresholds["systolic_max"] else "✅ 正常"
            st.metric("卒中风险", risk)
    else:
        st.info("该病人还没有数据")

elif page == "📈 可视化图表":
    st.header(f"历史趋势图表 - {current_patient}")
    df = get_data(current_patient, 50, "asc")
    if not df.empty:
        st.plotly_chart(px.line(df, x="timestamp", y="heart_rate", title="心率趋势"), use_container_width=True)
        st.plotly_chart(px.line(df, x="timestamp", y=["systolic_bp", "diastolic_bp"], title="血压趋势"), use_container_width=True)
        st.plotly_chart(px.line(df, x="timestamp", y="spo2", title="血氧趋势"), use_container_width=True)
    else:
        st.info("该病人还没有数据")

elif page == "🚨 异常报警":
    st.header(f"信号异常报警 - {current_patient}")
    df = get_data(current_patient, 50)
    if not df.empty:
        def highlight_abnormal(val, col_name):
            if col_name == "heart_rate" and (val < thresholds["heart_rate_min"] or val > thresholds["heart_rate_max"]):
                return "color: white; background-color: #ff4d4d; font-weight: bold"
            if col_name in ["systolic_bp", "diastolic_bp"] and val > thresholds["systolic_max"]:
                return "color: white; background-color: #ff4d4d; font-weight: bold"
            if col_name == "spo2" and val < thresholds["spo2_min"]:
                return "color: white; background-color: #ff4d4d; font-weight: bold"
            return ""
        
        df_display = df.copy()
        df_display["异常类型"] = ""
        for idx, row in df.iterrows():
            abnormal_list = []
            if row["heart_rate"] < thresholds["heart_rate_min"] or row["heart_rate"] > thresholds["heart_rate_max"]:
                abnormal_list.append(f"心率({row['heart_rate']:.1f})")
            if row["systolic_bp"] > thresholds["systolic_max"] or row["diastolic_bp"] > thresholds["diastolic_max"]:
                abnormal_list.append(f"血压({row['systolic_bp']:.0f}/{row['diastolic_bp']:.0f})")
            if row["spo2"] < thresholds["spo2_min"]:
                abnormal_list.append(f"血氧({row['spo2']:.1f})")
            if abnormal_list:
                df_display.loc[idx, "异常类型"] = "、".join(abnormal_list)
        
        styled_df = df_display.style.apply(lambda x: [highlight_abnormal(v, col) for col, v in x.items()], axis=1)
        
        if not df_display[df_display["异常类型"] != ""].empty:
            st.error(f"🚨 发现 {len(df_display[df_display['异常类型'] != ''])} 条异常记录！")
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ 所有信号正常")
    else:
        st.info("该病人还没有数据")

elif page == "🧬 脑数字孪生模型":
    st.header(f"🧬 大脑数字孪生体模型 - {current_patient}")
    df = get_data(current_patient, 1)
    if not df.empty and st.button("🚀 运行内置简易模型"):
        with st.spinner("高性能数值计算中..."):
            latest = df.iloc[0]
            def cerebral_model(y, t, bp): return [-0.5*y[0] + 0.3*(bp-100) + np.random.normal(0,0.5)]
            t = np.linspace(0,60,600)
            sol = odeint(cerebral_model, [10], t, args=(latest["systolic_bp"],))
            risk = min(max(15 + (latest["systolic_bp"]-120)*0.8 + (100-latest["spo2"])*0.5, 5), 95)
            st.plotly_chart(px.line(x=t, y=sol[:,0], title="大脑颅内压动态演化曲线"), use_container_width=True)
            st.success(f"**卒中风险概率：{risk:.1f}%**")

    with st.expander("🔌 高级模型接入接口（上传 .py 文件）", expanded=True):
        model_file = st.file_uploader("上传脑数字孪生模型代码 (.py)", type=["py"])
        if model_file and st.button("加载并运行外部模型"):
            try:
                code = model_file.read().decode("utf-8")
                local_vars = {}
                exec(code, globals(), local_vars)
                if "run_brain_model" in local_vars:
                    latest = df.iloc[0] if not df.empty else None
                    fig, risk = local_vars["run_brain_model"](latest)
                    st.plotly_chart(fig, use_container_width=True)
                    st.success(f"**外部模型运行成功！卒中风险：{risk:.1f}%**")
                else:
                    st.error("文件必须定义 def run_brain_model(latest_data) 函数")
            except Exception as e:
                st.error(f"加载失败：{e}")

else:
    st.header("阈值设置")
    st.code(str(thresholds))

st.caption(f"当前查看病人：**{current_patient}** | 数据完全独立存储 | 已开启缓存加速")