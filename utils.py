import streamlit as st
from datetime import datetime

def init_session_state():
    if 'current_patient_id' not in st.session_state:
        st.session_state.current_patient_id = None
    if 'current_patient_name' not in st.session_state:
        st.session_state.current_patient_name = "全部病人"
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = "all"
    if 'custom_genders' not in st.session_state:
        st.session_state.custom_genders = []
    if 'patient_thresholds' not in st.session_state:
        st.session_state.patient_thresholds = {}
    if 'default_thresholds' not in st.session_state:
        st.session_state.default_thresholds = {"heart_rate_min": 60, "heart_rate_max": 100, "systolic_max": 140, "diastolic_max": 90, "spo2_min": 95}
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = datetime.now()
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True

def get_current_thresholds(current_patient_id):
    if current_patient_id and current_patient_id in st.session_state.patient_thresholds:
        return st.session_state.patient_thresholds[current_patient_id]
    return st.session_state.default_thresholds

def force_refresh():
    st.cache_data.clear()
    st.session_state.last_refresh_time = datetime.now()
    return st.session_state.last_refresh_time

def get_patient_id_map(patients_df):
    patient_options = ["全部病人"]
    patient_id_map = {"全部病人": None}
    if not patients_df.empty:
        sorted_patients = patients_df.sort_values("patient_code")
        for _, row in sorted_patients.iterrows():
            display_name = f"{row['patient_name']} ({row['patient_code']})"
            patient_options.append(display_name)
            patient_id_map[display_name] = row['id']
    return patient_options, patient_id_map
