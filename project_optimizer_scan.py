#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent 项目系统性优化分析器

功能：
1. 文件依赖关系扫描
2. 冗余/过时文件识别
3. 重复功能检测
4. 未使用代码识别
5. 生成优化建议报告

运行: D:\anaconda3\python.exe project_optimizer_scan.py
"""

import os
import sys
import re
import ast
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent


class FileAnalyzer:
    """文件内容分析器"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.content = ""
        self.imports = []
        self.classes = []
        self.functions = []
        self.references = set()
        self.is_referenced_by = set()
        
        if filepath.exists() and filepath.suffix == '.py':
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    self.content = f.read()
                self._parse_content()
            except Exception as e:
                print(f"⚠️ 无法读取 {filepath}: {e}")
    
    def _parse_content(self):
        """解析Python文件内容"""
        try:
            tree = ast.parse(self.content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.imports.append(alias.name)
                        
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        self.imports.append(f"{module}.{alias.name}" if alias.name != '*' else module)
                        
                elif isinstance(node, ast.ClassDef):
                    self.classes.append(node.name)
                    
                elif isinstance(node, ast.FunctionDef):
                    self.functions.append(node.name)
                    
        except SyntaxError:
            pass
        
        # 提取字符串中的引用（如文件名、类名等）
        for match in re.finditer(r'[a-zA-Z_][a-zA-Z0-9_]*\.py', self.content):
            self.references.add(match.group(0))
        
        for cls in self.classes:
            self.references.add(cls)
            
        for func in self.functions:
            self.references.add(func)
    
    def is_test_file(self) -> bool:
        """判断是否为测试文件"""
        name = self.filepath.name.lower()
        return name.startswith('test_') or name.endswith('_test.py')
    
    def is_main_entry(self) -> bool:
        """判断是否为主入口文件"""
        return self.filepath.name in ['wagent.py', 'main.py', '__main__.py']
    
    def get_size_kb(self) -> int:
        """获取文件大小(KB)"""
        return self.filepath.stat().st_size // 1024 if self.filepath.exists() else 0


class ProjectScanner:
    """项目全面扫描器"""
    
    def __init__(self, root_path: Path):
        self.root = root_path
        self.files = {}
        self.test_files = []
        self.core_files = []
        self.redundant_candidates = []
        self.duplicate_functions = defaultdict(list)
        self.unused_files = []
        self.optimization_report = []
        
    def scan_all_files(self):
        """扫描所有Python文件"""
        for py_file in self.root.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
                
            analyzer = FileAnalyzer(py_file)
            self.files[str(py_file)] = analyzer
            
            if analyzer.is_test_file():
                self.test_files.append(analyzer)
            elif analyzer.is_main_entry():
                self.core_files.append(analyzer)
                
    def find_redundant_files(self):
        """识别冗余/过时文件"""
        
        # 检查1: 旧的入口文件
        old_entries = ['main.py', 'main_async.py', 'main_interactive.py']
        for entry in old_entries:
            path = self.root / entry
            if path.exists():
                self.redundant_candidates.append({
                    'file': entry,
                    'reason': '旧版入口文件，已被wagent.py替代',
                    'type': 'deprecated_entry',
                    'size': path.stat().st_size
                })
        
        # 检查2: 旧版AI模块 vs 新版engines
        old_ai_modules = {
            'ai/director_ai.py': 'wagent/engines/director.py',
            'ai/researcher_ai.py': 'wagent/engines/researcher.py',
            'ai/writer_ai.py': 'wagent/engines/writer.py'
        }
        
        for old_file, new_file in old_ai_modules.items():
            old_path = self.root / old_file
            new_path = self.root / new_file
            
            if old_path.exists() and new_path.exists():
                self.redundant_candidates.append({
                    'file': old_file,
                    'reason': f'旧版AI模块，已被{new_file}替代',
                    'type': 'legacy_module',
                    'size': old_path.stat().st_size,
                    'replacement': new_file
                })
        
        # 检查3: 根目录的独立测试文件 vs tests/目录
        root_tests = [f for f in self.root.glob('test_*.py') 
                     if f.name not in ['test_v52_system.py', 'test_v53_upgrade.py']]
        
        for test_file in root_tests:
            analyzer = self.files.get(str(test_file))
            if analyzer and len(analyzer.functions) > 0:
                self.redundant_candidates.append({
                    'file': test_file.name,
                    'reason': '旧版独立测试文件，功能已整合到v52/v53测试套件',
                    'type': 'legacy_test',
                    'size': test_file.stat().st_size,
                    'functions_count': len(analyzer.functions)
                })
        
        # 检查4: 工具/演示文件
        demo_files = ['demo_template_system.py', 'quick_validation.py']
        for demo in demo_files:
            path = self.root / demo
            if path.exists():
                self.redundant_candidates.append({
                    'file': demo,
                    'reason': '演示/验证脚本，非核心功能',
                    'type': 'demo_script',
                    'size': path.stat().st_size
                })
        
        # 检查5: 数据模块
        data_modules = ['data/novel_data.py', 'data/generated_data.py', 'data/redis_config.py']
        for dm in data_modules:
            path = self.root / dm
            if path.exists():
                is_used = self._check_if_module_is_used(dm.replace('/', '.').replace('.py', ''))
                if not is_used:
                    self.redundant_candidates.append({
                        'file': dm,
                        'reason': '未被任何核心模块导入的数据模块',
                        'type': 'unused_data_module',
                        'size': path.stat().st_size
                    })
    
    def _check_if_module_is_used(self, module_name: str) -> bool:
        """检查模块是否被其他文件导入"""
        pattern = re.compile(rf'(import\s+{re.escape(module_name)}|from\s+{re.escape(module_name)})')
        
        for filepath, analyzer in self.files.items():
            if module_name.replace('.', '/') not in filepath:
                if pattern.search(analyzer.content):
                    return True
        return False
    
    def find_duplicate_functionality(self):
        """检测重复功能"""
        
        # 收集所有函数和类定义
        all_definitions = []
        for filepath, analyzer in self.files.items():
            for func in analyzer.functions:
                all_definitions.append({
                    'name': func,
                    'file': filepath,
                    'type': 'function'
                })
            for cls in analyzer.classes:
                all_definitions.append({
                    'name': cls,
                    'file': filepath,
                    'type': 'class'
                })
        
        # 查找同名但不同文件的定义
        name_map = defaultdict(list)
        for definition in all_definitions:
            name_map[definition['name']].append(definition)
        
        for name, definitions in name_map.items():
            files = set(d['file'] for d in definitions)
            if len(files) > 1:
                self.duplicate_functions[name] = definitions
    
    def generate_optimization_plan(self):
        """生成优化方案"""
        
        report = []
        report.append("=" * 80)
        report.append("📊 WAgent 项目系统性优化分析报告")
        report.append("=" * 80)
        report.append(f"\n🕐 扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"📁 项目根目录: {self.root}")
        
        # 统计信息
        total_files = len(self.files)
        total_test_files = len(self.test_files)
        total_redundant = len(self.redundant_candidates)
        total_duplicates = len(self.duplicate_functions)
        
        total_size = sum(f.get_size_kb() for f in self.files.values())
        redundant_size = sum(r.get('size', 0) for r in self.redundant_candidates)
        
        report.append(f"\n{'─'*60}")
        report.append("📈 项目统计")
        report.append("─"*60)
        report.append(f"  总Python文件数: {total_files}")
        report.append(f"  测试文件数: {total_test_files}")
        report.append(f"  冗余候选文件: {total_redundant}")
        report.append(f"  重复功能点: {total_duplicates}")
        report.append(f"  总代码量: {total_size} KB")
        report.append(f"  可优化空间: {redundant_size / 1024:.1f} MB (冗余文件)")
        
        # 冗余文件详情
        if self.redundant_candidates:
            report.append(f"\n{'═'*60}")
            report.append("⚠️ 冗余/过时文件详情")
            report.append("═"*60)
            
            by_type = defaultdict(list)
            for rc in self.redundant_candidates:
                by_type[rc['type']].append(rc)
            
            type_order = ['deprecated_entry', 'legacy_module', 'legacy_test', 'demo_script', 'unused_data_module']
            type_names = {
                'deprecated_entry': '🚫 旧版入口文件',
                'legacy_module': '🔄 旧版功能模块',
                'legacy_test': '🧪 旧版测试文件',
                'demo_script': '🎭 演示/验证脚本',
                'unused_data_module': '📦 未使用数据模块'
            }
            
            for t in type_order:
                if t in by_type:
                    report.append(f"\n{type_names.get(t, t)} ({len(by_type[t])}个):")
                    for item in by_type[t]:
                        size_str = f"{item['size']/1024:.1f} KB" if item.get('size') else "N/A"
                        report.append(f"  • {item['file']:<35} [{size_str}]")
                        report.append(f"    └─ {item['reason']}")
                        if item.get('replacement'):
                            report.append(f"    └─ 替代者: {item['replacement']}")
        
        # 重复功能详情
        if self.duplicate_functions:
            report.append(f"\n{'═'*60}")
            report.append("🔀 重复功能检测")
            report.append("═"*60)
            
            shown = 0
            for name, defs in list(self.duplicate_functions.items())[:10]:
                report.append(f"\n  '{name}' 出现在 {len(defs)} 个文件中:")
                for d in defs[:3]:
                    file_short = Path(d['file']).name
                    report.append(f"    - {file_short} ({d['type']})")
                shown += 1
            
            if len(self.duplicate_functions) > 10:
                report.append(f"\n  ... 还有 {len(self.duplicate_functions)-10} 组重复")
        
        # 优化建议
        report.append(f"\n{'═'*60}")
        report.append("✨ 优化建议与执行计划")
        report.append("═"*60)
        
        suggestions = [
            ("高优先级", [
                "删除旧版入口文件 (main.py, main_async.py, main_interactive.py)",
                "删除旧版AI模块 (ai/*.py → 已迁移至 wagent/engines/)",
                "合并旧版测试到统一套件"
            ]),
            ("中优先级", [
                "清理未使用的data模块",
                "移除演示脚本(demo_template_system.py等)",
                "整理tools/目录下的辅助工具"
            ]),
            ("低优先级", [
                "统一重复的函数/类命名",
                "添加类型注解提升可维护性",
                "优化__pycache__缓存管理"
            ])
        ]
        
        for priority, items in suggestions:
            report.append(f"\n[{priority}]")
            for item in items:
                report.append(f"  ☐ {item}")
        
        # 预期收益
        report.append(f"\n{'─'*60}")
        report.append("💰 预期优化收益")
        report.append("─"*60)
        report.append(f"  可释放空间: ~{redundant_size/1024:.1f} MB")
        report.append(f"  减少文件数: ~{total_redundant} 个")
        report.append(f"  代码复杂度降低: 显著")
        report.append(f"  维护成本降低: 中等")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)


def run_project_scan():
    """执行项目扫描"""
    print("\n" + "="*70)
    print("🔍 WAgent 项目系统性优化扫描器")
    print("="*70 + "\n")
    
    scanner = ProjectScanner(PROJECT_ROOT)
    
    print("📂 正在扫描项目文件...")
    scanner.scan_all_files()
    print(f"   ✓ 已扫描 {len(scanner.files)} 个Python文件\n")
    
    print("🔍 正在识别冗余文件...")
    scanner.find_redundant_files()
    print(f"   ✓ 发现 {len(scanner.redundant_candidates)} 个冗余候选\n")
    
    print("🔍 正在检测重复功能...")
    scanner.find_duplicate_functionality()
    print(f"   ✓ 发现 {len(scanner.duplicate_functions)} 组重复定义\n")
    
    print("📊 正在生成优化报告...")
    report = scanner.generate_optimization_plan()
    
    print(report)
    
    # 保存报告
    report_path = PROJECT_ROOT / "_optimization_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n💾 完整报告已保存至: {report_path}")
    
    return scanner


if __name__ == "__main__":
    scanner = run_project_scan()
