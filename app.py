import streamlit as st
import matplotlib.pyplot as plt
import matplotlib
import json
import requests
import pytesseract
from PIL import Image
import pandas as pd
import matplotlib.font_manager as fm
import os
import easyocr
import io
import numpy as np
import time
import re

# 设置 Tesseract 路径
pytesseract.pytesseract.tesseract_cmd = r"E:\Tesseract-OCR\tesseract.exe"

# 设置字体支持中文
fm.fontManager.addfont('SimHei.ttf')
matplotlib.rcParams["font.family"] = "SimHei"
matplotlib.rcParams["axes.unicode_minus"] = False

DATA_PATH = "data/user_data.json"

# ========== 工具函数 ==========

def load_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(new_data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

def clear_data():
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

@st.cache_resource(show_spinner=False)
def get_easyocr_reader():
    return easyocr.Reader(['en', 'ch_sim'], gpu=False)

def extract_text_from_image(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        max_size = (1000, 1000)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size)
            st.info("图片过大，已自动压缩处理。")

        np_image = np.array(img)
        reader = get_easyocr_reader()
        result = reader.readtext(np_image, detail=0)
        return "\n".join(result) if result else "⚠️ 没有识别出任何文字，请上传更清晰的图片。"
    except Exception as e:
        return f"❌ 文本提取失败：{e}"

def analyze_weak_points_with_kimi(mistake_text):
    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "sk-你的APIKEY"  # ← 你需要替换为自己的 API 密钥
    }
    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": "你是一个专业学习导师。请从以下学生错题或描述中，提取出3~5个具体的知识点名称。每行一个，简洁明了。"},
            {"role": "user", "content": mistake_text}
        ]
    }

    try:
        for _ in range(3):
            res = requests.post(url, json=data, headers=headers)
            if res.status_code == 200:
                text = res.json()["choices"][0]["message"]["content"]
                return [line.strip(" 123456.-") for line in text.strip().splitlines() if line.strip()]
            time.sleep(2)
        return []
    except Exception:
        return []

def search_bilibili_videos(keyword, max_results=5):
    url = "https://api.bilibili.com/x/web-interface/search/type"
    params = {
        "search_type": "video",
        "keyword": keyword,
        "page": 1
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            results = data.get("data", {}).get("result", [])
            videos = []
            for item in results:
                title = re.sub(r"<.*?>", "", item.get("title", ""))
                link = item.get("arcurl", "")
                duration = item.get("duration", "00:00")
                videos.append({"title": title, "link": link, "duration": duration})
            return videos[:max_results]
        else:
            return []
    except Exception:
        return []

def draw_pie_chart(data):
    subjects = data.get("subjects", {})
    if not subjects:
        return
    names, times = [], []
    for subject, info in subjects.items():
        names.append(subject)
        times.append(info.get("time_spent", 0))

    def autopct(pct):
        total = sum(times)
        hours = int(pct / 100. * total)
        return f"{hours}小时\n({pct:.1f}%)"

    fig, ax = plt.subplots()
    ax.pie(times, labels=names, autopct=autopct, startangle=50)
    ax.axis('equal')
    st.pyplot(fig)

# ========== 页面函数 ==========

def input_learning_data():
    st.header("📥 输入你的学习数据")

    num_subjects = st.number_input("请输入学科数量", min_value=1, max_value=10, value=1)
    custom_subjects = [st.text_input(f"请输入第 {i+1} 门学科名称", key=f"subject_{i}") for i in range(num_subjects)]

    subject_data = {}
    all_texts = []

    for subject in custom_subjects:
        st.subheader(f"📘 {subject} 学习情况")
        uploaded_image = st.file_uploader(f"上传 {subject} 的错题图片", type=["png", "jpg", "jpeg"], key=f"{subject}_img")
        extracted_text = ""

        if uploaded_image is not None:
            with st.spinner("正在提取文本..."):
                image_bytes = uploaded_image.read()
                extracted_text = extract_text_from_image(image_bytes)
                st.text_area("识别出的错题内容", extracted_text, key=f"{subject}_ocr_text")
        else:
            st.info("可上传错题图片以辅助提取")

        mistake = st.text_area(f"{subject} 的错题描述", extracted_text, key=f"{subject}_mistake")
        notes = st.text_area(f"{subject} 的学习备注", key=f"{subject}_notes")
        time_spent = st.slider(f"⏱️ 每天用于 {subject} 的学习时间（小时）", 0, 12, 1, key=f"{subject}_time")

        all_texts.append(mistake)
        all_texts.append(notes)

        subject_data[subject] = {
            "mistake": mistake,
            "notes": notes,
            "time_spent": time_spent
        }

    # ========== 分析知识点 ========== #
    st.markdown("## 🧠 薄弱知识点分析")
    keywords = []
    merged_text = "\n".join([t for t in all_texts if t.strip()])
    if merged_text:
        keywords = analyze_weak_points_with_kimi(merged_text)
        if keywords:
            st.success("自动识别到知识点：")
            st.write(", ".join(keywords))

    manual_input = st.text_input("✍️ 手动补充知识点（用中文逗号隔开）")
    if manual_input:
        keywords += [kw.strip() for kw in manual_input.split("，") if kw.strip()]
    keywords = list(set(keywords))

    if st.button("💾 保存数据"):
        save_data({
            "subjects": subject_data,
            "keywords": keywords
        })
        st.success("✅ 数据与知识点已保存！")

    if st.button("🧹 清空所有数据"):
        clear_data()
        st.success("✅ 数据已清空！")

def generate_report():
    st.header("📊 AI生成个性化学习报告")
    data = load_data()
    if not data:
        st.warning("请先录入学习数据")
        return

    with st.spinner("正在生成学习报告..."):
        draw_pie_chart(data)
        report = generate_learning_report(data)
        st.markdown(report)

        keywords = data.get("keywords", [])
        ##st.markdown("## 🎥 推荐学习视频（按知识点）")
##        if not keywords:
##            st.warning("未检测到有效的知识点")
  ##          return

    ##    for kw in keywords:
      ##      st.markdown(f"### 🎯 知识点：{kw}")
        ##    videos = search_bilibili_videos(kw, max_results=5)
          ##  if not videos:
            ##    st.info("没有找到相关视频")
          ##  else:
            ##    for v in videos:
              ##      st.markdown(f"- [{v['title']}]({v['link']}) ⏱ {v['duration']}")

def ai_question_answer():
    st.header("🧑‍🏫 提问任意学习问题")
    uploaded_image = st.file_uploader("上传问题图片", type=["png", "jpg", "jpeg"], key="question_img")
    extracted_text = ""
    if uploaded_image is not None:
        with st.spinner("正在识别图片文字..."):
            extracted_text = extract_text_from_image(uploaded_image.read())
            st.text_area("识别出的文本", extracted_text, key="question_text")
    question = st.text_area("请输入你的问题（可修改）", extracted_text)
    if st.button("💡 AI回答"):
        st.info("此功能暂未连接 Kimi 接口，请集成后启用。")

# ========== 主函数 ==========

def main():
    st.set_page_config(page_title="小知学伴", layout="wide")
    st.title("🎓 小知学伴 - AI学习助手")

    menu = st.sidebar.radio("功能菜单", ["输入学习数据", "生成学习报告", "AI答疑"])

    if menu == "输入学习数据":
        input_learning_data()
    elif menu == "生成学习报告":
        generate_report()
    elif menu == "AI答疑":
        ai_question_answer()

if __name__ == "__main__":
    main()
