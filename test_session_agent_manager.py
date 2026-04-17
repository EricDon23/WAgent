#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent SessionAgentManager 测试套件

测试覆盖：
1. 会话创建与实例绑定（1:1映射）
2. 生命周期管理（创建→运行→暂停→恢复→停止→销毁）
3. 数据隔离验证（会话间独立性）
4. 持久化存储与恢复
5. 故事绑定与查询
6. 销毁确认机制
7. 统计信息准确性
"""

import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from wagent.stories_manager import (
    SessionAgentManager,
    AgentInstance,
    SessionConfig,
    SessionState,
    create_session_manager
)


class TestSessionAgentManager:
    """会话-WAgent实例管理核心测试"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = SessionAgentManager(base_dir=self.test_dir)

    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_create_single_session(self):
        """测试创建单个会话"""
        instance = self.manager.create_session(
            session_id="sess_001",
            story_id="story_test"
        )

        assert instance is not None
        assert instance.session_id == "sess_001"
        assert instance.state == SessionState.CREATED
        assert instance.instance_id.startswith("agent_")
        print(f"   ✅ 创建成功: {instance.instance_id}")

    def test_duplicate_session_rejected(self):
        """拒绝重复会话ID"""
        self.manager.create_session("sess_dup")

        try:
            self.manager.create_session("sess_dup")
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "已存在" in str(e)
            print(f"   ✅ 正确拒绝重复ID")

    def test_start_agent_instance(self):
        """启动Agent实例"""
        self.manager.create_session("sess_002", "story_abc")
        success, msg = self.manager.start_agent(
            "sess_002",
            story_path="stories/story_abc"
        )

        assert success is True
        instance = self.manager.get_instance("sess_002")
        assert instance.state == SessionState.RUNNING
        assert instance.bound_story_path == "stories/story_abc"
        print(f"   ✅ 启动成功: {msg}")

    def test_pause_and_resume(self):
        """暂停与恢复Agent"""
        self.manager.create_session("sess_003")
        self.manager.start_agent("sess_003")

        # 暂停
        success, msg = self.manager.pause_agent("sess_003")
        assert success
        assert self.manager.get_instance("sess_003").state == SessionState.PAUSED

        # 恢复
        success, msg = self.manager.resume_agent("sess_003")
        assert success
        assert self.manager.get_instance("sess_003").state == SessionState.RUNNING
        print(f"   ✅ 暂停/恢复循环正常")

    def test_stop_agent_force(self):
        """强制停止Agent"""
        self.manager.create_session("sess_004")
        self.manager.start_agent("sess_004")

        success, msg = self.manager.stop_agent("sess_004", force=True)
        assert success
        assert self.manager.get_instance("sess_004").state == SessionState.STOPPED
        print(f"   ✅ 强制停止成功")

    def test_destroy_with_confirmation(self):
        """销毁会话（带确认回调）"""
        self.manager.create_session("sess_005")
        self.manager.start_agent("sess_005")

        confirmed = [False]

        def confirm_callback(plan):
            print(f"   📋 销毁计划: {plan['consequences'][:2]}")
            confirmed[0] = True
            return True  # 用户确认

        success, msg = self.manager.destroy_session(
            "sess_005",
            confirm_callback=confirm_callback
        )

        assert success
        assert confirmed[0]
        assert self.manager.get_instance("sess_005") is None
        print(f"   ✅ 销毁成功: {msg}")

    def test_destroy_cancelled_by_user(self):
        """用户取消销毁操作"""
        self.manager.create_session("sess_006")

        def deny_callback(plan):
            return False  # 用户取消

        success, msg = self.manager.destroy_session(
            "sess_006",
            confirm_callback=deny_callback
        )

        assert not success
        assert "取消" in msg
        assert self.manager.get_instance("sess_006") is not None  # 会话仍然存在
        print(f"   ✅ 用户取消生效: {msg}")


class TestDataIsolation:
    """数据隔离性测试 - 确保会话间完全独立"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = SessionAgentManager(base_dir=self.test_dir)

        # 创建3个独立会话
        for i in range(3):
            sess_id = f"iso_sess_{i}"
            self.manager.create_session(sess_id, f"story_{i}")
            self.manager.start_agent(sess_id, f"stories/story_{i}")

    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_independent_state(self):
        """各会话状态完全独立"""
        inst0 = self.manager.get_instance("iso_sess_0")
        inst1 = self.manager.get_instance("iso_sess_1")

        # 更新inst0的统计
        self.manager.update_instance_stats(
            "iso_sess_0",
            words_generated=1000,
            chapter=2,
            memory_usage=50.5
        )

        # inst1不应受影响
        assert inst0.total_words_generated == 1000
        assert inst1.total_words_generated == 0
        assert inst0.memory_usage_mb == 50.5
        assert inst1.memory_usage_mb == 0.0
        print(f"   ✅ 状态隔离验证通过")

    def test_story_binding_isolation(self):
        """故事绑定互不干扰"""
        # 每个会话绑定不同故事（与setup_method一致）
        for i in range(3):
            session_id = f"iso_sess_{i}"
            story_path = f"stories/story_{i}"  # 与setup_method一致

            # 确认每个会话只绑定自己的故事
            found_session = self.manager.get_session_by_story(story_path)
            assert found_session == session_id, \
                f"故事{story_path}应绑定到{session_id}，实际是{found_session}"

        print(f"   ✅ 故事绑定隔离验证通过")

    def test_conversation_history_isolation(self):
        """对话历史隔离"""
        inst0 = self.manager.get_instance("iso_sess_0")
        inst1 = self.manager.get_instance("iso_sess_1")

        # 向inst0添加对话
        inst0.conversation_history.append({
            'role': 'user',
            'content': '这是会话0的输入'
        })

        # inst1不应有这条记录
        assert len(inst0.conversation_history) == 1
        assert len(inst1.conversation_history) == 0
        print(f"   ✅ 对话历史隔离验证通过")


class TestPersistenceAndRecovery:
    """持久化存储与恢复测试"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_sessions_persisted_to_disk(self):
        """会话数据持久化到磁盘"""
        manager1 = SessionAgentManager(base_dir=self.test_dir)
        manager1.create_session("persist_001", "story_a")
        manager1.start_agent("persist_001", "stories/story_a")
        manager1.update_instance_stats("persist_001", words_generated=500)

        sessions_file = Path(self.test_dir) / "_sessions_registry.json"

        # 详细诊断
        assert self.test_dir and Path(self.test_dir).exists(), \
            f"测试目录不存在: {self.test_dir}"
        assert sessions_file.exists(), \
            f"注册表文件应存在: {sessions_file}, 目录内容: {list(Path(self.test_dir).iterdir())}"

        with open(sessions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert "persist_001" in data, f"会话persist_001不在数据中: {list(data.keys())}"
        assert data['persist_001']['total_words_generated'] == 500
        print(f"   ✅ 持久化成功，文件大小: {sessions_file.stat().st_size} bytes")

    def test_recovery_after_restart(self):
        """程序重启后恢复会话"""
        # 第一次启动：创建并配置会话
        manager1 = SessionAgentManager(base_dir=self.test_dir)
        manager1.create_session("recovery_001", "story_b")
        manager1.start_agent("recovery_001", "stories/story_b")
        del manager1  # 模拟程序关闭

        # 第二次启动：从磁盘恢复
        manager2 = SessionAgentManager(base_dir=self.test_dir)
        recovered = manager2.get_instance("recovery_001")

        assert recovered is not None, "应能恢复会话"
        assert recovered.session_id == "recovery_001"
        assert recovered.bound_story_path == "stories/story_b"
        print(f"   ✅ 恢复成功: 实例ID={recovered.instance_id}, 状态={recovered.state.value}")

    def test_export_import_functionality(self):
        """导出与导入功能"""
        manager = SessionAgentManager(base_dir=self.test_dir)
        manager.create_session("export_001")
        manager.start_agent("export_001", "stories/export_test")
        manager.update_instance_stats("export_001", words_generated=2000, chapter=5)

        export_dir = Path(self.test_dir) / "exports"
        exported = manager.export_session_data("export_001", export_dir)

        assert exported is not None
        assert exported.exists()

        with open(exported, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data['session_id'] == "export_001"
        assert data['total_words_generated'] == 2000
        assert 'version' in data
        print(f"   ✅ 导出成功: {exported.name}")


class TestStatisticsAndReporting:
    """统计信息和报告功能测试"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = SessionAgentManager(base_dir=self.test_dir)

    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_statistics_accuracy(self):
        """统计信息准确"""
        for i in range(5):
            self.manager.create_session(f"stat_{i}", f"story_{i}")
            if i < 3:
                self.manager.start_agent(f"stat_{i}")

        stats = self.manager.get_statistics()

        assert stats['total_created'] == 5
        assert stats['active_count'] >= 3
        assert stats['total_instances'] == 5
        assert 'states_distribution' in stats
        print(f"   统计: 创建={stats['total_created']}, 活跃={stats['active_count']}")

    def test_list_all_sessions(self):
        """列出所有会话"""
        for i in range(4):
            sid = f"list_{i}"
            self.manager.create_session(sid)
            if i % 2 == 0:
                self.manager.start_agent(sid)

        all_sessions = self.manager.list_all_sessions(active_only=False)
        active_only = self.manager.list_all_sessions(active_only=True)

        assert len(all_sessions) >= len(active_only)
        assert len(all_sessions) == 4
        print(f"   全部={len(all_sessions)}, 活跃={len(active_only)}")


def run_tests():
    """运行所有SessionAgentManager测试"""
    print("=" * 70)
    print("🧪 WAgent SessionAgentManager 测试套件")
    print("=" * 70)
    print(f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    test_classes = [
        ("会话管理核心功能", TestSessionAgentManager),
        ("数据隔离性验证", TestDataIsolation),
        ("持久化与恢复", TestPersistenceAndRecovery),
        ("统计与报告", TestStatisticsAndReporting),
    ]

    total = passed = failed = 0
    errors = []

    for name, cls in test_classes:
        print(f"\n{'─' * 60}")
        print(f"📋 {name}")
        print(f"{'─' * 60}")

        instance = cls()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        ok = fail = 0

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
                errors.append(f"{name}.{method_name}: {str(e)[:100]}")
                print(f"  ❌ {method_name}: {str(e)[:80]}")

                if hasattr(instance, 'teardown_method'):
                    try:
                        instance.teardown_method()
                    except:
                        pass

        print(f"\n   小计: {ok}/{ok+fail}")

    print("\n" + "=" * 70)
    print("📊 SessionAgentManager 测试结果汇总")
    print("=" * 70)
    print(f"\n总测试数: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")

    if total > 0:
        rate = (passed / total) * 100
        print(f"通过率: {rate:.1f}%")

        if rate >= 95:
            print(f"\n🎉🎉🎉 SessionAgentManager 全部核心功能通过! ({rate:.0f}%)\n")
        elif rate >= 80:
            print(f"\n✨ SessionAgentManager 基本功能正常! ({rate:.0f}%)\n")
        else:
            print(f"\n⚠️ 存在问题需要修复\n")

    if errors:
        print(f"\n错误 ({len(errors)}):")
        for e in errors:
            print(f"   • {e}")

    print("=" * 70)

    return passed, failed, total


if __name__ == "__main__":
    p, f, t = run_tests()
    sys.exit(0 if f == 0 else 1)
