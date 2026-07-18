import base64
import io
import os
from datetime import datetime

import requests
import streamlit as st
from openai import OpenAI
from PIL import Image


st.set_page_config(
    page_title="GPT Image 迭代生成工具",
    layout="wide"
)


# -----------------------------
# 基础工具函数
# -----------------------------

def get_client(api_key: str, base_url: str):
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/")
    )


def extract_image_bytes(result) -> bytes:
    """
    兼容 b64_json 和 url 两种返回形式。
    """
    item = result.data[0]

    if getattr(item, "b64_json", None):
        return base64.b64decode(item.b64_json)

    if getattr(item, "url", None):
        resp = requests.get(item.url, timeout=120)
        resp.raise_for_status()
        return resp.content

    raise RuntimeError("响应中没有找到 b64_json 或 url")


def bytes_to_named_file(image_bytes: bytes, filename: str = "image.png"):
    """
    OpenAI SDK 的 images.edit 通常需要 file-like object。
    """
    file_obj = io.BytesIO(image_bytes)
    file_obj.name = filename
    file_obj.seek(0)
    return file_obj


def show_image_from_bytes(image_bytes: bytes, caption: str = ""):
    image = Image.open(io.BytesIO(image_bytes))
    st.image(image, caption=caption, use_container_width=True)


def normalize_uploaded_image(uploaded_file) -> bytes:
    """
    将用户上传图片转成 PNG bytes，避免 webp/jpg 等格式在部分网关不兼容。
    """
    image = Image.open(uploaded_file)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


# -----------------------------
# API 调用函数
# -----------------------------

def generate_image(
    client: OpenAI,
    model: str,
    prompt: str,
    size: str,
    quality: str,
    output_format: str,
    background: str | None = None,
):
    kwargs = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": 1,
    }

    if output_format:
        kwargs["output_format"] = output_format

    if background and background != "default":
        kwargs["background"] = background

    result = client.images.generate(**kwargs)
    return extract_image_bytes(result)


def edit_image_with_references(
    client: OpenAI,
    model: str,
    prompt: str,
    image_bytes_list: list[bytes],
    size: str,
    quality: str,
    output_format: str,
):
    """
    使用一张或多张图片作为输入进行编辑。

    image_bytes_list 的顺序很重要：
    - 第 1 张通常放当前主图
    - 后面放参考图

    prompt 里最好明确说明：
    “第一张图是需要修改的主图，后面的图是参考风格/构图/颜色。”
    """

    image_files = []

    for idx, image_bytes in enumerate(image_bytes_list):
        file_obj = bytes_to_named_file(
            image_bytes,
            filename=f"input_{idx + 1}.png"
        )
        image_files.append(file_obj)

    kwargs = {
        "model": model,
        "image": image_files if len(image_files) > 1 else image_files[0],
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": 1,
    }

    if output_format:
        kwargs["output_format"] = output_format

    result = client.images.edit(**kwargs)
    return extract_image_bytes(result)


# -----------------------------
# Session State
# -----------------------------

if "current_image" not in st.session_state:
    st.session_state.current_image = None

if "history" not in st.session_state:
    st.session_state.history = []


# -----------------------------
# 页面
# -----------------------------

st.title("GPT Image 迭代生成工具")

with st.sidebar:
    st.header("API 配置")

    base_url = st.text_input(
        "Base URL",
        value=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="例如：https://api.openai.com/v1 或你的中转网关地址"
    )

    api_key = st.text_input(
        "API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password"
    )

    model = st.text_input(
        "模型名称",
        value=os.getenv("IMAGE_MODEL", "gpt-image-2"),
        help="如果你的服务商实际模型名是 gpt-image-1，就改成 gpt-image-1"
    )

    st.divider()

    size_mode = st.radio(
        "尺寸输入方式",
        ["常用预设", "自定义"],
        index=0,
        horizontal=True,
        help="gpt-image-2 支持自定义像素尺寸（WxH），通常在 1K–4K 范围内",
    )

    if size_mode == "常用预设":
        size = st.selectbox(
            "图片尺寸",
            [
                "1024x1024",
                "1024x1536",
                "1536x1024",
                "2048x2048",
                "2048x1152",
                "1152x2048",
                "3840x2160",
                "2160x3840",
                "auto",
            ],
            index=0
        )
    else:
        size = st.text_input(
            "自定义尺寸 (宽x高)",
            value="1024x1024",
            help="格式：宽x高，例如 1280x720。gpt-image-2 支持 1K–4K 范围内的自定义像素尺寸",
        )

    quality = st.selectbox(
        "质量",
        [
            "low",
            "medium",
            "high",
        ],
        index=1
    )

    output_format = st.selectbox(
        "输出格式",
        [
            "png",
            "jpeg",
            "webp",
        ],
        index=0
    )

    background = st.selectbox(
        "背景",
        [
            "default",
            "transparent",
        ],
        index=0,
        help="不是所有模型或网关都支持 transparent"
    )

    st.divider()

    if st.button("清空当前会话"):
        st.session_state.current_image = None
        st.session_state.history = []
        st.rerun()


if not api_key:
    st.warning("请先在左侧输入 API Key")
    st.stop()


client = get_client(api_key=api_key, base_url=base_url)


left, right = st.columns([1, 1])


# -----------------------------
# 左侧：输入区
# -----------------------------

with left:
    st.subheader("输入需求")

    mode_options = [
        "从零生成新图片",
        "使用参考图生成/编辑",
        "基于当前图片继续修改",
        "基于当前图片 + 参考图继续修改",
    ]

    default_index = 0
    if st.session_state.current_image is not None:
        default_index = 2

    mode = st.radio(
        "选择操作模式",
        mode_options,
        index=default_index
    )

    uploaded_files = st.file_uploader(
        "上传参考图，可多选",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="可以上传风格参考图、商品图、构图参考图、背景参考图等"
    )

    reference_images = []

    if uploaded_files:
        st.caption(f"已上传 {len(uploaded_files)} 张参考图")

        preview_cols = st.columns(min(len(uploaded_files), 3))

        for idx, uploaded_file in enumerate(uploaded_files):
            image_bytes = normalize_uploaded_image(uploaded_file)
            reference_images.append(image_bytes)

            with preview_cols[idx % len(preview_cols)]:
                st.image(
                    Image.open(io.BytesIO(image_bytes)),
                    caption=f"参考图 {idx + 1}",
                    use_container_width=True
                )

    prompt = st.text_area(
        "Prompt / 修改需求",
        height=220,
        placeholder=(
            "例如：第一张图是要修改的主图，后面的图是参考图。"
            "请保持主图中的商品主体不变，参考第二张图的背景风格，"
            "把整体改成高级灰色商业摄影风格，柔和光影，细节清晰。"
        )
    )

    st.info(
        "提示：如果上传了多张图片，建议在 prompt 里明确说明："
        "第一张图是什么、第二张图参考什么、第三张图参考什么。"
    )

    submit = st.button("开始生成 / 编辑", type="primary")

    if submit:
        if not prompt.strip():
            st.error("请输入 prompt")
            st.stop()

        if size != "auto":
            parts = size.lower().split("x")
            if (
                len(parts) != 2
                or not parts[0].isdigit()
                or not parts[1].isdigit()
                or int(parts[0]) <= 0
                or int(parts[1]) <= 0
            ):
                st.error("自定义尺寸格式错误，请使用 宽x高，例如 1280x720")
                st.stop()

        try:
            with st.spinner("正在调用图像模型，请稍等..."):

                # 1. 从零文生图
                if mode == "从零生成新图片":
                    image_bytes = generate_image(
                        client=client,
                        model=model,
                        prompt=prompt,
                        size=size,
                        quality=quality,
                        output_format=output_format,
                        background=background,
                    )

                # 2. 只有参考图，没有当前图
                elif mode == "使用参考图生成/编辑":
                    if not reference_images:
                        st.error("这个模式需要至少上传一张参考图。")
                        st.stop()

                    enhanced_prompt = (
                        "请根据输入图片和用户要求生成结果。"
                        "输入图片均为参考图，可参考其主体、构图、风格、颜色或背景。"
                        "\n\n用户要求：\n"
                        f"{prompt}"
                    )

                    image_bytes = edit_image_with_references(
                        client=client,
                        model=model,
                        prompt=enhanced_prompt,
                        image_bytes_list=reference_images,
                        size=size,
                        quality=quality,
                        output_format=output_format,
                    )

                # 3. 只基于当前图片继续修改
                elif mode == "基于当前图片继续修改":
                    if st.session_state.current_image is None:
                        st.error("当前还没有图片，请先生成一张图。")
                        st.stop()

                    enhanced_prompt = (
                        "第一张图是需要修改的主图。"
                        "请尽量保持主图的主体、构图和身份一致，只按照用户要求进行修改。"
                        "\n\n用户修改要求：\n"
                        f"{prompt}"
                    )

                    image_bytes = edit_image_with_references(
                        client=client,
                        model=model,
                        prompt=enhanced_prompt,
                        image_bytes_list=[st.session_state.current_image],
                        size=size,
                        quality=quality,
                        output_format=output_format,
                    )

                # 4. 当前图 + 参考图
                elif mode == "基于当前图片 + 参考图继续修改":
                    if st.session_state.current_image is None:
                        st.error("当前还没有图片，请先生成一张图。")
                        st.stop()

                    if not reference_images:
                        st.error("这个模式需要至少上传一张参考图。")
                        st.stop()

                    enhanced_prompt = (
                        "输入图片说明：\n"
                        "第 1 张图是需要修改的主图，请保持其主体、结构和核心内容一致。\n"
                        "第 2 张及之后的图片是参考图，只用于参考风格、颜色、背景、材质、构图或局部元素。\n"
                        "不要直接照搬参考图中的无关主体，除非用户明确要求。\n\n"
                        "用户修改要求：\n"
                        f"{prompt}"
                    )

                    image_bytes = edit_image_with_references(
                        client=client,
                        model=model,
                        prompt=enhanced_prompt,
                        image_bytes_list=[
                            st.session_state.current_image,
                            *reference_images
                        ],
                        size=size,
                        quality=quality,
                        output_format=output_format,
                    )

                else:
                    raise RuntimeError(f"未知模式：{mode}")

            st.session_state.current_image = image_bytes

            st.session_state.history.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode,
                "prompt": prompt,
                "image": image_bytes,
                "reference_count": len(reference_images),
            })

            st.success("完成")

        except Exception as e:
            st.exception(e)


# -----------------------------
# 右侧：当前结果
# -----------------------------

with right:
    st.subheader("当前图片")

    if st.session_state.current_image:
        show_image_from_bytes(
            st.session_state.current_image,
            caption="当前版本"
        )

        st.download_button(
            label="下载当前图片",
            data=st.session_state.current_image,
            file_name=f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{output_format}",
            mime=f"image/{output_format}",
        )
    else:
        st.info("还没有生成图片")


# -----------------------------
# 历史版本
# -----------------------------

st.divider()
st.subheader("历史版本")

if not st.session_state.history:
    st.caption("暂无历史记录")
else:
    for idx, item in reversed(list(enumerate(st.session_state.history))):
        with st.expander(
            f"版本 {idx + 1} | {item['time']} | {item['mode']} | 参考图 {item['reference_count']} 张"
        ):
            st.write("Prompt：")
            st.code(item["prompt"], language="text")

            show_image_from_bytes(
                item["image"],
                caption=f"版本 {idx + 1}"
            )

            col1, col2 = st.columns([1, 1])

            with col1:
                if st.button(f"恢复为当前版本 {idx + 1}", key=f"restore_{idx}"):
                    st.session_state.current_image = item["image"]
                    st.rerun()

            with col2:
                st.download_button(
                    label=f"下载版本 {idx + 1}",
                    data=item["image"],
                    file_name=f"image_version_{idx + 1}.{output_format}",
                    mime=f"image/{output_format}",
                    key=f"download_{idx}",
                )
