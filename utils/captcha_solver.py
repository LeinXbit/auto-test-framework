# -*- coding: utf-8 -*-
"""
验证码识别封装
    - 基于 ddddocr 自动识别 GVA 字符验证码
    - 支持长度校验失败自动重试
"""
import base64

from utils.logger import get_logger

logger = get_logger(__name__)


class CaptchaSolver:
    """ddddocr 验证码识别器（懒加载，避免每次实例化都加载模型）"""

    _ocr = None

    def __init__(self, expected_length=None, max_retry=5):
        self.expected_length = expected_length
        self.max_retry = max_retry

    @classmethod
    def _get_ocr(cls):
        if cls._ocr is None:
            import ddddocr
            cls._ocr = ddddocr.DdddOcr(show_ad=False)
        return cls._ocr

    def solve(self, pic_base64):
        """
        识别单张验证码图片
        :param pic_base64: data:image/png;base64,xxxx 或纯 base64
        :return: 识别出的字符串
        """
        if "," in pic_base64:
            pic_base64 = pic_base64.split(",", 1)[1]
        img_bytes = base64.b64decode(pic_base64)
        ocr = self._get_ocr()
        code = ocr.classification(img_bytes)
        logger.debug(f"OCR 识别结果: {code!r}")
        return code

    def solve_with_retry(self, fetch_captcha_func, max_retry=None):
        """
        多次获取验证码并识别，直到长度匹配或重试上限
        :param fetch_captcha_func: 无参函数，返回 (picPath, captchaId)
        :return: (code, captchaId)
        """
        retry = max_retry if max_retry is not None else self.max_retry
        code, captcha_id = "", ""
        for attempt in range(1, retry + 1):
            pic_base64, captcha_id = fetch_captcha_func()
            code = self.solve(pic_base64)
            if self.expected_length is None or len(code) == self.expected_length:
                logger.info(f"验证码识别成功（第 {attempt} 次）: code={code!r}, captchaId={captcha_id}")
                return code, captcha_id
            logger.warning(f"第 {attempt} 次识别长度 {len(code)} != 期望 {self.expected_length}, 重试")
        logger.error(f"验证码识别重试 {retry} 次仍未匹配期望长度，返回最后一次结果: {code!r}")
        return code, captcha_id
