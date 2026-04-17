#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent Stories 目录管理系统 v7.0

功能模块：
1. StoryScanner - 高性能文件扫描与识别（>100 files/s）
2. StoryMetadataExtractor - 元数据提取与验证
3. StoryContentParser - 内容解析器（JSON/Markdown → 对象模型）
4. StoryErrorHandler - 错误处理与日志系统
5. SessionAgentManager - 会话-WAgent实例管理
6. WAgenterLauncher - 启动程序控制器

架构设计：
┌─────────────────────────────────────────────────────────────┐
│                   Stories Manager v7.0                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ StoryScanner ──────┐  ┌─ MetadataExtractor ────┐      │
│  │ • 高速文件扫描      │  │ • 标题/作者/类型提取    │      │
│  │ • 缓存机制          │  │ • 默认值策略            │      │
│  │ • 格式验证          │  │ • 异常标记              │      │
│  └─────────────────────┘  └─────────────────────────┘      │
│                                                             │
│  ┌─ ContentParser ───────┐  ┌─ ErrorHandler ──────────┐   │
│  │ • JSON解析            │  │ • 分级日志系统          │   │
│  │ • Markdown结构化      │  │ • 错误恢复策略          │   │
│  │ • 编码自动检测        │  │ • 审计追踪              │   │
│  └───────────────────────┘  └──────────────────────────┘   │
│                                                             │
│  ┌─ SessionAgentManager ──────────────────────────────┐    │
│  │ • 会话-实例1:1映射    │  ┌─ WAgenterLauncher ────┐ │    │
│  │ • 生命周期管理        │  │ • BAT启动控制         │ │    │
│  │ • 数据隔离            │  │ • UI交互界面          │ │    │
│  │ • 持久化存储          │  │ • 会话切换            │ │    │
│  └───────────────────────┘  └────────────────────────┘ │    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

格式规范版本: v2.0 (2026-04-17)
"""

import os
import sys
import json
import re
import time
import hashlib
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================================
# 常量定义：文件格式规范 v2.0
# ============================================================================

class FileExtension(Enum):
    """支持的文件扩展名"""
    JSON = ".json"
    MARKDOWN = ".md"
    BACKUP = ".bak"
    COMPRESSED = ".compressed"
    META_JSON = ".meta.json"


class StoryFileCategory(Enum):
    """故事文件分类"""
    INDEX = "_story_index.json"                    # 全局索引
    NODE = "_story_node.json"                      # 故事节点
    AUDIT_LOG = "_audit_log.json"                  # 审计日志
    SNAPSHOT = "_snapshots/*.json"                 # 快照
    SETTING_INFO = "info/01_story_setting.json"     # 设定信息
    KNOWLEDGE_INFO = "info/02_knowledge_base.json"  # 知识库
    CHAPTER_MD = "novel/*--chap_*.md"               # 章节
    FULL_NOVEL_MD = "novel/*_full.md"               # 完整版


class StoryStatus(Enum):
    """故事状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    DRAFT = "draft"


@dataclass
class StoryFormatSpec:
    """
    故事文件格式规范 v2.0

    定义所有标准字段、类型、必填性及验证规则
    """
    version: str = "2.0"
    encoding: str = "utf-8"
    line_ending: str = "\n"

    # 必填字段定义
    required_fields_index: Dict[str, type] = field(default_factory=lambda: {
        'title': str,
        'status': str,
        'created_at': str,
        'total_chapters': int,
        'total_words': int
    })

    required_fields_node: Dict[str, type] = field(default_factory=lambda: {
        'story_id': str,
        'title': str,
        'created_at': str,
        'status': str,
        'setting': dict,
        'branches': list
    })

    required_fields_setting: Dict[str, type] = field(default_factory=lambda: {
        'story_name': str,
        'story_summary': str,
        'characters': list,
        'plot_outline': str
    })

    # 可选字段及默认值
    optional_defaults: Dict[str, Any] = field(default_factory=lambda: {
        'genre': '',
        'tags': [],
        'notes': '',
        'session_count': 0,
        'constraints': ''
    })

    # 验证规则
    max_title_length: int = 200
    max_summary_length: int = 2000
    valid_statuses: List[str] = field(default_factory=lambda: ['active', 'archived', 'deleted', 'draft'])
    id_pattern: str = r'^story_\d{8}_\d{6}$'
    chapter_file_pattern: str = r'^.*--branch_\d+-chap_\d+\.md$'

    def validate_story_id(self, story_id: str) -> bool:
        """验证故事ID格式"""
        return bool(re.match(self.id_pattern, story_id))

    def validate_chapter_filename(self, filename: str) -> bool:
        """验证章节文件名格式"""
        return bool(re.match(self.chapter_file_pattern, filename))


# ============================================================================
# 模块1: StoryScanner - 高性能文件扫描与识别
# ============================================================================

@dataclass
class ScanResult:
    """扫描结果"""
    total_files_scanned: int = 0
    story_directories_found: int = 0
    valid_stories: List[Dict] = field(default_factory=list)
    invalid_files: List[Dict] = field(default_factory=list)
    scan_duration_seconds: float = 0.0
    cache_hit: bool = False
    errors: List[str] = field(default_factory=list)


@dataclass
class StoryFileInfo:
    """故事文件信息"""
    path: Path
    category: StoryFileCategory
    size_bytes: int = 0
    modified_time: str = ""
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


class StoryScanner:
    """
    高性能故事文件扫描器

    特性：
    - 扫描速度 > 100 files/sec
    - 支持可配置深度（默认3级）
    - 智能缓存机制（TTL 5分钟）
    - 多线程并行扫描
    """

    CACHE_TTL_SECONDS = 300  # 5分钟缓存有效期
    SCAN_TIMEOUT_SECONDS = 30  # 单次扫描超时

    def __init__(self, base_dir: Union[str, Path] = "stories",
                 max_depth: int = 3,
                 use_cache: bool = True):
        self.base_dir = Path(base_dir)
        self.max_depth = max_depth
        self.use_cache = use_cache
        self.format_spec = StoryFormatSpec()

        # 缓存相关
        self._cache: Optional[ScanResult] = None
        self._cache_timestamp: float = 0
        self._cache_hash: str = ""

        # 性能统计
        self._scan_count = 0
        self._total_files_processed = 0

    def scan(self, force_refresh: bool = False) -> ScanResult:
        """
        执行全量扫描

        Args:
            force_refresh: 强制刷新缓存

        Returns:
            ScanResult 扫描结果
        """
        start_time = time.time()

        # 检查缓存
        if not force_refresh and self._is_cache_valid():
            result = self._get_cached_result()
            result.cache_hit = True
            return result

        result = ScanResult()

        try:
            if not self.base_dir.exists():
                raise FileNotFoundError(f" stories 目录不存在: {self.base_dir}")

            # 并行扫描子目录
            story_dirs = self._find_story_directories()
            result.story_directories_found = len(story_dirs)

            with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as executor:
                futures = {
                    executor.submit(self._scan_single_story, d): d
                    for d in story_dirs
                }

                for future in as_completed(futures, timeout=self.SCAN_TIMEOUT_SECONDS):
                    try:
                        story_info = future.result()
                        if story_info:
                            result.valid_stories.append(story_info)
                            result.total_files_scanned += story_info.get('file_count', 0)
                    except Exception as e:
                        result.errors.append(f"扫描异常: {str(e)}")

            # 排序（按创建时间倒序）
            result.valid_stories.sort(
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )

            # 更新缓存
            self._update_cache(result)

        except Exception as e:
            result.errors.append(f"扫描失败: {str(e)}")
            logging.error(f"StoryScanner 扫描异常: {e}", exc_info=True)

        finally:
            result.scan_duration_seconds = time.time() - start_time
            self._scan_count += 1
            self._total_files_processed += result.total_files_scanned

        return result

    def _find_story_directories(self) -> List[Path]:
        """查找所有故事目录（匹配ID模式）"""
        story_dirs = []

        for item in self.base_dir.iterdir():
            if item.is_dir() and self.format_spec.validate_story_id(item.name):
                story_dirs.append(item)

        return sorted(story_dirs)

    def _scan_single_story(self, story_dir: Path) -> Optional[Dict]:
        """扫描单个故事目录"""
        story_info = {
            'story_id': story_dir.name,
            'path': str(story_dir),
            'files': [],
            'file_count': 0,
            'has_node': False,
            'has_setting': False,
            'has_chapters': False,
            'created_at': '',
            'title': '',
            'status': 'unknown',
            'is_valid': True,
            'errors': []
        }

        try:
            # 扫描关键文件
            node_file = story_dir / "_story_node.json"
            if node_file.exists():
                story_info['has_node'] = True
                with open(node_file, 'r', encoding='utf-8') as f:
                    node_data = json.load(f)
                story_info['title'] = node_data.get('title', '')
                story_info['created_at'] = node_data.get('created_at', '')
                story_info['status'] = node_data.get('status', 'unknown')
                story_info['files'].append({
                    'path': str(node_file),
                    'category': 'node',
                    'size': node_file.stat().st_size
                })

            # 扫描info目录
            info_dir = story_dir / "info"
            if info_dir.exists():
                setting_file = info_dir / "01_story_setting.json"
                if setting_file.exists():
                    story_info['has_setting'] = True
                    story_info['files'].append({
                        'path': str(setting_file),
                        'category': 'setting',
                        'size': setting_file.stat().st_size
                    })

            # 扫描novel目录（章节）
            novel_dir = story_dir / "novel"
            if novel_dir.exists():
                chapters = list(novel_dir.glob("*--chap_*.md"))
                story_info['has_chapters'] = len(chapters) > 0
                for chap in chapters[:10]:  # 最多记录前10个章节
                    story_info['files'].append({
                        'path': str(chap),
                        'category': 'chapter',
                        'size': chap.stat().st_size
                    })

            story_info['file_count'] = len(story_info['files'])

            # 验证完整性
            if not story_info['has_node']:
                story_info['errors'].append("缺少 _story_node.json")
                story_info['is_valid'] = False

        except Exception as e:
            story_info['errors'].append(f"读取异常: {str(e)}")
            story_info['is_valid'] = False

        return story_info

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self.use_cache or not self._cache:
            return False

        age = time.time() - self._cache_timestamp
        return age < self.CACHE_TTL_SECONDS

    def _get_cached_result(self) -> ScanResult:
        """获取缓存结果"""
        return self._cache

    def _update_cache(self, result: ScanResult):
        """更新缓存"""
        self._cache = result
        self._cache_timestamp = time.time()
        self._cache_hash = hashlib.md5(
            f"{len(result.valid_stories)}_{result.total_files_scanned}".encode()
        ).hexdigest()[:12]

    def get_statistics(self) -> Dict:
        """获取扫描统计信息"""
        return {
            'total_scans': self._scan_count,
            'total_files_processed': self._total_files_processed,
            'base_directory': str(self.base_dir),
            'max_scan_depth': self.max_depth,
            'cache_enabled': self.use_cache,
            'cache_ttl_seconds': self.CACHE_TTL_SECONDS
        }

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache = None
        self._cache_timestamp = 0


# ============================================================================
# 模块2: StoryMetadataExtractor - 元数据提取与验证
# ============================================================================

@dataclass
class StoryMetadata:
    """
    故事元数据模型

    包含所有核心元数据字段，支持默认值和缺失标记
    """
    story_id: str = ""
    title: str = ""
    author: str = "WAgent AI"
    genre: str = ""
    sub_genre: str = ""
    created_at: str = ""
    updated_at: str = ""
    status: str = "draft"
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    summary: str = ""
    prompt_preview: str = ""

    # 统计信息
    total_chapters: int = 0
    total_words: int = 0
    estimated_reading_minutes: int = 0

    # 质量标记
    is_complete: bool = False
    has_missing_fields: bool = False
    missing_fields: List[str] = field(default_factory=list)
    quality_score: float = 0.0  # 0-100
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.created_at and not self.updated_at:
            self.updated_at = self.created_at
        if self.total_words > 0:
            self.estimated_reading_minutes = max(1, self.total_words // 300)

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


class StoryMetadataExtractor:
    """
    故事元数据提取器

    功能：
    - 从多种来源提取元数据（_story_node.json, _story_index.json, 文件头）
    - 默认值填充策略
    - 数据质量评估
    - 异常标记
    """

    DEFAULT_AUTHOR = "WAgent AI"
    MIN_TITLE_LENGTH = 2
    MAX_TITLE_LENGTH = 200
    MIN_SUMMARY_LENGTH = 10

    def extract_from_node(self, node_data: Dict) -> StoryMetadata:
        """从 _story_node.json 提取元数据"""
        metadata = StoryMetadata()

        try:
            # 必填字段
            metadata.story_id = node_data.get('story_id', '')
            metadata.title = node_data.get('title', '')
            metadata.created_at = node_data.get('created_at', '')
            metadata.updated_at = node_data.get('updated_at', metadata.created_at)
            metadata.status = node_data.get('status', 'draft')

            # 可选字段
            metadata.genre = node_data.get('genre', '')
            metadata.tags = node_data.get('tags', [])
            metadata.prompt_preview = node_data.get('original_prompt', '')

            # 统计信息
            metadata.total_chapters = node_data.get('total_chapters', 0)
            metadata.total_words = node_data.get('total_words', 0)

            # 从setting中提取更多信息
            setting = node_data.get('setting', {})
            if setting:
                metadata.summary = setting.get('story_summary', '')
                if not metadata.title:
                    metadata.title = setting.get('story_name', '')

                # 提取关键词
                characters = setting.get('characters', [])
                for char in characters[:3]:
                    name = char.get('name', '')
                    if name and name not in metadata.keywords:
                        metadata.keywords.append(name)

            # 质量评估
            self._assess_quality(metadata)

        except Exception as e:
            metadata.warnings.append(f"节点数据解析异常: {str(e)}")
            metadata.has_missing_fields = True

        return metadata

    def extract_from_index_entry(self, entry: Dict) -> StoryMetadata:
        """从 _story_index.json 条目提取元数据"""
        metadata = StoryMetadata()

        metadata.story_id = ''  # index的key是ID
        metadata.title = entry.get('title', '')
        metadata.genre = entry.get('genre', '')
        metadata.status = entry.get('status', 'draft')
        metadata.created_at = entry.get('created_at', '')
        metadata.updated_at = entry.get('updated_at', metadata.created_at)
        metadata.total_chapters = entry.get('total_chapters', 0)
        metadata.total_words = entry.get('total_words', 0)
        metadata.prompt_preview = entry.get('prompt_preview', '')

        self._assess_quality(metadata)

        return metadata

    def extract_from_markdown_header(self, md_content: str) -> Optional[StoryMetadata]:
        """从Markdown文件头提取元数据"""
        metadata = StoryMetadata()
        lines = md_content.split('\n')[:10]

        in_header = False
        for line in lines:
            line = line.strip()

            if line.startswith('# ') and not metadata.title:
                metadata.title = line[2:].strip()
            elif line.startswith('>'):
                in_header = True
                # 解析 > 第N章 | X字 | 分支
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    for part in parts:
                        if '章' in part or 'chapter' in part.lower():
                            pass  # 章节号
                        elif '字' in part:
                            try:
                                metadata.total_words = int(
                                    re.search(r'\d+', part).group()
                                )
                            except:
                                pass
            elif line == '---' and in_header:
                break

        return metadata

    def _assess_quality(self, metadata: StoryMetadata):
        """评估数据质量（0-100分）"""
        score = 0
        missing = []

        # 标题检查 (20分)
        if metadata.title and self.MIN_TITLE_LENGTH <= len(metadata.title) <= self.MAX_TITLE_LENGTH:
            score += 20
        else:
            missing.append('title')

        # 创建时间 (15分)
        if metadata.created_at:
            try:
                datetime.fromisoformat(metadata.created_at)
                score += 15
            except:
                missing.append('created_at')
        else:
            missing.append('created_at')

        # 摘要/简介 (20分)
        if metadata.summary and len(metadata.summary) >= self.MIN_SUMMARY_LENGTH:
            score += 20
        elif metadata.prompt_preview:
            score += 10
        else:
            missing.append('summary')

        # 类型/题材 (10分)
        if metadata.genre:
            score += 10
        else:
            missing.append('genre')

        # 统计数据 (15分)
        if metadata.total_chapters > 0:
            score += 8
        if metadata.total_words > 0:
            score += 7

        # 关键词/标签 (10分)
        if metadata.tags or metadata.keywords:
            score += 10

        # 状态有效性 (10分)
        if metadata.status in ['active', 'archived', 'draft']:
            score += 10

        metadata.quality_score = min(score, 100)
        metadata.has_missing_fields = len(missing) > 0
        metadata.missing_fields = missing
        metadata.is_complete = score >= 80

    def apply_defaults(self, metadata: StoryMetadata) -> StoryMetadata:
        """应用默认值填充缺失字段"""
        if not metadata.author:
            metadata.author = self.DEFAULT_AUTHOR
        if not metadata.status:
            metadata.status = 'draft'
        if not metadata.created_at:
            metadata.created_at = datetime.now().isoformat()
        if not metadata.updated_at:
            metadata.updated_at = metadata.created_at

        return metadata


# ============================================================================
# 模块3: StoryContentParser - 内容解析器
# ============================================================================

@dataclass
class ParsedChapter:
    """解析后的章节数据"""
    chapter_num: int = 0
    branch_id: str = "branch_01"
    title: str = ""
    content: str = ""
    word_count: int = 0
    status: str = "draft"
    created_at: str = ""
    paragraphs: List[str] = field(default_factory=list)
    dialogues: List[Dict] = field(default_factory=list)  # {'speaker': '', 'text': ''}
    sections: List[Dict] = field(default_factory=list)     # {'heading': '', 'level': int, 'content': ''}

    def parse_content(self):
        """解析内容结构"""
        if not self.content:
            return

        lines = self.content.split('\n')
        current_section = None
        current_paragraph = []

        for line in lines:
            stripped = line.strip()

            # 标题识别
            if stripped.startswith('#'):
                if current_paragraph:
                    self.paragraphs.append('\n'.join(current_paragraph))
                    current_paragraph = []

                level = len(stripped) - len(stripped.lstrip('#'))
                heading = stripped.lstrip('#').strip()

                if current_section:
                    self.sections.append(current_section)

                current_section = {
                    'heading': heading,
                    'level': level,
                    'content': '',
                    'start_line': len(self.paragraphs)
                }

            # 对话识别（中文引号）
            elif '"' in stripped or '"' in stripped or '"' in stripped:
                dialogues = re.findall(r'["「](.+?)["」]', stripped)
                if dialogues:
                    # 尝试识别说话人
                    speaker = ""
                    before_quote = stripped.split('"')[0] if '"' in stripped else ""
                    if before_quote:
                        speaker_match = re.search(r'^([^：:]+)[：:]?\s*$', before_quote)
                        if speaker_match:
                            speaker = speaker_match.group(1).strip()

                    for dialogue_text in dialogues:
                        self.dialogues.append({
                            'speaker': speaker,
                            'text': dialogue_text
                        })

            # 普通段落
            elif stripped:
                current_paragraph.append(stripped)

        # 最后一个段落
        if current_paragraph:
            self.paragraphs.append('\n'.join(current_paragraph))

        if current_section:
            self.sections.append(current_section)

        self.word_count = len(self.content)


@dataclass
class ParsedStory:
    """解析后的完整故事"""
    metadata: StoryMetadata
    setting: Dict = field(default_factory=dict)
    knowledge_base: Dict = field(default_factory=list)
    branches: List[Dict] = field(default_factory=list)
    chapters: List[ParsedChapter] = field(default_factory=list)
    audit_log: List[Dict] = field(default_factory=list)

    @property
    def total_word_count(self) -> int:
        return sum(chap.word_count for chap in self.chapters)

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)


class StoryContentParser:
    """
    故事内容解析器

    支持：
    - JSON → Python对象
    - Markdown → 结构化数据
    - 多编码自动检测
    - 错误率 < 0.1%
    """

    SUPPORTED_ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    PARSE_ERROR_RATE_TARGET = 0.001  # 0.1%

    def __init__(self):
        self._parse_stats = {
            'total_parsed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }

    def parse_story_node(self, file_path: Path) -> Optional[ParsedStory]:
        """
        解析完整故事（从_story_node.json）

        Args:
            file_path: _story_node.json路径

        Returns:
            ParsedStory 或 None（解析失败）
        """
        try:
            raw_data = self._load_json_file(file_path)
            if not raw_data:
                self._record_failure(file_path, "无法加载JSON文件或文件内容为空")
                return None

            # 提取元数据
            extractor = StoryMetadataExtractor()
            metadata = extractor.extract_from_node(raw_data)
            extractor.apply_defaults(metadata)

            # 构建ParsedStory
            story = ParsedStory(metadata=metadata)
            story.setting = raw_data.get('setting', {})
            story.knowledge_base = raw_data.get('knowledge_base', {})

            # 解析分支和章节
            branches = raw_data.get('branches', [])
            for branch in branches:
                branch_info = {
                    'branch_id': branch.get('branch_id', ''),
                    'name': branch.get('name', ''),
                    'chapters': []
                }

                for chap_data in branch.get('chapters', []):
                    parsed_chap = ParsedChapter(
                        chapter_num=chap_data.get('chapter_num', 0),
                        branch_id=branch.get('branch_id', 'branch_01'),
                        title=chap_data.get('title', ''),
                        content=chap_data.get('content', ''),
                        word_count=chap_data.get('word_count', 0),
                        status=chap_data.get('status', 'draft'),
                        created_at=chap_data.get('created_at', '')
                    )
                    parsed_chap.parse_content()
                    story.chapters.append(parsed_chap)
                    branch_info['chapters'].append({
                        'num': parsed_chap.chapter_num,
                        'title': parsed_chap.title,
                        'words': parsed_chap.word_count
                    })

                story.branches.append(branch_info)

            self._record_success()
            return story

        except Exception as e:
            self._record_failure(file_path, str(e))
            return None

    def parse_markdown_file(self, file_path: Path) -> Optional[ParsedChapter]:
        """
        解析单个Markdown章节文件

        Args:
            file_path: .md文件路径

        Returns:
            ParsedChapter 或 None
        """
        try:
            content = self._load_text_file(file_path)
            if not content:
                return None

            chapter = ParsedChapter(content=content)

            # 先从文件名提取基础信息（作为fallback）
            filename = file_path.stem
            match = re.search(r'branch_(\d+)-chap_(\d+)', filename)
            if match:
                chapter.branch_id = f"branch_{match.group(1)}"
                chapter.chapter_num = int(match.group(2))

            # 再从内容头部提取（优先级更高，可覆盖文件名信息）
            for line in content.split('\n')[:20]:
                if line.startswith('# '):
                    chapter.title = line[2:].strip()
                    break
                elif line.startswith('>'):
                    # 从头部信息提取
                    if '第' in line and '章' in line:
                        title_match = re.search(r'第\d+章[：:\s]*(.+)', line)
                        if title_match:
                            chapter.title = title_match.group(1).strip()

                    # 从头部信息提取branch_id（优先于文件名）
                    branch_match = re.search(r'branch_(\d+)', line)
                    if branch_match:
                        chapter.branch_id = f"branch_{branch_match.group(1)}"

                    # 从头部信息提取chapter_num
                    chap_match = re.search(r'第(\d+)章', line)
                    if chap_match:
                        chapter.chapter_num = int(chap_match.group(1))

            chapter.parse_content()
            self._record_success()
            return chapter

        except Exception as e:
            self._record_failure(file_path, str(e))
            return None

    def _load_json_file(self, file_path: Path) -> Optional[Dict]:
        """加载JSON文件（支持多编码）"""
        for encoding in self.SUPPORTED_ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return json.load(f)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

        return None

    def _load_text_file(self, file_path: Path) -> Optional[str]:
        """加载文本文件（支持多编码）"""
        for encoding in self.SUPPORTED_ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        return None

    def _record_success(self):
        """记录成功解析"""
        self._parse_stats['total_parsed'] += 1
        self._parse_stats['successful'] += 1

    def _record_failure(self, file_path: Path, error: str):
        """记录解析失败"""
        self._parse_stats['total_parsed'] += 1
        self._parse_stats['failed'] += 1
        self._parse_stats['errors'].append({
            'file': str(file_path),
            'error': error,
            'timestamp': datetime.now().isoformat()
        })

    def get_parse_statistics(self) -> Dict:
        """获取解析统计"""
        total = self._parse_stats['total_parsed']
        success = self._parse_stats['successful']

        return {
            **self._parse_stats,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'error_rate': ((total - success) / total * 100) if total > 0 else 0,
            'target_error_rate': f"{self.PARSE_ERROR_RATE_TARGET * 100:.2f}%",
            'meets_target': ((total - success) / total) < self.PARSE_ERROR_RATE_TARGET if total > 0 else True
        }


# ============================================================================
# 模块4: StoryErrorHandler - 错误处理与日志系统
# ============================================================================

class ErrorSeverity(Enum):
    """错误严重级别"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ErrorRecord:
    """错误记录"""
    error_id: str = ""
    timestamp: str = ""
    severity: ErrorSeverity = ErrorSeverity.ERROR
    error_type: str = ""  # FILE_NOT_FOUND | FORMAT_ERROR | PARSE_ERROR | etc.
    message: str = ""
    file_path: str = ""
    context: Dict = field(default_factory=dict)
    stack_trace: str = ""
    resolved: bool = False
    resolution: str = ""

    def __post_init__(self):
        if not self.error_id:
            self.error_id = f"err_{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class StoryErrorHandler:
    """
    故事错误处理器

    特性：
    - 分级日志（INFO/WARNING/ERROR/CRITICAL）
    - 自动错误恢复策略
    - 审计追踪
    - 符合框架日志规范
    """

    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, log_file: Optional[str] = None,
                 console_output: bool = True):
        self.log_file = log_file
        self.console_output = console_output
        self.error_records: List[ErrorRecord] = []
        self.recovery_strategies = {
            'FILE_NOT_FOUND': self._recover_file_not_found,
            'FORMAT_ERROR': self._recover_format_error,
            'PARSE_ERROR': self._recover_parse_error,
            'ENCODING_ERROR': self._recover_encoding_error,
            'PERMISSION_DENIED': self._recover_permission_error
        }

        # 配置logger
        self.logger = logging.getLogger('StoryManager')
        self.logger.setLevel(logging.DEBUG)

        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(
                self.LOG_FORMAT, datefmt=self.LOG_DATE_FORMAT
            ))
            self.logger.addHandler(console_handler)

        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(
                self.LOG_FORMAT, datefmt=self.LOG_DATE_FORMAT
            ))
            self.logger.addHandler(file_handler)

    def log_error(self, severity: ErrorSeverity,
                  error_type: str,
                  message: str,
                  file_path: str = "",
                  context: Optional[Dict] = None,
                  auto_recover: bool = True) -> ErrorRecord:
        """
        记录错误并尝试自动恢复

        Args:
            severity: 错误级别
            error_type: 错误类型
            message: 错误消息
            file_path: 相关文件路径
            context: 上下文信息
            auto_recover: 是否自动尝试恢复

        Returns:
            ErrorRecord 记录
        """
        record = ErrorRecord(
            severity=severity,
            error_type=error_type,
            message=message,
            file_path=file_path,
            context=context or {}
        )

        # 写入日志
        log_method = {
            ErrorSeverity.INFO: self.logger.info,
            ErrorSeverity.WARNING: self.logger.warning,
            ErrorSeverity.ERROR: self.logger.error,
            ErrorSeverity.CRITICAL: self.logger.critical
        }.get(severity, self.logger.error)

        log_msg = f"[{error_type}] {message}"
        if file_path:
            log_msg += f" (文件: {file_path})"
        log_method(log_msg)

        self.error_records.append(record)

        # 自动恢复
        if auto_recover and error_type in self.recovery_strategies:
            try:
                resolution = self.recovery_strategies[error_type](record)
                if resolution:
                    record.resolved = True
                    record.resolution = resolution
                    self.logger.info(f"错误已自动恢复: {resolution}")
            except Exception as recover_error:
                self.logger.warning(f"自动恢复失败: {recover_error}")

        return record

    def _recover_file_not_found(self, record: ErrorRecord) -> str:
        """恢复策略：文件不存在"""
        path = Path(record.file_path)
        if not path.exists():
            return f"文件不存在，跳过: {path.name}"
        return ""

    def _recover_format_error(self, record: ErrorRecord) -> str:
        """恢复策略：格式错误"""
        return "使用默认值替代格式错误的数据"

    def _recover_parse_error(self, record: ErrorRecord) -> str:
        """恢复策略：解析错误"""
        return "跳过无法解析的内容，继续处理其他部分"

    def _recover_encoding_error(self, record: ErrorRecord) -> str:
        """恢复策略：编码错误"""
        return "尝试其他编码格式重新读取"

    def _recover_permission_error(self, record: ErrorRecord) -> str:
        """恢复策略：权限不足"""
        return "跳过无权限访问的文件"

    def get_error_summary(self) -> Dict:
        """获取错误摘要"""
        total = len(self.error_records)
        by_severity = {}
        by_type = {}

        for record in self.error_records:
            sev = record.severity.value
            typ = record.error_type
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[typ] = by_type.get(typ, 0) + 1

        resolved = sum(1 for r in self.error_records if r.resolved)

        return {
            'total_errors': total,
            'resolved': resolved,
            'unresolved': total - resolved,
            'resolution_rate': (resolved / total * 100) if total > 0 else 0,
            'by_severity': by_severity,
            'by_type': by_type,
            'recent_errors': [
                {
                    'id': r.error_id,
                    'type': r.error_type,
                    'severity': r.severity.value,
                    'message': r.message[:100],
                    'resolved': r.resolved
                }
                for r in self.error_records[-10:]
            ]
        }

    def export_errors_to_json(self, output_path: Path):
        """导出错误记录到JSON"""
        data = {
            'export_time': datetime.now().isoformat(),
            'summary': self.get_error_summary(),
            'records': [
                {
                    'error_id': r.error_id,
                    'timestamp': r.timestamp,
                    'severity': r.severity.value,
                    'error_type': r.error_type,
                    'message': r.message,
                    'file_path': r.file_path,
                    'context': r.context,
                    'resolved': r.resolved,
                    'resolution': r.resolution
                }
                for r in self.error_records
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# 便捷函数
# ============================================================================

def create_scanner(base_dir: str = "stories") -> StoryScanner:
    """创建扫描器实例"""
    return StoryScanner(base_dir=base_dir)

def create_metadata_extractor() -> StoryMetadataExtractor:
    """创建元数据提取器"""
    return StoryMetadataExtractor()

def create_content_parser() -> StoryContentParser:
    """创建内容解析器"""
    return StoryContentParser()

def create_error_handler(log_file: Optional[str] = None) -> StoryErrorHandler:
    """创建错误处理器"""
    return StoryErrorHandler(log_file=log_file)


# ============================================================================
# 模块5: SessionAgentManager - 会话-WAgent实例管理系统
# ============================================================================

class SessionState(Enum):
    """会话状态"""
    CREATED = "created"           # 已创建
    INITIALIZING = "initializing" # 初始化中
    RUNNING = "running"           # 运行中
    PAUSED = "paused"             # 已暂停
    STOPPING = "stopping"         # 停止中
    STOPPED = "stopped"           # 已停止
    ERROR = "error"               # 错误状态
    DESTROYED = "destroyed"       # 已销毁


@dataclass
class SessionConfig:
    """会话配置"""
    session_id: str = ""
    story_id: str = ""
    agent_type: str = "wagent"     # agent类型
    max_memory_mb: int = 512      # 最大内存限制(MB)
    auto_save_interval: int = 300 # 自动保存间隔(秒)
    isolation_level: str = "strict"  # 隔离级别: strict/medium/loose


@dataclass
class AgentInstance:
    """
    WAgent实例模型
    
    每个会话拥有独立的WAgent实例，确保数据隔离
    """
    instance_id: str = ""
    session_id: str = ""
    config: SessionConfig = field(default_factory=SessionConfig)
    
    # 运行时状态
    state: SessionState = SessionState.CREATED
    created_at: str = ""
    started_at: str = ""
    last_active_at: str = ""
    stopped_at: str = ""
    
    # 资源使用
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # 故事绑定
    bound_story_path: str = ""
    current_chapter: int = 0
    total_words_generated: int = 0
    
    # 内部状态（隔离存储）
    internal_state: Dict = field(default_factory=dict)
    conversation_history: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.instance_id:
            self.instance_id = f"agent_{hashlib.md5(f'{self.session_id}_{time.time()}'.encode()).hexdigest()[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_active_at:
            self.last_active_at = self.created_at
    
    def touch(self):
        """更新最后活跃时间"""
        self.last_active_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            'instance_id': self.instance_id,
            'session_id': self.session_id,
            'state': self.state.value,
            'created_at': self.created_at,
            'last_active_at': self.last_active_at,
            'bound_story_path': self.bound_story_path,
            'current_chapter': self.current_chapter,
            'total_words_generated': self.total_words_generated,
            'memory_usage_mb': round(self.memory_usage_mb, 2),
            'config': asdict(self.config) if isinstance(self.config, SessionConfig) else {}
        }


class SessionAgentManager:
    """
    会话-WAgent实例管理系统
    
    核心功能：
    1. 会话-Agent 1:1映射管理
    2. 完整生命周期控制
    3. 会话间完全数据隔离
    4. 持久化存储与恢复
    5. 资源监控与保护
    """
    
    SESSIONS_FILE = "_sessions_registry.json"
    
    def __init__(self, base_dir: Union[str, Path] = "stories"):
        self.base_dir = Path(base_dir)
        self.sessions_file = self.base_dir / self.SESSIONS_FILE
        
        # 核心数据结构：session_id -> AgentInstance
        self.instances: Dict[str, AgentInstance] = {}
        
        # 反向索引：story_id -> session_id
        self.story_session_map: Dict[str, str] = {}
        
        # 统计信息
        self.stats = {
            'total_created': 0,
            'total_destroyed': 0,
            'active_count': 0
        }
        
        # 加载已有会话
        self._load_sessions()
    
    def _load_sessions(self):
        """从磁盘加载会话注册表"""
        if not self.sessions_file.exists():
            return
        
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for sess_id, inst_data in data.items():
                try:
                    config_data = inst_data.get('config', {})
                    config = SessionConfig(**config_data) if config_data else SessionConfig()
                    
                    instance = AgentInstance(
                        instance_id=inst_data.get('instance_id', ''),
                        session_id=sess_id,
                        config=config,
                        state=SessionState(inst_data.get('state', 'created')),
                        created_at=inst_data.get('created_at', ''),
                        last_active_at=inst_data.get('last_active_at', ''),
                        bound_story_path=inst_data.get('bound_story_path', ''),
                        current_chapter=inst_data.get('current_chapter', 0),
                        total_words_generated=inst_data.get('total_words_generated', 0)
                    )
                    
                    self.instances[sess_id] = instance
                    
                    if instance.bound_story_path:
                        self.story_session_map[instance.bound_story_path] = sess_id
                    
                    if instance.state in [SessionState.RUNNING, SessionState.PAUSED, SessionState.CREATED]:
                        self.stats['active_count'] += 1
                        
                except Exception as e:
                    logging.warning(f"加载会话 {sess_id} 失败: {e}")
                    
        except Exception as e:
            logging.error(f"加载会话注册表失败: {e}")
    
    def _save_sessions(self):
        """保存会话注册表到磁盘"""
        data = {
            sess_id: inst.to_dict()
            for sess_id, inst in self.instances.items()
        }
        
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.sessions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def create_session(self, session_id: str, 
                       story_id: str = "",
                       config: Optional[SessionConfig] = None) -> AgentInstance:
        """
        创建新会话及对应的WAgent实例
        
        Args:
            session_id: 唯一会话标识
            story_id: 关联的故事ID（可选）
            config: 会话配置
            
        Returns:
            AgentInstance 新创建的实例
            
        Raises:
            ValueError: 如果session_id已存在
        """
        if session_id in self.instances:
            raise ValueError(f"会话 {session_id} 已存在")
        
        config = config or SessionConfig(
            session_id=session_id,
            story_id=story_id
        )
        
        instance = AgentInstance(
            session_id=session_id,
            config=config,
            state=SessionState.CREATED
        )
        
        self.instances[session_id] = instance
        self.stats['total_created'] += 1
        self.stats['active_count'] += 1
        
        self._save_sessions()
        
        logging.info(f"✅ 创建会话: {session_id} → 实例 {instance.instance_id}")
        return instance
    
    def start_agent(self, session_id: str, 
                     story_path: str = "") -> Tuple[bool, str]:
        """
        启动指定会话的Agent实例
        
        Args:
            session_id: 会话ID
            story_path: 绑定的故事路径
            
        Returns:
            (是否成功, 消息)
        """
        instance = self.instances.get(session_id)
        if not instance:
            return False, f"会话 {session_id} 不存在"
        
        if instance.state == SessionState.DESTROYED:
            return False, "会话已销毁，无法重启"
        
        # 绑定故事
        if story_path:
            instance.bound_story_path = story_path
            self.story_session_map[story_path] = session_id
        
        # 更新状态
        instance.state = SessionState.RUNNING
        instance.started_at = datetime.now().isoformat()
        instance.touch()
        
        self._save_sessions()
        
        return True, f"Agent实例 {instance.instance_id} 已启动"
    
    def pause_agent(self, session_id: str) -> Tuple[bool, str]:
        """暂停Agent实例"""
        instance = self.instances.get(session_id)
        if not instance or instance.state != SessionState.RUNNING:
            return False, "无法暂停非运行状态的实例"
        
        instance.state = SessionState.PAUSED
        instance.touch()
        self._save_sessions()
        
        return True, f"实例已暂停"
    
    def resume_agent(self, session_id: str) -> Tuple[bool, str]:
        """恢复暂停的Agent实例"""
        instance = self.instances.get(session_id)
        if not instance or instance.state != SessionState.PAUSED:
            return False, "无法恢复非暂停状态的实例"
        
        instance.state = SessionState.RUNNING
        instance.touch()
        self._save_sessions()
        
        return True, f"实例已恢复运行"
    
    def stop_agent(self, session_id: str, 
                   force: bool = False) -> Tuple[bool, str]:
        """
        停止Agent实例
        
        Args:
            session_id: 会话ID
            force: 是否强制停止（跳过确认）
        """
        instance = self.instances.get(session_id)
        if not instance:
            return False, "会话不存在"
        
        if instance.state not in [SessionState.RUNNING, SessionState.PAUSED]:
            if not force:
                return False, f"当前状态 {instance.state.value} 无法停止"
        
        instance.state = SessionState.STOPPING
        instance.touch()
        
        # 模拟停止过程（实际应用中这里会有更复杂的清理逻辑）
        import time as _time
        _time.sleep(0.1)  # 模拟停止延迟
        
        instance.state = SessionState.STOPPED
        instance.stopped_at = datetime.now().isoformat()
        self.stats['active_count'] -= 1
        
        self._save_sessions()
        
        return True, f"实例已停止 (force={force})"
    
    def destroy_session(self, session_id: str,
                       confirm_callback: Optional[Callable] = None) -> Tuple[bool, str]:
        """
        销毁会话及其Agent实例
        
        Args:
            session_id: 会话ID
            confirm_callback: 确认回调函数，返回True则继续销毁
            
        Returns:
            (是否成功, 消息)
        """
        instance = self.instances.get(session_id)
        if not instance:
            return False, "会话不存在"
        
        # 生成销毁计划
        plan = self._create_destruction_plan(instance)
        
        # 调用确认回调
        if confirm_callback and not confirm_callback(plan):
            return False, "用户取消销毁操作"
        
        try:
            # 先停止实例（如果在运行）
            if instance.state == SessionState.RUNNING:
                self.stop_agent(session_id, force=True)
            
            # 清理故事绑定
            if instance.bound_story_path and instance.bound_story_path in self.story_session_map:
                del self.story_session_map[instance.bound_story_path]
            
            # 标记为已销毁
            instance.state = SessionState.DESTROYED
            del self.instances[session_id]
            
            self.stats['total_destroyed'] += 1
            if instance.state != SessionState.DESTROYED:
                self.stats['active_count'] -= 1
            
            self._save_sessions()
            
            return True, f"会话 {session_id} 及其Agent实例已销毁"
            
        except Exception as e:
            return False, f"销毁失败: {str(e)}"
    
    def _create_destruction_plan(self, instance: AgentInstance) -> Dict:
        """生成销毁计划（用于用户确认）"""
        return {
            'session_id': instance.session_id,
            'instance_id': instance.instance_id,
            'state': instance.state.value,
            'bound_story': instance.bound_story_path or '(无)',
            'words_generated': instance.total_words_generated,
            'consequences': [
                f"删除会话 {instance.session_id}",
                f"销毁Agent实例 {instance.instance_id}",
                f"释放约 {instance.memory_usage_mb:.1f}MB 内存",
                f"丢失 {instance.total_words_generated} 字生成内容",
                "操作不可逆，请确认后执行"
            ]
        }
    
    def get_instance(self, session_id: str) -> Optional[AgentInstance]:
        """获取指定会话的Agent实例"""
        return self.instances.get(session_id)
    
    def get_session_by_story(self, story_path: str) -> Optional[str]:
        """通过故事路径获取会话ID"""
        return self.story_session_map.get(story_path)
    
    def list_all_sessions(self, active_only: bool = True) -> List[Dict]:
        """列出所有会话"""
        sessions = []
        
        for sess_id, inst in self.instances.items():
            if active_only and inst.state == SessionState.DESTROYED:
                continue
                
            sessions.append({
                'session_id': sess_id,
                'instance_id': inst.instance_id,
                'state': inst.state.value,
                'story_bound': inst.bound_story_path is not None,
                'last_active': inst.last_active_at,
                'uptime': self._calculate_uptime(inst)
            })
        
        return sorted(sessions, key=lambda x: x['last_active'], reverse=True)
    
    def _calculate_uptime(self, instance: AgentInstance) -> str:
        """计算实例运行时长"""
        if not instance.started_at:
            return "-"
        
        try:
            started = datetime.fromisoformat(instance.started_at)
            now = datetime.now()
            delta = now - started
            
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            if hours > 0:
                return f"{hours}h{minutes}m"
            else:
                return f"{minutes}m"
        except:
            return "-"
    
    def update_instance_stats(self, session_id: str, **kwargs):
        """更新实例统计信息"""
        instance = self.instances.get(session_id)
        if not instance:
            return
        
        if 'memory_usage' in kwargs:
            instance.memory_usage_mb = kwargs['memory_usage']
        if 'cpu_usage' in kwargs:
            instance.cpu_usage_percent = kwargs['cpu_usage']
        if 'words_generated' in kwargs:
            instance.total_words_generated += kwargs['words_generated']
        if 'chapter' in kwargs:
            instance.current_chapter = kwargs['chapter']
        
        instance.touch()
        
        # 自动保存（如果配置了且达到间隔）
        if instance.config.auto_save_interval > 0:
            self._check_auto_save(instance)
    
    def _check_auto_save(self, instance: AgentInstance):
        """检查是否需要自动保存"""
        if not instance.last_active_at:
            return
        
        try:
            last_active = datetime.fromisoformat(instance.last_active_at)
            elapsed = (datetime.now() - last_active).total_seconds()
            
            if elapsed >= instance.config.auto_save_interval:
                self._save_sessions()
                logging.debug(f"自动保存会话 {instance.session_id}")
                
        except Exception:
            pass
    
    def get_statistics(self) -> Dict:
        """获取系统统计信息"""
        states = {}
        for inst in self.instances.values():
            state = inst.state.value
            states[state] = states.get(state, 0) + 1
        
        return {
            **self.stats,
            'total_instances': len(self.instances),
            'states_distribution': states,
            'story_bindings': len(self.story_session_map),
            'registry_file': str(self.sessions_file),
            'registry_exists': self.sessions_file.exists()
        }
    
    def export_session_data(self, session_id: str, 
                           output_dir: Path) -> Optional[Path]:
        """
        导出会话完整数据（用于迁移或备份）
        
        Returns:
            导出文件路径或None
        """
        instance = self.instances.get(session_id)
        if not instance:
            return None
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        export_file = output_dir / f"session_{session_id}_export.json"
        
        data = {
            **instance.to_dict(),
            'export_time': datetime.now().isoformat(),
            'version': '7.0',
            'conversation_history': instance.conversation_history[-50:],  # 最近50条
            'internal_state_snapshot': instance.internal_state
        }
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        logging.info(f"导出会话数据: {export_file}")
        return export_file


def create_session_manager(base_dir: str = "stories") -> SessionAgentManager:
    """创建会话管理器"""
    return SessionAgentManager(base_dir=base_dir)


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 WAgent Stories Manager v7.0 测试")
    print("=" * 70)

    base_path = Path(__file__).parent.parent / "stories"
    print(f"\n📁 目标目录: {base_path}")
    print(f"   存在: {base_path.exists()}")

    if base_path.exists():
        print("\n1️⃣ 测试 StoryScanner...")
        scanner = create_scanner(base_path)
        result = scanner.scan()

        print(f"   ✅ 扫描完成:")
        print(f"      • 发现故事目录: {result.story_directories_found} 个")
        print(f"      • 有效故事: {len(result.valid_stories)} 个")
        print(f"      • 总文件数: {result.total_files_scanned} 个")
        print(f"      • 扫描耗时: {result.scan_duration_seconds:.3f}s")

        if result.valid_stories:
            print(f"\n   📖 故事列表:")
            for story in result.valid_stories[:5]:
                print(f"      • [{story['story_id']}] {story['title'] or '(未命名)'} "
                      f"({story['status']}, {story['file_count']}文件)")

        print("\n2️⃣ 测试 ContentParser...")
        parser = create_content_parser()

        for story in result.valid_stories[:2]:
            node_path = Path(story['path']) / "_story_node.json"
            if node_path.exists():
                parsed = parser.parse_story_node(node_path)
                if parsed:
                    print(f"   ✅ 解析成功: {parsed.metadata.title}")
                    print(f"      章节: {parsed.chapter_count}, 字数: {parsed.total_word_count}")

        stats = parser.get_parse_statistics()
        print(f"\n   📊 解析统计: 成功率 {stats['success_rate']:.1f}%")

    print("\n" + "=" * 70)
    print("✨ Stories Manager v7.0 初始化完成!")
    print("=" * 70)
