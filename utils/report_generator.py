from kimi_api import ask_kimi

def generate_learning_report(user_data):
    prompt = f"""
你是一个教育专家。根据以下学生的学习数据，分析其薄弱点、学习习惯，并给出提升建议：
数据如下：
{user_data}
请用中文输出一份简洁的学习报告，包含以下部分：
1. 学习概况；
2. 存在问题；
3. 改进建议。
"""
    return ask_kimi(prompt)
