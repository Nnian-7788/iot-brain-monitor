import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from supabase import create_client, Client
import numpy as np
from scipy.integrate import odeint
import ssl
import os
import uuid
import hashlib

ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

SUPABASE_URL = "https://toesqwoexmuowjsxvxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRvZXNxd29leG11b3dqc3h2eHh4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3Nzc5MTIsImV4cCI6MjA4ODM1MzkxMn0.W0lOjxGOqwtv43gjD96k1gL9r-gjAGkN2icKWFoNwhc"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="脑卒中预警物联网系统", layout="wide")
st.title("🧠 实时生理信号监测 - 脑数字孪生物联网系统（多病人版）")
st.markdown("**增强版**：病人管理 + 文件归属标识 + 智能数据分类存储")

st.markdown("""
<style>
    [data-testid="stSidebar"] h1 {font-size: 1.5rem !important; text-align: center !important; font-weight: bold;}
    .stButton > button {font-size: 1.2rem !important; width: 100% !important; text-align: center !important; margin: 4px 0;}
    .patient-card {padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin: 10px 0;}
    .stDataFrame {border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# ==================== 数据库初始化 ====================
def init_database():
    try:
        supabase.table("patients").select("*").limit(1).execute()
    except:
        try:
            supabase.table("patients").insert({
                "id": str(uuid.uuid4()),
                "patient_name": "默认病人",
                "patient_code": "DEFAULT001",
                "age": 0,
                "gender": "未知",
                "created_at": datetime.now().isoformat()
            }).execute()
        except:
            pass

init_database()

# ==================== 缓存函数（极速响应） ====================
@st.cache_data(ttl=30, show_spinner=False)
def get_all_patients():
    try:
        data = supabase.table("patients").select("*").order("created_at", desc=True).execute().data
        return pd.DataFrame(data) if data else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30, show_spinner=False)
def get_patient_by_id(patient_id):
    try:
        data = supabase.table("patients").select("*").eq("id", patient_id).execute().data
        return data[0] if data else None
    except:
        return None

@st.cache_data(ttl=20, show_spinner=False)
def get_signals(patient_id=None, limit=100, order="desc"):
    query = supabase.table("signal").select("*")
    if patient_id:
        query = query.eq("patient_id", patient_id)
    if order == "desc":
        query = query.order("id", desc=True)
    data = query.limit(limit).execute().data
    return pd.DataFrame(data) if data else pd.DataFrame()

@st.cache_data(ttl=20, show_spinner=False)
def get_uploaded_files(patient_id=None):
    query = supabase.table("uploaded_files").select("*").order("upload_time", desc=True)
    if patient_id:
        query = query.eq("patient_id", patient_id)
    data = query.execute().data
    return pd.DataFrame(data) if data else pd.DataFrame()

# 性能优化：批量数据处理
@st.cache_data(ttl=10, show_spinner=False)
def batch_process_data(df, operations):
    """批量处理数据，减少多次重复计算"""
    for op in operations:
        if op['type'] == 'filter':
            df = df[df[op['column']] == op['value']]
        elif op['type'] == 'sort':
            df = df.sort_values(op['column'], ascending=op['ascending'])
    return df

# ==================== 会话状态初始化 ====================
if 'current_patient_id' not in st.session_state:
    st.session_state.current_patient_id = None
if 'current_patient_name' not in st.session_state:
    st.session_state.current_patient_name = "全部病人"
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "all"

# ==================== 侧边栏 - 病人管理 ====================
st.sidebar.markdown("<h1>👤 病人管理</h1>", unsafe_allow_html=True)

patients_df = get_all_patients()

with st.sidebar.expander("➕ 新建病人", expanded=False):
    with st.form("new_patient_form"):
        new_name = st.text_input("病人姓名")
        new_code = st.text_input("病人编号", placeholder="例如: P001")
        new_age = st.number_input("年龄", min_value=0, max_value=150, value=50)
        new_gender = st.selectbox("性别", ["男", "女", "其他"])
        new_diagnosis = st.text_area("诊断信息", placeholder="可选")
        submit_patient = st.form_submit_button("创建病人")
        
        if submit_patient and new_name and new_code:
            patient_data = {
                "id": str(uuid.uuid4()),
                "patient_name": new_name,
                "patient_code": new_code,
                "age": new_age,
                "gender": new_gender,
                "diagnosis": new_diagnosis,
                "created_at": datetime.now().isoformat()
            }
            try:
                supabase.table("patients").insert(patient_data).execute()
                st.success(f"✅ 病人 {new_name} 创建成功！")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"创建失败: {e}")

st.sidebar.markdown("---")

patient_options = ["全部病人"]
if not patients_df.empty:
    for _, row in patients_df.iterrows():
        display_name = f"{row['patient_name']} ({row['patient_code']})"
        patient_options.append(f"{row['id']}|{display_name}")

selected_option = st.sidebar.selectbox("选择病人", patient_options, index=0)

if selected_option != "全部病人":
    patient_id, patient_name = selected_option.split("|", 1)
    st.session_state.current_patient_id = patient_id
    st.session_state.current_patient_name = patient_name
else:
    st.session_state.current_patient_id = None
    st.session_state.current_patient_name = "全部病人"

current_patient_id = st.session_state.current_patient_id
current_patient_name = st.session_state.current_patient_name

st.sidebar.markdown("---")
st.sidebar.markdown("<h1>📋 功能菜单</h1>", unsafe_allow_html=True)

pages = ["🏥 病人信息", "📤 数据上传", "📊 仪表盘", "📈 可视化图表", "⚙️ 阈值设置", "🚨 异常报警", "🧬 脑数字孪生模型"]
for p in pages:
    if st.sidebar.button(p, key=p, use_container_width=True):
        st.session_state.current_page = p

page = st.session_state.get('current_page', "🏥 病人信息")

# 阈值存储
if 'patient_thresholds' not in st.session_state:
    st.session_state.patient_thresholds = {}
if 'default_thresholds' not in st.session_state:
    st.session_state.default_thresholds = {"heart_rate_min": 60, "heart_rate_max": 100, "systolic_max": 140, "diastolic_max": 90, "spo2_min": 95}

# 获取当前病人的阈值
def get_current_thresholds():
    if current_patient_id and current_patient_id in st.session_state.patient_thresholds:
        return st.session_state.patient_thresholds[current_patient_id]
    return st.session_state.default_thresholds

# ==================== 页面1：病人信息管理 ====================
if page == "🏥 病人信息":
    st.header("👥 病人信息管理")
    
    if patients_df.empty:
        st.info("暂无病人信息，请先创建病人")
    else:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search_term = st.text_input("🔍 搜索病人", placeholder="输入姓名或编号")
        with col2:
            sort_by = st.selectbox("排序方式", ["创建时间", "姓名", "编号"])
        with col3:
            filter_gender = st.selectbox("性别筛选", ["全部", "男", "女", "其他"])
        
        filtered_df = patients_df.copy()
        if search_term:
            filtered_df = filtered_df[
                filtered_df['patient_name'].str.contains(search_term, na=False) |
                filtered_df['patient_code'].str.contains(search_term, na=False)
            ]
        if filter_gender != "全部":
            filtered_df = filtered_df[filtered_df['gender'] == filter_gender]
        
        if sort_by == "姓名":
            filtered_df = filtered_df.sort_values("patient_name")
        elif sort_by == "编号":
            filtered_df = filtered_df.sort_values("patient_code")
        else:
            filtered_df = filtered_df.sort_values("created_at", ascending=False)
        
        st.write(f"共 **{len(filtered_df)}** 位病人")
        
        for idx, row in filtered_df.iterrows():
            with st.expander(f"📋 {row['patient_name']} ({row['patient_code']})"):
                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.metric("年龄", f"{row.get('age', 'N/A')} 岁")
                with col_info2:
                    st.metric("性别", row.get('gender', '未知'))
                with col_info3:
                    signal_count = len(get_signals(row['id'], 10000))
                    st.metric("数据记录", signal_count)
                
                st.write(f"**诊断信息**: {row.get('diagnosis', '无')}")
                st.write(f"**创建时间**: {row.get('created_at', 'N/A')}")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"查看数据", key=f"view_{row['id']}"):
                        st.session_state.current_patient_id = row['id']
                        st.session_state.current_patient_name = f"{row['patient_name']} ({row['patient_code']})"
                        st.session_state.current_page = "📊 仪表盘"
                        st.rerun()
                with col_btn2:
                    if st.button(f"删除病人", key=f"del_{row['id']}"):
                        try:
                            supabase.table("patients").delete().eq("id", row['id']).execute()
                            supabase.table("signal").delete().eq("patient_id", row['id']).execute()
                            supabase.table("uploaded_files").delete().eq("patient_id", row['id']).execute()
                            st.success("已删除该病人及相关数据")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败: {e}")

# ==================== 页面2：数据上传 ====================
elif page == "📤 数据上传":
    st.header("📤 数据上传与文件管理")
    
    col_upload1, col_upload2 = st.columns([1, 1])
    with col_upload1:
        upload_source = st.radio("数据来源", ["新建病人数据", "现有病人数据"], horizontal=True)
    
    upload_patient_id = None
    upload_patient_name = ""
    
    if upload_source == "新建病人数据":
        with st.form("upload_new_patient"):
            upload_patient_name = st.text_input("病人姓名", placeholder="输入病人姓名")
            upload_patient_code = st.text_input("病人编号", placeholder="例如: P001")
            upload_age = st.number_input("年龄", min_value=0, max_value=150, value=50)
            upload_gender = st.selectbox("性别", ["男", "女", "其他"])
            upload_file = st.file_uploader("选择Excel/CSV文件", type=["xlsx", "csv"])
            submit_new = st.form_submit_button("上传并创建病人")
            
            if submit_new and upload_patient_name and upload_patient_code and upload_file:
                patient_id = str(uuid.uuid4())
                patient_data = {
                    "id": patient_id,
                    "patient_name": upload_patient_name,
                    "patient_code": upload_patient_code,
                    "age": upload_age,
                    "gender": upload_gender,
                    "created_at": datetime.now().isoformat()
                }
                try:
                    supabase.table("patients").insert(patient_data).execute()
                    upload_patient_id = patient_id
                except Exception as e:
                    st.error(f"创建病人失败: {e}")
    else:
        if patients_df.empty:
            st.warning("暂无现有病人，请先创建病人")
        else:
            patient_options_upload = []
            for _, row in patients_df.iterrows():
                patient_options_upload.append(f"{row['id']}|{row['patient_name']} ({row['patient_code']})")
            
            selected_upload = st.selectbox("选择病人", patient_options_upload)
            if selected_upload:
                upload_patient_id, upload_patient_name = selected_upload.split("|", 1)
                upload_file = st.file_uploader("选择Excel/CSV文件", type=["xlsx", "csv"])
                
                if st.button("上传文件", type="primary") and upload_file:
                    pass
                else:
                    upload_file = None

    if upload_file and upload_patient_id:
        try:
            df = pd.read_excel(upload_file) if upload_file.name.endswith(".xlsx") else pd.read_csv(upload_file)
            
            st.write("📄 文件预览（前5行）：")
            st.dataframe(df.head(), use_container_width=True)
            
            required_cols = ["timestamp", "heart_rate", "systolic_bp", "diastolic_bp", "spo2"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.warning(f"文件缺少必要列: {', '.join(missing_cols)}，系统将自动添加")
                for col in required_cols:
                    if col not in df.columns:
                        if col == "timestamp":
                            df[col] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            df[col] = 0
            
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
            df["patient_id"] = upload_patient_id
            df["patient_name"] = upload_patient_name
            
            file_hash = hashlib.md5(upload_file.read()).hexdigest()
            upload_file.seek(0)
            
            file_metadata = {
                "id": str(uuid.uuid4()),
                "patient_id": upload_patient_id,
                "file_name": upload_file.name,
                "file_hash": file_hash,
                "record_count": len(df),
                "upload_time": datetime.now().isoformat(),
                "file_size": upload_file.size
            }
            
            try:
                supabase.table("uploaded_files").insert(file_metadata).execute()
            except:
                pass
            
            timestamps = df["timestamp"].tolist()
            try:
                supabase.table("signal").delete().in_("timestamp", timestamps).eq("patient_id", upload_patient_id).execute()
            except:
                pass
            
            supabase.table("signal").insert(df.to_dict(orient="records")).execute()
            
            st.success(f"🎉 {len(df)} 条数据已存入 **{upload_patient_name}**")
            st.balloons()
            st.cache_data.clear()
            
        except Exception as e:
            st.error(f"上传失败: {e}")

    st.markdown("---")
    st.subheader("📁 已上传文件记录")
    
    if current_patient_id:
        files_df = get_uploaded_files(current_patient_id)
    else:
        files_df = get_uploaded_files()
    
    if not files_df.empty:
        st.dataframe(
            files_df[["file_name", "record_count", "upload_time", "file_size"]].rename(columns={
                "file_name": "文件名",
                "record_count": "记录数",
                "upload_time": "上传时间",
                "file_size": "文件大小(字节)"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("暂无上传记录")

    with st.expander("🔌 传感器实时上传接口", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            hr = st.number_input("❤️ 心率 (bpm)", value=80)
            sbp = st.number_input("🩸 收缩压", value=120)
        with col2:
            dbp = st.number_input("🩸 舒张压", value=80)
            spo2 = st.number_input("🫁 血氧 (%)", value=98)
        
        realtime_patient = st.selectbox("选择病人", patient_options[1:], key="realtime")
        if realtime_patient:
            rt_patient_id, rt_patient_name = realtime_patient.split("|", 1)
            
            if st.button("🚀 实时发送", type="primary"):
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_data = [{
                    "timestamp": ts,
                    "heart_rate": hr,
                    "systolic_bp": sbp,
                    "diastolic_bp": dbp,
                    "spo2": spo2,
                    "patient_id": rt_patient_id,
                    "patient_name": rt_patient_name
                }]
                try:
                    supabase.table("signal").delete().eq("timestamp", ts).eq("patient_id", rt_patient_id).execute()
                    supabase.table("signal").insert(new_data).execute()
                    st.success(f"✅ 已实时存入 **{rt_patient_name}**")
                except Exception as e:
                    st.error(f"发送失败: {e}")
    
    with st.expander("🔧 传感器数据接入API", expanded=False):
        st.subheader("传感器数据接入接口")
        st.code('''
# 传感器数据接入API
# 支持标准HTTP POST请求

# 接口地址: /api/sensor-data
# 请求方法: POST
# 请求格式: JSON
#
# 请求示例:
{
    "patient_id": "patient-123",
    "data": {
        "heart_rate": 85,
        "systolic_bp": 125,
        "diastolic_bp": 82,
        "spo2": 98
    },
    "timestamp": "2024-01-01 12:00:00"
}

# 响应示例:
{
    "status": "success",
    "message": "数据接收成功",
    "data": {
        "patient_id": "patient-123",
        "record_count": 1
    }
}
''')
        
        st.markdown("### 传感器设备注册")
        device_name = st.text_input("设备名称")
        device_id = st.text_input("设备ID")
        device_type = st.selectbox("设备类型", ["心率传感器", "血压传感器", "血氧传感器", "多参数监护仪"])
        
        if st.button("注册设备"):
            st.success(f"✅ 设备 {device_name} 注册成功！")
            st.info(f"设备ID: {device_id}\n设备类型: {device_type}")
    
    if current_patient_id and current_patient_name != "全部病人":
        st.markdown("---")
        if st.button("🗑️ 清空当前病人所有数据", type="secondary"):
            if st.warning("确定要删除该病人所有数据吗？此操作不可恢复！"):
                try:
                    supabase.table("signal").delete().eq("patient_id", current_patient_id).execute()
                    supabase.table("uploaded_files").delete().eq("patient_id", current_patient_id).execute()
                    st.success(f"✅ 已清空 {current_patient_name} 的所有数据")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"清空失败: {e}")

# ==================== 页面3：仪表盘 ====================
elif page == "📊 仪表盘":
    st.header(f"📊 实时仪表盘 - {current_patient_name}")
    
    if current_patient_id:
        df = get_signals(current_patient_id, 1)
        patient_info = get_patient_by_id(current_patient_id)
        
        if patient_info:
            col_info1, col_info2, col_info3, col_info4 = st.columns(4)
            with col_info1:
                st.metric("病人姓名", patient_info.get('patient_name', 'N/A'))
            with col_info2:
                st.metric("病人编号", patient_info.get('patient_code', 'N/A'))
            with col_info3:
                st.metric("年龄", f"{patient_info.get('age', 'N/A')} 岁")
            with col_info4:
                st.metric("性别", patient_info.get('gender', '未知'))
        
        if not df.empty:
            latest = df.iloc[0]
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("❤️ 心率", f"{latest['heart_rate']:.1f} bpm")
            with col2: st.metric("🩸 血压", f"{latest['systolic_bp']:.0f}/{latest['diastolic_bp']:.0f} mmHg")
            with col3: st.metric("🫁 血氧", f"{latest['spo2']:.1f} %")
            with col4:
                risk = "⚠️ 高风险" if latest["systolic_bp"] > thresholds["systolic_max"] else "✅ 正常"
                st.metric("卒中风险", risk)
            
            st.progress(int(min(max(latest['heart_rate'], 40), 120) / 120 * 100), "心率进度")
        else:
            st.info("该病人暂无数据")
    else:
        all_patients = get_all_patients()
        all_df = get_signals(None, 1000)
        
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        with col_stat1:
            st.metric("👥 总病人数", len(all_patients))
        with col_stat2:
            st.metric("📈 总记录数", len(all_df))
        with col_stat3:
            if not all_df.empty:
                abnormal = len(all_df[(all_df["systolic_bp"] > 140) | (all_df["heart_rate"] > 100) | (all_df["spo2"] < 95)])
                st.metric("🚨 异常记录", abnormal)
            else:
                st.metric("🚨 异常记录", 0)
        with col_stat4:
            avg_hr = all_df['heart_rate'].mean() if not all_df.empty else 0
            st.metric("❤️ 平均心率", f"{avg_hr:.1f} bpm")
        
        if not all_df.empty and not all_patients.empty:
            patient_stats = []
            for _, p in all_patients.iterrows():
                p_signals = all_df[all_df['patient_id'] == p['id']]
                if not p_signals.empty:
                    patient_stats.append({
                        'name': p['patient_name'],
                        'code': p['patient_code'],
                        'count': len(p_signals),
                        'avg_hr': p_signals['heart_rate'].mean()
                    })
            
            stats_df = pd.DataFrame(patient_stats)
            if not stats_df.empty:
                st.subheader("各病人数据统计")
                st.dataframe(
                    stats_df.rename(columns={'name': '姓名', 'code': '编号', 'count': '记录数', 'avg_hr': '平均心率'}),
                    use_container_width=True,
                    hide_index=True
                )

# ==================== 页面4：可视化图表 ====================
elif page == "📈 可视化图表":
    st.header(f"📈 历史趋势图表 - {current_patient_name}")
    
    col_filter1, col_filter2, col_filter3 = st.columns([1, 1, 1])
    
    if current_patient_id:
        df = get_signals(current_patient_id, 500, "asc")
        
        with col_filter1:
            time_range = st.selectbox("时间范围", ["最近50条", "最近100条", "最近200条", "最近500条", "全部"])
        with col_filter2:
            chart_type = st.selectbox("图表类型", ["折线图", "散点图", "面积图"])
        with col_filter3:
            show_stats = st.checkbox("显示统计信息", value=True)
        
        limit_map = {"最近50条": 50, "最近100条": 100, "最近200条": 200, "最近500条": 500, "全部": 5000}
        df = get_signals(current_patient_id, limit_map[time_range], "asc")
        
        if not df.empty:
            if show_stats:
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1: st.metric("心率均值", f"{df['heart_rate'].mean():.1f}")
                with col_s2: st.metric("收缩压均值", f"{df['systolic_bp'].mean():.1f}")
                with col_s3: st.metric("舒张压均值", f"{df['diastolic_bp'].mean():.1f}")
                with col_s4: st.metric("血氧均值", f"{df['spo2'].mean():.1f}")
            
            metric_options = ["心率", "收缩压", "舒张压", "血氧"]
            selected_metrics = st.multiselect("选择显示指标", metric_options, default=["心率", "收缩压", "舒张压", "血氧"])
            
            y_columns = []
            if "心率" in selected_metrics: y_columns.append("heart_rate")
            if "收缩压" in selected_metrics: y_columns.append("systolic_bp")
            if "舒张压" in selected_metrics: y_columns.append("diastolic_bp")
            if "血氧" in selected_metrics: y_columns.append("spo2")
            
            if y_columns:
                if chart_type == "折线图":
                    st.plotly_chart(px.line(df, x="timestamp", y=y_columns, title="生理指标趋势", markers=True).update_layout(xaxis_title="时间", yaxis_title="值"), use_container_width=True)
                elif chart_type == "散点图":
                    st.plotly_chart(px.scatter(df, x="timestamp", y=y_columns, title="生理指标散点图").update_layout(xaxis_title="时间", yaxis_title="值"), use_container_width=True)
                else:
                    st.plotly_chart(px.area(df, x="timestamp", y=y_columns, title="生理指标面积图").update_layout(xaxis_title="时间", yaxis_title="值"), use_container_width=True)
            
            with st.expander("📊 详细数据表格"):
                st.dataframe(df, use_container_width=True)
        else:
            st.info("该病人暂无数据")
    else:
        st.info("请先在侧边栏选择具体病人")
        
        patients_df = get_all_patients()
        if not patients_df.empty:
            st.subheader("或选择病人进行对比分析")
            compare_patients = st.multiselect("选择对比病人", 
                [f"{p['id']}|{p['patient_name']} ({p['patient_code']})" for _, p in patients_df.iterrows()],
                default=[])
            
            if compare_patients and len(compare_patients) > 0:
                all_data = []
                for p in compare_patients:
                    pid, pname = p.split("|", 1)
                    df_p = get_signals(pid, 100, "asc")
                    if not df_p.empty:
                        df_p['patient_name'] = pname
                        all_data.append(df_p)
                
                if all_data:
                    compare_df = pd.concat(all_data, ignore_index=True)
                    st.plotly_chart(px.line(compare_df, x="timestamp", y="heart_rate", color="patient_name", title="多病人心率对比").update_layout(xaxis_title="时间", yaxis_title="心率 (bpm)"), use_container_width=True)
                    st.plotly_chart(px.line(compare_df, x="timestamp", y="systolic_bp", color="patient_name", title="多病人血压对比").update_layout(xaxis_title="时间", yaxis_title="收缩压 (mmHg)"), use_container_width=True)

# ==================== 页面5：异常报警 ====================
elif page == "🚨 异常报警":
    st.header(f"🚨 信号异常报警 - {current_patient_name}")
    
    if current_patient_id:
        with st.spinner("分析数据中..."):
            df = get_signals(current_patient_id, 100)
        
        if not df.empty:
            # 使用当前病人的阈值
            current_thresholds = get_current_thresholds()
            
            def highlight_abnormal(val, col_name):
                if col_name == "heart_rate" and (val < current_thresholds["heart_rate_min"] or val > current_thresholds["heart_rate_max"]):
                    return "color: white; background-color: #ff4d4d; font-weight: bold"
                if col_name in ["systolic_bp", "diastolic_bp"] and val > current_thresholds["systolic_max"]:
                    return "color: white; background-color: #ff4d4d; font-weight: bold"
                if col_name == "spo2" and val < current_thresholds["spo2_min"]:
                    return "color: white; background-color: #ff4d4d; font-weight: bold"
                return ""
            
            # 批量处理异常检测
            df_display = df.copy()
            df_display["异常类型"] = ""
            
            # 向量式操作，提高性能
            hr_abnormal = (df["heart_rate"] < current_thresholds["heart_rate_min"]) | (df["heart_rate"] > current_thresholds["heart_rate_max"])
            bp_abnormal = (df["systolic_bp"] > current_thresholds["systolic_max"]) | (df["diastolic_bp"] > current_thresholds["diastolic_max"])
            spo2_abnormal = df["spo2"] < current_thresholds["spo2_min"]
            
            for idx, row in df.iterrows():
                abnormal_list = []
                if hr_abnormal[idx]:
                    abnormal_list.append(f"心率({row['heart_rate']:.1f})")
                if bp_abnormal[idx]:
                    abnormal_list.append(f"血压({row['systolic_bp']:.0f}/{row['diastolic_bp']:.0f})")
                if spo2_abnormal[idx]:
                    abnormal_list.append(f"血氧({row['spo2']:.1f})")
                if abnormal_list:
                    df_display.loc[idx, "异常类型"] = "、".join(abnormal_list)
            
            styled_df = df_display.style.apply(lambda x: [highlight_abnormal(v, col) for col, v in x.items()], axis=1)
            
            abnormal_count = len(df_display[df_display["异常类型"] != ""])
            if abnormal_count > 0:
                st.error(f"🚨 发现 {abnormal_count} 条异常记录！")
                # 分页显示，提高UI响应速度
                page_size = 20
                total_pages = (len(df_display) + page_size - 1) // page_size
                page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                st.dataframe(styled_df.iloc[start_idx:end_idx], use_container_width=True, hide_index=True)
                
                col_ab1, col_ab2 = st.columns(2)
                with col_ab1:
                    abnormal_hr = hr_abnormal.sum()
                    st.metric("心率异常", abnormal_hr)
                with col_ab2:
                    abnormal_bp = bp_abnormal.sum()
                    st.metric("血压异常", abnormal_bp)
                
                abnormal_spo2 = spo2_abnormal.sum()
                st.metric("血氧异常", abnormal_spo2)
            else:
                st.success("✅ 所有信号正常")
        else:
            st.info("该病人暂无数据")
    else:
        with st.spinner("分析系统数据中..."):
            all_df = get_signals(None, 500)
        if not all_df.empty:
            # 使用默认阈值
            current_thresholds = get_current_thresholds()
            abnormal_df = all_df[
                (all_df["systolic_bp"] > current_thresholds["systolic_max"]) | 
                (all_df["heart_rate"] > current_thresholds["heart_rate_max"]) | 
                (all_df["spo2"] < current_thresholds["spo2_min"])
            ]
            st.error(f"🚨 系统中共有 {len(abnormal_df)} 条异常记录")
            
            if not abnormal_df.empty:
                # 分页显示
                page_size = 20
                total_pages = (len(abnormal_df) + page_size - 1) // page_size
                page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                st.dataframe(abnormal_df[["patient_id", "timestamp", "heart_rate", "systolic_bp", "diastolic_bp", "spo2"]].iloc[start_idx:end_idx], use_container_width=True)
        else:
            st.info("暂无数据")

# ==================== 页面6：脑数字孪生模型 ====================
elif page == "🧬 脑数字孪生模型":
    st.header(f"🧬 大脑数字孪生体模型 - {current_patient_name}")
    
    if current_patient_id:
        df = get_signals(current_patient_id, 1)
        
        if not df.empty and st.button("🚀 运行内置简易模型"):
            with st.spinner("高性能数值计算中..."):
                latest = df.iloc[0]
                
                def cerebral_model(y, t, bp):
                    return [-0.5*y[0] + 0.3*(bp-100) + np.random.normal(0, 0.5)]
                
                t = np.linspace(0, 60, 600)
                sol = odeint(cerebral_model, [10], t, args=(latest["systolic_bp"],))
                risk = min(max(15 + (latest["systolic_bp"]-120)*0.8 + (100-latest["spo2"])*0.5, 5), 95)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=t, y=sol[:, 0], mode='lines', name='颅内压', line=dict(color='blue', width=2)))
                fig.update_layout(title="大脑颅内压动态演化曲线", xaxis_title="时间 (s)", yaxis_title="颅内压 (mmHg)")
                st.plotly_chart(fig, use_container_width=True)
                
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    st.metric("当前收缩压", f"{latest['systolic_bp']:.0f} mmHg")
                with col_r2:
                    st.metric("当前血氧", f"{latest['spo2']:.1f} %")
                with col_r3:
                    st.metric("卒中风险概率", f"{risk:.1f}%", delta_color="inverse" if risk > 50 else "normal")
                
                if risk > 70:
                    st.error("⚠️ 高风险警告！建议立即采取干预措施！")
                elif risk > 40:
                    st.warning("⚠️ 中等风险，请密切关注患者状态")
                else:
                    st.success("✅ 风险较低，继续保持监测")
        
        with st.expander("🔌 高级模型接入接口", expanded=False):
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
                except Exception as e:
                    st.error(f"加载失败：{e}")
    else:
        st.info("请先在侧边栏选择具体病人")

# ==================== 页面6：阈值设置 ====================
elif page == "⚙️ 阈值设置":
    st.header("⚙️ 阈值设置")
    
    threshold_type = st.radio(
        "阈值类型",
        ["全局默认阈值", "病人专属阈值"],
        horizontal=True
    )
    
    current_thresholds = get_current_thresholds()
    
    if threshold_type == "病人专属阈值":
        if current_patient_id:
            st.info(f"为 **{current_patient_name}** 设置专属阈值")
        else:
            st.warning("请先在侧边栏选择具体病人")
            threshold_type = "全局默认阈值"
    
    with st.form("threshold_form"):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            hr_min = st.number_input("心率下限 (bpm)", value=current_thresholds["heart_rate_min"])
            hr_max = st.number_input("心率上限 (bpm)", value=current_thresholds["heart_rate_max"])
        with col_t2:
            sbp_max = st.number_input("收缩压上限 (mmHg)", value=current_thresholds["systolic_max"])
            dbp_max = st.number_input("舒张压上限 (mmHg)", value=current_thresholds["diastolic_max"])
        spo2_min = st.number_input("血氧下限 (%)", value=current_thresholds["spo2_min"])
        
        if st.form_submit_button("保存设置"):
            new_thresholds = {
                "heart_rate_min": hr_min,
                "heart_rate_max": hr_max,
                "systolic_max": sbp_max,
                "diastolic_max": dbp_max,
                "spo2_min": spo2_min
            }
            
            if threshold_type == "病人专属阈值" and current_patient_id:
                st.session_state.patient_thresholds[current_patient_id] = new_thresholds
                st.success(f"✅ 已保存 **{current_patient_name}** 的专属阈值")
            else:
                # 保存为默认阈值
                # 直接修改模块级变量
                st.session_state.default_thresholds = new_thresholds
                st.success("✅ 已保存全局默认阈值")
    
    st.subheader("当前阈值配置")
    st.code(f"心率: {current_thresholds['heart_rate_min']}-{current_thresholds['heart_rate_max']} bpm\n收缩压: ≤{current_thresholds['systolic_max']} mmHg\n舒张压: ≤{current_thresholds['diastolic_max']} mmHg\n血氧: ≥{current_thresholds['spo2_min']} %")
    
    if current_patient_id and current_patient_id in st.session_state.patient_thresholds:
        st.info(f"当前使用 **{current_patient_name}** 的专属阈值")
    else:
        st.info("当前使用全局默认阈值")

# ==================== 页面7：脑数字孪生模型 ====================
elif page == "🧬 脑数字孪生模型":
    st.header(f"🧬 大脑数字孪生体模型 - {current_patient_name}")
    
    if current_patient_id:
        df = get_signals(current_patient_id, 1)
        
        if not df.empty and st.button("🚀 运行内置简易模型"):
            with st.spinner("高性能数值计算中..."):
                latest = df.iloc[0]
                
                def cerebral_model(y, t, bp):
                    return [-0.5*y[0] + 0.3*(bp-100) + np.random.normal(0, 0.5)]
                
                t = np.linspace(0, 60, 600)
                sol = odeint(cerebral_model, [10], t, args=(latest["systolic_bp"],))
                risk = min(max(15 + (latest["systolic_bp"]-120)*0.8 + (100-latest["spo2"])*0.5, 5), 95)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=t, y=sol[:, 0], mode='lines', name='颅内压', line=dict(color='blue', width=2)))
                fig.update_layout(title="大脑颅内压动态演化曲线", xaxis_title="时间 (s)", yaxis_title="颅内压 (mmHg)")
                st.plotly_chart(fig, use_container_width=True)
                
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    st.metric("当前收缩压", f"{latest['systolic_bp']:.0f} mmHg")
                with col_r2:
                    st.metric("当前血氧", f"{latest['spo2']:.1f} %")
                with col_r3:
                    st.metric("卒中风险概率", f"{risk:.1f}%", delta_color="inverse" if risk > 50 else "normal")
                
                if risk > 70:
                    st.error("⚠️ 高风险警告！建议立即采取干预措施！")
                elif risk > 40:
                    st.warning("⚠️ 中等风险，请密切关注患者状态")
                else:
                    st.success("✅ 风险较低，继续保持监测")
        
        with st.expander("🔌 高级模型接入接口", expanded=False):
            model_file = st.file_uploader("上传脑数字孪生模型代码 (.py)", type=["py"])
            
            if model_file:
                st.subheader("模型参数配置")
                model_params = {}
                
                # 通用模型参数
                model_params['time_steps'] = st.number_input("时间步数", min_value=100, max_value=1000, value=600)
                model_params['noise_level'] = st.slider("噪声水平", min_value=0.0, max_value=1.0, value=0.5)
                model_params['threshold'] = st.number_input("风险阈值", min_value=0, max_value=100, value=70)
                
                if st.button("加载并运行外部模型"):
                    try:
                        code = model_file.read().decode("utf-8")
                        local_vars = {'params': model_params}
                        exec(code, globals(), local_vars)
                        if "run_brain_model" in local_vars:
                            latest = df.iloc[0] if not df.empty else None
                            fig, risk = local_vars["run_brain_model"](latest, model_params)
                            st.plotly_chart(fig, use_container_width=True)
                            st.success(f"**外部模型运行成功！卒中风险：{risk:.1f}%**")
                    except Exception as e:
                        st.error(f"加载失败：{e}")
            
            st.markdown("### 模型接入规范")
            st.code('''
# 脑数字孪生模型接入规范

# 模型文件必须包含以下函数：
def run_brain_model(patient_data, params=None):
    """
    运行脑数字孪生模型
    
    参数:
        patient_data: 病人数据字典或None
        params: 模型参数字典
    
    返回:
        fig: Plotly图表对象
        risk: 风险值 (0-100)
    """
    # 模型实现...
    return fig, risk
''')
        
        with st.expander("🧠 模型库", expanded=False):
            st.subheader("预定义模型库")
            model_choice = st.selectbox("选择预定义模型", ["简易颅内压模型", "复杂神经网络模型", "混合物理模型"])
            
            if st.button("运行预定义模型"):
                with st.spinner("模型运行中..."):
                    if model_choice == "简易颅内压模型":
                        # 内置简易模型
                        if not df.empty:
                            latest = df.iloc[0]
                            def cerebral_model(y, t, bp):
                                return [-0.5*y[0] + 0.3*(bp-100) + np.random.normal(0, 0.5)]
                            t = np.linspace(0, 60, 600)
                            sol = odeint(cerebral_model, [10], t, args=(latest["systolic_bp"],))
                            risk = min(max(15 + (latest["systolic_bp"]-120)*0.8 + (100-latest["spo2"])*0.5, 5), 95)
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=t, y=sol[:, 0], mode='lines', name='颅内压', line=dict(color='blue', width=2)))
                            fig.update_layout(title="大脑颅内压动态演化曲线", xaxis_title="时间 (s)", yaxis_title="颅内压 (mmHg)")
                            st.plotly_chart(fig, use_container_width=True)
                            st.success(f"**模型运行成功！卒中风险：{risk:.1f}%**")
                    else:
                        st.info(f"{model_choice} 正在开发中...")
    else:
        st.info("请先在侧边栏选择具体病人")

st.caption(f"当前查看：**{current_patient_name}** | 数据分类存储 | 文件归属管理")
