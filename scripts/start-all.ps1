# AI Auto-ETL 平台启动脚本 (Windows)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Auto-ETL Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "创建 Python 虚拟环境..." -ForegroundColor Yellow
    python -m venv venv
}

# 激活虚拟环境
Write-Host "激活虚拟环境..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# 安装后端依赖
Write-Host "安装后端依赖..." -ForegroundColor Yellow
pip install -r backend\requirements.txt

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  服务启动说明" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "1. 启动 LiteLLM Proxy:" -ForegroundColor White
Write-Host "   litellm --config config.yaml --port 4000" -ForegroundColor Gray
Write-Host ""
Write-Host "2. 启动 Embedding 服务:" -ForegroundColor White
Write-Host "   cd servers && python embedding_server.py" -ForegroundColor Gray
Write-Host ""
Write-Host "3. 启动后端服务:" -ForegroundColor White
Write-Host "   cd backend && uvicorn app.main:app --reload --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "4. 启动前端服务:" -ForegroundColor White
Write-Host "   cd frontend && npm install && npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
