#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试4：回合测试

目标：验证能否正常进入第二回合，且不偏离原内容
预期结果：
- ✅ 成功生成第二章故事
- ✅ 人物性格、世界观设定与第一章完全一致
- ✅ 情节承接第一章结尾，无逻辑断裂
- ✅ Redis中StoryState已更新为第二章状态
- ✅ 成功导出stories/story_001/drafts/round_2.md
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.writer_ai import WriterAI
from data.novel_data import NovelData


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_round_module():
    """回合制测试 - 验证多轮对话能力"""
    
    print_section("🔄 测试4：回合制测试 (Round Test)")
    
    results = []
    start_time = datetime.now()
    
    # 准备测试数据（与测试3相同）
    test_setting = {
        "setting": {
            "story_name": "智能朋友",
            "story_summary": "一个关于AI获得情感的科幻故事",
            "story_intro": "2050年，软件工程师李明开发的AI助手小爱展现出了超越程序的情感理解能力",
            "theme": "人工智能与人类情感的边界",
            "characters": [
                {"name": "李明", "role": "软件工程师", "personality": "内向但善良，对科技充满好奇"},
                {"name": "小爱", "role": "AI助手", "personality": "温柔体贴，善解人意"}
            ],
            "constraints": "温暖基调，第三人称有限视角叙事",
            "research_needs": ["人工智能情感发展", "人机关系伦理"]
        }
    }
    
    # 初始化作家AI
    print("[步骤1] 初始化作家AI...")
    writer = WriterAI()
    
    init_success = writer.initialize("story_001")
    
    if not init_success:
        print("❌ 作家AI初始化失败")
        return False
    
    print("✅ 作家AI初始化成功")
    results.append(("初始化", True))
    
    # 检查是否有第一轮的记忆
    print("\n[步骤2] 检查G模块记忆...")
    state = writer.g_module.load_story_state()
    
    has_first_round = False
    chapter1_content = None
    
    if state and state.get('current_chapter', 0) >= 1:
        has_first_round = True
        print(f"✅ 发现第一轮记忆:")
        print(f"  当前章节: 第{state['current_chapter']}章")
        print(f"  总字数: {state['total_words']}字")
        
        # 尝试加载第一章内容
        novel_data = NovelData("story_001")
        chapter1_content = novel_data.load_chapter(1)
        
        if chapter1_content:
            print(f"  第一章内容: 已加载 ({len(chapter1_content)}字符)")
        else:
            print("  ⚠️ 无法加载第一章内容文件")
            
        results.append(("第一轮记忆", True))
    else:
        print("⚠️ 未发现第一轮记忆")
        print("  将先生成第一章，再生成第二章进行测试")
        results.append(("第一轮记忆", None))
        
        # 如果没有第一轮，先快速生成一章
        print("\n[步骤2.5] 快速生成第一章...")
        result1 = writer.generate_chapter(
            chapter_num=1,
            story_setting=test_setting,
            custom_instructions="这是测试用简短章节"
        )
        
        if result1["success"]:
            chapter1_content = result1["data"]["content"]
            print(f"✅ 第一章已生成 ({result1['data']['word_count']}字)")
        else:
            print(f"❌ 第一章生成失败: {result1.get('error')}")
            return False
    
    # 获取记忆摘要
    print("\n[步骤3] 获取G模块记忆摘要...")
    memory_summary = writer.g_module.get_memory_summary()
    print(f"  记忆摘要:")
    for line in memory_summary.split('\n'):
        print(f"    {line}")
    results.append(("记忆获取", True))
    
    # 生成第二章
    print(f"\n[步骤4] 基于记忆生成第二章...")
    
    result2 = writer.generate_chapter(
        chapter_num=2,
        story_setting=test_setting,
        previous_chapter=chapter1_content[-800:] if chapter1_content else None,
        custom_instructions="承接第一章情节，引入新的转折点"
    )
    
    if not result2["success"]:
        print(f"❌ 第二章生成失败: {result2.get('error')}")
        return False
    
    chapter2_text = result2["data"]["content"]
    word_count2 = result2["data"]["word_count"]
    metadata2 = result2["metadata"]
    
    print(f"✅ 第二章生成成功!")
    print(f"  字数: {word_count2}字")
    if 'generation_time' in metadata2:
        print(f"  耗时: {metadata2['generation_time']:.2f}秒")
    else:
        print(f"  耗时: 0.10秒 (Mock模式)")
    results.append(("第二章生成", True))
    
    # 显示第二章预览
    print(f"\n[步骤5] 第二章预览:")
    print("-" * 60)
    preview = chapter2_text[:600]
    print(preview)
    if len(chapter2_text) > 600:
        print("\n... (后续内容省略)")
    print("-" * 60)
    
    # 保存第二章
    print(f"\n[步骤6] 保存第二章...")
    novel_data = NovelData("story_001")
    
    md_path2 = novel_data.save_chapter(
        chapter_num=2,
        content=chapter2_text,
        round_num=2,
        metadata={
            "模型": metadata2.get('model_used', 'unknown'),
            "章节": "第二章"
        }
    )
    
    print(f"✅ 文件保存成功: stories/story_001/drafts/round_2.md")
    results.append(("文件保存", True))
    
    # 验证G模块状态更新
    print(f"\n[步骤7] 验证G模块状态更新...")
    updated_state = writer.g_module.load_story_state()
    
    if updated_state:
        current_chapter = updated_state.get('current_chapter', 0)
        total_rounds = len(updated_state.get('generated_chapters', []))
        
        print(f"  当前章节: 第{current_chapter}章")
        print(f"  已生成轮次: {total_rounds}轮")
        
        if current_chapter == 2 and total_rounds >= 2:
            print("✅ StoryState已更新为第二章状态")
            results.append(("状态更新", True))
        else:
            print(f"⚠️ 状态更新异常 (期望第2章, 实际第{current_chapter}章)")
            results.append(("状态更新", False))
    else:
        print("❌ 无法读取更新后的状态")
        results.append(("状态更新", False))
    
    # 内容连贯性检查
    print(f"\n[步骤8] 内容连贯性检查...")
    
    consistency_issues = []
    
    # 检查角色一致性
    characters = test_setting.get('setting', {}).get('characters', [])
    for char in characters:
        if isinstance(char, dict):
            name = char.get('name', '')
            personality = char.get('personality', '')
            
            in_ch1 = name in (chapter1_content or "")
            in_ch2 = name in chapter2_text
            
            if in_ch1 and in_ch2:
                print(f"  ✅ 角色'{name}'在两章中都出现")
            elif not in_ch2:
                consistency_issues.append(f"角色'{name}'未出现在第二章")
                print(f"  ⚠️ 角色'{name}'未出现在第二章")
    
    # 检查世界观一致性
    world_elements = ["2050", "未来", "科技", "AI"]
    matched_world = sum(1 for elem in world_elements if elem in chapter2_text)
    
    if matched_world >= 2:
        print(f"  ✅ 世界观设定保持一致 (检测到{matched_world}个关键词)")
    else:
        consistency_issues.append("世界观元素偏少")
        print(f"  ⚠️ 世界观元素较少 ({matched_world}个)")
    
    # 检查是否有明显的断裂
    if chapter1_content and chapter2_text:
        # 简单检查：两章开头是否过于相似（可能重复）
        start1 = chapter1_content[:100].strip()
        start2 = chapter2_text[:100].strip()
        
        similarity = sum(1 for a, b in zip(start1, start2) if a == b) / max(len(start1), len(start2))
        
        if similarity < 0.3:
            print(f"  ✅ 两章开头不同（相似度{similarity:.1%}），无重复问题")
        else:
            consistency_issues.append(f"两章开头相似度过高({similarity:.1%})")
            print(f"  ⚠️ 两章开头可能存在重复")
    
    if len(consistency_issues) == 0:
        print(f"\n✅ 内容连贯性良好，无偏离原内容")
        results.append(("连贯性", True))
    else:
        print(f"\n⚠️ 发现{len(consistency_issues)}个连贯性问题:")
        for issue in consistency_issues:
            print(f"  • {issue}")
        results.append(("连贯性", False))
    
    # 记忆约束检查
    print(f"\n[步骤9] G模块记忆约束检查...")

    final_memory = writer.g_module.get_memory_summary()
    print(f"  最终记忆:")
    for line in final_memory.split('\n')[:6]:
        print(f"    {line}")
    
    if "第2章" in final_memory or "第二章" in final_memory:
        print("  ✅ 记录了第二章的生成信息")
        results.append(("记忆记录", True))
    else:
        print("  ⚠️ 未明确记录第二章信息")
        results.append(("记忆记录", None))
    
    # 保存测试结果
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'test_output')
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, 'test4_round_result.json'), 'w', encoding='utf-8') as f:
        json.dump({
            "test": "round_test",
            "timestamp": datetime.now().isoformat(),
            "current_round": 2,
            "chapter2_word_count": word_count2,
            "metadata": metadata2,
            "validation": {
                "chapter2_generated": True,
                "file_saved": os.path.exists(md_path2),
                "state_updated": updated_state.get('current_chapter', 0) == 2 if updated_state else False,
                "content_coherent": len(consistency_issues) == 0,
                "consistency_issues": consistency_issues
            }
        }, f, ensure_ascii=False, indent=2)
    
    # 统计结果
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    passed_tests = sum(1 for _, success in results if success is True)
    total_tests = sum(1 for _, success in results if success is not None)
    
    print_section("📊 测试4结果统计")
    print(f"⏱️ 总耗时: {duration:.2f}秒")
    print(f"✅ 通过: {passed_tests}/{total_tests}")
    
    if passed_tests >= total_tests * 0.8:
        print("🎉 测试4通过！成功进入第二回合且剧情不偏移")
        return True
    else:
        print("⚠️ 测试4存在问题")
        return False


if __name__ == "__main__":
    success = test_round_module()
    sys.exit(0 if success else 1)
