import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
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

@st.cache_data(ttl=300, show_spinner=False)
def get_all_patients():
    try:
        data = supabase.table("patients").select("*").order("created_at", desc=True).execute().data
        return pd.DataFrame(data) if data else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_patient_by_id(patient_id):
    try:
        data = supabase.table("patients").select("*").eq("id", patient_id).execute().data
        return data[0] if data else None
    except:
        return None

@st.cache_data(ttl=120, show_spinner=False)
def get_signals(patient_id=None, limit=100, order="desc"):
    query = supabase.table("signal").select("*")
    if patient_id:
        query = query.eq("patient_id", patient_id)
    if order == "desc":
        query = query.order("id", desc=True)
    data = query.limit(limit).execute().data
    return pd.DataFrame(data) if data else pd.DataFrame()

@st.cache_data(ttl=120, show_spinner=False)
def get_uploaded_files(patient_id=None):
    query = supabase.table("uploaded_files").select("*").order("upload_time", desc=True)
    if patient_id:
        query = query.eq("patient_id", patient_id)
    data = query.execute().data
    return pd.DataFrame(data) if data else pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def get_patient_stats(patient_id):
    df = get_signals(patient_id, 10000)
    if df.empty:
        return {"count": 0, "avg_hr": 0, "avg_bp": 0, "avg_spo2": 0}
    return {
        "count": len(df),
        "avg_hr": df['heart_rate'].mean() if 'heart_rate' in df.columns else 0,
        "avg_bp": (df['systolic_bp'].mean() + df['diastolic_bp'].mean())/2 if 'systolic_bp' in df.columns else 0,
        "avg_spo2": df['spo2'].mean() if 'spo2' in df.columns else 0
    }

@st.cache_data(ttl=120, show_spinner=False)
def detect_abnormal_signals(df, thresholds):
    if df.empty:
        return pd.DataFrame(), 0
    
    hr_abnormal = (df["heart_rate"] < thresholds["heart_rate_min"]) | (df["heart_rate"] > thresholds["heart_rate_max"])
    bp_abnormal = (df["systolic_bp"] > thresholds["systolic_max"]) | (df["diastolic_bp"] > thresholds["diastolic_max"])
    spo2_abnormal = df["spo2"] < thresholds["spo2_min"]
    
    df_display = df.copy()
    df_display["异常类型"] = ""
    
    def get_abnormal_type(row):
        abnormal_list = []
        if row['hr_abnormal']:
            abnormal_list.append(f"心率({row['heart_rate']:.1f})")
        if row['bp_abnormal']:
            abnormal_list.append(f"血压({row['systolic_bp']:.0f}/{row['diastolic_bp']:.0f})")
        if row['spo2_abnormal']:
            abnormal_list.append(f"血氧({row['spo2']:.1f})")
        return "、".join(abnormal_list) if abnormal_list else ""
    
    df_display['hr_abnormal'] = hr_abnormal
    df_display['bp_abnormal'] = bp_abnormal
    df_display['spo2_abnormal'] = spo2_abnormal
    df_display["异常类型"] = df_display.apply(get_abnormal_type, axis=1)
    df_display = df_display.drop(['hr_abnormal', 'bp_abnormal', 'spo2_abnormal'], axis=1)
    
    abnormal_count = len(df_display[df_display["异常类型"] != ""])
    return df_display, abnormal_count

@st.cache_data(ttl=600, show_spinner=False)
def run_brain_model_cached(systolic_bp, spo2, time_steps=300):
    def cerebral_model(y, t, bp):
        return [-0.5*y[0] + 0.3*(bp-100) + np.random.normal(0, 0.5)]
    
    t = np.linspace(0, 60, time_steps)
    sol = odeint(cerebral_model, [10], t, args=(systolic_bp,), rtol=1e-3, atol=1e-3)
    risk = min(max(15 + (systolic_bp-120)*0.8 + (100-spo2)*0.5, 5), 95)
    return t, sol, risk

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
