#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent API连接性诊断工具
检查所有AI引擎的API连接状态
"""

import sys
import os
import asyncio
import aiohttp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


async def test_doubao_api():
    """测试豆包API"""
    print("\n" + "="*60)
    print("🔍 测试1: 豆包 (Doubao) API - 导演AI")
    print("="*60)
    
    api_key = os.getenv('DOUBAO_API_KEY', '')
    base_url = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    model = os.getenv('DOUBAO_MODEL', 'doubao-seed-2-0-pro-260215')
    
    print(f"   API Key: {api_key[:15]}...{api_key[-6:] if len(api_key) > 20 else ''}")
    print(f"   Base URL: {base_url}")
    print(f"   Model: {model}")
    
    if not api_key or 'your_' in api_key.lower():
        print("   ❌ 未配置有效的API密钥")
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己"}],
                    "temperature": 0.7,
                    "max_tokens": 100
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                
                print(f"   HTTP状态码: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    content = data['choices'][0]['message']['content']
                    print(f"   ✅ API连接成功！")
                    print(f"   📝 响应内容: {content[:100]}...")
                    return True
                else:
                    error_text = await resp.text()
                    print(f"   ❌ API错误: {resp.status}")
                    print(f"   📄 错误详情: {error_text[:200]}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ 连接异常: {e}")
        return False


async def test_deepseek_api():
    """测试DeepSeek API"""
    print("\n" + "="*60)
    print("🔍 测试2: DeepSeek API - 作家AI")
    print("="*60)
    
    api_key = os.getenv('DEEPSEEK_API_KEY', '')
    base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
    print(f"   Base URL: {base_url}")
    
    if not api_key or 'your_' in api_key.lower():
        print("   ❌ 未配置有效的API密钥")
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "说一句话测试"}],
                    "max_tokens": 50
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                
                print(f"   HTTP状态码: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    content = data['choices'][0]['message']['content']
                    print(f"   ✅ API连接成功！")
                    print(f"   📝 响应: {content[:80]}...")
                    return True
                else:
                    error_text = await resp.text()
                    print(f"   ❌ API错误: {resp.status}")
                    print(f"   📄 详情: {error_text[:150]}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ 连接异常: {e}")
        return False


async def test_dashscope_api():
    """测试通义千问API"""
    print("\n" + "="*60)
    print("🔍 测试3: 通义千问 (DashScope) API - 研究员AI")
    print("="*60)
    
    api_key = os.getenv('DASHSCOPE_API_KEY', '')
    base_url = os.getenv('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    
    print(f"   API Key: {api_key[:10]}..." if len(api_key) > 10 else "   API Key: [未配置]")
    print(f"   Base URL: {base_url}")
    
    if not api_key or 'your_' in api_key.lower():
        print("   ⚠️ 未配置有效密钥（使用默认值占位符）")
        print("   💡 提示: 需要在.env中配置真实的阿里云DashScope API Key")
        return None  # 返回None表示未配置
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen-plus",
                    "messages": [{"role": "user", "content": "测试"}],
                    "max_tokens": 30
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                
                print(f"   HTTP状态码: {resp.status}")
                
                if resp.status == 200:
                    print("   ✅ API连接成功！")
                    return True
                else:
                    error_text = await resp.text()
                    print(f"   ❌ API错误: {resp.status}")
                    print(f"   📄 详情: {error_text[:150]}")
                    return False
                    
    except Exception as e:
        print(f"   ❌ 连接异常: {e}")
        return False


async def main():
    """主函数"""
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#" + "  🏥 WAgent API 诊断中心".center(58) + "#")
    print("#" + "  检查所有AI引擎的连接状态".center(56) + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    results = {}
    
    results['doubao'] = await test_doubao_api()
    results['deepseek'] = await test_deepseek_api()
    results['dashscope'] = await test_dashscope_api()
    
    # 汇总
    print("\n" + "#"*70)
    print("#  诊断结果汇总")
    print("#"*70)
    
    for name, result in results.items():
        if result is True:
            status = "✅ 正常"
        elif result is False:
            status = "❌ 失败"
        else:
            status = "⚠️ 未配置"
        
        engine_name = {'doubao': '导演AI (Doubao)', 
                      'deepseek': '作家AI (DeepSeek)', 
                      'dashscope': '研究员AI (Qwen)'}[name]
        print(f"#  {engine_name}: {status}")
    
    print("#"*70)
    
    # 给出建议
    available = sum(1 for r in results.values() if r is True)
    
    print(f"\n📊 可用引擎数: {available}/3")
    
    if available == 0:
        print("\n⚠️ 所有API均不可用！系统将使用Mock数据（模拟数据）")
        print("💡 解决方案:")
        print("   1. 检查API密钥是否正确")
        print("   2. 确认账户余额充足")
        print("   3. 验证网络连接正常")
        print("   4. 更新.env文件中的API配置")
    elif available < 3:
        print(f"\n⚠️ 只有{available}个引擎可用，部分功能将使用Mock数据")
    else:
        print("\n✅ 所有引擎可用！可以正常生成故事")


if __name__ == '__main__':
    asyncio.run(main())
