#!/bin/bash

# AI Auto-ETL 平台启动脚本 (Linux/Mac)

echo "========================================"
echo "  AI Auto-ETL Platform"
echo "========================================"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装后端依赖
echo "安装后端依赖..."
pip install -r backend/requirements.txt

echo ""
echo "========================================"
echo "  服务启动说明"
echo "========================================"
echo "1. 启动 LiteLLM Proxy:"
echo "   litellm --config ./config.yaml --port 4000"
echo ""
echo "2. 启动 Embedding 服务:"
echo "   cd servers && python ./servers/embedding_server.py"
echo ""
echo "3. 启动 chroma 数据库"
echo "   chroma run --path ./chroma_data --port 8033 --host 0.0.0.0"
echo ""
echo "4. 启动后端服务:"
echo "   cd backend && uvicorn app.main:app --reload --port 8000"
echo ""
echo "5. 启动前端服务:"
echo "   cd frontend && npm install && npm run dev"
echo ""
echo "========================================"
