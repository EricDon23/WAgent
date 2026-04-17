#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
故事会话管理系统 (Story Session Manager)

核心功能：
1. 故事树节点数据结构 (StoryNode)
2. 会话创建、更新、保存和加载
3. 多版本分支支持
4. 完整的故事状态快照
5. 会话索引与浏览
6. 断点续写支持

设计原则：
- 每个故事是一个独立的StoryNode树
- 支持多分支（不同创作方向）
- 所有状态变更自动序列化
- 可从任意节点恢复会话
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class ChapterRecord:
    """章节记录"""
    chapter_num: int
    title: str = ""
    content: str = ""
    word_count: int = 0
    created_at: str = ""
    modified_at: str = ""
    status: str = "draft"  # draft/revised/final
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
        self.word_count = len(self.content)


@dataclass 
class StoryBranch:
    """故事分支（支持多版本）"""
    branch_id: str  # 如 "branch_01", "branch_02"
    name: str = ""  # 分支名称
    chapters: List[ChapterRecord] = field(default_factory=list)
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.name:
            self.name = f"分支 {self.branch_id}"
    
    @property
    def total_chapters(self) -> int:
        return len(self.chapters)
    
    @property
    def total_words(self) -> int:
        return sum(ch.word_count for ch in self.chapters)
    
    def get_latest_chapter(self) -> Optional[ChapterRecord]:
        return self.chapters[-1] if self.chapters else None
    
    def add_chapter(self, record: ChapterRecord):
        """添加章节"""
        self.chapters.append(record)


@dataclass
class StoryNode:
    """
    故事树节点 - 核心数据结构
    
    表示一个完整的故事项目，包含：
    - 元信息（ID、标题、时间等）
    - 故事设定（导演AI输出）
    - 研究资料（研究员AI输出）
    - 一个或多个分支（每个分支包含多个章节）
    - 状态信息
    """
    # === 基本信息 ===
    story_id: str
    title: str = ""
    genre: str = ""
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"  # active/completed/abandoned/archived
    
    # === 用户输入 ===
    original_prompt: str = ""  # 用户原始创意输入
    
    # === AI生成内容 ===
    setting: Dict[str, Any] = field(default_factory=dict)  # 故事设定
    knowledge_base: Dict[str, Any] = field(default_factory=dict)  # 研究资料
    
    # === 分支结构 ===
    branches: List[StoryBranch] = field(default_factory=list)
    current_branch_id: str = ""  # 当前活跃的分支
    
    # === 统计信息 ===
    total_chapters: int = 0
    total_words: int = 0
    session_count: int = 0  # 会话次数
    
    # === 扩展元数据 ===
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    
    def __post_init__(self):
        now = datetime.now()
        if not self.created_at:
            self.created_at = now.isoformat()
        self.updated_at = now.isoformat()
        
        # 如果没有分支，创建默认分支
        if not self.branches:
            default_branch = StoryBranch(
                branch_id="branch_01",
                name="主分支"
            )
            self.branches.append(default_branch)
            self.current_branch_id = "branch_01"
        
        self._update_stats()
    
    @property
    def current_branch(self) -> Optional[StoryBranch]:
        """获取当前活跃分支"""
        for b in self.branches:
            if b.branch_id == self.current_branch_id:
                return b
        return self.branches[0] if self.branches else None
    
    def _update_stats(self):
        """更新统计信息"""
        self.total_chapters = sum(b.total_chapters for b in self.branches)
        self.total_words = sum(b.total_words for b in self.branches)
        self.updated_at = datetime.now().isoformat()
    
    def create_branch(self, branch_id: str = None, name: str = "") -> StoryBranch:
        """创建新分支"""
        if not branch_id:
            existing_ids = [b.branch_id for b in self.branches]
            next_num = len(existing_ids) + 1
            branch_id = f"branch_{next_num:02d}"
        
        new_branch = StoryBranch(
            branch_id=branch_id,
            name=name or f"分支 {branch_id}"
        )
        
        self.branches.append(new_branch)
        self.current_branch_id = branch_id
        self._update_stats()
        
        return new_branch
    
    def switch_branch(self, branch_id: str) -> bool:
        """切换到指定分支"""
        for b in self.branches:
            if b.branch_id == branch_id:
                self.current_branch_id = branch_id
                self._update_stats()
                return True
        return False
    
    def add_chapter(self, chapter_record: ChapterRecord, 
                   branch_id: str = None) -> bool:
        """添加章节到指定分支"""
        target_branch_id = branch_id or self.current_branch_id
        
        for b in self.branches:
            if b.branch_id == target_branch_id:
                b.add_chapter(chapter_record)
                self._update_stats()
                self.session_count += 1
                return True
        
        return False
    
    def get_all_chapters(self) -> List[ChapterRecord]:
        """获取所有分支的所有章节（按顺序）"""
        all_chapters = []
        for b in sorted(self.branches, key=lambda x: x.branch_id):
            all_chapters.extend(b.chapters)
        return all_chapters
    
    def get_full_novel_text(self) -> str:
        """获取完整小说文本"""
        lines = [f"# {self.title}\n"]
        lines.append(f"> **WAgent AI生成作品**\n")
        lines.append(f"> 创建时间: {self.created_at[:10]}\n")
        lines.append(f"> 最后更新: {self.updated_at[:19]}\n")
        lines.append(f"> 总章节数: {self.total_chapters}\n\n")
        
        total_wc = 0
        for ch in self.get_all_chapters():
            wc = len(ch.content)
            total_wc += wc
            
            lines.append(f"---\n\n## 第{ch.chapter_num}章 ({wc}字)\n\n")
            lines.append(ch.content)
            lines.append("\n\n")
        
        lines.append(f"\n---\n\n*全文共计 {total_wc} 字*\n")
        
        return "".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'story_id': self.story_id,
            'title': self.title,
            'genre': self.genre,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'status': self.status,
            'original_prompt': self.original_prompt,
            'setting': self.setting,
            'knowledge_base': self.knowledge_base,
            'branches': [
                {
                    'branch_id': b.branch_id,
                    'name': b.name,
                    'created_at': b.created_at,
                    'chapters': [
                        asdict(ch) for ch in b.chapters
                    ]
                }
                for b in self.branches
            ],
            'current_branch_id': self.current_branch_id,
            'total_chapters': self.total_chapters,
            'total_words': self.total_words,
            'session_count': self.session_count,
            'tags': self.tags,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StoryNode':
        """从字典创建实例（用于反序列化）"""
        branches_data = data.get('branches', [])
        branches = []
        
        for bd in branches_data:
            chapters = [
                ChapterRecord(**ch) for ch in bd.get('chapters', [])
            ]
            
            branch = StoryBranch(
                branch_id=bd['branch_id'],
                name=bd.get('name', ''),
                chapters=chapters,
                created_at=bd.get('created_at', '')
            )
            branches.append(branch)
        
        node = cls(
            story_id=data['story_id'],
            title=data.get('title', ''),
            genre=data.get('genre', ''),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            status=data.get('status', 'active'),
            original_prompt=data.get('original_prompt', ''),
            setting=data.get('setting', {}),
            knowledge_base=data.get('knowledge_base', {}),
            branches=branches,
            current_branch_id=data.get('current_branch_id', ''),
            tags=data.get('tags', []),
            notes=data.get('notes', '')
        )
        
        node.total_chapters = data.get('total_chapters', 0)
        node.total_words = data.get('total_words', 0)
        node.session_count = data.get('session_count', 0)
        
        return node


class StorySessionManager:
    """
    故事会话管理器
    
    职责：
    1. 管理所有故事节点（CRUD）
    2. 提供会话保存/加载接口
    3. 维护故事索引
    4. 提供故事浏览功能
    5. 支持断点续写
    """
    
    def __init__(self, base_dir: str = "stories"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 索引文件路径
        self.index_file = self.base_dir / "_story_index.json"
        
        # 内存中的索引
        self._index: Dict[str, Dict] = {}
        
        # 加载现有索引
        self._load_index()
    
    def _load_index(self):
        """加载故事索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self._index = json.load(f)
            except Exception as e:
                print(f"⚠️ 加载索引失败: {e}")
                self._index = {}
    
    def _save_index(self):
        """保存故事索引"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
    
    def create_story(self, story_id: str, title: str = "", 
                     prompt: str = "") -> StoryNode:
        """创建新故事节点"""
        node = StoryNode(
            story_id=story_id,
            title=title,
            original_prompt=prompt
        )
        
        # 创建故事专属目录
        story_dir = self.base_dir / story_id
        story_dir.mkdir(parents=True, exist_ok=True)
        
        # 子目录结构
        (story_dir / "info").mkdir(exist_ok=True)
        (story_dir / "novel").mkdir(exist_ok=True)
        (story_dir / "archive").mkdir(exist_ok=True)
        
        # 保存节点文件
        self._save_node(node)
        
        # 更新索引
        self._index[story_id] = {
            'title': title,
            'genre': '',
            'status': 'active',
            'created_at': node.created_at,
            'updated_at': node.updated_at,
            'total_chapters': 0,
            'total_words': 0,
            'prompt_preview': prompt[:100] if prompt else ''
        }
        self._save_index()
        
        return node
    
    def load_story(self, story_id: str) -> Optional[StoryNode]:
        """加载故事节点"""
        node_file = self.base_dir / story_id / "_story_node.json"
        
        if not node_file.exists():
            return None
        
        try:
            with open(node_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return StoryNode.from_dict(data)
            
        except Exception as e:
            print(f"❌ 加载故事失败: {e}")
            return None
    
    def save_story(self, node: StoryNode) -> bool:
        """保存故事节点（更新）"""
        self._save_node(node)
        
        # 更新索引
        self._index[node.story_id] = {
            'title': node.title,
            'genre': node.genre,
            'status': node.status,
            'created_at': node.created_at,
            'updated_at': node.updated_at,
            'total_chapters': node.total_chapters,
            'total_words': node.total_words,
            'prompt_preview': node.original_prompt[:100] if node.original_prompt else ''
        }
        self._save_index()
        
        return True
    
    def _save_node(self, node: StoryNode):
        """保存节点到文件"""
        story_dir = self.base_dir / node.story_id
        story_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 保存主节点文件
        node_file = story_dir / "_story_node.json"
        with open(node_file, 'w', encoding='utf-8') as f:
            json.dump(node.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        
        # 2. 保存设定文档
        if node.setting:
            setting_file = story_dir / "info" / "setting.json"
            with open(setting_file, 'w', encoding='utf-8') as f:
                json.dump(node.setting, f, ensure_ascii=False, indent=2, default=str)
        
        # 3. 保存研究资料
        if node.knowledge_base:
            kb_file = story_dir / "info" / "knowledge_base.json"
            with open(kb_file, 'w', encoding='utf-8') as f:
                json.dump(node.knowledge_base, f, ensure_ascii=False, indent=2, default=str)
        
        # 4. 保存各分支的章节
        novel_dir = story_dir / "novel"
        
        for branch in node.branches:
            for ch in branch.chapters:
                # 单章节文件
                filename = f"{node.story_id}--{branch.branch_id}-chap_{ch.chapter_num:02d}.md"
                filepath = novel_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {node.title}\n\n")
                    f.write(f"> 第{ch.chapter_num}章 | {ch.word_count}字 | {branch.name}\n")
                    f.write(f"> 状态: {ch.status} | 创建于 {ch.created_at[:19]}\n\n")
                    f.write("---\n\n")
                    f.write(ch.content)
                    
                    if ch.content and not ch.content.endswith('\n'):
                        f.write('\n')
        
        # 5. 保存完整小说合并版
        full_novel_path = novel_dir / f"{node.story_id}_full.md"
        full_text = node.get_full_novel_text()
        
        with open(full_novel_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
    
    def list_stories(self, include_archived: bool = False) -> List[Dict]:
        """列出所有故事"""
        stories = []
        
        for sid, info in self._index.items():
            if not include_archived and info.get('status') == 'archived':
                continue
            
            stories.append({
                'story_id': sid,
                **info,
                'path': str(self.base_dir / sid)
            })
        
        # 按更新时间排序（最新在前）
        stories.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        return stories
    
    def get_story_summary(self, story_id: str) -> Optional[Dict]:
        """获取故事摘要"""
        node = self.load_story(story_id)
        
        if not node:
            return None
        
        latest_ch = node.current_branch.get_latest_chapter() if node.current_branch else None
        
        return {
            'story_id': node.story_id,
            'title': node.title,
            'genre': node.genre,
            'status': node.status,
            'original_prompt': node.original_prompt,
            'created_at': node.created_at,
            'updated_at': node.updated_at,
            'total_chapters': node.total_chapters,
            'total_words': node.total_words,
            'session_count': node.session_count,
            'branch_count': len(node.branches),
            'current_branch': node.current_branch_id,
            'latest_chapter': latest_ch.chapter_num if latest_ch else 0,
            'has_setting': bool(node.setting),
            'has_knowledge': bool(node.knowledge_base),
            'tags': node.tags,
            'notes': node.notes
        }
    
    def delete_story(self, story_id: str, archive: bool = True) -> bool:
        """删除或归档故事"""
        if archive:
            # 归档而非真删除
            node = self.load_story(story_id)
            if node:
                node.status = 'archived'
                self.save_story(node)
                return True
        else:
            # 真正删除
            story_dir = self.base_dir / story_id
            if story_dir.exists():
                import shutil
                shutil.rmtree(story_dir)
            
            if story_id in self._index:
                del self._index[story_id]
                self._save_index()
                return True
        
        return False
    
    def export_story(self, story_id: str, output_format: str = "zip") -> Optional[str]:
        """导出故事为打包文件"""
        node = self.load_story(story_id)
        
        if not node:
            return None
        
        story_dir = self.base_dir / story_id
        
        if output_format == "zip":
            import zipfile
            zip_path = self.base_dir / "archive" / f"{story_id}_full.zip"
            zip_path.parent.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in story_dir.rglob('*'):
                    if file_path.is_file() and '_story_node.json' not in file_path.name:
                        arcname = file_path.relative_to(self.base_dir)
                        zf.write(file_path, arcname)
            
            return str(zip_path)
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取全局统计信息"""
        stories = self.list_stories(include_archived=True)
        
        active = [s for s in stories if s['status'] == 'active']
        completed = [s for s in stories if s['status'] == 'completed']
        archived = [s for s in stories if s['status'] == 'archived']
        
        total_chapters = sum(s.get('total_chapters', 0) for s in stories)
        total_words = sum(s.get('total_words', 0) for s in stories)
        
        return {
            'total_stories': len(stories),
            'active_stories': len(active),
            'completed_stories': len(completed),
            'archived_stories': len(archived),
            'total_chapters': total_chapters,
            'total_words': total_words,
            'storage_size': self._get_storage_size(),
            'last_updated': max((s.get('updated_at', '') for s in stories), default='')
        }
    
    def _get_storage_size(self) -> str:
        """计算存储大小"""
        total_size = 0
        
        for path in self.base_dir.rglob('*'):
            if path.is_file() and '_story_index' not in path.name:
                total_size += path.stat().st_size
        
        if total_size < 1024:
            return f"{total_size} B"
        elif total_size < 1024 * 1024:
            return f"{total_size / 1024:.1f} KB"
        else:
            return f"{total_size / (1024*1024):.1f} MB"
    
    def print_story_list(self):
        """打印故事列表（美化输出）"""
        stories = self.list_stories()
        
        if not stories:
            print("\n📭 暂无故事记录")
            print("   运行 python wagent.py 开始创作您的第一个故事！\n")
            return
        
        print("\n" + "="*70)
        print("📚 WAgent 故事库")
        print("="*70)
        
        for i, story in enumerate(stories, 1):
            status_icon = {
                'active': '🟢',
                'completed': '✅',
                'archived': '📦'
            }.get(story['status'], '❓')
            
            print(f"\n{i}. [{status_icon}] {story['title'] or '(未命名)'}")
            print(f"   ID: {story['story_id']}")
            print(f"   类型: {story.get('genre', '未设置')}")
            print(f"   章节: {story.get('total_chapters', 0)} 章 | "
                  f"总字数: {story.get('total_words', 0):,}")
            print(f"   创建: {story.get('created_at', '')[:10]} | "
                  f"更新: {story.get('updated_at', '')[:10]}")
            
            if story.get('prompt_preview'):
                print(f"   创意: {story['prompt_preview']}...")
        
        stats = self.get_statistics()
        print(f"\n{'─'*70}")
        print(f"📊 统计: {stats['total_stories']} 个故事 | "
              f"{stats['total_chapters']} 章 | "
              f"{stats['total_words']:,} 字 | "
              f"占用 {stats['storage_size']}")
        print("="*70 + "\n")


# 全局便捷函数
_session_manager = None

def get_session_manager(base_dir: str = "stories") -> StorySessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = StorySessionManager(base_dir)
    return _session_manager


def list_all_stories():
    """列出所有故事（便捷函数）"""
    mgr = get_session_manager()
    mgr.print_story_list()


def load_latest_story() -> Optional[StoryNode]:
    """加载最近更新的故事"""
    mgr = get_session_manager()
    stories = mgr.list_stories()
    
    if stories:
        return mgr.load_story(stories[0]['story_id'])
    return None
