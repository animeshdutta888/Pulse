from __future__ import annotations

from pulse.models import Approval, ApprovalState
from pulse.store import get_approval, update_approval_state


def approve(approval_id: str) -> Approval:
    approval = update_approval_state(approval_id, ApprovalState.approved)
    if not approval:
        raise ValueError(f"Unknown approval {approval_id}")
    return approval


def reject(approval_id: str) -> Approval:
    approval = update_approval_state(approval_id, ApprovalState.rejected)
    if not approval:
        raise ValueError(f"Unknown approval {approval_id}")
    return approval


def require_approved(approval_id: str) -> Approval:
    approval = get_approval(approval_id)
    if not approval:
        raise ValueError(f"Unknown approval {approval_id}")
    if approval.state != ApprovalState.approved:
        raise PermissionError("Approval required before execution")
    return approval
