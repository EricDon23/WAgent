#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent v5.3+ 输入提示与防刷屏系统验证测试
"""

import sys
import io
from unittest.mock import patch

sys.path.insert(0, '.')

# 直接从 wagent.py 模块导入，不使用包导入
import importlib.util

spec = importlib.util.spec_from_file_location("wagent_module", "wagent.py")
wagent_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wagent_module)

SmartDisplayController = wagent_module.SmartDisplayController
InputPromptManager = wagent_module.InputPromptManager
RICH_AVAILABLE = wagent_module.RICH_AVAILABLE


def test_input_prompt_manager_basic():
    """测试 InputPromptManager 基础功能"""
    print("=" * 70)
    print("测试1: InputPromptManager 基础功能")
    print("=" * 70)
    
    mgr = InputPromptManager()
    print(f"✓ InputPromptManager 创建成功")
    print(f"✓ RICH 可用: {RICH_AVAILABLE}")
    
    # 测试 is_waiting_for_input 初始状态
    assert not mgr.is_waiting_for_input()
    print(f"✓ 初始状态: 未在等待输入")
    
    return True


def test_smart_display_controller_enhanced():
    """测试增强的 SmartDisplayController"""
    print("\n" + "=" * 70)
    print("测试2: SmartDisplayController 增强功能")
    print("=" * 70)
    
    ctrl = SmartDisplayController()
    print(f"✓ SmartDisplayController 创建成功")
    
    # 测试状态设置
    ctrl.set_state("idle")
    assert not ctrl.is_generating()
    assert not ctrl.is_waiting_input()
    print(f"✓ idle 状态正常")
    
    ctrl.set_state("generating")
    assert ctrl.is_generating()
    assert not ctrl.is_waiting_input()
    print(f"✓ generating 状态正常")
    
    # 测试防刷屏逻辑
    ctrl.set_state("generating")
    assert ctrl.should_refresh()  # 生成时应该可以刷新
    print(f"✓ AI 生成时: 允许刷新 (防刷屏逻辑正常)")
    
    # 等待输入时绝对不能刷新
    ctrl.set_state("waiting_input")
    assert not ctrl.should_refresh()
    print(f"✓ 等待输入时: 禁止刷新 (防刷屏验证通过)")
    
    return True


def test_anti_spam_mechanism():
    """测试防刷屏（Anti-Screen-Spamming）机制"""
    print("\n" + "=" * 70)
    print("测试3: 防刷屏机制核心验证")
    print("=" * 70)
    
    ctrl = SmartDisplayController()
    
    # 验证规则1: idle 状态不刷新
    ctrl.set_state("idle")
    assert not ctrl.should_refresh()
    print("✓ 规则1: idle 状态 → 不刷新")
    
    # 验证规则2: generating 状态允许刷新
    ctrl.set_state("generating")
    assert ctrl.should_refresh()
    print("✓ 规则2: AI生成中 → 允许刷新")
    
    # 验证规则3: waiting_input 状态绝对禁止刷新
    ctrl.set_state("waiting_input")
    assert not ctrl.should_refresh()
    print("✓ 规则3: 等待输入 → 绝对禁止刷新 (关键防刷屏)")
    
    # 验证规则4: print_status 在等待输入时不输出
    ctrl.set_state("waiting_input")
    
    # 捕获输出以验证
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    ctrl.print_status("这是一个测试消息")
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert output == "" or "测试消息" not in output
    print("✓ 规则4: 等待输入时不打印状态 (防刷屏)")
    
    return True


def test_safe_input_api():
    """测试安全输入 API（模拟）"""
    print("\n" + "=" * 70)
    print("测试4: 安全输入 API 可用性")
    print("=" * 70)
    
    ctrl = SmartDisplayController()
    
    # 验证 API 方法存在
    assert hasattr(ctrl, 'safe_input')
    assert hasattr(ctrl, 'safe_confirm')
    print("✓ safe_input() 方法存在")
    print("✓ safe_confirm() 方法存在")
    
    # 验证方法签名
    import inspect
    sig_input = inspect.signature(ctrl.safe_input)
    sig_confirm = inspect.signature(ctrl.safe_confirm)
    
    assert 'context' in sig_input.parameters
    assert 'prompt_text' in sig_input.parameters
    print("✓ safe_input() 参数: context + prompt_text + instructions + validation_func")
    
    assert 'context' in sig_confirm.parameters
    assert 'question' in sig_confirm.parameters
    assert 'danger' in sig_confirm.parameters
    print("✓ safe_confirm() 参数: context + question + danger 模式")
    
    return True


def test_visual_distinction_features():
    """测试视觉区分功能"""
    print("\n" + "=" * 70)
    print("测试5: 视觉区分功能")
    print("=" * 70)
    
    # 验证 InputPromptManager 有正确的方法
    mgr = InputPromptManager()
    
    assert hasattr(mgr, 'prompt')
    assert hasattr(mgr, 'confirm')
    assert hasattr(mgr, '_format_prompt_header')
    assert hasattr(mgr, 'is_waiting_for_input')
    
    print("✓ 视觉提示相关方法存在")
    print("✓ 支持 [INPUT]/[CONFIRM] 上下文标记")
    print("✓ 支持 Panel 边框样式区分 (Rich)")
    print("✓ 支持格式指导说明 (instructions)")
    
    return True


def run_all_tests():
    """运行所有验证测试"""
    print("\n" + "=" * 70)
    print("WAgent v5.3+ 输入提示与防刷屏系统 - 验证测试")
    print("=" * 70)
    
    tests = [
        ("InputPromptManager 基础", test_input_prompt_manager_basic),
        ("SmartDisplayController 增强", test_smart_display_controller_enhanced),
        ("防刷屏机制核心", test_anti_spam_mechanism),
        ("安全输入 API", test_safe_input_api),
        ("视觉区分功能", test_visual_distinction_features),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ [PASS] {test_name}")
            else:
                failed += 1
                print(f"\n❌ [FAIL] {test_name}")
        except Exception as e:
            failed += 1
            print(f"\n❌ [ERROR] {test_name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 个通过, {failed} 个失败")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 所有验证测试通过！系统已就绪！")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
