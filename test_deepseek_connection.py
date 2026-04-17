#!/usr/bin/env python
"""
DeepSeek API连通性测试脚本
使用官方提供的模板代码验证连接是否成功
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    print("🔍 测试DeepSeek API连通性...")
    
    try:
        # 从环境变量获取API Key
        api_key = os.getenv('DEEPSEEK_API_KEY')
        
        if not api_key:
            print("❌ 未找到DEEPSEEK_API_KEY环境变量")
            exit(1)
        
        # 初始化OpenAI客户端
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        # 发送测试请求
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
            stream=False
        )
        
        # 打印响应
        print("✅ DeepSeek API调用成功！")
        print(f"响应内容: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ 调用失败：{str(e)}")
        print("请检查：")
        print("1. API Key是否正确")
        print("2. 网络是否正常")
        print("3. API Key是否有余额")