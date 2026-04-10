class AppError(Exception):
    """应用基础异常。"""


class ValidationAppError(AppError):
    """输入校验失败。"""


class NotFoundAppError(AppError):
    """资源不存在。"""


class ExternalServiceAppError(AppError):
    """外部服务调用失败。"""
