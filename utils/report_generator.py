"""
报告生成模块 - 成果报告 + 过程报告
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_full_report(session_data: dict) -> str:
    """生成完整的文献综述报告 (Markdown格式)

    Args:
        session_data: 会话数据，包含文献信息、提取结果、评价结果、合成结果

    Returns:
        str: 报告Markdown文本
    """
    papers = session_data.get("papers", [])
    extraction = session_data.get("extraction_results", [])
    rob = session_data.get("rob_results", [])
    synthesis_text = session_data.get("synthesis_text", "")

    now = datetime.now().strftime("%Y年%m月%d日")
    total_papers = len(papers)
    extracted = len([r for r in extraction if "error" not in r])

    lines = [
        "---",
        "title: 文献综述报告",
        f"date: {now}",
        "---",
        "",
        "# 文献综述报告",
        "",
        f"> 由循证分析智能体辅助生成 | 生成日期: {now}",
        "",
        "## 摘要",
        "",
        f"本综述共纳入 {total_papers} 篇文献，完成数据提取 {extracted} 篇。",
        "本报告由AI辅助生成，学生已审核确认提取数据的准确性。",
        "",
        "## 1. 引言",
        "",
        "（请在此补充研究背景和目的）",
        "",
        "## 2. 方法",
        "",
        "### 2.1 文献纳入标准",
        "（请在此补充PICOT和纳入/排除标准）",
        "",
        "### 2.2 检索策略",
        "（请在此补充检索数据库、检索式和检索时间）",
        "",
        "### 2.3 数据提取",
        f"由循证分析智能体按照标准化模板提取数据，学生逐条审核确认。共提取 {extracted}/{total_papers} 篇文献数据。",
        "",
        "### 2.4 质量评价",
        "采用Cochrane偏倚风险评价工具（针对RCT）或相应评价工具（针对非RCT研究），由AI辅助评价，学生审核确认。",
        "",
        "### 2.5 分析方法",
        "（请在此补充使用的分析方法，如叙事性合成/Meta分析等）",
        "",
        "## 3. 结果",
        "",
        "### 3.1 文献筛选结果",
        f"共纳入 {total_papers} 篇文献。",
        "",
        "### 3.2 研究特征",
        "",
    ]

    # 研究特征表
    if extraction:
        lines.append("| 作者/年份 | 研究设计 | 样本量 | 研究对象 | 主要结局指标 |")
        lines.append("|-----------|---------|--------|---------|------------|")
        for r in extraction:
            if "error" in r:
                continue
            lines.append(
                f"| {r.get('author_year', '未知')[:20]} "
                f"| {r.get('study_design', '')[:15]} "
                f"| {r.get('sample_size', '')} "
                f"| {r.get('population', '')[:25]} "
                f"| {r.get('outcome_measures', '')[:25]} |"
            )
        lines.append("")

    # 质量评价
    if rob:
        lines.append("### 3.3 质量评价结果")
        lines.append("")
        lines.append("| 文献 | 总体评价 |")
        lines.append("|------|---------|")
        for r in rob:
            label = {"low": "低偏倚风险", "high": "高偏倚风险", "unclear": "偏倚风险不清楚"}
            overall = label.get(r.get("overall", ""), "不清楚")
            lines.append(f"| {r.get('paper_title', '')[:30]} | {overall} |")
        lines.append("")

    # 描述性总结
    if extraction:
        lines.append("### 3.4 描述性总结")
        lines.append("")
        for r in extraction:
            if "error" in r:
                continue
            author = r.get("author_year", r.get("paper", "未知"))
            findings = r.get("main_findings", "")
            lines.append(f"- **{author}**：{findings[:100]}")
        lines.append("")

    # 合成结果
    if synthesis_text:
        lines.append("### 3.5 证据合成结果")
        lines.append("")
        lines.append(synthesis_text[:500])
        lines.append("")

    # 讨论与结论
    lines.extend([
        "## 4. 讨论",
        "",
        "（请在此补充对研究结果的讨论）",
        "",
        "## 5. 结论",
        "",
        "（请在此补充本综述的主要结论）",
        "",
        "## 参考文献",
        "",
    ])

    for idx, r in enumerate(extraction, 1):
        if "error" in r:
            continue
        author = r.get("author_year", r.get("paper", "未知"))
        title = r.get("title", "未报告标题")
        lines.append(f"[{idx}] {author}. {title}.")

    return "\n".join(lines)


def generate_process_report(session_data: dict) -> str:
    """生成过程性工作报告

    记录学生与AI交互的全过程，供教师评估学习投入度
    """
    log = session_data.get("process_log", [])
    papers = session_data.get("papers", [])
    extraction = session_data.get("extraction_results", [])
    rob = session_data.get("rob_results", [])

    now = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    lines = [
        "# 过程性工作报告",
        "",
        f"> 生成时间: {now}",
        "",
        "## 1. 基本统计",
        "",
        f"- 上传文献数: {len(papers)} 篇",
        f"- 完成提取数: {len([r for r in extraction if 'error' not in r])} 篇",
        f"- 完成质量评价: {len(rob)} 篇",
        f"- 操作记录数: {len(log)} 条",
        "",
        "## 2. 操作时间线",
        "",
    ]

    if log:
        lines.append("| 时间 | 操作 | 详情 |")
        lines.append("|------|------|------|")
        for entry in log:
            t = entry.get("time", "")[:19]
            op = entry.get("operation", "")
            detail = entry.get("detail", "")[:50]
            lines.append(f"| {t} | {op} | {detail} |")
    else:
        lines.append("（无详细操作记录）")
    lines.append("")

    # 提取结果修改记录
    modified = [r for r in extraction if r.get("_student_modified")]
    if modified:
        lines.append(f"## 3. 学生修改记录")
        lines.append("")
        lines.append(f"学生共修改了 {len(modified)} 篇文献的提取数据：")
        for r in modified:
            lines.append(f"- {r.get('paper', '')}")
        lines.append("")

    # 教师评估区
    lines.extend([
        "## 4. 教师评估",
        "",
        "| 评估维度 | 评分 (1-5) | 备注 |",
        "|---------|-----------|------|",
        "| 文献上传完整性 | | |",
        "| 数据审核仔细程度 | | |",
        "| 质量评价参与度 | | |",
        "| 报告撰写质量 | | |",
        "| 总体学习投入度 | | |",
        "",
        "**教师综合评价**：",
        "",
        "（教师在此填写综合评价和建议）",
        "",
        "---",
        "*本报告由循证分析智能体自动生成。*",
    ])

    return "\n".join(lines)


def export_to_markdown(report_text: str) -> bytes:
    """导出为Markdown文件

    Returns:
        bytes: 文件内容的字节数据
    """
    return report_text.encode("utf-8")


def add_process_log(session_data: dict, operation: str, detail: str = ""):
    """向过程日志中添加一条记录"""
    if "process_log" not in session_data:
        session_data["process_log"] = []
    session_data["process_log"].append({
        "time": datetime.now().isoformat(),
        "operation": operation,
        "detail": detail
    })
