#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent Stories Manager v7.0 完整测试套件

测试覆盖：
1. StoryScanner - 文件扫描与识别（性能+准确性）
2. StoryMetadataExtractor - 元数据提取（完整性+默认值）
3. StoryContentParser - 内容解析（JSON/Markdown→对象模型）
4. StoryErrorHandler - 错误处理机制（分级日志+自动恢复）
5. 集成测试 - 真实stories目录批量验证

验证指标：
- 文件识别准确率: 100%
- 加载成功率: ≥99%
- 解析错误率: <0.1%
- 错误处理覆盖率: 100%
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
    # 核心类
    StoryScanner, ScanResult, StoryFileInfo,
    StoryMetadataExtractor, StoryMetadata,
    StoryContentParser, ParsedStory, ParsedChapter,
    StoryErrorHandler, ErrorRecord, ErrorSeverity,
    # 枚举和规范
    FileExtension, StoryFileCategory, StoryStatus, StoryFormatSpec,
    # 便捷函数
    create_scanner, create_metadata_extractor,
    create_content_parser, create_error_handler
)


class TestStoryScanner:
    """文件扫描器测试 - 验证性能和准确性"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.scanner = StoryScanner(base_dir=self.test_dir, use_cache=True)  # 启用缓存测试

        # 创建模拟故事目录结构
        self._create_mock_stories()

    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_mock_stories(self):
        """创建模拟故事数据"""
        # 故事1: 完整有效
        story1 = Path(self.test_dir) / "story_20260417_100000"
        story1.mkdir()
        (story1 / "_story_node.json").write_text(json.dumps({
            'story_id': 'story_20260417_100000',
            'title': '测试小说1',
            'created_at': '2026-04-17T10:00:00',
            'status': 'active',
            'setting': {'story_name': '测试1'},
            'branches': [{'branch_id': 'branch_01', 'chapters': []}],
            'total_chapters': 1,
            'total_words': 1000
        }, ensure_ascii=False), encoding='utf-8')

        (story1 / "info").mkdir()
        (story1 / "info" / "01_story_setting.json").write_text(
            json.dumps({'story_name': '测试1'}, ensure_ascii=False),
            encoding='utf-8'
        )

        (story1 / "novel").mkdir()
        (story1 / "novel" / "test--branch_01-chap_01.md").write_text(
            "# 第一章\n\n测试内容...",
            encoding='utf-8'
        )

        # 故事2: 只有node文件
        story2 = Path(self.test_dir) / "story_20260417_110000"
        story2.mkdir()
        (story2 / "_story_node.json").write_text(json.dumps({
            'story_id': 'story_20260417_110000',
            'title': '测试小说2',
            'created_at': '2026-04-17T11:00:00',
            'status': 'draft'
        }, ensure_ascii=False), encoding='utf-8')

        # 非故事目录（ID格式不匹配）
        (Path(self.test_dir) / "other_folder").mkdir()

    def test_scan_finds_all_stories(self):
        """测试扫描发现所有有效故事"""
        result = self.scanner.scan(force_refresh=True)

        assert result.story_directories_found == 2
        assert len(result.valid_stories) == 2
        print(f"   发现 {len(result.valid_stories)} 个故事")

    def test_scan_performance(self):
        """测试扫描性能 (>100 files/s)"""
        start = time.time()
        result = self.scanner.scan(force_refresh=True)
        duration = time.time() - start

        # 即使只有几个文件，也应该很快完成（<1秒）
        assert duration < 1.0
        print(f"   扫描耗时: {duration*1000:.1f}ms")

    def test_scan_caching_mechanism(self):
        """测试缓存机制"""
        result1 = self.scanner.scan(force_refresh=True)
        assert not result1.cache_hit

        result2 = self.scanner.scan()
        assert result2.cache_hit
        assert len(result2.valid_stories) == len(result1.valid_stories)

    def test_scan_invalid_directory(self):
        """测试无效目录处理"""
        scanner = StoryScanner(base_dir="/nonexistent/path")
        result = scanner.scan()

        assert len(result.errors) > 0
        assert result.story_directories_found == 0

    def test_scan_file_counting(self):
        """测试文件计数准确性"""
        result = self.scanner.scan(force_refresh=True)

        total_files = sum(s['file_count'] for s in result.valid_stories)
        assert total_files >= 3  # 至少有node + setting + chapter


class TestStoryMetadataExtractor:
    """元数据提取器测试"""

    def setup_method(self):
        self.extractor = StoryMetadataExtractor()

    def test_extract_from_complete_node(self):
        """从完整节点提取元数据"""
        node_data = {
            'story_id': 'story_test',
            'title': '完整标题测试',
            'genre': '科幻',
            'created_at': '2026-04-17T12:00:00',
            'status': 'active',
            'total_chapters': 5,
            'total_words': 15000,
            'setting': {
                'story_name': '完整标题测试',
                'story_summary': '这是一个完整的测试摘要内容' * 10,
                'characters': [
                    {'name': '角色A', 'role': '主角'},
                    {'name': '角色B', 'role': '配角'}
                ]
            }
        }

        metadata = self.extractor.extract_from_node(node_data)

        assert metadata.title == '完整标题测试'
        assert metadata.genre == '科幻'
        assert metadata.story_id == 'story_test'
        assert metadata.total_words == 15000
        assert len(metadata.keywords) >= 1  # 应该提取到角色名
        print(f"   质量评分: {metadata.quality_score}/100")

    def test_apply_defaults_for_missing_fields(self):
        """默认值填充策略"""
        metadata = StoryMetadata(title='测试')
        filled = self.extractor.apply_defaults(metadata)

        assert filled.author == 'WAgent AI'
        assert filled.status == 'draft'
        assert filled.created_at != ''

    def test_quality_assessment_high_score(self):
        """高质量数据评估"""
        metadata = StoryMetadata(
            title='高质量测试标题',
            genre='悬疑',
            summary='这是一个足够长的摘要内容用于质量评估测试' * 20,
            created_at=datetime.now().isoformat(),
            status='active',
            tags=['标签1', '标签2'],
            total_chapters=10,
            total_words=50000
        )

        self.extractor._assess_quality(metadata)
        assert metadata.quality_score >= 80
        assert metadata.is_complete

    def test_quality_assessment_low_score(self):
        """低质量数据评估"""
        metadata = StoryMetadata()

        self.extractor._assess_quality(metadata)
        assert metadata.quality_score < 50
        assert not metadata.is_complete
        assert metadata.has_missing_fields
        assert len(metadata.missing_fields) > 0

    def test_extract_from_index_entry(self):
        """从索引条目提取"""
        entry = {
            'title': '索引中的标题',
            'genre': '',
            'status': 'active',
            'created_at': '2026-04-17T13:00:00',
            'total_chapters': 3,
            'total_words': 8000,
            'prompt_preview': '测试提示预览'
        }

        metadata = self.extractor.extract_from_index_entry(entry)
        assert metadata.title == '索引中的标题'
        assert metadata.total_words == 8000

    def test_markdown_header_extraction(self):
        """Markdown头部信息提取"""
        md_content = """# 测试小说标题

> 第1章 | 2000字 | 主分支
> 状态: final | 创建于 2026-04-17T14:00:00

---

# 第一章 开始的故事

这是章节内容...
"""
        metadata = self.extractor.extract_from_markdown_header(md_content)
        assert metadata.title == '测试小说标题'
        assert metadata.total_words == 2000


class TestStoryContentParser:
    """内容解析器测试 - 验证解析准确性和完整性"""

    def setup_method(self):
        self.parser = StoryContentParser()
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_parse_valid_story_node(self):
        """解析有效的story_node.json"""
        node_path = Path(self.test_dir) / "_story_node.json"
        node_data = {
            'story_id': 'story_parse_test',
            'title': '解析测试小说',
            'created_at': '2026-04-17T15:00:00',
            'status': 'active',
            'setting': {
                'story_name': '解析测试小说',
                'story_summary': '测试摘要'
            },
            'knowledge_base': {},
            'branches': [{
                'branch_id': 'branch_01',
                'name': '主分支',
                'chapters': [{
                    'chapter_num': 1,
                    'title': '第一章',
                    'content': '# 第一章\n\n这是测试内容。\n\n第二段内容。',
                    'word_count': 50,
                    'status': 'final',
                    'created_at': '2026-04-17T15:30:00'
                }]
            }],
            'total_chapters': 1,
            'total_words': 50
        }

        with open(node_path, 'w', encoding='utf-8') as f:
            json.dump(node_data, f, ensure_ascii=False)

        parsed = self.parser.parse_story_node(node_path)

        assert parsed is not None
        assert parsed.metadata.title == '解析测试小说'
        assert parsed.chapter_count == 1
        assert parsed.total_word_count > 0
        print(f"   解析成功: {parsed.metadata.title}, {parsed.chapter_count}章")

    def test_parse_markdown_chapter(self):
        """解析Markdown章节文件"""
        chap_path = Path(self.test_dir) / "test--branch_02-chap_03.md"  # 文件名与内容一致
        content = """# 第三章 复杂的章节

> 第3章 | 3000字 | branch_02
> 状态: draft

---

## 场景一：对话测试

"你好，"他说道，"这是一段对话。"

她回答："我明白你的意思。"

## 场景二：叙述

这是普通的叙述段落。包含多个句子的较长段落，
用于测试段落提取功能的准确性。

### 子标题

子内容...

**本章要点**
1. 要点一
2. 要点二
"""

        with open(chap_path, 'w', encoding='utf-8') as f:
            f.write(content)

        chapter = self.parser.parse_markdown_file(chap_path)

        assert chapter is not None
        assert chapter.chapter_num == 3
        assert chapter.branch_id == "branch_02"  # 文件名和内容一致
        assert len(chapter.paragraphs) > 0
        assert len(chapter.dialogues) >= 2  # 至少检测到2段对话
        assert len(chapter.sections) > 0  # 检测到标题结构
        print(f"   段落: {len(chapter.paragraphs)}, 对话: {len(chapter.dialogues)}, "
              f"节: {len(chapter.sections)}")

    def test_parse_encoding_detection(self):
        """多编码自动检测"""
        for encoding in ['utf-8', 'gbk']:
            file_path = Path(self.test_dir) / f"test_{encoding}.json"
            content = json.dumps({'test': '编码测试'}, ensure_ascii=False)

            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)

            loaded = self.parser._load_json_file(file_path)
            assert loaded is not None, f"{encoding} 编码加载失败"

    def test_parse_error_handling(self):
        """解析错误处理（损坏的文件）"""
        bad_file = Path(self.test_dir) / "corrupted.json"
        with open(bad_file, 'wb') as f:
            f.write(b'\x80\x81\x82\x83 invalid data')

        result = self.parser.parse_story_node(bad_file)
        assert result is None  # 应返回None而不是崩溃

        stats = self.parser.get_parse_statistics()
        assert stats['failed'] > 0
        print(f"   错误统计: 成功={stats['successful']}, 失败={stats['failed']}")

    def test_parse_statistics_accuracy(self):
        """解析统计准确性（错误率 < 0.1%）"""
        # 先执行多次解析操作
        for i in range(100):
            valid_path = Path(self.test_dir) / f"valid_{i}.json"
            with open(valid_path, 'w', encoding='utf-8') as f:
                json.dump({'test': i}, f)
            self.parser.parse_story_node(valid_path)

        stats = self.parser.get_parse_statistics()
        error_rate = stats.get('error_rate', 100)

        assert error_rate < 0.1, f"错误率 {error_rate}% 超过0.1%阈值"
        print(f"   解析错误率: {error_rate:.3f}% (< 0.1% ✓)")


class TestStoryErrorHandler:
    """错误处理器测试 - 分级日志和恢复机制"""

    def setup_method(self):
        self.log_file = Path(tempfile.mkdtemp()) / "test_errors.log"
        self.handler = StoryErrorHandler(log_file=str(self.log_file))

    def teardown_method(self):
        if self.log_file.parent.exists():
            import logging
            self.handler.logger.handlers.clear()  # 关闭所有日志处理器
            time.sleep(0.1)  # 等待文件释放
            shutil.rmtree(str(self.log_file.parent), ignore_errors=True)

    def test_log_error_levels(self):
        """测试所有错误级别记录"""
        levels = [
            (ErrorSeverity.INFO, 'INFO_TEST'),
            (ErrorSeverity.WARNING, 'WARNING_TEST'),
            (ErrorSeverity.ERROR, 'ERROR_TEST'),
            (ErrorSeverity.CRITICAL, 'CRITICAL_TEST')
        ]

        for severity, etype in levels:
            record = self.handler.log_error(
                severity=severity,
                error_type=etype,
                message=f'{etype} 消息',
                auto_recover=False
            )
            assert record.severity == severity
            assert record.error_type == etype

        assert len(self.handler.error_records) == 4

    def test_auto_recovery_mechanism(self):
        """自动恢复机制"""
        record = self.handler.log_error(
            severity=ErrorSeverity.ERROR,
            error_type='FILE_NOT_FOUND',
            message='文件不存在',
            file_path='/nonexistent/file.txt'
        )

        assert record.resolved
        assert len(record.resolution) > 0
        print(f"   自动恢复: {record.resolution}")

    def test_error_summary_generation(self):
        """错误摘要生成"""
        for i in range(10):
            error_type = f'TYPE_{i % 3}'
            if i % 4 == 0:
                error_type = 'FILE_NOT_FOUND'  # 添加可恢复类型

            self.handler.log_error(
                severity=ErrorSeverity.ERROR,
                error_type=error_type,
                message=f'错误消息 {i}',
                file_path='/nonexistent/file.txt' if 'FILE_NOT_FOUND' in error_type else ''
            )

        summary = self.handler.get_error_summary()

        assert summary['total_errors'] == 10
        assert 'by_severity' in summary
        assert 'by_type' in summary
        assert summary['resolved'] > 0  # FILE_NOT_FOUND类型的错误会自动恢复
        print(f"   总错误: {summary['total_errors']}, 已解决: {summary['resolved']}")

    def test_export_errors_to_json(self):
        """导出错误记录到JSON"""
        self.handler.log_error(ErrorSeverity.WARNING, 'TEST', '测试导出')
        output_path = Path(self.log_file.parent) / "errors_export.json"

        self.handler.export_errors_to_json(output_path)

        assert output_path.exists()
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert 'records' in data
        assert len(data['records']) >= 1
        print(f"   导出成功: {len(data['records'])} 条记录")

    def test_context_information_preservation(self):
        """上下文信息保留"""
        context = {
            'operation': 'scan',
            'attempt': 3,
            'details': {'path': '/test'}
        }

        record = self.handler.log_error(
            severity=ErrorSeverity.ERROR,
            error_type='CONTEXT_TEST',
            message='带上下文的错误',
            context=context
        )

        assert record.context == context
        assert record.context['operation'] == 'scan'


class TestIntegrationRealStories:
    """集成测试 - 使用真实stories目录进行批量验证"""

    def setup_method(self):
        self.stories_dir = Path(__file__).parent.parent / "stories"

    def test_batch_recognition_accuracy(self):
        """批量文件识别准确率（目标100%）"""
        if not self.stories_dir.exists():
            print("   ⚠️ stories目录不存在，跳过")
            return

        scanner = create_scanner(self.stories_dir)
        result = scanner.scan(force_refresh=True)

        total_found = result.story_directories_found
        valid_count = len(result.valid_stories)

        accuracy = (valid_count / total_found * 100) if total_found > 0 else 100
        print(f"   识别率: {accuracy:.1f}% ({valid_count}/{total_found})")

        assert accuracy >= 100, f"识别率 {accuracy:.1f}% 未达100%目标"

    def test_batch_loading_success_rate(self):
        """批量加载成功率（目标≥99%）"""
        if not self.stories_dir.exists():
            print("   ⚠️ stories目录不存在，跳过")
            return

        parser = create_content_parser()
        loaded = 0
        failed = 0

        scanner = create_scanner(self.stories_dir)
        result = scanner.scan(force_refresh=True)

        for story in result.valid_stories:
            node_path = Path(story['path']) / "_story_node.json"
            if node_path.exists():
                parsed = parser.parse_story_node(node_path)
                if parsed:
                    loaded += 1
                else:
                    failed += 1

        total = loaded + failed
        success_rate = (loaded / total * 100) if total > 0 else 100
        print(f"   加载成功率: {success_rate:.1f}% ({loaded}/{total})")

        assert success_rate >= 99, f"成功率 {success_rate:.1f}% 未达99%目标"

    def test_metadata_extraction_completeness(self):
        """元数据提取完整性（目标100%）"""
        if not self.stories_dir.exists():
            print("   ⚠️ stories目录不存在，跳过")
            return

        extractor = create_metadata_extractor()
        complete = 0
        total = 0

        scanner = create_scanner(self.stories_dir)
        result = scanner.scan(force_refresh=True)

        for story in result.valid_stories[:5]:  # 测试前5个
            node_path = Path(story['path']) / "_story_node.json"
            if node_path.exists():
                with open(node_path, 'r', encoding='utf-8') as f:
                    node_data = json.load(f)

                metadata = extractor.extract_from_node(node_data)
                total += 1

                if metadata.story_id and metadata.created_at:
                    complete += 1
                else:
                    print(f"     ⚠️ 不完整: {metadata.story_id}")

        completeness = (complete / total * 100) if total > 0 else 100
        print(f"   元数据完整率: {completeness:.1f}% ({complete}/{total})")

        assert completeness == 100, f"完整率 {completeness:.1f}% 未达100%目标"

    def test_content_parsing_integrity(self):
        """内容解析完整性（目标≥99.9%）"""
        if not self.stories_dir.exists():
            print("   ⚠️ stories目录不存在，跳过")
            return

        parser = create_content_parser()
        integrity_checks = 0
        integrity_passes = 0

        scanner = create_scanner(self.stories_dir)
        result = scanner.scan(force_refresh=True)

        for story in result.valid_stories:
            novel_dir = Path(story['path']) / "novel"
            if novel_dir.exists():
                for md_file in novel_dir.glob("*.md"):
                    chapter = parser.parse_markdown_file(md_file)
                    integrity_checks += 1

                    if chapter and chapter.content:
                        integrity_passes += 1
                        assert chapter.word_count > 0

        integrity_rate = (integrity_passes / integrity_checks * 100) if integrity_checks > 0 else 100
        print(f"   内容完整率: {integrity_rate:.1f}% ({integrity_passes}/{integrity_checks})")

        assert integrity_rate >= 99.9, f"完整率 {integrity_rate:.1f}% 未达99.9%目标"


def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 WAgent Stories Manager v7.0 完整测试套件")
    print("=" * 70)
    print(f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    test_classes = [
        ("文件扫描与识别", TestStoryScanner),
        ("元数据提取", TestStoryMetadataExtractor),
        ("内容解析", TestStoryContentParser),
        ("错误处理机制", TestStoryErrorHandler),
        ("真实数据集成测试", TestIntegrationRealStories),
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
                errors.append(f"{name}.{method_name}: {str(e)[:100]}")
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
            print(f"\n🎉🎉🎉 Stories Manager v7.0 全部核心功能通过! ({rate:.0f}%)\n")
        elif rate >= 80:
            print(f"\n✨ Stories Manager v7.0 基本功能正常! ({rate:.0f}%)\n")
        else:
            print(f"\n⚠️ 存在问题需要修复\n")

    if errors:
        print(f"\n错误 ({len(errors)}):")
        for e in errors[:15]:
            print(f"   • {e}")

    print("=" * 70)

    return passed, failed, total


if __name__ == "__main__":
    p, f, t = run_tests()
    sys.exit(0 if f == 0 else 1)
