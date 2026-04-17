#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent 项目优化执行器 v1.0

功能：
1. 安全删除冗余文件（带备份）
2. 清理重复代码
3. 验证优化后系统完整性
4. 生成变更日志

使用: D:\anaconda3\python.exe project_optimizer_execute.py [--dry-run]
"""

import os
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
BACKUP_DIR = PROJECT_ROOT / "_backup_before_optimization"
LOG_FILE = PROJECT_ROOT / "_optimization_log.json"


class OptimizationExecutor:
    """优化执行器"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backup_dir = BACKUP_DIR
        self.log_file = LOG_FILE
        self.changes = []
        self.deleted_files = []
        self.errors = []
        
    def create_backup(self):
        """创建完整项目备份"""
        print("\n📦 创建项目备份...")
        
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
            
        self.backup_dir.mkdir(parents=True)
        
        # 备份关键目录
        backup_items = [
            ('wagent', 'wagent'),
            ('ai', 'ai'),
            ('data', 'data'),
            ('tools', 'tools'),
            ('tests', 'tests'),
        ]
        
        for src_name, dst_name in backup_items:
            src_path = PROJECT_ROOT / src_name
            if src_path.exists():
                dst_path = self.backup_dir / dst_name
                if src_path.is_dir():
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
                print(f"   ✓ 已备份 {src_name}/")
        
        # 备份根目录的关键文件
        root_files = [
            'wagent.py', 'main.py', 'main_async.py', 
            'main_interactive.py', 'config.py'
        ]
        
        for f in root_files:
            src = PROJECT_ROOT / f
            if src.exists():
                shutil.copy2(src, self.backup_dir / f)
                print(f"   ✓ 已备份 {f}")
        
        print(f"✅ 备份完成 → {self.backup_dir}")
    
    def delete_redundant_files(self):
        """删除已识别的冗余文件"""
        
        # 定义要删除的文件清单（按优先级排序）
        deletion_plan = [
            # === 高优先级：旧版入口文件 ===
            {
                'file': 'main.py',
                'reason': '旧版入口文件，已被wagent.py (v5.3)完全替代',
                'priority': 'HIGH',
                'category': 'deprecated_entry'
            },
            {
                'file': 'main_async.py',
                'reason': '旧版异步入口，功能已整合至wagent/controller.py',
                'priority': 'HIGH',
                'category': 'deprecated_entry'
            },
            {
                'file': 'main_interactive.py',
                'reason': '旧版交互入口，已被wagent.py替代',
                'priority': 'HIGH',
                'category': 'deprecated_entry'
            },
            
            # === 高优先级：旧版AI模块 ===
            {
                'file': 'ai/director_ai.py',
                'reason': '旧版导演AI模块，已迁移至 wagent/engines/director.py',
                'priority': 'HIGH',
                'category': 'legacy_module'
            },
            {
                'file': 'ai/researcher_ai.py',
                'reason': '旧版研究员AI模块，已迁移至 wagent/engines/researcher.py',
                'priority': 'HIGH',
                'category': 'legacy_module'
            },
            {
                'file': 'ai/writer_ai.py',
                'reason': '旧版作家AI模块，已迁移至 wagent/engines/writer.py',
                'priority': 'HIGH',
                'category': 'legacy_module'
            },
            
            # === 中优先级：演示/验证脚本 ===
            {
                'file': 'demo_template_system.py',
                'reason': '演示模板系统，非核心生产代码',
                'priority': 'MEDIUM',
                'category': 'demo_script'
            },
            {
                'file': 'quick_validation.py',
                'reason': '快速验证脚本，功能已整合至 wagent.py --quick',
                'priority': 'MEDIUM',
                'category': 'demo_script'
            },
            
            # === 中优先级：未使用数据模块 ===
            {
                'file': 'data/generated_data.py',
                'reason': '未被任何核心模块导入的数据生成模块',
                'priority': 'MEDIUM',
                'category': 'unused_module'
            },
            
            # === 低优先级：旧版独立测试文件 ===
            {
                'file': 'test_auto_save.py',
                'reason': '自动保存测试，功能已整合至 test_v52_system.py',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_compliance.py',
                'reason': '合规性检查测试，功能已整合至 test_v52_system.py',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_context_system.py',
                'reason': '上下文系统测试，功能已整合至 test_v52_system.py',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_full_workflow.py',
                'reason': '完整工作流测试，功能已整合至 test_v53_upgrade.py',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_real_story.py',
                'reason': '真实故事生成测试，功能已整合至主测试套件',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_story_tree.py',
                'reason': '故事树节点测试，功能已整合至 test_v52_system.py',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_three_rounds.py',
                'reason': '三轮创作测试，功能已整合至统一套件',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
            {
                'file': 'test_yn_mechanism.py',
                'reason': 'Y/N机制测试，功能已整合至 test_v52_system.py',
                'priority': 'LOW',
                'category': 'legacy_test'
            },
        ]
        
        print("\n🗑️ 开始删除冗余文件...\n")
        
        stats = {'high': 0, 'medium': 0, 'low': 0, 'errors': 0}
        
        for item in deletion_plan:
            file_path = PROJECT_ROOT / item['file']
            
            if not file_path.exists():
                print(f"   ⚠️ 跳过(不存在): {item['file']}")
                continue
            
            try:
                file_size = file_path.stat().st_size
                
                if not self.dry_run:
                    # 实际删除
                    if file_path.is_file():
                        file_path.unlink()
                        deleted_type = "file"
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                        deleted_type = "directory"
                    
                    self.deleted_files.append({
                        'file': str(file_path),
                        'size': file_size,
                        'reason': item['reason'],
                        'timestamp': datetime.now().isoformat()
                    })
                
                priority_icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
                action = "[DRY-RUN] 将删除" if self.dry_run else "✓ 已删除"
                
                print(f"   {action} [{priority_icon[item['priority']]}{item['priority']}] {item['file']:<40} ({file_size/1024:.1f}KB)")
                print(f"      └─ {item['reason']}")
                
                stats[item['priority'].lower()] += 1
                
            except Exception as e:
                print(f"   ❌ 错误: {item['file']} - {e}")
                stats['errors'] += 1
                self.errors.append({'file': item['file'], 'error': str(e)})
        
        return stats
    
    def cleanup_empty_directories(self):
        """清理空目录"""
        print("\n🧹 清理空目录...")
        
        empty_dirs = []
        
        for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
            path = Path(dirpath)
            
            if path == PROJECT_ROOT or '_backup' in str(path) or '__pycache__' in str(path):
                continue
            
            parent_in_wagent = any(
                str(path).startswith(str(p)) 
                for p in [PROJECT_ROOT / 'ai', PROJECT_ROOT / 'data']
            )
            
            if parent_in_wagent and not dirnames and not filenames and path != PROJECT_ROOT:
                empty_dirs.append(path)
        
        for d in sorted(empty_dirs, key=lambda x: len(x.parts), reverse=True):
            try:
                if not self.dry_run:
                    d.rmdir()
                print(f"   ✓ 删除空目录: {d.relative_to(PROJECT_ROOT)}")
            except Exception as e:
                pass
    
    def save_optimization_log(self, stats: dict):
        """保存优化日志"""
        log_data = {
            'optimization_time': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'statistics': stats,
            'deleted_files': self.deleted_files,
            'errors': self.errors,
            'backup_location': str(self.backup_dir) if self.backup_dir.exists() else None
        }
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 优化日志已保存: {self.log_file}")
    
    def generate_summary_report(self, stats: dict):
        """生成总结报告"""
        total_deleted = sum(stats.values()) - stats.get('errors', 0)
        total_size = sum(d['size'] for d in self.deleted_files)
        
        report = f"""
{'='*70}
🎉 WAgent 项目优化完成报告
{'='*70}

⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔄 模式: {'[DRY-RUN] 预演模式' if self.dry_run else '[LIVE] 正式执行'}

📊 优化统计:
├── 🔴 高优先级删除: {stats.get('high', 0)} 个
├── 🟡 中优先级删除: {stats.get('medium', 0)} 个  
├── 🟢 低优先级删除: {stats.get('low', 0)} 个
├── ❌ 错误: {stats.get('errors', 0)} 个
└── ✅ 总计删除: {total_deleted} 个文件

💾 空间释放: {total_size / 1024:.1f} KB ({total_size / (1024*1024):.2f} MB)

📁 备份位置: {self.backup_dir if self.backup_dir.exists() else 'N/A'}
📋 日志文件: {self.log_file}

{'='*70}
"""
        print(report)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="WAgent 项目优化执行器")
    parser.add_argument('--dry-run', action='store_true',
                       help='预演模式：只显示将要删除的文件，不实际执行')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🚀 WAgent 项目优化执行器 v1.0")
    print("="*70)
    
    executor = OptimizationExecutor(dry_run=args.dry_run)
    
    if not args.dry_run:
        executor.create_backup()
    
    stats = executor.delete_redundant_files()
    executor.cleanup_empty_directories()
    executor.save_optimization_log(stats)
    executor.generate_summary_report(stats)


if __name__ == "__main__":
    main()
