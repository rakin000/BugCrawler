import openai
import base64

API_KEY_PATH = '/Users/qwb/Desktop/Distributed System Research/Furina/Tools/bug_crawler/config/gpt/api_key.txt'

with open(API_KEY_PATH, 'r') as f:
    API_KEY = f.read()

'''
    OpenAI restrict GPT-4 model's maximum context length is 8192 tokens.
    If upload file content > 8192 tokens. Please reduce the length of the messages.
'''
def get_gpt_answer(question, file_path):
    # 读取 .log 文件并转换为 base64 编码
    with open(file_path, "rb") as f:
        file_data = f.read()

    # 将文件数据编码为 base64 字符串
    base64_string = base64.b64encode(file_data).decode("utf-8")

    # 设置 OpenAI API 密钥
    openai.api_key = API_KEY

    # 使用node v1/chat/completions 发送请求
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "user",
                "content": f"Question：{question}\n\n (base64 encoding)：{base64_string}"
            },
        ]
    )
    res = response['choices'][0]['message']['content'].strip()
    return res


# testing
if __name__ == '__main__':
    question = '''
        The following are logs from Qpid Dispatch.
        Do you find any evidence of a calling relationship between processes?
        - Say ‘YES:{processes}’ if you detect a relationship in the log
        - Say ‘NO:{INDEX}’ if there is no relationship
        - Say ‘Unsure if you need more details or context’
    '''
    # log_file = "../../../bug_cases/Qpid-Dispatch-37/out01.log"
    log_file = "../../testing/out1_test.log"
    Q1_res = get_gpt_answer(question, log_file)