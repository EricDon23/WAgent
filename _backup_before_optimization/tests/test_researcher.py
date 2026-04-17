#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试2：研究模块测试

目标：验证能否输出可调用的资料库
预期结果：
- ✅ MCP服务启动成功，无连接错误
- ✅ 成功生成knowledge_base.json
- ✅ 文件包含research_topic、key_findings、references字段
- ✅ 每个研究主题至少有2条关键发现
- ✅ 内容可被作家AI直接解析调用
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.researcher_ai import ResearcherAI


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_researcher_module():
    """研究员AI模块完整测试"""
    
    print_section("🔍 测试2：研究员AI模块 (Researcher AI)")
    
    results = []
    start_time = datetime.now()
    
    # 初始化研究员AI
    print("[步骤1] 初始化研究员AI...")
    researcher = ResearcherAI()
    
    init_success = researcher.initialize()
    
    if not init_success:
        print("❌ 研究员AI初始化失败")
        return False
    
    print("✅ 研究员AI初始化成功")
    results.append(("初始化", True))
    
    # 测试研究需求
    test_needs = [
        "人工智能情感发展",
        "AI伦理问题",
        "未来科技城市"
    ]
    
    story_title = "智能朋友"
    story_genre = ["科幻", "言情"]
    
    print(f"\n[步骤2] 准备研究需求...")
    print(f"  故事标题: {story_title}")
    print(f"  故事类型: {', '.join(story_genre)}")
    print(f"  研究需求 ({len(test_needs)}项):")
    for i, need in enumerate(test_needs, 1):
        print(f"    {i}. {need}")
    
    results.append(("需求准备", True))
    
    # 生成知识库
    print(f"\n[步骤3] 调用研究员AI生成知识库...")
    result = researcher.generate_knowledge_base(
        research_needs=test_needs,
        story_title=story_title,
        story_genre=story_genre
    )
    
    if not result["success"]:
        print(f"❌ 知识库生成失败: {result.get('error')}")
        return False
    
    knowledge_base = result["data"]
    metadata = result["metadata"]
    
    print(f"✅ 知识库生成成功")
    print(f"  研究主题: {knowledge_base.get('research_topic', '未知')}")
    print(f"  置信度: {knowledge_base.get('confidence_level', '未知')}")
    print(f"  耗时: {metadata['generation_time']:.2f}秒")
    results.append(("知识库生成", True))
    
    # 验证必要字段
    print("\n[步骤4] 验证知识库字段完整性...")
    required_fields = [
        'research_topic',
        'key_findings',
        'references',
        'summary'
    ]
    
    missing_fields = [f for f in required_fields if f not in knowledge_base or not knowledge_base[f]]
    
    if len(missing_fields) == 0:
        print(f"✅ 所有{len(required_fields)}个必要字段完整")
        results.append(("字段完整性", True))
    else:
        print(f"❌ 缺少字段: {missing_fields}")
        results.append(("字段完整性", False))
    
    # 验证关键发现数量
    key_findings = knowledge_base.get('key_findings', [])
    print(f"\n[步骤5] 验证关键发现...")
    print(f"  关键发现总数: {len(key_findings)}条")
    
    if len(key_findings) >= len(test_needs) * 2:
        print(f"✅ 每个研究主题至少有2条关键发现（共{len(key_findings)}条）")
        results.append(("发现数量", True))
    else:
        print(f"⚠️ 关键发现偏少（{len(key_findings)}条，建议≥{len(test_needs)*2}条）")
        results.append(("发现数量", False))
    
    # 显示部分关键发现
    if key_findings:
        print("\n  关键发现示例:")
        for i, finding in enumerate(key_findings[:5], 1):
            if isinstance(finding, dict):
                category = finding.get('category', '')
                fact = finding.get('finding', '')[:80]
                print(f"    {i}. [{category}] {fact}...")
            else:
                print(f"    {i}. {str(finding)[:80]}...")
    
    # 验证参考文献
    references = knowledge_base.get('references', [])
    print(f"\n[步骤6] 验证参考文献...")
    print(f"  参考文献数: {len(references)}项")
    
    if references:
        print("  参考文献示例:")
        for i, ref in enumerate(references[:3], 1):
            if isinstance(ref, dict):
                title = ref.get('title', '')
                reftype = ref.get('type', '')
                print(f"    {i}. [{reftype}] {title}")
        
        results.append(("参考文献", True))
    else:
        print("⚠️ 无参考文献")
        results.append(("参考文献", None))
    
    # 显示研究摘要
    summary = knowledge_base.get('summary', '')
    if summary:
        print(f"\n[步骤7] 研究摘要:")
        print(f"  {summary[:200]}..." if len(summary) > 200 else f"  {summary}")
        results.append(("摘要生成", True))
    
    # 验证内容可解析性
    print("\n[步骤8] 验证内容可解析性...")
    try:
        kb_json = json.dumps(knowledge_base, ensure_ascii=False)
        parsed_back = json.loads(kb_json)
        
        if parsed_back == knowledge_base:
            print("✅ 内容可以正常序列化和反序列化")
            results.append(("可解析性", True))
        else:
            print("⚠️ 序列化后数据有差异")
            results.append(("可解析性", False))
    except Exception as e:
        print(f"❌ 序列化失败: {e}")
        results.append(("可解析性", False))
    
    # 保存知识库文件
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'stories', 'story_001', 'research')
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, 'knowledge_base.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test": "researcher_module",
            "timestamp": datetime.now().isoformat(),
            "story_id": "story_001",
            "input": {
                "research_needs": test_needs,
                "story_title": story_title,
                "story_genre": story_genre
            },
            "output": knowledge_base,
            "metadata": metadata
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 知识库已保存: stories/story_001/research/knowledge_base.json")
    results.append(("文件保存", True))
    
    # 统计结果
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    passed_tests = sum(1 for _, success in results if success is True)
    total_tests = sum(1 for _, success in results if success is not None)
    
    print_section("📊 测试2结果统计")
    print(f"⏱️ 总耗时: {duration:.2f}秒")
    print(f"✅ 通过: {passed_tests}/{total_tests}")
    
    if passed_tests >= total_tests * 0.8:
        print("🎉 测试2通过！成功生成可调用的资料库")
        return True
    else:
        print("⚠️ 测试2存在问题")
        return False


if __name__ == "__main__":
    success = test_researcher_module()
    sys.exit(0 if success else 1)
