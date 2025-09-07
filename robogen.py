#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboGen Flask Web Application
基于nanobanana API的机器人设计工作流交互式页面
"""

import os
import json
import uuid
import base64
import mimetypes
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从配置文件加载配置


def load_config():
    """从config.json加载配置，如果不存在则使用默认值"""
    default_config = {
        "google_api_key": "your_google_api_key_here",
        "model_name": "gemini-2.5-flash-image-preview",
        "secret_key": "your-secret-key-here"
    }

    try:
        config_path = 'config.json'
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        else:
            logger.warning(
                "config.json not found, using default configuration")
            return default_config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return default_config


# 加载配置
config = load_config()

app = Flask(__name__)
app.secret_key = config.get("secret_key", "your-secret-key-here")  # 从配置文件获取密钥

# 配置
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# 确保文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Google Gemini API配置
GOOGLE_API_KEY = config.get("google_api_key")
MODEL_NAME = config.get("model_name", "gemini-2.5-flash-image-preview")

# 从模板文件加载工作流步骤定义


def load_workflow_steps():
    """从templates/prompts.json加载工作流步骤"""
    try:
        prompts_path = os.path.join('templates', 'prompts.json')
        with open(prompts_path, 'r', encoding='utf-8') as f:
            prompts_data = json.load(f)

        # 转换格式以匹配原有的WORKFLOW_STEPS结构
        workflow_steps = {}
        for key, value in prompts_data.items():
            step_num = int(key.split('_')[1])  # 从 'step_1' 提取数字 1
            workflow_steps[step_num] = {
                'title': value['title'],
                'description': value['description'],
                'prompt': value['prompt']
            }

        return workflow_steps
    except Exception as e:
        logger.error(f"Error loading prompts from template: {e}")
        # 如果加载失败，返回空字典，这样应用仍可运行
        return {}


# 工作流步骤定义
WORKFLOW_STEPS = load_workflow_steps()


class RoboGenAPI:
    """封装nanobanana API的类"""

    def __init__(self, api_key, model_name):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def save_binary_file(self, file_name, data):
        """保存二进制文件"""
        try:
            filepath = os.path.join(app.config['OUTPUT_FOLDER'], file_name)
            with open(filepath, "wb") as f:
                f.write(data)
            logger.info(f"File saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None

    def generate_with_image(self, prompt_text, image_path=None):
        """使用图片和文本生成内容"""
        try:
            parts = [types.Part.from_text(text=prompt_text)]

            # 如果有图片，添加到parts中
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_data = f.read()

                # 检测MIME类型
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type:
                    mime_type = 'image/jpeg'  # 默认

                parts.append(types.Part.from_bytes(
                    data=image_data,
                    mime_type=mime_type
                ))

            contents = [types.Content(role="user", parts=parts)]

            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )

            text_response = ""
            generated_files = []
            file_index = 0

            for chunk in self.client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=generate_content_config,
            ):
                if (chunk.candidates is None or
                    chunk.candidates[0].content is None or
                        chunk.candidates[0].content.parts is None):
                    continue

                # 遍历所有parts来处理不同类型的内容
                for part in chunk.candidates[0].content.parts:
                    # 处理生成的图片
                    if (hasattr(part, 'inline_data') and part.inline_data and
                            hasattr(part.inline_data, 'data') and part.inline_data.data):

                        logger.info(f"Found image data in response - MIME type: {part.inline_data.mime_type}")
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"generated_step_{file_index}_{timestamp}"

                        inline_data = part.inline_data
                        data_buffer = inline_data.data
                        file_extension = mimetypes.guess_extension(
                            inline_data.mime_type)

                        if file_extension:
                            full_filename = f"{file_name}{file_extension}"
                            saved_path = self.save_binary_file(
                                full_filename, data_buffer)
                            if saved_path:
                                generated_files.append(saved_path)
                                logger.info(f"Successfully saved image: {saved_path}")

                        file_index += 1
                    
                    # 处理文本响应
                    elif hasattr(part, 'text') and part.text:
                        text_response += part.text
                        logger.debug(f"Added text content: {part.text[:100]}...")
                
                # 兼容旧的文本处理方式
                if hasattr(chunk, 'text') and chunk.text:
                    text_response += chunk.text
                    logger.debug(f"Added chunk text: {chunk.text[:100]}...")

            logger.info(f"Generation complete - Text length: {len(text_response)}, Files generated: {len(generated_files)}")
            
            return {
                'success': True,
                'text': text_response,
                'files': generated_files
            }

        except Exception as e:
            logger.error(f"Error in generate_with_image: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# 初始化API
robogen_api = RoboGenAPI(GOOGLE_API_KEY, MODEL_NAME)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """主页"""
    return render_template('index.html', workflow_steps=WORKFLOW_STEPS)


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    if 'file' not in request.files:
        flash('没有选择文件')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('没有选择文件')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 添加时间戳避免文件名冲突
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath
        })
    else:
        return jsonify({
            'success': False,
            'error': '不支持的文件格式'
        })


@app.route('/process_step', methods=['POST'])
def process_step():
    """处理工作流步骤"""
    try:
        data = request.get_json()
        step_number = data.get('step')
        image_path = data.get('image_path')

        if step_number not in WORKFLOW_STEPS:
            return jsonify({
                'success': False,
                'error': '无效的步骤号'
            })

        step_config = WORKFLOW_STEPS[step_number]
        prompt = step_config['prompt']

        # 调用API生成内容
        result = robogen_api.generate_with_image(prompt, image_path)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in process_step: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/outputs/<filename>')
def download_file(filename):
    """下载生成的文件"""
    try:
        return send_file(
            os.path.join(app.config['OUTPUT_FOLDER'], filename),
            as_attachment=True
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return "文件不存在", 404


@app.route('/view_output/<filename>')
def view_output(filename):
    """查看生成的图片"""
    try:
        return send_file(
            os.path.join(app.config['OUTPUT_FOLDER'], filename)
        )
    except Exception as e:
        logger.error(f"Error viewing file: {e}")
        return "文件不存在", 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
