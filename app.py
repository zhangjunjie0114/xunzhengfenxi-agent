"""
循证分析智能体 (Evidence Analysis Agent)
基于Streamlit的文献综述辅助工具 — V4 Wizard 重构版
"""
import streamlit as st
import os
import json
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ========== 页面配置 ==========
st.set_page_config(
    page_title="循证分析智能体",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a Bug': None,
        'About': None,
    }
)

# ========== 精确隐藏 Streamlit Chrome ==========
# 只隐藏不需要的原生 UI，保留侧边栏及其展开/折叠控件
_structural_css = """
<style>
/* 隐藏顶部工具栏（Deploy按钮 + 三点菜单）——保留侧边栏控件 */
.stDeployButton {display: none !important;}
[data-testid="stDeployButton"] {display: none !important;}
[data-testid="stAppDeployButton"] {display: none !important;}
#MainMenu {display: none !important;}

/* 隐藏页脚 */
footer {display: none !important;}
[data-testid="stFooter"] {display: none !important;}

/* 隐藏全屏和管理按钮 */
button[title*="fullscreen"] {display: none !important;}
button[title*="Manage"] {display: none !important;}

/* 隐藏 Streamlit 水印 */
.stApp a[href*="streamlit"] {display: none !important;}
a[href*="streamlit"] {display: none !important;}

/* 表格横向滚动 */
div[data-testid="stMarkdownContainer"] table {
    display: block; overflow-x: auto; white-space: nowrap; max-width: 100%;
}
</style>
"""
st.html(_structural_css)

# ========== 导入工具模块 ==========
from utils.llm_caller import call_llm, test_connection, PROVIDER_MODELS, DEFAULT_MODELS
from utils.pdf_parser import parse_pdf
from utils.data_extractor import load_template, extract_from_papers, results_to_dataframe, dataframe_to_results
from utils.risk_of_bias import (
    assess_rob, generate_rob_chart, generate_rob_code,
    generate_traffic_light, generate_multi_outcome_traffic_light,
    generate_rob_summary_bar,
    COCHRANE_TOOL_INFO, EPHPP_TOOL_INFO
)
from utils.synthesis import (
    generate_study_characteristics_table,
    generate_descriptive_summary,
    generate_narrative_synthesis,
    generate_forest_plot,
    generate_forest_plot_code,
    generate_meta_analysis_forest,
    determine_effect_measure,
    ALL_SUMMARY_METHODS,
    generate_prisma_flowchart,
)
from utils.meta_analysis import (
    parse_studies_from_extraction,
    compute_meta_analysis,
    compute_leave_one_out,
    compute_subgroup_analysis,
    compute_funnel_plot_data,
    prepare_meta_data_for_report,
)
from utils.report_generator import (
    generate_full_report,
    generate_process_report,
    export_to_markdown,
    generate_discussion_outline,
    search_external_evidence,
    generate_literature_summary,
    format_apa_citation,
    format_chinese_citation,
    format_references,
    render_references,
    generate_paper_abstract,
    generate_paper_introduction,
    generate_paper_methods,
    generate_paper_results,
    generate_paper_discussion,
    generate_full_paper_draft,
    merge_full_paper,
)

# ========== Wizard 步骤定义 ==========
WIZARD_STEPS = [
    {"id": 1, "name": "文献上传", "icon": "📄", "key": "literature"},
    {"id": 2, "name": "数据提取", "icon": "📊", "key": "extraction"},
    {"id": 3, "name": "质量评价", "icon": "✅", "key": "quality"},
    {"id": 4, "name": "证据合成", "icon": "📝", "key": "synthesis"},
    {"id": 5, "name": "报告生成", "icon": "📋", "key": "report"},
]

# ========== 会话状态初始化 ==========
def init_session_state():
    """初始化所有会话状态变量"""
    defaults = {
        "provider": "DeepSeek V4 (本地代理)",
        "api_key": "",
        "model": "deepseek-v4-flash",
        "api_base": "https://api.deepseek.com/v1",
        "student_id": "",
        "student_name": "",
        "papers": [],
        "paper_texts": {},
        "extraction_results": [],
        "extraction_template": None,
        "rob_results": [],
        "rob_tool": "rob2",
        "rob_outcomes": [],
        "rob_current_outcome": "",
        "synthesis_results": {},
        "wizard_step": 1,
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "process_log": [],
        "initialized": True,
        "connection_status": None,
        "uploaded_files_processed": [],
        "meta_result": None,
        "meta_studies": [],
        "meta_em": "SMD",
        "meta_model": "random",
        "paper_sections": {},
        "paper_step": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()

# ========== 工具函数 ==========

def progress_callback(current, total, message):
    """进度回调函数"""
    progress_placeholder = st.session_state.get("progress_placeholder")
    status_text = st.session_state.get("status_text")
    if progress_placeholder is not None:
        progress_placeholder.progress(current / total)
    if status_text is not None:
        status_text.text(f"{message} ({current}/{total})")
    st.session_state.progress_value = current / total


def get_template_path():
    """获取模板路径"""
    return os.path.join(os.path.dirname(__file__), "templates", "extraction_template.json")


def get_student_dir():
    """获取当前学生的会话目录"""
    sid = st.session_state.get("student_id", "")
    if not sid:
        return None
    student_dir = os.path.join(os.path.dirname(__file__), "sessions", sid)
    os.makedirs(student_dir, exist_ok=True)
    return student_dir


def save_session():
    """保存会话数据到学生目录"""
    sid = st.session_state.get("student_id", "")
    if not sid:
        st.toast("⚠️ 请先在侧边栏填写学号", icon="⚠️")
        return False

    try:
        student_dir = get_student_dir()
        if not student_dir:
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_data_{timestamp}.json"

        data = {
            "student_id": sid,
            "student_name": st.session_state.get("student_name", ""),
            "papers": st.session_state.papers,
            "extraction_results": st.session_state.extraction_results,
            "rob_results": st.session_state.rob_results,
            "synthesis_results": st.session_state.synthesis_results,
            "process_log": st.session_state.process_log,
            "session_id": st.session_state.session_id,
            "wizard_step": st.session_state.wizard_step,
            "saved_at": timestamp,
        }
        with open(os.path.join(student_dir, filename), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False


def load_session(session_path: str):
    """从本地恢复会话数据"""
    try:
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state.papers = data.get("papers", [])
        st.session_state.extraction_results = data.get("extraction_results", [])
        st.session_state.rob_results = data.get("rob_results", [])
        st.session_state.synthesis_results = data.get("synthesis_results", {})
        st.session_state.process_log = data.get("process_log", [])
        st.session_state.session_id = data.get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
        st.session_state.student_id = data.get("student_id", st.session_state.student_id)
        st.session_state.student_name = data.get("student_name", st.session_state.student_name)
        st.session_state.wizard_step = data.get("wizard_step", 1)
        saved_at = data.get("saved_at", "未知")
        st.toast(f"📂 已恢复 {saved_at} 的保存记录", icon="✅")
        return True
    except Exception as e:
        st.error(f"恢复失败: {e}")
        return False


def log_operation(operation: str, detail: str = ""):
    """记录操作日志"""
    if "process_log" not in st.session_state:
        st.session_state.process_log = []
    st.session_state.process_log.append({
        "time": datetime.now().isoformat(),
        "operation": operation,
        "detail": detail
    })


# ========== 步骤完成条件判断 ==========

def can_advance_from(step: int) -> tuple[bool, str]:
    """检查当前步骤是否满足前进条件，返回 (是否可以前进, 原因说明)"""
    if step == 1:
        has_papers = any("✅" in p.get("status", "") for p in st.session_state.papers)
        if not has_papers:
            return False, "请先上传并成功解析至少一篇文献"
        return True, ""
    elif step == 2:
        if not st.session_state.extraction_results:
            return False, "请先完成数据提取"
        return True, ""
    elif step == 3:
        evaluated = [o for o in st.session_state.rob_outcomes if o.get("results")]
        if not evaluated:
            return False, "请先完成至少一个结局的质量评价"
        return True, ""
    elif step == 4:
        return True, ""
    elif step == 5:
        return True, ""
    return True, ""


# ========== 侧边栏 ==========

def render_sidebar():
    """渲染侧边栏：学生身份、API 配置、会话管理"""
    with st.sidebar:
        # ===== 学生身份 =====
        st.markdown("### 🧑‍🎓 学生信息")
        st.caption("填写学号和姓名后可使用保存/恢复功能")

        student_id = st.text_input(
            "学号",
            value=st.session_state.student_id,
            key="sidebar_student_id",
            placeholder="请输入学号",
        )
        st.session_state.student_id = student_id.strip()

        student_name = st.text_input(
            "姓名",
            value=st.session_state.student_name,
            key="sidebar_student_name",
            placeholder="请输入姓名",
        )
        st.session_state.student_name = student_name.strip()

        st.divider()

        # ===== API 配置 =====
        st.markdown("### ⚙️ API 配置")

        provider = st.selectbox(
            "API 提供商",
            list(PROVIDER_MODELS.keys()),
            index=list(PROVIDER_MODELS.keys()).index(st.session_state.provider)
            if st.session_state.provider in PROVIDER_MODELS else 0,
            key="sidebar_provider",
        )
        st.session_state.provider = provider

        available_models = PROVIDER_MODELS.get(provider, [])
        default_model = DEFAULT_MODELS.get(provider, available_models[0] if available_models else "")
        current_model = st.session_state.model
        if current_model not in available_models:
            current_model = default_model

        model = st.selectbox(
            "模型",
            available_models,
            index=available_models.index(current_model) if current_model in available_models else 0,
            key="sidebar_model"
        )
        st.session_state.model = model

        api_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.api_key,
            key="sidebar_api_key",
            placeholder="请输入你的 API Key",
            help="你的 API Key 仅在当前会话内存中，不会保存到服务器",
        )
        st.session_state.api_key = api_key

        if "第三方" in provider or "DeepSeek" in provider:
            api_base = st.text_input(
                "API 地址",
                value=st.session_state.api_base or "https://api.deepseek.com/v1",
                key="sidebar_api_base",
            )
            st.session_state.api_base = api_base

        if st.button("🔄 测试连接", key="sidebar_test_conn", width="stretch"):
            if not api_key and "Ollama" not in provider:
                st.error("请先输入 API Key")
            else:
                with st.spinner("测试连接中..."):
                    success, msg = test_connection(provider, api_key, model,
                                                   st.session_state.get("api_base", ""))
                    if success:
                        st.success(msg)
                        st.session_state.connection_status = "connected"
                    else:
                        st.error(msg)
                        st.session_state.connection_status = "failed"

        status = st.session_state.connection_status
        if status == "connected":
            st.caption("✅ API 已连接")
        elif status == "failed":
            st.caption("❌ API 连接失败")
        st.caption(f"当前模型: {st.session_state.model}")

        st.divider()

        # ===== 会话管理 =====
        st.markdown("### 💾 会话管理")

        if not st.session_state.student_id:
            st.caption("⚠️ 请先在上方填写学号")
        else:
            # 保存
            if st.button("💾 保存当前工作", key="sidebar_save", width="stretch"):
                if save_session():
                    st.toast("✅ 已保存当前工作")
                    log_operation("保存工作进度")

            # 恢复 —— 扫描该学生的会话目录
            student_dir = os.path.join(os.path.dirname(__file__), "sessions", st.session_state.student_id)
            if os.path.exists(student_dir):
                session_files = sorted(
                    [f for f in os.listdir(student_dir) if f.startswith("session_data_") and f.endswith(".json")],
                    reverse=True
                )
                if session_files:
                    options = ["（选择保存记录）"] + session_files
                    selected = st.selectbox(
                        f"学号 {st.session_state.student_id} 的已保存记录",
                        options,
                        key="sidebar_session",
                        format_func=lambda x: x.replace("session_data_", "").replace(".json", "") if x != options[0] else x
                    )
                    if selected != options[0]:
                        if st.button("📂 恢复选中记录", key="sidebar_load", width="stretch"):
                            data_path = os.path.join(student_dir, selected)
                            if load_session(data_path):
                                st.success("✅ 恢复成功")
                                st.rerun()
                else:
                    st.caption("暂无已保存的记录")
            else:
                st.caption("暂无已保存的记录")

        st.divider()

        # ===== 重置 =====
        if st.button("🔄 重置所有数据", key="sidebar_reset", width="stretch", type="secondary"):
            for key in ["papers", "paper_texts", "extraction_results", "rob_results",
                        "rob_outcomes", "synthesis_results", "process_log", "paper_sections"]:
                if key in st.session_state:
                    st.session_state[key] = [] if key != "synthesis_results" and key != "paper_sections" else {}
            st.session_state.paper_sections = {}
            st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.wizard_step = 1
            st.session_state.paper_step = 0
            st.success("已重置所有数据")
            st.rerun()

        st.caption(f"会话ID: {st.session_state.session_id[:16]}...")


# ========== 顶部导航栏渲染 ==========

def render_topbar():
    """渲染顶部导航栏 — 原生 Streamlit 组件"""
    step = st.session_state.wizard_step
    current_step_info = WIZARD_STEPS[step - 1]

    with st.container(border=False):
        col_left, col_center = st.columns([2, 3])

        with col_left:
            st.markdown(f"### :material/science: 循证分析智能体")

        with col_center:
            st.caption(f"步骤 {step}/{len(WIZARD_STEPS)} · {current_step_info['name']}")
            progress_pct = int((step - 1) / (len(WIZARD_STEPS) - 1) * 100)
            st.progress(progress_pct / 100)

    st.divider()


# ========== 步骤头部渲染 ==========

def render_step_header(step_info: dict):
    """渲染步骤标题"""
    st.subheader(f"{step_info['icon']} {step_info['name']}")


# ========== 空状态组件 ==========

def render_empty_state(icon: str, title: str, description: str):
    """渲染空状态占位"""
    st.info(f"{icon} **{title}** — {description}")


# ========== 统计信息横幅 ==========

def render_stat_banner(stats: list[dict]):
    """渲染统计卡片 — stats = [{"label": "", "value": ""}, ...]"""
    cols = st.columns(len(stats))
    for i, s in enumerate(stats):
        with cols[i]:
            st.metric(s['label'], s['value'])


# ========== 步骤 1: 文献上传 ==========

def render_step_literature():
    """文献上传步骤"""
    render_step_header(WIZARD_STEPS[0])

    # 上传区域
    uploaded_files = st.file_uploader(
        "选择 PDF 文献（支持批量上传）",
        type=["pdf"],
        accept_multiple_files=True,
        help="支持一次选择多篇PDF，每篇不超过20MB",
        key="wizard_lit_uploader"
    )

    if uploaded_files:
        processed_file_list = st.session_state.get("uploaded_files_processed", [])
        processed = set(processed_file_list) if isinstance(processed_file_list, list) else set()

        unprocessed = [f for f in uploaded_files if f.name not in processed]

        if unprocessed:
            total = len(uploaded_files)
            progress_bar = st.progress(0, text="正在解析文献...")

            for i, uploaded_file in enumerate(uploaded_files):
                file_name = uploaded_file.name

                if file_name in [p.get("file_name") for p in st.session_state.papers]:
                    progress_bar.progress((i + 1) / total, text=f"⏭️ {file_name} 已存在，跳过")
                    processed.add(file_name)
                    continue

                progress_bar.progress((i + 1) / total, text=f"📖 正在解析: {file_name}")

                try:
                    file_bytes = uploaded_file.getvalue()
                    result = parse_pdf(file_bytes, is_bytes=True)

                    if result["success"]:
                        st.session_state.papers.append({
                            "file_name": file_name,
                            "title": result["metadata"].get("title", file_name),
                            "text": result["text"],
                            "pages": result["pages"],
                            "status": "✅ 解析成功"
                        })
                        st.session_state.paper_texts[file_name] = result["text"]
                        log_operation("上传文献", file_name)
                    else:
                        st.session_state.papers.append({
                            "file_name": file_name,
                            "title": file_name,
                            "text": "",
                            "pages": 0,
                            "status": f"❌ {result['error']}"
                        })
                    processed.add(file_name)
                except Exception as e:
                    st.session_state.papers.append({
                        "file_name": file_name,
                        "title": file_name,
                        "text": "",
                        "pages": 0,
                        "status": f"❌ 解析异常: {str(e)[:50]}"
                    })
                    processed.add(file_name)

            progress_bar.empty()
            st.session_state.uploaded_files_processed = list(processed)
            st.success(f"✅ 已处理 {len(processed)} 篇文献")
    else:
        st.session_state.uploaded_files_processed = []

    st.divider()

    # 文献列表
    if st.session_state.papers:
        success_count = sum(1 for p in st.session_state.papers if "✅" in p.get("status", ""))
        fail_count = sum(1 for p in st.session_state.papers if "❌" in p.get("status", ""))

        render_stat_banner([
            {"label": "已上传文献", "value": str(len(st.session_state.papers))},
            {"label": "解析成功", "value": str(success_count)},
            {"label": "解析失败", "value": str(fail_count)},
        ])

        for idx, paper in enumerate(st.session_state.papers):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            col1.write(f"**{paper.get('file_name', '未知')}**")
            col2.write(f"页数: {paper.get('pages', '?')}")
            col3.write(paper.get("status", ""))
            if col4.button("删除", key=f"wiz_del_{idx}"):
                st.session_state.papers.pop(idx)
                st.rerun()

        with st.expander("📖 预览文献内容"):
            for paper in st.session_state.papers:
                if paper.get("text"):
                    with st.expander(f"📄 {paper.get('file_name', '')} ({paper.get('pages', '?')}页)"):
                        preview = paper["text"][:800]
                        if len(paper["text"]) > 800:
                            preview += "\n\n...（内容较长，已截断）"
                        st.code(preview, language="text")
                else:
                    st.markdown(f"❌ {paper.get('file_name', '')} - 解析失败，无可用文本")

        clear_col, _ = st.columns([1, 4])
        if clear_col.button("🗑️ 清空所有文献", type="secondary", key="wiz_clear_all"):
            st.session_state.papers = []
            st.session_state.paper_texts = {}
            st.rerun()
    else:
        render_empty_state(
            "📂",
            "暂无文献",
            "上传 PDF 格式的文献全文开始分析，支持批量上传",
        )


# ========== 步骤 2: 数据提取 ==========

def render_step_extraction():
    """数据提取步骤"""
    render_step_header(WIZARD_STEPS[1])

    if not st.session_state.papers:
        render_empty_state(
            "📂",
            "请先上传文献",
            "返回上一步上传并解析 PDF 文献后再进行数据提取",
        )
        return

    if not st.session_state.api_key and "Ollama" not in st.session_state.provider:
        st.warning("⚠️ 请先在设置中配置 API Key（点击右上角齿轮图标）")
        return

    has_results = len(st.session_state.extraction_results) > 0

    # 模板编辑
    with st.expander("📋 编辑提取模板", expanded=not has_results):
        st.caption("定义AI提取数据的字段，双击单元格修改，支持增删行")

        if st.session_state.extraction_template is None:
            st.session_state.extraction_template = load_template(get_template_path())

        tmpl_data = []
        for idx, f in enumerate(st.session_state.extraction_template):
            tmpl_data.append({
                "序号": idx + 1,
                "字段名": f["field_name"],
                "显示名称": f["label"],
                "提取说明": f["description"],
                "必填": "是" if f.get("required") else "否",
                "类型": f.get("type", "text")
            })
        import pandas as pd
        tmpl_df = pd.DataFrame(tmpl_data)

        edited_tmpl = st.data_editor(
            tmpl_df,
            width="stretch",
            height=300,
            key="wiz_template_editor",
            column_config={
                "序号": st.column_config.NumberColumn("序号", width=50, disabled=True),
                "字段名": st.column_config.TextColumn("字段名", width=120),
                "显示名称": st.column_config.TextColumn("显示名称", width=120),
                "提取说明": st.column_config.TextColumn("提取说明", width=300),
                "必填": st.column_config.SelectboxColumn("必填", width=60, options=["是", "否"]),
                "类型": st.column_config.SelectboxColumn("类型", width=70, options=["text", "number", "list"]),
            },
            num_rows="dynamic"
        )

        updated_template = []
        for _, row in edited_tmpl.iterrows():
            fname = str(row.get("字段名", "")).strip()
            if fname:
                updated_template.append({
                    "field_name": fname,
                    "label": str(row.get("显示名称", fname)),
                    "description": str(row.get("提取说明", "")),
                    "required": row.get("必填") == "是",
                    "type": row.get("类型", "text")
                })
        st.session_state.extraction_template = updated_template

        col_reset, col_count = st.columns(2)
        col_count.metric("字段数", len(updated_template))
        if col_reset.button("🔄 恢复默认模板", width="stretch", key="wiz_reset_tmpl"):
            st.session_state.extraction_template = load_template(get_template_path())
            st.rerun()

    st.divider()

    # 提取操作
    if not has_results:
        if st.button("🚀 开始提取数据", type="primary", width="stretch", key="wiz_start_extract"):
            papers_data = []
            valid_papers = [p for p in st.session_state.papers if p.get("text")]

            if not valid_papers:
                st.error("没有可解析的文献文本，请检查文献上传状态")
                return

            for p in valid_papers:
                papers_data.append({
                    "file_name": p.get("file_name", ""),
                    "title": p.get("title", p.get("file_name", "")),
                    "text": p.get("text", "")
                })

            progress_placeholder = st.empty()
            status_text = st.empty()
            st.session_state.progress_placeholder = progress_placeholder
            st.session_state.status_text = status_text

            with st.spinner("AI 正在逐篇提取数据..."):
                current_template = st.session_state.extraction_template or load_template(get_template_path())
                results = extract_from_papers(
                    papers_data,
                    current_template,
                    call_llm,
                    progress_callback=progress_callback
                )

            st.session_state.extraction_results = results
            log_operation("数据提取", f"提取 {len(results)} 篇")
            st.success(f"✅ 提取完成！共处理 {len(results)} 篇文献")
            st.rerun()
    else:
        if st.button("🔄 重新提取", width="stretch", key="wiz_reextract"):
            st.session_state.extraction_results = []
            st.rerun()

    # 显示提取结果
    if has_results:
        template = st.session_state.extraction_template or load_template(get_template_path())
        df = results_to_dataframe(st.session_state.extraction_results, template)

        st.markdown("**📋 提取结果（双击单元格可直接编辑，修改自动保存）**")
        st.caption("💡 编辑后数据自动保存，下游模块均使用编辑后的数据")

        edited_df = st.data_editor(
            df,
            width="stretch",
            height=400,
            key="wiz_extraction_editor",
            disabled=["文献", "状态"]
        )

        try:
            if not edited_df.equals(df):
                updated_results = dataframe_to_results(
                    edited_df, template, st.session_state.extraction_results
                )
                st.session_state.extraction_results = updated_results
                st.toast("✅ 修改已自动保存", icon="💾")
        except Exception as e:
            pass

        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 导出 CSV",
                csv,
                "extraction_results.csv",
                "text/csv",
                width="stretch",
                key="wiz_export_csv"
            )
        with col2:
            if st.button("💾 确认保存所有修改", width="stretch", key="wiz_save_extract"):
                log_operation("确认保存提取数据", f"当前共 {len(df)} 篇文献")
                save_session()
                st.success("✅ 已保存到本地会话文件")

        # 溯源查看
        with st.expander("🔍 数据溯源"):
            for idx, r in enumerate(st.session_state.extraction_results):
                if "error" in r:
                    continue
                with st.expander(f"📄 {r.get('paper', f'文献{idx+1}')}"):
                    modified_tag = "✏️ 已编辑" if r.get("_student_modified") else ""
                    st.markdown(f"**提取数据摘要** {modified_tag}")
                    for key, val in r.items():
                        if key.startswith("_") or key in ["paper", "file_name"]:
                            continue
                        if val and val != "未报告":
                            st.markdown(f"- **{key}**: {str(val)[:200]}")
                    st.divider()


# ========== 步骤 3: 质量评价 ==========

def render_step_quality():
    """质量评价步骤"""
    render_step_header(WIZARD_STEPS[2])

    if not st.session_state.extraction_results:
        render_empty_state(
            "📊",
            "请先完成数据提取",
            "返回上一步完成数据提取后再进行质量评价",
        )
        return

    if not st.session_state.api_key and "Ollama" not in st.session_state.provider:
        st.warning("⚠️ 请先在设置中配置 API Key（点击右上角齿轮图标）")
        return

    # 工具选择
    col_tool1, col_tool2 = st.columns([2, 3])
    with col_tool1:
        tool = st.radio(
            "选择评价工具",
            ["Cochrane RoB2", "EPHPP"],
            index=0 if st.session_state.rob_tool == "rob2" else 1,
            horizontal=True,
            key="wiz_rob_tool",
        )
        st.session_state.rob_tool = "rob2" if tool == "Cochrane RoB2" else "ephpp"

    with col_tool2:
        if st.session_state.rob_tool == "rob2":
            st.info(f"**{COCHRANE_TOOL_INFO['name']}** — {COCHRANE_TOOL_INFO['applicable_to']}\n\n"
                    f"{COCHRANE_TOOL_INFO['rating_scale']}")
        else:
            st.info(f"**{EPHPP_TOOL_INFO['name']}** — {EPHPP_TOOL_INFO['applicable_to']}\n\n"
                    f"{EPHPP_TOOL_INFO['rating_scale']}")

    st.divider()

    # Outcome 管理
    st.markdown("**📌 结局（Outcome）管理**")
    st.caption("添加多个结局指标，每个独立生成红绿灯图")

    col_out1, col_out2, col_out3 = st.columns([3, 1, 1])
    with col_out1:
        new_outcome = st.text_input("新增结局名称", placeholder="如：焦虑、抑郁、生活质量...",
                                    key="wiz_new_outcome")
    with col_out2:
        if st.button("➕ 添加结局", width="stretch", key="wiz_add_outcome"):
            name = new_outcome.strip()
            if name:
                existing = [o for o in st.session_state.rob_outcomes if o["name"] == name]
                if not existing:
                    st.session_state.rob_outcomes.append({"name": name, "results": []})
                    st.session_state.rob_current_outcome = name
                    st.rerun()
                else:
                    st.warning(f"结局「{name}」已存在")
            else:
                st.error("请输入结局名称")
    with col_out3:
        if st.session_state.rob_outcomes:
            if st.button("🗑️ 清空所有", width="stretch", key="wiz_clear_outcomes"):
                st.session_state.rob_outcomes = []
                st.session_state.rob_results = []
                st.rerun()

    if st.session_state.rob_outcomes:
        for oi, outcome in enumerate(st.session_state.rob_outcomes):
            col_a, col_b, col_c = st.columns([2, 1, 1])
            status = "✅ 已评价" if outcome["results"] else "⏳ 待评价"
            col_a.markdown(f"**{oi+1}. {outcome['name']}** — {status}")
            if col_b.button(f"🗑️ 删除", key=f"wiz_del_outcome_{oi}"):
                st.session_state.rob_outcomes.pop(oi)
                st.rerun()
            if outcome["results"]:
                if col_c.button(f"🔄 重评", key=f"wiz_redo_outcome_{oi}"):
                    outcome["results"] = []
                    st.rerun()

    st.divider()

    # 评价操作
    if st.session_state.rob_outcomes:
        selected_outcome = st.selectbox(
            "选择要评价的结局",
            [o["name"] for o in st.session_state.rob_outcomes],
            key="wiz_rob_outcome_selector"
        )

        current_outcome_obj = None
        for o in st.session_state.rob_outcomes:
            if o["name"] == selected_outcome:
                current_outcome_obj = o
                break

        outcome_has_results = current_outcome_obj and current_outcome_obj["results"]
        tool_key = st.session_state.rob_tool

        if not outcome_has_results:
            if st.button(f"🚀 开始评价「{selected_outcome}」", type="primary",
                         width="stretch", key="wiz_start_rob"):
                papers_data = []
                for r in st.session_state.extraction_results:
                    if "error" in r:
                        continue
                    paper_text = ""
                    for p in st.session_state.papers:
                        if p.get("file_name") == r.get("file_name") or p.get("title") == r.get("paper"):
                            paper_text = p.get("text", "")
                            break
                    papers_data.append({
                        "title": r.get("paper", ""),
                        "text": paper_text,
                        "study_design": r.get("study_design", ""),
                        "file_name": r.get("file_name", "")
                    })

                if not papers_data:
                    st.error("没有可评价的文献数据")
                    return

                progress_placeholder = st.empty()
                status_text = st.empty()
                st.session_state.progress_placeholder = progress_placeholder
                st.session_state.status_text = status_text

                tool_display = "RoB2" if tool_key == "rob2" else "EPHPP"
                with st.spinner(f"AI 正在使用{tool_display}评价「{selected_outcome}」..."):
                    results = assess_rob(papers_data, call_llm, progress_callback, tool=tool_key)

                if current_outcome_obj is not None:
                    current_outcome_obj["results"] = results
                st.session_state.rob_results = results
                log_operation("质量评价", f"[{tool_display}] {selected_outcome} - {len(results)}篇")
                st.success(f"✅ 「{selected_outcome}」评价完成！")
                st.rerun()

        # 展示评价结果
        if outcome_has_results:
            results = current_outcome_obj["results"]
            n_papers = len(results)

            st.subheader(f"📊 Traffic Light 图 — {selected_outcome}")
            fig = generate_traffic_light(results, tool=tool_key, outcome_name=selected_outcome)
            st.plotly_chart(fig, width="stretch")

            st.subheader("📈 各维度偏倚分布汇总")
            bar_fig = generate_rob_summary_bar(results, tool=tool_key)
            st.plotly_chart(bar_fig, width="stretch")

            evaluated_outcomes = {o["name"]: o["results"]
                                  for o in st.session_state.rob_outcomes if o["results"]}
            if len(evaluated_outcomes) >= 2:
                st.subheader(f"🔄 多结局累计偏倚风险图（{len(evaluated_outcomes)}个结局）")
                multi_fig = generate_multi_outcome_traffic_light(evaluated_outcomes, tool=tool_key)
                st.plotly_chart(multi_fig, width="stretch")

            with st.expander("📋 详细评价结果"):
                if tool_key == "rob2":
                    icon_map = {"low": "🟢", "some_concerns": "🟡", "high": "🔴"}
                    overall_label = {"low": "低风险", "some_concerns": "有些担忧", "high": "高风险"}
                else:
                    icon_map = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}
                    overall_label = {"strong": "强", "moderate": "中", "weak": "弱"}

                for idx, r in enumerate(results):
                    overall = r.get("overall", "some_concerns" if tool_key == "rob2" else "moderate")
                    icon = icon_map.get(overall, "🟡")
                    label = overall_label.get(overall, overall)

                    with st.expander(f"{icon} {r.get('paper_title', f'文献{idx+1}')} — 总体: {label}"):
                        reasoning = r.get("overall_reasoning", "")
                        if reasoning:
                            st.markdown(f"**总体判断依据**：{reasoning[:300]}")
                            st.divider()
                        domains = r.get("domains", {})
                        for did, dval in domains.items():
                            if isinstance(dval, dict):
                                judgment = dval.get("judgment", "")
                                evidence = dval.get("evidence", "")
                                reasoning_text = dval.get("reasoning", "")
                                j_icon = icon_map.get(judgment, "🟡")
                                st.markdown(f"{j_icon} **{did}**: {judgment}")
                                if evidence:
                                    st.caption(f"📎 原文依据: {evidence[:200]}")
                                if reasoning_text:
                                    st.caption(f"💡 推理: {reasoning_text[:200]}")
                                st.divider()

            with st.expander("💻 R 代码备选"):
                r_code = generate_rob_code(results, tool=tool_key)
                st.code(r_code, language="r")
    else:
        render_empty_state(
            "📌",
            "请先添加结局指标",
            "添加至少一个结局（Outcome）后即可开始质量评价",
        )
        st.markdown("""
        > **为什么要添加结局？** 一篇综述通常有3-4个结局指标（如焦虑、抑郁、生活质量），
        > 每个结局独立评价偏倚风险，最终可生成累计叠加视图。
        """)


# ========== 步骤 4: 证据合成 ==========

def render_step_synthesis():
    """证据合成步骤"""
    render_step_header(WIZARD_STEPS[3])

    if not st.session_state.extraction_results:
        render_empty_state(
            "📊",
            "请先完成数据提取",
            "返回上一步完成数据提取后再进行证据合成",
        )
        return

    synth_mode = st.radio(
        "选择合成方式",
        ["📋 研究特征表", "📝 描述性总结", "🔗 叙事性合成",
         "📋 PRISMA 流程图", "📊 Meta 分析", "📐 其他证据总结法"],
        horizontal=True,
        key="wiz_synth_mode"
    )

    st.divider()

    if synth_mode == "📋 研究特征表":
        st.subheader("研究特征总结表 (Study Characteristics Table)")
        rows = []
        for r in st.session_state.extraction_results:
            if "error" in r:
                continue
            rows.append({
                "作者/年份": r.get("author_year", "未知")[:25],
                "研究设计": r.get("study_design", "未报告")[:20],
                "样本量": r.get("sample_size", "未报告"),
                "研究对象": r.get("population", "未报告")[:40],
                "干预措施": r.get("intervention", "未报告")[:40],
                "主要结局指标": r.get("outcome_measures", "未报告")[:40],
                "主要发现": r.get("main_findings", "未报告")[:60],
            })
        if rows:
            import pandas as pd
            df_table = pd.DataFrame(rows)
            st.data_editor(
                df_table, width="stretch",
                height=min(60 + len(rows) * 40, 500),
                key="wiz_study_chars"
            )
            table = generate_study_characteristics_table(st.session_state.extraction_results)
            st.download_button("📥 下载 Markdown 版本", table, "study_characteristics.md", "text/markdown",
                               key="wiz_dl_chars")
        else:
            st.info("暂无有效提取数据")

    elif synth_mode == "📝 描述性总结":
        st.subheader("描述性总结 (Descriptive Summary)")
        summary = generate_descriptive_summary(st.session_state.extraction_results)
        st.markdown(summary)
        st.download_button("📥 下载 Markdown", summary, "descriptive_summary.md", "text/markdown",
                           key="wiz_dl_desc")

    elif synth_mode == "🔗 叙事性合成":
        st.subheader("叙事性合成 (Narrative Synthesis)")
        synthesis = generate_narrative_synthesis(
            st.session_state.extraction_results, st.session_state.rob_results
        )
        st.markdown(synthesis)
        st.session_state.synthesis_results["narrative"] = synthesis
        st.download_button("📥 下载 Markdown", synthesis, "narrative_synthesis.md", "text/markdown",
                           key="wiz_dl_narrative")

    elif synth_mode == "📋 PRISMA 流程图":
        st.subheader("📋 PRISMA 2020 文献筛选流程图")
        col_pr1, col_pr2, col_pr3 = st.columns(3)
        with col_pr1:
            identified = st.number_input("数据库检索记录数", min_value=0, value=0, step=1, key="wiz_pr_ident")
            additional = st.number_input("其他来源记录数", min_value=0, value=0, step=1, key="wiz_pr_add")
            duplicates = st.number_input("去重记录数", min_value=0, value=0, step=1, key="wiz_pr_dup")
        with col_pr2:
            screened = st.number_input("初筛记录数", min_value=0, value=0, step=1, key="wiz_pr_screen")
            excluded = st.number_input("初筛排除数", min_value=0, value=0, step=1, key="wiz_pr_excl")
            full_text = st.number_input("全文获取数", min_value=0, value=0, step=1, key="wiz_pr_ft")
        with col_pr3:
            excluded_fulltext = st.number_input("全文排除数", min_value=0, value=0, step=1, key="wiz_pr_exclft")
            qualitative = st.number_input("纳入定性合成数", min_value=0, value=0, step=1, key="wiz_pr_qual")
            quantitative = st.number_input("纳入定量合成数", min_value=0, value=0, step=1, key="wiz_pr_quant")

        st.markdown("**排除原因明细（可选）：**")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            r1_label = st.text_input("排除原因1", value="非随机对照设计", key="wiz_pr_r1l")
            r1_num = st.number_input("篇数", min_value=0, value=0, step=1, key="wiz_pr_r1n")
        with col_r2:
            r2_label = st.text_input("排除原因2", value="人群不符", key="wiz_pr_r2l")
            r2_num = st.number_input("篇数", min_value=0, value=0, step=1, key="wiz_pr_r2n")
        with col_r3:
            r3_label = st.text_input("排除原因3", value="结局指标不符", key="wiz_pr_r3l")
            r3_num = st.number_input("篇数", min_value=0, value=0, step=1, key="wiz_pr_r3n")

        if st.button("📋 生成 PRISMA 流程图", type="primary", width="stretch", key="wiz_pr_gen"):
            reasons = {}
            if r1_label and r1_num > 0:
                reasons[r1_label] = r1_num
            if r2_label and r2_num > 0:
                reasons[r2_label] = r2_num
            if r3_label and r3_num > 0:
                reasons[r3_label] = r3_num
            with st.spinner("正在生成PRISMA流程图..."):
                fig = generate_prisma_flowchart(
                    identified=identified, additional=additional, duplicates=duplicates,
                    screened=screened, excluded=excluded, full_text=full_text,
                    excluded_fulltext=excluded_fulltext, excluded_reasons=reasons,
                    qualitative=qualitative, quantitative=quantitative,
                )
                st.plotly_chart(fig, width="stretch")
                st.session_state.synthesis_results["prisma_data"] = {
                    "identified": identified, "additional": additional,
                    "duplicates": duplicates, "screened": screened,
                    "excluded": excluded, "full_text": full_text,
                    "excluded_fulltext": excluded_fulltext,
                    "qualitative": qualitative, "quantitative": quantitative,
                }

    elif synth_mode == "📊 Meta 分析":
        render_meta_analysis_section()
    elif synth_mode == "📐 其他证据总结法":
        render_alternative_synthesis_section()

    st.divider()
    st.caption("💡 提示：所有生成的文本建议先由学生审核确认后再用于最终报告。")


# ========== Meta 分析子模块 ==========

def _build_forest_plot(meta_result) -> object:
    """根据 MetaResult 生成Plotly森林图"""
    import plotly.graph_objects as go
    r = meta_result.get_expanded()
    em = r.effect_measure
    null_value = 0 if em in ("MD", "SMD") else 1
    model_label = "随机效应" if r.is_random else "固定效应"

    fig = go.Figure()
    for s in r.study_details:
        fig.add_trace(go.Scatter(
            x=[s["effect"]], y=[s["author"]],
            mode="markers",
            marker={"size": max(8, min(s.get("weight_re", s["weight_fixed"]) / 2, 20)),
                    "color": "#2196F3", "line": {"width": 1, "color": "#1565C0"}},
            error_x={"type": "data", "symmetric": False,
                     "array": [s["ci_upper"] - s["effect"]],
                     "arrayminus": [s["effect"] - s["ci_lower"]]},
            hovertemplate=(
                f"<b>{s['author']}</b><br>{em}: {s['effect']:.3f}<br>"
                f"95%CI: ({s['ci_lower']:.3f}, {s['ci_upper']:.3f})<extra></extra>"
            ), showlegend=False
        ))

    fig.add_trace(go.Scatter(
        x=[r.pooled_effect], y=[f"合并效应量 ({model_label})"],
        mode="markers",
        marker={"size": 20, "color": "#F44336", "symbol": "diamond-wide",
                "line": {"width": 2, "color": "#B71C1C"}},
        error_x={"type": "data", "symmetric": False,
                 "array": [r.pooled_ci_upper - r.pooled_effect],
                 "arrayminus": [r.pooled_effect - r.pooled_ci_lower]},
        hovertemplate=(
            f"<b>合并效应量</b><br>{em}: {r.pooled_effect:.4f}<br>"
            f"95%CI: ({r.pooled_ci_lower:.4f}, {r.pooled_ci_upper:.4f})<br>"
            f"I²={r.i_squared:.1f}%<extra></extra>"
        ), showlegend=False
    ))

    fig.add_vline(x=null_value, line_dash="dash", line_color="gray", opacity=0.6)
    fig.update_layout(
        title=(f"<b>森林图</b><br><span style='font-size:12px;color:#666'>"
               f"{em} | {model_label} | {r.n_studies}篇研究 | I²={r.i_squared:.1f}%</span>"),
        xaxis={"title": f"{em} (95% CI)", "zeroline": False},
        yaxis={"title": "", "autorange": "reversed"},
        height=max(300, r.n_studies * 50 + 120),
        showlegend=False, hovermode="y",
        margin={"l": 10, "r": 10, "t": 60, "b": 50},
        plot_bgcolor="white", xaxis_showgrid=True, xaxis_gridcolor="#f0f0f0"
    )
    return fig


def _render_heterogeneity_tab(meta_result):
    """渲染异质性详情"""
    r = meta_result
    col_h1, col_h2, col_h3 = st.columns(3)
    col_h1.metric("Cochran's Q", f"{r.q_stat:.3f}")
    col_h2.metric("自由度 (df)", r.q_df)
    col_h3.metric("Q检验P值", f"{r.q_p_value:.4f}")

    col_h4, col_h5, col_h6 = st.columns(3)
    col_h4.metric("I²", f"{r.i_squared:.1f}%")
    col_h5.metric("τ² (组间方差)", f"{r.tau_squared:.4f}")
    col_h6.metric("H统计量", f"{r.h_statistic:.2f}")

    if r.i_squared <= 25:
        het_desc, het_color = "低异质性", "🟢"
    elif r.i_squared <= 50:
        het_desc, het_color = "中等异质性", "🟡"
    elif r.i_squared <= 75:
        het_desc, het_color = "较高异质性", "🟠"
    else:
        het_desc, het_color = "高异质性", "🔴"

    st.info(f"{het_color} **异质性判断**：I²={r.i_squared:.1f}% 表示{het_desc}。"
            + ("建议使用随机效应模型并探索异质性来源。" if r.i_squared > 50 else ""))

    if r.q_p_value < 0.05 and r.i_squared > 50:
        st.warning("⚠️ Q检验显著（P<0.05）且I²>50%，提示研究间存在真实异质性。")

    st.markdown("**各研究权重详情：**")
    rows = []
    for sd in r.study_details:
        rows.append({
            "研究": sd["author"],
            "效应量": f"{sd['effect']:.3f}",
            "95%CI": f"({sd['ci_lower']:.3f}, {sd['ci_upper']:.3f})",
            "固定效应权重": f"{sd['weight_fixed_pct']:.1f}%",
            "随机效应权重": f"{sd['weight_re_pct']:.1f}%",
        })
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_sensitivity_tab(studies, effect_measure, model_str):
    """渲染敏感性分析"""
    if len(studies) < 3:
        st.info("💡 需要至少3篇研究才能进行leave-one-out敏感性分析。")
        return

    with st.spinner("正在计算leave-one-out敏感性分析..."):
        loo_results = compute_leave_one_out(studies, effect_measure, model_str)

    if not loo_results:
        st.info("无法进行敏感性分析。")
        return

    st.markdown("**Leave-one-out 敏感性分析：**")
    rows = []
    for res in loo_results:
        r_exp = res.get_expanded()
        rows.append({
            "排除的研究": res.warning.replace("排除「", "").replace("」后的分析结果", ""),
            "合并效应量": f"{r_exp.pooled_effect:.3f}",
            "95%CI下限": f"{r_exp.pooled_ci_lower:.3f}",
            "95%CI上限": f"{r_exp.pooled_ci_upper:.3f}",
            "I²(%)": f"{res.i_squared:.1f}",
        })

    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        import plotly.graph_objects as go
        fig = go.Figure()
        for i, res in enumerate(loo_results):
            r_exp = res.get_expanded()
            excluded_name = res.warning.replace("排除「", "").replace("」后的分析结果", "")
            fig.add_trace(go.Scatter(
                x=[r_exp.pooled_effect], y=[excluded_name],
                mode="markers",
                marker={"size": 12, "color": "#FF9800"},
                error_x={"type": "data", "symmetric": False,
                         "array": [r_exp.pooled_ci_upper - r_exp.pooled_effect],
                         "arrayminus": [r_exp.pooled_effect - r_exp.pooled_ci_lower]},
                showlegend=False,
            ))

        full_result = compute_meta_analysis(studies, effect_measure, model_str)
        full_exp = full_result.get_expanded()
        fig.add_vline(x=full_exp.pooled_effect, line_dash="dash", line_color="red",
                      annotation_text="全部研究合并效应量")
        fig.update_layout(
            title="Leave-one-out 敏感性分析",
            xaxis={"title": f"{effect_measure} (95% CI)"},
            yaxis={"title": "", "autorange": "reversed"},
            height=max(200, len(loo_results) * 50 + 80),
            plot_bgcolor="white", margin={"l": 10, "r": 10, "t": 40, "b": 50}
        )
        st.plotly_chart(fig, width="stretch")

    st.caption("💡 如果排除任何单项研究后合并效应量未发生实质性变化，说明结果稳健。")


def _render_subgroup_tab(extraction_results, effect_measure, model_str):
    """渲染亚组分析"""
    subgroup_field = st.selectbox(
        "选择亚组分类依据",
        ["study_design", "country", "population"],
        format_func=lambda x: {"study_design": "研究设计", "country": "国家/地区",
                                "population": "研究对象"}.get(x, x),
        key="wiz_subgroup_field"
    )

    if st.session_state.get("meta_studies") and st.session_state.get("meta_em") == effect_measure:
        import copy
        studies = copy.deepcopy(st.session_state.meta_studies)
    else:
        studies, _ = parse_studies_from_extraction(extraction_results, effect_measure)

    if len(studies) < 3:
        st.info("💡 需要至少3篇研究才能进行有意义的亚组分析。")
        return

    for s in studies:
        for r in extraction_results:
            if "error" in r and r.get("author_year", "")[:20] == s.author:
                continue
            if r.get("author_year", "")[:20] == s.author or r.get("paper", "")[:20] == s.author:
                s.subgroup = r.get(subgroup_field, "未分类")[:20]
                break

    result = compute_subgroup_analysis(studies, effect_measure, model_str)

    st.markdown("**亚组分析结果：**")
    for g_name, g_result in result["groups"].items():
        with st.expander(f"📁 {g_name}（{g_result.n_studies}篇研究）", expanded=True):
            g_exp = g_result.get_expanded()
            st.markdown(g_result.get_summary_text())

    st.divider()
    st.markdown(f"**组间异质性检验**：Q_between={result['q_between']:.3f}，P={result['q_between_p']:.4f}")
    if result["q_between_p"] < 0.05:
        st.info("📊 组间异质性显著（P<0.05），提示亚组间效应量存在差异。")
    else:
        st.info("📊 组间异质性不显著，亚组间效应量未见明显差异。")

    import plotly.graph_objects as go
    fig = go.Figure()
    for i, (g_name, g_result) in enumerate(result["groups"].items()):
        g_exp = g_result.get_expanded()
        fig.add_trace(go.Scatter(
            x=[g_exp.pooled_effect], y=[g_name],
            mode="markers",
            marker={"size": 15, "color": ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"][i % 4]},
            error_x={"type": "data", "symmetric": False,
                     "array": [g_exp.pooled_ci_upper - g_exp.pooled_effect],
                     "arrayminus": [g_exp.pooled_effect - g_exp.pooled_ci_lower]},
            showlegend=False,
        ))

    fig.add_vline(x=0 if effect_measure in ("MD", "SMD") else 1,
                  line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="亚组分析森林图",
        xaxis={"title": f"{effect_measure} (95% CI)"},
        yaxis={"title": "", "autorange": "reversed"},
        height=max(200, len(result["groups"]) * 60 + 60),
        plot_bgcolor="white", margin={"l": 10, "r": 10, "t": 40, "b": 50}
    )
    st.plotly_chart(fig, width="stretch")


def _render_funnel_tab(studies, effect_measure):
    """渲染漏斗图"""
    if len(studies) < 3:
        st.info("💡 需要至少3篇研究才能生成有意义的漏斗图。")
        return

    funnel = compute_funnel_plot_data(studies, effect_measure)
    import plotly.graph_objects as go

    fig = go.Figure()
    for fl in funnel["funnel_lines"]:
        fig.add_trace(go.Scatter(
            x=[fl["ci_lower"], fl["ci_upper"]],
            y=[fl["se"], fl["se"]],
            mode="lines",
            line={"color": "rgba(0,0,0,0.1)", "width": 1},
            showlegend=False, hoverinfo="skip"
        ))

    se_range = [0, funnel["max_se"]]
    fig.add_trace(go.Scatter(
        x=[funnel["center"], funnel["center"]],
        y=[0, funnel["max_se"]],
        mode="lines", line={"color": "red", "width": 1.5, "dash": "dash"},
        name="合并效应量", showlegend=True
    ))

    for p in funnel["points"]:
        fig.add_trace(go.Scatter(
            x=[p["effect"]], y=[p["se"]],
            mode="markers",
            marker={"size": 10, "color": "#2196F3", "line": {"width": 1, "color": "#1565C0"}},
            name=p["author"], showlegend=False,
            hovertemplate=f"<b>{p['author']}</b><br>效应量: {p['effect']:.3f}<br>标准误: {p['se']:.3f}<extra></extra>"
        ))

    fig.update_layout(
        title="<b>漏斗图 (Funnel Plot)</b>",
        xaxis={"title": f"{effect_measure}"},
        yaxis={"title": "标准误 (SE)", "autorange": "reversed"},
        height=400, showlegend=True,
        plot_bgcolor="white", margin={"l": 10, "r": 10, "t": 40, "b": 50}
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Egger's 检验（发表偏倚检验）：**")
    col_e1, col_e2, col_e3 = st.columns(3)
    col_e1.metric("截距 (bias)", f"{funnel['egger_intercept']:.4f}")
    col_e2.metric("截距标准误", f"{funnel['egger_intercept_se']:.4f}")
    col_e3.metric("P值", f"{funnel['egger_p_value']:.4f}")

    if funnel["egger_p_value"] < 0.05:
        st.warning("⚠️ Egger检验显著（P<0.05），提示可能存在发表偏倚。")
    else:
        st.info("✅ Egger检验不显著，未检测到明显发表偏倚。")


def render_meta_analysis_section():
    """Meta 分析子模块"""
    st.subheader("📊 Meta 分析 / 森林图")
    st.caption("支持固定效应和随机效应（DerSimonian-Laird）模型")

    try:
        recommendation = determine_effect_measure(st.session_state.extraction_results)
        st.info(f"**数据特征分析**：{recommendation['reason']}")
    except Exception:
        pass

    col_em, col_model = st.columns([2, 1])
    with col_em:
        effect_measure = st.selectbox(
            "效应量类型",
            ["auto (自动推荐)", "MD", "SMD", "OR", "RR"],
            index=0, key="wiz_meta_em"
        )
    with col_model:
        model_type = st.selectbox(
            "统计模型",
            ["随机效应模型 (DerSimonian-Laird)", "固定效应模型"],
            index=0, key="wiz_meta_model"
        )

    em_map = {"auto (自动推荐)": "auto", "MD": "MD", "SMD": "SMD", "OR": "OR", "RR": "RR"}
    selected_em = em_map.get(effect_measure, "auto")
    is_random = "随机效应" in model_type

    effect_info = []
    for r in st.session_state.extraction_results:
        if "error" not in r and r.get("effect_size_value"):
            effect_info.append(
                f"- {r.get('author_year', r.get('paper', ''))}: "
                f"{r.get('effect_size', '')} = {r.get('effect_size_value', '')}"
            )
    if effect_info:
        with st.expander("📊 查看可用的效应量数据", expanded=False):
            for e in effect_info:
                st.markdown(e)

    if st.button("📊 执行 Meta 分析", type="primary", width="stretch", key="wiz_do_meta"):
        with st.spinner("正在解析效应量数据并进行Meta分析..."):
            if selected_em == "auto":
                try:
                    rec = determine_effect_measure(st.session_state.extraction_results)
                    selected_em = rec["recommended"]
                except Exception:
                    selected_em = "SMD"

            studies, warning = parse_studies_from_extraction(
                st.session_state.extraction_results, selected_em
            )

            if len(studies) < 2:
                st.warning(f"⚠️ 可用数据不足。仅找到 {len(studies)} 篇有效研究。")
                fig_old = generate_meta_analysis_forest(
                    st.session_state.extraction_results, effect_measure=selected_em
                )
                st.plotly_chart(fig_old, width="stretch")
            else:
                model_str = "random" if is_random else "fixed"
                meta_result = compute_meta_analysis(studies, selected_em, model_str)
                st.session_state.meta_result = meta_result
                st.session_state.meta_studies = studies
                st.session_state.meta_em = selected_em
                st.session_state.meta_model = model_str
                meta_data = prepare_meta_data_for_report(meta_result)
                st.session_state.synthesis_results["meta_summary"] = meta_data["meta_summary"]
                st.rerun()

    if st.session_state.get("meta_result"):
        meta_result = st.session_state.meta_result
        studies = st.session_state.get("meta_studies", [])
        selected_em = st.session_state.get("meta_em", "MD")
        model_str = st.session_state.get("meta_model", "random")

        if meta_result.warning:
            st.warning(f"⚠️ {meta_result.warning}")

        st.markdown("**森林图 (Forest Plot)：**")
        fig = _build_forest_plot(meta_result)
        st.plotly_chart(fig, width="stretch")

        r_exp = meta_result.get_expanded()
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        col_m1.metric("纳入研究", meta_result.n_studies)
        col_m2.metric(f"合并{selected_em}", f"{r_exp.pooled_effect:.3f}")
        col_m3.metric("95%CI", f"({r_exp.pooled_ci_lower:.3f}, {r_exp.pooled_ci_upper:.3f})")
        col_m4.metric("I²异质性", f"{meta_result.i_squared:.1f}%")
        col_m5.metric("Z检验P值", f"{meta_result.pooled_p_value:.4f}")

        st.divider()
        tabs = st.tabs(["📊 异质性详情", "🔪 敏感性分析", "🎯 亚组分析", "📈 漏斗图"])
        with tabs[0]:
            _render_heterogeneity_tab(meta_result)
        with tabs[1]:
            _render_sensitivity_tab(studies, selected_em, model_str)
        with tabs[2]:
            _render_subgroup_tab(st.session_state.extraction_results, selected_em, model_str)
        with tabs[3]:
            _render_funnel_tab(studies, selected_em)

        st.divider()
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.download_button("📥 下载Meta分析摘要", meta_result.get_summary_text(),
                               "meta_summary.md", "text/markdown", width="stretch",
                               key="wiz_dl_meta_sum")
        with col_exp2:
            r_code = generate_forest_plot_code(st.session_state.extraction_results)
            st.download_button("📥 下载R代码", r_code, "forest_plot.R", "text/plain",
                               width="stretch", key="wiz_dl_meta_r")

    elif not effect_info:
        st.info("💡 当前数据中未检测到效应量信息。")


def render_alternative_synthesis_section():
    """其他证据总结法子模块"""
    st.subheader("其他证据总结法 (Alternative Synthesis Methods)")
    st.caption("当研究间异质性过大或不适合做Meta分析时使用")

    method_keys = list(ALL_SUMMARY_METHODS.keys())
    method_options = [
        f"{ALL_SUMMARY_METHODS[k]['icon']} {ALL_SUMMARY_METHODS[k]['name']} — {ALL_SUMMARY_METHODS[k]['subtitle']}"
        for k in method_keys
    ]

    selected_method = st.selectbox("选择分析方法", method_options, index=0, key="wiz_alt_method")
    method_key = method_keys[method_options.index(selected_method)]
    method_info = ALL_SUMMARY_METHODS[method_key]
    st.caption(method_info["description"])

    if st.button(f"🚀 生成 {method_info['name']}", type="primary", width="stretch",
                 key="wiz_alt_gen"):
        with st.spinner(f"正在生成 {method_info['name']}..."):
            result = method_info["func"](st.session_state.extraction_results)

        if result["figure"] is not None:
            st.plotly_chart(result["figure"], width="stretch")
        if result["summary"]:
            st.markdown(result["summary"])
        if result["code"]:
            with st.expander("💻 R 代码备选"):
                st.code(result["code"], language="r")

        key = f"alt_synth_{method_key}"
        st.session_state.synthesis_results[key] = result["summary"]

    with st.expander("📖 各方法简要说明"):
        st.markdown("""
        | 方法 | 适用场景 | 优势 |
        |------|---------|------|
        | **Combining P-values** | 各研究报告了P值但效应量不完整 | 利用所有可用信息 |
        | **Harvest Plot** | 展示各研究的样本量和效应方向 | 直观呈现证据格局 |
        | **Effect Direction Plot** | 多个结局指标的比较 | 简洁展示多维度效应方向 |
        | **Vote Counting** | 最简单快捷的总结方式 | 容易理解和执行 |
        | **Box-and-Whisker Plot** | 展示效应量分布 | 看出集中趋势和离散程度 |
        | **Bubble Plot** | 多维度展示（效应量、年份、样本量） | 信息密度大 |
        """)


# ========== 步骤 5: 报告生成 ==========

def render_step_report():
    """报告生成步骤"""
    render_step_header(WIZARD_STEPS[4])

    if not st.session_state.extraction_results:
        render_empty_state(
            "📊",
            "请先完成数据提取",
            "返回前面的步骤完成数据提取后再生成报告",
        )
        return

    report_type = st.radio(
        "选择报告类型",
        ["📄 完整论文初稿", "📄 成果报告 (Product)", "📈 过程报告 (Process)"],
        horizontal=True,
        index=0,
        key="wiz_report_type"
    )

    st.divider()

    session_data = {
        "papers": st.session_state.papers,
        "extraction_results": st.session_state.extraction_results,
        "rob_results": st.session_state.rob_results,
        "synthesis_text": st.session_state.synthesis_results.get("narrative", ""),
        "process_log": st.session_state.process_log,
        "meta_text": st.session_state.synthesis_results.get("meta_summary", ""),
    }

    # ===== 完整论文初稿 =====
    if "完整论文" in report_type:
        st.markdown("### 📝 分步生成完整论文初稿")
        st.caption("AI基于提取数据和合成结果，分章节生成系统评价全文初稿。")

        ref_style = st.selectbox(
            "参考文献格式",
            ["APA 7th (英文)", "GB/T 7714 (中文)"],
            index=0, key="wiz_paper_ref"
        )
        ref_style_key = "apa" if "APA" in ref_style else "chinese"

        if "paper_sections" not in st.session_state:
            st.session_state.paper_sections = {}
        if "paper_step" not in st.session_state:
            st.session_state.paper_step = 0

        steps = [
            ("📋 摘要", "abstract", "中英文结构式摘要+关键词"),
            ("📖 前言", "introduction", "背景→概念→理论→研究空白→目的"),
            ("🔬 方法", "methods", "PICOS→检索→筛选→提取→质量→统计"),
            ("📊 结果", "results", "文献筛选→特征表→Meta分析→GRADE"),
            ("💬 讨论+结论", "discussion", "主要发现→比较→机制→局限→结论"),
        ]

        current_step = st.session_state.paper_step

        # 步骤指示器
        cols = st.columns(len(steps))
        for i, (label, key, _) in enumerate(steps):
            with cols[i]:
                if i < current_step:
                    st.markdown(f"✅ **{label}**")
                elif i == current_step:
                    st.markdown(f"🟢 **{label}**")
                else:
                    st.markdown(f"⏳ {label}")

        st.divider()

        step_label, step_key, step_hint = steps[current_step]
        st.markdown(f"### 第{current_step+1}步：{step_label}")
        st.caption(step_hint)

        existing_content = st.session_state.paper_sections.get(step_key, "")

        col_gen, col_reg = st.columns([1, 1])
        with col_gen:
            if st.button(f"🚀 生成{step_label}", type="primary" if not existing_content else "secondary",
                         width="stretch", key=f"wiz_paper_gen_{step_key}"):
                if st.session_state.api_key:
                    with st.spinner(f"AI正在生成{step_label}..."):
                        if step_key == "abstract":
                            result = generate_paper_abstract(
                                st.session_state.extraction_results, call_llm_func=call_llm
                            )
                            if isinstance(result, dict):
                                content = (
                                    f"**中文摘要**\n\n{result.get('abstract_cn', '')}\n\n"
                                    f"**关键词**：{result.get('keywords_cn', '')}\n\n---\n\n"
                                    f"**Abstract**\n\n{result.get('abstract_en', '')}\n\n"
                                    f"**Keywords**：{result.get('keywords_en', '')}"
                                )
                            else:
                                content = str(result)
                        else:
                            section_func = {
                                "introduction": generate_paper_introduction,
                                "methods": generate_paper_methods,
                                "results": generate_paper_results,
                                "discussion": generate_paper_discussion,
                            }
                            func = section_func.get(step_key)
                            if func:
                                if step_key == "methods":
                                    content = func(
                                        st.session_state.extraction_results,
                                        st.session_state.rob_results, call_llm
                                    )
                                elif step_key == "results":
                                    prisma_data = st.session_state.synthesis_results.get("prisma_data")
                                    grade_text = st.session_state.synthesis_results.get(
                                        "grade_text",
                                        "GRADE评估尚未完成，请参见质量评价部分。"
                                    )
                                    content = func(
                                        st.session_state.extraction_results,
                                        session_data.get("meta_text", ""),
                                        grade_text, prisma_data, call_llm
                                    )
                                else:
                                    content = func(st.session_state.extraction_results, call_llm)
                            else:
                                content = ""
                        if content:
                            st.session_state.paper_sections[step_key] = content
                            st.success(f"✅ {step_label}生成完成！")
                            st.rerun()
                else:
                    st.warning("⚠️ 需配置API Key后方可生成")

        with col_reg:
            if existing_content:
                if st.button("🔄 重新生成", width="stretch", key=f"wiz_paper_regen_{step_key}"):
                    st.session_state.paper_sections[step_key] = ""
                    st.rerun()

        content_to_edit = st.session_state.paper_sections.get(step_key, "")
        if content_to_edit:
            edited = st.text_area(
                f"编辑{step_label}内容", value=content_to_edit, height=400,
                key=f"wiz_paper_edit_{step_key}"
            )
            if edited != content_to_edit:
                st.session_state.paper_sections[step_key] = edited
        else:
            st.info("💡 点击上方「生成」按钮开始生成此章节。也可手动输入。")
            manual_text = st.text_area(
                f"手动输入{step_label}", height=200, key=f"wiz_paper_manual_{step_key}"
            )
            if manual_text:
                st.session_state.paper_sections[step_key] = manual_text
                st.rerun()

        # 论文步骤内导航
        st.divider()
        nav_cols = st.columns([1, 2, 1])
        with nav_cols[0]:
            if current_step > 0:
                if st.button("⬅ 上一步", width="stretch", key="wiz_paper_prev"):
                    st.session_state.paper_step = current_step - 1
                    st.rerun()
        with nav_cols[2]:
            if current_step < len(steps) - 1:
                if st.session_state.paper_sections.get(step_key, ""):
                    if st.button("下一步 ➡", type="primary", width="stretch", key="wiz_paper_next"):
                        st.session_state.paper_step = current_step + 1
                        st.rerun()
                else:
                    st.button("下一步 ➡", disabled=True, width="stretch", key="wiz_paper_next_dis")
            else:
                if st.button("📄 合并全文并下载", type="primary", width="stretch",
                             key="wiz_paper_merge"):
                    all_sections = st.session_state.paper_sections
                    if all_sections:
                        full_text = merge_full_paper(
                            all_sections, st.session_state.extraction_results, ref_style_key
                        )
                        st.session_state.generated_report = full_text
                        st.session_state.report_type = "📄 完整论文初稿"
                        log_operation("生成完整论文初稿", "V3分步生成")
                        st.success("✅ 全文合并完成！")

        filled = sum(1 for k, _, _ in steps if st.session_state.paper_sections.get(k, ""))
        st.caption(f"进度：已生成 {filled}/{len(steps)} 个章节")

        if st.session_state.get("generated_report") and st.session_state.get(
                "report_type") == "📄 完整论文初稿":
            st.divider()
            st.markdown("### 📄 完整论文初稿")

            preview_tab, refs_tab = st.tabs(["📖 报告预览", "📚 参考文献预览"])
            with preview_tab:
                st.markdown(st.session_state.generated_report)
            with refs_tab:
                paper_list = [r for r in st.session_state.extraction_results if "error" not in r]
                if paper_list:
                    refs = format_references(paper_list, style=ref_style_key)
                    for i, ref in enumerate(refs, 1):
                        st.markdown(f"[{i}] {ref}")

            md_bytes = export_to_markdown(st.session_state.generated_report)
            st.download_button(
                "📥 下载完整论文初稿 (.md)", md_bytes,
                f"完整论文初稿_{st.session_state.session_id[:8]}.md",
                "text/markdown", width="stretch", key="wiz_dl_paper"
            )

        return  # 完整论文模式直接返回

    # ===== V2 成果报告 / 过程报告 =====
    ref_style = st.selectbox(
        "选择参考文献格式",
        ["APA 7th (英文)", "GB/T 7714 (中文)"],
        index=0, key="wiz_report_ref"
    )
    ref_style_key = "apa" if "APA" in ref_style else "chinese"

    if st.button("📄 生成成果报告", type="primary", width="stretch", key="wiz_gen_report"):
        with st.spinner("正在生成报告..."):
            if "成果报告" in report_type:
                report = generate_full_report(session_data)
                paper_list = [r for r in st.session_state.extraction_results if "error" not in r]
                refs = format_references(paper_list, style=ref_style_key)
                ref_section = render_references(refs, style=ref_style_key)
                report += "\n\n" + ref_section
            else:
                report = generate_process_report(session_data)

        st.session_state.generated_report = report
        st.session_state.report_type = report_type
        st.session_state.ref_style = ref_style_key
        log_operation("生成报告", report_type)
        st.success("✅ 报告生成完成！")

    # Discussion 生成
    with st.expander("💬 生成 Discussion 部分", expanded=False):
        if st.button("📝 生成 Discussion 大纲", width="stretch", key="wiz_disc_outline"):
            with st.spinner("正在生成Discussion大纲..."):
                outline = generate_discussion_outline(session_data)
                st.session_state.discussion_outline = outline
                st.success("✅ Discussion大纲已生成")

            if st.session_state.api_key:
                ext_result = search_external_evidence(
                    st.session_state.extraction_results, call_llm
                )
                st.session_state.external_evidence = ext_result

        if st.session_state.get("discussion_outline"):
            st.markdown("**Discussion大纲：**")
            st.markdown(st.session_state.discussion_outline)
        if st.session_state.get("external_evidence"):
            st.divider()
            st.markdown("**外部证据比较：**")
            st.markdown(st.session_state.external_evidence)

    st.divider()

    # 文献综述总结
    if st.session_state.get("generated_report"):
        with st.expander("📝 文献综述总结", expanded=False):
            if st.button("🚀 生成文献综述总结", type="primary", width="stretch",
                         key="wiz_lit_summary"):
                if st.session_state.api_key:
                    with st.spinner("AI正在生成文献综述总结段落..."):
                        session_data_for_summary = {
                            "papers": st.session_state.papers,
                            "extraction_results": st.session_state.extraction_results,
                            "synthesis_text": st.session_state.synthesis_results.get("narrative", ""),
                        }
                        summary = generate_literature_summary(
                            session_data_for_summary, call_llm_func=call_llm
                        )
                        st.session_state.literature_summary = summary
                        st.success("✅ 文献综述总结已生成！")
                else:
                    st.warning("⚠️ 需配置API Key后方可生成")

            if st.session_state.get("literature_summary"):
                st.divider()
                st.markdown("**文献综述总结：**")
                st.markdown(st.session_state.literature_summary)

    st.divider()

    # 显示报告
    if st.session_state.get("generated_report"):
        display_report = st.session_state.generated_report

        tab_show, tab_refs = st.tabs(["📖 报告预览", "📚 参考文献预览"])
        with tab_show:
            st.markdown(display_report)

        report_name = "成果报告" if "成果报告" in st.session_state.report_type else "过程报告"
        st.download_button(
            f"📥 下载 {report_name} (.md)",
            export_to_markdown(display_report),
            f"{report_name}_{st.session_state.session_id[:8]}.md",
            "text/markdown", width="stretch", key="wiz_dl_report"
        )

        with tab_refs:
            paper_list = [r for r in st.session_state.extraction_results if "error" not in r]
            if paper_list:
                refs = format_references(paper_list, style=st.session_state.get("ref_style", "apa"))
                for i, ref in enumerate(refs, 1):
                    st.markdown(f"[{i}] {ref}")
    else:
        render_empty_state(
            "📋",
            "点击生成报告",
            "点击上方「生成成果报告」按钮开始",
        )


# ========== Wizard 导航按钮 ==========

def render_wizard_nav():
    """渲染底部导航按钮 — 原生 Streamlit"""
    step = st.session_state.wizard_step
    can_adv, reason = can_advance_from(step)

    st.divider()

    with st.container():
        col_prev, col_info, col_next = st.columns([1, 2, 1])

        with col_prev:
            if step > 1:
                if st.button(":material/arrow_back: 上一步", key="wiz_nav_prev",
                             help=f"返回「{WIZARD_STEPS[step - 2]['name']}」",
                             width="stretch"):
                    st.session_state.wizard_step = step - 1
                    st.rerun()

        with col_info:
            if not can_adv:
                st.caption(f":material/warning: {reason}")

        with col_next:
            if step < len(WIZARD_STEPS):
                if can_adv:
                    if st.button("下一步 :material/arrow_forward:", type="primary",
                                 key="wiz_nav_next", width="stretch",
                                 help=f"进入「{WIZARD_STEPS[step]['name']}」"):
                        st.session_state.wizard_step = step + 1
                        st.rerun()
                else:
                    st.button("下一步 :material/arrow_forward:", disabled=True,
                              key="wiz_nav_next_dis", width="stretch")


# ========== 主函数 ==========

def main():
    """应用主入口"""
    # 侧边栏（API 配置、会话管理）
    render_sidebar()

    # 顶部导航栏（步骤指示器 + 进度条）
    render_topbar()

    # 主内容区
    step = st.session_state.wizard_step

    if step == 1:
        render_step_literature()
    elif step == 2:
        render_step_extraction()
    elif step == 3:
        render_step_quality()
    elif step == 4:
        render_step_synthesis()
    elif step == 5:
        render_step_report()

    # 底部导航
    render_wizard_nav()


if __name__ == "__main__":
    main()
