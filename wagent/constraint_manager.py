#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
约束保障与审计跟踪系统 (Constraint Assurance & Audit System)

核心功能：
1. 用户初始约束条件验证与持久化
2. 内容生成过程实时监控
3. 修改操作审计跟踪（完整记录）
4. 约束违规检测与预警
5. 功能回滚机制支持
6. 变更历史回溯查看

设计原则：
- 所有操作可追溯
- 约束条件不可被绕过
- 支持时间线式变更浏览
- 异常情况自动恢复
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class ConstraintType(Enum):
    """约束类型"""
    WORD_COUNT = "字数约束"
    STYLE = "风格约束"
    CONTENT = "内容约束"
    PLOT = "情节约束"
    CHARACTER = "角色约束"
    WORLD_BUILDING = "世界观约束"


class AuditAction(Enum):
    """审计动作类型"""
    CREATE = "创建"
    MODIFY = "修改"
    DELETE = "删除"
    CONFIRM = "确认"
    REJECT = "拒绝"
    ROLLBACK = "回滚"


@dataclass
class UserConstraint:
    """用户约束条件"""
    constraint_id: str
    type: ConstraintType
    description: str  # 约束描述
    value: Any  # 约束值（如字数范围、风格关键词等）
    is_mandatory: bool = True  # 是否必须满足
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            'constraint_id': self.constraint_id,
            'type': self.type.value,
            'description': self.description,
            'value': self.value,
            'is_mandatory': self.is_mandatory,
            'created_at': self.created_at
        }


@dataclass
class AuditRecord:
    """审计记录"""
    record_id: str
    action: AuditAction
    target_type: str  # 操作对象类型：setting/chapter/constraint/context
    target_id: str  # 操作对象ID
    user_input: str = ""  # 用户输入/指令
    before_state: Dict = field(default_factory=dict)  # 操作前状态快照
    after_state: Dict = field(default_factory=dict)   # 操作后状态快照
    details: str = ""
    is_rollback: bool = False
    timestamp: str = ""  # 自动生成
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            'record_id': self.record_id,
            'timestamp': self.timestamp,
            'action': self.action.value,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'user_input': self.user_input,
            'before_state': self.before_state,
            'after_state': self.after_state,
            'details': self.details,
            'is_rollback': self.is_rollback
        }


@dataclass 
class ConstraintViolation:
    """约束违规记录"""
    violation_id: str
    constraint_type: ConstraintType
    constraint_description: str
    actual_value: Any
    expected_value: Any
    severity: str  # critical/major/minor/warning
    context: str = ""  # 违规上下文
    is_resolved: bool = False
    timestamp: str = ""  # 自动生成
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ContextSnapshot:
    """上下文快照（用于回滚）"""
    snapshot_id: str
    snapshot_type: str  # setting/knowledge/chapter/full
    data: Dict[str, Any]  # 完整数据快照
    checksum: str = ""  # 数据校验和
    timestamp: str = ""  # 自动生成
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        
        if not self.checksum:
            import hashlib
            json_str = json.dumps(self.data, sort_keys=True, default=str)
            self.checksum = hashlib.md5(json_str.encode()).hexdigest()[:16]


class ConstraintManager:
    """
    约束保障管理器
    
    职责：
    1. 管理用户设定的约束条件
    2. 监控内容生成是否符合约束
    3. 记录所有审计日志
    4. 提供回滚能力
    """
    
    def __init__(self, story_dir: str = None):
        self.story_dir = Path(story_dir) if story_dir else Path(".")
        self.constraints_file = self.story_dir / "_constraints.json"
        self.audit_log_file = self.story_dir / "_audit_log.json"
        self.snapshots_dir = self.story_dir / "_snapshots"
        
        self.constraints: List[UserConstraint] = []
        self.audit_records: List[AuditRecord] = []
        self.violations: List[ConstraintViolation] = []
        self.snapshots: List[ContextSnapshot] = []
        
        # 加载已有数据
        self._load_data()
    
    def _load_data(self):
        """加载已有数据"""
        if self.constraints_file.exists():
            try:
                with open(self.constraints_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.constraints = [
                    UserConstraint(**c) for c in data.get('constraints', [])
                ]
            except Exception as e:
                print(f"⚠️ 加载约束失败: {e}")
        
        if self.audit_log_file.exists():
            try:
                with open(self.audit_log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.audit_records = [AuditRecord(**r) for r in data.get('records', [])]
            except Exception as e:
                print(f"⚠️ 加载审计日志失败: {e}")
        
        if self.snapshots_dir.exists():
            for snap_file in self.snapshots_dir.glob("*.json"):
                try:
                    with open(snap_file, 'r', encoding='utf-8') as f:
                        snap_data = json.load(f)
                        self.snapshots.append(ContextSnapshot(**snap_data))
                except:
                    pass
    
    def _save_constraints(self):
        """保存约束数据"""
        with open(self.constraints_file, 'w', encoding='utf-8') as f:
            json.dump({
                'constraints': [c.to_dict() for c in self.constraints],
                'updated_at': datetime.now().isoformat(),
                'total_count': len(self.constraints)
            }, f, ensure_ascii=False, indent=2)
    
    def _save_audit_record(self, record: AuditRecord):
        """追加保存审计记录"""
        self.audit_records.append(record)
        
        with open(self.audit_log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'records': [r.to_dict() for r in self.audit_records],
                'total_records': len(self.audit_records),
                'last_updated': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def _save_snapshot(self, snapshot: ContextSnapshot):
        """保存快照"""
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        snap_file = self.snapshots_dir / f"{snapshot.snapshot_id}.json"
        with open(snap_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(snapshot), f, ensure_ascii=False, indent=2, default=str)
        
        self.snapshots.append(snapshot)
    
    def add_constraint(self, ctype: ConstraintType, description: str,
                       value: Any, mandatory: bool = True) -> UserConstraint:
        """添加用户约束"""
        constraint = UserConstraint(
            constraint_id=f"constraint_{len(self.constraints)+1}_{datetime.now().strftime('%H%M%S')}",
            type=ctype,
            description=description,
            value=value,
            is_mandatory=mandatory
        )
        
        self.constraints.append(constraint)
        self._save_constraints()
        
        # 记录审计
        audit = AuditRecord(
            record_id=f"audit_{len(self.audit_records)+1}",
            action=AuditAction.CREATE,
            target_type="constraint",
            target_id=constraint.constraint_id,
            details=f"添加约束: {description}"
        )
        self._save_audit_record(audit)
        
        return constraint
    
    def validate_content(self, content: str, chapter_num: int = 0) -> Tuple[bool, List[ConstraintViolation]]:
        """
        验证内容是否符合所有约束
        
        Returns:
            (是否通过, 违规列表)
        """
        violations = []
        
        for constraint in self.constraints:
            violation = self._check_single_constraint(constraint, content, chapter_num)
            if violation:
                violations.append(violation)
                self.violations.append(violation)
        
        return len(violations) == 0, violations
    
    def _check_single_constraint(self, constraint: UserConstraint, 
                                content: str, chapter_num: int) -> Optional[ConstraintViolation]:
        """检查单个约束"""
        word_count = len(content)
        
        if constraint.type == ConstraintType.WORD_COUNT:
            value = constraint.value
            
            if isinstance(value, dict):
                min_words = value.get('min', 0)
                max_words = value.get('max', float('inf'))
                
                if word_count < min_words:
                    return ConstraintViolation(
                        violation_id=f"violate_{len(self.violations)+1}",
                        constraint_type=ConstraintType.WORD_COUNT,
                        constraint_description=constraint.description,
                        actual_value=word_count,
                        expected_value=f"{min_words}-{max_words}",
                        severity="major" if word_count < min_words * 0.5 else "minor",
                        context=f"第{chapter_num}章"
                    )
                elif word_count > max_words:
                    return ConstraintViolation(
                        violation_id=f"violate_{len(self.violations)+1}",
                        constraint_type=ConstraintType.WORD_COUNT,
                        constraint_description=constraint.description,
                        actual_value=word_count,
                        expected_value=f"{min_words}-{max_words}",
                        severity="warning",
                        context=f"第{chapter_num}章"
                    )
        
        elif constraint.type == ConstraintType.STYLE:
            keywords = constraint.value if isinstance(constraint.value, list) else [str(constraint.value)]
            
            content_lower = content.lower()
            found = sum(1 for kw in keywords if kw.lower() in content_lower)
            
            if found == 0 and constraint.is_mandatory:
                return ConstraintViolation(
                    violation_id=f"violate_{len(self.violations)+1}",
                    constraint_type=ConstraintType.STYLE,
                    constraint_description=constraint.description,
                    actual_value="未检测到",
                    expected_value=str(keywords),
                    severity="minor",
                    context=f"第{chapter_num}章"
                )
        
        elif constraint.type == ConstraintType.CONTENT:
            forbidden = constraint.value.get('forbidden', []) if isinstance(constraint.value, dict) else []
            required = constraint.value.get('required', []) if isinstance(constraint.value, dict) else []
            
            for word in forbidden:
                if word.lower() in content.lower():
                    return ConstraintViolation(
                        violation_id=f"violate_{len(self.violations)+1}",
                        constraint_type=ConstraintType.CONTENT,
                        constraint_description=f"禁止出现: {word}",
                        actual_value=f"包含禁词",
                        expected_value=f"不应包含 {word}",
                        severity="critical",
                        context=f"第{chapter_num}章"
                    )
            
            for word in required:
                if word.lower() not in content.lower():
                    return ConstraintViolation(
                        violation_id=f"violate_{len(self.violations)+1}",
                        constraint_type=ConstraintType.CONTENT,
                        constraint_description=f"必须包含: {word}",
                        actual_value=f"缺少关键词",
                        expected_value=f"应包含 {word}",
                        severity="major",
                        context=f"第{chapter_num}章"
                    )
        
        return None
    
    def audit_action(self, action: AuditAction, target_type: str, target_id: str,
                   before: Dict = None, after: Dict = None, 
                   user_input: str = "", details: str = "") -> AuditRecord:
        """记录审计日志"""
        record = AuditRecord(
            record_id=f"audit_{len(self.audit_records)+1}_{datetime.now().strftime('%H%M%S%f')}",
            action=action,
            target_type=target_type,
            target_id=target_id,
            user_input=user_input,
            before_state=before or {},
            after_state=after or {},
            details=details
        )
        
        self._save_audit_record(record)
        return record
    
    def create_snapshot(self, snapshot_type: str, data: Dict, 
                         description: str = "") -> ContextSnapshot:
        """创建数据快照（用于回滚）"""
        snapshot = ContextSnapshot(
            snapshot_id=f"snap_{len(self.snapshots)+1}_{datetime.now().strftime('%H%M%S')}",
            snapshot_type=snapshot_type,
            data=data.copy()
        )
        
        self._save_snapshot(snapshot)
        
        # 记录审计
        self.audit_action(
            action=AuditAction.CREATE,
            target_type="snapshot",
            target_id=snapshot.snapshot_id,
            details=f"创建快照: {description or snapshot_type}"
        )
        
        return snapshot
    
    def rollback_to_snapshot(self, snapshot_id: str) -> Optional[ContextSnapshot]:
        """回滚到指定快照"""
        target_snap = None
        
        for snap in self.snapshots:
            if snap.snapshot_id == snapshot_id:
                target_snap = snap
                break
        
        if not target_snap:
            print(f"❌ 快照不存在: {snapshot_id}")
            return None
        
        # 记录回滚审计
        self.audit_action(
            action=AuditAction.ROLLBACK,
            target_type="snapshot",
            target_id=snapshot_id,
            details=f"回滚到快照: {target_snap.snapshot_type}"
        )
        
        return target_snap
    
    def get_audit_history(self, limit: int = 20) -> List[AuditRecord]:
        """获取审计历史"""
        return self.audit_records[-limit:]
    
    def get_violation_report(self) -> Dict[str, Any]:
        """获取违规报告"""
        by_severity = {'critical': [], 'major': [], 'minor': [], 'warning': []}
        
        for v in self.violations:
            sev = v.severity.lower()
            if sev in by_severity:
                by_severity[sev].append(v)
        
        return {
            'total_violations': len(self.violations),
            'unresolved': sum(1 for v in self.violations if not v.is_resolved),
            'by_severity': {k: len(v) for k, v in by_severity.items()},
            'recent_violations': self.violations[-10:] if self.violations else []
        }
    
    def export_audit_report(self) -> str:
        """导出完整审计报告"""
        report_lines = [
            "="*70,
            "📋 WAgent 约束保障与审计报告",
            "="*70,
            f"\n生成时间: {datetime.now().isoformat()}",
            f"\n{'─'*50}",
            "统计摘要",
            "─"*50,
            f"总约束数: {len(self.constraints)}",
            f"总审计记录: {len(self.audit_records)}",
            f"总违规次数: {len(self.violations)}",
            f"未解决违规: {sum(1 for v in self.violations if not v.is_resolved)}",
            f"快照数量: {len(self.snapshots)}"
        ]
        
        # 约束列表
        report_lines.append(f"\n{'═'*50}")
        report_lines.append("用户约束条件")
        report_lines.append("═"*50)
        
        for i, c in enumerate(self.constraints, 1):
            mandatory = "✅ 必须" if c.is_mandatory else "⚪ 可选"
            report_lines.append(f"\n{i}. [{mandatory}] {c.type.value}: {c.description}")
            report_lines.append(f"   值: {c.value}")
        
        # 最近违规
        if self.violations:
            report_lines.append(f"\n{'═'*50}")
            report_lines.append("最近违规记录")
            report_lines.append("═"*50)
            
            for v in self.violations[-5:]:
                icon = {'critical':'❌','major':'⚠️','minor':'ℹ️','warning':'💡'}.get(v.severity,'?')
                report_lines.append(f"\n{icon} [{v.constraint_type.value}] {v.constraint_description}")
                report_lines.append(f"   期望: {v.expected_value} | 实际: {v.actual_value}")
                report_lines.append(f"   位置: {v.context}")
        
        # 最近审计记录
        if self.audit_records:
            report_lines.append(f"\n{'═'*50}")
            report_lines.append("最近操作记录")
            report_lines.append("═"*50)
            
            for rec in self.audit_records[-10:]:
                action_icon = {
                    'CREATE': '➕', 'MODIFY': '✏️', 'DELETE': '🗑',
                    'CONFIRM': '✅', 'REJECT': '❌', 'ROLLBACK': '↩️'
                }.get(rec.action.value, '•')
                
                report_lines.append(f"\n{action_icon} [{rec.target_type}] {rec.details[:60]}")
                if rec.user_input:
                    report_lines.append(f"   输入: {rec.user_input[:40]}")
        
        report_lines.append("\n" + "="*70)
        
        return "\n".join(report_lines)


# 全局便捷函数
def create_constraint_manager(story_dir: str = None) -> ConstraintManager:
    """创建约束管理器实例"""
    return ConstraintManager(story_dir)


def validate_story_constraints(content: str, constraints: List[UserConstraint], 
                             chapter_num: int = 0) -> Tuple[bool, List]:
    """快速验证函数（不依赖实例）"""
    mgr = ConstraintManager()
    mgr.constraints = constraints
    return mgr.validate_content(content, chapter_num)
