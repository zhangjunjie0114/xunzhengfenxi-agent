"""
循证分析智能体 (Evidence Analysis Agent)
基于Streamlit的文献综述辅助工具
"""
import streamlit as st
import os
import json
import time
from datetime import datetime

# 页面配置必须在最前面
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

# 隐藏所有 Streamlit 原生UI元素
_hide_ui = """
<style>
/* ========== 彻底隐藏所有 Streamlit 原生UI元素 ========== */

/* 隐藏顶层header/工具栏区域 */
header {display: none !important;}
.stApp > header {display: none !important;}
[data-testid="stHeader"] {display: none !important;}

/* 隐藏部署按钮 */
.stDeployButton {display: none !important;}
[data-testid="baseButton-header"] {display: none !important;}

/* 隐藏菜单 */
#MainMenu {display: none !important;}

/* 隐藏工具栏+状态 */
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
[data-testid="stAppViewBlock"] {display: none !important;}
[data-testid="stAppViewContainer"] > section {padding-top: 0 !important;}

/* 隐藏页脚 */
footer {display: none !important;}
[data-testid="stFooter"] {display: none !important;}

/* 隐藏所有带 kind="header" 的按钮 */
button[kind="header"] {display: none !important;}

/* 隐藏所有 data-testid 中包含 "toolbar" 或 "header" 的元素 */
[data-testid*="Toolbar"] {display: none !important;}
[data-testid*="Header"] {display: none !important;}

/* 隐藏全屏、管理应用等所有悬浮按钮 */
button[title*="fullscreen"] {display: none !important;}
button[title*="Manage"] {display: none !important;}
button[title*="管理"] {display: none !important;}
button[aria-label*="fullscreen"] {display: none !important;}

/* 隐藏 Streamlit 品牌水印和社区云入口 */
.stApp a[href*="streamlit"] {display: none !important;}
a[href*="streamlit"] {display: none !important;}
[data-testid="stAppDeployButton"] {display: none !important;}
[data-testid="stAppDeployButtonLink"] {display: none !important;}

/* 隐藏 "Running" / "Complete" 等状态指示条 */
[data-testid="stStatus"] {display: none !important;}
.appview-container .stStatus {display: none !important;}

/* 隐藏连接提示 */
[data-testid="stConnectionStatus"] {display: none !important;}
.stAlert > div[role="alert"] {display: none !important;}

/* 调整主内容区 — 消除顶部空白 */
.appview-container .main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 0 !important;
}
section.main > div:first-child {padding-top: 0 !important;}
.stApp {margin-top: 0 !important;}
.st-emotion-cache-1jicfl2 {padding-top: 0 !important;}

/* 隐藏 Streamlit 生成的所有 iframe 提示 */
iframe[title*="streamlit"] {display: none !important;}

/* 隐藏侧边栏中可能出现的 Streamlit 原生按钮 */
section[data-testid="stSidebar"] button[kind="header"] {display: none !important;}

/* 隐藏所有带 st- 前缀的工具类图标按钮 */
button[class*="st-emotion"] {border: none !important;}
</style>
"""
st.markdown(_hide_ui, unsafe_allow_html=True)

# 导入工具模块
from utils.llm_caller import call_llm, test_connection, PROVIDER_MODELS, DEFAULT_MODELS
from utils.pdf_parser import parse_pdf
from utils.data_extractor import load_template, extract_from_papers, results_to_dataframe
from utils.risk_of_bias import assess_rob, generate_rob_chart, generate_rob_code
from utils.synthesis import (
    generate_study_characteristics_table,
    generate_descriptive_summary,
    generate_narrative_synthesis,
    generate_forest_plot,
    generate_forest_plot_code
)
from utils.report_generator import (
    generate_full_report,
    generate_process_report,
    export_to_markdown,
    add_process_log
)

# ========== 会话状态初始化 ==========
def init_session_state():
    """初始化所有会话状态变量"""
    defaults = {
        "provider": "兼容OpenAI格式的第三方",
        "api_key": "",
        "model": "deepseek-chat",
        "api_base": "https://api.deepseek.com/v1",
        "papers": [],
        "paper_texts": {},
        "extraction_results": [],
        "extraction_template": None,
        "rob_results": [],
        "synthesis_results": {},
        "current_step": 1,
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "process_log": [],
        "initialized": True,
        "connection_status": None,
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


def get_session_dir():
    """获取会话目录"""
    session_dir = os.path.join(os.path.dirname(__file__), "sessions", st.session_state.session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def save_session():
    """保存会话数据到本地"""
    try:
        session_dir = get_session_dir()
        data = {
            "papers": st.session_state.papers,
            "extraction_results": st.session_state.extraction_results,
            "rob_results": st.session_state.rob_results,
            "synthesis_results": st.session_state.synthesis_results,
            "process_log": st.session_state.process_log,
            "session_id": st.session_state.session_id,
        }
        with open(os.path.join(session_dir, "session_data.json"), "w", encoding="utf-8") as f:
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
        st.session_state.session_id = data.get("session_id", "")
        return True
    except Exception as e:
        st.error(f"恢复失败: {e}")
        return False


def log_operation(operation: str, detail: str = ""):
    """记录操作日志"""
    add_process_log(st.__dict__, operation, detail)
    # 同步记录到session_state
    if "process_log" not in st.session_state:
        st.session_state.process_log = []
    st.session_state.process_log.append({
        "time": datetime.now().isoformat(),
        "operation": operation,
        "detail": detail
    })


# ========== 侧边栏 - API配置面板 ==========

def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🧪 循证分析智能体")
        st.caption("Evidence Analysis Agent")

        st.divider()

        # 步骤进度指示
        st.markdown("### 📋 分析进度")
        steps = [
            "1️⃣ 文献上传",
            "2️⃣ 数据提取",
            "3️⃣ 质量评价",
            "4️⃣ 证据合成",
            "5️⃣ 报告生成"
        ]
        current = st.session_state.current_step - 1
        for i, step in enumerate(steps):
            if i < current:
                st.markdown(f"✅ ~~{step}~~")
            elif i == current:
                st.markdown(f"**➡️ {step}**")
            else:
                st.markdown(f"⏳ {step}")

        st.divider()

        # API配置
        with st.expander("⚙️ API 配置", expanded=not bool(st.session_state.api_key)):
            provider = st.selectbox(
                "API 提供商",
                list(PROVIDER_MODELS.keys()),
                index=list(PROVIDER_MODELS.keys()).index(st.session_state.provider)
                if st.session_state.provider in PROVIDER_MODELS else 0,
                key="provider_select",
                help="选择你要使用的大模型服务商；DeepSeek V4 为本机代理模式"
            )
            st.session_state.provider = provider

            # 更新模型列表
            available_models = PROVIDER_MODELS.get(provider, [])
            default_model = DEFAULT_MODELS.get(provider, available_models[0] if available_models else "")

            current_model = st.session_state.model
            if current_model not in available_models:
                current_model = default_model

            model = st.selectbox(
                "模型",
                available_models,
                index=available_models.index(current_model) if current_model in available_models else 0,
                key="model_select"
            )
            st.session_state.model = model

            # API Key
            api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.api_key,
                key="api_key_input",
                help="输入你的API Key（DeepSeek V4本地代理通常可用任意值或PROXY_MANAGED）"
            )
            st.session_state.api_key = api_key

            # 第三方API地址
            if "第三方" in provider or "DeepSeek" in provider:
                api_base = st.text_input(
                    "API 地址",
                    value=st.session_state.api_base or "https://api.deepseek.com/v1",
                    key="api_base_input",
                    help="输入第三方API的完整地址"
                )
                st.session_state.api_base = api_base

            # 测试连接
            if st.button("🔄 测试连接", use_container_width=True, key="test_conn"):
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

        st.divider()

        # 保存/恢复
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存", use_container_width=True):
                if save_session():
                    st.toast("✅ 已保存当前工作")
                    log_operation("保存工作进度")
        with col2:
            if st.button("📂 恢复", use_container_width=True):
                session_dir = os.path.join(os.path.dirname(__file__), "sessions")
                if os.path.exists(session_dir):
                    sessions = [d for d in os.listdir(session_dir)
                                if os.path.isdir(os.path.join(session_dir, d))]
                    if sessions:
                        selected = st.selectbox("选择要恢复的会话", sessions)
                        if st.button("确认恢复"):
                            data_path = os.path.join(session_dir, selected, "session_data.json")
                            if os.path.exists(data_path):
                                if load_session(data_path):
                                    st.success("✅ 恢复成功")
                                    st.rerun()
                    else:
                        st.info("暂无保存的会话")
                else:
                    st.info("暂无保存的会话")

        # 重置
        if st.button("🔄 重置所有数据", use_container_width=True, type="secondary"):
            for key in ["papers", "paper_texts", "extraction_results", "rob_results",
                        "synthesis_results", "process_log"]:
                if key in st.session_state:
                    st.session_state[key] = [] if isinstance(st.session_state[key], list) else {}
            st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.current_step = 1
            st.success("已重置所有数据")
            st.rerun()

        # 当前配置信息
        st.divider()
        st.caption(f"当前模型: {st.session_state.model}")
        st.caption(f"会话ID: {st.session_state.session_id[:16]}...")
        if st.session_state.connection_status == "connected":
            st.caption("✅ API 已连接")
        elif st.session_state.connection_status == "failed":
            st.caption("❌ API 连接失败")


# ========== 主页面 - Tab布局 ==========

def render_tab_literature():
    """文献管理 Tab"""
    st.header("📄 文献管理")
    st.caption("上传已筛选的 PDF 文献全文，系统自动解析元数据")

    # 上传区域
    uploaded_files = st.file_uploader(
        "选择 PDF 文献（支持批量上传）",
        type=["pdf"],
        accept_multiple_files=True,
        help="支持一次选择多篇PDF，每篇不超过20MB"
    )

    if uploaded_files:
        # 获取已处理的文件列表
        processed = set(st.session_state.get("uploaded_files_processed", set()))
        current_names = {f.name for f in uploaded_files}

        # 检查是否有新文件需要处理
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
            st.session_state.uploaded_files_processed = processed
            st.success(f"✅ 已处理 {len(processed)} 篇文献")

    else:
        # 清除上传控件时重置处理状态
        st.session_state.uploaded_files_processed = set()

    st.divider()

    # 文献列表
    if st.session_state.papers:
        st.subheader(f"已上传文献 ({len(st.session_state.papers)} 篇)")

        # 统计
        success_count = sum(1 for p in st.session_state.papers if "✅" in p.get("status", ""))
        fail_count = sum(1 for p in st.session_state.papers if "❌" in p.get("status", ""))
        col1, col2 = st.columns(2)
        col1.metric("解析成功", success_count)
        col2.metric("解析失败", fail_count)

        # 文献列表表格
        for idx, paper in enumerate(st.session_state.papers):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            col1.write(f"**{paper.get('file_name', '未知')}**")
            col2.write(f"页数: {paper.get('pages', '?')}")
            col3.write(paper.get("status", ""))
            if col4.button("删除", key=f"del_{idx}"):
                st.session_state.papers.pop(idx)
                st.rerun()

        # 预览已解析的文献
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
        if clear_col.button("🗑️ 清空所有文献", type="secondary"):
            st.session_state.papers = []
            st.session_state.paper_texts = {}
            st.rerun()
    else:
        st.info("💡 请上传 PDF 格式的文献全文开始分析")


def render_tab_extraction():
    """数据提取 Tab"""
    st.header("📊 数据提取")
    st.caption("AI 按标准化模板逐篇提取文献数据，学生审核修正")

    # 检查是否有文献
    if not st.session_state.papers:
        st.warning("⚠️ 请先在「文献管理」Tab 上传文献")
        return

    # 检查API配置
    if not st.session_state.api_key and "Ollama" not in st.session_state.provider:
        st.warning("⚠️ 请先在左侧边栏配置 API Key")
        return

    # 提取操作
    has_results = len(st.session_state.extraction_results) > 0

    col1, col2 = st.columns(2)
    with col1:
        if not has_results:
            if st.button("🚀 开始提取数据", type="primary", use_container_width=True):
                # 准备文献数据
                papers_data = []
                valid_papers = [p for p in st.session_state.papers if p.get("text")]

                if not valid_papers:
                    st.error("没有可解析的文献文本，请检查文献上传状态")
                    st.stop()

                for p in valid_papers:
                    papers_data.append({
                        "file_name": p.get("file_name", ""),
                        "title": p.get("title", p.get("file_name", "")),
                        "text": p.get("text", "")
                    })

                # 进度显示
                progress_placeholder = st.empty()
                status_text = st.empty()
                st.session_state.progress_placeholder = progress_placeholder
                st.session_state.status_text = status_text

                with st.spinner("AI 正在逐篇提取数据..."):
                    # 使用当前模板（优先用 session_state 中的自定义模板）
                    current_template = st.session_state.extraction_template or load_template(get_template_path())
                    results = extract_from_papers(
                        papers_data,
                        current_template,  # 直接传入模板列表
                        call_llm,
                        progress_callback=progress_callback
                    )

                st.session_state.extraction_results = results
                log_operation("数据提取", f"提取 {len(results)} 篇")
                st.success(f"✅ 提取完成！共处理 {len(results)} 篇文献")
                st.rerun()
        else:
            if st.button("🔄 重新提取", use_container_width=True):
                st.session_state.extraction_results = []
                st.rerun()

    # 模板编辑 - 可视化交互表格
    with col2:
        with st.expander("📋 编辑提取模板", expanded=True):
            st.caption("定义AI提取数据的字段，双击单元格修改，支持增删行")

            # 初始化模板（从文件加载后存入 session_state）
            if st.session_state.extraction_template is None:
                st.session_state.extraction_template = load_template(get_template_path())

            # 将模板转为 DataFrame 展示
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
                use_container_width=True,
                height=300,
                key="template_editor",
                column_config={
                    "序号": st.column_config.NumberColumn("序号", width=50, disabled=True),
                    "字段名": st.column_config.TextColumn("字段名", width=120, help="英文标识，如 author_year"),
                    "显示名称": st.column_config.TextColumn("显示名称", width=120, help="中文显示名"),
                    "提取说明": st.column_config.TextColumn("提取说明", width=300, help="告诉AI提取什么"),
                    "必填": st.column_config.SelectboxColumn("必填", width=60, options=["是", "否"]),
                    "类型": st.column_config.SelectboxColumn("类型", width=70, options=["text", "number", "list"]),
                },
                num_rows="dynamic"
            )

            # 将编辑后的 DataFrame 转回模板格式并存入 session_state
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
            if col_reset.button("🔄 恢复默认模板", use_container_width=True):
                st.session_state.extraction_template = load_template(get_template_path())
                st.rerun()

    st.divider()

    # 显示提取结果
    if has_results:
        template = load_template(get_template_path())

        # 转换为 DataFrame 展示
        df = results_to_dataframe(st.session_state.extraction_results, template)

        st.subheader("📋 提取结果（双击单元格可直接编辑）")

        # 可编辑表格
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            height=400,
            key="extraction_editor",
            disabled=["文献", "状态"]
        )

        # 导出按钮
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 导出 CSV",
                csv,
                "extraction_results.csv",
                "text/csv",
                use_container_width=True
            )
        with col2:
            if st.button("📋 生成 Supplementary Material", use_container_width=True):
                st.info("生成的补充材料可直接作为论文附件")
                st.code(df.to_markdown(index=False), language="markdown")

        st.divider()

        # 溯源查看
        st.subheader("🔍 数据溯源")
        for idx, r in enumerate(st.session_state.extraction_results):
            if "error" in r:
                continue
            with st.expander(f"📄 {r.get('paper', f'文献{idx+1}')}"):
                st.markdown("**提取数据摘要：**")
                for key, val in r.items():
                    if key.startswith("_") or key in ["paper", "file_name"]:
                        continue
                    if val and val != "未报告":
                        st.markdown(f"- **{key}**: {str(val)[:200]}")
                st.divider()

    elif st.session_state.papers:
        st.info("💡 准备好后点击「开始提取数据」按钮")
    else:
        st.info("💡 请先上传文献")


def render_tab_quality():
    """质量评价 Tab"""
    st.header("✅ 质量评价 (Risk of Bias)")
    st.caption("AI 辅助进行偏倚风险评价，生成可视化图表")

    if not st.session_state.extraction_results:
        st.warning("⚠️ 请先在「数据提取」Tab 完成数据提取")
        return

    if not st.session_state.api_key and "Ollama" not in st.session_state.provider:
        st.warning("⚠️ 请先在左侧边栏配置 API Key")
        return

    has_rob = len(st.session_state.rob_results) > 0

    if not has_rob:
        if st.button("🚀 开始质量评价", type="primary", use_container_width=True):
            # 准备数据
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
                st.stop()

            progress_placeholder = st.empty()
            status_text = st.empty()
            st.session_state.progress_placeholder = progress_placeholder
            st.session_state.status_text = status_text

            with st.spinner("AI 正在评价..."):
                results = assess_rob(papers_data, call_llm, progress_callback)

            st.session_state.rob_results = results
            log_operation("质量评价", f"评价 {len(results)} 篇")
            st.success("✅ 质量评价完成！")
            st.rerun()
    else:
        if st.button("🔄 重新评价", use_container_width=True):
            st.session_state.rob_results = []
            st.rerun()

    st.divider()

    # 显示评价结果
    if has_rob:
        # 图表
        st.subheader("📊 偏倚风险总结图")
        fig = generate_rob_chart(st.session_state.rob_results)
        st.plotly_chart(fig, use_container_width=True)

        # 详细评价表格
        st.subheader("📋 详细评价结果")
        for idx, r in enumerate(st.session_state.rob_results):
            with st.expander(f"{'🟢' if r.get('overall')=='low' else '🟡' if r.get('overall')=='unclear' else '🔴'} "
                           f"{r.get('paper_title', f'文献{idx+1}')} "
                           f"(总体: {'低风险' if r.get('overall')=='low' else '高风险' if r.get('overall')=='high' else '不清楚'})"):
                domains = r.get("domains", {})
                for dname, dval in domains.items():
                    if isinstance(dval, dict):
                        judgment = dval.get("judgment", "unclear")
                        evidence = dval.get("evidence", "")
                        icon = {"low": "🟢", "high": "🔴", "unclear": "🟡"}.get(judgment, "🟡")
                        st.markdown(f"{icon} **{dname}**: {judgment}")
                        if evidence:
                            st.caption(f"依据: {evidence[:200]}")
                        st.divider()

        # 导出R代码
        st.subheader("💻 R 代码备选")
        with st.expander("查看 R 语言代码（可在 RStudio 中运行生成图表）"):
            r_code = generate_rob_code(st.session_state.rob_results)
            st.code(r_code, language="r")
            st.download_button(
                "📥 下载 R 代码",
                r_code,
                "rob_plot.R",
                "text/plain",
                use_container_width=True
            )
    else:
        st.info("💡 准备好后点击「开始质量评价」按钮")


def render_tab_synthesis():
    """证据合成 Tab"""
    st.header("📝 证据合成")
    st.caption("生成研究特征表、描述性总结、叙事性合成与 Meta 分析")

    if not st.session_state.extraction_results:
        st.warning("⚠️ 请先在「数据提取」Tab 完成数据提取")
        return

    # 子模块切换
    synth_mode = st.radio(
        "选择合成方式",
        ["📋 研究特征表", "📝 描述性总结", "🔗 叙事性合成", "📊 Meta 分析"],
        horizontal=True,
        key="synth_mode"
    )

    st.divider()

    if synth_mode == "📋 研究特征表":
        st.subheader("研究特征总结表 (Study Characteristics Table)")
        table = generate_study_characteristics_table(st.session_state.extraction_results)
        st.markdown(table)
        st.download_button("📥 下载 Markdown", table, "study_characteristics.md", "text/markdown")

    elif synth_mode == "📝 描述性总结":
        st.subheader("描述性总结 (Descriptive Summary)")
        summary = generate_descriptive_summary(st.session_state.extraction_results)
        st.markdown(summary)
        st.download_button("📥 下载 Markdown", summary, "descriptive_summary.md", "text/markdown")

    elif synth_mode == "🔗 叙事性合成":
        st.subheader("叙事性合成 (Narrative Synthesis)")
        synthesis = generate_narrative_synthesis(
            st.session_state.extraction_results,
            st.session_state.rob_results
        )
        st.markdown(synthesis)
        st.session_state.synthesis_results["narrative"] = synthesis
        st.download_button("📥 下载 Markdown", synthesis, "narrative_synthesis.md", "text/markdown")

    elif synth_mode == "📊 Meta 分析":
        st.subheader("Meta 分析 / 森林图")

        # 效应量建议
        effect_info = []
        for r in st.session_state.extraction_results:
            if "error" not in r and r.get("effect_size_value"):
                effect_info.append(f"- {r.get('paper', '')}: {r.get('effect_size', '')} = {r.get('effect_size_value', '')}")

        if effect_info:
            st.markdown("**可用的效应量数据：**")
            for e in effect_info:
                st.markdown(e)

        # 森林图
        st.markdown("**森林图 (Forest Plot)：**")
        fig = generate_forest_plot(st.session_state.extraction_results)
        st.plotly_chart(fig, use_container_width=True)

        # R代码
        st.markdown("**R 语言代码备选：**")
        with st.expander("查看 R 代码"):
            r_code = generate_forest_plot_code(st.session_state.extraction_results)
            st.code(r_code, language="r")
            st.download_button("📥 下载 R 代码", r_code, "forest_plot.R", "text/plain")

        if not effect_info:
            st.info("💡 提示：如数据中包含效应量信息（OR/RR/MD/SMD 等），可生成更准确的森林图。"
                    "当前默认使用模拟数据进行演示。")

    st.divider()
    st.caption("💡 提示：所有生成的文本建议先由学生审核确认后再用于最终报告。")


def render_tab_report():
    """报告生成 Tab"""
    st.header("📋 报告生成")
    st.caption("生成文献综述成果报告和过程性工作报告")

    if not st.session_state.extraction_results:
        st.warning("⚠️ 请先完成数据提取和证据合成")
        return

    report_type = st.radio(
        "选择报告类型",
        ["📄 成果报告 (Product)", "📈 过程报告 (Process)"],
        horizontal=True
    )

    st.divider()

    # 准备会话数据
    session_data = {
        "papers": st.session_state.papers,
        "extraction_results": st.session_state.extraction_results,
        "rob_results": st.session_state.rob_results,
        "synthesis_text": st.session_state.synthesis_results.get("narrative", ""),
        "process_log": st.session_state.process_log
    }

    if st.button("🚀 生成报告", type="primary", use_container_width=True):
        with st.spinner("正在生成报告..."):
            if "成果报告" in report_type:
                report = generate_full_report(session_data)
            else:
                report = generate_process_report(session_data)

        st.session_state.generated_report = report
        st.session_state.report_type = report_type
        log_operation("生成报告", report_type)
        st.success("✅ 报告生成完成！")

    st.divider()

    # 显示生成的报告
    if st.session_state.get("generated_report"):
        report = st.session_state.generated_report
        st.markdown(report)

        # 下载
        md_bytes = export_to_markdown(report)
        report_name = "成果报告" if "成果报告" in st.session_state.report_type else "过程报告"
        st.download_button(
            f"📥 下载 {report_name} (.md)",
            md_bytes,
            f"{report_name}_{st.session_state.session_id[:8]}.md",
            "text/markdown",
            use_container_width=True
        )

        # PDF 备选提示
        st.info("💡 Markdown 格式可直接粘贴到 Word/Google Docs 中排版。"
                "如需 PDF 格式，可将 Markdown 用 Pandoc 转换。")
    else:
        st.info("💡 点击「生成报告」按钮开始")


# ========== 主布局 ==========

def main():
    """应用主入口"""
    # 侧边栏
    render_sidebar()

    # 主区域
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📄 文献管理",
        "📊 数据提取",
        "✅ 质量评价",
        "📝 证据合成",
        "📋 报告生成"
    ])

    with tab1:
        render_tab_literature()

    with tab2:
        # 更新当前步骤
        if st.session_state.papers:
            st.session_state.current_step = max(st.session_state.current_step, 2)
        render_tab_extraction()

    with tab3:
        if st.session_state.extraction_results:
            st.session_state.current_step = max(st.session_state.current_step, 3)
        render_tab_quality()

    with tab4:
        if st.session_state.rob_results:
            st.session_state.current_step = max(st.session_state.current_step, 4)
        render_tab_synthesis()

    with tab5:
        if st.session_state.synthesis_results:
            st.session_state.current_step = max(st.session_state.current_step, 5)
        render_tab_report()


if __name__ == "__main__":
    main()
