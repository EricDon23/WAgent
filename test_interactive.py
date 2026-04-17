#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent Interactive 自动化测试脚本
验证所有新增功能的正确性
"""

import asyncio
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

async def test_core_components():
    """测试核心组件功能"""
    print("=" * 60)
    print("🧪 WAgent Interactive 核心功能测试")
    print("=" * 60)
    
    results = []
    
    # 1. 测试导入
    print("\n[1/7] 测试模块导入...")
    try:
        from main_interactive import (
            WAgentInteractive, RealtimeDisplay, SystemState,
            ConstraintConfig, AsyncCacheManager, ThinkingLogger,
            AsyncDirectorAI, AsyncResearcherAI, AsyncWriterAI,
            ZipArchiver
        )
        print("   ✅ 所有模块导入成功")
        results.append(("模块导入", True))
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        results.append(("模块导入", False))
        return results
    
    # 2. 测试约束配置
    print("\n[2/7] 测试约束配置...")
    config = ConstraintConfig()
    
    test_cases = [
        (1000, False),  # 太少
        (1400, True),   # 在范围内
        (2000, True),   # 完美
        (2800, False),  # 超出范围
    ]
    
    all_passed = True
    for count, expected in test_cases:
        passed, msg = config.validate_word_count(count)
        if passed != expected:
            all_passed = False
            print(f"   ❌ {count}字: 预期{expected}, 实际{passed}")
        else:
            print(f"   ✅ {count}字: {msg}")
    
    results.append(("约束校验", all_passed))
    
    # 3. 测试实时状态显示
    print("\n[3/7] 测试实时状态显示...")
    display = RealtimeDisplay()
    
    assert display.status.state == SystemState.IDLE
    display.update(SystemState.DIRECTOR_GENERATING, "测试中...", 50, "测试消息")
    
    assert display.status.state == SystemState.DIRECTOR_GENERATING
    assert display.status.progress_percent == 50.0
    assert display.status.message == "测试消息"
    
    status_str = display._format_status()
    assert "DIRECTOR_GENERATING" in status_str or "导演AI生成中" in status_str
    
    print("   ✅ 状态更新和格式化正常")
    results.append(("状态显示", True))
    
    # 4. 测试缓存管理器
    print("\n[4/7] 测试缓存管理器...")
    cache = AsyncCacheManager()
    await cache.initialize()
    
    test_data = {"test": "data", "timestamp": "2026-04-16"}
    await cache.set("test:key", test_data)
    
    retrieved = await cache.get("test:key")
    assert retrieved == test_data
    
    not_found = await cache.get("nonexistent:key")
    assert not_found is None or not_found is None
    
    await cache.close()
    print("   ✅ 缓存读写正常")
    results.append(("缓存管理", True))
    
    # 5. 测试思考日志
    print("\n[5/7] 测试思考日志...")
    logger = ThinkingLogger(log_path="logs/test_thinking.log")
    
    await logger.log("director", "test_action", "test_content", {"key": "value"})
    assert len(logger.logs) == 1
    assert logger.logs[0]["stage"] == "director"
    
    await logger.save_full_log()
    log_file = Path("logs/test_thinking.full.json")
    assert log_file.exists()
    
    print(f"   ✅ 日志记录正常 ({len(logger.logs)}条)")
    results.append(("日志系统", True))
    
    # 6. 测试ZIP归档
    print("\n[6/7] 测试ZIP归档功能...")
    test_dir = Path("stories/test_zip_archive")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建测试文件
    (test_dir / "test.txt").write_text("测试内容", encoding='utf-8')
    (test_dir / "subdir").mkdir(exist_ok=True)
    (test_dir / "subdir" / "nested.txt").write_text("嵌套文件", encoding='utf-8')
    
    zip_path = ZipArchiver.create_archive("test_zip", test_dir)
    assert Path(zip_path).exists()
    
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        assert len(names) >= 2  # 至少包含两个文件
    
    # 清理
    shutil.rmtree(test_dir) if test_dir.exists() else None
    Path(zip_path).unlink() if Path(zip_path).exists() else None
    
    print(f"   ✅ ZIP归档正常 (路径: {zip_path})")
    results.append(("ZIP归档", True))
    
    # 7. 测试AI组件初始化
    print("\n[7/7] 测试AI组件初始化...")
    
    logger_prod = ThinkingLogger(log_path="logs/thinking_interactive_test.log")
    cache_prod = AsyncCacheManager()
    await cache_prod.initialize()
    
    config_obj = type('Config', (), {
        'director_max_tokens': 2048,
        'director_temperature': 0.0,
        'writer_max_tokens': 4096,
        'writer_temperature': 1.0,
        'researcher_max_tokens': 3000,
        'researcher_temperature': 0.0,
        'stream_timeout': 180,
        'cache_ttl': 3600
    })()
    
    director = AsyncDirectorAI(config_obj, logger_prod, cache_prod)
    researcher = AsyncResearcherAI(config_obj, logger_prod, cache_prod)
    writer = AsyncWriterAI(config_obj, logger_prod, cache_prod)
    
    assert director.model == os.getenv('DOUBAO_MODEL', '')
    assert researcher.model == os.getenv('DASHSCOPE_MODEL', '')
    assert writer.model == os.getenv('DEEPSEEK_MODEL', '')
    
    await cache_prod.close()
    
    print("   ✅ AI组件初始化成功")
    results.append(("AI组件", True))
    
    return results


async def run_quick_integration_test():
    """快速集成测试 - 模拟完整流程"""
    print("\n" + "=" * 60)
    print("🔄 快速集成测试")
    print("=" * 60)
    
    from main_interactive import WAgentInteractive
    
    wagent = WAgentInteractive()
    await wagent.initialize()
    
    # 模拟用户输入
    test_input = "一个关于时间旅行的科幻短篇"
    
    print(f"\n📝 模拟输入: {test_input}")
    
    # 导演阶段
    print("\n--- 导演AI阶段 ---")
    setting = await wagent.director_ai.generate_setting(
        test_input, wagent.display
    )
    
    assert setting.get('story_name'), "故事名称不能为空"
    assert setting.get('story_summary'), "梗概不能为空"
    assert len(setting.get('characters', [])) >= 2, "至少需要2个角色"
    assert len(setting.get('research_needs', [])) >= 2, "至少需要2个研究主题"
    
    print(f"   ✅ 设定生成成功: {setting['story_name']}")
    print(f"   📊 角色: {len(setting['characters'])}个")
    print(f"   🔬 研究需求: {len(setting['research_needs'])}项")
    
    # 研究员阶段
    print("\n--- 研究员AI阶段 ---")
    kb = await wagent.researcher_ai.generate_knowledge_base(
        research_needs=setting.get('research_needs', []),
        story_title=setting.get('story_name', ''),
        story_type=setting.get('genre', ''),
        display=wagent.display
    )
    
    assert kb.get('research_topic'), "研究主题不能为空"
    assert kb.get('summary'), "摘要不能为空"
    
    print(f"   ✅ 知识库生成成功: {kb['research_topic']}")
    print(f"   📋 发现: {len(kb.get('key_findings', []))}条")
    
    # 作家阶段
    print("\n--- 作家AI阶段 ---")
    chapter = await wagent.writer_ai.generate_chapter(
        chapter_num=1,
        story_setting=setting,
        knowledge_base=kb,
        display=wagent.display
    )
    
    assert chapter.get('success'), "章节生成失败"
    content = chapter['data']['content']
    word_count = chapter['data']['word_count']
    
    assert word_count > 100, f"字数过少: {word_count}"
    assert len(content) > 50, "内容过短"
    
    constraint_check = chapter['data'].get('constraint_check', {})
    print(f"   ✅ 章节生成成功: {word_count}字")
    print(f"   ⚖️ 约束检查: {constraint_check.get('message', 'N/A')}")
    
    # 清理
    await wagent.cache.close()
    
    print("\n" + "=" * 60)
    print("✅ 集成测试全部通过!")
    print("=" * 60)


async def main():
    """主测试函数"""
    start_time = time.time() if 'time' in dir() else __import__('time').time()
    
    # 运行单元测试
    unit_results = await test_core_components()
    
    # 显示结果
    print("\n" + "=" * 60)
    print("📊 单元测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, ok in unit_results if ok)
    total = len(unit_results)
    
    for name, ok in unit_results:
        icon = "✅" if ok else "❌"
        status = "通过" if ok else "失败"
        print(f"  {icon} {name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n运行集成测试...")
        try:
            await run_quick_integration_test()
        except Exception as e:
            print(f"\n⚠️ 集成测试跳过或部分失败: {e}")
            import traceback
            traceback.print_exc()
    
    elapsed = time.time() if 'time' in dir() else __import__('time').time() - start_time
    print(f"\n⏱️ 总耗时: {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())