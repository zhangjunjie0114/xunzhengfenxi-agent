"""
PDF解析模块 - 基于PyMuPDF(fitz)实现
支持从文件路径和字节流两种方式输入
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_pdf(file_path_or_bytes, is_bytes: bool = False) -> dict:
    """解析PDF文件，提取文本和元数据
    
    Args:
        file_path_or_bytes: 文件路径（str）或文件字节内容（bytes）
        is_bytes: True表示输入为字节流，False表示输入为文件路径
    
    Returns:
        dict: {
            "text": 全文文本,
            "pages": 页码数量,
            "metadata": {标题, 作者等},
            "page_texts": 每页文本列表,
            "success": bool,
            "error": 错误信息(如果失败)
        }
    """
    import fitz  # PyMuPDF
    
    result = {
        "text": "",
        "pages": 0,
        "metadata": {},
        "page_texts": [],
        "success": False,
        "error": ""
    }
    
    try:
        if is_bytes:
            doc = fitz.open(stream=file_path_or_bytes, filetype="pdf")
        else:
            doc = fitz.open(file_path_or_bytes)
        
        result["pages"] = len(doc)
        
        # 提取元数据
        meta = doc.metadata
        result["metadata"] = {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
        }
        
        # 提取每页文本
        page_texts = []
        full_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            page_texts.append(text)
            full_text.append(f"[第{page_num + 1}页]\n{text}")
        
        result["page_texts"] = page_texts
        result["text"] = "\n\n".join(full_text)
        result["success"] = True
        
        doc.close()
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"PDF解析失败: {error_msg}")
        result["error"] = f"PDF解析失败: {error_msg}"
        result["success"] = False
    
    return result


def extract_metadata(text: str) -> dict:
    """从文本中提取文献基本信息
    
    Args:
        text: 文献全文文本
    
    Returns:
        dict: 包含标题、作者、期刊、年份等基本信息
    """
    metadata = {
        "title": "",
        "authors": "",
        "journal": "",
        "year": "",
        "doi": "",
    }
    
    # 尝试从文本开头提取标题（通常在第一段）
    lines = text.split('\n')
    # 过滤空行
    lines = [l.strip() for l in lines if l.strip()]
    
    if lines:
        # 第一段非空行通常为标题
        metadata["title"] = lines[0][:200]  # 截断过长的标题
    
    # 尝试提取年份
    year_pattern = r'(19\d{2}|20\d{2})'
    years = re.findall(year_pattern, text)
    if years:
        # 取出现最频繁的年份
        from collections import Counter
        year_counts = Counter(years)
        metadata["year"] = year_counts.most_common(1)[0][0]
    
    # 尝试提取DOI
    doi_pattern = r'(10\.\d{4,}/[-._;()/:A-Za-z0-9]+)'
    dois = re.findall(doi_pattern, text)
    if dois:
        metadata["doi"] = dois[0]
    
    return metadata


def get_pdf_preview(text: str, max_chars: int = 500) -> str:
    """获取PDF文本预览
    
    Args:
        text: 全文文本
        max_chars: 最大字符数
    
    Returns:
        str: 预览文本
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...\n[内容已截断，点击'查看原文'展开全文]"


if __name__ == "__main__":
    # 测试入口
    import sys
    if len(sys.argv) > 1:
        result = parse_pdf(sys.argv[1])
        print(f"页数: {result['pages']}")
        print(f"元数据: {result['metadata']}")
        print(f"成功: {result['success']}")
        if result['error']:
            print(f"错误: {result['error']}")
        if result['text']:
            print(f"文本预览 (前300字): {result['text'][:300]}")
    else:
        print("用法: python pdf_parser.py <pdf文件路径>")
