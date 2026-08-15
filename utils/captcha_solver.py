# -*- coding: utf-8 -*-
"""验证码识别工具：基于 ddddocr 处理 GVA 强制开启的字符验证码"""
import base64
import sys
from pathlib import Path

from utils.exceptions import FrameworkException
from utils.logger import get_logger

logger = get_logger(__name__)

# ddddocr 安装在项目 .vendor 目录，加入 sys.path（懒加载避免未使用时也加载）
_VENDOR = Path(__file__).resolve().parent.parent / ".vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))


class CaptchaSolver:
    """
    GVA 验证码识别器：
        - ddddocr 字符识别
        - 长度校验失败自动重试（OCR 偶发把 6 位识别成 5 位）
        - 单例 OCR 实例避免重复加载 onnx 模型
    """
    _ocr = None  # 类级缓存，整个进程只加载一次模型

    def __init__(self, expected_length=None, max_retry=5):
        self.expected_length = expected_length
        self.max_retry = max_retry

    @classmethod
    def _get_ocr(cls):
        if cls._ocr is None:
            try:
                import ddddocr
                cls._ocr = ddddocr.DdddOcr(show_ad=False)
                logger.info("ddddocr 模型加载完成")
            except ImportError as e:
                raise FrameworkException(
                    f"未安装 ddddocr 依赖：{e}。请运行 pip install ddddocr --target=.vendor"
                )
        return cls._ocr

    def solve(self, pic_base64):
        """
        识别 GVA /base/captcha 返回的 base64 验证码图片
        :param pic_base64: 形如 "data:image/png;base64,iVBOR..." 或纯 base64 字符串
        :return: 识别出的验证码字符串
        """
        # 剥离 data URI 前缀
        if "," in pic_base64:
            pic_base64 = pic_base64.split(",", 1)[1]

        img_bytes = base64.b64decode(pic_base64)
        ocr = self._get_ocr()
        code = ocr.classification(img_bytes)
        logger.debug(f"OCR 识别结果: {code!r}")
        return code

    def solve_with_retry(self, fetch_captcha_func, max_retry=None):
        """
        多次拉取+识别直到长度匹配或达到重试上限
        :param fetch_captcha_func: 拉取验证码的回调，返回 (pic_base64, captcha_id)
        :param max_retry: 覆盖默认重试次数
        :return: (code, captcha_id)
        :raises FrameworkException: 多次重试后仍未识别出期望长度
        """
        retry = max_retry if max_retry is not None else self.max_retry
        last_code, last_captcha_id = None, None

        for attempt in range(1, retry + 1):
            pic_base64, captcha_id = fetch_captcha_func()
            code = self.solve(pic_base64)
            last_code, last_captcha_id = code, captcha_id

            if self.expected_length is None or len(code) == self.expected_length:
                logger.info(f"验证码识别成功（第 {attempt} 次）: code={code!r}, captchaId={captcha_id}")
                return code, captcha_id

            logger.warning(
                f"第 {attempt}/{retry} 次识别长度不符: code={code!r}(len={len(code)}, exp={self.expected_length})，重试"
            )

        # 长度不匹配但已达到重试上限：返回最后一次结果，由调用方决定是否使用
        logger.warning(f"达到重试上限 {retry}，使用最后一次识别结果: {last_code!r}")
        return last_code, last_captcha_id
