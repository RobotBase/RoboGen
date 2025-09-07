# RoboGen

基于nanobanana API的机器人设计工作流交互式页面。

## 安全配置

为了保护敏感信息，项目采用了以下安全措施：

### 1. 配置文件分离

- 提示词已移动到 `templates/prompts.json` 文件中
- API密钥和敏感配置通过配置文件管理，而不是硬编码

### 2. 设置配置文件

复制配置示例文件并填入你的真实配置：

```bash
cp config.example.json config.json
```

然后编辑 `config.json` 文件，填入你的真实API密钥：

```json
{
    "google_api_key": "你的Google API密钥",
    "model_name": "gemini-2.5-flash-image-preview",
    "secret_key": "你的Flask应用密钥"
}
```

### 3. 环境保护

- `config.json` 文件已添加到 `.gitignore` 中，不会被提交到版本控制
- 敏感的上传和输出文件夹也已被忽略

## 运行应用

```bash
python robogen.py
```

应用将在 `http://localhost:5000` 启动。

## 注意事项

- 请勿将包含真实API密钥的 `config.json` 文件提交到版本控制
- 确保你的 API 密钥具有适当的权限和使用限制
- 定期更换 API 密钥以保证安全
