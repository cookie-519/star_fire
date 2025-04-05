import requests

KIMI_API_KEY = "sk-I0dxd07uFwsojf6460SVpMDBG3d2jGLgqtyBwD2WjcJeJ6vd"
KIMI_API_URL = "https://api.moonshot.cn/v1"

def ask_kimi(prompt):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}"
    }

    data = {
        "model": "moonshot-v1-8k",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    response = requests.post(KIMI_API_URL, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return f"调用失败：{response.text}"
