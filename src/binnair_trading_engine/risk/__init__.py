"""리스크 관리 모듈."""

from .checker import RiskChecker, RiskCheckResult
from .default import DefaultRiskChecker

__all__ = ["RiskChecker", "RiskCheckResult", "DefaultRiskChecker", "create_risk_checker"]


def create_risk_checker(config) -> RiskChecker:
    """설정에 따라 RiskChecker 생성."""
    return DefaultRiskChecker()
