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
import re

# 设置 Tesseract 路径
pytesseract.pytesseract.tesseract_cmd = r"E:\Tesseract-OCR\tesseract.exe"

# 设置字体支持中文
fm.fontManager.addfont('SimHei.ttf')
matplotlib.rcParams["font.family"] = "SimHei"
matplotlib.rcParams["axes.unicode_minus"] = False

DATA_PATH = "data/user_data.json"


# ========== 工具函数 ==========
def clean_keyword(kw):
    kw = kw.strip()
    kw = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", kw)  # 只保留中英文+数字
    return kw


def load_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def search_bilibili_videos(keyword, max_results=10, retries=3, wait_seconds=2):
    url = "https://api.bilibili.com/x/web-interface/search/type"
    params = {
        "search_type": "video",
        "keyword": keyword,
        "page": 1
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for attempt in range(retries):
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200 and "data" in res.json():
                data = res.json()
                results = data.get("data", {}).get("result", [])
                videos = []
                for item in results:
                    title = re.sub(r"<.*?>", "", item.get("title", ""))
                    link = item.get("arcurl", "")
                    duration = item.get("duration", "00:00")
                    minutes = convert_duration_to_minutes(duration)
                    videos.append({
                        "title": title,
                        "link": link,
                        "duration": duration,
                        "minutes": minutes
                    })
                if videos:
                    return videos[:max_results]
            else:
                print(f"请求失败，状态码：{res.status_code}")
        except Exception as e:
            print(f"搜索发生异常：{e}")
        time.sleep(wait_seconds)

    return []



def convert_duration_to_minutes(duration):
    try:
        parts = duration.split(":")
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60
        elif len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60
        return 0
    except:
        return 0


def analyze_weak_points_with_kimi(mistake_text):
    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "sk-你的APIKEY"
    }
    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": "你是一个专业学习导师。请从以下学生错题内容中，**提取出3~5个具体的知识点名称**，每行一个，内容简洁明了，仅列出知识点名称，不要解释或建议。"},
            {"role": "user", "content": mistake_text}
        ]
    }

    try:
        for _ in range(3):
            res = requests.post(url, json=data, headers=headers)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                return [line.strip(" 123456.-") for line in content.strip().splitlines() if line.strip()]
            time.sleep(2)
        return []
    except Exception as e:
        return []


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

    # 整合错题 + 备注内容，用于分析薄弱知识点
    #st.markdown("### 📽️ 推荐学习视频（按知识点）")

    all_contents = []
    for subject, info in data.get("subjects", {}).items():
        mistake = info.get("mistake", "")
        notes = info.get("notes", "")
        if mistake:
            all_contents.append(f"{subject}错题：{mistake}")
        if notes:
            all_contents.append(f"{subject}备注：{notes}")

    full_text = "\n".join(all_contents).strip()
    if not full_text:
        st.info("未找到可分析的内容。")
        return
    

    with st.spinner("正在分析关键知识点..."):
        # 使用 Kimi 分析知识点和常见错误
        url = "https://api.moonshot.cn/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "sk-I0dxd07uFwsojf6460SVpMDBG3d2jGLgqtyBwD2WjcJeJ6vd"  # 你的 API KEY
        }
        data_payload = {
            "model": "moonshot-v1-8k",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业学习导师，请根据以下学生的错题与学习备注，提炼出3~5个关键知识点。每个知识点以如下格式输出：\n\n知识点名称：XXX\n含义简述：YYY\n常见问题：ZZZ\n\n请务必每个知识点换行输出，确保格式清晰。"
                },
                {
                    "role": "user",
                    "content": full_text
                }
            ]
        }

        try:
            res = requests.post(url, json=data_payload, headers=headers)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                st.markdown("### 🧠 Kimi 分析的知识点概览")
                st.markdown(content)

                # 提取知识点标题（用于搜索 B站视频）
                knowledge_points = re.findall(r"知识点名称[:：]\s*(.*)", content)
                if not knowledge_points:
                    st.warning("未能识别知识点标题用于推荐")
                    return

                st.markdown("### 🎬 推荐学习视频")
                    for kw in knowledge_points:
                        kw_cleaned = clean_keyword(kw)
                        st.markdown(f"### 🎯 知识点：{kw_cleaned}")
                        videos = search_bilibili_videos(kw_cleaned, max_results=5)
                        if not videos:
                            search_url = f"https://search.bilibili.com/all?keyword={kw_cleaned}"
                            st.info(f"🔎 未找到相关视频，可手动查看 [B站搜索结果]({search_url})")
                        else:
                            for v in videos:
                                st.markdown(f"- [{v['title']}]({v['link']}) ⏱ {v['duration']}")
                    
                    else:
                        st.warning("Kimi 分析失败，请稍后重试。")
                    except Exception as e:
                        st.error(f"请求失败：{e}")

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
