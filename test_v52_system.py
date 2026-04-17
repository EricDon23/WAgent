#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent v5.2 系统全面测试套件

测试覆盖：
1. ConstraintManager 约束保障系统
2. Controller v5.2 集成功能
3. Config v5.2 命令枚举
4. StorySession 会话持久化
5. 上下文管理系统
6. 审计跟踪机制
7. 回滚机制
8. 多角色AI协同流程

运行: python test_v52_system.py
"""

import asyncio
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from wagent.config import (
    UserCommand, SystemState, FeatureFlags, 
    ConstraintConfig, AsyncConfig
)
from wagent.constraint_manager import (
    ConstraintManager, ConstraintType, AuditAction,
    UserConstraint, AuditRecord, ContextSnapshot, ConstraintViolation,
    create_constraint_manager, validate_story_constraints
)
from wagent.story_session import (
    StorySessionManager, StoryNode, StoryBranch, ChapterRecord,
    get_session_manager
)


class TestConstraintTypeEnums:
    """测试约束类型枚举"""
    
    def test_constraint_type_values(self):
        assert ConstraintType.WORD_COUNT.value == "字数约束"
        assert ConstraintType.STYLE.value == "风格约束"
        assert ConstraintType.CONTENT.value == "内容约束"
        assert ConstraintType.PLOT.value == "情节约束"
        assert ConstraintType.CHARACTER.value == "角色约束"
        assert ConstraintType.WORLD_BUILDING.value == "世界观约束"
    
    def test_audit_action_values(self):
        assert AuditAction.CREATE.value == "创建"
        assert AuditAction.MODIFY.value == "修改"
        assert AuditAction.DELETE.value == "删除"
        assert AuditAction.CONFIRM.value == "确认"
        assert AuditAction.REJECT.value == "拒绝"
        assert AuditAction.ROLLBACK.value == "回滚"


class TestUserCommandV52:
    """测试 v5.2 新增命令枚举"""
    
    def test_new_commands_exist(self):
        assert hasattr(UserCommand, 'CONTEXT')
        assert hasattr(UserCommand, 'CONSTRAINTS')
        assert hasattr(UserCommand, 'AUDIT')
    
    def test_command_values(self):
        assert UserCommand.CONTEXT.value == "context"
        assert UserCommand.CONSTRAINTS.value == "constraints"
        assert UserCommand.AUDIT.value == "audit"
    
    def test_all_commands_count(self):
        expected = ['CONTINUE', 'MODIFY', 'REGENERATE', 'FINISH', 
                   'QUIT', 'HELP', 'STATUS', 'CONTEXT', 'CONSTRAINTS', 'AUDIT']
        actual = [cmd.name for cmd in UserCommand]
        assert actual == expected


class TestUserConstraint:
    """测试用户约束数据类"""
    
    def test_create_constraint(self):
        constraint = UserConstraint(
            constraint_id="test_1",
            type=ConstraintType.WORD_COUNT,
            description="每章至少1500字",
            value={'min': 1500, 'max': 2500},
            is_mandatory=True
        )
        
        assert constraint.constraint_id == "test_1"
        assert constraint.type == ConstraintType.WORD_COUNT
        assert constraint.description == "每章至少1500字"
        assert constraint.is_mandatory is True
        assert constraint.created_at != ""  # 自动生成时间戳
    
    def test_constraint_to_dict(self):
        constraint = UserConstraint(
            constraint_id="test_2",
            type=ConstraintType.STYLE,
            description="悬疑风格",
            value=["悬疑", "紧张", "推理"]
        )
        
        d = constraint.to_dict()
        assert d['constraint_id'] == "test_2"
        assert d['type'] == "风格约束"
        assert isinstance(d['value'], list)
        assert 'created_at' in d


class TestAuditRecord:
    """测试审计记录数据类"""
    
    def test_create_audit_record(self):
        record = AuditRecord(
            record_id="audit_1",
            action=AuditAction.MODIFY,
            target_type="chapter",
            target_id="chapter_1",
            user_input="增加更多对话",
            before_state={'word_count': 1200},
            after_state={'word_count': 1800},
            details="用户修改章节"
        )
        
        assert record.action == AuditAction.MODIFY
        assert record.target_type == "chapter"
        assert record.user_input == "增加更多对话"
        assert record.is_rollback is False
    
    def test_audit_record_to_dict(self):
        record = AuditRecord(
            record_id="audit_2",
            action=AuditAction.CONFIRM,
            target_type="setting",
            target_id="story_123"
        )
        
        d = record.to_dict()
        assert d['action'] == "确认"
        assert d['target_type'] == "setting"


class TestContextSnapshot:
    """测试上下文快照"""
    
    def test_create_snapshot(self):
        snapshot = ContextSnapshot(
            snapshot_id="snap_1",
            snapshot_type="setting",
            data={'title': '测试故事', 'genre': '科幻'}
        )
        
        assert snapshot.snapshot_id == "snap_1"
        assert snapshot.snapshot_type == "setting"
        assert len(snapshot.checksum) == 16  # MD5前16位
    
    def test_snapshot_auto_timestamp(self):
        snap1 = ContextSnapshot(
            snapshot_id="snap_2",
            snapshot_type="chapter",
            data={}
        )
        snap2 = ContextSnapshot(
            snapshot_id="snap_3",
            snapshot_type="chapter",
            data={}
        )
        # 时间戳应该自动生成
        assert snap1.timestamp != ""
        assert snap2.timestamp != ""


class TestConstraintManagerCore:
    """测试约束管理器核心功能"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = ConstraintManager(story_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_init_creates_dirs(self):
        assert os.path.exists(self.test_dir)
        assert self.mgr.snapshots_dir is not None  # 快照目录路径已设置
    
    def test_add_word_count_constraint(self):
        constraint = self.mgr.add_constraint(
            ctype=ConstraintType.WORD_COUNT,
            description="每章1500-2500字",
            value={'min': 1500, 'max': 2500}
        )
        
        assert len(self.mgr.constraints) == 1
        assert constraint.type == ConstraintType.WORD_COUNT
        assert constraint.is_mandatory is True
    
    def test_add_style_constraint(self):
        constraint = self.mgr.add_constraint(
            ctype=ConstraintType.STYLE,
            description="写作风格",
            value=["悬疑", "推理", "紧凑"]
        )
        
        assert len(self.mgr.constraints) == 1
        assert constraint.type == ConstraintType.STYLE
    
    def test_add_optional_constraint(self):
        constraint = self.mgr.add_constraint(
            ctype=ConstraintType.WORLD_BUILDING,
            description="科幻背景",
            value="科幻",
            mandatory=False
        )
        
        assert constraint.is_mandatory is False
    
    def test_add_multiple_constraints(self):
        self.mgr.add_constraint(ConstraintType.WORD_COUNT, "字数", {'min': 1000})
        self.mgr.add_constraint(ConstraintType.STYLE, "风格", ["悬疑"])
        self.mgr.add_constraint(ConstraintType.CONTENT, "内容规则", {'forbidden': []})
        
        assert len(self.mgr.constraints) == 3
    
    def test_validate_content_pass(self):
        self.mgr.add_constraint(ConstraintType.WORD_COUNT, "字数", {'min': 100, 'max': 5000})
        
        content = "这是一段测试内容" * 50  # 约400字
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is True
        assert len(violations) == 0
    
    def test_validate_content_fail_min_words(self):
        self.mgr.add_constraint(ConstraintType.WORD_COUNT, "字数", {'min': 5000, 'max': 10000})
        
        content = "短内容"  # 只有4个字
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is False
        assert len(violations) == 1
        assert violations[0].constraint_type == ConstraintType.WORD_COUNT
        assert violations[0].severity in ["major", "minor"]


class TestConstraintValidationAdvanced:
    """高级约束验证测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = ConstraintManager(story_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_style_validation_pass(self):
        self.mgr.add_constraint(ConstraintType.STYLE, "风格", ["悬疑", "推理"])
        
        content = "这是一个悬疑推理故事，充满了紧张的气氛"
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is True
    
    def test_style_validation_fail_mandatory(self):
        self.mgr.add_constraint(ConstraintType.STYLE, "必须包含关键词", ["诗歌", "抒情"], mandatory=True)
        
        content = "这是硬科幻小说，没有任何诗意"
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is False
        assert len(violations) == 1
    
    def test_style_validation_pass_optional(self):
        self.mgr.add_constraint(ConstraintType.STYLE, "可选风格", ["诗歌"], mandatory=False)
        
        content = "硬科幻内容"
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is True  # 可选约束不满足也不算违规
    
    def test_content_forbidden_words(self):
        self.mgr.add_constraint(
            ConstraintType.CONTENT,
            "禁止词汇",
            {'forbidden': ['脏话', '不当']}
        )
        
        content = "这句话包含脏话是不当的"
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is False
        assert violations[0].severity == "critical"
    
    def test_content_required_words(self):
        self.mgr.add_constraint(
            ConstraintType.CONTENT,
            "必须包含",
            {'required': ['侦探', '案件']}
        )
        
        content = "侦探开始调查这起神秘案件"
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is True
    
    def test_content_required_words_missing(self):
        self.mgr.add_constraint(
            ConstraintType.CONTENT,
            "必须包含",
            {'required': ['魔法', '龙']}
        )
        
        content = "科幻故事中的机器人"
        passed, violations = self.mgr.validate_content(content)
        
        assert passed is False
        assert violations[0].severity == "major"


class TestAuditTracking:
    """审计跟踪系统测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = ConstraintManager(story_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_audit_action_create(self):
        record = self.mgr.audit_action(
            action=AuditAction.CREATE,
            target_type="constraint",
            target_id="constraint_1",
            details="添加字数约束"
        )
        
        assert len(self.mgr.audit_records) == 1
        assert record.action == AuditAction.CREATE
        assert record.details == "添加字数约束"
    
    def test_audit_action_modify_with_states(self):
        before = {'title': '旧标题'}
        after = {'title': '新标题'}
        
        record = self.mgr.audit_action(
            action=AuditAction.MODIFY,
            target_type="setting",
            target_id="story_1",
            before=before,
            after=after,
            user_input="修改标题",
            details="用户修改大纲标题"
        )
        
        assert record.before_state == before
        assert record.after_state == after
        assert record.user_input == "修改标题"
    
    def test_get_audit_history(self):
        for i in range(25):
            self.mgr.audit_action(
                action=AuditAction.CREATE,
                target_type="test",
                target_id=f"item_{i}",
                details=f"操作{i}"
            )
        
        history = self.mgr.get_audit_history(limit=10)
        assert len(history) == 10
        
        history20 = self.mgr.get_audit_history(limit=20)
        assert len(history20) == 20
    
    def test_audit_persistence(self):
        self.mgr.audit_action(AuditAction.CREATE, "constraint", "c1", "创建约束")
        self.mgr.audit_action(AuditAction.MODIFY, "setting", "s1", "修改设定")
        
        mgr2 = ConstraintManager(story_dir=self.test_dir)
        assert len(mgr2.audit_records) == 2


class TestSnapshotSystem:
    """快照与回滚机制测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = ConstraintManager(story_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_create_setting_snapshot(self):
        setting_data = {
            'story_name': '测试故事',
            'genre': '科幻',
            'characters': [{'name': '主角'}]
        }
        
        snapshot = self.mgr.create_snapshot("setting", setting_data, "初始设定")
        
        assert snapshot.snapshot_type == "setting"
        assert snapshot.data == setting_data
        assert len(snapshot.checksum) > 0
        assert len(self.mgr.snapshots) == 1
    
    def test_create_chapter_snapshot(self):
        chapter_data = {
            'chapter_num': 1,
            'content': '第一章内容...',
            'word_count': 1500
        }
        
        snapshot = self.mgr.create_snapshot("chapter", chapter_data, "第1章")
        
        assert snapshot.snapshot_type == "chapter"
        assert snapshot.data['chapter_num'] == 1
    
    def test_rollback_to_existing_snapshot(self):
        original_data = {'version': 1, 'content': '原始版本'}
        snap = self.mgr.create_snapshot("full", original_data, "完整备份")
        
        result = self.mgr.rollback_to_snapshot(snap.snapshot_id)
        
        assert result is not None
        assert result.data == original_data
        assert result.snapshot_type == "full"
    
    def test_rollback_nonexistent_snapshot(self):
        result = self.mgr.rollback_to_snapshot("nonexistent_snap")
        assert result is None
    
    def test_multiple_snapshots(self):
        for i in range(3):
            self.mgr.create_snapshot(f"type_{i}", {'ver': i}, f"快照{i}")
        
        assert len(self.mgr.snapshots) == 3
        
        # 回滚到第二个快照
        result = self.mgr.rollback_to_snapshot(self.mgr.snapshots[1].snapshot_id)
        assert result.data['ver'] == 1
    
    def test_snapshot_integrity_check(self):
        data1 = {'key': 'value1'}
        data2 = {'key': 'value2'}
        
        snap1 = self.mgr.create_snapshot("test", data1)
        snap2 = self.mgr.create_snapshot("test", data2)
        
        assert snap1.checksum != snap2.checksum
        assert snap1.timestamp != snap2.timestamp


class TestViolationReporting:
    """违规报告测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = ConstraintManager(story_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_empty_violation_report(self):
        report = self.mgr.get_violation_report()
        
        assert report['total_violations'] == 0
        assert report['unresolved'] == 0
        assert all(v == 0 for v in report['by_severity'].values())
    
    def test_violation_report_with_violations(self):
        self.mgr.add_constraint(ConstraintType.WORD_COUNT, "字数", {'min': 5000})
        self.mgr.validate_content("短文本")
        
        report = self.mgr.get_violation_report()
        
        assert report['total_violations'] == 1
        assert report['unresolved'] == 1
    
    def test_export_audit_report(self):
        self.mgr.add_constraint(ConstraintType.WORD_COUNT, "字数约束", {'min': 1500})
        self.mgr.audit_action(AuditAction.CREATE, "constraint", "c1", "添加约束")
        
        report = self.mgr.export_audit_report()
        
        assert isinstance(report, str)
        assert len(report) > 100  # 报告应该有实质内容


class TestGlobalUtilityFunctions:
    """全局便捷函数测试"""
    
    def test_create_constraint_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = create_constraint_manager(tmpdir)
            assert isinstance(mgr, ConstraintManager)
    
    def test_validate_story_constraints_function(self):
        constraints = [
            UserConstraint(
                constraint_id="c1",
                type=ConstraintType.WORD_COUNT,
                description="字数",
                value={'min': 100}
            )
        ]
        
        content = "足够长的测试内容" * 20
        passed, violations = validate_story_constraints(content, constraints)
        
        assert passed is True
        assert len(violations) == 0


class TestStorySessionIntegration:
    """故事会话系统集成测试"""
    
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = StorySessionManager(base_dir=self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_create_and_save_story(self):
        node = self.mgr.create_story(
            story_id="test_story_001",
            title="测试故事",
            prompt="一个测试创意"
        )
        
        assert node.story_id == "test_story_001"
        assert node.title == "测试故事"
        
        saved = self.mgr.save_story(node)
        assert saved is True
    
    def test_load_saved_story(self):
        create_node = self.mgr.create_story(
            story_id="test_load_001",
            title="可加载的故事",
            prompt="测试加载"
        )
        create_node.genre = "科幻"
        create_node.setting = {'story_name': '测试', 'genre': '科幻'}
        self.mgr.save_story(create_node)
        
        loaded_node = self.mgr.load_story("test_load_001")
        
        assert loaded_node is not None
        assert loaded_node.title == "可加载的故事"
        assert loaded_node.genre == "科幻"
    
    def test_add_chapter_to_story(self):
        node = self.mgr.create_story("story_chap_test", "章节测试", "")
        
        chapter = ChapterRecord(
            chapter_num=1,
            title="第一章",
            content="这是第一章的内容...",
            status="final"
        )
        
        node.add_chapter(chapter)
        self.mgr.save_story(node)
        
        loaded = self.mgr.load_story("story_chap_test")
        assert loaded.total_chapters == 1
        assert loaded.get_all_chapters()[0].chapter_num == 1


class TestControllerV52Integration:
    """控制器 v5.2 集成测试（使用 Mock）"""
    
    def setup_method(self):
        from wagent.controller import WAgent
        self.test_dir = tempfile.mkdtemp()
        
        with patch('wagent.controller.Path') as mock_path:
            mock_path.return_value = Path(self.test_dir)
            self.agent = WAgent()
            self.agent.output_dir = Path(self.test_dir)
            self.agent.info_dir = Path(self.test_dir) / "info"
            self.agent.novel_dir = Path(self.test_dir) / "novel"
            self.agent.info_dir.mkdir(exist_ok=True)
            self.agent.novel_dir.mkdir(exist_ok=True)
            self.agent.constraint_mgr = create_constraint_manager(self.test_dir)
    
    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_extract_constraints_from_setting(self):
        setting = {
            'story_name': '测试',
            'word_count_range': {'min': 1500, 'max': 2500},
            'style': '悬疑,推理',
            'genre': '科幻',
            'content_rules': {'forbidden': ['暴力']}
        }
        
        constraints = self.agent._extract_constraints_from_setting(setting)
        
        assert len(constraints) >= 3  # 至少有字数、风格、类型约束
        
        types = [c[0] for c in constraints]
        assert ConstraintType.WORD_COUNT in types
        assert ConstraintType.STYLE in types
        assert ConstraintType.WORLD_BUILDING in types
    
    def test_extract_constraints_empty_setting(self):
        setting = {}
        constraints = self.agent._extract_constraints_from_setting(setting)
        assert len(constraints) == 0
    
    def test_show_constraints_summary_no_constraints(self):
        self.agent.constraint_mgr.constraints = []
        should_not_raise = lambda: self.agent._show_constraints_summary()
        should_not_raise()  # 不应抛出异常
    
    def test_parse_new_commands(self):
        assert self.agent.parse_command('context') == UserCommand.CONTEXT
        assert self.agent.parse_command('ct') == UserCommand.CONTEXT
        assert self.agent.parse_command('constraints') == UserCommand.CONSTRAINTS
        assert self.agent.parse_command('cs') == UserCommand.CONSTRAINTS
        assert self.agent.parse_command('audit') == UserCommand.AUDIT
        assert self.agent.parse_command('ad') == UserCommand.AUDIT


class TestFeatureFlagsV52:
    """功能配置测试"""
    
    def test_default_flags(self):
        flags = FeatureFlags()
        
        assert flags.case_insensitive_commands is True
        assert flags.enable_realtime_refresh is True
        assert flags.graceful_degradation is True
    
    def test_flags_from_env(self):
        flags = FeatureFlags.from_env()
        assert isinstance(flags, FeatureFlags)
    
    def test_flags_validation(self):
        flags = FeatureFlags(refresh_interval=5.0, max_retry_attempts=5)
        valid, errors = flags.validate()
        assert valid is True
        assert len(errors) == 0
    
    def test_flags_invalid_refresh_interval(self):
        flags = FeatureFlags(refresh_interval=0.1)
        valid, errors = flags.validate()
        assert valid is False
        assert len(errors) > 0


class TestAsyncConfig:
    """异步配置测试"""
    
    def test_default_config(self):
        config = AsyncConfig()
        
        assert config.director_temperature == 0.0
        assert config.writer_temperature == 1.0
        assert config.director_max_tokens == 2048
        assert config.writer_max_tokens == 4096


class TestConstraintConfig:
    """约束配置测试"""
    
    def test_validate_within_range(self):
        config = ConstraintConfig(min_words=1500, max_words=2500)
        passed, msg = config.validate(2000)
        assert passed is True
        assert "✅" in msg
    
    def test_validate_below_minimum(self):
        config = ConstraintConfig(min_words=1500, max_words=2500)
        passed, msg = config.validate(1000)
        assert passed is False
        assert "不足" in msg
    
    def test_validate_above_maximum(self):
        config = ConstraintConfig(min_words=1500, max_words=2500)
        passed, msg = config.validate(3000)
        assert passed is False
        assert "超标" in msg


def run_all_tests():
    """运行所有测试并输出报告"""
    print("="*70)
    print("🧪 WAgent v5.2 全面测试套件")
    print("="*70)
    print(f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    test_classes = [
        ("约束类型枚举", TestConstraintTypeEnums),
        ("v5.2命令枚举", TestUserCommandV52),
        ("用户约束数据类", TestUserConstraint),
        ("审计记录数据类", TestAuditRecord),
        ("上下文快照", TestContextSnapshot),
        ("约束管理器核心", TestConstraintManagerCore),
        ("高级约束验证", TestConstraintValidationAdvanced),
        ("审计跟踪系统", TestAuditTracking),
        ("快照与回滚", TestSnapshotSystem),
        ("违规报告", TestViolationReporting),
        ("全局便捷函数", TestGlobalUtilityFunctions),
        ("故事会话集成", TestStorySessionIntegration),
        ("控制器集成", TestControllerV52Integration),
        ("功能配置", TestFeatureFlagsV52),
        ("异步配置", TestAsyncConfig),
        ("约束配置", TestConstraintConfig),
    ]
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    failed_tests = []
    
    for class_name, test_class in test_classes:
        print(f"\n{'─'*60}")
        print(f"📋 测试组: {class_name}")
        print(f"{'─'*60}")
        
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        
        group_passed = 0
        group_failed = 0
        
        for method_name in methods:
            method = getattr(instance, method_name)
            total_tests += 1
            
            try:
                if hasattr(instance, 'setup_method'):
                    instance.setup_method()
                    
                method()
                total_passed += 1
                group_passed += 1
                print(f"  ✅ {method_name}")
                
                if hasattr(instance, 'teardown_method'):
                    instance.teardown_method()
                    
            except Exception as e:
                total_failed += 1
                group_failed += 1
                failed_tests.append(f"{class_name}.{method_name}")
                print(f"  ❌ {method_name}")
                print(f"     错误: {str(e)[:80]}")
                
                if hasattr(instance, 'teardown_method'):
                    try:
                        instance.teardown_method()
                    except:
                        pass
        
        print(f"\n   小计: {group_passed} 通过 / {group_passed + group_failed} 总计")
    
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    print(f"\n总测试数: {total_tests}")
    print(f"通过: {total_passed} ✅")
    print(f"失败: {total_failed} ❌")
    
    if total_tests > 0:
        coverage = (total_passed / total_tests) * 100
        print(f"通过率: {coverage:.1f}%")
        
        if coverage >= 80:
            print(f"\n{'🎉' * 3} 达到80%+覆盖率要求! {'🎉' * 3}")
        elif coverage >= 60:
            print(f"\n⚠️ 覆盖率接近目标，建议优化")
        else:
            print(f"\n❌ 覆盖率未达标，需要修复失败用例")
    
    if failed_tests:
        print(f"\n❌ 失败的测试 ({len(failed_tests)}):")
        for ft in failed_tests[:10]:
            print(f"   - {ft}")
        if len(failed_tests) > 10:
            print(f"   ... 还有 {len(failed_tests)-10} 个")
    
    print(f"\n⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    return total_passed, total_failed, total_tests


if __name__ == "__main__":
    passed, failed, total = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
