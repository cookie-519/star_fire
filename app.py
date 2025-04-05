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
from io import BytesIO


# 设置 pytesseract 路径
pytesseract.pytesseract.tesseract_cmd = r"E:\Tesseract-OCR\tesseract.exe"

# 设置字体
fm.fontManager.addfont('SimHei.ttf')  # 确保文件在当前目录
matplotlib.rcParams["font.family"] = ("SimHei")
matplotlib.rcParams["axes.unicode_minus"] = False

DATA_PATH = "data/user_data.json"


# Kimi API 请求函数
def analyze_mistakes_with_kimi(mistake_text):
    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "sk-I0dxd07uFwsojf6460SVpMDBG3d2jGLgqtyBwD2WjcJeJ6vd"
    }
    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system",
             "content": "你是一个专业学习导师，请分析以下错题内容，找出学生的共性问题、薄弱知识点，并提出改进建议，尽量精炼且实用。"},
            {"role": "user", "content": mistake_text}
        ]
    }
    try:
        for attempt in range(3):  # 最多重试3次
            res = requests.post(url, json=data, headers=headers)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                print(f"Request failed with status code {res.status_code}. Retrying...")
                time.sleep(2)  # 等待2秒后重试
        return "❌ 错题分析失败：服务器未响应"
    except Exception as e:
        return f"❌ 错题分析失败：{e}"
# 读取本地数据
def load_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


# 保存数据，支持数据累加
def save_data(new_data):
    existing_data = load_data()

    # 累加数据
    if "subjects" in existing_data:
        existing_data["subjects"].update(new_data["subjects"])
    else:
        existing_data = new_data

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)


# 解析图片中的错题内容
def extract_text_from_image(image):

    if image is None:
        raise ValueError("No image provided. Please upload an image.")

    if isinstance(image, str):  # 如果是文件路径或 URL
        with open(image, "rb") as f:
            image_bytes = f.read()
        img = Image.open(BytesIO(image_bytes))
    else:  # 如果是文件对象或字节流
        img = Image.open(BytesIO(image.read()))

    
    reader = easyocr.Reader(['ch_sim'])  # 使用简体中文
    
    # 将上传的图片文件（字节流）转为 PIL 图像
    img = Image.open(BytesIO(image.read()))  # 将字节流转换为 PIL 图像

    # 使用 easyocr 读取图像中的文本
    result = reader.readtext(img)
    
    text = ""
    for detection in result:
        text += detection[1] + "\n"
    
    return text



# 图片转换为字节流的辅助函数
def image_to_bytes(image):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()


# 生成学习报告中的饼图
def picture(data):
    subjects = data.get("subjects", {})
    report_lines = ["## 📝 学习报告"]

    # 创建一个空的 DataFrame，用于展示数据
    report_data = []
    subject_names = []
    time_spent_data = []

    for subject, info in subjects.items():
        report_data.append({
            "学科": subject,
            "学习时间 (小时/天)": info.get("time_spent", 0),
            "错题描述": info.get("mistake", '无'),
            "学习备注": info.get("notes", '无')
        })
        subject_names.append(subject)
        time_spent_data.append(info.get("time_spent", 0))

    # 自定义标签显示具体时间和百分比
    def func(pct, allvalues):
        absolute = int(pct / 100.*sum(allvalues))  # 计算具体时间
        return f"{absolute}小时\n({pct:.1f}%)"  # 格式化输出

    # 绘制合并所有科目学习时间的饼图
    fig, ax = plt.subplots()
    ax.pie(time_spent_data, labels=subject_names, autopct=lambda pct: func(pct, time_spent_data), startangle=50)
    ax.axis('equal')  # 保证饼图是圆形的
    report_lines.append("### 学习时间分布图")
    
    # 将图片保存到文件并通过 Streamlit 显示
    st.pyplot(fig)  # This will display the pie chart directly


# 主函数
def main():
    st.set_page_config(page_title="小知学伴", layout="wide")
    st.title("🎓 小知学伴 - AI学习助手")

    menu = st.sidebar.radio("功能菜单", ["输入学习数据", "生成学习报告", "AI答疑"])

    if menu == "输入学习数据":
        st.header("📥 输入你的学习数据")

        # 用户自定义学科数量和名称
        num_subjects = st.number_input("请输入学科数量", min_value=1, max_value=10, value=1)

        custom_subjects = []
        for i in range(num_subjects):
            subject_name = st.text_input(f"请输入第 {i+1} 门学科名称", key=f"subject_{i}")
            custom_subjects.append(subject_name)

        selected_subjects = custom_subjects
        subject_data = {}
        all_mistakes = []

        for subject in selected_subjects:
            st.subheader(f"📘 {subject} 学习情况")

            uploaded_image = st.file_uploader(f"上传 {subject} 的错题图片", type=["png", "jpg", "jpeg"],
                                              key=f"{subject}_image")
            extracted_text = ""

            if uploaded_image:
                extracted_text = extract_text_from_image(image)
                st.text_area(f"{subject} 识别出的错题内容", extracted_text, key=f"{subject}_ocr_text")

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

        if st.button("保存数据"):
            data = {
                "subjects": subject_data
            }
            save_data(data)
            st.success("✅ 数据已保存！")

        if st.button("清空所有数据"):
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            st.success("✅ 所有数据已清空！")


        # ✅ 错题分析区
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


 # AI答疑部分
    elif menu == "AI答疑":
    
        st.header("🧑‍🏫 提问任意学习问题")
    
        # 上传问题图片
        uploaded_image = st.file_uploader("上传问题图片", type=["png", "jpg", "jpeg"], key="question_image")
        
        # 识别图片中的文本
        extracted_question_text = ""
        if uploaded_image:
            # 提取图片中的文本
            extracted_question_text = extract_text_from_image(image)
            st.text_area("识别出的问题", extracted_question_text, key="question_ocr_text")
    
        # 用户输入问题文本
        question = st.text_area("请输入你的问题（可编辑）", extracted_question_text)
    
        if st.button("AI回答"):
            # 如果没有上传图片，则直接使用用户输入的问题
            if not question and extracted_question_text:
                question = extracted_question_text  # 如果没有输入，使用图片中的文本
    
            if question:
                with st.spinner("AI 正在思考..."):
                    # 使用 Kimi API 获取回答
                    reply = ask_kimi(question)
                    st.markdown("**AI答复：**")
                    st.write(reply)
            else:
                st.warning("请输入或上传问题图片以获取答案。")



if __name__ == '__main__':
    main()
