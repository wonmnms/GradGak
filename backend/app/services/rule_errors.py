"""규칙·카탈로그 데이터 결함을 나타내는 예외. 코드 버그와 구분해 API가 500으로 보낸다."""


class InvalidRuleDataError(LookupError, ValueError):
    """범위는 있지만 규칙·카탈로그 데이터가 불완전하거나 모순이다."""
