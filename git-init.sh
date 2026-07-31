#!/bin/bash
echo "🚀 初始化 Git 仓库并推送到 GitHub"
echo ""

cd "$(dirname "$0")"

git init
git add -A
git commit -m "🎉 初始提交: 循证分析智能体 v1.0"

echo ""
echo "✅ Git 仓库已初始化！"
echo ""
echo "接下来请登录 https://github.com 创建一个新仓库（不要勾选任何初始化选项）"
echo "然后运行以下命令推送："
echo ""
echo "  git remote add origin https://github.com/你的用户名/你的仓库名.git"
echo "  git push -u origin main"
echo ""
