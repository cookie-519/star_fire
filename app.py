import streamlit as st
import json
import requests
import pytesseract
from PIL import Image
from kimi_api import ask_kimi
from utils.report_generator import generate_learning_report

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
        res = requests.post(url, json=data, headers=headers)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
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
    return pytesseract.image_to_string(image, lang="chi_sim")






def main():
    st.set_page_config(page_title="小知学伴", layout="wide")
    st.title("🎓 小知学伴 - AI学习助手")

    menu = st.sidebar.radio("功能菜单", ["输入学习数据", "生成学习报告", "AI答疑"])

    if menu == "输入学习数据":
        st.header("📥 输入你的学习数据")

        # 学科选择
        all_subjects = ["高数", "高代", "英语", "大物", "程序设计"]
        selected_subjects = st.multiselect("选择你想记录的学科", all_subjects)

        subject_data = {}
        all_mistakes = []

        for subject in selected_subjects:
            st.subheader(f"📘 {subject} 学习情况")

            uploaded_image = st.file_uploader(f"上传 {subject} 的错题图片", type=["png", "jpg", "jpeg"],
                                              key=f"{subject}_image")
            extracted_text = ""

            if uploaded_image:
                image = Image.open(uploaded_image)
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
                report = generate_learning_report(data)
            st.markdown(report)
        else:
            st.warning("请先在左侧填写学习数据")


    elif menu == "AI答疑":

        st.header("🧑‍🏫 提问任意学习问题")

        uploaded_question_image = st.file_uploader("上传问题图片", type=["png", "jpg", "jpeg"], key="question_image")

        extracted_question_text = ""

        if uploaded_question_image:
            image = Image.open(uploaded_question_image)

            extracted_question_text = extract_text_from_image(image)

            st.text_area("识别出的问题", extracted_question_text, key="question_ocr_text")

        question = st.text_area("请输入你的问题（可编辑）", extracted_question_text)

        if st.button("AI回答"):
            with st.spinner("AI 正在思考..."):
                reply = ask_kimi(question)

            st.markdown("**AI答复：**")

            st.write(reply)




if __name__ == '__main__':
    main()
