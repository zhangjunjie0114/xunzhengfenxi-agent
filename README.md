# 🧪 循证分析智能体 (Evidence Analysis Agent)

基于 Streamlit 的文献综述辅助工具，帮助护理专业学生完成文献综述的 **上传→提取→评价→合成→报告** 全流程。

## ✨ 功能

| 模块 | 功能 |
|------|------|
| 📄 **文献管理** | 批量上传 PDF，自动解析元数据 |
| 📊 **数据提取** | AI 按标准化模板提取数据，可编辑审核，支持溯源 |
| ✅ **质量评价** | Risk of Bias 评价 + Cochrane 风格可视化图表 |
| 📝 **证据合成** | 研究特征表 / 描述性总结 / 叙事性合成 / Meta 分析 |
| 📋 **报告生成** | 成果报告 + 过程报告，Markdown 导出 |

## 🚀 快速开始

### 方式一：本地运行

```bash
# 1. 安装 Python 3.10+
# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
streamlit run app.py
```

Mac/Linux: `bash run.sh`
Windows: 双击 `run.bat`

### 方式二：Streamlit Cloud 部署

1. 将本仓库 Fork/Clone 到 GitHub
2. 登录 https://streamlit.io/cloud
3. 选择仓库 → Deploy

## ⚙️ API 配置

应用支持四种 LLM 提供商，在左侧边栏配置：

| 提供商 | 需要 API Key | 说明 |
|--------|-------------|------|
| **Claude (Anthropic)** ✅ 推荐 | ✅ | 长上下文能力强 |
| **OpenAI (GPT)** | ✅ | 兼容 GPT-4o |
| **兼容 OpenAI 的第三方** | ✅ | 如 DeepSeek / Qwen |
| **Ollama 本地模型** | ❌ 免费 | 离线运行，速度较慢 |

## 📁 项目结构

```
循证分析应用工具/
├── app.py                 # 主应用
├── requirements.txt       # 依赖清单
├── utils/                 # 工具模块
│   ├── llm_caller.py     # LLM 调用封装
│   ├── pdf_parser.py     # PDF 解析
│   ├── data_extractor.py # 数据提取
│   ├── risk_of_bias.py   # 质量评价
│   ├── synthesis.py      # 证据合成
│   └── report_generator.py # 报告生成
├── templates/             # 提取模板
└── sessions/              # 工作区
```

## 📝 使用流程

1. **上传文献** → 批量上传 PDF
2. **配置 API** → 输入 Key，测试连接
3. **提取数据** → AI 提取，学生审核
4. **质量评价** → AI 评价，学生确认
5. **证据合成** → 生成特征表/总结/森林图
6. **生成报告** → 导出 Markdown

## 📄 许可证

仅供教育研究使用
