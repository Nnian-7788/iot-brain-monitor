import time
import pandas as pd
import numpy as np
from app import get_all_patients, get_signals, get_patient_stats, run_brain_model_cached, detect_abnormal_signals

# 性能测试函数
def test_performance():
    results = []
    
    # 测试1: 获取所有病人信息
    start_time = time.time()
    patients_df = get_all_patients()
    end_time = time.time()
    results.append({"测试项": "获取所有病人信息", "耗时(秒)": end_time - start_time, "数据量": len(patients_df)})
    
    # 测试2: 获取信号数据
    start_time = time.time()
    signals_df = get_signals(limit=1000)
    end_time = time.time()
    results.append({"测试项": "获取信号数据(1000条)", "耗时(秒)": end_time - start_time, "数据量": len(signals_df)})
    
    # 测试3: 获取病人统计信息
    if not patients_df.empty:
        patient_id = patients_df.iloc[0]['id']
        start_time = time.time()
        stats = get_patient_stats(patient_id)
        end_time = time.time()
        results.append({"测试项": "获取病人统计信息", "耗时(秒)": end_time - start_time, "数据量": stats["count"]})
    
    # 测试4: 脑数字孪生模型计算
    start_time = time.time()
    t, sol, risk = run_brain_model_cached(120, 98)
    end_time = time.time()
    results.append({"测试项": "脑数字孪生模型计算", "耗时(秒)": end_time - start_time, "数据量": len(t)})
    
    # 测试5: 异常检测
    if not signals_df.empty:
        thresholds = {"heart_rate_min": 60, "heart_rate_max": 100, "systolic_max": 140, "diastolic_max": 90, "spo2_min": 95}
        start_time = time.time()
        df_display, abnormal_count = detect_abnormal_signals(signals_df, thresholds)
        end_time = time.time()
        results.append({"测试项": "异常检测", "耗时(秒)": end_time - start_time, "数据量": len(signals_df)})
    
    # 测试6: 重复调用缓存函数
    start_time = time.time()
    for i in range(5):
        get_all_patients()
    end_time = time.time()
    results.append({"测试项": "重复调用缓存函数(5次)", "耗时(秒)": end_time - start_time, "数据量": 5})
    
    # 生成测试报告
    report_df = pd.DataFrame(results)
    print("性能测试报告")
    print("=" * 60)
    print(report_df.to_string(index=False))
    print("=" * 60)
    
    # 计算总耗时
    total_time = sum([r["耗时(秒)"] for r in results])
    print(f"总耗时: {total_time:.4f} 秒")
    
    return report_df

if __name__ == "__main__":
    print("开始性能测试...")
    test_performance()
    print("性能测试完成！")
