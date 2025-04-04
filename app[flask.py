import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for
from PIL import Image
from io import BytesIO
import base64
import time
import markdown2
import pdfkit
from datetime import datetime

# 百度 OCR API 凭证
BAIDU_API_KEY = "NPjp0N3hvrka5UwT08FnciAO"
BAIDU_SECRET_KEY = "qg3dLPDeW7X3xXKhpSmPslMCaXPKw3rU"

DATA_PATH = "data/user_data.json"
os.makedirs("data", exist_ok=True)

app = Flask(__name__)


# === 百度 OCR Access Token ===
def get_baidu_access_token():
    token_url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY
    }
    response = requests.post(token_url, data=params)
    return response.json().get("access_token")


# === 使用百度 OCR 识别图片 ===
def extract_text_from_image(image):
    image = image.convert("RGB")

    token = get_baidu_access_token()
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()

    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"image": img_b64}

    response = requests.post(url, headers=headers, data=data)
    result = response.json()

    if "words_result" in result:
        return "\n".join([item["words"] for item in result["words_result"]])
    else:
        return f"❌ OCR失败：{result.get('error_msg', '未知错误')}"


# === 学习报告生成 ===
def generate_learning_report(data):
    time_spent = data.get("time_spent", 0)
    subjects = data.get("subjects", {})
    report = "# 📘 个性化学习报告\n\n"
    report += f"你每天平均学习时间为 **{time_spent} 小时**。\n\n"
    report += f"你记录了 **{len(subjects)} 门学科** 的学习情况。\n\n"

    for subject, info in subjects.items():
        mistake = info.get("mistake", "").strip()
        notes = info.get("notes", "").strip()
        report += f"## 🧪 {subject}\n"
        report += f"- 错题描述：{mistake or '无记录'}\n"
        report += f"- 学习备注：{notes or '无'}\n"
        if mistake:
            report += "- 建议：加强复习相关知识点，必要时寻求帮助。\n"
        report += "\n"

    report += "---\n📈 **总体建议**：保持学习习惯，重视错题总结，持续进步！\n"
    return report


# === PDF 导出 ===
def export_report_to_pdf(markdown_text, output_path="learning_report.pdf"):
    html = markdown2.markdown(markdown_text)
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
    try:
        pdfkit.from_string(html, output_path, configuration=config)
        return output_path
    except Exception as e:
        return f"❌ PDF 导出失败：{e}"


# === 主程序 ===
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return '没有文件部分'

    file = request.files['file']
    if file.filename == '':
        return '未选择文件'

    if file:
        image = Image.open(file)
        extracted_text = extract_text_from_image(image)
        return render_template('index.html', extracted_text=extracted_text)


@app.route('/save_data', methods=['POST'])
def save_user_data():
    data = request.form.to_dict()
    save_data(data)
    return redirect(url_for('home'))


@app.route('/generate_report')
def generate_report():
    data = load_data()
    report = generate_learning_report(data)
    return render_template('report.html', report=report)


@app.route('/download_pdf')
def download_pdf():
    data = load_data()
    report = generate_learning_report(data)
    filename = f"学习报告_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = export_report_to_pdf(report, output_path=filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name=filename)
    else:
        return "PDF 生成失败"


def load_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    app.run(debug=True)
