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
from kimi_api import ask_kimi
from utils.report_generator import generate_learning_report

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
    existing_data = load_data()
    if "subjects" in existing_data:
        existing_data["subjects"].update(new_data["subjects"])
    else:
        existing_data = new_data

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)


def clear_data():
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)


# 全局加载 EasyOCR 识别器（避免重复加载）
@st.cache_resource(show_spinner=False)
def get_easyocr_reader():
    return easyocr.Reader(['en', 'ch_sim'], gpu=False)

# 优化后的图像文本提取函数
def extract_text_from_image(image_bytes):
    try:
        # 打开图片
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")  # 保证格式兼容

        # 图像压缩（防止大图崩溃）
        max_size = (1000, 1000)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size)
            st.info("图片过大，已自动压缩处理。")

        np_image = np.array(img)

        reader = get_easyocr_reader()
        result = reader.readtext(np_image, detail=0)

        if not result:
            return "⚠️ 没有识别出任何文字，请上传更清晰的图片。"
        return "\n".join(result)

    except Exception as e:
        return f"❌ 文本提取失败：{e}"



def analyze_mistakes_with_kimi(mistake_text):
    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "sk-I0dxd07uFwsojf6460SVpMDBG3d2jGLgqtyBwD2WjcJeJ6vd"
    }
    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": "你是一个专业学习导师，请分析以下错题内容，找出学生的共性问题、薄弱知识点，并提出改进建议，尽量精炼且实用。"},
            {"role": "user", "content": mistake_text}
        ]
    }

    try:
        for _ in range(3):
            res = requests.post(url, json=data, headers=headers)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            time.sleep(2)
        return "❌ 错题分析失败：服务器未响应"
    except Exception as e:
        return f"❌ 错题分析失败：{e}"


def draw_pie_chart(data):
    subjects = data.get("subjects", {})
    if not subjects:
        return

    names = []
    times = []

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
    all_mistakes = []

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

        mistake = st.text_area(f"{subject} 的错题描述（可编辑）", extracted_text, key=f"{subject}_mistake")
        notes = st.text_area(f"{subject} 的其他学习备注", key=f"{subject}_notes")
        time_spent = st.slider(f"⏱️ 每天用于 {subject} 的学习时间（小时）", 0, 12, 1, key=f"{subject}_time")

        if mistake:
            all_mistakes.append(f"{subject}：{mistake}")

        subject_data[subject] = {
            "mistake": mistake,
            "notes": notes,
            "time_spent": time_spent
        }

    if st.button("💾 保存数据"):
        save_data({"subjects": subject_data})
        st.success("✅ 数据已保存！")

    if st.button("🧹 清空所有数据"):
        clear_data()
        st.success("✅ 数据已清空！")

    if all_mistakes:
        st.markdown("### 🧠 错题分析")
        for i, m in enumerate(all_mistakes, 1):
            st.write(f"{i}. {m}")

        if st.button("🧠 分析我的错题"):
            with st.spinner("正在分析中..."):
                response = analyze_mistakes_with_kimi("\n".join(all_mistakes))
                st.markdown("#### 📊 Kimi 分析结果")
                st.write(response)


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

        st.markdown("## 📽️ 推荐学习视频（按知识点）")
    
            # 整合所有错题文本
            all_mistake_texts = []
            for subject, info in data.get("subjects", {}).items():
                mistake = info.get("mistake", "")
                if mistake:
                    all_mistake_texts.append(mistake)
    
            if not all_mistake_texts:
                st.info("没有错题内容可分析")
                return
    
            with st.spinner("正在分析薄弱知识点..."):
                keywords = analyze_weak_points_with_kimi("\n".join(all_mistake_texts))
    
            if not keywords:
                st.warning("未能识别出有效的知识点")
                return
    
            for kw in keywords:
                st.markdown(f"### 🎯 知识点：{kw}")
                videos = search_bilibili_videos(kw, max_results=5)
                if not videos:
                    st.write("未找到相关视频")
                else:
                    for v in videos:
                        st.markdown(f"- [{v['title']}]({v['link']}) ⏱ {v['duration']}")



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
        if not question:
            st.warning("请输入或上传问题以获取答案")
        else:
            with st.spinner("AI 正在思考..."):
                answer = ask_kimi(question)
                st.markdown("#### 💬 AI答复")
                st.write(answer)


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
