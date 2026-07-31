"""
PDF OCR识别模块 — 提供扫描件PDF的文字识别能力

支持两种OCR引擎（按优先级）：
1. PaddleOCR — 推荐，中文识别效果好
2. Tesseract — 通用OCR引擎

如果两者均未安装，模块可以正常运行，仅返回提示信息。

用法：
    from utils.pdf_ocr import ocr_pdf
    result = ocr_pdf(pdf_bytes)
    if result["success"]:
        text = result["text"]
"""
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


def _check_paddleocr() -> bool:
    """检查PaddleOCR是否可用"""
    try:
        import paddleocr
        return True
    except ImportError:
        return False


def _check_tesseract() -> bool:
    """检查Tesseract是否可用"""
    try:
        import subprocess
        result = subprocess.run(["tesseract", "--version"],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def _ocr_with_paddleocr(pdf_bytes: bytes, lang: str = "ch") -> dict:
    """使用PaddleOCR识别PDF中的文字

    Args:
        pdf_bytes: PDF文件字节内容
        lang: 语言，默认中文 "ch"

    Returns:
        dict: {"text": str, "pages": int, "success": bool, "error": str}
    """
    result = {"text": "", "pages": 0, "success": False, "error": ""}
    try:
        from paddleocr import PaddleOCR
        import fitz  # PyMuPDF

        # 将PDF转换为图片
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result["pages"] = len(doc)

        ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

        all_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            # 将PDF页面渲染为图片
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")

            # 使用PaddleOCR识别
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                tmp.write(img_bytes)
                tmp.flush()
                ocr_result = ocr.ocr(tmp.name)

            if ocr_result and ocr_result[0]:
                page_text = []
                for line in ocr_result[0]:
                    if line and len(line) >= 1:
                        text = line[1][0] if len(line) > 1 and isinstance(line[1], (list, tuple)) else ""
                        if text:
                            page_text.append(text)
                all_text.append(f"[第{page_num + 1}页]\n" + "\n".join(page_text))

        doc.close()
        result["text"] = "\n\n".join(all_text)
        result["success"] = bool(result["text"].strip())
        return result

    except Exception as e:
        error_msg = f"PaddleOCR识别失败: {e}"
        logger.warning(error_msg)
        result["error"] = error_msg
        return result


def _ocr_with_tesseract(pdf_bytes: bytes, lang: str = "chi_sim") -> dict:
    """使用Tesseract OCR识别PDF中的文字

    Args:
        pdf_bytes: PDF文件字节内容
        lang: 语言，默认中文简体 "chi_sim"

    Returns:
        dict: {"text": str, "pages": int, "success": bool, "error": str}
    """
    result = {"text": "", "pages": 0, "success": False, "error": ""}
    try:
        import fitz  # PyMuPDF
        import subprocess
        import tempfile

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result["pages"] = len(doc)

        all_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                tmp_img.write(img_bytes)
                img_path = tmp_img.name

            try:
                output_base = tempfile.mktemp()
                subprocess.run(
                    ["tesseract", img_path, output_base, "-l", lang, "--psm", "6"],
                    capture_output=True, timeout=60
                )
                output_path = output_base + ".txt"
                if os.path.exists(output_path):
                    with open(output_path, "r", encoding="utf-8") as f:
                        page_text = f.read().strip()
                    if page_text:
                        all_text.append(f"[第{page_num + 1}页]\n{page_text}")
                    os.unlink(output_path)
            finally:
                if os.path.exists(img_path):
                    os.unlink(img_path)

        doc.close()
        result["text"] = "\n\n".join(all_text)
        result["success"] = bool(result["text"].strip())
        return result

    except Exception as e:
        error_msg = f"Tesseract识别失败: {e}"
        logger.warning(error_msg)
        result["error"] = error_msg
        return result


def ocr_pdf(pdf_bytes: bytes, lang: str = "ch") -> dict:
    """对扫描件PDF进行OCR文字识别

    自动检测可用的OCR引擎（PaddleOCR > Tesseract），
    按优先级依次尝试。

    Args:
        pdf_bytes: PDF文件字节内容
        lang: 语言参数，默认中文

    Returns:
        dict: {
            "text": str,          # 识别后的文字
            "pages": int,         # 页数
            "engine": str,        # 使用的引擎 ("paddleocr" / "tesseract" / "none")
            "success": bool,      # 是否成功
            "error": str          # 错误信息（如果失败）
        }
    """
    result = {"text": "", "pages": 0, "engine": "none", "success": False, "error": ""}

    # 尝试PaddleOCR
    if _check_paddleocr():
        logger.info("使用PaddleOCR进行识别...")
        ocr_result = _ocr_with_paddleocr(pdf_bytes, lang)
        if ocr_result["success"]:
            result["text"] = ocr_result["text"]
            result["pages"] = ocr_result["pages"]
            result["engine"] = "paddleocr"
            result["success"] = True
            return result
        else:
            result["error"] = ocr_result.get("error", "PaddleOCR失败")
            logger.warning(f"PaddleOCR失败: {ocr_result.get('error')}，尝试Tesseract...")
    else:
        logger.info("PaddleOCR未安装，检查Tesseract...")

    # 尝试Tesseract
    if _check_tesseract():
        tess_lang = "chi_sim" if lang in ("ch", "chi_sim") else lang
        ocr_result = _ocr_with_tesseract(pdf_bytes, tess_lang)
        if ocr_result["success"]:
            result["text"] = ocr_result["text"]
            result["pages"] = ocr_result["pages"]
            result["engine"] = "tesseract"
            result["success"] = True
            return result
        else:
            err = ocr_result.get("error", "Tesseract失败")
            result["error"] = (result["error"] + "; " + err) if result["error"] else err
    else:
        err_msg = "Tesseract未安装或不可用"
        result["error"] = (result["error"] + "; " + err_msg) if result["error"] else err_msg

    if not result["success"]:
        result["error"] = (
            f"OCR不可用。{result['error']}\n\n"
            f"请安装OCR引擎：\n"
            f"  - PaddleOCR: pip install paddleocr\n"
            f"  - Tesseract: brew install tesseract (macOS) 或 apt install tesseract-ocr (Linux)"
        )

    return result


def get_ocr_status() -> dict:
    """检查系统中OCR引擎的可用状态

    Returns:
        dict: {
            "paddleocr": bool,
            "tesseract": bool,
            "any_available": bool,
            "message": str
        }
    """
    has_paddle = _check_paddleocr()
    has_tesseract = _check_tesseract()

    messages = []
    if has_paddle:
        messages.append("PaddleOCR ✅ 可用")
    else:
        messages.append("PaddleOCR ❌ 未安装 (pip install paddleocr)")
    if has_tesseract:
        messages.append("Tesseract ✅ 可用")
    else:
        messages.append("Tesseract ❌ 未安装")

    return {
        "paddleocr": has_paddle,
        "tesseract": has_tesseract,
        "any_available": has_paddle or has_tesseract,
        "message": " | ".join(messages),
    }
