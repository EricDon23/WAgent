#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Constraint Manager 问题修复验证测试
"""

import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')

from wagent.constraint_manager import (
    ConstraintManager,
    ConstraintType,
    AuditAction,
    UserConstraint,
    AuditRecord,
    ConstraintViolation
)


def test_enum_string_compatibility():
    """测试枚举与字符串的兼容性"""
    print("=" * 60)
    print("测试1: 枚举与字符串兼容性")
    print("=" * 60)
    
    # 1. 测试 UserConstraint
    print("\n1.1 测试 UserConstraint:")
    c1 = UserConstraint(
        constraint_id="test_c1",
        type=ConstraintType.WORD_COUNT,
        description="字数测试",
        value={"min": 100, "max": 500}
    )
    print(f"   ✓ 用枚举创建成功: {c1.type}")
    
    # 测试用字符串创建（从JSON加载）
    c2 = UserConstraint(
        constraint_id="test_c2",
        type="字数约束",
        description="字数测试2",
        value={"min": 200, "max": 1000}
    )
    print(f"   ✓ 用字符串创建成功: {c2.type} (自动转换为枚举)")
    assert c2.type == ConstraintType.WORD_COUNT
    print("   ✓ 转换为枚举正确")
    
    # 测试 to_dict
    d1 = c1.to_dict()
    print(f"   ✓ to_dict 成功: type={d1['type']}")
    assert d1['type'] == "字数约束"
    
    # 2. 测试 AuditRecord
    print("\n1.2 测试 AuditRecord:")
    a1 = AuditRecord(
        record_id="test_a1",
        action=AuditAction.CREATE,
        target_type="setting",
        target_id="test"
    )
    print(f"   ✓ 用枚举创建成功: {a1.action}")
    
    a2 = AuditRecord(
        record_id="test_a2",
        action="创建",
        target_type="constraint",
        target_id="test2"
    )
    print(f"   ✓ 用字符串创建成功: {a2.action} (自动转换)")
    assert a2.action == AuditAction.CREATE
    
    # 测试 to_dict
    ad1 = a1.to_dict()
    assert ad1['action'] == "创建"
    print(f"   ✓ to_dict 成功")
    
    # 3. 测试 ConstraintViolation
    print("\n1.3 测试 ConstraintViolation:")
    v1 = ConstraintViolation(
        violation_id="test_v1",
        constraint_type=ConstraintType.STYLE,
        constraint_description="风格违规",
        actual_value="未找到",
        expected_value="应包含关键词",
        severity="minor"
    )
    print(f"   ✓ 用枚举创建成功: {v1.constraint_type}")
    
    v2 = ConstraintViolation(
        violation_id="test_v2",
        constraint_type="风格约束",
        constraint_description="风格违规2",
        actual_value="未找到2",
        expected_value="应包含关键词2",
        severity="major"
    )
    print(f"   ✓ 用字符串创建成功: {v2.constraint_type} (自动转换)")
    assert v2.constraint_type == ConstraintType.STYLE
    
    # 测试 to_dict
    vd1 = v1.to_dict()
    assert vd1['constraint_type'] == "风格约束"
    print(f"   ✓ to_dict 成功")
    
    print("\n✅ 测试1通过！")
    return True


def test_full_cycle_with_json_save_load():
    """测试完整的保存-加载循环"""
    print("\n" + "=" * 60)
    print("测试2: 完整保存-加载循环")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. 创建约束管理器
        mgr = ConstraintManager(str(tmp_path))
        print(f"✓ 在 {tmp_path} 创建约束管理器")
        
        # 2. 添加一些约束
        c1 = mgr.add_constraint(
            ConstraintType.WORD_COUNT,
            "每章至少100字",
            {"min": 100, "max": 2000}
        )
        c2 = mgr.add_constraint(
            ConstraintType.STYLE,
            "保持悬疑风格",
            ["悬疑", "紧张", "反转"],
            mandatory=True
        )
        print(f"✓ 添加了 2 个约束")
        
        # 3. 创建一些审计记录（通过add_constraint自动添加）
        assert len(mgr.audit_records) >= 2
        print(f"✓ 审计记录数: {len(mgr.audit_records)}")
        
        # 4. 直接访问保存的JSON，模拟从磁盘加载
        print("\n4.1 直接加载JSON文件测试:")
        constraints_file = tmp_path / "_constraints.json"
        assert constraints_file.exists()
        
        with open(constraints_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 手动重新构造对象
        for c_data in data.get('constraints', []):
            c = UserConstraint(**c_data)
            print(f"   ✓ 重建约束: {c.constraint_id}, type={c.type}")
            assert hasattr(c.type, 'value')  # 应该是枚举对象
        
        print("\n4.2 测试ConstraintManager重新加载:")
        mgr2 = ConstraintManager(str(tmp_path))
        assert len(mgr2.constraints) == 2
        assert len(mgr2.audit_records) >= 2
        print("   ✓ ConstraintManager重新加载成功")
        
        # 5. 验证枚举转换
        for c in mgr2.constraints:
            assert hasattr(c.type, 'value')
            assert isinstance(c.type, ConstraintType)
        print("   ✓ 所有约束type都是枚举对象")
        
        for a in mgr2.audit_records:
            assert hasattr(a.action, 'value')
            assert isinstance(a.action, AuditAction)
        print("   ✓ 所有审计action都是枚举对象")
        
        print("\n✅ 测试2通过！")
        return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Constraint Manager 问题修复验证")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    try:
        if test_enum_string_compatibility():
            passed += 1
        else:
            failed += 1
    except Exception as e:
        failed += 1
        print(f"\n❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        if test_full_cycle_with_json_save_load():
            passed += 1
        else:
            failed += 1
    except Exception as e:
        failed += 1
        print(f"\n❌ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
