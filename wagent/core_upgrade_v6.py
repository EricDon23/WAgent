#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent 核心功能升级包 v6.0

包含三大核心模块：
1. StorySessionBinder - 会话与StoryTree绑定管理器
2. DataCompressor - 内存优化与数据压缩系统
3. KnowledgeBaseManager - 研究者资料管理系统

架构设计：
┌─────────────────────────────────────────────────────────────┐
│                    WAgent v6.0 升级包                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ StorySessionBinder ─┐  ┌─ DataCompressor ─┐       │
│  │ • 会话-StoryTree绑定  │  │ • 数据压缩算法    │       │
│  │ • 同步删除机制        │  │ • 内存优化        │       │
│  │ • 确认提示系统        │  │ • 自动持久化      │       │
│  └──────────────────────┘  └──────────────────┘       │
│                                                             │
│  ┌─ KnowledgeBaseManager ───────────────────────────────┐  │
│  │ • knowledge_base 访问                              │  │
│  │ • 数据支持度判断                                   │  │
│  │ • 扩展资料搜索                                     │  │
│  │ • 分类存储系统                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
"""

import json
import os
import zlib
import gzip
import pickle
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum


# ============================================================================
# 模块1: StorySessionBinder - 会话与StoryTree绑定管理器
# ============================================================================

class BindAction(Enum):
    """绑定操作类型"""
    BIND = "bind"           # 绑定会话到StoryTree
    UNBIND = "unbind"       # 解除绑定
    DELETE = "delete"       # 删除（会话+StoryTree）
    MIGRATE = "migrate"     # 迁移StoryTree到新会话
    BACKUP = "backup"       # 备份绑定关系


@dataclass
class BindingRecord:
    """
    绑定记录
    
    维护会话ID与StoryTree目录之间的映射关系
    """
    session_id: str           # 企业级会话ID (sess_xxx)
    storytree_path: str       # StoryTree物理路径 (stories/story_xxx)
    bound_at: str = ""        # 绑定时间
    unbound_at: str = ""      # 解绑时间
    is_active: bool = True   # 绑定是否有效
    metadata: Dict = field(default_factory=dict)
    record_id: str = ""      # 自动生成的唯一标识
    
    def __post_init__(self):
        if not self.record_id:
            self.record_id = f"bind_{hashlib.md5(f'{self.session_id}:{self.storytree_path}'.encode()).hexdigest()[:12]}"
        if not self.bound_at:
            self.bound_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        result = {
            'record_id': self.record_id,
            'session_id': self.session_id,
            'storytree_path': self.storytree_path,
            'bound_at': self.bound_at,
            'unbound_at': self.unbound_at,
            'is_active': self.is_active,
            'metadata': self.metadata
        }
        return result


@dataclass 
class DeletionPlan:
    """
    删除计划
    
    在执行删除前生成，用于确认提示
    """
    session_id: str
    storytree_path: str
    affected_files: List[str] = field(default_factory=list)  # 受影响的文件列表
    total_size_bytes: int = 0
    chapter_count: int = 0
    has_backup: bool = False
    consequences: List[str] = field(default_factory=list)
    
    def generate_summary(self) -> str:
        """生成删除摘要（用于用户确认）"""
        size_mb = self.total_size_bytes / (1024 * 1024)
        
        lines = [
            "=" * 60,
            "⚠️  删除操作确认",
            "=" * 60,
            "",
            f"[bold red]会话ID:[/bold red] {self.session_id}",
            f"[bold red]StoryTree:[/bold red] {Path(self.storytree_path).name}",
            "",
            "[yellow]影响范围:[/yellow]",
            f"  📁 文件数量: {len(self.affected_files)} 个",
            f"  💾 总大小: {size_mb:.2f} MB",
            f"  📝 章节数量: {self.chapter_count} 章",
            "",
            "[red]操作后果:[/red]"
        ]
        
        for i, consequence in enumerate(self.consequences, 1):
            lines.append(f"  {i}. {consequence}")
        
        if self.has_backup:
            lines.append("")
            lines.append("[green]✓ 已创建安全备份[/green]")
        else:
            lines.append("")
            lines.append("[yellow]⚠ 将永久删除，无法恢复[/yellow]")
        
        lines.extend([
            "",
            "输入 [bold green]yes[/bold green] 确认删除",
            "输入 [bold]no[/bold] 或其他内容取消",
            "=" * 60
        ])
        
        return "\n".join(lines)


class StorySessionBinder:
    """
    会话与StoryTree绑定管理器
    
    核心功能：
    1. 建立会话与StoryTree的强关联
    2. 同步删除机制（删除会话时同时清理StoryTree）
    3. 操作前确认提示系统
    4. 绑定关系持久化存储
    """
    
    def __init__(self, base_dir: str = "stories",
                 binding_file: str = "_session_bindings.json"):
        self.base_dir = Path(base_dir)
        self.binding_file = self.base_dir / binding_file  # 相对于base_dir的绝对路径
        self.bindings: Dict[str, BindingRecord] = {}  # session_id -> BindingRecord

        # 加载已有绑定
        self._load_bindings()
    
    def _load_bindings(self):
        """从磁盘加载绑定记录"""
        if self.binding_file.exists():
            try:
                with open(self.binding_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for sid, bdata in data.items():
                    binding = BindingRecord(**bdata)
                    self.bindings[sid] = binding
                    
            except Exception as e:
                pass
    
    def _save_bindings(self):
        """保存绑定记录到磁盘"""
        data = {
            sid: bind.to_dict() 
            for sid, bind in self.bindings.items()
        }
        
        with open(self.binding_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def bind(self, session_id: str, storytree_path: str, 
             metadata: Optional[Dict] = None) -> BindingRecord:
        """
        绑定会话到StoryTree
        
        Args:
            session_id: 企业级会话ID
            storytree_path: StoryTree目录路径 (相对或绝对)
            metadata: 额外元数据
            
        Returns:
            创建的BindingRecord
        """
        path_obj = Path(storytree_path)
        if not path_obj.is_absolute():
            path_obj = self.base_dir / path_obj
        
        binding = BindingRecord(
            session_id=session_id,
            storytree_path=str(path_obj),
            metadata=metadata or {}
        )
        
        self.bindings[session_id] = binding
        self._save_bindings()
        
        return binding
    
    def unbind(self, session_id: str) -> bool:
        """
        解除绑定（不删除任何数据）
        
        Returns:
            是否成功解绑
        """
        if session_id not in self.bindings:
            return False
        
        binding = self.bindings[session_id]
        binding.is_active = False
        binding.unbound_at = datetime.now().isoformat()
        
        del self.bindings[session_id]
        self._save_bindings()
        
        return True
    
    def get_binding(self, session_id: str) -> Optional[BindingRecord]:
        """获取绑定记录"""
        return self.bindings.get(session_id)
    
    def get_storytree_by_session(self, session_id: str) -> Optional[str]:
        """通过会话ID获取StoryTree路径"""
        binding = self.bindings.get(session_id)
        return binding.storytree_path if binding and binding.is_active else None
    
    def get_session_by_storytree(self, storytree_path: str) -> Optional[str]:
        """通过StoryTree路径获取会话ID"""
        # 先尝试直接匹配
        for sid, binding in self.bindings.items():
            if binding.is_active and binding.storytree_path == storytree_path:
                return sid
            if binding.is_active and binding.storytree_path.endswith(storytree_path):
                return sid

        # 再尝试解析后的绝对路径匹配（相对于base_dir）
        path_obj = Path(storytree_path)
        if not path_obj.is_absolute():
            path_obj = self.base_dir / path_obj

        resolved_input = path_obj.resolve()

        for sid, binding in self.bindings.items():
            if binding.is_active:
                try:
                    stored_path = Path(binding.storytree_path).resolve()
                    if resolved_input == stored_path:
                        return sid
                except:
                    continue

        return None
    
    def create_deletion_plan(self, session_id: str) -> Optional[DeletionPlan]:
        """
        创建删除计划（用于用户确认）
        
        分析将要被删除的所有内容并生成详细报告
        """
        binding = self.bindings.get(session_id)
        if not binding:
            return None
        
        storytree_path = Path(binding.storytree_path)
        
        if not storytree_path.exists():
            return DeletionPlan(
                session_id=session_id,
                storytree_path=binding.storytree_path,
                consequences=["StoryTree目录不存在，无需删除"]
            )
        
        plan = DeletionPlan(
            session_id=session_id,
            storytree_path=binding.storytree_path
        )
        
        # 遍历所有受影响的文件
        for file_path in storytree_path.rglob('*'):
            if file_path.is_file() and '_backup' not in str(file_path):
                rel_path = file_path.relative_to(storytree_path)
                plan.affected_files.append(str(rel_path))
                plan.total_size_bytes += file_path.stat().st_size
                
                # 统计章节数
                if 'chap_' in file_path.name and file_path.suffix == '.md':
                    plan.chapter_count += 1
        
        # 生成后果列表
        plan.consequences = [
            f"删除会话 {session_id} 及其所有关联数据",
            f"永久删除 StoryTree 目录: {storytree_path.name}",
            f"丢失 {plan.chapter_count} 个已写章节",
            f"释放 {plan.total_size_bytes / (1024*1024):.2f} MB 磁盘空间"
        ]
        
        # 检查是否有备份
        backup_dir = storytree_path.parent / "_archive"
        plan.has_backup = backup_dir.exists()
        
        if plan.has_backup:
            plan.consequences.insert(0, "备份已存在于 _archive/ 目录中")
        
        return plan
    
    def execute_deletion(self, session_id: str, 
                         confirm_callback: Optional[Callable[[DeletionPlan], bool]] = None) -> Tuple[bool, str]:
        """
        执行删除操作（带确认机制）
        
        Args:
            session_id: 要删除的会话ID
            confirm_callback: 自定义确认回调（返回True则继续删除）
            
        Returns:
            (是否成功, 消息)
        """
        plan = self.create_deletion_plan(session_id)
        
        if not plan:
            return False, "未找到该会话的绑定记录"
        
        # 调用确认回调（如果提供）
        if confirm_callback:
            if not confirm_callback(plan):
                return False, "用户取消删除操作"
        
        try:
            storytree_path = Path(plan.storytree_path)
            
            # 1. 先备份（如果还没有的话）
            if not plan.has_backup:
                archive_dir = storytree_path.parent / "_archive"
                archive_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"{storytree_path.name}_deleted_{timestamp}"
                shutil.copytree(storytree_path, archive_dir / backup_name)
            
            # 2. 解除绑定
            self.unbind(session_id)
            
            # 3. 删除StoryTree目录
            if storytree_path.exists():
                shutil.rmtree(storytree_path)
            
            return True, f"成功删除会话 {session_id} 及其 StoryTree"
            
        except Exception as e:
            return False, f"删除失败: {str(e)}"
    
    def list_all_bindings(self, active_only: bool = True) -> List[BindingRecord]:
        """列出所有绑定"""
        bindings = list(self.bindings.values())
        
        if active_only:
            bindings = [b for b in bindings if b.is_active]
        
        return sorted(bindings, key=lambda x: x.bound_at, reverse=True)
    
    def migrate_storytree(self, old_session_id: str, new_session_id: str) -> bool:
        """
        迁移StoryTree到新会话
        
        用于会话切换时保持StoryTree关联
        """
        old_binding = self.bindings.get(old_session_id)
        if not old_binding:
            return False
        
        # 创建新绑定
        self.bind(new_session_id, old_binding.storytree_path, {
            'migrated_from': old_session_id,
            'migrated_at': datetime.now().isoformat()
        })
        
        # 解除旧绑定
        self.unbind(old_session_id)
        
        return True


# ============================================================================
# 模块2: DataCompressor - 内存优化与数据压缩系统
# ============================================================================

class CompressionLevel(Enum):
    """压缩级别"""
    NONE = 0          # 不压缩
    FAST = 1          # 快速压缩（速度优先）
    BALANCED = 6      # 平衡模式（推荐）
    MAXIMUM = 9       # 最大压缩（空间优先）


@dataclass
class CompressedData:
    """压缩后的数据对象"""
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    algorithm: str = "zlib"
    checksum_original: str = ""
    checksum_compressed: str = ""
    compressed_data: bytes = b""
    timestamp: str = ""
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.original_size > 0:
            self.compression_ratio = self.compressed_size / self.original_size

    @property
    def space_saved(self) -> int:
        """节省的空间（字节）"""
        return self.original_size - self.compressed_size

    @property
    def savings_percent(self) -> float:
        """空间节省百分比"""
        if self.original_size == 0:
            return 0.0
        return (1 - self.compression_ratio) * 100

    def to_dict(self) -> dict:
        """转换为字典（排除bytes字段）"""
        return {
            'original_size': self.original_size,
            'compressed_size': self.compressed_size,
            'compression_ratio': self.compression_ratio,
            'algorithm': self.algorithm,
            'checksum_original': self.checksum_original,
            'checksum_compressed': self.checksum_compressed,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
            'has_compressed_data': len(self.compressed_data) > 0
        }

    def decompress(self) -> Any:
        """解压数据"""
        try:
            if self.algorithm == "zlib":
                data = zlib.decompress(self.compressed_data)
            elif self.algorithm == "gzip":
                data = gzip.decompress(self.compressed_data)
            elif self.algorithm == "pickle+zlib":
                data = pickle.loads(zlib.decompress(self.compressed_data))
            else:
                raise ValueError(f"未知算法: {self.algorithm}")

            # 验证校验和
            if self.checksum_original:
                current_checksum = hashlib.md5(data).hexdigest()
                if current_checksum != self.checksum_original:
                    raise ValueError("数据完整性校验失败")

            return json.loads(data.decode('utf-8'))

        except Exception as e:
            raise RuntimeError(f"解压失败: {str(e)}")


@dataclass
class CompressionStats:
    """压缩统计信息"""
    total_original_bytes: int = 0
    total_compressed_bytes: int = 0
    total_files: int = 0
    compression_time_seconds: float = 0.0
    
    @property
    def overall_ratio(self) -> float:
        if self.total_original_bytes == 0:
            return 0.0
        return self.total_compressed_bytes / self.total_original_bytes
    
    @property
    def space_saved_mb(self) -> float:
        return (self.total_original_bytes - self.total_compressed_bytes) / (1024 * 1024)


class DataCompressor:
    """
    数据压缩与内存优化管理器
    
    功能：
    1. 多种压缩算法支持（zlib/gzip/pickle）
    2. 可配置的压缩级别
    3. 数据完整性验证（MD5校验和）
    4. 批量压缩与解压
    5. 自动退出处理
    """
    
    def __init__(self, default_level: CompressionLevel = CompressionLevel.BALANCED):
        self.default_level = default_level
        self.stats = CompressionStats()
    
    def compress_data(self, data: Any, 
                       level: Optional[CompressionLevel] = None,
                       algorithm: str = "zlib") -> CompressedData:
        """
        压缩数据
        
        Args:
            data: 要压缩的数据（通常是字典或列表）
            level: 压缩级别
            algorithm: 压缩算法 (zlib/gzip/pickle+zlib)
            
        Returns:
            CompressedData对象
        """
        start_time = datetime.now()
        
        # 序列化
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        elif isinstance(data, str):
            json_str = data.encode('utf-8')
        elif isinstance(data, bytes):
            json_str = data
        else:
            json_str = pickle.dumps(data)
            algorithm = "pickle+zlib"
        
        original_size = len(json_str)
        checksum_original = hashlib.md5(json_str).hexdigest()
        
        # 选择压缩级别
        comp_level = (level or self.default_level).value
        
        # 执行压缩
        if algorithm == "zlib":
            compressed = zlib.compress(json_str, level=comp_level)
        elif algorithm == "gzip":
            compressed = gzip.compress(json_str, compresslevel=comp_level)
        elif algorithm == "pickle+zlib":
            compressed = zlib.compress(pickle.dumps(data), level=comp_level)
        else:
            raise ValueError(f"不支持算法: {algorithm}")
        
        compressed_size = len(compressed)
        checksum_compressed = hashlib.md5(compressed).hexdigest()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # 更新统计
        self.stats.total_original_bytes += original_size
        self.stats.total_compressed_bytes += compressed_size
        self.stats.total_files += 1
        self.stats.compression_time_seconds += duration
        
        return CompressedData(
            original_size=original_size,
            compressed_size=compressed_size,
            algorithm=algorithm,
            checksum_original=checksum_original,
            checksum_compressed=checksum_compressed,
            compressed_data=compressed,
            metadata={'compression_level': comp_level}
        )
    
    def compress_file(self, file_path: Path, 
                        output_path: Optional[Path] = None,
                        level: Optional[CompressionLevel] = None) -> Tuple[bool, CompressedData]:
        """
        压缩文件
        
        Returns:
            (是否成功, CompressedData对象)
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            compressed = self.compress_data(data, level=level)
            
            out_path = output_path or file_path.with_suffix('.compressed')
            
            with open(out_path, 'wb') as f:
                f.write(compressed.compressed_data)
            
            # 保存元数据
            meta_path = out_path.with_suffix('.meta.json')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({
                    **compressed.to_dict(),
                    'original_file': str(file_path),
                    'compressed_file': str(out_path)
                }, f, ensure_ascii=False, indent=2, default=str)
            
            return True, compressed
            
        except Exception as e:
            return False, CompressedData(metadata={'error': str(e)})
    
    def batch_compress_directory(self, directory: Path, 
                                  pattern: str = "*.json",
                                  level: Optional[CompressionLevel] = None) -> List[Tuple[Path, CompressedData]]:
        """批量压缩目录中的文件"""
        results = []
        
        for file_path in directory.rglob(pattern):
            success, compressed = self.compress_file(file_path, level=level)
            if success:
                results.append((file_path, compressed))
        
        return results
    
    def save_compressed_to_disk(self, data: Any, 
                                save_path: Path,
                                level: Optional[CompressionLevel] = None) -> CompressedData:
        """
        压缩数据并保存到磁盘
        
        用于程序退出时的自动数据处理
        """
        compressed = self.compress_data(data, level)
        
        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存压缩数据
        with open(save_path, 'wb') as f:
            f.write(compressed.compressed_data)
        
        # 保存元数据
        meta_path = save_path.with_suffix('.meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(compressed.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        
        return compressed
    
    def load_from_disk(self, save_path: Path) -> Any:
        """从磁盘加载并解压数据"""
        meta_path = save_path.with_suffix('.meta.json')

        # 读取元数据
        if meta_path.exists():
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # 过滤掉非数据类字段（如has_compressed_data）
            valid_fields = {k: v for k, v in meta.items()
                          if k in ['original_size', 'compressed_size', 'compression_ratio',
                                  'algorithm', 'checksum_original', 'checksum_compressed',
                                  'timestamp', 'metadata']}
            compressed = CompressedData(**valid_fields)
            compressed.compressed_data = open(save_path, 'rb').read()

            return compressed.decompress()
        else:
            # 尝试直接解压
            compressed_data = open(save_path, 'rb').read()
            compressed = CompressedData(compressed_data=compressed_data)
            return compressed.decompress()
    
    def get_stats_report(self) -> Dict:
        """获取压缩统计报告"""
        return {
            'total_files': self.stats.total_files,
            'total_original_mb': self.stats.total_original_bytes / (1024*1024),
            'total_compressed_mb': self.stats.total_compressed_bytes / (1024*1024),
            'space_saved_mb': self.stats.space_saved_mb,
            'overall_ratio': f"{self.stats.overall_ratio:.1%}",
            'savings_percent': f"{(1-self.stats.overall_ratio)*100:.1f}%",
            'avg_compression_time': f"{self.stats.compression_time_seconds/max(1,self.stats.total_files):.3f}s"
        }
    
    def optimize_memory_usage(self, data_dict: Dict[str, Any],
                               threshold_kb: int = 100) -> Dict[str, Any]:
        """
        优化内存使用：自动压缩大对象
        
        Args:
            data_dict: 包含可能的大对象的字典
            threshold_kb: 超过此大小的对象将被压缩（KB）
            
        Returns:
            优化后的字典（大对象替换为CompressedData占位符）
        """
        optimized = {}
        large_objects = {}
        
        for key, value in data_dict.items():
            # 估算大小
            try:
                size = len(json.dumps(value, ensure_ascii=False, default=str).encode('utf-8'))
                size_kb = size / 1024
                
                if size_kb > threshold_kb:
                    # 压缩大对象
                    compressed = self.compress_data(value)
                    
                    optimized[key] = {
                        '__compressed__': True,
                        'original_type': type(value).__name__,
                        'compressed_ref': id(compressed),  # 防止GC回收
                        'metadata': compressed.to_dict()
                    }
                    large_objects[key] = compressed
                else:
                    optimized[key] = value
            except:
                optimized[key] = value
        
        return optimized


# ============================================================================
# 模块3: KnowledgeBaseManager - 研究者资料管理系统
# ============================================================================

class KnowledgeCategory(Enum):
    """知识分类"""
    GENERAL = "general"           # 通用知识
    SCIENCE_FICTION = "sci_fi"   # 科幻
    MYSTERY = "mystery"           # 悬疑
    ROMANCE = "romance"           # 言情
    HISTORY = "history"           # 历史
    TECHNOLOGY = "technology"     # 科技
    CULTURE = "culture"           # 文化
    PSYCHOLOGY = "psychology"     # 心理学
    CRIME = "crime"               # 犯罪
    FANTASY = "fantasy"           # 奇幻
    OTHER = "other"               # 其他


class SupportLevel(Enum):
    """数据支持度等级"""
    FULL_SUPPORT = "full_support"         # 完全支持
    PARTIAL_SUPPORT = "partial_support" # 部分支持
    MINIMAL_SUPPORT = "minimal_support" # 最小支持
    NO_DATA = "no_data"                  # 无数据
    NEEDS_EXPANSION = "needs_expansion"  # 需要扩展


@dataclass
class KnowledgeEntry:
    """知识库条目"""
    title: str
    content_summary: str
    category: KnowledgeCategory
    tags: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    size_bytes: int = 0
    relevance_score: float = 0.0  # 相关性评分 (0-1)
    entry_id: str = ""  # 自动生成的唯一标识
    
    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = f"kb_{hashlib.md5(str(self.title + str(datetime.now())).encode()).hexdigest()[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = datetime.now().isoformat()
        self.access_count += 1
    
    def to_dict(self) -> dict:
        result = asdict(self)
        result['category'] = self.category.value
        return result


@dataclass
class SupportAssessment:
    """支持度评估结果"""
    genre: str                          # 故事题材
    support_level: SupportLevel         # 支持等级
    matched_entries: List[KnowledgeEntry] = field(default_factory=list)
    missing_areas: List[str] = field(default_factory=list)  # 缺失领域
    confidence: float = 0.0              # 评估置信度 (0-1)
    recommendations: List[str] = field(default_factory=list)
    needs_expansion: bool = False       # 是否需要扩展搜索
    
    def to_report(self) -> str:
        """生成可读的报告"""
        level_icons = {
            SupportLevel.FULL_SUPPORT: '✅',
            SupportLevel.PARTIAL_SUPPORT: '🟡',
            SupportLevel.MINIMAL_SUPPORT: '🟠',
            SupportLevel.NO_DATA: '❌',
            SupportLevel.NEEDS_EXPANSION: '🔄'
        }
        
        icon = level_icons.get(self.support_level, '?')
        
        lines = [
            f"\n{'='*60}",
            f"📚 知识支持度评估报告",
            f"{'='*60}",
            f"",
            f"[bold]题材:[/bold] {self.genre}",
            f"[bold]支持等级:[/bold] {icon} {self.support_level.value}",
            f"[bold]置信度:[/bold] {self.confidence:.0%}",
            f""
        ]
        
        if self.matched_entries:
            lines.append("[green]匹配的知识条目:[/green]")
            for i, entry in enumerate(self.matched_entries[:10], 1):
                lines.append(f"  {i}. [{entry.category.value}] {entry.title}")
                if len(self.matched_entries) > 10:
                    lines.append(f"  ... 还有 {len(self.matched_entries)-10} 条")
            lines.append("")
        
        if self.missing_areas:
            lines.append("[yellow]缺失领域:[/yellow]")
            for area in self.missing_areas[:5]:
                lines.append(f"  ⚠️ {area}")
            lines.append("")
        
        if self.recommendations:
            lines.append("[cyan]建议:[/cyan]")
            for rec in self.recommendations[:5]:
                lines.append(f"  → {rec}")
            lines.append("")
        
        if self.needs_expansion:
            lines.append("[blue]ℹ️ 建议触发扩展资料搜索[/blue]")
        
        lines.append(f"{'='*60}\n")
        
        return "\n".join(lines)


class KnowledgeBaseManager:
    """
    研究者资料管理系统
    
    功能：
    1. 访问 knowledge_base 目录
    2. 数据支持度判断逻辑
    3. 扩展资料搜索流程
    4. 分类存储系统
    """
    
    def __init__(self, base_path: str = "knowledge_base"):
        self.base_path = Path(base_path)
        self.entries: Dict[str, KnowledgeEntry] = {}  # entry_id -> KnowledgeEntry
        self.categories: Dict[KnowledgeCategory, List[KnowledgeEntry]] = {
            cat: [] for cat in KnowledgeCategory
        }
        
        # 题材关键词映射
        self.genre_keywords = {
            '科幻': ['科幻', '未来', '太空', '机器人', 'AI', '科技', '外星', '时间旅行'],
            '悬疑': ['悬疑', '推理', '侦探', '犯罪', '谜团', '秘密', '真相'],
            '言情': ['言情', '爱情', '浪漫', '感情', '恋爱', '婚姻'],
            '历史': ['历史', '古代', '朝代', '战争', '宫廷', '皇帝'],
            '奇幻': ['奇幻', '魔法', '龙', '精灵', '巫师', '冒险', '异世界'],
            '恐怖': ['恐怖', '惊悚', '鬼魂', '僵尸', '怪物', '超自然'],
            '武侠': ['武侠', '江湖', '功夫', '门派', '剑客', '内功'],
            '都市': ['都市', '现代', '职场', '商战', '官场', '生活']
        }
        
        # 加载现有知识库
        self._scan_knowledge_base()
    
    def _scan_knowledge_base(self):
        """扫描knowledge_base目录加载现有数据"""
        if not self.base_path.exists():
            return
        
        # 扫描所有JSON文件
        for json_file in self.base_path.rglob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 可能是单个条目或条目数组
                entries_data = data if isinstance(data, list) else [data]
                
                for entry_data in entries_data:
                    try:
                        category = KnowledgeCategory(entry_data.get('category', 'other'))
                        
                        entry = KnowledgeEntry(
                            title=entry_data.get('title', ''),
                            content_summary=entry_data.get('content_summary', entry_data.get('summary', '')),
                            category=category,
                            tags=entry_data.get('tags', []),
                            source_url=entry_data.get('source'),
                            size_bytes=len(json.dumps(entry_data, ensure_ascii=False).encode('utf-8'))
                        )
                        
                        self.entries[entry.entry_id] = entry
                        self.categories[category].append(entry)
                        
                    except Exception as e:
                        pass
                        
            except Exception as e:
                pass
    
    def assess_support(self, story_genre: str, 
                       story_requirements: List[str]) -> SupportAssessment:
        """
        评估知识库对指定故事的支持程度
        
        Args:
            story_genre: 故事题材（如"科幻悬疑"）
            story_requirements: 故事需求列表（如["量子计算", "心理分析"]）
            
        Returns:
            SupportAssessment评估结果
        """
        # 提取题材关键词
        genre_lower = story_genre.lower()
        matched_genres = []
        all_keywords = []
        
        for genre, keywords in self.genre_keywords.items():
            if any(kw in genre_lower for kw in keywords):
                matched_genres.append(genre)
                all_keywords.extend(keywords)
        
        # 如果没有匹配到已知题材，使用整个字符串作为搜索词
        if not matched_genres:
            matched_genres = [story_genre]
            all_keywords = [genre_lower]
        
        # 搜索匹配条目
        matched_entries = []
        missing_areas = []
        
        for entry in self.entries.values():
            score = self._calculate_relevance(entry, story_genre, story_requirements)
            
            if score > 0.3:  # 相关性阈值
                entry.relevance_score = score
                matched_entries.append(entry)
        
        # 按相关性排序
        matched_entries.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # 检查缺失领域
        for req in story_requirements:
            req_found = any(
                req.lower() in (e.content_summary.lower() + ' '.join(e.tags).lower())
                for e in matched_entries[:10]
            )
            if not req_found:
                missing_areas.append(req)
        
        # 确定支持等级
        if len(matched_entries) >= 5 and not missing_areas:
            support_level = SupportLevel.FULL_SUPPORT
        elif len(matched_entries) >= 2 and len(missing_areas) <= 2:
            support_level = SupportLevel.PARTIAL_SUPPORT
        elif len(matched_entries) >= 1:
            support_level = SupportLevel.MINIMAL_SUPPORT
        else:
            support_level = SupportLevel.NO_DATA if not matched_entries else SupportLevel.NEEDS_EXPANSION
        
        # 计算置信度
        coverage = len(missing_areas) / max(len(story_requirements), 1)
        confidence = 1.0 - min(coverage, 1.0)
        
        # 生成建议
        recommendations = []
        if missing_areas:
            for missing_area in missing_areas[:3]:
                recommendations.append(f"建议补充关于'{missing_area}'的研究资料")
        
        if support_level in [SupportLevel.NO_DATA, SupportLevel.NEEDS_EXPANSION]:
            recommendations.append("建议启动扩展资料搜索流程")
            needs_expansion = True
        else:
            needs_expansion = False
        
        return SupportAssessment(
            genre=story_genre,
            support_level=support_level,
            matched_entries=matched_entries,
            missing_areas=missing_areas,
            confidence=confidence,
            recommendations=recommendations,
            needs_expansion=needs_expansion
        )
    
    def _calculate_relevance(self, entry: KnowledgeEntry, 
                             genre: str, requirements: List[str]) -> float:
        """计算条目相关性评分 (0-1)"""
        score = 0.0
        
        # 题材匹配 (权重40%)
        genre_lower = genre.lower()
        title_lower = entry.title.lower()
        summary_lower = entry.content_summary.lower()
        
        for g_kw in self.genre_keywords.values():
            if any(kw in genre_lower for kw in g_kw):
                if any(kw in title_lower or kw in summary_lower for kw in g_kw):
                    score += 0.4
                    break
        
        # 需求匹配 (权重40%)
        if requirements:
            matched_req = sum(
                1 for req in requirements
                if req.lower() in (summary_lower + ' '.join(entry.tags).lower())
            )
            score += (matched_req / len(requirements)) * 0.4
        
        # 访问频率加权 (权重20%)
        if entry.access_count > 0:
            score += min(entry.access_count / 100, 0.2)
        
        return min(score, 1.0)
    
    def search_knowledge(self, query: str,
                           max_results: int = 10,
                           category_filter: Optional[KnowledgeCategory] = None) -> List[KnowledgeEntry]:
        """
        搜索知识库

        Args:
            query: 搜索查询
            max_results: 最大返回数
            category_filter: 分类过滤

        Returns:
            匹配的KnowledgeEntry列表
        """
        query_lower = query.lower() if query else ''
        results = []

        for entry in self.entries.values():
            # 分类过滤
            if category_filter and entry.category != category_filter:
                continue

            # 如果query为空且指定了分类，直接包含该分类所有条目
            if not query_lower and category_filter:
                entry.relevance_score = 1.0
                results.append(entry)
                continue

            # 关键词匹配
            text = f"{entry.title} {entry.content_summary} {' '.join(entry.tags)}".lower()

            score = 0.0
            if query_lower:
                for word in query_lower.split():
                    if word.lower() in text:
                        score += 1.0

            if score > 0:
                entry.relevance_score = min(score / len(query_lower.split()), 1.0)
                results.append(entry)
        
        # 排序并限制数量
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # 更新访问统计
        for entry in results[:max_results]:
            entry.touch()
        
        return results[:max_results]
    
    def add_entry(self, title: str, content: str,
                  category: Union[KnowledgeCategory, str],
                  tags: Optional[List[str]] = None,
                  source: Optional[str] = None) -> KnowledgeEntry:
        """
        添加新的知识条目（自动分类存储）
        
        Args:
            title: 标题
            content: 内容摘要
            category: 分类
            tags: 标签列表
            source: 来源URL
            
        Returns:
            创建的KnowledgeEntry
        """
        if isinstance(category, str):
            # 支持常见别名映射
            category_aliases = {
                'science_fiction': 'sci_fi',
                '科幻': 'sci_fi',
                'sf': 'sci_fi',
                'mystery': 'mystery',
                '悬疑': 'mystery',
                '推理': 'mystery',
                'romance': 'romance',
                '言情': 'romance',
                '爱情': 'romance',
                'history': 'history',
                '历史': 'history',
                '古代': 'history',
                'technology': 'technology',
                '科技': 'technology',
                '技术': 'technology',
                'culture': 'culture',
                '文化': 'culture',
                'psychology': 'psychology',
                '心理学': 'psychology',
                '心理': 'psychology',
                'crime': 'crime',
                '犯罪': 'crime',
                '刑侦': 'crime',
                'fantasy': 'fantasy',
                '奇幻': 'fantasy',
                '魔法': 'fantasy'
            }
            normalized = category.lower().strip()
            category_str = category_aliases.get(normalized, normalized)

            try:
                category = KnowledgeCategory(category_str)
            except ValueError:
                category = KnowledgeCategory.OTHER
        
        entry = KnowledgeEntry(
            title=title,
            content_summary=content[:500] if len(content) > 500 else content,
            category=category,
            tags=tags or [],
            source_url=source,
            size_bytes=len(content.encode('utf-8'))
        )
        
        # 存储到内存
        self.entries[entry.entry_id] = entry
        self.categories[category].append(entry)
        
        # 保存到磁盘
        self._save_entry_to_disk(entry)
        
        return entry
    
    def _save_entry_to_disk(self, entry: KnowledgeEntry):
        """保存条目到磁盘（按分类存储）"""
        category_dir = self.base_path / entry.category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = "".join(c if c.isalnum() or c in '-_ ' else '_' for c in entry.title[:50])
        filename = f"{safe_title}_{entry.entry_id}.json"
        
        filepath = category_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2, default=str)
    
    def get_statistics(self) -> Dict:
        """获取知识库统计信息"""
        return {
            'total_entries': len(self.entries),
            'categories': {
                cat.value: len(entries) 
                for cat, entries in self.categories.items()
            },
            'total_size_kb': sum(e.size_bytes for e in self.entries.values()) / 1024,
            'most_accessed': sorted(
                self.entries.values(), 
                key=lambda x: x.access_count, 
                reverse=True
            )[:5]
        }
    
    def export_for_researcher(self, assessment: SupportAssessment) -> Dict:
        """
        为研究员导出搜索指令
        
        基于支持度评估结果，生成优化的搜索参数
        """
        search_config = {
            'base_query': assessment.genre,
            'focus_areas': assessment.missing_areas,
            'existing_knowledge': [
                {
                    'title': e.title,
                    'summary': e.content_summary[:200],
                    'relevance': e.relevance_score
                }
                for e in assessment.matched_entries[:5]
            ],
            'search_strategy': 'focused' if assessment.support_level != SupportLevel.NO_DATA else 'broad',
            'max_results': 15 if assessment.needs_expansion else 5,
            'priority_keywords': list(set(
                kw for req in assessment.missing_areas 
                for kw in req.split()
            ))[:10]
        }
        
        return search_config


def create_story_binder(base_dir: str = "stories") -> StorySessionBinder:
    """便捷函数：创建StorySessionBinder"""
    return StorySessionBinder(base_dir=base_dir)

def create_compressor(level: CompressionLevel = CompressionLevel.BALANCED) -> DataCompressor:
    """便捷函数：创建DataCompressor"""
    return DataCompressor(default_level=level)

def create_knowledge_manager(base_path: str = "knowledge_base") -> KnowledgeBaseManager:
    """便捷函数：创建KnowledgeBaseManager"""
    return KnowledgeBaseManager(base_path=base_path)


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 WAgent v6.0 核心升级模块测试")
    print("=" * 70)
    
    print("\n1️⃣ 测试 StorySessionBinder...")
    binder = create_story_binder("_test_bind")
    
    bind1 = binder.bind("sess_test_001", "stories/test_story_001", {"test": True})
    print(f"   ✅ 绑定成功: {bind1.session_id} → {bind1.storytree_path}")
    
    plan = binder.create_deletion_plan("sess_test_001")
    print(f"   ✅ 删除计划: {len(plan.affected_files)} 文件将受影响")
    
    unbind_ok = binder.unbind("sess_test_001")
    print(f"   ✅ 解绑成功: {unbind_ok}")
    
    print("\n2️⃣ 测试 DataCompressor...")
    compressor = create_compressor()
    
    test_data = {
        'title': '测试故事',
        'chapters': [{'num': 1, 'content': 'x' * 10000}],
        'metadata': {'genre': '科幻', 'tags': ['AI']}
    }
    
    compressed = compressor.compress_data(test_data)
    print(f"   ✅ 压缩完成: {compressed.original_size//1024}KB → {compressed.compressed_size//1024}KB ({compressed.savings_percent:.1f}% 节省)")
    
    restored = compressed.decompress()
    assert restored['title'] == test_data['title']
    print(f"   ✅ 解压验证通过: 数据完整")
    
    stats = compressor.get_stats_report()
    print(f"   ✅ 统计: {stats['savings_percent']} 空间节省")
    
    print("\n3️⃣ 测试 KnowledgeBaseManager...")
    kb_mgr = create_knowledge_manager("_test_knowledge")
    
    kb_mgr.add_entry("量子计算基础", "量子比特、叠加态、量子纠缠等概念", "science_fiction", ["量子", "物理"])
    kb_mgr.add_entry("犯罪心理学", "罪犯心理画像、动机分析方法", "mystery", ["心理学", "犯罪"])
    kb_mgr.add_entry("古代中国史", "从夏朝到清朝的历史变迁", "history", ["历史", "朝代"])
    
    assessment = kb_mgr.assess_support("科幻悬疑", ["量子计算", "心理分析", "未来科技"])
    report = assessment.to_report()
    print(f"   ✅ 支持度评估: {assessment.support_level.value}")
    print(f"   ✅ 匹配条目: {len(assessment.matched_entries)}")
    
    stats = kb_mgr.get_statistics()
    print(f"   ✅ 知识库统计: {stats['total_entries']} 条目")
    
    print("\n" + "=" * 70)
    print("🎉 所有核心模块测试通过!")
    print("=" * 70)
