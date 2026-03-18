import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import uuid

from config import (
    supabase, init_database, get_all_patients, get_patient_by_id,
    get_signals, get_uploaded_files, get_patient_stats,
    detect_abnormal_signals, run_brain_model_cached
)
from utils import (
    init_session_state, get_current_thresholds, force_refresh, get_patient_id_map
)

st.set_page_config(page_title="Lovewellsup", layout="wide")
st.title("🧠 欢迎来到 DT-Iot 系统 🧠")
st.markdown("**Enhanced Version**：Designed by Nnian, 2026")

st.markdown("""
<style>
    [data-testid="stSidebar"] h1 {font-size: 1.5rem !important; text-align: center !important; font-weight: bold;}
    .stButton > button {font-size: 1.2rem !important; width: 100% !important; text-align: center !important; margin: 4px 0;}
    .patient-card {padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin: 10px 0;}
    .stDataFrame {border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

init_database()
init_session_state()

st.sidebar.markdown("<h1>👤 病人管理</h1>", unsafe_allow_html=True)

patients_df = get_all_patients()
patient_options, patient_id_map = get_patient_id_map(patients_df)

with st.sidebar.expander("➕ 新建病人", expanded=False):
    with st.form("new_patient_form"):
        new_name = st.text_input("病人姓名")
        new_code = st.text_input("病人编号", placeholder="例如: P001")
        new_age = st.number_input("年龄", min_value=0, max_value=150, value=50)
        
        gender_options = ["男", "女", "其他"]
        new_gender = st.selectbox("性别", gender_options)
        
        custom_gender = None
        if new_gender == "其他":
            custom_gender = st.text_input("自定义性别", placeholder="请输入1-20个字符", max_chars=20)
        else:
            custom_gender = new_gender
        
        new_diagnosis = st.text_area("诊断信息", placeholder="可选")
        submit_patient = st.form_submit_button("创建病人")
        
        if submit_patient and new_name and new_code:
            final_gender = None
            
            if new_gender == "其他":
                if not custom_gender:
                    st.error("选择'其他'时请输入自定义性别")
                elif len(custom_gender.strip()) < 1:
                    st.error("自定义性别不能为空")
                else:
                    # 验证是否包含HTML标签或脚本内容
                    import re
                    html_pattern = re.compile(r'<[^>]+>')
                    script_pattern = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL)
                    
                    if html_pattern.search(custom_gender) or script_pattern.search(custom_gender):
                        st.error("自定义性别不允许包含HTML标签或脚本内容")
                    else:
                        final_gender = custom_gender
                        if final_gender not in st.session_state.custom_genders:
                            st.session_state.custom_genders.append(final_gender)
            else:
                final_gender = new_gender
            
            if final_gender:
                patient_data = {
                    "id": str(uuid.uuid4()),
                    "patient_name": new_name,
                    "patient_code": new_code,
                    "age": new_age,
                    "gender": final_gender,
                    "diagnosis": new_diagnosis,
                    "created_at": datetime.now().isoformat()
                }
                try:
                    supabase.table("patients").insert(patient_data).execute()
                    st.success(f"✅ 病人 {new_name} 创建成功！")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")

with st.sidebar.expander("👥 选择病人", expanded=True):
    selected_option = st.selectbox("", patient_options, index=0)
    
    if selected_option != "全部病人":
        patient_id = patient_id_map[selected_option]
        st.session_state.current_patient_id = patient_id
        st.session_state.current_patient_name = selected_option
    else:
        st.session_state.current_patient_id = None
        st.session_state.current_patient_name = "全部病人"

current_patient_id = st.session_state.current_patient_id
current_patient_name = st.session_state.current_patient_name

if patients_df.empty:
    st.session_state.custom_genders = []
else:
    all_genders = patients_df['gender'].unique().tolist()
    valid_custom_genders = [g for g in st.session_state.custom_genders if g in all_genders]
    if valid_custom_genders != st.session_state.custom_genders:
        st.session_state.custom_genders = valid_custom_genders

st.sidebar.markdown("---")
st.sidebar.markdown("<h1>📋 功能菜单</h1>", unsafe_allow_html=True)

pages = ["🏥 病人信息", "📤 数据上传", "📊 仪表盘", "📈 可视化图表", "⚙️ 阈值设置", "🚨 异常报警", "🧬 脑数字孪生模型"]
for p in pages:
    if st.sidebar.button(p, key=p, use_container_width=True):
        st.session_state.current_page = p

page = st.session_state.get('current_page', "🏥 病人信息")

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
            gender_filter_options = ["全部", "男", "女", "其他"] + st.session_state.custom_genders
            filter_gender = st.selectbox("性别筛选", gender_filter_options)
        
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
                    stats = get_patient_stats(row['id'])
                    st.metric("数据记录", stats["count"])
                
                st.write(f"**诊断信息**: {row.get('diagnosis', '无')}")
                st.write(f"**创建时间**: {row.get('created_at', 'N/A')}")
                
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button(f"查看数据", key=f"view_{row['id']}"):
                        st.session_state.current_patient_id = row['id']
                        st.session_state.current_patient_name = f"{row['patient_name']} ({row['patient_code']})"
                        st.session_state.current_page = "📊 仪表盘"
                        st.rerun()
                with col_btn2:
                    if st.button(f"编辑信息", key=f"edit_{row['id']}"):
                        st.session_state.edit_patient_id = row['id']
                        st.session_state.edit_patient_data = row.to_dict()
                with col_btn3:
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
                
                if 'edit_patient_id' in st.session_state and st.session_state.edit_patient_id == row['id']:
                    with st.form(f"edit_patient_form_{row['id']}"):
                        st.subheader("编辑病人信息")
                        
                        edit_name = st.text_input("病人姓名", value=row['patient_name'])
                        edit_code = st.text_input("病人编号", value=row['patient_code'])
                        edit_age = st.number_input("年龄", min_value=0, max_value=150, value=row.get('age', 50))
                        
                        edit_gender_options = ["男", "女", "其他"]
                        # 检查当前性别是否为自定义性别
                        current_gender = row.get('gender', '未知')
                        if current_gender not in ["男", "女", "其他"]:
                            # 如果是自定义性别，默认选择"其他"
                            edit_gender = st.selectbox("性别", edit_gender_options, index=2)  # 2 是"其他"的索引
                            edit_custom_gender = st.text_input("自定义性别", value=current_gender, placeholder="请输入1-20个字符", max_chars=20)
                        else:
                            edit_gender = st.selectbox("性别", edit_gender_options, index=edit_gender_options.index(current_gender) if current_gender in edit_gender_options else 0)
                            if edit_gender == "其他":
                                edit_custom_gender = st.text_input("自定义性别", placeholder="请输入1-20个字符", max_chars=20)
                            else:
                                edit_custom_gender = edit_gender
                        
                        edit_diagnosis = st.text_area("诊断信息", value=row.get('diagnosis', ''))
                        
                        col_edit_btn1, col_edit_btn2 = st.columns(2)
                        with col_edit_btn1:
                            submit_edit = st.form_submit_button("保存修改")
                        with col_edit_btn2:
                            cancel_edit = st.form_submit_button("取消")
                        
                        if cancel_edit:
                            del st.session_state.edit_patient_id
                            del st.session_state.edit_patient_data
                            st.rerun()
                        
                        if submit_edit:
                            if not edit_name or not edit_code:
                                st.error("病人姓名和编号不能为空")
                            else:
                                final_edit_gender = None
                                
                                if edit_gender == "其他":
                                    if not edit_custom_gender:
                                        st.error("选择'其他'时请输入自定义性别")
                                    elif len(edit_custom_gender.strip()) < 1:
                                        st.error("自定义性别不能为空")
                                    else:
                                        # 验证是否包含HTML标签或脚本内容
                                        import re
                                        html_pattern = re.compile(r'<[^>]+>')
                                        script_pattern = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL)
                                        
                                        if html_pattern.search(edit_custom_gender) or script_pattern.search(edit_custom_gender):
                                            st.error("自定义性别不允许包含HTML标签或脚本内容")
                                        else:
                                            final_edit_gender = edit_custom_gender
                                            if final_edit_gender not in st.session_state.custom_genders:
                                                st.session_state.custom_genders.append(final_edit_gender)
                                else:
                                    final_edit_gender = edit_gender
                                
                                if final_edit_gender:
                                    update_data = {
                                        "patient_name": edit_name,
                                        "patient_code": edit_code,
                                        "age": edit_age,
                                        "gender": final_edit_gender,
                                        "diagnosis": edit_diagnosis
                                    }
                                    
                                    try:
                                        supabase.table("patients").update(update_data).eq("id", row['id']).execute()
                                        st.success(f"✅ 病人信息更新成功！")
                                        st.cache_data.clear()
                                        del st.session_state.edit_patient_id
                                        del st.session_state.edit_patient_data
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"更新失败: {e}")

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
            
            upload_gender_options = ["男", "女", "其他"]
            upload_gender = st.selectbox("性别", upload_gender_options)
            
            upload_custom_gender = None
            if upload_gender == "其他":
                upload_custom_gender = st.text_input("自定义性别", placeholder="请输入1-20个字符", max_chars=20)
            else:
                upload_custom_gender = upload_gender
            
            upload_file = st.file_uploader("选择Excel/CSV文件", type=["xlsx", "csv"])
            submit_new = st.form_submit_button("上传并创建病人")
            
            if submit_new and upload_patient_name and upload_patient_code and upload_file:
                final_upload_gender = None
                
                if upload_gender == "其他":
                    if not upload_custom_gender:
                        st.error("选择'其他'时请输入自定义性别")
                    elif len(upload_custom_gender.strip()) < 1:
                        st.error("自定义性别不能为空")
                    else:
                        # 验证是否包含HTML标签或脚本内容
                        import re
                        html_pattern = re.compile(r'<[^>]+>')
                        script_pattern = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL)
                        
                        if html_pattern.search(upload_custom_gender) or script_pattern.search(upload_custom_gender):
                            st.error("自定义性别不允许包含HTML标签或脚本内容")
                        else:
                            final_upload_gender = upload_custom_gender
                            if final_upload_gender not in st.session_state.custom_genders:
                                st.session_state.custom_genders.append(final_upload_gender)
                else:
                    final_upload_gender = upload_gender
                
                if final_upload_gender:
                    patient_id = str(uuid.uuid4())
                    patient_data = {
                        "id": patient_id,
                        "patient_name": upload_patient_name,
                        "patient_code": upload_patient_code,
                        "age": upload_age,
                        "gender": final_upload_gender,
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
            patient_options_upload = patient_options[1:]
            selected_upload = st.selectbox("选择病人", patient_options_upload)
            if selected_upload:
                upload_patient_id = patient_id_map[selected_upload]
                upload_patient_name = selected_upload
                upload_file = st.file_uploader("选择Excel/CSV文件", type=["xlsx", "csv"])
                
                if st.button("上传文件", type="primary") and upload_file:
                    pass
                else:
                    upload_file = None

    if upload_file and upload_patient_id:
        try:
            with st.spinner("正在处理文件..."):
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
            
            with st.spinner("正在上传数据..."):
                try:
                    supabase.table("uploaded_files").insert(file_metadata).execute()
                except:
                    pass
                
                batch_size = 1000
                timestamps = df["timestamp"].tolist()
                for i in range(0, len(timestamps), batch_size):
                    batch_timestamps = timestamps[i:i+batch_size]
                    try:
                        supabase.table("signal").delete().in_("timestamp", batch_timestamps).eq("patient_id", upload_patient_id).execute()
                    except:
                        pass
                
                records = df.to_dict(orient="records")
                for i in range(0, len(records), batch_size):
                    batch_records = records[i:i+batch_size]
                    supabase.table("signal").insert(batch_records).execute()
            
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
            rt_patient_id = patient_id_map[realtime_patient]
            
            if st.button("🚀 实时发送", type="primary"):
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_data = [{
                    "timestamp": ts,
                    "heart_rate": hr,
                    "systolic_bp": sbp,
                    "diastolic_bp": dbp,
                    "spo2": spo2,
                    "patient_id": rt_patient_id,
                    "patient_name": realtime_patient
                }]
                try:
                    supabase.table("signal").delete().eq("timestamp", ts).eq("patient_id", rt_patient_id).execute()
                    supabase.table("signal").insert(new_data).execute()
                    st.success(f"✅ 已实时存入 **{realtime_patient}**")
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
        ''')
        
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

elif page == "📊 仪表盘":
    st.header(f"📊 实时仪表盘 - {current_patient_name}")
    
    col_refresh1, col_refresh2 = st.columns([3, 1])
    with col_refresh1:
        st.write(f"**数据更新状态**: 最后更新于 {st.session_state.last_refresh_time.strftime('%Y-%m-%d %H:%M:%S')}")
    with col_refresh2:
        col_auto, col_manual = st.columns(2)
        with col_auto:
            st.session_state.auto_refresh = st.checkbox("自动刷新", value=st.session_state.auto_refresh)
        with col_manual:
            if st.button("手动刷新"):
                force_refresh()
                st.rerun()
    
    if st.session_state.auto_refresh:
        time_since_refresh = (datetime.now() - st.session_state.last_refresh_time).total_seconds()
        if time_since_refresh > 5:
            force_refresh()
            st.rerun()
    
    if current_patient_id:
        with st.spinner("加载数据中..."):
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
            current_thresholds = get_current_thresholds(current_patient_id)
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("❤️ 心率", f"{latest['heart_rate']:.1f} bpm")
            with col2: st.metric("🩸 血压", f"{latest['systolic_bp']:.0f}/{latest['diastolic_bp']:.0f} mmHg")
            with col3: st.metric("🫁 血氧", f"{latest['spo2']:.1f} %")
            with col4:
                risk = "⚠️ 高风险" if latest["systolic_bp"] > current_thresholds["systolic_max"] else "✅ 正常"
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
                current_thresholds = get_current_thresholds(None)
                abnormal = len(all_df[(all_df["systolic_bp"] > current_thresholds["systolic_max"]) | (all_df["heart_rate"] > current_thresholds["heart_rate_max"]) | (all_df["spo2"] < current_thresholds["spo2_min"])])
                st.metric("🚨 异常记录", abnormal)
            else:
                st.metric("🚨 异常记录", 0)
        with col_stat4:
            avg_hr = all_df['heart_rate'].mean() if not all_df.empty else 0
            st.metric("❤️ 平均心率", f"{avg_hr:.1f} bpm")
        
        if not all_df.empty and not all_patients.empty:
            patient_stats = []
            
            grouped = all_df.groupby('patient_id')
            patient_data = grouped.agg({
                'heart_rate': 'mean',
                'systolic_bp': 'mean',
                'diastolic_bp': 'mean',
                'spo2': 'mean',
                'patient_id': 'count'
            }).rename(columns={'patient_id': 'count'})
            
            for _, p in all_patients.iterrows():
                if p['id'] in patient_data.index:
                    stats = patient_data.loc[p['id']]
                    patient_stats.append({
                        'name': p['patient_name'],
                        'code': p['patient_code'],
                        'count': int(stats['count']),
                        'avg_hr': stats['heart_rate']
                    })
            
            stats_df = pd.DataFrame(patient_stats)
            if not stats_df.empty:
                st.subheader("各病人数据统计")
                st.dataframe(
                    stats_df.rename(columns={'name': '姓名', 'code': '编号', 'count': '记录数', 'avg_hr': '平均心率'}),
                    use_container_width=True,
                    hide_index=True
                )

elif page == "📈 可视化图表":
    st.header(f"📈 历史趋势图表 - {current_patient_name}")
    
    col_filter1, col_filter2, col_filter3 = st.columns([1, 1, 1])
    
    if current_patient_id:
        with col_filter1:
            time_range = st.selectbox("时间范围", ["近1小时", "近6小时", "近24小时", "近7天", "全部"])
        with col_filter2:
            chart_type = st.selectbox("图表类型", ["折线图", "散点图", "面积图"])
        with col_filter3:
            show_stats = st.checkbox("显示统计信息", value=True)
        
        now = datetime.now()
        if time_range == "近1小时":
            time_limit = now - pd.Timedelta(hours=1)
            limit = 360
        elif time_range == "近6小时":
            time_limit = now - pd.Timedelta(hours=6)
            limit = 2160
        elif time_range == "近24小时":
            time_limit = now - pd.Timedelta(hours=24)
            limit = 8640
        elif time_range == "近7天":
            time_limit = now - pd.Timedelta(days=7)
            limit = 60480
        else:
            time_limit = None
            limit = 5000
        
        with st.spinner("加载数据中..."):
            df = get_signals(current_patient_id, min(1000, limit), "asc")
            
            if time_limit and not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                if df['timestamp'].dt.tz is not None:
                    import pytz
                    time_limit = time_limit.replace(tzinfo=pytz.UTC)
                df = df[df['timestamp'] >= time_limit]
            
            if len(df) < 50 and limit > 1000:
                df = get_signals(current_patient_id, limit, "asc")
                if time_limit and not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    if df['timestamp'].dt.tz is not None:
                        import pytz
                        time_limit = time_limit.replace(tzinfo=pytz.UTC)
                    df = df[df['timestamp'] >= time_limit]
        
        if not df.empty:
            if show_stats:
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1: st.metric("心率均值", f"{df['heart_rate'].mean():.1f}")
                with col_s2: st.metric("收缩压均值", f"{df['systolic_bp'].mean():.1f}")
                with col_s3: st.metric("舒张压均值", f"{df['diastolic_bp'].mean():.1f}")
                with col_s4: st.metric("血氧均值", f"{df['spo2'].mean():.1f}")
            
            st.subheader("心率监测")
            hr_fig = go.Figure()
            hr_fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['heart_rate'], name='心率',
                mode='lines+markers', line=dict(color='red', width=2), marker=dict(size=3),
                hovertemplate='时间: %{x}<br>心率: %{y:.1f} bpm<extra></extra>'
            ))
            hr_fig.update_layout(title='心率趋势', xaxis_title='时间', yaxis_title='心率 (bpm)',
                                hovermode='x unified', template='plotly_white', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(hr_fig, use_container_width=True)
            
            st.subheader("血压监测")
            bp_fig = go.Figure()
            bp_fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['systolic_bp'], name='收缩压',
                mode='lines+markers', line=dict(color='blue', width=2), marker=dict(size=3),
                hovertemplate='时间: %{x}<br>收缩压: %{y:.1f} mmHg<extra></extra>'
            ))
            bp_fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['diastolic_bp'], name='舒张压',
                mode='lines+markers', line=dict(color='green', width=2), marker=dict(size=3),
                hovertemplate='时间: %{x}<br>舒张压: %{y:.1f} mmHg<extra></extra>'
            ))
            bp_fig.update_layout(title='血压趋势', xaxis_title='时间', yaxis_title='血压 (mmHg)',
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                hovermode='x unified', template='plotly_white', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(bp_fig, use_container_width=True)
            
            st.subheader("血氧监测")
            spo2_fig = go.Figure()
            spo2_fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['spo2'], name='血氧',
                mode='lines+markers', line=dict(color='purple', width=2), marker=dict(size=3),
                hovertemplate='时间: %{x}<br>血氧: %{y:.1f} %<extra></extra>'
            ))
            spo2_fig.update_layout(title='血氧趋势', xaxis_title='时间', yaxis_title='血氧 (%)',
                                  hovermode='x unified', template='plotly_white', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(spo2_fig, use_container_width=True)
            
            with st.expander("📊 详细数据表格"):
                st.dataframe(df, use_container_width=True)
        else:
            st.info("该病人暂无数据")
    else:
        st.info("请先在侧边栏选择具体病人")

elif page == "🚨 异常报警":
    st.header(f"🚨 信号异常报警 - {current_patient_name}")
    
    if current_patient_id:
        with st.spinner("分析数据中..."):
            df = get_signals(current_patient_id, 100)
        
        if not df.empty:
            current_thresholds = get_current_thresholds(current_patient_id)
            df_display, abnormal_count = detect_abnormal_signals(df, current_thresholds)
            
            def highlight_abnormal(val, col_name):
                if col_name == "heart_rate" and (val < current_thresholds["heart_rate_min"] or val > current_thresholds["heart_rate_max"]):
                    return "color: white; background-color: #ff4d4d; font-weight: bold"
                if col_name in ["systolic_bp", "diastolic_bp"] and val > current_thresholds["systolic_max"]:
                    return "color: white; background-color: #ff4d4d; font-weight: bold"
                if col_name == "spo2" and val < current_thresholds["spo2_min"]:
                    return "color: white; background-color: #ff4d4d; font-weight: bold"
                return ""
            
            if abnormal_count > 0:
                st.error(f"🚨 发现 {abnormal_count} 条异常记录！")
                page_size = 20
                total_pages = (len(df_display) + page_size - 1) // page_size
                page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                
                # 先对DataFrame进行切片，然后再应用样式
                paginated_df = df_display.iloc[start_idx:end_idx]
                styled_df = paginated_df.style.apply(lambda x: [highlight_abnormal(v, col) for col, v in x.items()], axis=1)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                hr_abnormal = (df["heart_rate"] < current_thresholds["heart_rate_min"]) | (df["heart_rate"] > current_thresholds["heart_rate_max"])
                bp_abnormal = (df["systolic_bp"] > current_thresholds["systolic_max"]) | (df["diastolic_bp"] > current_thresholds["diastolic_max"])
                spo2_abnormal = df["spo2"] < current_thresholds["spo2_min"]
                
                col_ab1, col_ab2 = st.columns(2)
                with col_ab1:
                    st.metric("心率异常", hr_abnormal.sum())
                with col_ab2:
                    st.metric("血压异常", bp_abnormal.sum())
                
                st.metric("血氧异常", spo2_abnormal.sum())
            else:
                st.success("✅ 所有信号正常")
        else:
            st.info("该病人暂无数据")
    else:
        with st.spinner("分析系统数据中..."):
            all_df = get_signals(None, 500)
        if not all_df.empty:
            current_thresholds = get_current_thresholds(None)
            abnormal_df = all_df[
                (all_df["systolic_bp"] > current_thresholds["systolic_max"]) | 
                (all_df["heart_rate"] > current_thresholds["heart_rate_max"]) | 
                (all_df["spo2"] < current_thresholds["spo2_min"])
            ]
            st.error(f"🚨 系统中共有 {len(abnormal_df)} 条异常记录")
            
            if not abnormal_df.empty:
                page_size = 20
                total_pages = (len(abnormal_df) + page_size - 1) // page_size
                page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                st.dataframe(abnormal_df[["patient_id", "timestamp", "heart_rate", "systolic_bp", "diastolic_bp", "spo2"]].iloc[start_idx:end_idx], use_container_width=True)
        else:
            st.info("暂无数据")

elif page == "🧬 脑数字孪生模型":
    st.header(f"🧬 大脑数字孪生体模型 - {current_patient_name}")
    
    if current_patient_id:
        df = get_signals(current_patient_id, 1)
        
        if not df.empty and st.button("🚀 运行内置简易模型"):
            with st.spinner("数值计算中..."):
                latest = df.iloc[0]
                t, sol, risk = run_brain_model_cached(latest["systolic_bp"], latest["spo2"])
                
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

elif page == "⚙️ 阈值设置":
    st.header("⚙️ 阈值设置")
    
    threshold_type = st.radio("阈值类型", ["全局默认阈值", "病人专属阈值"], horizontal=True)
    
    current_thresholds = get_current_thresholds(current_patient_id)
    
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
                st.session_state.default_thresholds = new_thresholds
                st.success("✅ 已保存全局默认阈值")
    
    st.subheader("当前阈值配置")
    st.code(f"心率: {current_thresholds['heart_rate_min']}-{current_thresholds['heart_rate_max']} bpm\n收缩压: ≤{current_thresholds['systolic_max']} mmHg\n舒张压: ≤{current_thresholds['diastolic_max']} mmHg\n血氧: ≥{current_thresholds['spo2_min']} %")
    
    if current_patient_id and current_patient_id in st.session_state.patient_thresholds:
        st.info(f"当前使用 **{current_patient_name}** 的专属阈值")
    else:
        st.info("当前使用全局默认阈值")

st.caption(f"Version:1.2.0, 2026.3.18")
