from collections import defaultdict
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib
import json
import requests
import pytesseract
from PIL import Image
from kimi_api import ask_kimi
from utils.report_generator import generate_learning_report
import pandas as pd
import matplotlib.font_manager as fm
import os
import easyocr
import io
from langdetect import detect

# 设置 pytesseract 路径
pytesseract.pytesseract.tesseract_cmd = r"E:\\Tesseract-OCR\\tesseract.exe"

# 设置字体
try:
    fm.fontManager.addfont('SimHei.ttf')
    matplotlib.rcParams["font.family"] = ("SimHei")
except Exception as e:
    print("字体加载失败：", e)

matplotlib.rcParams["axes.unicode_minus"] = False

DATA_PATH = "data/user_data.json"


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
        for attempt in range(3):
            res = requests.post(url, json=data, headers=headers)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
        return "❌ 错题分析失败：服务器未响应"
    except Exception as e:
        return f"❌ 错题分析失败：{e}"


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


def extract_text_from_image(image):
    if image is None:
        return {'chinese': '', 'english': ''}
    try:
        reader = easyocr.Reader(['en', 'ch_sim'])
        result = reader.readtext(image)
        chinese_text, english_text = [], []
        for detection in result:
            detected_text = detection[1]
            try:
                language = detect(detected_text)
                if language == 'zh':
                    chinese_text.append(detected_text)
                elif language == 'en':
                    english_text.append(detected_text)
            except:
                continue
        return {
            'chinese': "\n".join(chinese_text),
            'english': "\n".join(english_text)
        }
    except Exception as e:
        return {'chinese': '', 'english': f"❌ 文本识别失败：{e}"}


def picture(data):
    subjects = data.get("subjects", {})
    report_data, subject_names, time_spent_data = [], [], []

    for subject, info in subjects.items():
        report_data.append({
            "学科": subject,
            "学习时间 (小时/天)": info.get("time_spent", 0),
            "错题描述": info.get("mistake", '无'),
            "学习备注": info.get("notes", '无')
        })
        subject_names.append(subject)
        time_spent_data.append(info.get("time_spent", 0))

    def func(pct, allvalues):
        absolute = int(pct / 100. * sum(allvalues))
        return f"{absolute}小时\n({pct:.1f}%)"

    fig, ax = plt.subplots()
    ax.pie(time_spent_data, labels=subject_names, autopct=lambda pct: func(pct, time_spent_data), startangle=50)
    ax.axis('equal')
    st.pyplot(fig)


def main():
    st.set_page_config(page_title="小知学伴", layout="wide")
    st.title("🎓 小知学伴 - AI学习助手")

    menu = st.sidebar.radio("功能菜单", ["输入学习数据", "生成学习报告", "AI答疑"])

    if menu == "输入学习数据":
        st.header("📥 输入你的学习数据")
        num_subjects = st.number_input("请输入学科数量", min_value=1, max_value=10, value=1)
        custom_subjects = [st.text_input(f"请输入第 {i+1} 门学科名称", key=f"subject_{i}") for i in range(num_subjects)]

        subject_data, all_mistakes = {}, []

        for subject in custom_subjects:
            st.subheader(f"📘 {subject} 学习情况")
            uploaded_image = st.file_uploader(f"上传 {subject} 的错题图片", type=["png", "jpg", "jpeg"], key=f"{subject}_image")

            extracted_text, combined_text = {'chinese': '', 'english': ''}, ''

            if uploaded_image is not None:
                with st.spinner("正在提取文本..."):
                    image_bytes = uploaded_image.read()
                    extracted_text = extract_text_from_image(image_bytes)
                    combined_text = f"【中文】\n{extracted_text['chinese']}\n\n【English】\n{extracted_text['english']}"
                    st.text_area(f"{subject} 识别出的错题内容", combined_text, key=f"{subject}_ocr_text")
            else:
                st.warning("请先上传图片！")

            mistake = st.text_area(f"{subject} 的错题描述（可编辑）", combined_text, key=f"{subject}_mistake")
            notes = st.text_area(f"{subject} 的其他学习备注", key=f"{subject}_notes")
            time_spent = st.slider(f"⏱️ 每天用于 {subject} 的学习时间（小时）", 0, 12, 1, key=f"{subject}_time")

            if mistake:
                all_mistakes.append(f"{subject}：{mistake}")

            subject_data[subject] = {
                "mistake": mistake,
                "notes": notes,
                "time_spent": time_spent
            }

        if st.button("保存数据"):
            save_data({"subjects": subject_data})
            st.success("✅ 数据已保存！")

        if st.button("清空所有数据"):
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            st.success("✅ 所有数据已清空！")

        if all_mistakes:
            st.markdown("### 🧠 错题分析")
            st.write("你已输入以下错题：")
            for i, m in enumerate(all_mistakes, 1):
                st.write(f"{i}. {m}")

            if st.button("分析我的错题"):
                with st.spinner("正在分析中..."):
                    mistake_text = "\n".join(all_mistakes)
                    response = analyze_mistakes_with_kimi(mistake_text)
                    st.markdown("#### 📊 Kimi 分析结果")
                    st.write(response)

    elif menu == "生成学习报告":
        st.header("📊 AI生成个性化学习报告")
        data = load_data()
        if data:
            with st.spinner("正在分析..."):
                picture(data)
                report = generate_learning_report(data)
                st.markdown(report)
        else:
            st.warning("请先在左侧填写学习数据")

    elif menu == "AI答疑":
        st.header("🧑‍🏫 提问任意学习问题")
        uploaded_image = st.file_uploader("上传问题图片", type=["png", "jpg", "jpeg"], key="question_image")
        extracted_question_text, combined_text = '', ''

        if uploaded_image:
            with st.spinner("正在提取文本..."):
                image_bytes = uploaded_image.read()
                extracted_text = extract_text_from_image(image_bytes)
                combined_text = f"【中文】\n{extracted_text['chinese']}\n\n【English】\n{extracted_text['english']}"
                st.text_area(f"识别出的错题内容", combined_text, key=f"question_ocr_text")
        else:
            st.warning("请先上传图片！")

        question = st.text_area("请输入你的问题（可编辑）", combined_text)

        if st.button("AI回答"):
            if question:
                with st.spinner("AI 正在思考..."):
                    reply = ask_kimi(question)
                    st.markdown("**AI答复：**")
                    st.write(reply)
            else:
                st.warning("请输入或上传问题图片以获取答案。")


if __name__ == '__main__':
    main()
