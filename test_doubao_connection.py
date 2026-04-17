#!/usr/bin/env python
"""
豆包模型连接测试脚本
验证修正后的模型ID和配置是否正确
"""

from ai.director_ai import DirectorAI
import json

if __name__ == "__main__":
    print("🔍 测试豆包模型连接...")
    
    try:
        # 初始化导演AI
        director = DirectorAI()
        
        # 测试生成故事设定
        test_input = "一个关于AI获得情感的科幻故事"
        result = director.generate_setting(test_input)
        
        if result["success"]:
            print("✅ 豆包模型调用成功！")
            print(f"故事名称：{result['data']['story_name']}")
            print(f"一句话梗概：{result['data']['story_summary']}")
            print(f"需要研究的主题：{result['data']['research_needs']}")
            print(f"使用的模型：{result['metadata']['model_used']}")
        else:
            print(f"❌ 调用失败：{result.get('error')}")
            
    except Exception as e:
        print(f"❌ 调用失败：{str(e)}")
        print("请检查：")
        print("1. API Key是否正确")
        print("2. 模型ID是否与火山引擎控制台完全一致")
        print("3. 网络是否正常")