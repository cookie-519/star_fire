import sqlite3
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

# 设置 Selenium WebDriver
driver = webdriver.Chrome()

# 打开题库网站
driver.get('https://www.example.com/questions')  # 假设是题库网站

# 等待页面加载
time.sleep(3)

# 抓取题目数据（根据页面结构调整抓取方式）
questions = driver.find_elements(By.CLASS_NAME, 'question-class')  # 假设题目在这个类下
answers = driver.find_elements(By.CLASS_NAME, 'answer-class')  # 假设答案在这个类下

# 创建 SQLite 数据库
conn = sqlite3.connect('questions.db')
c = conn.cursor()

# 创建表
c.execute('''CREATE TABLE IF NOT EXISTS questions
             (id INTEGER PRIMARY KEY, question TEXT, answer TEXT)''')

# 存储抓取到的数据
for q, a in zip(questions, answers):
    question_text = q.text.strip()
    answer_text = a.text.strip()
    c.execute("INSERT INTO questions (question, answer) VALUES (?, ?)", (question_text, answer_text))

# 提交并关闭数据库连接
conn.commit()
conn.close()

# 关闭浏览器
driver.quit()
