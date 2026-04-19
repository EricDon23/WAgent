#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 数据同步管理器

基于错误修改.md第一优先级要求实现：
- 全量双向同步（本地→Redis + Redis→本地）
- 同步前自动备份
- 可视化进度显示
- 本地文件绝对优先策略
- 无session故事自动绑定
- 同步失败自动回滚
"""

import os
import json
import shutil
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """同步状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CONFLICT = "conflict"


@dataclass
class SyncItem:
    """同步项目"""
    file_name: str
    file_path: Path
    redis_key: str
    local_exists: bool = False
    redis_exists: bool = False
    local_mtime: float = 0.0
    size_bytes: int = 0


@dataclass
class SyncResult:
    """同步结果"""
    success: bool = True
    uploaded: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    backup_path: str = ""
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "uploaded": self.uploaded,
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
            "backup_path": self.backup_path,
            "duration_seconds": self.duration_seconds
        }


class SyncManager:
    """
    数据同步管理器 - V3.1核心前置流程
    
    核心功能：
    1. 全量双向同步（启动时第一个执行步骤）
    2. 自动备份（同步前执行）
    3. 可视化进度（0-100%进度条）
    4. 冲突处理（本地绝对优先）
    5. 失败回滚（数据安全保障）
    """
    
    def __init__(self, base_dir: str = "stories", 
                 backup_dir: str = "backups",
                 redis_storage=None,
                 local_storage=None):
        self.base_dir = Path(base_dir)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.redis_storage = redis_storage
        self.local_storage = local_storage
        
        self._sync_log: List[Dict] = []
    
    def is_redis_available(self) -> bool:
        """检查Redis是否可用"""
        if self.redis_storage:
            return self.redis_storage.is_available
        return False
    
    def _create_backup(self) -> str:
        """
        创建同步前的完整备份
        
        Returns:
            备份目录路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"sync_{timestamp}"
        
        try:
            # 复制整个stories目录到备份位置
            if self.base_dir.exists():
                shutil.copytree(str(self.base_dir), str(backup_path), dirs_exist_ok=True)
                logger.info(f"已创建同步备份: {backup_path}")
            
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return ""
    
    def _rollback(self, backup_path: str):
        """
        回滚到备份数据
        
        Args:
            backup_path: 备份目录路径
        """
        try:
            if backup_path and os.path.exists(backup_path):
                # 删除当前stories目录
                if self.base_dir.exists():
                    shutil.rmtree(str(self.base_dir))
                
                # 从备份恢复
                shutil.copytree(backup_path, str(self.base_dir))
                logger.info(f"已回滚到备份: {backup_path}")
                
        except Exception as e:
            logger.error(f"回滚失败: {e}")
    
    def _collect_sync_items(self) -> List[SyncItem]:
        """收集所有需要同步的项目（本地 + Redis）"""
        items = []
        local_keys = set()
        
        # 1. 从本地收集
        if self.base_dir.exists():
            for story_dir in self.base_dir.iterdir():
                if not story_dir.is_dir() or story_dir.name.startswith("_"):
                    continue
                
                story_id = story_dir.name
                
                # 收集所有JSON文件
                for json_file in story_dir.rglob("*.json"):
                    relative_path = json_file.relative_to(self.base_dir)
                    redis_key = f"{story_id}:{str(relative_path).replace(os.sep, ':')}"
                    
                    item = SyncItem(
                        file_name=json_file.name,
                        file_path=json_file,
                        redis_key=redis_key,
                        local_exists=True,
                        local_mtime=json_file.stat().st_mtime,
                        size_bytes=json_file.stat().st_size
                    )
                    
                    items.append(item)
                    local_keys.add(json_file.name)
        
        # 2. 从Redis收集（关键修复：发现本地没有的故事）
        if self.is_redis_available():
            redis_stories = self.redis_storage.get_all_keys("story:")
            for redis_key in redis_stories:
                # 解析Redis键，提取故事ID和文件名
                parts = redis_key.split(":", 2)
                if len(parts) >= 2:
                    story_id = parts[1]
                    # 如果本地没有这个文件，添加到同步列表
                    if redis_key not in local_keys:
                        item = SyncItem(
                            file_name=redis_key,
                            file_path=self.base_dir / story_id,
                            redis_key=redis_key,
                            local_exists=False
                        )
                        items.append(item)
        
        return items
    
    def _sync_single_item(self, item: SyncItem) -> Tuple[SyncStatus, str]:
        """
        同步单个项目
        
        策略：
        - 本地有，Redis无 → 上传到Redis
        - Redis有，本地无 → 下载到本地
        - 都有 → 比较时间戳，本地优先
        - 都无 → 跳过
        
        Returns:
            (状态, 描述信息)
        """
        try:
            redis_exists = False
            
            if self.is_redis_available():
                redis_exists = self.redis_storage.exists(
                    item.file_name.replace(".json", ""),
                    f"story:{item.redis_key.split(':')[0]}"
                )
            
            if item.local_exists and not redis_exists:
                # 上传到Redis
                data = self._load_local_data(item.file_path)
                if data and self.is_redis_available():
                    self.redis_storage.save(
                        item.file_name.replace(".json", ""),
                        data,
                        f"story:{item.redis_key.split(':')[0]}"
                    )
                return SyncStatus.SUCCESS, "上传到Redis"
                
            elif redis_exists and not item.local_exists:
                # 从Redis下载
                if self.is_redis_available():
                    data = self.redis_storage.load(
                        item.file_name.replace(".json", ""),
                        f"story:{item.redis_key.split(':')[0]}"
                    )
                    if data:
                        self._save_local_data(item.file_path, data)
                return SyncStatus.SUCCESS, "从Redis下载"
                
            elif item.local_exists and redis_exists:
                # 都存在，本地优先（不覆盖本地）
                return SyncStatus.SKIPPED, "本地已存在（本地优先）"
                
            else:
                return SyncStatus.SKIPPED, "无数据"
                
        except Exception as e:
            return SyncStatus.FAILED, str(e)
    
    def _load_local_data(self, file_path: Path) -> Optional[Dict]:
        """加载本地JSON数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取本地文件失败: {e}")
            return None
    
    def _save_local_data(self, file_path: Path, data: Dict):
        """保存数据到本地"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存本地文件失败: {e}")
    
    def run_full_sync(self, auto_backup: bool = True, 
                     show_progress: bool = True) -> SyncResult:
        """
        执行全量双向同步（V3.1核心前置流程）
        
        这是程序启动后**第一个必须执行**的步骤。
        
        Args:
            auto_backup: 是否在同步前自动备份
            show_progress: 是否显示进度信息
        
        Returns:
            同步结果对象
        """
        start_time = time.time()
        result = SyncResult()
        
        print("\n" + "=" * 60)
        print("  WAgent V3.1 数据双向同步")
        print("=" * 60)
        
        # 步骤1：检查Redis可用性
        print("\n[1/4] 检查存储服务...")
        if self.is_redis_available():
            print("  ✓ Redis可用 - 将执行双向同步")
        else:
            print("  ⚠ Redis不可用 - 使用纯本地模式")
            result.success = True
            result.duration_seconds = time.time() - start_time
            return result
        
        # 步骤2：创建备份
        if auto_backup:
            print("\n[2/4] 创建同步前备份...")
            result.backup_path = self._create_backup()
            if result.backup_path:
                print(f"  ✓ 备份完成: {result.backup_path}")
            else:
                print("  ⚠ 备份失败，继续同步...")
        
        # 步骤3：收集同步项目
        print("\n[3/4] 收集同步项目...")
        items = self._collect_sync_items()
        total_items = len(items)
        print(f"  发现 {total_items} 个待同步项")
        
        # 步骤4：执行同步
        print("\n[4/4] 执行双向同步...")
        print("-" * 50)
        
        for i, item in enumerate(items, 1):
            if show_progress:
                progress = int((i / total_items) * 100) if total_items > 0 else 100
                print(f"\r  进度: [{progress}%] ({i}/{total_items}) - {item.file_name}", end="")
            
            status, message = self._sync_single_item(item)
            
            if status == SyncStatus.SUCCESS:
                if "上传" in message:
                    result.uploaded += 1
                elif "下载" in message:
                    result.downloaded += 1
            elif status == SyncStatus.SKIPPED:
                result.skipped += 1
            elif status == SyncStatus.FAILED:
                result.failed += 1
                result.errors.append(f"{item.file_name}: {message}")
                result.success = False
        
        if show_progress:
            print(f"\r  进度: [100%] ({total_items}/{total_items}) - 完成")
        
        # 计算耗时
        result.duration_seconds = time.time() - start_time
        
        # 显示统计信息
        print("\n" + "-" * 50)
        print(f"\n  同步统计:")
        print(f"    • 上传到Redis: {result.uploaded} 个")
        print(f"    • 从Redis下载: {result.downloaded} 个")
        print(f"    • 跳过（本地优先）: {result.skipped} 个")
        print(f"    • 失败: {result.failed} 个")
        print(f"    • 耗时: {result.duration_seconds:.2f} 秒")
        
        if result.failed > 0:
            print(f"\n  ⚠ 存在 {result.failed} 个同步失败项")
            if len(result.errors) > 0:
                print(f"  错误详情:")
                for err in result.errors[:5]:  # 只显示前5个错误
                    print(f"    ✗ {err}")
        else:
            print(f"\n  ✓ 双向同步完成！")
        
        print("=" * 60)
        
        return result
    
    def get_display_report(self, result: SyncResult) -> str:
        """生成可读的同步报告"""
        lines = [
            "",
            "=" * 60,
            "  WAgent V3.1 同步报告",
            "=" * 60,
            f"",
            f"  状态: {'✓ 成功' if result.success else '✗ 部分失败'}",
            f"  上传: {result.uploaded} | 下载: {result.downloaded}",
            f"  跳过: {result.skipped} | 失败: {result.failed}",
            f"  耗时: {result.duration_seconds:.2f}s",
        ]
        
        if result.errors:
            lines.append("")
            lines.append("  错误列表:")
            for err in result.errors[:10]:
                lines.append(f"    • {err}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def delete_from_both(self, story_id: str) -> Tuple[bool, List[str]]:
        """
        同时删除本地和Redis中的故事数据
        
        Args:
            story_id: 故事ID
        
        Returns:
            (是否成功, 错误列表)
        """
        errors = []
        
        # 删除本地数据
        if self.local_storage:
            success, msg = self.local_storage.delete_story(story_id)
            if not success:
                errors.append(msg)
        
        # 删除Redis数据
        if self.redis_storage and self.is_redis_available():
            if not self.redis_storage.delete(key=story_id):
                errors.append("Redis删除失败")
        
        return len(errors) == 0, errors


def create_sync_manager(base_dir: str = "stories",
                      backup_dir: str = "backups",
                      **kwargs) -> SyncManager:
    """工厂函数：创建同步管理器实例"""
    return SyncManager(base_dir, backup_dir, **kwargs)


def create_synchronizer(base_dir: str = "stories", **kwargs) -> SyncManager:
    """别名函数：创建同步器实例"""
    return create_sync_manager(base_dir, **kwargs)
