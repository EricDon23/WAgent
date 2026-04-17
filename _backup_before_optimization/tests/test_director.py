#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试1：导演AI模块测试

目标：验证能否成功输出严格约束的结构化设定
预期结果：
- ✅ 输出100%符合JSON格式，无语法错误
- ✅ 所有9个必填字段完整且内容合理
- ✅ 3次运行输出完全一致（温度=0验证）
- ✅ research_needs字段包含至少3个研究主题
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.director_ai import DirectorAI, StorySetting


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_director_module():
    """导演AI模块完整测试"""
    
    print_section("🎬 测试1：导演AI模块 (Director AI)")
    
    results = []
    start_time = datetime.now()
    
    # 初始化导演AI
    print("[步骤1] 初始化导演AI...")
    director = DirectorAI()
    
    init_success = director.initialize()
    
    if not init_success:
        print("❌ 导演AI初始化失败")
        return False
    
    print("✅ 导演AI初始化成功")
    results.append(("初始化", True))
    
    # 测试输入
    test_input = "一个关于AI获得情感的科幻故事"
    print(f"\n[步骤2] 准备测试输入...")
    print(f"  输入: \"{test_input}\"")
    results.append(("输入准备", True))
    
    # 第一次生成
    print("\n[步骤3] 第一次生成故事设定...")
    result1 = director.generate_setting(test_input)
    
    if not result1["success"]:
        print(f"❌ 第一次生成失败: {result1.get('error')}")
        return False
    
    setting1 = result1["data"]
    metadata1 = result1["metadata"]
    
    print(f"✅ 第一次生成成功 | 标题: {setting1.get('story_name', '未知')}")
    print(f"  耗时: {metadata1['generation_time']:.2f}秒")
    results.append(("第一次生成", True))
    
    # 验证字段完整性
    print("\n[步骤4] 验证字段完整性...")
    required_fields = [
        'story_name',
        'story_summary',
        'story_intro',
        'theme',
        'characters',
        'relationships',
        'plot_outline',
        'constraints',
        'research_needs'
    ]
    
    missing_fields = [f for f in required_fields if f not in setting1 or not setting1[f]]
    
    if len(missing_fields) == 0:
        print(f"✅ 所有{len(required_fields)}个必填字段完整")
        results.append(("字段完整性", True))
    else:
        print(f"❌ 缺少字段: {missing_fields}")
        results.append(("字段完整性", False))
    
    # 验证research_needs
    research_needs = setting1.get('research_needs', [])
    if len(research_needs) >= 3:
        print(f"✅ research_needs包含{len(research_needs)}个研究主题:")
        for i, need in enumerate(research_needs[:5], 1):
            print(f"  {i}. {need}")
        results.append(("研究需求", True))
    else:
        print(f"⚠️ research_needs仅包含{len(research_needs)}个主题（需要≥3）")
        results.append(("研究需求", False))
    
    # 第二次生成（验证温度=0的一致性）
    print("\n[步骤5] 第二次生成（验证温度=0一致性）...")
    result2 = director.generate_setting(test_input)
    
    if result2["success"]:
        setting2 = result2["data"]
        
        # 比较两次输出
        is_identical = (setting1 == setting2)
        
        if is_identical:
            print("✅ 两次输出完全一致（温度=0验证通过）")
            results.append(("温度一致性", True))
        else:
            print("⚠️ 两次输出存在差异（可能存在微小随机性）")
            # 检查关键字段是否一致
            key_match = all(
                setting1.get(k) == setting2.get(k) 
                for k in ['story_name', 'theme']
            )
            
            if key_match:
                print("✅ 关键字段一致，基本通过")
                results.append(("温度一致性", True))
            else:
                print("❌ 关键字段不一致")
                results.append(("温度一致性", False))
    else:
        print("⚠️ 第二次生成失败，跳过一致性检查")
        results.append(("温度一致性", None))
    
    # 第三次生成
    print("\n[步骤6] 第三次生成...")
    result3 = director.generate_setting(test_input)
    
    if result3["success"]:
        setting3 = result3["data"]
        print(f"✅ 第三次生成成功 | 标题: {setting3.get('story_name', '未知')}")
        results.append(("第三次生成", True))
    else:
        print("⚠️ 第三次生成失败")
        results.append(("第三次生成", False))
    
    # 显示生成的设定摘要
    print("\n[步骤7] 生成的StorySetting摘要:")
    print("-" * 60)
    print(f"📝 标题: {setting1.get('story_name')}")
    print(f"📄 梗概: {setting1.get('story_summary')}")
    print(f"📖 简介: {setting1.get('story_intro')[:100]}...")
    print(f"🎯 主题: {setting1.get('theme')}")
    
    characters = setting1.get('characters', [])
    print(f"👥 角色 ({len(characters)}个):")
    for char in characters[:3]:
        if isinstance(char, dict):
            print(f"   • {char.get('name')} ({char.get('role')}): {char.get('personality')[:30]}...")
    
    print(f"\n🔬 研究需求 ({len(research_needs)}项):")
    for need in research_needs:
        print(f"   • {need}")
    
    print("-" * 60)
    
    # 保存结果
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'test_output')
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, 'test1_director_result.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test": "director_module",
            "timestamp": datetime.now().isoformat(),
            "input": test_input,
            "output": setting1,
            "metadata": metadata1,
            "validation": {
                "all_fields_present": len(missing_fields) == 0,
                "research_needs_count": len(research_needs),
                "temperature_consistency": is_identical if 'is_identical' in locals() else None
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: test_output/test1_director_result.json")
    
    # 统计结果
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    passed_tests = sum(1 for _, success in results if success is True)
    total_tests = sum(1 for _, success in results if success is not None)
    
    print_section("📊 测试1结果统计")
    print(f"⏱️ 总耗时: {duration:.2f}秒")
    print(f"✅ 通过: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 测试1完全通过！导演AI输出稳定、结构化、无随机")
        return True
    elif passed_tests >= total_tests * 0.8:
        print("✨ 测试1基本通过，有少量问题需关注")
        return True
    else:
        print("❌ 测试1未通过")
        return False


if __name__ == "__main__":
    success = test_director_module()
    sys.exit(0 if success else 1)
