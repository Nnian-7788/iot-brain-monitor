import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3

# ==================== 系统标题 ====================
st.set_page_config(page_title="脑卒中预警物联网系统", layout="wide")
st.title("🧠 实时生理信号监测 - 脑卒中动态预警物联网系统")
st.markdown("**当前功能**：Excel上传（模拟传感器传输） + 云端存储 + 可视化仪表盘 + 异常报警")

# ==================== 数据库连接 ====================
def get_db_connection():
    conn = sqlite3.connect('iot_signals.db')  # 数据文件会保存在项目文件夹里
    return conn

# 创建数据库表（第一次运行自动创建）
conn = get_db_connection()
conn.execute('''
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        heart_rate REAL,
        systolic_bp REAL,
        diastolic_bp REAL,
        spo2 REAL
    )
''')
conn.close()

# ==================== 阈值设置（可随时修改） ====================
thresholds = {
    "heart_rate_min": 60, "heart_rate_max": 100,      # 心率正常范围
    "systolic_max": 140, "diastolic_max": 90,        # 血压（脑卒中高危：收缩压>140或舒张压>90）
    "spo2_min": 95                                   # 血氧
}

# ==================== 侧边栏导航 ====================
page = st.sidebar.selectbox("选择功能", ["📤 数据上传", "📊 仪表盘", "📈 可视化图表", "🚨 异常报警", "⚙️ 阈值设置"])

# ==================== 页面1：数据上传（模拟传感器实时传输） ====================
if page == "📤 数据上传":
    st.header("上传Excel文件（模拟传感器数据）")
    uploaded_file = st.file_uploader("选择你的生理信号Excel文件", type=["xlsx", "csv"])
    
    if uploaded_file:
        # 读取Excel或CSV
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.success(f"✅ 成功读取 {len(df)} 条数据！")
        st.dataframe(df.head())  # 显示前几行预览
        
        # 如果没有时间戳，自动添加
        if "timestamp" not in df.columns:
            df["timestamp"] = [datetime.now().strftime("%Y-%m-%d %H:%M:%S") for _ in range(len(df))]
        
        # 存入数据库（模拟传输到云端服务器）
        conn = get_db_connection()
        df.to_sql("signals", conn, if_exists="append", index=False)
        conn.close()
        
        st.balloons()
        st.success("🎉 数据已成功传输并存储到云端数据库！")

# ==================== 页面2：仪表盘（最新数据 + 风险提示） ====================
elif page == "📊 仪表盘":
    st.header("实时仪表盘")
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM signals ORDER BY id DESC LIMIT 10", conn)
    conn.close()
    
    if not df.empty:
        latest = df.iloc[0]  # 最新一条数据
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            hr_color = "red" if not (thresholds["heart_rate_min"] <= latest["heart_rate"] <= thresholds["heart_rate_max"]) else "green"
            st.metric("❤️ 心率", f"{latest['heart_rate']:.1f} bpm", delta=None)
        with col2:
            bp_color = "red" if latest["systolic_bp"] > thresholds["systolic_max"] or latest["diastolic_bp"] > thresholds["diastolic_max"] else "green"
            st.metric("🩸 血压", f"{latest['systolic_bp']:.0f}/{latest['diastolic_bp']:.0f} mmHg")
        with col3:
            spo2_color = "red" if latest["spo2"] < thresholds["spo2_min"] else "green"
            st.metric("🫁 血氧", f"{latest['spo2']:.1f} %")
        with col4:
            risk = "⚠️ 高风险（可能脑卒中）" if bp_color == "red" or hr_color == "red" else "✅ 低风险"
            st.metric("卒中风险", risk)
    else:
        st.info("还没有数据，请先上传Excel")

# ==================== 页面3：可视化图表 ====================
elif page == "📈 可视化图表":
    st.header("历史趋势图表")
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM signals ORDER BY id", conn)
    conn.close()
    
    if not df.empty:
        # 心率图
        fig_hr = px.line(df, x="timestamp", y="heart_rate", title="心率趋势")
        st.plotly_chart(fig_hr, use_container_width=True)
        
        # 血压图
        fig_bp = px.line(df, x="timestamp", y=["systolic_bp", "diastolic_bp"], title="血压趋势")
        st.plotly_chart(fig_bp, use_container_width=True)
        
        # 血氧图
        fig_spo2 = px.line(df, x="timestamp", y="spo2", title="血氧趋势")
        st.plotly_chart(fig_spo2, use_container_width=True)
    else:
        st.info("还没有数据")

# ==================== 页面4：异常报警 ====================
elif page == "🚨 异常报警":
    st.header("信号异常报警（脑卒中预警）")
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM signals ORDER BY id DESC", conn)
    conn.close()
    
    if not df.empty:
        # 检查异常
        abnormal = df[
            (df["heart_rate"] < thresholds["heart_rate_min"]) | 
            (df["heart_rate"] > thresholds["heart_rate_max"]) |
            (df["systolic_bp"] > thresholds["systolic_max"]) |
            (df["diastolic_bp"] > thresholds["diastolic_max"]) |
            (df["spo2"] < thresholds["spo2_min"])
        ]
        
        if not abnormal.empty:
            st.error(f"🚨 发现 {len(abnormal)} 条异常记录！请立即关注（高血压是脑卒中主要风险因素）")
            st.dataframe(abnormal)
        else:
            st.success("✅ 所有信号正常，无异常报警")
    else:
        st.info("还没有数据")

# ==================== 页面5：阈值设置 ====================
else:
    st.header("自定义阈值（后期可改成动态预警）")
    st.write("修改下面数值后，刷新页面生效（目前硬编码，未来可保存到数据库）")
    # 这里你可以手动改代码里的thresholds字典

st.caption("系统已就绪！这是你的物联网原型，后续可轻松扩展真实传感器 + 脑数字孪生模型")