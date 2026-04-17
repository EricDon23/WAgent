#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent v6.0 核心升级功能测试套件

测试覆盖：
1. StorySessionBinder - 会话与StoryTree绑定管理
2. DataCompressor - 内存优化与数据压缩
3. KnowledgeBaseManager - 研究者资料管理
4. 集成测试 - 三大模块协同工作

运行: D:\anaconda3\python.exe test_core_upgrade_v6.py
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from wagent.core_upgrade_v6 import (
    # 模块1
    StorySessionBinder, BindingRecord, BindAction, DeletionPlan,
    create_story_binder,
    # 模块2
    DataCompressor, CompressedData, CompressionLevel, CompressionStats,
    create_compressor,
    # 模块3
    KnowledgeBaseManager, KnowledgeEntry, KnowledgeCategory,
    SupportAssessment, SupportLevel,
    create_knowledge_manager
)


class TestStorySessionBinder:
    """会话与StoryTree绑定管理器测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.binder = StorySessionBinder(base_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_create_binding(self):
        binding = self.binder.bind(
            session_id="sess_001",
            storytree_path="stories/story_test",
            metadata={"user": "test_user"}
        )
        
        assert binding.session_id == "sess_001"
        assert "story_test" in binding.storytree_path
        assert binding.is_active is True
        assert binding.bound_at != ""
    
    def test_retrieve_binding(self):
        self.binder.bind("sess_002", "stories/another_story")
        
        retrieved = self.binder.get_binding("sess_002")
        
        assert retrieved is not None
        assert retrieved.storytree_path == str(Path(self.test_dir) / "stories" / "another_story")
    
    def test_unbind_session(self):
        self.binder.bind("sess_003", "stories/to_unbind")
        
        success = self.binder.unbind("sess_003")
        
        assert success is True
        assert self.binder.get_binding("sess_003") is None
    
    def test_get_storytree_by_session(self):
        self.binder.bind("sess_004", "stories/find_me")
        
        path = self.binder.get_storytree_by_session("sess_004")
        
        assert path is not None
        assert "find_me" in path
    
    def test_get_session_by_storytree(self):
        self.binder.bind("sess_005", "stories/reverse_lookup")
        
        sid = self.binder.get_session_by_storytree("stories/reverse_lookup")
        
        assert sid == "sess_005"
    
    def test_list_bindings(self):
        for i in range(5):
            self.binder.bind(f"sess_list_{i}", f"stories/list_{i}")
        
        all_bindings = self.binder.list_all_bindings()
        active_only = self.binder.list_all_bindings(active_only=True)
        
        assert len(all_bindings) == 5
        assert len(active_only) == 5
        
        # 解绑一个后，active_only应该减少
        self.binder.unbind("sess_list_0")
        active_after = self.binder.list_all_bindings(active_only=True)
        assert len(active_after) == 4
    
    def test_persistence(self):
        self.binder.bind("sess_persist", "stories/persist_data")
        
        # 创建新实例（模拟重启）
        new_binder = StorySessionBinder(base_dir=self.test_dir)
        
        loaded = new_binder.get_binding("sess_persist")
        
        assert loaded is not None
        assert loaded.is_active is True
    
    def test_create_deletion_plan_with_existing_tree(self):
        self.binder.bind("sess_del", "stories/tree_to_delete")
        
        # 创建假的StoryTree目录
        tree_path = Path(self.test_dir) / "stories" / "tree_to_delete"
        tree_path.mkdir(parents=True, exist_ok=True)
        
        (tree_path / "_story_node.json").write_text('{"title": "测试"}', encoding='utf-8')
        (tree_path / "novel").mkdir(exist_ok=True)
        (tree_path / "novel" / "chap_01.md").write_text("# 第一章\n内容..." * 100, encoding='utf-8')
        
        plan = self.binder.create_deletion_plan("sess_del")
        
        assert plan is not None
        assert plan.session_id == "sess_del"
        assert len(plan.affected_files) >= 1
        assert plan.chapter_count >= 1
        assert len(plan.consequences) > 0
    
    def test_create_deletion_plan_nonexistent(self):
        self.binder.bind("sess_no_tree", "stories/nonexistent")
        
        plan = self.binder.create_deletion_plan("sess_no_tree")
        
        assert plan is not None
        assert plan.total_size_bytes == 0
    
    def test_execute_deletion_with_confirmation(self):
        self.binder.bind("sess_exec", "stories/exec_delete")
        
        tree_path = Path(self.test_dir) / "stories" / "exec_delete"
        tree_path.mkdir(parents=True, exist_ok=True)
        (tree_path / "data.txt").write_text("重要数据", encoding='utf-8')
        
        # 使用确认回调
        confirmed = [False]
        def confirm_callback(plan):
            if plan.total_size_bytes > 0:
                confirmed[0] = True
                return True
            return False
        
        success, msg = self.binder.execute_deletion("sess_exec", confirm_callback)
        
        assert success is True
        assert confirmed[0] is True
        assert not tree_path.exists()  # 目录应被删除
        assert self.binder.get_binding("sess_exec") is None  # 绑定应解除
    
    def test_cancel_deletion(self):
        self.binder.bind("sess_cancel", "stories/cancel_del")
        
        def deny_callback(plan):
            return False  # 用户取消
        
        success, msg = self.binder.execute_deletion("sess_cancel", deny_callback)
        
        assert success is False
        assert "取消" in msg or "cancel" in msg.lower()
        assert self.binder.get_binding("sess_cancel") is not None  # 绑定应保留
    
    def test_migrate_storytree(self):
        self.binder.bind("sess_old", "stories/migrate_me")
        
        success = self.binder.migrate_storytree("sess_old", "sess_new")
        
        assert success is True
        assert self.binder.get_binding("sess_old") is None
        assert self.binder.get_binding("sess_new") is not None


class TestDataCompressor:
    """数据压缩系统测试"""
    
    def setup_method(self):
        self.compressor = DataCompressor(default_level=CompressionLevel.BALANCED)
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_compress_dict(self):
        data = {
            'title': '测试故事',
            'chapters': [{'num': i} for i in range(10)],
            'metadata': {'genre': '科幻'}
        }
        
        compressed = self.compressor.compress_data(data)
        
        assert compressed.original_size > 0
        assert compressed.compressed_size > 0
        assert compressed.algorithm == "zlib"
        assert compressed.checksum_original != ""
    
    def test_compress_and_decompress(self):
        original = {
            'key': 'value',
            'list': [1, 2, 3],
            'nested': {'a': 'b'},
            'text': '大量文本' * 100
        }
        
        compressed = self.compressor.compress_data(original)
        restored = compressed.decompress()
        
        assert restored == original
        assert compressed.savings_percent > 0  # 应该有空间节省
    
    def test_compression_stats(self):
        for i in range(5):
            data = {'index': i, 'data': 'x' * (100 * (i + 1))}
            self.compressor.compress_data(data)

        stats = self.compressor.get_stats_report()

        assert stats['total_files'] == 5
        # overall_ratio 是格式化字符串（如 "85.3%"），验证它不是 "100.0%"
        assert stats['overall_ratio'] != "100.0%"  # 应该有压缩效果
    
    def test_different_compression_levels(self):
        data = {'text': '压缩级别测试' * 50}
        
        fast = self.compressor.compress_data(data, CompressionLevel.FAST)
        balanced = self.compressor.compress_data(data, CompressionLevel.BALANCED)
        maximum = self.compressor.compress_data(data, CompressionLevel.MAXIMUM)
        
        # 最大压缩应该产生最小体积
        assert maximum.compressed_size <= balanced.compressed_size
        assert balanced.compressed_size <= fast.compressed_size
    
    def test_compress_file(self):
        file_path = Path(self.test_dir) / "test.json"
        data = {'large_array': list(range(1000))}
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        success, compressed = self.compressor.compress_file(file_path)
        
        assert success is True
        assert compressed.original_size > 0
        assert (file_path.with_suffix('.compressed')).exists()
        assert (file_path.with_suffix('.meta.json')).exists()
    
    def test_save_and_load_from_disk(self):
        data = {
            'session_id': 'test_session',
            'chapters': [{'num': 1, 'content': '章节内容'}],
            'timestamp': datetime.now().isoformat()
        }
        
        save_path = Path(self.test_dir) / "saved_data"
        
        # 保存
        compressed = self.compressor.save_compressed_to_disk(data, save_path)
        
        # 加载
        loaded = self.compressor.load_from_disk(save_path)
        
        assert loaded['session_id'] == data['session_id']
        assert len(loaded['chapters']) == len(data['chapters'])
    
    def test_optimize_memory_usage(self):
        large_data = {
            'small_key': '小数据',
            'large_key': '大数据' * 5000,  # 约20KB
            'medium_key': ['项'] * 2000
        }
        
        optimized = self.compressor.optimize_memory_usage(large_data, threshold_kb=5)
        
        # 大对象应该被压缩
        assert '__compressed__' in optimized.get('large_key', {})
        # 小对象保持原样
        assert isinstance(optimized['small_key'], str)


class TestKnowledgeBaseManager:
    """研究者资料管理系统测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.kb = KnowledgeBaseManager(base_path=os.path.join(self.test_dir, "knowledge"))
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_add_entry(self):
        entry = self.kb.add_entry(
            title="量子计算基础",
            content="量子比特、叠加态等概念介绍",
            category="science_fiction",
            tags=["量子", "物理"]
        )
        
        assert entry.entry_id.startswith("kb_")
        assert entry.title == "量子计算基础"
        assert entry.category == KnowledgeCategory.SCIENCE_FICTION
        assert "量子" in entry.tags
        
        # 文件应保存到磁盘（使用枚举值sci_fi作为目录名）
        expected_dir = Path(self.test_dir) / "knowledge" / "sci_fi"
        assert expected_dir.exists()
    
    def test_search_knowledge(self):
        self.kb.add_entry("AI伦理", "人工智能的道德问题讨论", "technology", ["AI", "伦理"])
        self.kb.add_entry("机器人三定律", "阿西莫夫的机器人定律", "science_fiction", ["机器人"])
        
        results = self.kb.search_knowledge("AI 机器人")
        
        assert len(results) >= 1
        assert any("AI伦理" in r.title or "机器人" in r.title for r in results)
    
    def test_assess_full_support(self):
        # 添加相关知识
        self.kb.add_entry("科幻小说写作技巧", "如何写好科幻故事", "general", ["科幻", "写作"])
        self.kb.add_entry("未来科技设定", "2050年科技发展预测", "sci_fi", ["科技", "未来"])
        self.kb.add_entry("悬疑情节设计", "如何设计悬念和反转", "mystery", ["悬疑", "推理"])
        
        assessment = self.kb.assess_support(
            story_genre="科幻悬疑",
            story_requirements=["科技设定", "悬疑情节", "角色塑造"]
        )
        
        assert assessment.support_level in [
            SupportLevel.FULL_SUPPORT, 
            SupportLevel.PARTIAL_SUPPORT,
            SupportLevel.MINIMAL_SUPPORT
        ]
        assert assessment.confidence >= 0
        assert isinstance(assessment.to_report(), str)
    
    def test_assess_no_data(self):
        assessment = self.kb.assess_support(
            story_genre="完全不存在的题材",
            story_requirements=["需要完全不存在的内容"]
        )
        
        assert assessment.support_level in [SupportLevel.NO_DATA, SupportLevel.NEEDS_EXPANSION]
    
    def test_category_filtering(self):
        self.kb.add_entry("历史知识1", "古代史内容", "history", ["历史"])
        self.kb.add_entry("科幻知识1", "太空探索", "sci_fi", ["科幻"])
        self.kb.add_entry("科幻知识2", "时间旅行", "sci_fi", ["时间"])
        
        sci_fi_results = self.kb.search_knowledge("", category_filter=KnowledgeCategory.SCIENCE_FICTION)
        
        assert all(e.category == KnowledgeCategory.SCIENCE_FICTION for e in sci_fi_results)
        assert len(sci_fi_results) >= 2
    
    def test_statistics(self):
        self.kb.add_entry("条目1", "内容1", "general")
        self.kb.add_entry("条目2", "内容2", "technology")
        self.kb.add_entry("条目3", "内容3", "mystery")
        
        stats = self.kb.get_statistics()
        
        assert stats['total_entries'] == 3
        assert 'general' in stats['categories']
        assert stats['total_size_kb'] > 0
    
    def test_access_tracking(self):
        entry = self.kb.add_entry("热门条目", "经常被访问的内容", "general")
        
        initial_count = entry.access_count
        
        self.kb.search_knowledge("热门条目")
        self.kb.search_knowledge("热门条目")
        
        updated_entry = self.kb.entries[entry.entry_id]
        
        assert updated_entry.access_count > initial_count
    
    def test_export_for_researcher(self):
        self.kb.add_entry("相关资料1", "关于主题A的研究", "sci_fi", ["主题A"])
        
        assessment = self.kb.assess_support("科幻", ["主题A", "主题B"])
        
        export_config = self.kb.export_for_researcher(assessment)
        
        assert export_config['base_query'] == "科幻"
        assert 'focus_areas' in export_config
        assert 'existing_knowledge' in export_config
        assert export_config['search_strategy'] in ['focused', 'broad']


class TestIntegrationThreeModules:
    """三大模块集成测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        
        self.binder = StorySessionBinder(base_dir=self.test_dir)
        self.compressor = DataCompressor()
        self.kb = KnowledgeBaseManager(base_path=os.path.join(self.test_dir, "kb"))
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_full_workflow(self):
        # 1. 创建会话并绑定StoryTree
        session_id = "integration_sess"
        self.binder.bind(session_id, "stories/integration_story", {"phase": "testing"})

        # 2. 准备研究资料
        self.kb.add_entry("研究资料1", "关于故事背景的知识", "general", ["背景"])

        # 3. 评估支持度
        assessment = self.kb.assess_support("通用", ["背景知识"])

        # 4. 压缩会话数据
        session_data = {
            'session_id': session_id,
            'assessment': assessment.to_report(),
            'knowledge_entries': len(assessment.matched_entries),
            'timestamp': datetime.now().isoformat()
        }

        compressed = self.compressor.save_compressed_to_disk(
            session_data,
            Path(self.test_dir) / "session_backup"
        )

        # 5. 验证所有操作成功
        assert self.binder.get_binding(session_id) is not None
        assert self.kb.get_statistics()['total_entries'] >= 1
        assert compressed.original_size > 0

        # 6. 加载并验证数据完整性
        loaded = self.compressor.load_from_disk(Path(self.test_dir) / "session_backup")
        assert loaded['session_id'] == session_id


def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 WAgent v6.0 核心升级功能测试套件")
    print("=" * 70)
    print(f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    test_classes = [
        ("会话与StoryTree绑定", TestStorySessionBinder),
        ("内存优化与数据压缩", TestDataCompressor),
        ("研究者资料管理", TestKnowledgeBaseManager),
        ("三大模块集成", TestIntegrationThreeModules),
    ]
    
    total = 0
    passed = 0
    failed = 0
    errors = []
    
    for name, cls in test_classes:
        print(f"\n{'─' * 60}")
        print(f"📋 {name}")
        print(f"{'─' * 60}")
        
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        
        ok = 0
        fail = 0
        
        for method_name in methods:
            total += 1
            
            try:
                if hasattr(instance, 'setup_method'):
                    instance.setup_method()
                
                getattr(instance, method_name)()
                passed += 1
                ok += 1
                print(f"  ✅ {method_name}")
                
                if hasattr(instance, 'teardown_method'):
                    instance.teardown_method()
                    
            except Exception as e:
                failed += 1
                fail += 1
                errors.append(f"{name}.{method_name}: {str(e)[:80]}")
                print(f"  ❌ {method_name}")
                
                if hasattr(instance, 'teardown_method'):
                    try:
                        instance.teardown_method()
                    except:
                        pass
        
        print(f"\n   小计: {ok}/{ok+fail}")
    
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"\n总测试数: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    
    if total > 0:
        rate = (passed / total) * 100
        print(f"通过率: {rate:.1f}%")
        
        if rate >= 90:
            print(f"\n🎉🎉🎉 v6.0 核心升级通过! ({rate:.0f}%)\n")
        else:
            print(f"\n⚠️ 存在问题需要修复\n")
    
    if errors:
        print(f"\n错误 ({len(errors)}):")
        for e in errors[:10]:
            print(f"   • {e}")
    
    print("=" * 70)
    
    return passed, failed, total


if __name__ == "__main__":
    p, f, t = run_tests()
    sys.exit(0 if f == 0 else 1)
