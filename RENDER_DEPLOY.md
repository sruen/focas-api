# FOCAS Render 部署说明

## 1. 创建仓库

把本目录提交到 GitHub、GitLab 或 Bitbucket 仓库。Render 官方 Web Service 需要从 Git 仓库、公开 Git URL 或 Docker 镜像部署，不是直接上传 ZIP。

## 2. 创建 Render Web Service

在 Render 控制台选择 `New` -> `Web Service`，连接仓库后填写：

- Runtime / Language: `Python`
- Region: `Singapore`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m focas_api.server`
- Health Check Path: `/health`

## 3. 环境变量

添加：

- `FOCAS_API_KEY`: 自己设置一串密码

Render 会提供公网 HTTPS 地址，例如：

`https://focas-api.onrender.com`

## 4. 验证

部署成功后访问：

`https://你的服务名.onrender.com/health`

正常返回：

```json
{"status":"ok","service":"focas-api","engine_version":"1.1.5"}
```

## 5. GPT Action 调用

GPT Action 认证方式使用 Bearer：

`Authorization: Bearer 你的FOCAS_API_KEY`
