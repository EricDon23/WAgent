#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent - Writing Agent 主程序入口

功能：
- 一键运行所有四次核心测试
- 显示完整的测试报告
- 生成项目验收文档

使用方法：
    python main.py                    # 运行全部测试
    python main.py --test=1          # 只运行测试1（导演AI）
    python main.py --test=2          # 只运行测试2（研究员AI）
    python main.py --test=3          # 只运行测试3（作家AI）
    python main.py --test=4          # 只运行测试4（回合测试）
    python main.py --quick           # 快速验证模式

项目架构：
    交互层 (CLI/测试)
        ↓
    AI处理层 (三AI协作)
        ├─ 导演AI → StorySetting
        ├─ 研究员AI → KnowledgeBase
        └─ 作家AI → 故事文本
        ↓
    工具层 (MCP/IO/文本处理)
        ↓
    数据层 (G模块/存储)

作者：WAgent Team
日期：2026-04-16
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🚀 WAgent - Writing Agent 三AI协作故事创作系统 v1.0         ║
║                                                               ║
║   导演AI(豆包) + 研究员AI(通义千问) + 作家AI(DeepSeek)       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78 + "\n")


def ensure_directories():
    """确保必要的目录存在"""
    dirs = [
        'test_output',
        'stories/story_001/settings',
        'stories/story_001/research',
        'stories/story_001/drafts',
        'stories/story_001/states',
        'logs',
        'data/states'
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


def run_test(test_num: int) -> bool:
    """
    运行指定测试
    
    Args:
        test_num: 测试编号 (1-4)
        
    Returns:
        是否通过
    """
    test_scripts = {
        1: ("tests/test_director.py", "导演AI模块"),
        2: ("tests/test_researcher.py", "研究员AI模块"),
        3: ("tests/test_writer.py", "作家AI模块"),
        4: ("tests/test_round.py", "回合制测试")
    }
    
    if test_num not in test_scripts:
        print(f"❌ 无效的测试编号: {test_num}")
        return False
    
    script_path, test_name = test_scripts[test_num]
    
    print_section(f"🧪 运行测试{test_num}: {test_name}")
    
    if not os.path.exists(script_path):
        print(f"❌ 测试脚本不存在: {script_path}")
        return False
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ 标准错误输出:")
            print(result.stderr[:500])
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⚠️ 测试{test_num}超时")
        return False
    except Exception as e:
        print(f"❌ 测试{test_num}执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有四次测试"""
    results = {}
    
    for i in range(1, 5):
        success = run_test(i)
        results[f"test_{i}"] = success
        
        if not success and i < 4:
            print("\n⚠️ 当前测试失败，是否继续？(自动继续)")
    
    return results


def generate_final_report(results: dict):
    """生成最终测试报告"""
    print_section("📊 最终测试报告")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    test_names = {
        "test_1": "导演AI模块",
        "test_2": "研究员AI模块",
        "test_3": "作家AI模块",
        "test_4": "回合制测试"
    }
    
    print(f"\n{'='*60}")
    print(f"  总体结果: {passed_tests}/{total_tests} 通过 ({pass_rate:.0f}%)")
    print(f"{'='*60}\n")
    
    print("各阶段详情:")
    print("-" * 60)
    
    for test_id, success in results.items():
        name = test_names.get(test_id, test_id)
        icon = "✅" if success else "❌"
        status = "通过" if success else "未通过"
        print(f"  {icon} {name}: {status}")
    
    print("-" * 60)
    
    # 评级
    if pass_rate >= 90:
        rating = "🌟 优秀"
        verdict = "系统完全符合要求，可以投入使用！"
    elif pass_rate >= 75:
        rating = "✨ 良好"
        verdict = "系统基本达标，有少量问题需关注。"
    elif pass_rate >= 50:
        rating = "⚠️ 一般"
        verdict = "系统部分功能正常，需要优化。"
    else:
        rating = "❌ 较差"
        verdict = "系统存在较多问题，需要修复。"
    
    print(f"\n🏆 综合评级: {rating}")
    print(f"💬 验收结论: {verdict}")
    
    # 检查生成的文件
    print(f"\n📁 生成的文件:")
    files_to_check = [
        "test_output/test1_director_result.json",
        "stories/story_001/research/knowledge_base.json",
        "stories/story_001/drafts/round_1.md",
        "stories/story_001/drafts/round_2.md",
        "test_output/test4_round_result.json"
    ]
    
    for filepath in files_to_check:
        exists = os.path.exists(filepath)
        icon = "✅" if exists else "⚠️"
        status = "已生成" if exists else "未找到"
        print(f"  {icon} {filepath}: {status}")
    
    # 保存报告
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "pass_rate": pass_rate,
        "rating": rating.split()[1] if rating else "unknown",
        "details": {
            f"test_{i+1}": {
                "name": test_names[f"test_{i+1}"],
                "passed": results[f"test_{i+1}"]
            } for i in range(4)
        },
        "generated_files": {
            filepath: os.path.exists(filepath)
            for filepath in files_to_check
        }
    }
    
    report_path = "test_output/final_test_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 完整报告已保存: {report_path}")
    
    return pass_rate >= 75


def quick_validation():
    """快速验证模式"""
    print_section("⚡ 快速验证模式")
    
    checks = []
    
    # 检查配置文件
    print("[1] 检查配置文件...")
    has_env = os.path.exists('.env')
    print(f"  .env 文件: {'✅ 存在' if has_env else '❌ 缺失'}")
    checks.append(("配置文件", has_env))
    
    # 检查依赖
    print("\n[2] 检查关键依赖...")
    dependencies = [
        ('langchain', 'langchain'),
        ('pydantic', 'pydantic'),
        ('dotenv', 'python-dotenv'),
        ('openai', 'langchain-openai')
    ]
    
    for module_name, package_name in dependencies:
        try:
            __import__(module_name)
            print(f"  {package_name}: ✅ 已安装")
        except ImportError:
            print(f"  {package_name}: ❌ 未安装")
    
    # 检查核心模块
    print("\n[3] 检查核心模块...")
    modules_to_check = [
        ('ai/director_ai.py', '导演AI'),
        ('ai/researcher_ai.py', '研究员AI'),
        ('ai/writer_ai.py', '作家AI'),
        ('data/g_module.py', 'G模块'),
        ('data/novel_data.py', '小说数据'),
        ('tools/io_tool.py', 'IO工具'),
        ('tools/text_processor.py', '文本工具')
    ]
    
    modules_ok = True
    for path, name in modules_to_check:
        exists = os.path.exists(path)
        icon = "✅" if exists else "❌"
        print(f"  {icon} {name}: {'存在' if exists else '缺失'}")
        if not exists:
            modules_ok = False
    
    checks.append(("核心模块", modules_ok))
    
    # 检查测试脚本
    print("\n[4] 检查测试脚本...")
    tests_exist = all(os.path.exists(f'tests/test_{i}.py') for i in range(1, 5))
    print(f"  测试脚本: {'✅ 全部存在' if tests_exist else '❌ 有缺失'}")
    checks.append(("测试脚本", tests_exist))
    
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    
    print(f"\n{'='*50}")
    print(f"  快速验证: {passed}/{total} 通过")
    
    if passed == total:
        print("  🎉 所有检查通过！可以运行完整测试")
        return True
    else:
        print("  ⚠️ 存在问题，请先修复")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="WAgent - Writing Agent 三AI协作故事创作系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                  运行全部四次测试
  python main.py --test=1        只运行导演AI测试
  python main.py --quick         快速验证环境
  python main.py --help           显示帮助信息
"""
    )
    
    parser.add_argument(
        '--test',
        type=int,
        choices=[1, 2, 3, 4],
        help='指定要运行的测试编号 (1-4)'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='快速验证模式'
    )
    
    args = parser.parse_args()
    
    start_time = datetime.now()
    
    print_banner()
    ensure_directories()
    
    print(f"⏰ 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    if args.quick:
        quick_validation()
    elif args.test:
        success = run_test(args.test)
        sys.exit(0 if success else 1)
    else:
        results = run_all_tests()
        final_pass = generate_final_report(results)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n⏱️ 总耗时: {duration:.2f}秒")
        print(f"🕐 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n" + "=" * 78 + "\n")
        
        sys.exit(0 if final_pass else 1)


if __name__ == "__main__":
    main()
